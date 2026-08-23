from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, File, Form, Header, Request, Response, UploadFile, status

from ..contracts import (
    AuthorizationStatus,
    CaptureStatus,
    LivenessStatus,
    MatchStatus,
    PayConfirmRequest,
    PaySessionRequest,
    PinStatus,
    SessionRequest,
    iso,
    money,
)
from ..dependencies import get_store
from ..errors import ApiError
from ..repositories.memory import MemoryStore, now_utc
from ..security import display_mask_name, mask_ic, verify_secret
from ..serializers import session_dto
from ..services.biometric import DevelopmentBiometricEngine
from ..services.authorization import authorization_decision


router = APIRouter(prefix="/pay", tags=["payment"])


@router.post("/session")
async def create_payment_session(
    payload: PaySessionRequest,
    request: Request,
    x_kiosk_key: str | None = Header(default=None),
) -> dict[str, object]:
    store = get_store(request)
    kiosk = store.verify_kiosk(payload.kiosk_id, x_kiosk_key)
    session = store.create_session("pay", kiosk_id=kiosk.id, amount=payload.amount)
    return {**session_dto(session), "kiosk_id": kiosk.id, "kiosk_name": kiosk.kiosk_name}


@router.post("/identify")
async def identify(
    request: Request,
    session_id: str = Form(...),
    nonce: str = Form(...),
    frame: UploadFile = File(...),
    x_kiosk_key: str | None = Header(default=None),
    x_sfg_simulation: str = Header(default="pad_error"),
) -> dict[str, object]:
    store: MemoryStore = get_store(request)
    session = store.require_session(session_id, nonce=nonce, purpose="pay")
    store.verify_kiosk(session.kiosk_id or "", x_kiosk_key)
    session.identify_frames += 1
    if session.identify_frames > store.settings.max_identify_frames:
        session.status = "failed"
        raise ApiError(429, "identify_limit_reached", "Start a new payment session.")
    image = await frame.read(store.settings.max_upload_bytes + 1)
    engine: DevelopmentBiometricEngine = request.app.state.biometric_engine
    verdict = engine.analyse_identification(image, frame.content_type, x_sfg_simulation)
    del image
    session.capture_status = verdict.capture_status
    session.liveness_status = verdict.liveness_status
    session.match_status = verdict.match_status

    if verdict.capture_status is not CaptureStatus.READY:
        return {"capture_status": verdict.capture_status.value}
    if verdict.liveness_status is not LivenessStatus.LIVE:
        session.status = "failed"
        raise ApiError(
            403, "liveness_rejected", "The liveness check did not pass.",
            capture_status=verdict.capture_status.value,
            liveness_status=(verdict.liveness_status or LivenessStatus.ERROR).value,
        )
    if verdict.match_status is not MatchStatus.CONFIRMED:
        session.status = "failed"
        code = 404 if verdict.match_status is MatchStatus.NO_MATCH else 409
        raise ApiError(
            code, "identity_not_confirmed", "No safe identity match was confirmed.",
            capture_status=CaptureStatus.READY.value,
            liveness_status=LivenessStatus.LIVE.value,
            match_status=(verdict.match_status or MatchStatus.ERROR).value,
        )
    candidates = [user for user in store.users.values() if user.profile_state == "active" and user.consent_status.value == "CONSENT_GRANTED"]
    if not candidates:
        session.status = "failed"
        session.match_status = MatchStatus.NO_MATCH
        raise ApiError(404, "identity_not_confirmed", "No safe identity match was confirmed.", match_status=MatchStatus.NO_MATCH.value)
    user = candidates[0]
    session.matched_user = user.citizen_id
    session.status = "matched"
    return {
        "capture_status": CaptureStatus.READY.value,
        "liveness_status": LivenessStatus.LIVE.value,
        "match_status": MatchStatus.CONFIRMED.value,
        "citizen_display_name": display_mask_name(user.full_name),
        "subject_type": "main",
        "masked_ic": mask_ic(user.ic),
        "amount": money(session.amount or Decimal("0.00")),
    }


@router.post("/confirm")
async def confirm(
    payload: PayConfirmRequest,
    request: Request,
    x_kiosk_key: str | None = Header(default=None),
) -> dict[str, object]:
    store = get_store(request)
    session = store.require_session(
        payload.session_id, nonce=payload.nonce, purpose="pay", allowed_status=("matched", "consumed")
    )
    kiosk = store.verify_kiosk(session.kiosk_id or "", x_kiosk_key)
    if session.status == "consumed":
        cached = store.idempotency.get(f"charge:{session.session_id}")
        if cached is None or session.verification_completed_at is None:
            raise ApiError(409, "invalid_session_order", "The payment session is incomplete.")
        return {
            "pin_status": PinStatus.ACCEPTED.value,
            "authorization_status": AuthorizationStatus.GRANTED.value,
            "verification_completed_at": iso(session.verification_completed_at),
            "transaction_id": cached.id,
            "reference": cached.reference,
            "amount": money(cached.amount),
            "merchant_name": kiosk.merchant_name,
            "balance_after": money(cached.balance_after),
        }
    user = store.users.get(session.matched_user or "")
    if not user or not verify_secret(payload.pin, user.pin_hash):
        session.pin_attempts += 1
        session.authorization_status = AuthorizationStatus.DENIED
        if session.pin_attempts >= store.settings.pin_max_attempts:
            session.pin_status = PinStatus.LOCKED
            session.status = "failed"
            raise ApiError(
                423, "pin_locked", "The PIN attempt limit was reached.",
                pin_status=PinStatus.LOCKED.value,
                authorization_status=AuthorizationStatus.DENIED.value,
            )
        session.pin_status = PinStatus.REJECTED
        raise ApiError(
            401, "wrong_pin", "The PIN was not accepted.",
            pin_status=PinStatus.REJECTED.value,
            authorization_status=AuthorizationStatus.DENIED.value,
            attempts_left=store.settings.pin_max_attempts - session.pin_attempts,
        )
    session.pin_status = PinStatus.ACCEPTED
    session.authorization_status = authorization_decision(
        liveness_status=session.liveness_status,
        match_status=session.match_status,
        identity_confirmation_status=session.identity_confirmation_status,
        pin_status=session.pin_status,
        identity_confirmation_enabled=session.identity_confirmation_status is not None,
        pin_required=not store.settings.face_only_mode,
    )
    if session.authorization_status is not AuthorizationStatus.GRANTED:
        session.status = "failed"
        raise ApiError(
            403, "authorization_denied", "The payment could not be authorized.",
            pin_status=session.pin_status.value,
            authorization_status=AuthorizationStatus.DENIED.value,
        )
    try:
        transaction = await store.charge(session, session.session_id)
    except ApiError:
        session.status = "failed"
        raise
    session.status = "consumed"
    session.verification_completed_at = now_utc()
    return {
        "pin_status": PinStatus.ACCEPTED.value,
        "authorization_status": AuthorizationStatus.GRANTED.value,
        "verification_completed_at": iso(session.verification_completed_at),
        "transaction_id": transaction.id,
        "reference": transaction.reference,
        "amount": money(transaction.amount),
        "merchant_name": kiosk.merchant_name,
        "balance_after": money(transaction.balance_after),
    }


@router.post("/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel(
    payload: SessionRequest,
    request: Request,
    x_kiosk_key: str | None = Header(default=None),
) -> Response:
    store = get_store(request)
    session = store.require_session(payload.session_id, purpose="pay", allowed_status=("open", "matched"))
    store.verify_kiosk(session.kiosk_id or "", x_kiosk_key)
    session.status = "failed"
    session.authorization_status = AuthorizationStatus.DENIED
    return Response(status_code=status.HTTP_204_NO_CONTENT)
