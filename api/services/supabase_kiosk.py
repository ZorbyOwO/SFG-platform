"""Trusted Supabase RPC client for real kiosk identification and payment.

Only the FastAPI process constructs this client. The service-role credential,
encrypted gallery rows, unmasked identity, PIN, and exact wallet mutation stay
inside the trusted tier and are never projected to kiosk hardware.
"""

from __future__ import annotations

import base64
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from ..errors import ApiError
from .template_sealer import ENCRYPTION_VERSION


LOGGER = logging.getLogger(__name__)
REQUEST_TIMEOUT_SECONDS = 10.0
VALIDATED_FINGERPRINT = "a18bbbd47a57d14d"


@dataclass(frozen=True, slots=True)
class HostedTemplate:
    template_id: str
    citizen_id: str
    capture_pose: str
    generation_id: str
    encrypted_payload: str
    nonce: str
    compatibility_fingerprint: str


@dataclass(frozen=True, slots=True)
class CitizenIdentity:
    citizen_id: str
    full_name: str
    ic_number: str


@dataclass(frozen=True, slots=True)
class WalletCharge:
    transaction_id: str
    reference: str
    amount: Decimal
    merchant_name: str
    balance_after: Decimal


def _unavailable() -> ApiError:
    return ApiError(
        503,
        "real_kiosk_unavailable",
        "Real face payment is temporarily unavailable. No wallet was charged.",
    )


def _uuid(value: object) -> str:
    if not isinstance(value, str):
        raise _unavailable()
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError):
        raise _unavailable() from None


def _singleton_object(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        return value[0]
    raise _unavailable()


def _money(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise _unavailable()
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise _unavailable() from None
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        raise _unavailable()
    return amount.quantize(Decimal("0.01"))


def _postgres_base64(value: str) -> tuple[str, bytes]:
    """Normalize only the CR/LF wrapping emitted by PostgreSQL encode()."""

    normalized = value.replace("\r", "").replace("\n", "")
    if not normalized:
        raise _unavailable()
    try:
        return normalized, base64.b64decode(normalized, validate=True)
    except Exception:
        raise _unavailable() from None


class SupabaseKioskClient:
    """Fail-closed PostgREST RPC boundary for the kiosk trusted tier."""

    def __init__(
        self,
        *,
        supabase_url: str,
        backend_secret: str,
        compatibility_fingerprint: str = VALIDATED_FINGERPRINT,
        client: Any | None = None,
    ) -> None:
        if not supabase_url or not backend_secret or not compatibility_fingerprint:
            raise _unavailable()
        base = supabase_url.rstrip("/")
        if not (base.startswith("https://") or base.rsplit(":", 1)[-1].strip("/") == "54321"):
            raise _unavailable()
        self._base_url = base
        self._secret = backend_secret
        self._fingerprint = compatibility_fingerprint
        self._client = client

    def _rpc(self, name: str, payload: dict[str, Any]) -> object:
        headers = {
            "Authorization": f"Bearer {self._secret}",
            "apikey": self._secret,
            "Content-Type": "application/json",
        }
        sender = self._client or httpx
        try:
            response = sender.post(
                f"{self._base_url}/rest/v1/rpc/{name}",
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            LOGGER.warning("kiosk_backend rpc=%s result=unreachable detail=%s", name, type(exc).__name__)
            raise _unavailable() from None
        if response.status_code // 100 == 2:
            try:
                return response.json()
            except Exception:
                raise _unavailable() from None

        safe_code = ""
        if response.status_code == 400:
            try:
                body = response.json()
                if isinstance(body, dict) and isinstance(body.get("message"), str):
                    safe_code = body["message"].lower()
            except Exception:
                safe_code = ""
        if "insufficient_funds" in safe_code:
            raise ApiError(409, "insufficient_funds", "The wallet has insufficient funds.")
        if "account_unavailable" in safe_code or "citizen_profile_unavailable" in safe_code:
            raise ApiError(409, "account_unavailable", "The matched account is unavailable.")
        if "kiosk_unavailable" in safe_code:
            raise ApiError(409, "kiosk_unavailable", "This kiosk is unavailable.")
        LOGGER.warning("kiosk_backend rpc=%s result=refused status=%s", name, response.status_code)
        raise _unavailable()

    def load_templates(self) -> tuple[HostedTemplate, ...]:
        body = self._rpc(
            "sfg_backend_load_identification_gallery",
            {"p_encryption_version": ENCRYPTION_VERSION},
        )
        if not isinstance(body, list):
            raise _unavailable()
        records: list[HostedTemplate] = []
        citizens: set[str] = set()
        for raw in body:
            if not isinstance(raw, dict):
                raise _unavailable()
            template_id = _uuid(raw.get("template_id"))
            citizen_id = _uuid(raw.get("citizen_id"))
            generation_id = _uuid(raw.get("generation_id"))
            if raw.get("capture_pose") != "front" or citizen_id in citizens:
                raise _unavailable()
            fingerprint_object = raw.get("compatibility_fingerprint")
            if not isinstance(fingerprint_object, dict):
                raise _unavailable()
            fingerprint = fingerprint_object.get("fingerprint")
            if fingerprint != self._fingerprint:
                raise _unavailable()
            encrypted_payload = raw.get("encrypted_payload")
            nonce = raw.get("nonce")
            if not isinstance(encrypted_payload, str) or not isinstance(nonce, str):
                raise _unavailable()
            encrypted_payload, encrypted_bytes = _postgres_base64(encrypted_payload)
            nonce, nonce_bytes = _postgres_base64(nonce)
            if len(encrypted_bytes) <= 512 or len(nonce_bytes) != 12:
                raise _unavailable()
            records.append(
                HostedTemplate(
                    template_id=template_id,
                    citizen_id=citizen_id,
                    capture_pose="front",
                    generation_id=generation_id,
                    encrypted_payload=encrypted_payload,
                    nonce=nonce,
                    compatibility_fingerprint=fingerprint,
                )
            )
            citizens.add(citizen_id)
        return tuple(records)

    def profile_identity(self, citizen_id: str) -> CitizenIdentity:
        normalized_id = _uuid(citizen_id)
        body = _singleton_object(
            self._rpc("sfg_backend_profile_identity", {"p_citizen_id": normalized_id})
        )
        full_name = body.get("full_name")
        ic_number = body.get("ic_number")
        if (
            _uuid(body.get("citizen_id")) != normalized_id
            or not isinstance(full_name, str)
            or len(full_name.strip()) < 2
            or not isinstance(ic_number, str)
            or len(ic_number) != 12
            or not ic_number.isdigit()
        ):
            raise _unavailable()
        return CitizenIdentity(normalized_id, full_name.strip(), ic_number)

    def verify_pin(self, citizen_id: str, pin: str) -> bool:
        normalized_id = _uuid(citizen_id)
        if len(pin) != 6 or not pin.isdigit():
            return False
        body = _singleton_object(
            self._rpc(
                "sfg_backend_verify_pin",
                {"p_citizen_id": normalized_id, "p_pin": pin},
            )
        )
        accepted = body.get("accepted")
        if not isinstance(accepted, bool):
            raise _unavailable()
        return accepted

    def charge_main_wallet(
        self,
        *,
        citizen_id: str,
        kiosk_id: str,
        amount: Decimal,
        idempotency_key: str,
    ) -> WalletCharge:
        normalized_id = _uuid(citizen_id)
        normalized_amount = _money(amount)
        if normalized_amount <= 0 or not kiosk_id or len(idempotency_key) < 8:
            raise _unavailable()
        body = _singleton_object(
            self._rpc(
                "sfg_backend_charge_profile_wallet",
                {
                    "p_citizen_id": normalized_id,
                    "p_amount": f"{normalized_amount:.2f}",
                    "p_kiosk_id": kiosk_id,
                    "p_idempotency_key": idempotency_key,
                },
            )
        )
        transaction_id = _uuid(body.get("transaction_id"))
        reference = body.get("reference")
        merchant_name = body.get("merchant_name")
        charged_amount = _money(body.get("amount"))
        balance_after = _money(body.get("balance_after"))
        if (
            not isinstance(reference, str)
            or not reference.startswith("SFG-")
            or not isinstance(merchant_name, str)
            or not merchant_name.strip()
            or charged_amount != normalized_amount
        ):
            raise _unavailable()
        return WalletCharge(
            transaction_id=transaction_id,
            reference=reference,
            amount=charged_amount,
            merchant_name=merchant_name.strip(),
            balance_after=balance_after,
        )


__all__ = [
    "CitizenIdentity",
    "HostedTemplate",
    "SupabaseKioskClient",
    "WalletCharge",
]
