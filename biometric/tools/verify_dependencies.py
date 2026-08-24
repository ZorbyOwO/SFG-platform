"""Verify that an environment exactly matches one package lock."""

from __future__ import annotations

import argparse
from importlib.metadata import distributions
from pathlib import Path


def _canonical(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def _expected(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("--"):
            continue
        name, version = line.split("==", 1)
        values[_canonical(name)] = version
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("lock", type=Path)
    args = parser.parse_args()
    expected = _expected(args.lock)
    installed = {
        _canonical(dist.metadata["Name"]): dist.version
        for dist in distributions()
        if dist.metadata.get("Name") and _canonical(dist.metadata["Name"]) not in {"pip", "setuptools"}
    }
    missing = sorted(set(expected) - set(installed))
    extra = sorted(set(installed) - set(expected))
    changed = sorted(name for name in set(expected) & set(installed) if expected[name] != installed[name])
    if missing or extra or changed:
        print(f"dependency_lock=FAIL missing={len(missing)} extra={len(extra)} changed={len(changed)}")
        return 1
    print(f"dependency_lock=PASS packages={len(expected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
