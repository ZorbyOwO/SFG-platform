from __future__ import annotations

import pytest

from api.errors import ApiError
from api.services.identity import SupabaseTokenVerifier


class StubUserEndpoint:
    """Stands in for the Supabase /auth/v1/user call."""

    def __init__(self, responses: dict[str, str | None]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, token: str) -> str | None:
        self.calls.append(token)
        return self.responses.get(token)


def test_a_valid_token_resolves_to_the_supabase_subject_id() -> None:
    endpoint = StubUserEndpoint({"good-token": "8f14e45f-ea8d-4c2b-9f7a-1d2c3b4a5e6f"})
    verifier = SupabaseTokenVerifier(resolve_subject=endpoint, cache_seconds=60)

    assert verifier.subject_for("good-token") == "8f14e45f-ea8d-4c2b-9f7a-1d2c3b4a5e6f"


def test_an_unknown_token_is_rejected_as_an_invalid_session() -> None:
    verifier = SupabaseTokenVerifier(resolve_subject=StubUserEndpoint({}), cache_seconds=60)

    with pytest.raises(ApiError) as raised:
        verifier.subject_for("forged-token")

    assert raised.value.status_code == 401
    assert raised.value.error == "invalid_session"


def test_an_empty_token_is_rejected_without_calling_supabase() -> None:
    endpoint = StubUserEndpoint({})
    verifier = SupabaseTokenVerifier(resolve_subject=endpoint, cache_seconds=60)

    with pytest.raises(ApiError):
        verifier.subject_for("")

    assert endpoint.calls == []


def test_a_repeated_token_is_verified_once_inside_the_cache_window() -> None:
    endpoint = StubUserEndpoint({"good-token": "subject-1"})
    verifier = SupabaseTokenVerifier(resolve_subject=endpoint, cache_seconds=60)

    verifier.subject_for("good-token")
    verifier.subject_for("good-token")

    assert endpoint.calls == ["good-token"]


def test_an_expired_cache_entry_is_verified_again() -> None:
    endpoint = StubUserEndpoint({"good-token": "subject-1"})
    clock = iter([100.0, 400.0])
    verifier = SupabaseTokenVerifier(
        resolve_subject=endpoint, cache_seconds=60, clock=lambda: next(clock)
    )

    verifier.subject_for("good-token")
    verifier.subject_for("good-token")

    assert endpoint.calls == ["good-token", "good-token"]


def test_a_rejected_token_is_never_cached_as_valid() -> None:
    endpoint = StubUserEndpoint({})
    verifier = SupabaseTokenVerifier(resolve_subject=endpoint, cache_seconds=60)

    for _ in range(2):
        with pytest.raises(ApiError):
            verifier.subject_for("forged-token")

    assert endpoint.calls == ["forged-token", "forged-token"]


def test_an_upstream_failure_fails_closed_rather_than_admitting_the_caller() -> None:
    def exploding(token: str) -> str | None:
        raise RuntimeError("supabase unreachable")

    verifier = SupabaseTokenVerifier(resolve_subject=exploding, cache_seconds=60)

    with pytest.raises(ApiError) as raised:
        verifier.subject_for("good-token")

    assert raised.value.status_code == 503
    assert raised.value.error == "identity_verification_unavailable"
