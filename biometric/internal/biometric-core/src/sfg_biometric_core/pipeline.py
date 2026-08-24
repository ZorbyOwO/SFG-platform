"""Fail-closed orchestration of the neutral core stages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from . import (
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


LOGGER = logging.getLogger(__name__)
_CAPTURE_STATUSES = {CAPTURE_READY, NO_FACE, MULTIPLE_FACES, INVALID_CAPTURE, CAMERA_ERROR}
_PAD_STATUSES = {PAD_LIVE, PAD_REJECT, PAD_UNCERTAIN, PAD_ERROR}


@dataclass(frozen=True, repr=False)
class PipelineResult:
    capture_status: str
    liveness_status: str | None = None
    template: Any | None = None
    diagnostic_code: str | None = None

    def __repr__(self) -> str:
        return (
            f"<PipelineResult capture_status={self.capture_status!r} "
            f"liveness_status={self.liveness_status!r} "
            f"template_present={self.template is not None} "
            f"diagnostic_code={self.diagnostic_code!r}>"
        )


class BiometricCorePipeline:
    """Run validated frame -> YuNet -> PAD -> SFace, and nothing else."""

    def __init__(self, *, detector: Any, pad: Any, sface: Any) -> None:
        self.detector = detector
        self.pad = pad
        self.sface = sface

    def process_frame(self, frame: Any) -> PipelineResult:
        try:
            detection = self.detector.detect(frame)
            capture_status = getattr(detection, "capture_status", INVALID_CAPTURE)
            if capture_status not in _CAPTURE_STATUSES:
                LOGGER.warning("biometric_core stage=yunet code=INVALID_CAPTURE_STATUS")
                return PipelineResult(INVALID_CAPTURE, diagnostic_code="YUNET_STATUS_INVALID")
        except Exception:
            LOGGER.warning("biometric_core stage=yunet code=YUNET_RUNTIME_FAILURE")
            return PipelineResult(INVALID_CAPTURE, diagnostic_code="YUNET_RUNTIME_FAILURE")

        face = getattr(detection, "face", None)
        if capture_status != CAPTURE_READY or face is None:
            return PipelineResult(capture_status=capture_status)

        try:
            liveness = self.pad.assess(frame, face)
            liveness_status = getattr(liveness, "status", PAD_ERROR)
            if liveness_status not in _PAD_STATUSES:
                LOGGER.warning("biometric_core stage=pad code=PAD_STATUS_INVALID")
                return PipelineResult(capture_status, PAD_ERROR, diagnostic_code="PAD_STATUS_INVALID")
        except Exception:
            LOGGER.warning("biometric_core stage=pad code=PAD_RUNTIME_FAILURE")
            return PipelineResult(capture_status, PAD_ERROR, diagnostic_code="PAD_RUNTIME_FAILURE")

        if liveness_status != PAD_LIVE:
            return PipelineResult(capture_status, liveness_status)

        try:
            template = self.sface.template_from_detection(frame, face)
        except Exception:
            LOGGER.warning("biometric_core stage=sface code=SFACE_ERROR")
            return PipelineResult(capture_status, PAD_LIVE, diagnostic_code="SFACE_ERROR")
        if template is None:
            LOGGER.warning("biometric_core stage=sface code=SFACE_TEMPLATE_MISSING")
            return PipelineResult(capture_status, PAD_LIVE, diagnostic_code="SFACE_TEMPLATE_MISSING")
        return PipelineResult(capture_status, PAD_LIVE, template=template)

    def process(self, frame: Any) -> PipelineResult:
        return self.process_frame(frame)


__all__ = ["BiometricCorePipeline", "PipelineResult"]
