"""Identity boundary between the Supabase-authenticated browser and this tier.

The citizen app holds a Supabase session, while the trusted biometric tier holds
no Supabase secret. Rather than inventing a credential, this verifier asks
Supabase itself to validate the bearer token and return its subject. Only the
public project URL and the browser-safe publishable key are required.

Verification failures and upstream outages both fail closed.
"""

from __future__ import annotations

import logging
from time import monotonic
from typing import Callable

from ..errors import ApiError


LOGGER = logging.getLogger(__name__)

ResolveSubject = Callable[[str], str | None]


class SupabaseTokenVerifier:
    """Resolve a Supabase access token to its subject id, with a short cache."""

    def __init__(
        self,
        *,
        resolve_subject: ResolveSubject,
        cache_seconds: int = 60,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._resolve_subject = resolve_subject
        self._cache_seconds = cache_seconds
        self._clock = clock
        self._cache: dict[str, tuple[str, float]] = {}

    def subject_for(self, access_token: str) -> str:
        if not access_token or not access_token.strip():
            raise ApiError(401, "authentication_required", "Sign in to continue.")

        now = self._clock()
        cached = self._cache.get(access_token)
        if cached is not None and cached[1] > now:
            return cached[0]
        self._cache.pop(access_token, None)

        try:
            subject = self._resolve_subject(access_token)
        except ApiError:
            raise
        except Exception as exc:
            LOGGER.warning("identity code=IDENTITY_UPSTREAM_FAILURE detail=%s", type(exc).__name__)
            raise ApiError(
                503,
                "identity_verification_unavailable",
                "Identity verification is temporarily unavailable. Try again shortly.",
            ) from None

        if not subject:
            raise ApiError(401, "invalid_session", "Your session expired. Please sign in again.")

        self._cache[access_token] = (subject, now + self._cache_seconds)
        return subject


def supabase_user_endpoint(supabase_url: str, publishable_key: str, *, timeout_seconds: float = 8.0) -> ResolveSubject:
    """Build the real resolver that asks Supabase to validate a bearer token."""

    base = supabase_url.rstrip("/")

    def resolve(access_token: str) -> str | None:
        import httpx

        response = httpx.get(
            f"{base}/auth/v1/user",
            headers={"Authorization": f"Bearer {access_token}", "apikey": publishable_key},
            timeout=timeout_seconds,
        )
        if response.status_code in {401, 403}:
            return None
        response.raise_for_status()
        payload = response.json()
        subject = payload.get("id") if isinstance(payload, dict) else None
        return subject if isinstance(subject, str) and subject else None

    return resolve


__all__ = ["ResolveSubject", "SupabaseTokenVerifier", "supabase_user_endpoint"]
