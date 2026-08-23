from __future__ import annotations

import secrets
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app


@pytest.fixture()
def api_client() -> dict[str, object]:
    key = secrets.token_urlsafe(28)
    settings = replace(Settings.from_env(), app_env="test", pin_max_attempts=3)
    with TestClient(create_app(settings, kiosk_key=key)) as client:
        yield {"client": client, "kiosk_key": key}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_and_activate(client: TestClient, ic: str = "880712135423") -> dict[str, str]:
    password = f"Aa9!{secrets.token_urlsafe(14)}"
    pin = f"{secrets.randbelow(800000) + 100000:06d}"
    while pin in {ic[:6], f"{ic[4:6]}{ic[2:4]}{ic[:2]}"} or len(set(pin)) == 1:
        pin = f"{secrets.randbelow(800000) + 100000:06d}"
    wrong_pin = f"{(int(pin) + 137) % 1_000_000:06d}"
    registration = client.post("/auth/register", json={
        "ic": ic,
        "full_name": "Aisyah Rahman",
        "email": f"citizen-{ic}@example.com",
        "password": password,
        "password_confirm": password,
    })
    assert registration.status_code == 201, registration.text
    token = registration.json()["access_token"]
    headers = bearer(token)
    session_response = client.post("/enrol/session", json={}, headers=headers)
    assert session_response.status_code == 200, session_response.text
    session = session_response.json()
    for pose in ("front", "right", "left"):
        response = client.post(
            "/enrol/face",
            data={"session_id": session["session_id"], "nonce": session["nonce"], "pose": pose},
            files={"frame": ("simulation.jpg", b"not-a-face", "image/jpeg")},
            headers={**headers, "X-SFG-Simulation": "success"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["liveness_status"] == "PAD_LIVE"
    complete = client.post("/enrol/complete", json={"session_id": session["session_id"]}, headers=headers)
    assert complete.status_code == 200, complete.text
    pin_response = client.post("/enrol/pin", json={"pin": pin, "pin_confirm": pin}, headers=headers)
    assert pin_response.status_code == 200, pin_response.text
    active = client.post(
        "/enrol/activate",
        json={"terms_acknowledged": True, "privacy_acknowledged": True},
        headers=headers,
    )
    assert active.status_code == 200, active.text
    return {
        "token": token,
        "pin": pin,
        "wrong_pin": wrong_pin,
        "password": password,
        "citizen_id": registration.json()["citizen_id"],
    }


def open_payment(client: TestClient, kiosk_key: str, amount: str = "20.00") -> dict[str, str]:
    response = client.post(
        "/pay/session",
        json={"kiosk_id": "SFG-KIOSK-001", "amount": amount},
        headers={"X-Kiosk-Key": kiosk_key},
    )
    assert response.status_code == 200, response.text
    return response.json()


def identify(client: TestClient, kiosk_key: str, session: dict[str, str], scenario: str):
    return client.post(
        "/pay/identify",
        data={"session_id": session["session_id"], "nonce": session["nonce"]},
        files={"frame": ("simulation.jpg", b"not-a-face", "image/jpeg")},
        headers={"X-Kiosk-Key": kiosk_key, "X-SFG-Simulation": scenario},
    )
