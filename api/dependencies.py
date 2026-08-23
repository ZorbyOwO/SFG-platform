from __future__ import annotations

from fastapi import Header, Request

from .errors import ApiError
from .models import User
from .repositories.memory import MemoryStore


def get_store(request: Request) -> MemoryStore:
    return request.app.state.store


def get_access_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(401, "authentication_required", "Sign in to continue.")
    token = authorization[7:].strip()
    if not token:
        raise ApiError(401, "authentication_required", "Sign in to continue.")
    return token


def current_user(request: Request, authorization: str | None = Header(default=None)) -> User:
    store = get_store(request)
    user = store.user_for_access_token(get_access_token(authorization))
    if not user:
        raise ApiError(401, "invalid_session", "Your session expired. Please sign in again.")
    return user


def kiosk_key(x_kiosk_key: str | None = Header(default=None)) -> str | None:
    return x_kiosk_key
