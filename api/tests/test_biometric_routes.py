from __future__ import annotations

import secrets
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app
from api.services.biometric_core import CoreCVBiometricEngine
from api.services.template_store import EncryptedTemplateStore


CITIZEN = "11111111-2222-3333-4444-555555555555"
OTHER_CITIZEN = "99999999-8888-7777-6666-555555555555"
POSES = ("front", "right", "left")


def jpeg_bytes() -> bytes:
    import cv2

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
    """Build a genuine SFaceTemplate so the real sealing path is exercised."""

    from api.services.biometric_core import _ensure_importable, default_corecv_root

    _ensure_importable(default_corecv_root())
    from sfg_biometric_core.compatibility import DEFAULT_FINGERPRINT
    from sfg_biometric_core.sface import SFaceTemplate

    values = np.zeros((1, 128), dtype=np.float32)
    values[0, 0] = marker
    return SFaceTemplate.from_array(values, fingerprint=DEFAULT_FINGERPRINT)


def StubTemplate() -> Any:  # noqa: N802 - reads as a constructor at call sites
    return real_template()


class ScriptedPipeline:
    """Returns a live capture by default; individual results can be scripted."""

    def __init__(self) -> None:
        self.next_results: list[StubResult] = []

    def queue(self, result: StubResult) -> None:
        self.next_results.append(result)

    def process_frame(self, frame: np.ndarray) -> StubResult:
        if self.next_results:
            return self.next_results.pop(0)
        return StubResult("CAPTURE_READY", "PAD_LIVE", template=StubTemplate())


class StubVerifier:
    def __init__(self) -> None:
        self.tokens = {"citizen-token": CITIZEN, "other-token": OTHER_CITIZEN}

    def subject_for(self, access_token: str) -> str:
        from api.errors import ApiError

        subject = self.tokens.get(access_token)
        if not subject:
            raise ApiError(401, "invalid_session", "Your session expired. Please sign in again.")
        return subject


class StubPersister:
    """Accepts every sealed bundle so completion exercises the full order."""

    def __init__(self) -> None:
        self.bundles: list[tuple[str, str]] = []

    def persist_generation(
        self,
        *,
        citizen_id: str,
        generation_id: str,
        bundles: dict[str, Any],
    ) -> tuple[str, ...]:
        assert len(generation_id) == 36
        self.bundles.extend((citizen_id, pose) for pose in bundles)
        return tuple(f"hosted-{pose}" for pose in bundles)


@pytest.fixture()
def biometric(tmp_path: Path) -> Iterator[dict[str, Any]]:
    pipeline = ScriptedPipeline()
    settings = replace(Settings.from_env(), app_env="test")
    store = EncryptedTemplateStore(tmp_path / "templates.sqlite3", EncryptedTemplateStore.generate_key())
    app = create_app(
        settings,
        kiosk_key=secrets.token_urlsafe(28),
        corecv_engine=CoreCVBiometricEngine(pipeline=pipeline, max_upload_bytes=5_242_880),
        token_verifier=StubVerifier(),
        template_store=store,
        template_persister=StubPersister(),
    )
    with TestClient(app) as client:
        yield {"client": client, "pipeline": pipeline, "store": store}


def auth(token: str = "citizen-token") -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def start_session(client: TestClient, purpose: str = "enrol", token: str = "citizen-token") -> dict[str, Any]:
    response = client.post("/biometric/session", json={"purpose": purpose}, headers=auth(token))
    assert response.status_code == 200, response.text
    return response.json()


def capture(
    client: TestClient, session: dict[str, Any], pose: str, token: str = "citizen-token"
) -> Any:
    return client.post(
        "/biometric/capture",
        data={"session_id": session["session_id"], "nonce": session["nonce"], "pose": pose},
        files={"frame": ("capture.jpg", jpeg_bytes(), "image/jpeg")},
        headers=auth(token),
    )


def capture_all(client: TestClient, session: dict[str, Any]) -> None:
    for pose in POSES:
        response = capture(client, session, pose)
        assert response.status_code == 200, response.text
        assert response.json()["liveness_status"] == "PAD_LIVE"


def test_starting_a_session_returns_the_required_positions(biometric: dict[str, Any]) -> None:
    session = start_session(biometric["client"])

    assert session["required_positions"] == list(POSES)
    assert session["session_id"] and session["nonce"]


def test_an_unauthenticated_caller_cannot_start_a_session(biometric: dict[str, Any]) -> None:
    response = biometric["client"].post("/biometric/session", json={"purpose": "enrol"})

    assert response.status_code == 401


def test_a_forged_token_cannot_start_a_session(biometric: dict[str, Any]) -> None:
    response = biometric["client"].post(
        "/biometric/session", json={"purpose": "enrol"}, headers=auth("forged")
    )

    assert response.status_code == 401


def test_a_live_capture_records_the_pose(biometric: dict[str, Any]) -> None:
    session = start_session(biometric["client"])

    body = capture(biometric["client"], session, "front").json()

    assert body["capture_status"] == "CAPTURE_READY"
    assert body["liveness_status"] == "PAD_LIVE"
    assert body["positions_complete"] == ["front"]


def test_a_capture_response_never_contains_a_template_or_embedding(biometric: dict[str, Any]) -> None:
    session = start_session(biometric["client"])

    body = capture(biometric["client"], session, "front").json()

    assert set(body) == {
        "capture_status",
        "liveness_status",
        "positions_complete",
        "templates_accepted",
        "required_positions",
    }
    assert "facial_template" not in body
    assert "embedding" not in body
    # No field may carry vector values or a serialized template payload.
    for value in body.values():
        assert not isinstance(value, (int, float)) or isinstance(value, bool) or value < 1000
        if isinstance(value, str):
            assert len(value) < 64
        if isinstance(value, list):
            assert all(isinstance(item, str) and len(item) < 32 for item in value)


@pytest.mark.parametrize(
    "result,expected_capture",
    [
        (StubResult("NO_FACE"), "NO_FACE"),
        (StubResult("MULTIPLE_FACES"), "MULTIPLE_FACES"),
        (StubResult("INVALID_CAPTURE"), "INVALID_CAPTURE"),
        (StubResult("CAMERA_ERROR"), "CAMERA_ERROR"),
    ],
)
def test_a_failed_capture_is_reported_without_recording_the_pose(
    biometric: dict[str, Any], result: StubResult, expected_capture: str
) -> None:
    session = start_session(biometric["client"])
    biometric["pipeline"].queue(result)

    body = capture(biometric["client"], session, "front").json()

    assert body["capture_status"] == expected_capture
    assert body["positions_complete"] == []


@pytest.mark.parametrize("liveness", ["PAD_REJECT", "PAD_UNCERTAIN", "PAD_ERROR"])
def test_a_capture_that_fails_liveness_does_not_record_the_pose(
    biometric: dict[str, Any], liveness: str
) -> None:
    session = start_session(biometric["client"])
    biometric["pipeline"].queue(StubResult("CAPTURE_READY", liveness))

    body = capture(biometric["client"], session, "front").json()

    assert body["liveness_status"] == liveness
    assert body["positions_complete"] == []


def test_an_unknown_pose_is_rejected(biometric: dict[str, Any]) -> None:
    session = start_session(biometric["client"])

    response = capture(biometric["client"], session, "upside-down")

    assert response.status_code == 422


def test_a_capture_with_the_wrong_nonce_is_rejected(biometric: dict[str, Any]) -> None:
    session = start_session(biometric["client"])
    session["nonce"] = "not-the-nonce"

    assert capture(biometric["client"], session, "front").status_code == 404


def test_another_citizen_cannot_capture_into_someone_elses_session(biometric: dict[str, Any]) -> None:
    session = start_session(biometric["client"])

    response = capture(biometric["client"], session, "front", token="other-token")

    assert response.status_code == 404


def test_a_non_image_upload_is_rejected(biometric: dict[str, Any]) -> None:
    session = start_session(biometric["client"])

    response = biometric["client"].post(
        "/biometric/capture",
        data={"session_id": session["session_id"], "nonce": session["nonce"], "pose": "front"},
        files={"frame": ("notes.txt", b"this is not an image", "text/plain")},
        headers=auth(),
    )

    assert response.status_code == 415


def test_completing_requires_every_position(biometric: dict[str, Any]) -> None:
    session = start_session(biometric["client"])
    capture(biometric["client"], session, "front")

    response = biometric["client"].post(
        "/biometric/complete", json={"session_id": session["session_id"]}, headers=auth()
    )

    assert response.status_code == 422
    assert response.json()["error"] == "insufficient_templates"


def test_completing_all_positions_activates_the_enrolment(biometric: dict[str, Any]) -> None:
    session = start_session(biometric["client"])
    capture_all(biometric["client"], session)

    body = biometric["client"].post(
        "/biometric/complete", json={"session_id": session["session_id"]}, headers=auth()
    ).json()

    assert body["template_status"] == "TEMPLATE_ACTIVE"
    assert body["templates_stored"] == 3


def test_a_completed_session_cannot_be_replayed(biometric: dict[str, Any]) -> None:
    session = start_session(biometric["client"])
    capture_all(biometric["client"], session)
    biometric["client"].post("/biometric/complete", json={"session_id": session["session_id"]}, headers=auth())

    replay = biometric["client"].post(
        "/biometric/complete", json={"session_id": session["session_id"]}, headers=auth()
    )

    assert replay.status_code == 404


def test_reenrolment_replaces_the_previous_generation_and_keeps_three_active(
    biometric: dict[str, Any],
) -> None:
    client = biometric["client"]
    first = start_session(client)
    capture_all(client, first)
    client.post("/biometric/complete", json={"session_id": first["session_id"]}, headers=auth())

    second = start_session(client, purpose="reenrol")
    capture_all(client, second)
    body = client.post(
        "/biometric/complete", json={"session_id": second["session_id"]}, headers=auth()
    ).json()

    assert body["templates_stored"] == 3


def test_an_abandoned_reenrolment_leaves_the_original_enrolment_intact(
    biometric: dict[str, Any],
) -> None:
    client = biometric["client"]
    first = start_session(client)
    capture_all(client, first)
    client.post("/biometric/complete", json={"session_id": first["session_id"]}, headers=auth())

    second = start_session(client, purpose="reenrol")
    capture(client, second, "front")
    client.post("/biometric/cancel", json={"session_id": second["session_id"]}, headers=auth())

    status = client.get("/biometric/status", headers=auth()).json()

    assert status["templates_stored"] == 3
    assert status["template_status"] == "TEMPLATE_ACTIVE"


def test_status_reports_no_enrolment_before_any_capture(biometric: dict[str, Any]) -> None:
    status = biometric["client"].get("/biometric/status", headers=auth()).json()

    assert status["templates_stored"] == 0
    assert status["template_status"] is None


def test_health_reports_the_real_core_separately_from_the_kiosk_simulator(
    biometric: dict[str, Any]
) -> None:
    health = biometric["client"].get("/health").json()

    assert health["biometric_core"]["state"] == "loaded"
    assert health["biometric_core"]["adapter"] == "corecv_in_process"
    assert health["models"]["adapter"] == "development_simulation"


def test_a_native_api_mode_session_is_accepted_without_the_supabase_verifier(
    biometric: dict[str, Any]
) -> None:
    """`api` data mode authenticates against this tier's own user store."""

    client: TestClient = biometric["client"]
    registration = client.post("/auth/register", json={
        "ic": "880712135423",
        "full_name": "Aisyah Rahman",
        "email": "citizen-880712135423@example.com",
        "password": "Str0ngPassw0rd",
        "password_confirm": "Str0ngPassw0rd",
    })
    assert registration.status_code == 201, registration.text
    native_token = registration.json()["access_token"]

    session = client.post(
        "/biometric/session", json={"purpose": "enrol"}, headers=auth(native_token)
    )

    assert session.status_code == 200, session.text
