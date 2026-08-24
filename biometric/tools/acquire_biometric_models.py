"""Acquire only the four pinned mother assets and verify exact hashes."""

from __future__ import annotations

import hashlib
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Asset:
    relative_path: str
    url: str
    sha256: str
    size: int


ASSETS = (
    Asset(
        "face_detection_yunet_2023mar.onnx",
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        232589,
    ),
    Asset(
        "face_recognition_sface_2021dec.onnx",
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/47534e27c9851bb1128ccc0102f1145e27f23f98/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        38696353,
    ),
    Asset(
        "silent_face/2.7_80x80_MiniFASNetV2.pth",
        "https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/b6d5f04ad78778917853b25c778acef6d5626d15/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth",
        "a5eb02e1843f19b5386b953cc4c9f011c3f985d0ee2bb9819eea9a142099bec0",
        1849453,
    ),
    Asset(
        "silent_face/4_0_0_80x80_MiniFASNetV1SE.pth",
        "https://raw.githubusercontent.com/minivision-ai/Silent-Face-Anti-Spoofing/b6d5f04ad78778917853b25c778acef6d5626d15/resources/anti_spoof_models/4_0_0_80x80_MiniFASNetV1SE.pth",
        "84ee1d37d96894d5e82de5a57df044ef80a58be2b218b5ed7cdfd875ec2f5990",
        1856130,
    ),
)


def _valid(path: Path, asset: Asset) -> bool:
    return (
        path.is_file()
        and path.stat().st_size == asset.size
        and hashlib.sha256(path.read_bytes()).hexdigest() == asset.sha256
    )


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    model_root = package_root / "internal" / "biometric-core" / "models"
    for asset in ASSETS:
        destination = model_root / asset.relative_path
        if _valid(destination, asset):
            print(f"asset={asset.relative_path} status=VERIFIED")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".download")
        try:
            with urllib.request.urlopen(asset.url, timeout=120) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if not _valid(temporary, asset):
                raise RuntimeError(f"asset={asset.relative_path} status=HASH_OR_SIZE_INVALID")
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        print(f"asset={asset.relative_path} status=ACQUIRED_AND_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
