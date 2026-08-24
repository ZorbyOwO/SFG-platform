from __future__ import annotations

import base64
import sqlite3
from pathlib import Path

import pytest

from api.services.template_store import EncryptedTemplateStore, TemplateDecryptionError


FINGERPRINT = "a18bbbd47a57d14d"


def payload(marker: bytes = b"SENSITIVE-TEMPLATE-BYTES") -> str:
    return base64.b64encode(marker + b"\x00" * (512 - len(marker))).decode("ascii")


@pytest.fixture()
def store(tmp_path: Path) -> EncryptedTemplateStore:
    return EncryptedTemplateStore(tmp_path / "templates.sqlite3", EncryptedTemplateStore.generate_key())


def test_storing_each_pose_reports_the_active_position_count(store: EncryptedTemplateStore) -> None:
    assert store.store_active_template("citizen-1", "front", payload(), FINGERPRINT) == 1
    assert store.store_active_template("citizen-1", "right", payload(), FINGERPRINT) == 2
    assert store.store_active_template("citizen-1", "left", payload(), FINGERPRINT) == 3
    assert store.active_positions("citizen-1") == {"front", "right", "left"}


def test_recapturing_one_pose_replaces_it_instead_of_adding_a_second_active_template(
    store: EncryptedTemplateStore,
) -> None:
    store.store_active_template("citizen-1", "front", payload(b"FIRST"), FINGERPRINT)
    assert store.store_active_template("citizen-1", "front", payload(b"SECOND"), FINGERPRINT) == 1
    assert store.active_positions("citizen-1") == {"front"}


def test_stored_template_bytes_are_not_readable_in_the_database_file(
    tmp_path: Path, store: EncryptedTemplateStore
) -> None:
    store.store_active_template("citizen-1", "front", payload(b"SENSITIVE-TEMPLATE-BYTES"), FINGERPRINT)

    raw = (tmp_path / "templates.sqlite3").read_bytes()

    assert b"SENSITIVE-TEMPLATE-BYTES" not in raw
    assert payload(b"SENSITIVE-TEMPLATE-BYTES").encode("ascii") not in raw


def test_revoking_a_subject_clears_every_active_position(store: EncryptedTemplateStore) -> None:
    store.store_active_template("citizen-1", "front", payload(), FINGERPRINT)
    store.store_active_template("citizen-1", "left", payload(), FINGERPRINT)

    assert store.revoke_subject("citizen-1") == 2
    assert store.active_positions("citizen-1") == set()


def test_revoking_one_subject_leaves_another_subject_untouched(store: EncryptedTemplateStore) -> None:
    store.store_active_template("citizen-1", "front", payload(), FINGERPRINT)
    store.store_active_template("citizen-2", "front", payload(), FINGERPRINT)

    store.revoke_subject("citizen-1")

    assert store.active_positions("citizen-2") == {"front"}


def test_reenrolment_after_revocation_leaves_only_the_replacement_templates_active(
    store: EncryptedTemplateStore,
) -> None:
    for pose in ("front", "right", "left"):
        store.store_active_template("citizen-1", pose, payload(b"OLD"), FINGERPRINT)
    store.revoke_subject("citizen-1")
    for pose in ("front", "right", "left"):
        store.store_active_template("citizen-1", pose, payload(b"NEW"), FINGERPRINT)

    active = store.read_active_templates_for_trusted_backend("citizen-1")

    assert len(active) == 3
    assert {record.pose for record in active} == {"front", "right", "left"}
    assert all(base64.b64decode(record.payload_base64).startswith(b"NEW") for record in active)


def test_a_trusted_read_returns_the_exact_stored_payload(store: EncryptedTemplateStore) -> None:
    store.store_active_template("citizen-1", "front", payload(b"EXACT"), FINGERPRINT)

    [record] = store.read_active_templates_for_trusted_backend("citizen-1")

    assert record.payload_base64 == payload(b"EXACT")
    assert record.fingerprint_id == FINGERPRINT


def test_a_different_key_cannot_decrypt_a_stored_template(tmp_path: Path) -> None:
    database = tmp_path / "templates.sqlite3"
    EncryptedTemplateStore(database, EncryptedTemplateStore.generate_key()).store_active_template(
        "citizen-1", "front", payload(), FINGERPRINT
    )

    intruder = EncryptedTemplateStore(database, EncryptedTemplateStore.generate_key())

    with pytest.raises(TemplateDecryptionError):
        intruder.read_active_templates_for_trusted_backend("citizen-1")


def test_tampering_with_stored_ciphertext_is_detected(tmp_path: Path) -> None:
    database = tmp_path / "templates.sqlite3"
    store = EncryptedTemplateStore(database, EncryptedTemplateStore.generate_key())
    store.store_active_template("citizen-1", "front", payload(), FINGERPRINT)

    with sqlite3.connect(database) as connection:
        [(rowid, blob)] = connection.execute("select rowid, sealed_template from face_templates").fetchall()
        connection.execute(
            "update face_templates set sealed_template = ? where rowid = ?",
            (blob[:-1] + bytes([blob[-1] ^ 0xFF]), rowid),
        )

    with pytest.raises(TemplateDecryptionError):
        store.read_active_templates_for_trusted_backend("citizen-1")
