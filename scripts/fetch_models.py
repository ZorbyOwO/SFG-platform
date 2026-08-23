from __future__ import annotations

"""Verified model-fetch entry point.

The architecture names upstream model files but does not lock release URLs and SHA-256
values. This script therefore refuses to download unverified assets. Populate MANIFEST
through an approved change with an exact upstream URL, license record, and checksum.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelAsset:
    filename: str
    url: str
    sha256: str


MANIFEST: tuple[ModelAsset, ...] = ()
MODEL_DIR = Path(__file__).resolve().parents[1] / "api" / "models"


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not MANIFEST:
        raise SystemExit(
            "No approved model manifest is configured. Add reviewed URLs and SHA-256 values before downloading."
        )


if __name__ == "__main__":
    main()
