from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sfg_biometric_core import CAPTURE_READY, PAD_LIVE
from sfg_biometric_core.compatibility import DEFAULT_FINGERPRINT
from sfg_biometric_core.pipeline import PipelineResult

from sfg_registration_core import SFGRegistrationCore


class BiometricStub:
    def __init__(self) -> None:
        self.template = object()

    def process_frame(self, frame: object) -> PipelineResult:
        return PipelineResult(CAPTURE_READY, PAD_LIVE, template=self.template)


class OCRStub:
    def scan(self, image_bytes: bytes, *, media_type: str) -> dict[str, object]:
        return {"full_name": None, "ic": None, "requires_confirmation": True}


def test_facade_exposes_actual_mother_interface_but_safe_face_projection() -> None:
    biometric = BiometricStub()
    registration = SFGRegistrationCore(biometric=biometric, ocr=OCRStub())

    result = registration.process_face(object())

    assert registration.biometric is biometric
    assert result.capture_status == CAPTURE_READY
    assert result.liveness_status == PAD_LIVE
    assert result.template_generated is True
    assert not hasattr(result, "template")
    assert "object at" not in repr(result)


def test_scan_ic_delegates_to_assistance_and_requires_confirmation() -> None:
    registration = SFGRegistrationCore(biometric=BiometricStub(), ocr=OCRStub())

    result = registration.scan_ic(b"validated-by-stub", media_type="image/png")

    assert result == {"full_name": None, "ic": None, "requires_confirmation": True}


def test_frozen_fingerprint_and_public_statuses_are_unchanged() -> None:
    assert DEFAULT_FINGERPRINT.fingerprint_id() == "a18bbbd47a57d14d"
    assert CAPTURE_READY == "CAPTURE_READY"
    assert PAD_LIVE == "PAD_LIVE"


def test_registration_source_contains_no_duplicate_biometric_modules() -> None:
    source_dir = Path(__file__).resolve().parents[1] / "src" / "sfg_registration_core"
    forbidden = {"yunet.py", "silent_face_pad.py", "sface.py", "compatibility.py", "pipeline.py"}

    assert forbidden.isdisjoint({path.name for path in source_dir.glob("*.py")})
