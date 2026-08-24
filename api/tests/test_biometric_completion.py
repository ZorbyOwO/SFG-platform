"""End-to-end completion tests: seal, upload, then commit; fail closed on upload errors.

These tests exercise /biometric/complete with a real local encrypted store and
real template sealing, against a scripted hosted-store transport.
"""

from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app
from api.services.biometric_core import CoreCVBiometricEngine
from api.services.template_persister import TemplatePersistError
from api.services.template_sealer import (
    NONCE_BYTES,
    open_template_bundle,
    seal_template_bundle,
)
from api.services.template_store import EncryptedTemplateStore


CITIZEN = "11111111-2222-3333-4444-555555555555"
POSES = ("front", "right", "left")
SEAL_KEY = bytes(range(32))


def jpeg_bytes() -> bytes:
    import cv2
    import numpy as np

    ok, buffer = cv2.imencode(".jpg", np.zeros((240, 320, 3), dtype=np.uint8))
    assert ok
    return buffer.tobytes()


@dataclass
class StubResult:
    capture_status: str
    liveness_status: str | None = None
    template: Any | None = None
    diagnostic_code: str | None = None


def real_template(marker: float = 1.0) -> Any:
    import numpy as np

    from api.services.biometric_core import _ensure_importable, default_corecv_root

    _ensure_importable(default_corecv_root())
    from sfg_biometric_core.compatibility import DEFAULT_FINGERPRINT
    from sfg_biometric_core.sface import SFaceTemplate

    values = np.zeros((1, 128), dtype=np.float32)
    values[0, 0] = marker
    return SFaceTemplate.from_array(values, fingerprint=DEFAULT_FINGERPRINT)


class ScriptedPipeline:
    def process_frame(self, frame: Any) -> StubResult:
        return StubResult("CAPTURE_READY", "PAD_LIVE", template=real_template())


class StubVerifier:
    def subject_for(self, access_token: str) -> str:
        if access_token == "citizen-token":
            return CITIZEN
        from api.errors import ApiError

        raise ApiError(401, "invalid_session", "Your session expired. Please sign in again.")


class ScriptedPersister:
    """Records sealed bundles; can be told to fail specific poses.

    Verification of the AAD binding uses the same key file the router used to
    seal, resolved through the settings the app was built with, so an assertion
    here proves the real seal, not a parallel construction.
    """

    def __init__(self) -> None:
        self.bundles: list[tuple[str, str]] = []
        self.generations: list[tuple[str, str, set[str]]] = []
        self.legacy_calls = 0
        self.fail_poses: set[str] = set()
        self.key_resolver: Any = None  # set by env fixture: () -> bytes

    def persist(self, *, citizen_id: str, pose: str, bundle: Any) -> str:
        self.legacy_calls += 1
        if pose in self.fail_poses:
            raise TemplatePersistError("PERSIST_REFUSED")
        opened = open_template_bundle(
            citizen_id=citizen_id,
            pose=pose,
            bundle=bundle,
            key=self.key_resolver(),
        )
        assert isinstance(opened, str) and len(opened) > 0
        self.bundles.append((citizen_id, pose))
        return f"hosted-{pose}-{len(self.bundles)}"

    def persist_generation(
        self,
        *,
        citizen_id: str,
        generation_id: str,
        bundles: dict[str, Any],
    ) -> tuple[str, ...]:
        for pose, bundle in bundles.items():
            if pose in self.fail_poses:
                raise TemplatePersistError("PERSIST_REFUSED")
            opened = open_template_bundle(
                citizen_id=citizen_id,
                pose=pose,
                bundle=bundle,
                key=self.key_resolver(),
            )
            assert isinstance(opened, str) and len(opened) > 0
        self.generations.append((citizen_id, generation_id, set(bundles)))
        return tuple(f"hosted-{pose}" for pose in bundles)


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    persister = ScriptedPersister()
    store_key = EncryptedTemplateStore.generate_key()
    key_file = tmp_path / "seal.key"
    settings = replace(Settings.from_env(), app_env="test", biometric_key_file=key_file)
    store = EncryptedTemplateStore(tmp_path / "templates.sqlite3", store_key)
    app = create_app(
        settings,
        kiosk_key=secrets.token_urlsafe(28),
        corecv_engine=CoreCVBiometricEngine(pipeline=ScriptedPipeline(), max_upload_bytes=5_242_880),
        token_verifier=StubVerifier(),
        template_store=store,
        template_persister=persister,
    )
    from api.services.template_store import load_or_create_key

    persister.key_resolver = lambda: load_or_create_key(key_file)
    with TestClient(app) as client:
        yield {"client": client, "persister": persister}


def auth(token: str = "citizen-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def run_full_enrolment(env: dict[str, Any]) -> dict[str, Any]:
    client = env["client"]
    session = client.post("/biometric/session", json={"purpose": "enrol"}, headers=auth()).json()
    for pose in POSES:
        response = client.post(
            "/biometric/capture",
            data={"session_id": session["session_id"], "nonce": session["nonce"], "pose": pose},
            files={"frame": ("capture.jpg", jpeg_bytes(), "image/jpeg")},
            headers=auth(),
        )
        assert response.status_code == 200, response.text
    return session


def test_complete_uploads_one_atomic_generation_then_commits_locally(env: dict[str, Any]) -> None:
    session = run_full_enrolment(env)
    response = env["client"].post(
        "/biometric/complete", json={"session_id": session["session_id"]}, headers=auth()
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enrolment_status"] == "ENROLMENT_COMPLETED"
    assert body["template_status"] == "TEMPLATE_ACTIVE"
    assert body["templates_stored"] == 3
    assert env["persister"].legacy_calls == 0
    assert len(env["persister"].generations) == 1
    citizen_id, generation_id, poses = env["persister"].generations[0]
    assert citizen_id == CITIZEN
    assert len(generation_id) == 36
    assert poses == set(POSES)


def test_upload_failure_blocks_the_local_commit(env: dict[str, Any]) -> None:
    session = run_full_enrolment(env)
    env["persister"].fail_poses = {"left"}
    response = env["client"].post(
        "/biometric/complete", json={"session_id": session["session_id"]}, headers=auth()
    )
    assert response.status_code == 503
    assert response.json()["error"] == "template_upload_failed"


def test_missing_persistence_config_reports_honestly(tmp_path: Path) -> None:
    settings = replace(Settings.from_env(), app_env="test")
    store = EncryptedTemplateStore(tmp_path / "t.sqlite3", EncryptedTemplateStore.generate_key())
    app = create_app(
        settings,
        kiosk_key=secrets.token_urlsafe(28),
        corecv_engine=CoreCVBiometricEngine(pipeline=ScriptedPipeline(), max_upload_bytes=5_242_880),
        token_verifier=StubVerifier(),
        template_store=store,
    )
    with TestClient(app) as client:
        session_response = client.post("/biometric/session", json={"purpose": "enrol"}, headers=auth())
        assert session_response.status_code == 200
        session = session_response.json()
        for pose in POSES:
            capture_response = client.post(
                "/biometric/capture",
                data={"session_id": session["session_id"], "nonce": session["nonce"], "pose": pose},
                files={"frame": ("capture.jpg", jpeg_bytes(), "image/jpeg")},
                headers=auth(),
            )
            assert capture_response.status_code == 200
        complete = client.post(
            "/biometric/complete", json={"session_id": session["session_id"]}, headers=auth()
        )
        assert complete.status_code == 503
        assert complete.json()["error"] == "template_persistence_unavailable"


def test_health_reports_persistence_configuration() -> None:
    settings = replace(Settings.from_env(), app_env="test")
    app = create_app(settings, kiosk_key=secrets.token_urlsafe(28))
    with TestClient(app) as client:
        health = client.get("/health").json()
    assert health["template_persistence"] in {"configured", "unconfigured"}
