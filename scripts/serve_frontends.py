from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    processes = [
        subprocess.Popen(["npm", "run", "dev", "--", "--port", "5500"], cwd=ROOT / "web"),
        subprocess.Popen([sys.executable, "-m", "http.server", "5501", "-d", str(ROOT / "kiosk")]),
    ]
    try:
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        for process in processes:
            process.terminate()


if __name__ == "__main__":
    main()
