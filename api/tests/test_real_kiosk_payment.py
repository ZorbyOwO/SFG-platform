"""Route-level contract for face -> profile confirmation -> PIN -> wallet charge."""

from __future__ import annotations

import secrets
from dataclasses import replace
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.contracts import CaptureStatus, LivenessStatus, MatchStatus
from api.errors import ApiError
from api.main import create_app
from api.services.face_identification import FaceIdentificationResult
from api.services.supabase_kiosk import CitizenIdentity, WalletCharge


CITIZEN = "11111111-2222-3333-4444-555555555555"
KIOSK_ID = "SFG-KIOSK-001"
PIN = "482605"


class StubCore:
    fingerprint_id = "a18bbbd47a57d14d"

    @staticmethod
    def health() -> dict[str, str]:
        return {"adapter": "scripted_core"}


class ScriptedFaceIdentification:
    def __init__(self) -> None:
        self.result = FaceIdentificationResult(
            CaptureStatus.READY,
            LivenessStatus.LIVE,
            MatchStatus.CONFIRMED,
            CITIZEN,
        )
        self.calls: list[tuple[bytes, str | None]] = []

    def identify(self, image: bytes, content_type: str | None) -> FaceIdentificationResult:
        self.calls.append((image, content_type))
        return self.result


class ScriptedTrustedBackend:
    def __init__(self) -> None:
        self.identity = CitizenIdentity(CITIZEN, "Mock Citizen", "010101010101")
        self.accepted_pin = PIN
        self.pin_checks: list[tuple[str, str]] = []
        self.charges: list[tuple[str, str, Decimal, str]] = []
        self.charge_error: ApiError | None = None

    def profile_identity(self, citizen_id: str) -> CitizenIdentity:
        assert citizen_id == CITIZEN
        return self.identity

    def verify_pin(self, citizen_id: str, pin: str) -> bool:
        self.pin_checks.append((citizen_id, pin))
        return pin == self.accepted_pin

    def charge_main_wallet(
        self,
        *,
        citizen_id: str,
        kiosk_id: str,
        amount: Decimal,
        idempotency_key: str,
    ) -> WalletCharge:
        if self.charge_error is not None:
            raise self.charge_error
        self.charges.append((citizen_id, kiosk_id, amount, idempotency_key))
        return WalletCharge(
            transaction_id="99999999-aaaa-bbbb-cccc-dddddddddddd",
            reference="SFG-ABCDEF012345",
            amount=amount,
            merchant_name="Sarawak Mart Kuching",
            balance_after=Decimal("87.66"),
        )


@pytest.fixture()
def real_kiosk() -> dict[str, Any]:
    kiosk_key = secrets.token_urlsafe(28)
    face = ScriptedFaceIdentification()
    trusted = ScriptedTrustedBackend()
    settings = replace(
        Settings.from_env(),
        app_env="test",
        pin_max_attempts=3,
        supabase_url=None,
        supabase_backend_secret=None,
        supabase_publishable_key=None,
    )
    app = create_app(
        settings,
        kiosk_key=kiosk_key,
        corecv_engine=StubCore(),
        face_identification=face,
        supabase_kiosk=trusted,
    )
    with TestClient(app) as client:
        yield {"client": client, "key": kiosk_key, "face": face, "trusted": trusted}


def open_session(env: dict[str, Any], amount: str = "12.34") -> dict[str, str]:
    response = env["client"].post(
        "/pay/session",
        json={"kiosk_id": KIOSK_ID, "amount": amount},
        headers={"X-Kiosk-Key": env["key"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def identify(env: dict[str, Any], session: dict[str, str]) -> Any:
    return env["client"].post(
        "/pay/identify",
        data={"session_id": session["session_id"], "nonce": session["nonce"]},
        files={"frame": ("capture.jpg", b"transient-live-frame", "image/jpeg")},
        headers={"X-Kiosk-Key": env["key"]},
    )


def confirm_identity(env: dict[str, Any], session: dict[str, str], confirmed: bool) -> Any:
    return env["client"].post(
        "/pay/identity/confirm",
        json={
            "session_id": session["session_id"],
            "nonce": session["nonce"],
            "confirmed": confirmed,
        },
        headers={"X-Kiosk-Key": env["key"]},
    )


def submit_pin(env: dict[str, Any], session: dict[str, str], pin: str) -> Any:
    return env["client"].post(
        "/pay/confirm",
        json={"session_id": session["session_id"], "nonce": session["nonce"], "pin": pin},
        headers={"X-Kiosk-Key": env["key"]},
    )


def test_real_payment_charges_only_the_face_matched_profile(real_kiosk: dict[str, Any]) -> None:
    session = open_session(real_kiosk)
    identified = identify(real_kiosk, session)

    assert identified.status_code == 200, identified.text
    assert identified.json()["identity_confirmation_status"] == "IDENTITY_CONFIRMATION_REQUIRED"
    assert identified.json()["citizen_display_name"] == "Mock C. ***"
    assert identified.json()["masked_ic"] == "******-**-0101"

    before_yes = submit_pin(real_kiosk, session, PIN)
    assert before_yes.status_code == 409
    assert real_kiosk["trusted"].pin_checks == []

    yes = confirm_identity(real_kiosk, session, True)
    assert yes.status_code == 200
    assert yes.json()["identity_confirmation_status"] == "IDENTITY_CONFIRMED"

    first = submit_pin(real_kiosk, session, PIN)
    duplicate = submit_pin(real_kiosk, session, PIN)
    assert first.status_code == duplicate.status_code == 200
    assert first.json() == duplicate.json()
    assert first.json()["authorization_status"] == "AUTHORIZATION_GRANTED"
    assert first.json()["reference"] == "SFG-ABCDEF012345"
    assert real_kiosk["trusted"].charges == [
        (CITIZEN, KIOSK_ID, Decimal("12.34"), f"pay:{session['session_id']}")
    ]


def test_rejecting_the_proposed_identity_never_checks_pin_or_charges(real_kiosk: dict[str, Any]) -> None:
    session = open_session(real_kiosk)
    assert identify(real_kiosk, session).status_code == 200

    rejected = confirm_identity(real_kiosk, session, False)

    assert rejected.status_code == 200
    assert rejected.json()["identity_confirmation_status"] == "IDENTITY_REJECTED"
    assert submit_pin(real_kiosk, session, PIN).status_code == 409
    assert real_kiosk["trusted"].pin_checks == []
    assert real_kiosk["trusted"].charges == []


def test_wrong_pin_locks_the_real_session_without_charging(real_kiosk: dict[str, Any]) -> None:
    session = open_session(real_kiosk)
    assert identify(real_kiosk, session).status_code == 200
    assert confirm_identity(real_kiosk, session, True).status_code == 200

    attempts = [submit_pin(real_kiosk, session, "000000") for _ in range(3)]

    assert [response.status_code for response in attempts] == [401, 401, 423]
    assert attempts[-1].json()["pin_status"] == "PIN_LOCKED"
    assert real_kiosk["trusted"].charges == []


@pytest.mark.parametrize(
    ("result", "status"),
    [
        (FaceIdentificationResult(CaptureStatus.READY, LivenessStatus.REJECT, None), 403),
        (
            FaceIdentificationResult(
                CaptureStatus.READY, LivenessStatus.LIVE, MatchStatus.NO_MATCH
            ),
            404,
        ),
        (
            FaceIdentificationResult(
                CaptureStatus.READY, LivenessStatus.LIVE, MatchStatus.AMBIGUOUS
            ),
            409,
        ),
        (
            FaceIdentificationResult(
                CaptureStatus.READY, LivenessStatus.LIVE, MatchStatus.ERROR
            ),
            503,
        ),
    ],
)
def test_negative_real_identification_never_reaches_profile_or_pin(
    real_kiosk: dict[str, Any], result: FaceIdentificationResult, status: int
) -> None:
    real_kiosk["face"].result = result
    session = open_session(real_kiosk)

    response = identify(real_kiosk, session)

    assert response.status_code == status
    assert real_kiosk["trusted"].pin_checks == []
    assert real_kiosk["trusted"].charges == []


def test_failed_supabase_charge_does_not_consume_the_session(real_kiosk: dict[str, Any]) -> None:
    real_kiosk["trusted"].charge_error = ApiError(
        409, "insufficient_funds", "The wallet has insufficient funds."
    )
    session = open_session(real_kiosk)
    assert identify(real_kiosk, session).status_code == 200
    assert confirm_identity(real_kiosk, session, True).status_code == 200

    response = submit_pin(real_kiosk, session, PIN)

    assert response.status_code == 409
    assert response.json()["error"] == "insufficient_funds"
    assert real_kiosk["client"].app.state.store.sessions[session["session_id"]].status != "consumed"
