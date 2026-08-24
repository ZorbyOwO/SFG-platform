"""Pinned asset and template-compatibility checks for the shared core."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Mapping


YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
YUNET_BYTE_SIZE = 232589
YUNET_REVISION = "47534e27c9851bb1128ccc0102f1145e27f23f98"
YUNET_SOURCE_URL = "https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet"
YUNET_GIT_OBJECT = "2d8804a5986e229f1fde3a1994feacc66c91b58b"

SFACE_FILENAME = "face_recognition_sface_2021dec.onnx"
SFACE_SHA256 = "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"
SFACE_BYTE_SIZE = 38696353
SFACE_REVISION = "47534e27c9851bb1128ccc0102f1145e27f23f98"
SFACE_SOURCE_URL = "https://github.com/opencv/opencv_zoo/tree/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface"
SFACE_GIT_OBJECT = "5817e559d509b2c1d5069f3c49a388bc45d4395f"

PAD_REVISION = "b6d5f04ad78778917853b25c778acef6d5626d15"
PAD_SOURCE_URL = "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/tree/b6d5f04ad78778917853b25c778acef6d5626d15"
PAD_ONE_FILENAME = "2.7_80x80_MiniFASNetV2.pth"
PAD_TWO_FILENAME = "4_0_0_80x80_MiniFASNetV1SE.pth"
PAD_ONE_BYTE_SIZE = 1849453
PAD_TWO_BYTE_SIZE = 1856130
PAD_ONE_SHA256 = "a5eb02e1843f19b5386b953cc4c9f011c3f985d0ee2bb9819eea9a142099bec0"
PAD_TWO_SHA256 = "84ee1d37d96894d5e82de5a57df044ef80a58be2b218b5ed7cdfd875ec2f5990"
PAD_ONE_GIT_OBJECT = "47c4af2023fb072c0f5b0e0ade4824053a0558e1"
PAD_TWO_GIT_OBJECT = "55a25b316ef33ced3925687007a31a5e306990db"


@dataclass(frozen=True)
class AssetSpec:
    filename: str
    byte_size: int
    sha256: str | None
    source_revision: str
    source_url: str
    git_object: str | None = None


@dataclass(frozen=True)
class ModelManifest:
    yunet: AssetSpec
    sface: AssetSpec
    pad_models: Mapping[str, AssetSpec]

    @classmethod
    def default(cls) -> "ModelManifest":
        return cls(
            yunet=AssetSpec(
                filename=YUNET_FILENAME,
                byte_size=YUNET_BYTE_SIZE,
                sha256=YUNET_SHA256,
                source_revision=YUNET_REVISION,
                source_url=YUNET_SOURCE_URL,
                git_object=YUNET_GIT_OBJECT,
            ),
            sface=AssetSpec(
                filename=SFACE_FILENAME,
                byte_size=SFACE_BYTE_SIZE,
                sha256=SFACE_SHA256,
                source_revision=SFACE_REVISION,
                source_url=SFACE_SOURCE_URL,
                git_object=SFACE_GIT_OBJECT,
            ),
            pad_models={
                PAD_ONE_FILENAME: AssetSpec(
                    filename=PAD_ONE_FILENAME,
                    byte_size=PAD_ONE_BYTE_SIZE,
                    sha256=PAD_ONE_SHA256,
                    source_revision=PAD_REVISION,
                    source_url=PAD_SOURCE_URL,
                    git_object=PAD_ONE_GIT_OBJECT,
                ),
                PAD_TWO_FILENAME: AssetSpec(
                    filename=PAD_TWO_FILENAME,
                    byte_size=PAD_TWO_BYTE_SIZE,
                    sha256=PAD_TWO_SHA256,
                    source_revision=PAD_REVISION,
                    source_url=PAD_SOURCE_URL,
                    git_object=PAD_TWO_GIT_OBJECT,
                ),
            },
        )


@dataclass(frozen=True)
class AssetValidation:
    ok: bool
    code: str


@dataclass(frozen=True)
class ManifestValidation:
    ok: bool
    code: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_asset_path(path: str | Path, spec: AssetSpec) -> AssetValidation:
    """Validate one allowlisted file without loading or deserializing it."""

    candidate = Path(path)
    if not candidate.exists():
        return AssetValidation(False, "ASSET_MISSING")
    if not candidate.is_file():
        return AssetValidation(False, "ASSET_NOT_REGULAR_FILE")
    if candidate.name != spec.filename:
        return AssetValidation(False, "ASSET_FILENAME_MISMATCH")
    try:
        if candidate.stat().st_size != spec.byte_size:
            return AssetValidation(False, "ASSET_SIZE_MISMATCH")
        if not spec.sha256:
            return AssetValidation(False, "ASSET_HASH_NOT_CONFIGURED")
        if _sha256(candidate) != spec.sha256.lower():
            return AssetValidation(False, "ASSET_SHA256_MISMATCH")
    except OSError:
        return AssetValidation(False, "ASSET_UNREADABLE")
    return AssetValidation(True, "OK")


def validate_model_manifest(
    yunet_path: str | Path,
    sface_path: str | Path,
    pad_model_dir: str | Path,
    *,
    manifest: ModelManifest | None = None,
) -> ManifestValidation:
    """Validate all exact model paths and reject unexpected PAD payload files."""

    selected = manifest or ModelManifest.default()
    for path, spec in ((yunet_path, selected.yunet), (sface_path, selected.sface)):
        result = validate_asset_path(path, spec)
        if not result.ok:
            return ManifestValidation(False, result.code)

    pad_dir = Path(pad_model_dir)
    if not pad_dir.exists():
        return ManifestValidation(False, "PAD_MODEL_DIR_MISSING")
    if not pad_dir.is_dir():
        return ManifestValidation(False, "PAD_MODEL_DIR_NOT_DIRECTORY")

    expected_names = set(selected.pad_models)
    try:
        regular_names = {entry.name for entry in pad_dir.iterdir() if entry.is_file()}
    except OSError:
        return ManifestValidation(False, "PAD_MODEL_DIR_UNREADABLE")
    unexpected = regular_names - expected_names
    if unexpected:
        return ManifestValidation(False, "PAD_UNEXPECTED_ASSET")
    missing = expected_names - regular_names
    if missing:
        return ManifestValidation(False, "PAD_ASSET_MISSING")
    for name, spec in selected.pad_models.items():
        result = validate_asset_path(pad_dir / name, spec)
        if not result.ok:
            return ManifestValidation(False, result.code)
    return ManifestValidation(True, "OK")


@dataclass(frozen=True)
class CompatibilityFingerprint:
    """Every ingredient that must match before SFace comparison."""

    yunet_model_filename: str
    yunet_model_sha256: str
    sface_model_filename: str
    sface_model_sha256: str
    opencv_version: str
    dnn_backend: str
    dnn_target: str
    landmark_order: tuple[str, ...]
    alignment: str
    preprocessing: str
    template_dtype: str
    template_shape: tuple[int, int]
    serialization: str
    metric: str
    comparison_policy: str

    @classmethod
    def for_test(cls) -> "CompatibilityFingerprint":
        return cls(
            yunet_model_filename=YUNET_FILENAME,
            yunet_model_sha256=YUNET_SHA256,
            sface_model_filename=SFACE_FILENAME,
            sface_model_sha256=SFACE_SHA256,
            opencv_version="4.10.0",
            dnn_backend="OPENCV",
            dnn_target="CPU",
            landmark_order=(
                "right_eye",
                "left_eye",
                "nose_tip",
                "right_mouth_corner",
                "left_mouth_corner",
            ),
            alignment="FaceRecognizerSF.alignCrop/OpenCV-4.10/112x112/INTER_LINEAR",
            preprocessing="blobFromImage(scale=1,mean=0,swapRB=true,crop=false)",
            template_dtype="<f4",
            template_shape=(1, 128),
            serialization="little-endian IEEE-754 float32 C-order 512-byte",
            metric="FaceRecognizerSF.FR_COSINE",
            comparison_policy="SFG_SHARED_BIOMETRIC_CORE_V1_1N_LINEAR",
        )

    def with_change(self, field_name: str, value: object) -> "CompatibilityFingerprint":
        return replace(self, **{field_name: value})

    def mismatch_fields(self, other: "CompatibilityFingerprint") -> tuple[str, ...]:
        return tuple(
            field.name
            for field in fields(self)
            if getattr(self, field.name) != getattr(other, field.name)
        )

    def require_compatible(self, other: "CompatibilityFingerprint") -> None:
        if self.mismatch_fields(other):
            raise ValueError("COMPATIBILITY_MISMATCH")

    def fingerprint_id(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, object]:
        return {
            "yunet_model_filename": self.yunet_model_filename,
            "yunet_model_sha256": self.yunet_model_sha256,
            "sface_model_filename": self.sface_model_filename,
            "sface_model_sha256": self.sface_model_sha256,
            "opencv_version": self.opencv_version,
            "dnn_backend": self.dnn_backend,
            "dnn_target": self.dnn_target,
            "landmark_order": list(self.landmark_order),
            "alignment": self.alignment,
            "preprocessing": self.preprocessing,
            "template_dtype": self.template_dtype,
            "template_shape": list(self.template_shape),
            "serialization": self.serialization,
            "metric": self.metric,
            "comparison_policy": self.comparison_policy,
        }


DEFAULT_FINGERPRINT = CompatibilityFingerprint.for_test()


__all__ = [
    "AssetSpec",
    "AssetValidation",
    "CompatibilityFingerprint",
    "DEFAULT_FINGERPRINT",
    "ManifestValidation",
    "ModelManifest",
    "validate_asset_path",
    "validate_model_manifest",
]
