from __future__ import annotations

import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC = PACKAGE_ROOT / "src"
MOTHER_SRC = PACKAGE_ROOT / "internal" / "biometric-core" / "src"

for path in (str(SRC), str(MOTHER_SRC)):
    if path not in sys.path:
        sys.path.insert(0, path)
