"""Trusted live-face identification against the encrypted Supabase gallery."""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from typing import Any

from ..contracts import CaptureStatus, LivenessStatus, MatchStatus
from .biometric_core import CoreCVBiometricEngine, CoreCVUnavailable
from .supabase_kiosk import HostedTemplate
from .template_sealer import (
    ENCRYPTION_VERSION,
    SealedTemplateBundle,
    TemplateSealError,
    open_template_bundle,
)


@dataclass(frozen=True, slots=True, repr=False)
class FaceIdentificationResult:
    capture_status: CaptureStatus
    liveness_status: LivenessStatus | None
    match_status: MatchStatus | None
    citizen_id: str | None = None

    def __repr__(self) -> str:
        return (
            "<FaceIdentificationResult "
            f"capture_status={self.capture_status.value!r} "
            f"liveness_status={self.liveness_status.value if self.liveness_status else None!r} "
            f"match_status={self.match_status.value if self.match_status else None!r}>"
        )


class FaceIdentificationService:
    """Runs live CoreCV capture, authenticated decryption, and protected 1:N."""

    def __init__(
        self,
        *,
        engine: CoreCVBiometricEngine,
        trusted_client: Any,
        template_key: bytes,
        threshold: float,
    ) -> None:
        threshold_value = float(threshold)
        if not math.isfinite(threshold_value):
            raise ValueError("The SFace match threshold must be finite")
        if len(template_key) != 32:
            raise ValueError("The biometric template key must be 32 bytes")
        self._engine = engine
        self._trusted = trusted_client
        self._key = bytes(template_key)
        self._threshold = threshold_value

    def _open(self, record: HostedTemplate) -> Any:
        bundle = SealedTemplateBundle(
            encrypted_payload=record.encrypted_payload,
            nonce=record.nonce,
            compatibility_fingerprint=record.compatibility_fingerprint,
            encryption_version=ENCRYPTION_VERSION,
        )
        sealed = base64.b64decode(record.encrypted_payload, validate=True)
        nonce = base64.b64decode(record.nonce, validate=True)
        if len(sealed) <= 12 or len(nonce) != 12 or sealed[:12] != nonce:
            raise TemplateSealError("TEMPLATE_BUNDLE_MALFORMED")
        payload_base64 = open_template_bundle(
            citizen_id=record.citizen_id,
            pose="front",
            bundle=bundle,
            key=self._key,
        )
        return self._engine.deserialize_protected_template(
            payload_base64,
            record.compatibility_fingerprint,
        )

    def identify(self, image_bytes: bytes, content_type: str | None) -> FaceIdentificationResult:
        verdict = self._engine.analyse_enrolment(image_bytes, content_type)
        if not verdict.accepted:
            return FaceIdentificationResult(
                capture_status=verdict.capture_status,
                liveness_status=verdict.liveness_status,
                match_status=None,
            )

        probe = verdict.protected_template_for_trusted_backend()
        gallery = self._trusted.load_templates()
        if not gallery:
            del probe
            return FaceIdentificationResult(
                CaptureStatus.READY,
                LivenessStatus.LIVE,
                MatchStatus.NO_MATCH,
            )

        candidates: list[tuple[str, Any]] = []
        try:
            for record in gallery:
                if record.capture_pose != "front":
                    raise TemplateSealError("TEMPLATE_POSE_INVALID")
                candidates.append((record.citizen_id, self._open(record)))
            match_status, citizen_id = self._engine.match_1_to_n(
                probe,
                tuple(candidates),
                threshold=self._threshold,
            )
        except (TemplateSealError, CoreCVUnavailable, ValueError):
            match_status, citizen_id = MatchStatus.ERROR, None
        finally:
            del probe
            candidates.clear()

        return FaceIdentificationResult(
            CaptureStatus.READY,
            LivenessStatus.LIVE,
            match_status,
            citizen_id if match_status is MatchStatus.CONFIRMED else None,
        )


__all__ = ["FaceIdentificationResult", "FaceIdentificationService"]
