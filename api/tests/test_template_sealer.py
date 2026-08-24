"""Unit tests for the AES-GCM template bundle sealer."""

from __future__ import annotations

import base64

import pytest

from api.services.template_sealer import (
    ENCRYPTION_VERSION,
    NONCE_BYTES,
    SealedTemplateBundle,
    TemplateSealError,
    open_template_bundle,
    seal_template_bundle,
)


KEY = bytes(range(32))
CITIZEN = "11111111-2222-3333-4444-555555555555"
POSE = "front"
PAYLOAD = base64.b64encode(bytes(512)).decode("ascii")
FINGERPRINT = "a18bbbd47a57d14d"


def _seal() -> SealedTemplateBundle:
    return seal_template_bundle(
        citizen_id=CITIZEN, pose=POSE, payload_base64=PAYLOAD, fingerprint_id=FINGERPRINT, key=KEY
    )


def test_seal_produces_wire_fields_matching_db_contract():
    bundle = _seal()
    assert bundle.encryption_version == ENCRYPTION_VERSION
    assert bundle.compatibility_fingerprint == FINGERPRINT
    sealed = base64.b64decode(bundle.encrypted_payload, validate=True)
    nonce = base64.b64decode(bundle.nonce, validate=True)
    # Hosted CHECK constraints: payload strictly longer than a bare template
    # envelope plus overhead, and the standalone nonce is exactly 12 bytes.
    assert len(nonce) == NONCE_BYTES
    assert sealed[:NONCE_BYTES] == nonce
    assert len(sealed) > 512


def test_round_trip_returns_original_payload():
    bundle = _seal()
    opened = open_template_bundle(citizen_id=CITIZEN, pose=POSE, bundle=bundle, key=KEY)
    assert opened == PAYLOAD


def test_tampered_ciphertext_fails_closed():
    bundle = _seal()
    raw = bytearray(base64.b64decode(bundle.encrypted_payload))
    raw[-1] ^= 0xFF
    tampered = SealedTemplateBundle(
        encrypted_payload=base64.b64encode(bytes(raw)).decode("ascii"),
        nonce=bundle.nonce,
        compatibility_fingerprint=bundle.compatibility_fingerprint,
        encryption_version=bundle.encryption_version,
    )
    with pytest.raises(TemplateSealError) as excinfo:
        open_template_bundle(citizen_id=CITIZEN, pose=POSE, bundle=tampered, key=KEY)
    assert excinfo.value.code == "TEMPLATE_BUNDLE_TAMPERED"


def test_replay_for_another_citizen_fails_authentication():
    bundle = _seal()
    other = "99999999-8888-7777-6666-555555555555"
    with pytest.raises(TemplateSealError) as excinfo:
        open_template_bundle(citizen_id=other, pose=POSE, bundle=bundle, key=KEY)
    assert excinfo.value.code == "TEMPLATE_BUNDLE_TAMPERED"


def test_replay_for_another_pose_fails_authentication():
    bundle = _seal()
    with pytest.raises(TemplateSealError):
        open_template_bundle(citizen_id=CITIZEN, pose="left", bundle=bundle, key=KEY)


def test_wrong_key_fails_authentication():
    bundle = _seal()
    wrong = bytes(reversed(KEY))
    with pytest.raises(TemplateSealError):
        open_template_bundle(citizen_id=CITIZEN, pose=POSE, bundle=bundle, key=wrong)


def test_invalid_key_length_is_rejected_at_seal_time():
    with pytest.raises(TemplateSealError) as excinfo:
        seal_template_bundle(
            citizen_id=CITIZEN,
            pose=POSE,
            payload_base64=PAYLOAD,
            fingerprint_id=FINGERPRINT,
            key=b"short",
        )
    assert excinfo.value.code == "TEMPLATE_SEAL_KEY_INVALID"


def test_each_seal_uses_a_fresh_nonce():
    first, second = _seal(), _seal()
    assert first.encrypted_payload != second.encrypted_payload
    assert first.nonce != second.nonce


def test_empty_payload_is_refused():
    with pytest.raises(TemplateSealError) as excinfo:
        seal_template_bundle(
            citizen_id=CITIZEN, pose=POSE, payload_base64="", fingerprint_id=FINGERPRINT, key=KEY
        )
    assert excinfo.value.code == "TEMPLATE_PAYLOAD_EMPTY"
