"""Verify all four exact mother model payloads through the frozen validator."""

from __future__ import annotations

from pathlib import Path

from sfg_biometric_core.compatibility import validate_model_manifest


def main() -> int:
    root = Path(__file__).resolve().parents[1] / "internal" / "biometric-core" / "models"
    result = validate_model_manifest(
        root / "face_detection_yunet_2023mar.onnx",
        root / "face_recognition_sface_2021dec.onnx",
        root / "silent_face",
    )
    if not result.ok:
        print("mother_models=FAIL")
        return 1
    print("mother_models=PASS assets=4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
