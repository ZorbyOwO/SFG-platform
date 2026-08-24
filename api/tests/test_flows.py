from __future__ import annotations

from datetime import timedelta
import secrets

import pytest
from fastapi.testclient import TestClient

from api.repositories.memory import now_utc
from .conftest import bearer, identify, open_payment, register_and_activate


def test_health_is_honest_and_safe(api_client) -> None:
    client: TestClient = api_client["client"]
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mode"] == "development_in_memory"
    assert body["models"]["adapter"] == "development_simulation"
    serialized = response.text.lower()
    assert "database_url" not in serialized
    assert "encryption_key" not in serialized


def test_registration_login_enrolment_wallet_family_and_idempotency(api_client) -> None:
    client: TestClient = api_client["client"]
    account = register_and_activate(client)
    headers = bearer(account["token"])
    login = client.post("/auth/login", json={"ic": "880712-13-5423", "password": account["password"]})
    assert login.status_code == 200
    assert login.json()["enrolment_status"] == "ENROLMENT_COMPLETED"
    invalid_password = f"Aa9!{secrets.token_urlsafe(12)}"
    unknown = client.post("/auth/login", json={"ic": "900101135555", "password": invalid_password})
    wrong = client.post("/auth/login", json={"ic": "880712135423", "password": invalid_password})
    assert (unknown.status_code, unknown.json()) == (wrong.status_code, wrong.json())

    topup_key = "topup-idempotency-0001"
    first = client.post("/wallet/topup", json={"amount": 100, "mock_source": "test", "idempotency_key": topup_key}, headers=headers)
    second = client.post("/wallet/topup", json={"amount": 100, "mock_source": "test", "idempotency_key": topup_key}, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert client.get("/wallet", headers=headers).json()["available_balance"] == "100.00"

    family_key = "family-idempotency-0001"
    family = client.post("/family-members", json={
        "ic": "100101135555", "full_name": "Adam Harith", "relationship": "Son", "idempotency_key": family_key,
    }, headers=headers)
    assert family.status_code == 201, family.text
    member_id = family.json()["family_member_id"]
    enrol = client.post(f"/family-members/{member_id}/enrol/session", json={}, headers=headers).json()
    for pose in ("front", "right", "left"):
        capture = client.post(
            f"/family-members/{member_id}/enrol/face",
            data={"session_id": enrol["session_id"], "nonce": enrol["nonce"], "pose": pose},
            files={"frame": ("simulation.jpg", b"not-a-face", "image/jpeg")},
            headers={**headers, "X-SFG-Simulation": "success"},
        )
        assert capture.status_code == 200
    completed = client.post(
        f"/family-members/{member_id}/enrol/complete", json={"session_id": enrol["session_id"]}, headers=headers,
    )
    assert completed.status_code == 200
    wrong_pin = client.post("/wallet/transfers", json={
        "family_member_id": member_id, "amount": "20.00", "pin": account["wrong_pin"], "idempotency_key": "transfer-wrong-0001",
    }, headers=headers)
    assert wrong_pin.status_code == 401
    transfer_key = "transfer-idempotency-0001"
    first_transfer = client.post("/wallet/transfers", json={
        "family_member_id": member_id, "amount": "20.00", "pin": account["pin"], "idempotency_key": transfer_key,
    }, headers=headers)
    second_transfer = client.post("/wallet/transfers", json={
        "family_member_id": member_id, "amount": "20.00", "pin": account["pin"], "idempotency_key": transfer_key,
    }, headers=headers)
    assert first_transfer.status_code == second_transfer.status_code == 200
    assert first_transfer.json() == second_transfer.json()
    assert first_transfer.json()["main_balance"] == "80.00"
    assert first_transfer.json()["family_balance"] == "20.00"


def test_top_up_presets_custom_amount_and_bounds(api_client) -> None:
    client: TestClient = api_client["client"]
    account = register_and_activate(client)
    headers = bearer(account["token"])

    for index, amount in enumerate((20, 50, 100, 200, 500), start=1):
        response = client.post("/wallet/topup", json={
            "amount": amount,
            "mock_source": "test",
            "idempotency_key": f"topup-preset-{index:04d}",
        }, headers=headers)
        assert response.status_code == 200, response.text

    custom = client.post("/wallet/topup", json={
        "amount": "123.45",
        "mock_source": "test",
        "idempotency_key": "topup-custom-0001",
    }, headers=headers)
    assert custom.status_code == 200, custom.text
    assert client.get("/wallet", headers=headers).json()["available_balance"] == "993.45"

    for invalid_amount in ("0.99", "5000.01", "15.123"):
        invalid = client.post("/wallet/topup", json={
            "amount": invalid_amount,
            "mock_source": "test",
            "idempotency_key": f"topup-invalid-{invalid_amount}",
        }, headers=headers)
        assert invalid.status_code == 422
        assert invalid.json()["error"] == "invalid_amount"


def test_profile_pin_change_and_face_reenrolment_return_to_active(api_client) -> None:
    client: TestClient = api_client["client"]
    account = register_and_activate(client)
    headers = bearer(account["token"])
    replacement_pin = "482605"

    wrong_change = client.post("/auth/pin/change", json={
        "current_pin": account["wrong_pin"], "new_pin": replacement_pin, "new_pin_confirm": replacement_pin,
    }, headers=headers)
    assert wrong_change.status_code == 401

    changed = client.post("/auth/pin/change", json={
        "current_pin": account["pin"], "new_pin": replacement_pin, "new_pin_confirm": replacement_pin,
    }, headers=headers)
    assert changed.status_code == 200
    assert changed.json()["pin_status"] == "PIN_ACCEPTED"

    session_response = client.post("/profile/face-reenrol/session", json={}, headers=headers)
    assert session_response.status_code == 200, session_response.text
    session = session_response.json()
    for pose in ("front", "right", "left"):
        capture = client.post(
            "/enrol/face",
            data={"session_id": session["session_id"], "nonce": session["nonce"], "pose": pose},
            files={"frame": ("simulation.jpg", b"not-a-face", "image/jpeg")},
            headers={**headers, "X-SFG-Simulation": "success"},
        )
        assert capture.status_code == 200, capture.text

    completed = client.post("/enrol/complete", json={"session_id": session["session_id"]}, headers=headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["next_step"] == "dashboard"
    profile = client.get("/profile", headers=headers)
    assert profile.json()["account_status"] == "active"
    assert profile.json()["enrolment_status"] == "ENROLMENT_COMPLETED"


@pytest.mark.parametrize("scenario,expected", [
    ("pad_uncertain", "PAD_UNCERTAIN"),
    ("pad_error", "PAD_ERROR"),
    ("no_match", "NO_MATCH"),
    ("ambiguous_match", "AMBIGUOUS_MATCH"),
    ("match_error", "MATCH_ERROR"),
])
def test_negative_biometric_states_never_authorize(api_client, scenario: str, expected: str) -> None:
    client: TestClient = api_client["client"]
    key: str = api_client["kiosk_key"]
    account = register_and_activate(client)
    client.post("/wallet/topup", json={"amount": 100, "mock_source": "test", "idempotency_key": f"topup-{scenario}-0001"}, headers=bearer(account["token"]))
    session = open_payment(client, key)
    response = identify(client, key, session, scenario)
    assert response.status_code in {403, 404, 409, 503}
    body = response.json()
    assert expected in body.values()
    assert body.get("authorization_status") != "AUTHORIZATION_GRANTED"


def test_payment_pin_lock_insufficient_funds_success_duplicate_timeout_and_cancel(api_client) -> None:
    client: TestClient = api_client["client"]
    key: str = api_client["kiosk_key"]
    account = register_and_activate(client)
    headers = bearer(account["token"])

    locked_session = open_payment(client, key, "5.00")
    assert identify(client, key, locked_session, "success").status_code == 200
    for attempt in range(3):
        result = client.post("/pay/confirm", json={"session_id": locked_session["session_id"], "nonce": locked_session["nonce"], "pin": account["wrong_pin"]}, headers={"X-Kiosk-Key": key})
    assert result.status_code == 423
    assert result.json()["pin_status"] == "PIN_LOCKED"
    assert result.json()["authorization_status"] == "AUTHORIZATION_DENIED"

    client.post("/wallet/topup", json={"amount": 20, "mock_source": "test", "idempotency_key": "topup-payment-0001"}, headers=headers)
    insufficient = open_payment(client, key, "30.00")
    assert identify(client, key, insufficient, "success").status_code == 200
    denied_charge = client.post("/pay/confirm", json={"session_id": insufficient["session_id"], "nonce": insufficient["nonce"], "pin": account["pin"]}, headers={"X-Kiosk-Key": key})
    assert denied_charge.status_code == 402
    assert denied_charge.json()["error"] == "insufficient_funds"

    client.post("/wallet/topup", json={"amount": 100, "mock_source": "test", "idempotency_key": "topup-payment-0002"}, headers=headers)
    success_session = open_payment(client, key, "30.00")
    assert identify(client, key, success_session, "success").status_code == 200
    success_payload = {"session_id": success_session["session_id"], "nonce": success_session["nonce"], "pin": account["pin"]}
    first = client.post("/pay/confirm", json=success_payload, headers={"X-Kiosk-Key": key})
    duplicate = client.post("/pay/confirm", json=success_payload, headers={"X-Kiosk-Key": key})
    assert first.status_code == duplicate.status_code == 200
    assert first.json() == duplicate.json()
    assert first.json()["authorization_status"] == "AUTHORIZATION_GRANTED"
    assert "service_access_status" not in first.json()

    timeout_session = open_payment(client, key)
    client.app.state.store.sessions[timeout_session["session_id"]].expires_at = now_utc() - timedelta(seconds=1)
    timeout = identify(client, key, timeout_session, "success")
    assert timeout.status_code == 410
    cancelled = open_payment(client, key)
    cancel = client.post("/pay/cancel", json={"session_id": cancelled["session_id"]}, headers={"X-Kiosk-Key": key})
    assert cancel.status_code == 204
    after_cancel = identify(client, key, cancelled, "success")
    assert after_cancel.status_code == 409
