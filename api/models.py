from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .contracts import (
    AuthorizationStatus,
    CaptureStatus,
    ConsentStatus,
    EnrolmentStatus,
    IdentityConfirmationStatus,
    LivenessStatus,
    MatchStatus,
    PinStatus,
)


@dataclass(slots=True)
class User:
    citizen_id: str
    ic: str
    full_name: str
    email: str
    password_hash: str
    pin_hash: str | None = None
    enrolment_status: EnrolmentStatus = EnrolmentStatus.STARTED
    consent_status: ConsentStatus = ConsentStatus.REQUIRED
    profile_state: str = "pending_face"
    templates_stored: int = 0


@dataclass(slots=True)
class FamilyMember:
    id: str
    user_id: str
    ic: str
    full_name: str
    relationship: str
    enrolment_status: EnrolmentStatus = EnrolmentStatus.STARTED
    consent_status: ConsentStatus = ConsentStatus.REQUIRED
    profile_state: str = "pending_face"
    templates_stored: int = 0


@dataclass(slots=True)
class Wallet:
    id: str
    user_id: str
    family_member_id: str | None
    balance: Decimal = Decimal("0.00")
    currency: str = "MYR"


@dataclass(slots=True)
class Transaction:
    id: str
    user_id: str
    wallet_id: str
    family_member_id: str | None
    type: str
    status: str
    amount: Decimal
    balance_after: Decimal
    merchant_name: str | None
    kiosk_id: str | None
    auth_method: str
    reference: str
    idempotency_key: str | None
    correlation_id: str | None
    created_at: datetime


@dataclass(slots=True)
class VerificationSession:
    session_id: str
    correlation_id: str
    nonce: str
    purpose: str
    expires_at: datetime
    user_id: str | None = None
    family_member_id: str | None = None
    kiosk_id: str | None = None
    amount: Decimal | None = None
    status: str = "open"
    capture_status: CaptureStatus | None = None
    liveness_status: LivenessStatus | None = None
    match_status: MatchStatus | None = None
    identity_confirmation_status: IdentityConfirmationStatus | None = None
    pin_status: PinStatus | None = None
    authorization_status: AuthorizationStatus | None = None
    matched_user: str | None = None
    matched_family_member: str | None = None
    pin_attempts: int = 0
    identify_frames: int = 0
    positions: set[str] = field(default_factory=set)
    verification_completed_at: datetime | None = None


@dataclass(slots=True)
class Kiosk:
    id: str
    kiosk_name: str
    merchant_name: str
    api_key_hash: str
    is_active: bool = True
