"""Verify the embedded mother byte-for-byte against frozen SHA 37bbbf64."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    baseline = json.loads((package_root / "config" / "mother-baseline-sha256.json").read_text(encoding="utf-8"))
    mother = package_root / "internal" / "biometric-core"
    mismatches: list[str] = []
    for relative, expected in baseline["files"].items():
        path = mother / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "MISSING"
        if actual != expected:
            mismatches.append(relative)
    if mismatches:
        print(f"mother_immutability=FAIL mismatches={len(mismatches)}")
        return 1
    print(
        "mother_immutability=PASS "
        f"baseline={baseline['frozen_git_sha']} files={len(baseline['files'])} "
        f"fingerprint={baseline['manifest_fingerprint']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
