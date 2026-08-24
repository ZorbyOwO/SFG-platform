"""Real trusted 1:N orchestration over the unchanged frozen CoreCV mother."""

from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from api.contracts import CaptureStatus, LivenessStatus, MatchStatus
from api.services.biometric_core import (
    CoreCVBiometricEngine,
    _ensure_importable,
    default_corecv_root,
)
from api.services.face_identification import FaceIdentificationService
from api.services.supabase_kiosk import HostedTemplate
from api.services.template_sealer import seal_template_bundle


KEY = bytes(range(32))
CITIZEN_A = "11111111-2222-3333-4444-555555555555"
CITIZEN_B = "aaaaaaaa-2222-3333-4444-555555555555"
GENERATION_A = "66666666-7777-8888-9999-000000000000"
GENERATION_B = "bbbbbbbb-7777-8888-9999-000000000000"


_ensure_importable(default_corecv_root())
from sfg_biometric_core.compatibility import DEFAULT_FINGERPRINT
from sfg_biometric_core.sface import SFaceTemplate, serialize_protected_template


def jpeg_bytes() -> bytes:
    import cv2

    ok, buffer = cv2.imencode(".jpg", np.zeros((240, 320, 3), dtype=np.uint8))
    assert ok
    return buffer.tobytes()


def template(axis: int) -> SFaceTemplate:
    values = np.zeros((1, 128), dtype=np.float32)
    values[0, axis] = 1.0
    return SFaceTemplate.from_array(values, fingerprint=DEFAULT_FINGERPRINT)


@dataclass
class PipelineResult:
    capture_status: str
    liveness_status: str | None = None
    template: Any | None = None
    diagnostic_code: str | None = None


class ScoringSFace:
    fingerprint = DEFAULT_FINGERPRINT

    @staticmethod
    def compare(reference: SFaceTemplate, fresh: SFaceTemplate) -> float:
        return float(np.dot(reference.to_numpy().ravel(), fresh.to_numpy().ravel()))


class Pipeline:
    def __init__(self, result: PipelineResult) -> None:
        self.result = result
        self.sface = ScoringSFace()

    def process_frame(self, frame: np.ndarray) -> PipelineResult:
        return self.result


class TrustedGallery:
    def __init__(self, records: tuple[HostedTemplate, ...]) -> None:
        self.records = records
        self.calls = 0

    def load_templates(self) -> tuple[HostedTemplate, ...]:
        self.calls += 1
        return self.records


def hosted(template_value: SFaceTemplate, citizen_id: str, generation_id: str) -> HostedTemplate:
    envelope = serialize_protected_template(template_value)
    bundle = seal_template_bundle(
        citizen_id=citizen_id,
        pose="front",
        payload_base64=envelope.payload_base64,
        fingerprint_id=envelope.fingerprint.fingerprint_id(),
        key=KEY,
    )
    return HostedTemplate(
        template_id=("99999999-aaaa-bbbb-cccc-" + citizen_id.replace("-", "")[:12]),
        citizen_id=citizen_id,
        capture_pose="front",
        generation_id=generation_id,
        encrypted_payload=bundle.encrypted_payload,
        nonce=bundle.nonce,
        compatibility_fingerprint=bundle.compatibility_fingerprint,
    )


def service(
    records: tuple[HostedTemplate, ...],
    *,
    result: PipelineResult | None = None,
) -> tuple[FaceIdentificationService, TrustedGallery]:
    pipeline = Pipeline(result or PipelineResult("CAPTURE_READY", "PAD_LIVE", template(0)))
    engine = CoreCVBiometricEngine(
        pipeline=pipeline,
        max_upload_bytes=5_242_880,
        fingerprint_id=DEFAULT_FINGERPRINT.fingerprint_id(),
    )
    gallery = TrustedGallery(records)
    return (
        FaceIdentificationService(
            engine=engine,
            trusted_client=gallery,
            template_key=KEY,
            threshold=0.40,
        ),
        gallery,
    )


def test_identify_returns_only_the_unique_matched_citizen() -> None:
    identifier, _ = service(
        (
            hosted(template(0), CITIZEN_A, GENERATION_A),
            hosted(template(1), CITIZEN_B, GENERATION_B),
        )
    )

    result = identifier.identify(jpeg_bytes(), "image/jpeg")

    assert result.capture_status is CaptureStatus.READY
    assert result.liveness_status is LivenessStatus.LIVE
    assert result.match_status is MatchStatus.CONFIRMED
    assert result.citizen_id == CITIZEN_A
    assert not hasattr(result, "score")
    assert "1.0" not in repr(result)


def test_identify_returns_no_match_when_nobody_crosses_the_threshold() -> None:
    identifier, _ = service((hosted(template(1), CITIZEN_B, GENERATION_B),))

    result = identifier.identify(jpeg_bytes(), "image/jpeg")

    assert result.match_status is MatchStatus.NO_MATCH
    assert result.citizen_id is None


def test_identify_rejects_more_than_one_threshold_crossing_as_ambiguous() -> None:
    identifier, _ = service(
        (
            hosted(template(0), CITIZEN_A, GENERATION_A),
            hosted(template(0), CITIZEN_B, GENERATION_B),
        )
    )

    result = identifier.identify(jpeg_bytes(), "image/jpeg")

    assert result.match_status is MatchStatus.AMBIGUOUS
    assert result.citizen_id is None


def test_tampered_hosted_template_fails_closed_without_a_candidate() -> None:
    record = hosted(template(0), CITIZEN_A, GENERATION_A)
    sealed = bytearray(base64.b64decode(record.encrypted_payload))
    sealed[-1] ^= 1
    tampered = replace(record, encrypted_payload=base64.b64encode(sealed).decode("ascii"))
    identifier, _ = service((tampered,))

    result = identifier.identify(jpeg_bytes(), "image/jpeg")

    assert result.match_status is MatchStatus.ERROR
    assert result.citizen_id is None


def test_non_live_capture_never_loads_or_compares_the_gallery() -> None:
    identifier, gallery = service(
        (hosted(template(0), CITIZEN_A, GENERATION_A),),
        result=PipelineResult("CAPTURE_READY", "PAD_REJECT"),
    )

    result = identifier.identify(jpeg_bytes(), "image/jpeg")

    assert result.liveness_status is LivenessStatus.REJECT
    assert result.match_status is None
    assert result.citizen_id is None
    assert gallery.calls == 0
