"""OpenCV SFace alignment, template representation, and protected matching."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .compatibility import CompatibilityFingerprint, DEFAULT_FINGERPRINT, ModelManifest, validate_asset_path
from .yunet import FaceDetection


class TemplateError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SFaceLoadError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _runtime_fingerprint(manifest: ModelManifest, opencv_version: str) -> CompatibilityFingerprint:
    return DEFAULT_FINGERPRINT.with_change("yunet_model_filename", manifest.yunet.filename).with_change(
        "yunet_model_sha256", manifest.yunet.sha256 or ""
    ).with_change("sface_model_filename", manifest.sface.filename).with_change(
        "sface_model_sha256", manifest.sface.sha256 or ""
    ).with_change("opencv_version", opencv_version)


class SFaceTemplate:
    """Sensitive finite SFace row; its repr never includes vector values."""

    __slots__ = ("_values", "fingerprint")

    def __init__(self, values: np.ndarray, *, fingerprint: CompatibilityFingerprint):
        if not isinstance(values, np.ndarray) or values.dtype != np.float32 or values.shape != (1, 128):
            raise TemplateError("SFACE_TEMPLATE_INVALID")
        if not np.all(np.isfinite(values)):
            raise TemplateError("SFACE_TEMPLATE_NONFINITE")
        self._values = np.ascontiguousarray(values, dtype=np.float32).copy()
        self.fingerprint = fingerprint

    @classmethod
    def from_array(cls, values: np.ndarray, *, fingerprint: CompatibilityFingerprint) -> "SFaceTemplate":
        return cls(values, fingerprint=fingerprint)

    @property
    def shape(self) -> tuple[int, int]:
        return self._values.shape

    @property
    def dtype(self) -> np.dtype:
        return self._values.dtype

    @property
    def is_finite(self) -> bool:
        return bool(np.all(np.isfinite(self._values)))

    def to_numpy(self) -> np.ndarray:
        """Return an explicit protected-processing copy for a trusted caller."""

        return self._values.copy()

    def __repr__(self) -> str:
        return f"<SFaceTemplate shape={self.shape!r} dtype='float32' fingerprint={self.fingerprint.fingerprint_id()!r}>"


class SFaceEngine:
    def __init__(self, *, recognizer: Any, fingerprint: CompatibilityFingerprint, cosine_metric: Any = None) -> None:
        self._recognizer = recognizer
        self.fingerprint = fingerprint
        if cosine_metric is None:
            try:
                import cv2

                cosine_metric = cv2.FaceRecognizerSF_FR_COSINE
            except Exception:
                cosine_metric = 0
        self._cosine_metric = cosine_metric

    @classmethod
    def from_model_path(
        cls,
        model_path: str | Path,
        *,
        manifest: ModelManifest | None = None,
        cv2_module: Any | None = None,
    ) -> "SFaceEngine":
        selected = manifest or ModelManifest.default()
        validation = validate_asset_path(model_path, selected.sface)
        if not validation.ok:
            raise SFaceLoadError(validation.code)
        if cv2_module is None:
            import cv2 as cv2_module
        try:
            recognizer = cv2_module.FaceRecognizerSF.create(
                str(model_path),
                "",
                cv2_module.dnn.DNN_BACKEND_OPENCV,
                cv2_module.dnn.DNN_TARGET_CPU,
            )
            metric = cv2_module.FaceRecognizerSF_FR_COSINE
            version = str(getattr(cv2_module, "__version__", "unknown"))
        except Exception as exc:
            del exc
            raise SFaceLoadError("SFACE_LOAD_FAILED") from None
        return cls(
            recognizer=recognizer,
            fingerprint=_runtime_fingerprint(selected, version),
            cosine_metric=metric,
        )

    def align_crop(self, frame: np.ndarray, face: FaceDetection) -> np.ndarray:
        try:
            aligned = self._recognizer.alignCrop(frame, face.as_yunet_row())
        except Exception as exc:
            del exc
            raise TemplateError("SFACE_ALIGN_FAILED") from None
        if not isinstance(aligned, np.ndarray) or aligned.shape != (112, 112, 3) or aligned.dtype != np.uint8:
            raise TemplateError("SFACE_ALIGN_OUTPUT_INVALID")
        return aligned

    def template_from_detection(self, frame: np.ndarray, face: FaceDetection) -> SFaceTemplate:
        aligned = self.align_crop(frame, face)
        try:
            feature = self._recognizer.feature(aligned)
        except Exception as exc:
            del exc
            raise TemplateError("SFACE_FEATURE_FAILED") from None
        return SFaceTemplate.from_array(feature, fingerprint=self.fingerprint)

    def compare(self, reference: SFaceTemplate, fresh: SFaceTemplate) -> float:
        try:
            reference.fingerprint.require_compatible(self.fingerprint)
            fresh.fingerprint.require_compatible(self.fingerprint)
            score = self._recognizer.match(
                reference.to_numpy(),
                fresh.to_numpy(),
                self._cosine_metric,
            )
            score = float(np.asarray(score).reshape(()))
        except ValueError as exc:
            if str(exc) == "COMPATIBILITY_MISMATCH":
                raise TemplateError("COMPATIBILITY_MISMATCH") from None
            raise TemplateError("SFACE_COMPARE_FAILED") from None
        except Exception as exc:
            del exc
            raise TemplateError("SFACE_COMPARE_FAILED") from None
        if not np.isfinite(score):
            raise TemplateError("SFACE_SCORE_NONFINITE")
        return score


def serialize_template(template: SFaceTemplate) -> bytes:
    values = template.to_numpy()
    payload = np.asarray(values, dtype="<f4", order="C").tobytes(order="C")
    if len(payload) != 512:
        raise TemplateError("SFACE_TEMPLATE_SERIALIZATION_INVALID")
    return payload


def deserialize_template(payload: bytes, *, fingerprint: CompatibilityFingerprint) -> SFaceTemplate:
    if not isinstance(payload, (bytes, bytearray, memoryview)) or len(payload) != 512:
        raise TemplateError("SFACE_TEMPLATE_SERIALIZATION_INVALID")
    try:
        values = np.frombuffer(bytes(payload), dtype="<f4", count=128).reshape(1, 128).copy()
    except (TypeError, ValueError):
        raise TemplateError("SFACE_TEMPLATE_SERIALIZATION_INVALID") from None
    if not np.all(np.isfinite(values)):
        raise TemplateError("SFACE_TEMPLATE_NONFINITE")
    return SFaceTemplate.from_array(values, fingerprint=fingerprint)


@dataclass(frozen=True, repr=False)
class ProtectedTemplateEnvelope:
    payload_base64: str
    fingerprint: CompatibilityFingerprint

    def __repr__(self) -> str:
        return f"<ProtectedTemplateEnvelope fingerprint={self.fingerprint.fingerprint_id()!r} payload=<redacted>>"


def serialize_protected_template(template: SFaceTemplate) -> ProtectedTemplateEnvelope:
    return ProtectedTemplateEnvelope(
        payload_base64=base64.b64encode(serialize_template(template)).decode("ascii"),
        fingerprint=template.fingerprint,
    )


def deserialize_protected_template(
    envelope: ProtectedTemplateEnvelope,
    *,
    expected_fingerprint: CompatibilityFingerprint,
) -> SFaceTemplate:
    if not isinstance(envelope, ProtectedTemplateEnvelope):
        raise TemplateError("SFACE_TEMPLATE_SERIALIZATION_INVALID")
    try:
        envelope.fingerprint.require_compatible(expected_fingerprint)
        payload = base64.b64decode(envelope.payload_base64, validate=True)
    except ValueError as exc:
        if str(exc) == "COMPATIBILITY_MISMATCH":
            raise TemplateError("COMPATIBILITY_MISMATCH") from None
        raise TemplateError("SFACE_TEMPLATE_SERIALIZATION_INVALID") from None
    except (binascii.Error, TypeError):
        raise TemplateError("SFACE_TEMPLATE_SERIALIZATION_INVALID") from None
    return deserialize_template(payload, fingerprint=expected_fingerprint)


@dataclass(frozen=True, repr=False)
class TemplateCandidate:
    candidate_token: Any
    template: SFaceTemplate
    fingerprint: CompatibilityFingerprint

    def __repr__(self) -> str:
        return "<TemplateCandidate protected>"


class MatchOutcome:
    """Protected in-process match result with an explicitly safe projection.

    The unique opaque token is deliberately absent from ``repr`` and from
    ``to_safe_outcome``.  Only trusted backend code should call the named
    accessor; frontend/API serializers receive the safe projection instead.
    """

    __slots__ = ("__status", "__diagnostic_code", "__matched_candidate_token")

    def __init__(
        self,
        status: str,
        diagnostic_code: str | None = None,
        *,
        matched_candidate_token: Any | None = None,
    ) -> None:
        self.__status = status
        self.__diagnostic_code = diagnostic_code
        self.__matched_candidate_token = matched_candidate_token

    @property
    def status(self) -> str:
        return self.__status

    @property
    def diagnostic_code(self) -> str | None:
        return self.__diagnostic_code

    def __repr__(self) -> str:
        return f"<MatchOutcome status={self.status!r}>"

    def matched_candidate_token_for_trusted_backend(self) -> Any | None:
        """Return the unique internal token only at the trusted backend boundary."""

        if self.status != "MATCH_CONFIRMED":
            return None
        return self.__matched_candidate_token

    def to_safe_outcome(self) -> "MatchOutcome":
        """Return a status-only copy suitable for ordinary response mapping."""

        return MatchOutcome(self.status, self.diagnostic_code)


def match_1_to_n(
    fresh: SFaceTemplate,
    candidates: list[TemplateCandidate] | tuple[TemplateCandidate, ...],
    *,
    threshold: float,
    compare: Callable[[SFaceTemplate, SFaceTemplate], float],
    expected_fingerprint: CompatibilityFingerprint | None = None,
) -> MatchOutcome:
    """Return a protected result whose explicit safe projection contains status only."""

    expected = expected_fingerprint or fresh.fingerprint
    try:
        expected.require_compatible(fresh.fingerprint)
        threshold_value = float(threshold)
        if not np.isfinite(threshold_value):
            raise ValueError("THRESHOLD_INVALID")
        for candidate in candidates:
            expected.require_compatible(candidate.fingerprint)
            expected.require_compatible(candidate.template.fingerprint)
    except ValueError as exc:
        code = "COMPATIBILITY_MISMATCH" if str(exc) == "COMPATIBILITY_MISMATCH" else "MATCH_INPUT_INVALID"
        return MatchOutcome("MATCH_ERROR", code)

    crossing = 0
    matched_candidate_token: Any | None = None
    try:
        for candidate in candidates:
            score = float(compare(candidate.template, fresh))
            if not np.isfinite(score):
                return MatchOutcome("MATCH_ERROR", "MATCH_SCORE_NONFINITE")
            if score >= threshold_value:
                crossing += 1
                matched_candidate_token = candidate.candidate_token
                if crossing > 1:
                    return MatchOutcome("AMBIGUOUS_MATCH")
    except Exception:
        return MatchOutcome("MATCH_ERROR", "MATCH_COMPARISON_FAILURE")
    if crossing == 0:
        return MatchOutcome("NO_MATCH")
    return MatchOutcome("MATCH_CONFIRMED", matched_candidate_token=matched_candidate_token)


__all__ = [
    "MatchOutcome",
    "ProtectedTemplateEnvelope",
    "SFaceEngine",
    "SFaceLoadError",
    "SFaceTemplate",
    "TemplateCandidate",
    "TemplateError",
    "deserialize_protected_template",
    "deserialize_template",
    "match_1_to_n",
    "serialize_protected_template",
    "serialize_template",
]
