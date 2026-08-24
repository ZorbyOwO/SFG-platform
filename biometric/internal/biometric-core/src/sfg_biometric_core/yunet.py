"""CPU YuNet loading, frame validation, and exactly-one-face enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .compatibility import ModelManifest, validate_asset_path


@dataclass(frozen=True, repr=False)
class FaceDetection:
    box: tuple[float, float, float, float]
    landmarks: np.ndarray
    confidence: float = 1.0

    def as_yunet_row(self) -> np.ndarray:
        row = np.empty((15,), dtype=np.float32)
        row[:4] = self.box
        row[4:14] = np.asarray(self.landmarks, dtype=np.float32).reshape(10)
        row[14] = self.confidence
        return row

    def __repr__(self) -> str:
        return "<FaceDetection validated>"


@dataclass(frozen=True, repr=False)
class FrameValidation:
    ok: bool
    code: str

    def __repr__(self) -> str:
        return f"<FrameValidation ok={self.ok} code={self.code}>"


@dataclass(frozen=True, repr=False)
class DetectionOutcome:
    capture_status: str
    face: FaceDetection | None = None
    diagnostic_code: str | None = None

    def __repr__(self) -> str:
        return f"<DetectionOutcome capture_status={self.capture_status!r} diagnostic_code={self.diagnostic_code!r}>"


def validate_frame(frame: Any) -> FrameValidation:
    if not isinstance(frame, np.ndarray):
        return FrameValidation(False, "FRAME_NOT_NUMPY")
    if frame.ndim != 3:
        return FrameValidation(False, "FRAME_RANK")
    height, width, channels = frame.shape
    if height <= 0 or width <= 0:
        return FrameValidation(False, "FRAME_EMPTY")
    if channels != 3:
        return FrameValidation(False, "FRAME_CHANNELS")
    if frame.dtype != np.uint8:
        return FrameValidation(False, "FRAME_DTYPE")
    return FrameValidation(True, "OK")


def _valid_detection(row: np.ndarray, width: int, height: int) -> FaceDetection | None:
    if row.shape != (15,) or not np.all(np.isfinite(row)):
        return None
    x, y, box_width, box_height = [float(value) for value in row[:4]]
    if box_width <= 0 or box_height <= 0 or x < 0 or y < 0:
        return None
    if x + box_width > width or y + box_height > height:
        return None
    landmarks = np.asarray(row[4:14], dtype=np.float32).reshape(5, 2)
    if np.any(landmarks < 0) or np.any(landmarks[:, 0] > width) or np.any(landmarks[:, 1] > height):
        return None
    if np.unique(landmarks, axis=0).shape[0] < 3:
        return None
    return FaceDetection(
        box=(x, y, box_width, box_height),
        landmarks=np.ascontiguousarray(landmarks, dtype=np.float32),
        confidence=float(row[14]),
    )


def _faces_from_output(output: Any) -> np.ndarray | None:
    faces = output
    if isinstance(output, tuple):
        if len(output) != 2:
            return None
        faces = output[1]
    if faces is None:
        return np.empty((0, 15), dtype=np.float32)
    if not isinstance(faces, np.ndarray):
        return None
    if faces.size == 0:
        return np.empty((0, 15), dtype=np.float32)
    if faces.ndim == 1:
        if faces.shape != (15,):
            return None
        faces = faces.reshape(1, 15)
    if faces.ndim != 2 or faces.shape[1] != 15:
        return None
    return faces


class ModelLoadError(RuntimeError):
    """Safe model-load failure carrying only a stable diagnostic code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class YuNetDetector:
    def __init__(self, *, detector: Any, model_fingerprint: str | None = None) -> None:
        self._detector = detector
        self.model_fingerprint = model_fingerprint

    @classmethod
    def from_model_path(
        cls,
        model_path: str | Path,
        *,
        manifest: ModelManifest | None = None,
        cv2_module: Any | None = None,
    ) -> "YuNetDetector":
        selected = manifest or ModelManifest.default()
        validation = validate_asset_path(model_path, selected.yunet)
        if not validation.ok:
            raise ModelLoadError(validation.code)
        if cv2_module is None:
            import cv2 as cv2_module
        try:
            detector = cv2_module.FaceDetectorYN.create(
                str(model_path),
                "",
                (320, 320),
                0.9,
                0.3,
                5000,
                cv2_module.dnn.DNN_BACKEND_OPENCV,
                cv2_module.dnn.DNN_TARGET_CPU,
            )
        except Exception as exc:
            del exc
            raise ModelLoadError("YUNET_LOAD_FAILED") from None
        return cls(detector=detector, model_fingerprint=selected.yunet.sha256)

    def detect(self, frame: Any) -> DetectionOutcome:
        validation = validate_frame(frame)
        if not validation.ok:
            return DetectionOutcome("INVALID_CAPTURE", diagnostic_code=validation.code)
        height, width = frame.shape[:2]
        try:
            self._detector.setInputSize((int(width), int(height)))
            output = self._detector.detect(frame)
            faces = _faces_from_output(output)
        except Exception as exc:
            del exc
            return DetectionOutcome("INVALID_CAPTURE", diagnostic_code="YUNET_RUNTIME_FAILURE")
        if faces is None:
            return DetectionOutcome("INVALID_CAPTURE", diagnostic_code="YUNET_OUTPUT_SHAPE")
        if faces.shape[0] == 0:
            return DetectionOutcome("NO_FACE")
        if faces.shape[0] > 1:
            if any(_valid_detection(row, width, height) is None for row in faces):
                return DetectionOutcome("INVALID_CAPTURE", diagnostic_code="YUNET_DETECTION_INVALID")
            return DetectionOutcome("MULTIPLE_FACES")
        face = _valid_detection(faces[0], width, height)
        if face is None:
            return DetectionOutcome("INVALID_CAPTURE", diagnostic_code="YUNET_DETECTION_INVALID")
        return DetectionOutcome("CAPTURE_READY", face=face)


__all__ = [
    "DetectionOutcome",
    "FaceDetection",
    "FrameValidation",
    "ModelLoadError",
    "YuNetDetector",
    "validate_frame",
]
