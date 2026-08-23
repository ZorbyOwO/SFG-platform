from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request, Response, status

from ..contracts import (
    ChangePasswordRequest,
    ChangePinRequest,
    LoginRequest,
    PinStatus,
    PinVerifyRequest,
    RefreshRequest,
    RegisterRequest,
)
from ..dependencies import current_user, get_access_token, get_store
from ..errors import ApiError
from ..models import User
from ..repositories.memory import MemoryStore
from ..security import normalize_ic, validate_password, validate_pin, verify_secret, hash_secret


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request) -> dict[str, object]:
    request.app.state.rate_limiter.check(f"register:{request.client.host if request.client else 'unknown'}", limit=10, window_seconds=60)
    if payload.password != payload.password_confirm:
        raise ApiError(422, "password_mismatch", "The password confirmation does not match.")
    validate_password(payload.password)
    ic = normalize_ic(payload.ic)
    store = get_store(request)
    user = await store.create_user(ic, payload.full_name, str(payload.email), payload.password)
    access, refresh = store.issue_tokens(user.citizen_id)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "citizen_id": user.citizen_id,
        "enrolment_status": user.enrolment_status.value,
        "next_step": "face_enrolment",
    }


@router.post("/login")
async def login(payload: LoginRequest, request: Request) -> dict[str, object]:
    request.app.state.rate_limiter.check(f"login:{request.client.host if request.client else 'unknown'}", limit=20, window_seconds=60)
    try:
        ic = normalize_ic(payload.ic)
    except ApiError:
        ic = "000000000000"
    store = get_store(request)
    user = store.user_by_ic(ic)
    accepted = verify_secret(payload.password, user.password_hash if user else None)
    if not user or not accepted or user.profile_state == "suspended":
        raise ApiError(401, "invalid_credentials", "IC number or password is incorrect.")
    access, refresh = store.issue_tokens(user.citizen_id)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "enrolment_status": user.enrolment_status.value,
    }


@router.post("/refresh")
async def refresh(payload: RefreshRequest, request: Request) -> dict[str, str]:
    access, refresh_token = get_store(request).refresh(payload.refresh_token)
    return {"access_token": access, "refresh_token": refresh_token}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request, authorization: str | None = Header(default=None), _: User = Depends(current_user)
) -> Response:
    get_store(request).logout(get_access_token(authorization))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(payload: ChangePasswordRequest, user: User = Depends(current_user)) -> Response:
    if not verify_secret(payload.current_password, user.password_hash):
        raise ApiError(401, "invalid_credentials", "The current password was not accepted.")
    if payload.new_password != payload.new_password_confirm:
        raise ApiError(422, "password_mismatch", "The password confirmation does not match.")
    validate_password(payload.new_password)
    user.password_hash = hash_secret(payload.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/pin/verify")
async def verify_pin(payload: PinVerifyRequest, user: User = Depends(current_user)) -> dict[str, str]:
    if not verify_secret(payload.pin, user.pin_hash):
        raise ApiError(401, "wrong_pin", "The PIN was not accepted.", pin_status=PinStatus.REJECTED.value)
    return {"pin_status": PinStatus.ACCEPTED.value}


@router.post("/pin/change")
async def change_pin(payload: ChangePinRequest, user: User = Depends(current_user)) -> dict[str, str]:
    if not verify_secret(payload.current_pin, user.pin_hash):
        raise ApiError(401, "wrong_pin", "The PIN was not accepted.", pin_status=PinStatus.REJECTED.value)
    if payload.new_pin != payload.new_pin_confirm:
        raise ApiError(422, "pin_mismatch", "The PIN confirmation does not match.")
    validate_pin(payload.new_pin, user.ic)
    user.pin_hash = hash_secret(payload.new_pin)
    return {"pin_status": PinStatus.ACCEPTED.value}
