"""Encrypted, private, revocable storage for reusable biometric templates.

This is the trusted tier's only durable biometric boundary. It exists to satisfy
the SFG invariant that a reusable template is encrypted at rest, is never legible
to a browser or kiosk, and can be revoked as one atomic re-enrolment step.

The store deliberately holds the protected 512-byte serialization produced by the
frozen core, sealed with AES-GCM. It performs no matching, exposes no plaintext
through any ordinary projection, and never logs a payload.
"""

from __future__ import annotations

import base64
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


NONCE_BYTES = 12
KEY_BYTES = 32

# Internal storage lifecycle. These are deliberately lowercase and separate from
# the canonical v1.2 `template_status` family, which has only TEMPLATE_ACTIVE and
# TEMPLATE_REVOKED. A staged record has no canonical status because it is not yet
# part of the citizen's enrolment.
PENDING = "pending"
ACTIVE = "active"
REVOKED = "revoked"

_SCHEMA = """
create table if not exists face_templates (
  id integer primary key autoincrement,
  subject_id text not null,
  session_id text,
  pose text not null,
  sealed_template blob not null,
  fingerprint_id text not null,
  record_state text not null,
  created_at text not null,
  revoked_at text
);
create index if not exists face_templates_active_idx
  on face_templates(subject_id, pose) where record_state = 'active';
create index if not exists face_templates_pending_idx
  on face_templates(session_id, pose) where record_state = 'pending';
"""


class TemplateDecryptionError(RuntimeError):
    """Raised when a stored template fails authenticated decryption."""

    def __init__(self, code: str = "TEMPLATE_DECRYPTION_FAILED") -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, repr=False)
class ActiveTemplateRecord:
    """Protected in-process record for trusted backend code only."""

    pose: str
    payload_base64: str
    fingerprint_id: str

    def __repr__(self) -> str:
        return f"<ActiveTemplateRecord pose={self.pose!r} payload=<redacted>>"


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class EncryptedTemplateStore:
    """AES-GCM sealed template records in a private local database."""

    def __init__(self, database_path: str | Path, encryption_key: bytes) -> None:
        if not isinstance(encryption_key, (bytes, bytearray)) or len(encryption_key) != KEY_BYTES:
            raise ValueError("BIOMETRIC_TEMPLATE_ENCRYPTION_KEY must be 32 raw bytes")
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._cipher = AESGCM(bytes(encryption_key))
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    @staticmethod
    def generate_key() -> bytes:
        return AESGCM.generate_key(bit_length=256)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, isolation_level=None)
        connection.execute("pragma journal_mode=WAL")
        connection.execute("pragma synchronous=FULL")
        return connection

    def _associated_data(self, subject_id: str, pose: str, fingerprint_id: str) -> bytes:
        return f"{subject_id}|{pose}|{fingerprint_id}".encode("utf-8")

    def _seal(self, subject_id: str, pose: str, payload_base64: str, fingerprint_id: str) -> bytes:
        nonce = os.urandom(NONCE_BYTES)
        sealed = self._cipher.encrypt(
            nonce,
            payload_base64.encode("ascii"),
            self._associated_data(subject_id, pose, fingerprint_id),
        )
        return nonce + sealed

    def _open(self, subject_id: str, pose: str, sealed: bytes, fingerprint_id: str) -> str:
        if len(sealed) <= NONCE_BYTES:
            raise TemplateDecryptionError()
        try:
            opened = self._cipher.decrypt(
                sealed[:NONCE_BYTES],
                sealed[NONCE_BYTES:],
                self._associated_data(subject_id, pose, fingerprint_id),
            )
        except InvalidTag:
            raise TemplateDecryptionError() from None
        return opened.decode("ascii")

    def _active_count(self, connection: sqlite3.Connection, subject_id: str) -> int:
        [(count,)] = connection.execute(
            "select count(*) from face_templates where subject_id = ? and record_state = ?",
            (subject_id, ACTIVE),
        ).fetchall()
        return int(count)

    def store_active_template(
        self, subject_id: str, pose: str, payload_base64: str, fingerprint_id: str
    ) -> int:
        """Replace this subject's active template for one pose and report the active count."""

        sealed = self._seal(subject_id, pose, payload_base64, fingerprint_id)
        with self._lock, self._connect() as connection:
            connection.execute("begin immediate")
            connection.execute(
                "update face_templates set record_state = ?, revoked_at = ?"
                " where subject_id = ? and pose = ? and record_state = ?",
                (REVOKED, _now(), subject_id, pose, ACTIVE),
            )
            connection.execute(
                "insert into face_templates"
                " (subject_id, session_id, pose, sealed_template, fingerprint_id, record_state, created_at)"
                " values (?, null, ?, ?, ?, ?, ?)",
                (subject_id, pose, sealed, fingerprint_id, ACTIVE, _now()),
            )
            count = self._active_count(connection, subject_id)
            connection.execute("commit")
        return count

    def stage_template(
        self, session_id: str, subject_id: str, pose: str, payload_base64: str, fingerprint_id: str
    ) -> int:
        """Seal one capture for a session without touching the live enrolment."""

        sealed = self._seal(subject_id, pose, payload_base64, fingerprint_id)
        with self._lock, self._connect() as connection:
            connection.execute("begin immediate")
            connection.execute(
                "delete from face_templates where session_id = ? and pose = ? and record_state = ?",
                (session_id, pose, PENDING),
            )
            connection.execute(
                "insert into face_templates"
                " (subject_id, session_id, pose, sealed_template, fingerprint_id, record_state, created_at)"
                " values (?, ?, ?, ?, ?, ?, ?)",
                (subject_id, session_id, pose, sealed, fingerprint_id, PENDING, _now()),
            )
            [(count,)] = connection.execute(
                "select count(*) from face_templates where session_id = ? and record_state = ?",
                (session_id, PENDING),
            ).fetchall()
            connection.execute("commit")
        return int(count)

    def staged_positions(self, session_id: str) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "select pose from face_templates where session_id = ? and record_state = ?",
                (session_id, PENDING),
            ).fetchall()
        return {row[0] for row in rows}

    def read_session_staged_templates(
        self, session_id: str, subject_id: str
    ) -> list[ActiveTemplateRecord]:
        """Decrypt this session's staged bundles for the trusted upload path.

        Trusted-backend use only: called from /biometric/complete to seal and
        push each accepted capture. Never call from a path that serializes its
        result to a client.
        """

        with self._connect() as connection:
            rows = connection.execute(
                "select pose, sealed_template, fingerprint_id from face_templates"
                " where session_id = ? and subject_id = ? and record_state = ? order by pose",
                (session_id, subject_id, PENDING),
            ).fetchall()
        return [
            ActiveTemplateRecord(
                pose=pose,
                payload_base64=self._open(subject_id, pose, sealed, fingerprint_id),
                fingerprint_id=fingerprint_id,
            )
            for pose, sealed, fingerprint_id in rows
        ]

    def commit_session(self, session_id: str, subject_id: str) -> int:
        """Swap a completed session's staged captures in as the live generation.

        Revocation of the previous generation and activation of the replacement
        happen in one transaction, so an interrupted re-enrolment can never leave
        a citizen with a mixed or empty set of active templates.
        """

        with self._lock, self._connect() as connection:
            connection.execute("begin immediate")
            [(staged,)] = connection.execute(
                "select count(*) from face_templates"
                " where session_id = ? and subject_id = ? and record_state = ?",
                (session_id, subject_id, PENDING),
            ).fetchall()
            if staged:
                connection.execute(
                    "update face_templates set record_state = ?, revoked_at = ?"
                    " where subject_id = ? and record_state = ?",
                    (REVOKED, _now(), subject_id, ACTIVE),
                )
                connection.execute(
                    "update face_templates set record_state = ?"
                    " where session_id = ? and subject_id = ? and record_state = ?",
                    (ACTIVE, session_id, subject_id, PENDING),
                )
            count = self._active_count(connection, subject_id)
            connection.execute("commit")
        return count

    def discard_session(self, session_id: str) -> int:
        """Drop every staged capture for an abandoned or failed session."""

        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "delete from face_templates where session_id = ? and record_state = ?",
                (session_id, PENDING),
            )
            return int(cursor.rowcount)

    def active_positions(self, subject_id: str) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "select pose from face_templates where subject_id = ? and record_state = ?",
                (subject_id, ACTIVE),
            ).fetchall()
        return {row[0] for row in rows}

    def revoke_subject(self, subject_id: str) -> int:
        """Retire every active template for one subject as a single step."""

        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "update face_templates set record_state = ?, revoked_at = ?"
                " where subject_id = ? and record_state = ?",
                (REVOKED, _now(), subject_id, ACTIVE),
            )
            revoked = cursor.rowcount
        return int(revoked)

    def read_active_templates_for_trusted_backend(self, subject_id: str) -> list[ActiveTemplateRecord]:
        """Decrypt active templates for in-process trusted use only.

        Never call this from a request path that serializes its result to a client.
        """

        with self._connect() as connection:
            rows = connection.execute(
                "select pose, sealed_template, fingerprint_id from face_templates"
                " where subject_id = ? and record_state = ? order by pose",
                (subject_id, ACTIVE),
            ).fetchall()
        return [
            ActiveTemplateRecord(
                pose=pose,
                payload_base64=self._open(subject_id, pose, sealed, fingerprint_id),
                fingerprint_id=fingerprint_id,
            )
            for pose, sealed, fingerprint_id in rows
        ]


def load_or_create_key(key_file: str | Path) -> bytes:
    """Read the local development template key, creating it on first use."""

    path = Path(key_file)
    if path.is_file():
        material = base64.urlsafe_b64decode(path.read_text(encoding="utf-8").strip())
        if len(material) != KEY_BYTES:
            raise ValueError("The stored biometric template key is not 32 bytes")
        return material
    path.parent.mkdir(parents=True, exist_ok=True)
    material = EncryptedTemplateStore.generate_key()
    path.write_text(base64.urlsafe_b64encode(material).decode("ascii"), encoding="utf-8")
    return material


__all__ = [
    "ActiveTemplateRecord",
    "EncryptedTemplateStore",
    "TemplateDecryptionError",
    "load_or_create_key",
]
