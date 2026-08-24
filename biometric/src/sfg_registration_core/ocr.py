"""Privacy-minimizing OCR boundary with an isolated Paddle worker."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np

from .ic_parser import ICCandidates, normalize_malaysian_ic


LOGGER = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png"}


class ImageValidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    def __repr__(self) -> str:
        return f"<ImageValidationError code={self.code!r}>"


class OCRRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

    def __repr__(self) -> str:
        return f"<OCRRuntimeError code={self.code!r}>"


class CandidateBackend(Protocol):
    def scan(self, image_bytes: bytes, *, media_type: str) -> dict[str, object]: ...


def _detected_media_type(payload: bytes) -> str | None:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def validate_image_bytes(
    image_bytes: bytes,
    *,
    media_type: str,
    max_upload_bytes: int = MAX_UPLOAD_BYTES,
) -> np.ndarray:
    """Validate an in-memory JPEG/PNG without writing it to disk."""

    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise ImageValidationError("MEDIA_TYPE_UNSUPPORTED")
    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ImageValidationError("IMAGE_EMPTY")
    if len(image_bytes) > max_upload_bytes:
        raise ImageValidationError("IMAGE_TOO_LARGE")
    detected = _detected_media_type(image_bytes)
    if detected is None:
        raise ImageValidationError("IMAGE_MALFORMED")
    if detected != media_type:
        raise ImageValidationError("MEDIA_TYPE_MISMATCH")
    try:
        decoded = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        raise ImageValidationError("IMAGE_MALFORMED") from None
    if decoded is None or decoded.ndim != 3 or decoded.shape[2] != 3:
        raise ImageValidationError("IMAGE_MALFORMED")
    height, width = decoded.shape[:2]
    if height <= 0 or width <= 0 or height * width > MAX_IMAGE_PIXELS:
        raise ImageValidationError("IMAGE_DIMENSIONS_INVALID")
    return decoded


def _validated_candidate(payload: Any) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != {"full_name", "ic", "requires_confirmation"}:
        raise OCRRuntimeError("OCR_RESULT_INVALID")
    full_name = payload["full_name"]
    ic = payload["ic"]
    if full_name is not None and (not isinstance(full_name, str) or not full_name.strip()):
        raise OCRRuntimeError("OCR_RESULT_INVALID")
    if ic is not None and (not isinstance(ic, str) or normalize_malaysian_ic(ic) != ic):
        raise OCRRuntimeError("OCR_RESULT_INVALID")
    if payload["requires_confirmation"] is not True:
        raise OCRRuntimeError("OCR_RESULT_INVALID")
    return {"full_name": full_name, "ic": ic, "requires_confirmation": True}


class IsolatedPaddleOCRBackend:
    """Run PaddleOCR in the package's OCR-only Python environment."""

    def __init__(self, *, package_root: Path, timeout_seconds: int = 120) -> None:
        self.package_root = package_root.resolve()
        self.timeout_seconds = timeout_seconds

    @property
    def python_executable(self) -> Path:
        return self.package_root / ".venv-ocr" / "Scripts" / "python.exe"

    def scan(self, image_bytes: bytes, *, media_type: str) -> dict[str, object]:
        python = self.python_executable
        if not python.is_file():
            raise OCRRuntimeError("OCR_RUNTIME_UNAVAILABLE")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.package_root / "src")
        env["PADDLEOCR_LANG"] = env.get("PADDLEOCR_LANG", "en")
        env["PADDLEOCR_MODEL_DIR"] = env.get(
            "PADDLEOCR_MODEL_DIR", str(self.package_root / ".paddleocr-models")
        )
        env["PADDLE_PDX_CACHE_HOME"] = env["PADDLEOCR_MODEL_DIR"]
        env["PADDLE_PDX_MODEL_SOURCE"] = "bos"
        env["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        try:
            completed = subprocess.run(
                [str(python), "-m", "sfg_registration_core.ocr_worker", media_type],
                input=image_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise OCRRuntimeError("OCR_RUNTIME_FAILURE") from None
        if completed.returncode != 0:
            raise OCRRuntimeError("OCR_RUNTIME_FAILURE")
        try:
            payload = json.loads(completed.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OCRRuntimeError("OCR_RESULT_INVALID") from None
        return _validated_candidate(payload)


class OCRService:
    """Validate in memory, delegate OCR, and return only minimal candidates."""

    def __init__(self, *, backend: CandidateBackend) -> None:
        self.backend = backend

    def scan(self, image_bytes: bytes, *, media_type: str) -> dict[str, object]:
        validate_image_bytes(image_bytes, media_type=media_type)
        try:
            result = _validated_candidate(self.backend.scan(image_bytes, media_type=media_type))
        except (ImageValidationError, OCRRuntimeError):
            raise
        except Exception:
            LOGGER.warning("registration_ocr code=OCR_RUNTIME_FAILURE")
            raise OCRRuntimeError("OCR_RUNTIME_FAILURE") from None
        LOGGER.info("registration_ocr code=OCR_CANDIDATES_READY confirmation_required=true")
        return result


__all__ = [
    "ImageValidationError",
    "IsolatedPaddleOCRBackend",
    "MAX_UPLOAD_BYTES",
    "OCRRuntimeError",
    "OCRService",
    "SUPPORTED_MEDIA_TYPES",
    "validate_image_bytes",
]
