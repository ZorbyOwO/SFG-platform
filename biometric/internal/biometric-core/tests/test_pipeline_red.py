from __future__ import annotations

import numpy as np

from sfg_biometric_core import (
    CAPTURE_READY,
    PAD_REJECT,
    BiometricCorePipeline,
    DetectionOutcome,
    FaceDetection,
    LivenessOutcome,
)


class RejectingPAD:
    def assess(self, frame: np.ndarray, face: FaceDetection) -> LivenessOutcome:
        return LivenessOutcome(status=PAD_REJECT)


class Detector:
    def detect(self, frame: np.ndarray) -> DetectionOutcome:
        return DetectionOutcome(
            capture_status=CAPTURE_READY,
            face=FaceDetection(
                box=(1.0, 1.0, 6.0, 6.0),
                landmarks=np.asarray(
                    [[2.0, 3.0], [6.0, 3.0], [4.0, 4.0], [2.5, 6.0], [5.5, 6.0]],
                    dtype=np.float32,
                ),
            ),
        )


class ExplodingSFace:
    called = False

    def template_from_detection(self, frame: np.ndarray, face: FaceDetection):
        self.called = True
        raise AssertionError("SFace must not run after non-live PAD")


def test_pipeline_stops_before_sface_when_pad_rejects() -> None:
    sface = ExplodingSFace()
    result = BiometricCorePipeline(
        detector=Detector(),
        pad=RejectingPAD(),
        sface=sface,
    ).process(np.zeros((8, 8, 3), dtype=np.uint8))

    assert result.capture_status == CAPTURE_READY
    assert result.liveness_status == PAD_REJECT
    assert result.template is None
    assert sface.called is False
