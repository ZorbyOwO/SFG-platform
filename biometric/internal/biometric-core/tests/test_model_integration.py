from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from sfg_biometric_core import CAPTURE_READY
from sfg_biometric_core.compatibility import validate_model_manifest
from sfg_biometric_core.sface import SFaceEngine
from sfg_biometric_core.silent_face_pad import SilentFacePAD
from sfg_biometric_core.yunet import FaceDetection, YuNetDetector


ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
YUNET = MODELS / "face_detection_yunet_2023mar.onnx"
SFACE = MODELS / "face_recognition_sface_2021dec.onnx"
PAD = MODELS / "silent_face"


def _require_assets() -> None:
    if not (YUNET.is_file() and SFACE.is_file() and PAD.is_dir()):
        pytest.skip("pinned model payloads not acquired")


def _synthetic_fixture() -> np.ndarray:
    """Generate a non-person, in-memory fixture; no real image or dataset is used."""

    frame = np.zeros((180, 180, 3), dtype=np.uint8)
    yy, xx = np.mgrid[0:180, 0:180]
    frame[:, :, 0] = ((xx + yy) % 256).astype(np.uint8)
    frame[:, :, 1] = 80
    frame[:, :, 2] = 160
    cv2.circle(frame, (90, 90), 58, (190, 150, 110), thickness=-1)
    cv2.circle(frame, (68, 75), 8, (20, 20, 20), thickness=-1)
    cv2.circle(frame, (112, 75), 8, (20, 20, 20), thickness=-1)
    cv2.ellipse(frame, (90, 112), (22, 10), 0, 0, 180, (20, 20, 20), thickness=3)
    return frame


def test_pinned_manifest_and_all_four_model_loads() -> None:
    _require_assets()
    result = validate_model_manifest(YUNET, SFACE, PAD)
    assert result.ok is True
    YuNetDetector.from_model_path(YUNET)
    SFaceEngine.from_model_path(SFACE)
    SilentFacePAD.from_model_dir(PAD)


def test_actual_yunet_and_pad_structural_inputs_do_not_crash() -> None:
    _require_assets()
    detector = YuNetDetector.from_model_path(YUNET)
    pad = SilentFacePAD.from_model_dir(PAD)
    frame = _synthetic_fixture()
    detection = detector.detect(frame)
    assert detection.capture_status in {"NO_FACE", "MULTIPLE_FACES", CAPTURE_READY, "INVALID_CAPTURE"}
    if detection.face is not None:
        assert pad.assess(frame, detection.face).status in {"PAD_LIVE", "PAD_REJECT", "PAD_UNCERTAIN", "PAD_ERROR"}


def test_sface_template_from_synthetic_fixture_is_finite_and_canonical() -> None:
    _require_assets()
    engine = SFaceEngine.from_model_path(SFACE)
    frame = _synthetic_fixture()
    face = FaceDetection(
        box=(32.0, 32.0, 116.0, 116.0),
        landmarks=np.asarray(
            [[61.0, 74.0], [119.0, 74.0], [90.0, 98.0], [68.0, 119.0], [112.0, 119.0]],
            dtype=np.float32,
        ),
        confidence=0.99,
    )
    template = engine.template_from_detection(frame, face)
    assert template.shape == (1, 128)
    assert template.dtype == np.dtype(np.float32)
    assert template.is_finite
