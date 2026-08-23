from __future__ import annotations

"""Interactive development registration helper.

Secrets are requested at runtime with getpass and are never placed in this script,
fixtures, command history, logs, or documentation.
"""

import getpass
import json
import urllib.request


def main() -> None:
    base_url = input("API base URL [http://localhost:8000]: ").strip() or "http://localhost:8000"
    payload = {
        "ic": input("Mock IC number: ").strip(),
        "full_name": input("Full name: ").strip(),
        "email": input("Email: ").strip(),
        "password": getpass.getpass("Password: "),
    }
    payload["password_confirm"] = getpass.getpass("Confirm password: ")
    request = urllib.request.Request(
        f"{base_url}/auth/register",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        body = json.loads(response.read())
    print("Provisional development account created.")
    print(f"Enrolment status: {body['enrolment_status']}; next step: {body['next_step']}")


if __name__ == "__main__":
    main()
