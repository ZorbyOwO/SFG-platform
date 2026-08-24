from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest

from api.contracts import CaptureStatus, LivenessStatus
from api.errors import ApiError
from api.services.biometric_core import CoreCVBiometricEngine, CoreCVUnavailable, decode_frame


def jpeg_bytes(width: int = 320, height: int = 240) -> bytes:
    import cv2

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode(".jpg", frame)
    assert ok
    return buffer.tobytes()


@dataclass
class StubPipelineResult:
    capture_status: str
    liveness_status: str | None = None
    template: Any | None = None
    diagnostic_code: str | None = None


class StubPipeline:
    """Stands in for the frozen mother, which carries its own test suite."""

    def __init__(self, result: StubPipelineResult) -> None:
        self.result = result
        self.frames_seen: list[tuple[int, ...]] = []

    def process_frame(self, frame: np.ndarray) -> StubPipelineResult:
        self.frames_seen.append(frame.shape)
        return self.result


class StubTemplate:
    def __init__(self) -> None:
        self.fingerprint = type("FP", (), {"fingerprint_id": lambda self: "a18bbbd47a57d14d"})()


def engine_with(result: StubPipelineResult) -> tuple[CoreCVBiometricEngine, StubPipeline]:
    pipeline = StubPipeline(result)
    return CoreCVBiometricEngine(pipeline=pipeline, max_upload_bytes=5_242_880), pipeline


def test_decode_frame_returns_a_bgr_uint8_array(tmp_path: object) -> None:
    frame = decode_frame(jpeg_bytes(), "image/jpeg", max_upload_bytes=5_242_880)

    assert frame.shape == (240, 320, 3)
    assert frame.dtype == np.uint8


def test_decode_frame_rejects_an_unsupported_media_type() -> None:
    with pytest.raises(ApiError) as raised:
        decode_frame(jpeg_bytes(), "image/gif", max_upload_bytes=5_242_880)

    assert raised.value.status_code == 415


def test_decode_frame_rejects_a_declared_type_that_does_not_match_the_bytes() -> None:
    with pytest.raises(ApiError) as raised:
        decode_frame(jpeg_bytes(), "image/png", max_upload_bytes=5_242_880)

    assert raised.value.error == "invalid_capture"


def test_decode_frame_rejects_an_empty_upload() -> None:
    with pytest.raises(ApiError):
        decode_frame(b"", "image/jpeg", max_upload_bytes=5_242_880)


def test_decode_frame_rejects_an_upload_over_the_limit() -> None:
    with pytest.raises(ApiError) as raised:
        decode_frame(jpeg_bytes(), "image/jpeg", max_upload_bytes=8)

    assert raised.value.status_code == 413


def test_decode_frame_rejects_bytes_that_are_not_a_decodable_image() -> None:
    with pytest.raises(ApiError):
        decode_frame(b"\xff\xd8\xff" + b"junk" * 40, "image/jpeg", max_upload_bytes=5_242_880)


def test_a_live_capture_reports_ready_and_holds_a_protected_template() -> None:
    engine, _ = engine_with(StubPipelineResult("CAPTURE_READY", "PAD_LIVE", template=StubTemplate()))

    verdict = engine.analyse_enrolment(jpeg_bytes(), "image/jpeg")

    assert verdict.capture_status is CaptureStatus.READY
    assert verdict.liveness_status is LivenessStatus.LIVE
    assert verdict.template_generated is True
    assert verdict.protected_template_for_trusted_backend() is not None


def test_the_safe_payload_never_carries_a_template_or_embedding() -> None:
    engine, _ = engine_with(StubPipelineResult("CAPTURE_READY", "PAD_LIVE", template=StubTemplate()))

    payload = engine.analyse_enrolment(jpeg_bytes(), "image/jpeg").safe_payload()

    assert set(payload) <= {"capture_status", "liveness_status", "diagnostic_code"}
    assert "template" not in repr(payload).lower()


def test_a_rejected_liveness_result_produces_no_template() -> None:
    engine, _ = engine_with(StubPipelineResult("CAPTURE_READY", "PAD_REJECT"))

    verdict = engine.analyse_enrolment(jpeg_bytes(), "image/jpeg")

    assert verdict.liveness_status is LivenessStatus.REJECT
    assert verdict.template_generated is False
    assert verdict.protected_template_for_trusted_backend() is None


@pytest.mark.parametrize(
    "capture_status,expected",
    [
        ("NO_FACE", CaptureStatus.NO_FACE),
        ("MULTIPLE_FACES", CaptureStatus.MULTIPLE_FACES),
        ("INVALID_CAPTURE", CaptureStatus.INVALID),
        ("CAMERA_ERROR", CaptureStatus.CAMERA_ERROR),
    ],
)
def test_every_failing_capture_status_is_mapped_and_fails_closed(capture_status: str, expected: CaptureStatus) -> None:
    engine, _ = engine_with(StubPipelineResult(capture_status))

    verdict = engine.analyse_enrolment(jpeg_bytes(), "image/jpeg")

    assert verdict.capture_status is expected
    assert verdict.template_generated is False


def test_a_pipeline_crash_is_reported_as_a_closed_camera_error_not_an_exception() -> None:
    class ExplodingPipeline:
        def process_frame(self, frame: np.ndarray) -> None:
            raise RuntimeError("model exploded")

    engine = CoreCVBiometricEngine(pipeline=ExplodingPipeline(), max_upload_bytes=5_242_880)

    verdict = engine.analyse_enrolment(jpeg_bytes(), "image/jpeg")

    assert verdict.capture_status is CaptureStatus.INVALID
    assert verdict.diagnostic_code == "CORE_RUNTIME_FAILURE"
    assert verdict.template_generated is False


def test_health_reports_the_loaded_core_and_its_fingerprint() -> None:
    engine, _ = engine_with(StubPipelineResult("NO_FACE"))

    health = engine.health()

    assert health["adapter"] == "corecv_in_process"
    assert health["yunet"] == "loaded"
    assert health["sface"] == "loaded"
    assert health["antispoof"] == "loaded"


def test_an_unavailable_core_raises_a_named_error_rather_than_pretending_to_work() -> None:
    with pytest.raises(CoreCVUnavailable):
        CoreCVBiometricEngine.from_package("C:/definitely/not/a/real/corecv/path")
