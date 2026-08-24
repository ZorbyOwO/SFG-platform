from __future__ import annotations

import logging

import numpy as np

from sfg_biometric_core import (
    CAPTURE_READY,
    CAMERA_ERROR,
    INVALID_CAPTURE,
    MULTIPLE_FACES,
    NO_FACE,
    PAD_ERROR,
    PAD_LIVE,
    PAD_REJECT,
    PAD_UNCERTAIN,
)
from sfg_biometric_core.pipeline import BiometricCorePipeline, PipelineResult
from sfg_biometric_core.yunet import DetectionOutcome, FaceDetection
from sfg_biometric_core.silent_face_pad import PADResult


def _face() -> FaceDetection:
    return FaceDetection(
        box=(1.0, 1.0, 6.0, 6.0),
        landmarks=np.asarray(
            [[2.0, 3.0], [6.0, 3.0], [4.0, 4.0], [2.5, 6.0], [5.5, 6.0]],
            dtype=np.float32,
        ),
        confidence=0.99,
    )


class Detector:
    def __init__(self, outcome=None, error=None):
        self.outcome = outcome or DetectionOutcome(CAPTURE_READY, _face())
        self.error = error
        self.calls = 0

    def detect(self, frame):
        self.calls += 1
        if self.error:
            raise self.error
        return self.outcome


class PAD:
    def __init__(self, status=PAD_LIVE, error=None):
        self.status = status
        self.error = error
        self.calls = 0

    def assess(self, frame, face):
        self.calls += 1
        if self.error:
            raise self.error
        return PADResult(self.status)


class SFace:
    def __init__(self, result="protected-template", error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def template_from_detection(self, frame, face):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def test_pipeline_short_circuits_no_face_and_multiple_faces() -> None:
    for capture_status in (NO_FACE, MULTIPLE_FACES):
        detector = Detector(DetectionOutcome(capture_status))
        pad = PAD()
        sface = SFace()
        result = BiometricCorePipeline(detector=detector, pad=pad, sface=sface).process_frame(
            np.zeros((8, 8, 3), np.uint8)
        )
        assert result.capture_status == capture_status
        assert result.liveness_status is None
        assert pad.calls == 0
        assert sface.calls == 0


def test_pipeline_stops_for_all_non_live_pad_statuses() -> None:
    for status in (PAD_REJECT, PAD_UNCERTAIN, PAD_ERROR):
        detector = Detector()
        pad = PAD(status)
        sface = SFace()
        result = BiometricCorePipeline(detector=detector, pad=pad, sface=sface).process_frame(
            np.zeros((8, 8, 3), np.uint8)
        )
        assert result.capture_status == CAPTURE_READY
        assert result.liveness_status == status
        assert result.template is None
        assert sface.calls == 0


def test_pipeline_runs_sface_only_for_pad_live() -> None:
    sface = SFace()
    result = BiometricCorePipeline(detector=Detector(), pad=PAD(PAD_LIVE), sface=sface).process_frame(
        np.zeros((8, 8, 3), np.uint8)
    )
    assert result.capture_status == CAPTURE_READY
    assert result.liveness_status == PAD_LIVE
    assert result.template == "protected-template"
    assert sface.calls == 1


def test_pipeline_maps_exceptions_fail_closed_without_exception_leakage(caplog) -> None:
    frame = np.zeros((8, 8, 3), np.uint8)
    detector_error = RuntimeError("candidate=private score=0.99 frame=" + repr(frame))
    with caplog.at_level(logging.WARNING):
        result = BiometricCorePipeline(
            detector=Detector(error=detector_error), pad=PAD(), sface=SFace()
        ).process_frame(frame)
    assert result.capture_status == INVALID_CAPTURE
    assert result.liveness_status is None
    assert "private" not in caplog.text
    assert "0.99" not in caplog.text
    assert "frame=" not in repr(result)

    pad_error = BiometricCorePipeline(
        detector=Detector(), pad=PAD(error=RuntimeError("secret PAD probability")), sface=SFace()
    ).process_frame(frame)
    assert pad_error.liveness_status == PAD_ERROR
    assert pad_error.template is None

    sface_error = BiometricCorePipeline(
        detector=Detector(), pad=PAD(), sface=SFace(error=RuntimeError("secret vector"))
    ).process_frame(frame)
    assert sface_error.capture_status == CAPTURE_READY
    assert sface_error.liveness_status == PAD_LIVE
    assert sface_error.template is None
    assert sface_error.diagnostic_code == "SFACE_ERROR"
    assert "secret" not in repr(sface_error)


def test_pipeline_result_repr_contains_only_canonical_statuses() -> None:
    result = PipelineResult(CAPTURE_READY, PAD_LIVE, template=np.arange(128, dtype=np.float32), diagnostic_code=None)
    text = repr(result)
    assert "CAPTURE_READY" in text and "PAD_LIVE" in text
    assert "127." not in text
    assert "candidate" not in text.lower()


def test_camera_error_is_a_canonical_capture_value() -> None:
    result = PipelineResult(CAMERA_ERROR)
    assert result.capture_status == CAMERA_ERROR
