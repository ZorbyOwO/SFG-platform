from __future__ import annotations

import base64
from pathlib import Path

import pytest

from api.services.template_store import EncryptedTemplateStore


FINGERPRINT = "a18bbbd47a57d14d"


def payload(marker: bytes) -> str:
    return base64.b64encode(marker + b"\x00" * (512 - len(marker))).decode("ascii")


@pytest.fixture()
def store(tmp_path: Path) -> EncryptedTemplateStore:
    return EncryptedTemplateStore(tmp_path / "templates.sqlite3", EncryptedTemplateStore.generate_key())


def stage_all(store: EncryptedTemplateStore, session: str, subject: str, marker: bytes) -> None:
    for pose in ("front", "right", "left"):
        store.stage_template(session, subject, pose, payload(marker), FINGERPRINT)


def test_staged_templates_are_not_active_until_the_session_is_committed(store: EncryptedTemplateStore) -> None:
    stage_all(store, "session-1", "citizen-1", b"NEW")

    assert store.staged_positions("session-1") == {"front", "right", "left"}
    assert store.active_positions("citizen-1") == set()


def test_committing_a_session_promotes_every_staged_pose(store: EncryptedTemplateStore) -> None:
    stage_all(store, "session-1", "citizen-1", b"NEW")

    assert store.commit_session("session-1", "citizen-1") == 3
    assert store.active_positions("citizen-1") == {"front", "right", "left"}
    assert store.staged_positions("session-1") == set()


def test_restaging_a_pose_replaces_the_earlier_staged_capture(store: EncryptedTemplateStore) -> None:
    store.stage_template("session-1", "citizen-1", "front", payload(b"FIRST"), FINGERPRINT)
    store.stage_template("session-1", "citizen-1", "front", payload(b"SECOND"), FINGERPRINT)
    store.commit_session("session-1", "citizen-1")

    [record] = store.read_active_templates_for_trusted_backend("citizen-1")

    assert base64.b64decode(record.payload_base64).startswith(b"SECOND")


def test_reenrolment_commit_replaces_the_whole_previous_generation_atomically(
    store: EncryptedTemplateStore,
) -> None:
    stage_all(store, "session-old", "citizen-1", b"OLD")
    store.commit_session("session-old", "citizen-1")

    stage_all(store, "session-new", "citizen-1", b"NEW")
    store.commit_session("session-new", "citizen-1")

    active = store.read_active_templates_for_trusted_backend("citizen-1")

    assert len(active) == 3
    assert all(base64.b64decode(record.payload_base64).startswith(b"NEW") for record in active)


def test_an_abandoned_reenrolment_leaves_the_previous_generation_active(store: EncryptedTemplateStore) -> None:
    stage_all(store, "session-old", "citizen-1", b"OLD")
    store.commit_session("session-old", "citizen-1")

    stage_all(store, "session-new", "citizen-1", b"NEW")
    store.discard_session("session-new")

    active = store.read_active_templates_for_trusted_backend("citizen-1")

    assert len(active) == 3
    assert all(base64.b64decode(record.payload_base64).startswith(b"OLD") for record in active)


def test_committing_an_empty_session_does_not_revoke_the_existing_generation(
    store: EncryptedTemplateStore,
) -> None:
    stage_all(store, "session-old", "citizen-1", b"OLD")
    store.commit_session("session-old", "citizen-1")

    assert store.commit_session("session-empty", "citizen-1") == 3
    assert store.active_positions("citizen-1") == {"front", "right", "left"}


def test_one_subject_session_never_promotes_another_subject_staged_capture(
    store: EncryptedTemplateStore,
) -> None:
    store.stage_template("session-1", "citizen-1", "front", payload(b"MINE"), FINGERPRINT)
    store.stage_template("session-2", "citizen-2", "front", payload(b"THEIRS"), FINGERPRINT)

    store.commit_session("session-1", "citizen-1")

    assert store.active_positions("citizen-2") == set()
    assert store.staged_positions("session-2") == {"front"}


def test_committing_with_a_mismatched_subject_promotes_nothing(store: EncryptedTemplateStore) -> None:
    stage_all(store, "session-1", "citizen-1", b"NEW")

    assert store.commit_session("session-1", "attacker") == 0
    assert store.active_positions("attacker") == set()
    assert store.staged_positions("session-1") == {"front", "right", "left"}
