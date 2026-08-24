"""Short-lived enrolment sessions for the trusted biometric tier.

A session binds one citizen subject to one capture run. It carries no biometric
material: staged templates live sealed in the encrypted store, keyed by the
session id. Expiry, nonce checking, and single-use consumption all fail closed.
"""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ..errors import ApiError


ENROL = "enrol"
REENROL = "reenrol"
PURPOSES = frozenset({ENROL, REENROL})


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass(slots=True)
class BiometricSession:
    session_id: str
    correlation_id: str
    nonce: str
    subject_id: str
    purpose: str
    expires_at: datetime
    status: str = "open"
    positions: set[str] = field(default_factory=set)

    @property
    def expired(self) -> bool:
        return now_utc() >= self.expires_at


class BiometricSessionRegistry:
    """In-memory registry of open capture sessions for the trusted tier."""

    def __init__(self, *, timeout_seconds: int) -> None:
        self._timeout_seconds = timeout_seconds
        self._sessions: dict[str, BiometricSession] = {}
        self._lock = threading.Lock()

    def create(self, subject_id: str, purpose: str) -> BiometricSession:
        if purpose not in PURPOSES:
            raise ApiError(422, "invalid_purpose", "Choose a supported enrolment purpose.")
        session = BiometricSession(
            session_id=secrets.token_urlsafe(24),
            correlation_id=secrets.token_urlsafe(16),
            nonce=secrets.token_urlsafe(18),
            subject_id=subject_id,
            purpose=purpose,
            expires_at=now_utc() + timedelta(seconds=self._timeout_seconds),
        )
        with self._lock:
            self._prune()
            # One open session per subject; starting a new run supersedes the old.
            for existing in [s for s in self._sessions.values() if s.subject_id == subject_id]:
                existing.status = "superseded"
            self._sessions[session.session_id] = session
        return session

    def require(self, session_id: str, subject_id: str, *, nonce: str | None = None) -> BiometricSession:
        with self._lock:
            self._prune()
            session = self._sessions.get(session_id)
            if (
                session is None
                or session.status != "open"
                or session.expired
                or session.subject_id != subject_id
                or (nonce is not None and not secrets.compare_digest(session.nonce, nonce))
            ):
                raise ApiError(404, "session_not_found", "This enrolment session is no longer available.")
            return session

    def consume(self, session: BiometricSession) -> None:
        with self._lock:
            session.status = "consumed"

    def cancel(self, session: BiometricSession) -> None:
        with self._lock:
            session.status = "cancelled"

    def _prune(self) -> None:
        stale = [key for key, session in self._sessions.items() if session.expired]
        for key in stale:
            self._sessions.pop(key, None)


__all__ = ["BiometricSession", "BiometricSessionRegistry", "ENROL", "PURPOSES", "REENROL"]
