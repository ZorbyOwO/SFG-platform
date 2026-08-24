from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictDto(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EnrolmentStatus(StrEnum):
    STARTED = "ENROLMENT_STARTED"
    COMPLETED = "ENROLMENT_COMPLETED"
    FAILED = "ENROLMENT_FAILED"
    CANCELLED = "ENROLMENT_CANCELLED"


class ConsentStatus(StrEnum):
    GRANTED = "CONSENT_GRANTED"
    WITHDRAWN = "CONSENT_WITHDRAWN"
    REQUIRED = "CONSENT_REQUIRED"


class TemplateStatus(StrEnum):
    ACTIVE = "TEMPLATE_ACTIVE"
    REVOKED = "TEMPLATE_REVOKED"


class CaptureStatus(StrEnum):
    READY = "CAPTURE_READY"
    NO_FACE = "NO_FACE"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    INVALID = "INVALID_CAPTURE"
    CAMERA_ERROR = "CAMERA_ERROR"


class LivenessStatus(StrEnum):
    LIVE = "PAD_LIVE"
    REJECT = "PAD_REJECT"
    UNCERTAIN = "PAD_UNCERTAIN"
    ERROR = "PAD_ERROR"


class MatchStatus(StrEnum):
    CONFIRMED = "MATCH_CONFIRMED"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS = "AMBIGUOUS_MATCH"
    ERROR = "MATCH_ERROR"


class IdentityConfirmationStatus(StrEnum):
    REQUIRED = "IDENTITY_CONFIRMATION_REQUIRED"
    CONFIRMED = "IDENTITY_CONFIRMED"
    REJECTED = "IDENTITY_REJECTED"


class PinStatus(StrEnum):
    ACCEPTED = "PIN_ACCEPTED"
    REJECTED = "PIN_REJECTED"
    LOCKED = "PIN_LOCKED"


class AuthorizationStatus(StrEnum):
    GRANTED = "AUTHORIZATION_GRANTED"
    DENIED = "AUTHORIZATION_DENIED"


class ServiceAccessStatus(StrEnum):
    GRANTED = "SERVICE_ACCESS_GRANTED"
    DENIED = "SERVICE_ACCESS_DENIED"


CANONICAL_STATUS_FAMILIES: dict[str, tuple[str, ...]] = {
    "enrolment_status": tuple(item.value for item in EnrolmentStatus),
    "consent_status": tuple(item.value for item in ConsentStatus),
    "template_status": tuple(item.value for item in TemplateStatus),
    "capture_status": tuple(item.value for item in CaptureStatus),
    "liveness_status": tuple(item.value for item in LivenessStatus),
    "match_status": tuple(item.value for item in MatchStatus),
    "identity_confirmation_status": tuple(item.value for item in IdentityConfirmationStatus),
    "pin_status": tuple(item.value for item in PinStatus),
    "authorization_status": tuple(item.value for item in AuthorizationStatus),
    "service_access_status": tuple(item.value for item in ServiceAccessStatus),
}

CANONICAL_SHARED_FIELDS = frozenset(
    {
        "citizen_id", "citizen_display_name", "session_id", "correlation_id", "template_id",
        "enrolment_status", "consent_status", "template_status", "capture_status",
        "liveness_status", "match_status", "identity_confirmation_status", "pin_status",
        "authorization_status", "service_access_status", "kiosk_id", "kiosk_name",
        "verification_completed_at", "audit_event_id", "audit_event_type", "facial_template", "pin",
    }
)


class RegisterRequest(StrictDto):
    ic: str
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str
    password_confirm: str


class LoginRequest(StrictDto):
    ic: str
    password: str


class TokenPair(StrictDto):
    access_token: str
    refresh_token: str


class RefreshRequest(StrictDto):
    refresh_token: str


class PinRequest(StrictDto):
    pin: str = Field(pattern=r"^[0-9]{6}$")


class PinSetupRequest(PinRequest):
    pin_confirm: str = Field(pattern=r"^[0-9]{6}$")


class PaySessionRequest(StrictDto):
    kiosk_id: str
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class SessionRequest(StrictDto):
    session_id: str


class PayConfirmRequest(SessionRequest, PinRequest):
    nonce: str


class PayIdentityConfirmRequest(SessionRequest):
    nonce: str
    confirmed: bool


class TopUpRequest(StrictDto):
    amount: Decimal
    mock_source: str = Field(min_length=1, max_length=60)
    idempotency_key: str = Field(min_length=8, max_length=128)

    @field_validator("amount")
    @classmethod
    def valid_top_up_amount(cls, value: Decimal) -> Decimal:
        if (
            not value.is_finite()
            or value < Decimal("1.00")
            or value > Decimal("5000.00")
            or value.as_tuple().exponent < -2
        ):
            raise ValueError("invalid_amount")
        return value.quantize(Decimal("0.01"))


class TransferRequest(StrictDto):
    family_member_id: str
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    pin: str = Field(pattern=r"^[0-9]{6}$")
    idempotency_key: str = Field(min_length=8, max_length=128)


class FamilyCreateRequest(StrictDto):
    ic: str
    full_name: str = Field(min_length=2, max_length=120)
    relationship: str = Field(min_length=2, max_length=60)
    idempotency_key: str = Field(min_length=8, max_length=128)


class ActivateRequest(StrictDto):
    terms_acknowledged: Literal[True]
    privacy_acknowledged: Literal[True]


class ChangePasswordRequest(StrictDto):
    current_password: str
    new_password: str
    new_password_confirm: str


class ChangePinRequest(StrictDto):
    current_pin: str = Field(pattern=r"^[0-9]{6}$")
    new_pin: str = Field(pattern=r"^[0-9]{6}$")
    new_pin_confirm: str = Field(pattern=r"^[0-9]{6}$")


class PinVerifyRequest(PinRequest):
    purpose: str = Field(min_length=2, max_length=40)


class ProfilePatchRequest(StrictDto):
    full_name: str = Field(min_length=2, max_length=120)


class DeleteProfileRequest(StrictDto):
    password: str


def money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def iso(value: datetime) -> str:
    return value.isoformat()
