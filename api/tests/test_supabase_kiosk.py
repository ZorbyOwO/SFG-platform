"""Trusted PostgREST boundary for real kiosk identification and payment."""

from __future__ import annotations

import base64
from decimal import Decimal

import pytest

from api.errors import ApiError
from api.services.supabase_kiosk import (
    CitizenIdentity,
    HostedTemplate,
    SupabaseKioskClient,
    WalletCharge,
)


URL = "https://oxpvsblgjrvfbrbaluxp.supabase.co"
SECRET = "sb_secret_test_only_never_real"
CITIZEN = "11111111-2222-3333-4444-555555555555"
TEMPLATE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
GENERATION = "66666666-7777-8888-9999-000000000000"
FINGERPRINT = "a18bbbd47a57d14d"
PAYLOAD = base64.b64encode(bytes(560)).decode("ascii")
NONCE = base64.b64encode(bytes(12)).decode("ascii")


class FakeResponse:
    def __init__(self, status_code: int, body: object) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> object:
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


class FakeTransport:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, *, json: dict, headers: dict, timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return self.responses.pop(0)


def client(*responses: FakeResponse) -> tuple[SupabaseKioskClient, FakeTransport]:
    transport = FakeTransport(list(responses))
    return (
        SupabaseKioskClient(
            supabase_url=URL,
            backend_secret=SECRET,
            client=transport,
        ),
        transport,
    )


def hosted_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "template_id": TEMPLATE,
        "citizen_id": CITIZEN,
        "capture_pose": "front",
        "generation_id": GENERATION,
        "encrypted_payload": PAYLOAD,
        "nonce": NONCE,
        "compatibility_fingerprint": {"fingerprint": FINGERPRINT},
    }
    row.update(overrides)
    return row


def test_load_templates_accepts_a_complete_front_pose_row() -> None:
    trusted, transport = client(FakeResponse(200, [hosted_row()]))

    records = trusted.load_templates()

    assert records == (
        HostedTemplate(
            template_id=TEMPLATE,
            citizen_id=CITIZEN,
            capture_pose="front",
            generation_id=GENERATION,
            encrypted_payload=PAYLOAD,
            nonce=NONCE,
            compatibility_fingerprint=FINGERPRINT,
        ),
    )
    call = transport.calls[0]
    assert call["url"].endswith("/rest/v1/rpc/sfg_backend_load_identification_gallery")
    assert call["json"] == {"p_encryption_version": "sfg-aesgcm-v1"}
    assert call["headers"]["Authorization"] == f"Bearer {SECRET}"


def test_load_templates_accepts_postgres_wrapped_base64() -> None:
    wrapped_payload = "\n".join(PAYLOAD[index : index + 76] for index in range(0, len(PAYLOAD), 76))
    trusted, _ = client(
        FakeResponse(200, [hosted_row(encrypted_payload=wrapped_payload)])
    )

    records = trusted.load_templates()

    assert records[0].encrypted_payload == PAYLOAD


@pytest.mark.parametrize(
    "row",
    [
        hosted_row(capture_pose="left"),
        hosted_row(generation_id=None),
        hosted_row(nonce="not-base64"),
        hosted_row(compatibility_fingerprint={"fingerprint": "different"}),
    ],
)
def test_load_templates_rejects_malformed_or_incompatible_rows(row: dict[str, object]) -> None:
    trusted, _ = client(FakeResponse(200, [row]))

    with pytest.raises(ApiError) as raised:
        trusted.load_templates()

    assert raised.value.status_code == 503
    assert raised.value.error == "real_kiosk_unavailable"


def test_profile_identity_is_read_only_for_the_matched_citizen() -> None:
    trusted, _ = client(
        FakeResponse(
            200,
            {"citizen_id": CITIZEN, "full_name": "Mock Citizen", "ic_number": "010101010101"},
        )
    )

    assert trusted.profile_identity(CITIZEN) == CitizenIdentity(
        citizen_id=CITIZEN,
        full_name="Mock Citizen",
        ic_number="010101010101",
    )


@pytest.mark.parametrize("accepted", [True, False])
def test_verify_pin_returns_only_the_database_decision(accepted: bool) -> None:
    trusted, transport = client(FakeResponse(200, {"accepted": accepted}))

    assert trusted.verify_pin(CITIZEN, "123456") is accepted
    assert transport.calls[0]["json"] == {"p_citizen_id": CITIZEN, "p_pin": "123456"}


def test_charge_main_wallet_returns_the_atomic_rpc_result() -> None:
    trusted, transport = client(
        FakeResponse(
            200,
            {
                "transaction_id": "99999999-aaaa-bbbb-cccc-dddddddddddd",
                "reference": "SFG-ABCDEF012345",
                "amount": "12.34",
                "merchant_name": "SFG Development Merchant",
                "balance_after": "87.66",
            },
        )
    )

    result = trusted.charge_main_wallet(
        citizen_id=CITIZEN,
        kiosk_id="SFG-KIOSK-001",
        amount=Decimal("12.34"),
        idempotency_key="pay:session-12345678",
    )

    assert result == WalletCharge(
        transaction_id="99999999-aaaa-bbbb-cccc-dddddddddddd",
        reference="SFG-ABCDEF012345",
        amount=Decimal("12.34"),
        merchant_name="SFG Development Merchant",
        balance_after=Decimal("87.66"),
    )
    assert transport.calls[0]["json"] == {
        "p_citizen_id": CITIZEN,
        "p_amount": "12.34",
        "p_kiosk_id": "SFG-KIOSK-001",
        "p_idempotency_key": "pay:session-12345678",
    }


@pytest.mark.parametrize(
    ("message", "expected_error"),
    [
        ("insufficient_funds", "insufficient_funds"),
        ("account_unavailable", "account_unavailable"),
        ("kiosk_unavailable", "kiosk_unavailable"),
    ],
)
def test_charge_maps_safe_database_failures(message: str, expected_error: str) -> None:
    trusted, _ = client(FakeResponse(400, {"message": message}))

    with pytest.raises(ApiError) as raised:
        trusted.charge_main_wallet(
            citizen_id=CITIZEN,
            kiosk_id="SFG-KIOSK-001",
            amount=Decimal("12.34"),
            idempotency_key="pay:session-12345678",
        )

    assert raised.value.error == expected_error


@pytest.mark.parametrize("status", [401, 403, 404, 500, 503])
def test_trusted_backend_failures_never_fall_back(status: int) -> None:
    trusted, _ = client(FakeResponse(status, {"message": "backend detail"}))

    with pytest.raises(ApiError) as raised:
        trusted.load_templates()

    assert raised.value.status_code == 503
    assert raised.value.error == "real_kiosk_unavailable"


def test_insecure_remote_url_is_rejected() -> None:
    with pytest.raises(ApiError) as raised:
        SupabaseKioskClient(
            supabase_url="http://example.test",
            backend_secret=SECRET,
        )

    assert raised.value.error == "real_kiosk_unavailable"
