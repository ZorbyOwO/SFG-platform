from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from ..config import Settings
from ..contracts import ConsentStatus, EnrolmentStatus
from ..errors import ApiError
from ..models import FamilyMember, Kiosk, Transaction, User, VerificationSession, Wallet
from ..security import hash_secret, token_digest, verify_secret


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


def reference(prefix: str = "SFG") -> str:
    return f"{prefix}-{uuid4().hex[:12].upper()}"


class MemoryStore:
    """Non-production repository used for local integration and tests.

    It is process-local, clears on restart, never retains uploaded image bytes, and
    deliberately does not claim Supabase or biometric conformance.
    """

    def __init__(self, settings: Settings, *, kiosk_key: str | None = None) -> None:
        self.settings = settings
        self.users: dict[str, User] = {}
        self.users_by_ic: dict[str, str] = {}
        self.users_by_email: dict[str, str] = {}
        self.family: dict[str, FamilyMember] = {}
        self.wallets: dict[str, Wallet] = {}
        self.transactions: dict[str, Transaction] = {}
        self.sessions: dict[str, VerificationSession] = {}
        self.kiosks: dict[str, Kiosk] = {}
        self.access_tokens: dict[str, str] = {}
        self.refresh_tokens: dict[str, str] = {}
        self.idempotency: dict[str, object] = {}
        self._mutation_lock = asyncio.Lock()
        key = kiosk_key or self._read_kiosk_key()
        if key:
            self.kiosks["SFG-KIOSK-001"] = Kiosk(
                id="SFG-KIOSK-001",
                kiosk_name="Kiosk UTC",
                merchant_name="Sarawak Mart Kuching",
                api_key_hash=hash_secret(key),
            )

    def _read_kiosk_key(self) -> str | None:
        path = self.settings.kiosk_key_file
        if not path.exists():
            return None
        value = path.read_text(encoding="utf-8").strip()
        return value or None

    async def create_user(self, ic: str, full_name: str, email: str, password: str) -> User:
        async with self._mutation_lock:
            if ic in self.users_by_ic or any(member.ic == ic for member in self.family.values()):
                raise ApiError(409, "ic_already_registered", "This IC number is already registered.")
            lowered = email.lower()
            if lowered in self.users_by_email:
                raise ApiError(409, "email_already_registered", "This email is already registered.")
            citizen_id = new_id()
            user = User(citizen_id, ic, full_name, lowered, hash_secret(password))
            self.users[citizen_id] = user
            self.users_by_ic[ic] = citizen_id
            self.users_by_email[lowered] = citizen_id
            wallet = Wallet(new_id(), citizen_id, None)
            self.wallets[wallet.id] = wallet
            return user

    def user_by_ic(self, ic: str) -> User | None:
        citizen_id = self.users_by_ic.get(ic)
        return self.users.get(citizen_id) if citizen_id else None

    def issue_tokens(self, user_id: str) -> tuple[str, str]:
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(40)
        self.access_tokens[token_digest(access)] = user_id
        self.refresh_tokens[token_digest(refresh)] = user_id
        return access, refresh

    def user_for_access_token(self, token: str) -> User | None:
        user_id = self.access_tokens.get(token_digest(token))
        return self.users.get(user_id) if user_id else None

    def refresh(self, token: str) -> tuple[str, str]:
        user_id = self.refresh_tokens.pop(token_digest(token), None)
        if not user_id or user_id not in self.users:
            raise ApiError(401, "invalid_session", "Your session is no longer valid.")
        return self.issue_tokens(user_id)

    def logout(self, token: str) -> None:
        self.access_tokens.pop(token_digest(token), None)

    def main_wallet(self, user_id: str) -> Wallet:
        for wallet in self.wallets.values():
            if wallet.user_id == user_id and wallet.family_member_id is None:
                return wallet
        raise ApiError(404, "wallet_not_found", "Wallet not found.")

    def family_wallet(self, user_id: str, member_id: str) -> Wallet:
        for wallet in self.wallets.values():
            if wallet.user_id == user_id and wallet.family_member_id == member_id:
                return wallet
        raise ApiError(404, "wallet_not_found", "Wallet not found.")

    def list_wallets(self, user_id: str) -> list[Wallet]:
        return [wallet for wallet in self.wallets.values() if wallet.user_id == user_id]

    def list_family(self, user_id: str) -> list[FamilyMember]:
        return [member for member in self.family.values() if member.user_id == user_id]

    def get_family(self, user_id: str, member_id: str) -> FamilyMember:
        member = self.family.get(member_id)
        if not member or member.user_id != user_id:
            raise ApiError(404, "family_member_not_found", "Family Member not found.")
        return member

    async def create_family_member(
        self, user_id: str, ic: str, full_name: str, relationship: str, idempotency_key: str
    ) -> FamilyMember:
        cached = self.idempotency.get(f"family:{user_id}:{idempotency_key}")
        if isinstance(cached, FamilyMember):
            return cached
        async with self._mutation_lock:
            cached = self.idempotency.get(f"family:{user_id}:{idempotency_key}")
            if isinstance(cached, FamilyMember):
                return cached
            if len(self.list_family(user_id)) >= self.settings.max_family_members:
                raise ApiError(409, "family_limit_reached", "The Family Member limit has been reached.")
            if ic in self.users_by_ic or any(item.ic == ic for item in self.family.values()):
                raise ApiError(409, "ic_already_registered", "This IC number is already registered.")
            member = FamilyMember(new_id(), user_id, ic, full_name, relationship)
            self.family[member.id] = member
            wallet = Wallet(new_id(), user_id, member.id)
            self.wallets[wallet.id] = wallet
            self.idempotency[f"family:{user_id}:{idempotency_key}"] = member
            return member

    def create_session(
        self,
        purpose: str,
        *,
        user_id: str | None = None,
        family_member_id: str | None = None,
        kiosk_id: str | None = None,
        amount: Decimal | None = None,
    ) -> VerificationSession:
        session = VerificationSession(
            session_id=new_id(),
            correlation_id=new_id(),
            nonce=secrets.token_urlsafe(24),
            purpose=purpose,
            expires_at=now_utc() + timedelta(seconds=self.settings.session_timeout_seconds),
            user_id=user_id,
            family_member_id=family_member_id,
            kiosk_id=kiosk_id,
            amount=amount,
        )
        self.sessions[session.session_id] = session
        return session

    def require_session(
        self,
        session_id: str,
        *,
        nonce: str | None = None,
        purpose: str | None = None,
        allowed_status: tuple[str, ...] = ("open",),
    ) -> VerificationSession:
        session = self.sessions.get(session_id)
        if not session:
            raise ApiError(404, "session_not_found", "This session is no longer available.")
        if now_utc() >= session.expires_at:
            session.status = "expired"
            raise ApiError(410, "session_expired", "This session expired. Please start again.")
        if purpose and session.purpose != purpose:
            raise ApiError(409, "invalid_session_order", "This action does not belong to this session.")
        if nonce is not None and not secrets.compare_digest(session.nonce, nonce):
            raise ApiError(401, "invalid_nonce", "This session could not be validated.")
        if session.status not in allowed_status:
            raise ApiError(409, "invalid_session_order", "This action is not available in the current session state.")
        return session

    def verify_kiosk(self, kiosk_id: str, supplied_key: str | None) -> Kiosk:
        kiosk = self.kiosks.get(kiosk_id)
        if not kiosk or not kiosk.is_active or not supplied_key or not verify_secret(supplied_key, kiosk.api_key_hash):
            raise ApiError(401, "invalid_kiosk", "The kiosk could not be authenticated.")
        return kiosk

    async def top_up(self, user: User, amount: Decimal, idempotency_key: str) -> Transaction:
        key = f"topup:{user.citizen_id}:{idempotency_key}"
        cached = self.idempotency.get(key)
        if isinstance(cached, Transaction):
            return cached
        async with self._mutation_lock:
            cached = self.idempotency.get(key)
            if isinstance(cached, Transaction):
                return cached
            if user.profile_state != "active":
                raise ApiError(403, "enrolment_incomplete", "Complete enrolment before using the wallet.")
            wallet = self.main_wallet(user.citizen_id)
            wallet.balance = (wallet.balance + amount).quantize(Decimal("0.01"))
            transaction = Transaction(
                new_id(), user.citizen_id, wallet.id, None, "topup", "completed", amount,
                wallet.balance, None, None, "app_topup", reference(), idempotency_key, None, now_utc(),
            )
            self.transactions[transaction.id] = transaction
            self.idempotency[key] = transaction
            return transaction

    async def transfer(
        self, user: User, member: FamilyMember, amount: Decimal, pin: str, idempotency_key: str
    ) -> tuple[Transaction, Wallet, Wallet]:
        key = f"transfer:{user.citizen_id}:{idempotency_key}"
        cached = self.idempotency.get(key)
        if isinstance(cached, tuple):
            return cached
        if not verify_secret(pin, user.pin_hash):
            raise ApiError(401, "wrong_pin", "The PIN was not accepted.", pin_status="PIN_REJECTED")
        if member.profile_state != "active":
            raise ApiError(409, "recipient_unavailable", "This Family Member is not available for transfers.")
        if amount < self.settings.transfer_min_amount or amount > self.settings.transfer_max_amount:
            raise ApiError(422, "invalid_amount", "Enter an amount within the permitted transfer range.")
        async with self._mutation_lock:
            cached = self.idempotency.get(key)
            if isinstance(cached, tuple):
                return cached
            main = self.main_wallet(user.citizen_id)
            managed = self.family_wallet(user.citizen_id, member.id)
            if main.balance < amount:
                raise ApiError(409, "insufficient_funds", "The main wallet has insufficient funds.")
            main.balance = (main.balance - amount).quantize(Decimal("0.01"))
            managed.balance = (managed.balance + amount).quantize(Decimal("0.01"))
            correlation = new_id()
            ref = reference("SFG-T")
            out = Transaction(
                new_id(), user.citizen_id, main.id, None, "transfer_out", "completed", amount,
                main.balance, None, None, "guardian_pin", ref, idempotency_key, correlation, now_utc(),
            )
            incoming = Transaction(
                new_id(), user.citizen_id, managed.id, member.id, "transfer_in", "completed", amount,
                managed.balance, None, None, "guardian_pin", ref, None, correlation, now_utc(),
            )
            self.transactions[out.id] = out
            self.transactions[incoming.id] = incoming
            result = (out, main, managed)
            self.idempotency[key] = result
            return result

    async def charge(self, session: VerificationSession, idempotency_key: str) -> Transaction:
        key = f"charge:{idempotency_key}"
        cached = self.idempotency.get(key)
        if isinstance(cached, Transaction):
            return cached
        async with self._mutation_lock:
            cached = self.idempotency.get(key)
            if isinstance(cached, Transaction):
                return cached
            if not session.matched_user or session.amount is None or not session.kiosk_id:
                raise ApiError(409, "invalid_session_order", "The payment session is incomplete.")
            kiosk = self.kiosks[session.kiosk_id]
            wallet = (
                self.family_wallet(session.matched_user, session.matched_family_member)
                if session.matched_family_member
                else self.main_wallet(session.matched_user)
            )
            if wallet.balance < session.amount:
                raise ApiError(
                    402, "insufficient_funds", "The wallet has insufficient funds.",
                    pin_status="PIN_ACCEPTED", authorization_status="AUTHORIZATION_GRANTED",
                )
            wallet.balance = (wallet.balance - session.amount).quantize(Decimal("0.01"))
            transaction = Transaction(
                new_id(), session.matched_user, wallet.id, session.matched_family_member,
                "purchase", "completed", session.amount, wallet.balance, kiosk.merchant_name,
                kiosk.id, "face_pin", reference(), idempotency_key, session.correlation_id, now_utc(),
            )
            self.transactions[transaction.id] = transaction
            self.idempotency[key] = transaction
            return transaction

    def list_transactions(self, user_id: str, family_member_id: str | None = None) -> list[Transaction]:
        rows = [
            item for item in self.transactions.values()
            if item.user_id == user_id and (family_member_id is None or item.family_member_id == family_member_id)
        ]
        return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def get_transaction(self, user_id: str, transaction_id: str) -> Transaction:
        item = self.transactions.get(transaction_id)
        if not item or item.user_id != user_id:
            raise ApiError(404, "transaction_not_found", "Transaction not found.")
        return item

    async def delete_user(self, user: User) -> None:
        async with self._mutation_lock:
            family_ids = {item.id for item in self.list_family(user.citizen_id)}
            wallet_ids = {item.id for item in self.list_wallets(user.citizen_id)}
            self.family = {key: value for key, value in self.family.items() if key not in family_ids}
            self.wallets = {key: value for key, value in self.wallets.items() if key not in wallet_ids}
            for transaction in self.transactions.values():
                if transaction.user_id == user.citizen_id:
                    transaction.user_id = ""
                    transaction.wallet_id = ""
                    transaction.family_member_id = None
            self.users_by_ic.pop(user.ic, None)
            self.users_by_email.pop(user.email, None)
            self.users.pop(user.citizen_id, None)
            self.access_tokens = {key: value for key, value in self.access_tokens.items() if value != user.citizen_id}
            self.refresh_tokens = {key: value for key, value in self.refresh_tokens.items() if value != user.citizen_id}
