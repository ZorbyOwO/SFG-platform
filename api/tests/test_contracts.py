from __future__ import annotations

from api.contracts import CANONICAL_SHARED_FIELDS, CANONICAL_STATUS_FAMILIES


def test_complete_contract_vocabulary() -> None:
    assert len(CANONICAL_SHARED_FIELDS) == 22
    assert sum(len(values) for values in CANONICAL_STATUS_FAMILIES.values()) == 32
    assert all(value == value.upper() for values in CANONICAL_STATUS_FAMILIES.values() for value in values)
    assert CANONICAL_STATUS_FAMILIES["liveness_status"] == (
        "PAD_LIVE", "PAD_REJECT", "PAD_UNCERTAIN", "PAD_ERROR"
    )


def test_payment_contract_does_not_alias_service_access() -> None:
    assert "SERVICE_ACCESS_GRANTED" not in CANONICAL_STATUS_FAMILIES["authorization_status"]
    assert "AUTHORIZATION_GRANTED" not in CANONICAL_STATUS_FAMILIES["service_access_status"]
