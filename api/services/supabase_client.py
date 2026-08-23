from __future__ import annotations

from ..config import Settings


def build_privileged_database_client(settings: Settings) -> object:
    """The only construction boundary for a future privileged database client.

    Architecture v0.3 does not approve the final connection method or shared
    SUPABASE_* names. Until DATABASE_URL and the repository implementation are
    approved, production startup must remain blocked rather than fall back to an
    unsafe browser credential.
    """
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required for the production repository")
    raise NotImplementedError("Production Supabase repository awaits approved connection credentials")
