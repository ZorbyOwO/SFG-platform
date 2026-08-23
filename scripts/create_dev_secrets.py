from __future__ import annotations

import secrets
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "api" / ".runtime"
KEY_FILE = RUNTIME / "kiosk.key"


def main() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    if not KEY_FILE.exists():
        KEY_FILE.write_text(secrets.token_urlsafe(36), encoding="utf-8")
    print(f"Development kiosk key is ready in the git-ignored file: {KEY_FILE}")
    print("Do not paste its value into source, documentation, screenshots, chat, or Git.")


if __name__ == "__main__":
    main()
