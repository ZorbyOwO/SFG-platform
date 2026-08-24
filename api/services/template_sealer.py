"""Seal a staged template bundle for the hosted private biometric store.

The trusted tier holds the mother's protected template plus the pose and
compatibility fingerprint it was captured with. This module wraps that triple
into one JSON document, seals it with AES-256-GCM binding the subject, pose,
fingerprint, and envelope version as additional authenticated data, and emits
the exact wire fields the hosted ``private.sfg_biometric_templates`` CHECK
constraints accept:

* ``encrypted_payload`` = base64(nonce[12] || ciphertext || gcm_tag)
* ``nonce``             = base64(the same 12-byte nonce)

Binding the AAD means a sealed bundle cannot be replayed for a different
citizen, a different pose, or a different core runtime without failing
authenticated decryption. No raw frame ever passes through here: the caller
hands over the already-extracted template representation only.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ENCRYPTION_VERSION = "sfg-aesgcm-v1"
NONCE_BYTES = 12
KEY_BYTES = 32


class TemplateSealError(RuntimeError):
    """Raised when sealing or opening a bundle fails."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, repr=False)
class SealedTemplateBundle:
    """Wire-ready sealed bundle; safe to serialize toward the database only."""

    encrypted_payload: str
    nonce: str
    compatibility_fingerprint: str
    encryption_version: str = ENCRYPTION_VERSION

    def __repr__(self) -> str:
        return (
            "<SealedTemplateBundle "
            f"version={self.encryption_version!r} fingerprint={self.compatibility_fingerprint!r}>"
        )


def _aad(citizen_id: str, pose: str, fingerprint_id: str, version: str) -> bytes:
    return f"{citizen_id}|{pose}|{fingerprint_id}|{version}".encode("utf-8")


def _bundle_bytes(payload_base64: str, pose: str, fingerprint_id: str, version: str) -> bytes:
    import json

    return json.dumps(
        {"template": payload_base64, "pose": pose, "fingerprint": fingerprint_id},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def seal_template_bundle(
    *,
    citizen_id: str,
    pose: str,
    payload_base64: str,
    fingerprint_id: str,
    key: bytes,
) -> SealedTemplateBundle:
    """Seal one template bundle for upload to the hosted private store."""

    if not isinstance(key, (bytes, bytearray)) or len(key) != KEY_BYTES:
        raise TemplateSealError("TEMPLATE_SEAL_KEY_INVALID")
    if not payload_base64:
        raise TemplateSealError("TEMPLATE_PAYLOAD_EMPTY")
    version = ENCRYPTION_VERSION
    plaintext = _bundle_bytes(payload_base64, pose, fingerprint_id, version)
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(bytes(key)).encrypt(
        nonce, plaintext, _aad(citizen_id, pose, fingerprint_id, version)
    )
    return SealedTemplateBundle(
        encrypted_payload=base64.b64encode(nonce + sealed).decode("ascii"),
        nonce=base64.b64encode(nonce).decode("ascii"),
        compatibility_fingerprint=fingerprint_id,
    )


def open_template_bundle(
    *,
    citizen_id: str,
    pose: str,
    bundle: SealedTemplateBundle,
    key: bytes,
) -> str:
    """Authenticated-decrypt a bundle back to its protected serialization.

    Trusted-tier use only (e.g. a future kiosk matching path). Never call from
    a request path that serializes the result to a client.
    """

    if not isinstance(key, (bytes, bytearray)) or len(key) != KEY_BYTES:
        raise TemplateSealError("TEMPLATE_SEAL_KEY_INVALID")
    try:
        sealed = base64.b64decode(bundle.encrypted_payload, validate=True)
    except Exception:
        raise TemplateSealError("TEMPLATE_BUNDLE_MALFORMED") from None
    if len(sealed) <= NONCE_BYTES:
        raise TemplateSealError("TEMPLATE_BUNDLE_MALFORMED")
    try:
        opened = AESGCM(bytes(key)).decrypt(
            sealed[:NONCE_BYTES],
            sealed[NONCE_BYTES:],
            _aad(citizen_id, pose, bundle.compatibility_fingerprint, bundle.encryption_version),
        )
    except InvalidTag:
        raise TemplateSealError("TEMPLATE_BUNDLE_TAMPERED") from None
    import json

    try:
        document = json.loads(opened.decode("utf-8"))
    except Exception:
        raise TemplateSealError("TEMPLATE_BUNDLE_MALFORMED") from None
    payload = document.get("template")
    if not isinstance(payload, str) or not payload:
        raise TemplateSealError("TEMPLATE_BUNDLE_MALFORMED")
    return payload


__all__ = [
    "ENCRYPTION_VERSION",
    "KEY_BYTES",
    "NONCE_BYTES",
    "SealedTemplateBundle",
    "TemplateSealError",
    "open_template_bundle",
    "seal_template_bundle",
]
