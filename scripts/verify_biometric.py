"""Verify the vendored frozen biometric core inside the SFG platform.

Replaces the standalone package's `verify.cmd`, which assumed its own pair of
Python 3.10 virtual environments. The core now runs in-process in the SFG API
environment, so verification runs there too.

Checks, in order:

1. mother immutability  - every mother file still matches frozen SHA 37bbbf64
2. contract gate        - exactly 22 variables, 32 statuses, 18 config names
3. model manifest       - the four payloads match their pinned sizes and SHA-256
4. runtime fingerprint  - the loaded core matches validated Core v1
5. mother test suite    - the frozen core's own tests
6. facade test suite    - the registration facade's tests

Run from the repository root:

    .venv\\Scripts\\python.exe scripts\\verify_biometric.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "biometric"
MOTHER_SRC = PACKAGE / "internal" / "biometric-core" / "src"
FACADE_SRC = PACKAGE / "src"
VALIDATED_FINGERPRINT = "a18bbbd47a57d14d"


def child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join([str(FACADE_SRC), str(MOTHER_SRC)])
    return environment


def run_step(label: str, command: list[str]) -> bool:
    completed = subprocess.run(command, cwd=PACKAGE, env=child_environment(), check=False)
    ok = completed.returncode == 0
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    return ok


def check_fingerprint() -> bool:
    script = (
        "import sys;"
        f"sys.path[:0]=[{str(FACADE_SRC)!r},{str(MOTHER_SRC)!r}];"
        "from sfg_registration_core import SFGRegistrationCore;"
        f"core=SFGRegistrationCore.from_package({str(PACKAGE)!r});"
        "actual=core.biometric.sface.fingerprint.fingerprint_id();"
        f"expected={VALIDATED_FINGERPRINT!r};"
        "print('fingerprint', actual, 'expected', expected);"
        "sys.exit(0 if actual==expected else 1)"
    )
    return run_step("runtime compatibility fingerprint", [sys.executable, "-c", script])


def main() -> int:
    if not PACKAGE.is_dir():
        print("[FAIL] sfg/biometric is missing.", file=sys.stderr)
        return 1

    steps = [
        ("mother immutability", [sys.executable, str(PACKAGE / "tools" / "verify_mother.py")]),
        ("v1.2 contract gate", [sys.executable, str(PACKAGE / "tools" / "verify_contract.py")]),
        ("pinned model manifest", [sys.executable, str(PACKAGE / "tools" / "verify_models.py")]),
    ]
    results = [run_step(label, command) for label, command in steps]
    results.append(check_fingerprint())
    results.append(
        run_step("frozen mother test suite", [sys.executable, "-m", "pytest", "-q", "internal/biometric-core/tests"])
    )
    results.append(run_step("registration facade test suite", [sys.executable, "-m", "pytest", "-q", "tests"]))

    if all(results):
        print("\nVERIFY PASS: mother, contract, models, fingerprint, and both test suites.")
        return 0
    print("\nVERIFY FAIL: see the failing steps above.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
