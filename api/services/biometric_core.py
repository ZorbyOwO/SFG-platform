"""Trusted in-process adapter over the frozen SFG Shared Biometric Core.

The mother package is consumed, never reimplemented. This module owns only the
platform child's responsibilities: validating an in-memory upload, handing one
BGR frame to the unchanged pipeline, mapping its canonical statuses onto the API
contract, and keeping the resulting template out of every ordinary projection.

Raw frames are transient. They are decoded in memory, passed to the core, and
released before the handler returns. Nothing here writes an image to disk.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ..contracts import CaptureStatus, LivenessStatus, MatchStatus
from ..errors import ApiError


LOGGER = logging.getLogger(__name__)

SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_PIXELS = 20_000_000

_CAPTURE_BY_VALUE = {status.value: status for status in CaptureStatus}
_LIVENESS_BY_VALUE = {status.value: status for status in LivenessStatus}


class CoreCVUnavailable(RuntimeError):
    """Raised when the pinned core cannot be loaded; never silently simulated."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def default_corecv_root() -> Path:
    return Path(__file__).resolve().parents[2] / "biometric"


def _ensure_importable(corecv_root: Path) -> None:
    """Expose the vendored mother and facade without copying their internals."""

    for candidate in (corecv_root / "src", corecv_root / "internal" / "biometric-core" / "src"):
        resolved = str(candidate.resolve())
        if candidate.is_dir() and resolved not in sys.path:
            sys.path.insert(0, resolved)


def _detected_media_type(payload: bytes) -> str | None:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def decode_frame(image_bytes: bytes, content_type: str | None, *, max_upload_bytes: int) -> np.ndarray:
    """Validate an in-memory capture and decode it to a BGR uint8 frame."""

    if content_type not in SUPPORTED_MEDIA_TYPES:
        raise ApiError(415, "invalid_media_type", "Upload a JPEG or PNG capture.")
    if not image_bytes:
        raise ApiError(413, "invalid_capture", "The capture was empty.")
    if len(image_bytes) > max_upload_bytes:
        raise ApiError(413, "invalid_capture", "The capture exceeds the upload limit.")
    if _detected_media_type(image_bytes) != content_type:
        raise ApiError(422, "invalid_capture", "The capture format did not match its declared type.")

    import cv2

    try:
        frame = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        raise ApiError(422, "invalid_capture", "The capture could not be read.") from None
    if frame is None or frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
        raise ApiError(422, "invalid_capture", "The capture could not be read.")
    height, width = frame.shape[:2]
    if height <= 0 or width <= 0 or height * width > MAX_IMAGE_PIXELS:
        raise ApiError(422, "invalid_capture", "The capture dimensions are outside the accepted range.")
    return frame


@dataclass(frozen=True, repr=False)
class CoreCaptureVerdict:
    """Protected capture result; the template is absent from every safe view."""

    capture_status: CaptureStatus
    liveness_status: LivenessStatus | None
    diagnostic_code: str | None
    _template: Any | None = None

    @property
    def template_generated(self) -> bool:
        return self._template is not None

    @property
    def accepted(self) -> bool:
        return (
            self.capture_status is CaptureStatus.READY
            and self.liveness_status is LivenessStatus.LIVE
            and self._template is not None
        )

    def protected_template_for_trusted_backend(self) -> Any | None:
        """Return the sensitive template only at the trusted backend boundary."""

        return self._template

    def safe_payload(self) -> dict[str, str]:
        payload: dict[str, str] = {"capture_status": self.capture_status.value}
        if self.liveness_status is not None:
            payload["liveness_status"] = self.liveness_status.value
        if self.diagnostic_code is not None:
            payload["diagnostic_code"] = self.diagnostic_code
        return payload

    def __repr__(self) -> str:
        return (
            f"<CoreCaptureVerdict capture_status={self.capture_status.value!r} "
            f"liveness_status={self.liveness_status.value if self.liveness_status else None!r} "
            f"template_present={self.template_generated}>"
        )


class CoreCVBiometricEngine:
    """Runs the pinned YuNet -> Silent Face PAD -> SFace pipeline in process."""

    def __init__(self, *, pipeline: Any, max_upload_bytes: int, fingerprint_id: str | None = None) -> None:
        self._pipeline = pipeline
        self._max_upload_bytes = max_upload_bytes
        self._fingerprint_id = fingerprint_id

    @classmethod
    def from_package(
        cls,
        corecv_root: str | Path | None = None,
        *,
        max_upload_bytes: int = 5_242_880,
    ) -> "CoreCVBiometricEngine":
        """Load the vendored frozen core, or fail loudly with a named error."""

        root = Path(corecv_root) if corecv_root is not None else default_corecv_root()
        if not (root / "internal" / "biometric-core" / "src").is_dir():
            raise CoreCVUnavailable("CORECV_PACKAGE_MISSING")
        _ensure_importable(root)
        try:
            from sfg_registration_core import SFGRegistrationCore
        except ImportError:
            raise CoreCVUnavailable("CORECV_IMPORT_FAILED") from None
        try:
            registration = SFGRegistrationCore.from_package(root)
        except Exception as exc:
            LOGGER.warning("biometric_core stage=load code=CORECV_LOAD_FAILED detail=%s", type(exc).__name__)
            raise CoreCVUnavailable("CORECV_LOAD_FAILED") from None
        fingerprint = None
        try:
            fingerprint = registration.biometric.sface.fingerprint.fingerprint_id()
        except Exception:
            fingerprint = None
        return cls(
            pipeline=registration.biometric,
            max_upload_bytes=max_upload_bytes,
            fingerprint_id=fingerprint,
        )

    @property
    def fingerprint_id(self) -> str | None:
        return self._fingerprint_id

    def health(self) -> dict[str, str]:
        state = {
            "yunet": "loaded",
            "sface": "loaded",
            "antispoof": "loaded",
            "adapter": "corecv_in_process",
        }
        if self._fingerprint_id:
            state["compatibility_fingerprint"] = self._fingerprint_id
        return state

    def analyse_enrolment(self, image_bytes: bytes, content_type: str | None) -> CoreCaptureVerdict:
        """Decode one capture, run the frozen core, and release the frame."""

        frame = decode_frame(image_bytes, content_type, max_upload_bytes=self._max_upload_bytes)
        try:
            result = self._pipeline.process_frame(frame)
        except Exception as exc:
            LOGGER.warning("biometric_core stage=pipeline code=CORE_RUNTIME_FAILURE detail=%s", type(exc).__name__)
            return CoreCaptureVerdict(CaptureStatus.INVALID, None, "CORE_RUNTIME_FAILURE")
        finally:
            del frame

        capture_status = _CAPTURE_BY_VALUE.get(getattr(result, "capture_status", ""), CaptureStatus.INVALID)
        raw_liveness = getattr(result, "liveness_status", None)
        liveness_status = _LIVENESS_BY_VALUE.get(raw_liveness) if raw_liveness else None
        diagnostic_code = getattr(result, "diagnostic_code", None)
        template = getattr(result, "template", None)

        if capture_status is not CaptureStatus.READY or liveness_status is not LivenessStatus.LIVE:
            template = None
        return CoreCaptureVerdict(capture_status, liveness_status, diagnostic_code, template)

    def deserialize_protected_template(self, payload_base64: str, fingerprint_id: str) -> Any:
        """Restore a protected template through the frozen mother's serializer."""

        sface = getattr(self._pipeline, "sface", None)
        expected = getattr(sface, "fingerprint", None)
        if expected is None or expected.fingerprint_id() != fingerprint_id:
            raise CoreCVUnavailable("CORECV_COMPATIBILITY_MISMATCH")
        try:
            from sfg_biometric_core.sface import (
                ProtectedTemplateEnvelope,
                deserialize_protected_template,
            )

            envelope = ProtectedTemplateEnvelope(
                payload_base64=payload_base64,
                fingerprint=expected,
            )
            return deserialize_protected_template(envelope, expected_fingerprint=expected)
        except CoreCVUnavailable:
            raise
        except Exception:
            raise CoreCVUnavailable("CORECV_TEMPLATE_INVALID") from None

    def match_1_to_n(
        self,
        probe: Any,
        candidates: tuple[tuple[str, Any], ...],
        *,
        threshold: float,
    ) -> tuple[MatchStatus, str | None]:
        """Run the frozen mother's protected linear 1:N policy."""

        sface = getattr(self._pipeline, "sface", None)
        expected = getattr(sface, "fingerprint", None)
        compare = getattr(sface, "compare", None)
        if expected is None or not callable(compare):
            return MatchStatus.ERROR, None
        try:
            from sfg_biometric_core.sface import TemplateCandidate, match_1_to_n

            protected_candidates = tuple(
                TemplateCandidate(
                    candidate_token=token,
                    template=template,
                    fingerprint=template.fingerprint,
                )
                for token, template in candidates
            )
            outcome = match_1_to_n(
                probe,
                protected_candidates,
                threshold=threshold,
                compare=compare,
                expected_fingerprint=expected,
            )
        except Exception:
            return MatchStatus.ERROR, None
        mapped = {
            MatchStatus.CONFIRMED.value: MatchStatus.CONFIRMED,
            MatchStatus.NO_MATCH.value: MatchStatus.NO_MATCH,
            MatchStatus.AMBIGUOUS.value: MatchStatus.AMBIGUOUS,
            MatchStatus.ERROR.value: MatchStatus.ERROR,
        }.get(outcome.status, MatchStatus.ERROR)
        token = outcome.matched_candidate_token_for_trusted_backend()
        if mapped is not MatchStatus.CONFIRMED or not isinstance(token, str) or not token:
            return mapped, None
        return mapped, token


def seal_template(template: Any, *, corecv_root: str | Path | None = None) -> tuple[str, str]:
    """Serialize a protected template through the frozen core's own envelope.

    Returns the base64 payload and its compatibility fingerprint id. The exact
    512-byte little-endian float32 serialization belongs to the mother; this
    function never reimplements it.
    """

    _ensure_importable(Path(corecv_root) if corecv_root is not None else default_corecv_root())
    try:
        from sfg_biometric_core.sface import serialize_protected_template
    except ImportError:
        raise CoreCVUnavailable("CORECV_IMPORT_FAILED") from None
    envelope = serialize_protected_template(template)
    return envelope.payload_base64, envelope.fingerprint.fingerprint_id()


__all__ = [
    "CoreCaptureVerdict",
    "CoreCVBiometricEngine",
    "CoreCVUnavailable",
    "decode_frame",
    "default_corecv_root",
    "seal_template",
]
