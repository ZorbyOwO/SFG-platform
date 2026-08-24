"""Public one-package facade over OCR and the exact frozen mother."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sfg_biometric_core.pipeline import BiometricCorePipeline
from sfg_biometric_core.sface import SFaceEngine
from sfg_biometric_core.silent_face_pad import SilentFacePAD
from sfg_biometric_core.yunet import YuNetDetector

from .ocr import IsolatedPaddleOCRBackend, OCRService


@dataclass(frozen=True)
class SafeFaceResult:
    capture_status: str
    liveness_status: str | None
    diagnostic_code: str | None
    template_generated: bool


class SFGRegistrationCore:
    """Single entry point; ``biometric`` is the accepted mother interface."""

    def __init__(self, *, biometric: Any, ocr: Any) -> None:
        self.biometric = biometric
        self._ocr = ocr

    @classmethod
    def from_package(cls, package_root: str | Path | None = None) -> "SFGRegistrationCore":
        root = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[2]
        root = root.resolve()
        config = json.loads((root / "config" / "registration-core.example.json").read_text(encoding="utf-8"))

        def configured_path(name: str) -> Path:
            raw = os.environ.get(name, config[name])
            selected = Path(raw)
            return selected if selected.is_absolute() else (root / selected).resolve()

        detector = YuNetDetector.from_model_path(configured_path("YUNET_MODEL_PATH"))
        pad = SilentFacePAD.from_model_dir(configured_path("PAD_MODEL_DIR"))
        sface = SFaceEngine.from_model_path(configured_path("SFACE_MODEL_PATH"))
        biometric = BiometricCorePipeline(detector=detector, pad=pad, sface=sface)
        ocr = OCRService(backend=IsolatedPaddleOCRBackend(package_root=root))
        return cls(biometric=biometric, ocr=ocr)

    def scan_ic(self, image_bytes: bytes, media_type: str) -> dict[str, object]:
        """Return unconfirmed local candidates; never authoritative identity."""

        return self._ocr.scan(image_bytes, media_type=media_type)

    def process_face(self, frame: Any) -> SafeFaceResult:
        """Delegate to the mother and omit its sensitive template from the result."""

        result = self.biometric.process_frame(frame)
        return SafeFaceResult(
            capture_status=result.capture_status,
            liveness_status=result.liveness_status,
            diagnostic_code=result.diagnostic_code,
            template_generated=result.template is not None,
        )


__all__ = ["SFGRegistrationCore", "SafeFaceResult"]
