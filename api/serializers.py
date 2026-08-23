from __future__ import annotations

from .contracts import iso, money
from .models import FamilyMember, Transaction, User, VerificationSession, Wallet
from .security import mask_ic


def wallet_dto(wallet: Wallet) -> dict[str, object]:
    return {
        "wallet_id": wallet.id,
        "owner_type": "family" if wallet.family_member_id else "main",
        "owner_id": wallet.family_member_id or wallet.user_id,
        "family_member_id": wallet.family_member_id,
        "currency": wallet.currency,
        "available_balance": money(wallet.balance),
    }


def transaction_dto(item: Transaction) -> dict[str, object]:
    direction = "credit" if item.type in {"topup", "transfer_in", "reversal"} else "debit"
    return {
        "transaction_id": item.id,
        "reference": item.reference,
        "type": item.type,
        "status": item.status,
        "direction": direction,
        "amount": money(item.amount),
        "balance_after": money(item.balance_after),
        "currency": "MYR",
        "merchant_name": item.merchant_name,
        "kiosk_id": item.kiosk_id,
        "family_member_id": item.family_member_id,
        "occurred_at": iso(item.created_at),
    }


def family_dto(member: FamilyMember, wallet: Wallet) -> dict[str, object]:
    return {
        "family_member_id": member.id,
        "full_name": member.full_name,
        "relationship": member.relationship,
        "ic_number_masked": mask_ic(member.ic),
        "enrolment_status": member.enrolment_status.value,
        "consent_status": member.consent_status.value,
        "profile_state": member.profile_state,
        "wallet": wallet_dto(wallet),
    }


def profile_dto(user: User) -> dict[str, object]:
    return {
        "citizen_display_name": user.full_name,
        "ic_number_masked": mask_ic(user.ic),
        "enrolment_status": user.enrolment_status.value,
        "consent_status": user.consent_status.value,
        "account_status": user.profile_state,
    }


def session_dto(session: VerificationSession) -> dict[str, object]:
    return {
        "session_id": session.session_id,
        "correlation_id": session.correlation_id,
        "nonce": session.nonce,
        "expires_at": iso(session.expires_at),
    }
