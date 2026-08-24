from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from sfg_biometric_core import (
    INVALID_CAPTURE,
    MULTIPLE_FACES,
    NO_FACE,
)
from sfg_biometric_core.compatibility import (
    AssetSpec,
    CompatibilityFingerprint,
    ModelManifest,
    validate_asset_path,
    validate_model_manifest,
)
from sfg_biometric_core.yunet import YuNetDetector, validate_frame


def _spec(name: str, payload: bytes) -> AssetSpec:
    return AssetSpec(
        filename=name,
        byte_size=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        source_revision="test-revision",
        source_url="https://example.invalid/pinned",
    )


def test_manifest_rejects_missing_directory_wrong_type_and_corrupt_asset(tmp_path: Path) -> None:
    payload = b"model"
    spec = _spec("model.onnx", payload)

    missing = validate_asset_path(tmp_path / "missing.onnx", spec)
    wrong_type_path = tmp_path / "model.onnx"
    wrong_type_path.mkdir()
    wrong_type = validate_asset_path(wrong_type_path, spec)
    wrong_type_path.rmdir()
    corrupt_path = tmp_path / "model.onnx"
    corrupt_path.write_bytes(b"wrong")
    corrupt = validate_asset_path(corrupt_path, spec)

    assert missing.code == "ASSET_MISSING"
    assert wrong_type.code == "ASSET_NOT_REGULAR_FILE"
    assert corrupt.code == "ASSET_SHA256_MISMATCH"


def test_manifest_maps_inaccessible_asset(monkeypatch, tmp_path: Path) -> None:
    import sfg_biometric_core.compatibility as compatibility

    payload = b"model"
    path = tmp_path / "model.onnx"
    path.write_bytes(payload)
    spec = _spec("model.onnx", payload)

    def inaccessible(_path):
        raise OSError("access denied")

    monkeypatch.setattr(compatibility, "_sha256", inaccessible)
    assert validate_asset_path(path, spec).code == "ASSET_UNREADABLE"


def test_manifest_rejects_unexpected_pad_file(tmp_path: Path) -> None:
    yunet_bytes = b"yunet"
    sface_bytes = b"sface"
    pad_one = b"pad-one"
    pad_two = b"pad-two"
    manifest = ModelManifest(
        yunet=_spec("yunet.onnx", yunet_bytes),
        sface=_spec("sface.onnx", sface_bytes),
        pad_models={
            "one.pth": _spec("one.pth", pad_one),
            "two.pth": _spec("two.pth", pad_two),
        },
    )
    yunet = tmp_path / "yunet.onnx"
    sface = tmp_path / "sface.onnx"
    pad_dir = tmp_path / "pad"
    pad_dir.mkdir()
    yunet.write_bytes(yunet_bytes)
    sface.write_bytes(sface_bytes)
    (pad_dir / "one.pth").write_bytes(pad_one)
    (pad_dir / "two.pth").write_bytes(pad_two)
    (pad_dir / "unexpected.pth").write_bytes(b"unexpected")

    result = validate_model_manifest(yunet, sface, pad_dir, manifest=manifest)

    assert result.ok is False
    assert result.code == "PAD_UNEXPECTED_ASSET"


@pytest.mark.parametrize(
    "frame",
    [
        None,
        np.empty((0, 10, 3), dtype=np.uint8),
        np.empty((10, 10), dtype=np.uint8),
        np.empty((10, 10, 4), dtype=np.uint8),
        np.empty((10, 10, 3), dtype=np.float32),
        np.empty((10, 0, 3), dtype=np.uint8),
    ],
)
def test_invalid_frames_fail_closed(frame: np.ndarray | None) -> None:
    assert validate_frame(frame).ok is False


def _row(offset: float = 0.0) -> np.ndarray:
    return np.asarray(
        [
            2.0 + offset,
            2.0,
            6.0,
            6.0,
            3.0,
            4.0,
            7.0,
            4.0,
            5.0,
            5.0,
            3.5,
            7.0,
            6.5,
            7.0,
            0.99,
        ],
        dtype=np.float32,
    )


class DetectorStub:
    def __init__(self, output):
        self.output = output
        self.input_sizes: list[tuple[int, int]] = []

    def setInputSize(self, size):
        self.input_sizes.append(tuple(size))

    def detect(self, frame):
        return self.output


@pytest.mark.parametrize(
    ("faces", "status"),
    [
        (np.empty((0, 15), dtype=np.float32), NO_FACE),
        (np.vstack([_row()]), "CAPTURE_READY"),
        (np.vstack([_row(), _row(1.0)]), MULTIPLE_FACES),
    ],
)
def test_detector_maps_zero_and_multiple_faces_and_updates_input_size(faces, status) -> None:
    stub = DetectorStub((1, faces))
    detector = YuNetDetector(detector=stub)
    frame = np.zeros((11, 17, 3), dtype=np.uint8)

    result = detector.detect(frame)

    assert result.capture_status == status
    detector.detect(np.zeros((13, 19, 3), dtype=np.uint8))
    assert stub.input_sizes == [(17, 11), (19, 13)]


def test_detector_rejects_malformed_detection_and_maps_exceptions() -> None:
    malformed = DetectorStub((1, np.zeros((1, 14), dtype=np.float32)))
    assert YuNetDetector(detector=malformed).detect(np.zeros((10, 10, 3), np.uint8)).capture_status == INVALID_CAPTURE

    malformed_landmarks = _row()
    malformed_landmarks[4:14] = 0
    bad_landmarks = DetectorStub((1, malformed_landmarks.reshape(1, 15)))
    assert YuNetDetector(detector=bad_landmarks).detect(np.zeros((10, 10, 3), np.uint8)).capture_status == INVALID_CAPTURE

    class Raising:
        def setInputSize(self, size):
            pass

        def detect(self, frame):
            raise RuntimeError("sensitive detector internals")

    result = YuNetDetector(detector=Raising()).detect(np.zeros((10, 10, 3), np.uint8))
    assert result.capture_status == INVALID_CAPTURE
    assert "sensitive" not in repr(result)


def test_compatibility_fingerprint_rejects_each_locked_dimension() -> None:
    base = CompatibilityFingerprint.for_test()
    changes = {
        "sface_model_sha256": "different",
        "opencv_version": "different",
        "alignment": "different",
        "preprocessing": "different",
        "template_dtype": "<f8",
        "template_shape": (1, 127),
        "serialization": "pickle",
        "metric": "L2",
    }

    for field, value in changes.items():
        with pytest.raises(ValueError, match="COMPATIBILITY_MISMATCH"):
            base.require_compatible(base.with_change(field, value))
