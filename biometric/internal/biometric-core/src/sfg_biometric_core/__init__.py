"""Neutral, in-process SFG Shared Biometric Core public boundary."""

from __future__ import annotations

CAPTURE_READY = "CAPTURE_READY"
NO_FACE = "NO_FACE"
MULTIPLE_FACES = "MULTIPLE_FACES"
INVALID_CAPTURE = "INVALID_CAPTURE"
CAMERA_ERROR = "CAMERA_ERROR"

PAD_LIVE = "PAD_LIVE"
PAD_REJECT = "PAD_REJECT"
PAD_UNCERTAIN = "PAD_UNCERTAIN"
PAD_ERROR = "PAD_ERROR"

MATCH_CONFIRMED = "MATCH_CONFIRMED"
NO_MATCH = "NO_MATCH"
AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
MATCH_ERROR = "MATCH_ERROR"

from .pipeline import BiometricCorePipeline, PipelineResult
from .silent_face_pad import PADResult
from .sface import (
    MatchOutcome,
    ProtectedTemplateEnvelope,
    SFaceEngine,
    SFaceTemplate,
    TemplateCandidate,
    TemplateError,
    deserialize_protected_template,
    deserialize_template,
    match_1_to_n,
    serialize_protected_template,
    serialize_template,
)
from .yunet import DetectionOutcome, FaceDetection, FrameValidation, YuNetDetector, validate_frame

LivenessOutcome = PADResult

__all__ = [
    "AMBIGUOUS_MATCH",
    "BiometricCorePipeline",
    "CAMERA_ERROR",
    "CAPTURE_READY",
    "DetectionOutcome",
    "FaceDetection",
    "FrameValidation",
    "INVALID_CAPTURE",
    "LivenessOutcome",
    "MATCH_CONFIRMED",
    "MATCH_ERROR",
    "MatchOutcome",
    "MULTIPLE_FACES",
    "NO_FACE",
    "NO_MATCH",
    "PAD_ERROR",
    "PAD_LIVE",
    "PAD_REJECT",
    "PAD_UNCERTAIN",
    "PADResult",
    "PipelineResult",
    "ProtectedTemplateEnvelope",
    "SFaceEngine",
    "SFaceTemplate",
    "TemplateCandidate",
    "TemplateError",
    "YuNetDetector",
    "deserialize_protected_template",
    "deserialize_template",
    "match_1_to_n",
    "serialize_protected_template",
    "serialize_template",
    "validate_frame",
]
