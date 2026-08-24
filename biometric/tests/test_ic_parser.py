from __future__ import annotations

import pytest

from sfg_registration_core.ic_parser import extract_ic_candidates, normalize_malaysian_ic


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("900101011234", "900101-01-1234"),
        ("900101-01-1234", "900101-01-1234"),
        ("IC: 900101 01 1234", "900101-01-1234"),
    ],
)
def test_normalize_valid_synthetic_ic(source: str, expected: str) -> None:
    assert normalize_malaysian_ic(source) == expected


@pytest.mark.parametrize(
    "source",
    ["", "90010101123", "9001010112345", "90010A-01-1234", "123456 12", "IC unavailable"],
)
def test_malformed_or_incomplete_ic_is_not_fabricated(source: str) -> None:
    assert normalize_malaysian_ic(source) is None


def test_ambiguous_multiple_ic_candidates_return_null() -> None:
    result = extract_ic_candidates(["IC 900101-01-1234", "NO 910202-02-2345"])

    assert result.ic is None


def test_labelled_synthetic_name_and_ic_are_extracted() -> None:
    result = extract_ic_candidates(["NAME: ALICE TAN", "IC: 900101-01-1234"])

    assert result.full_name == "ALICE TAN"
    assert result.ic == "900101-01-1234"
    assert result.requires_confirmation is True


def test_unlabelled_or_insufficient_name_evidence_returns_null() -> None:
    assert extract_ic_candidates(["ALICE TAN", "900101-01-1234"]).full_name is None
    assert extract_ic_candidates(["NAME:", "IC: 900101-01-1234"]).full_name is None


def test_ambiguous_labelled_names_return_null() -> None:
    result = extract_ic_candidates(["NAME: ALICE TAN", "NAMA: BOB LIM", "IC: 900101-01-1234"])

    assert result.full_name is None
