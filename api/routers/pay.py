from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, File, Form, Header, Request, Response, UploadFile, status

from ..contracts import (
    AuthorizationStatus,
    CaptureStatus,
    LivenessStatus,
    MatchStatus,
    PayConfirmRequest,
    PayIdentityConfirmRequest,
    PaySessionRequest,
    IdentityConfirmationStatus,
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
from ..services.supabase_kiosk import WalletCharge


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
def identify(
    request: Request,
    session_id: str = Form(...),
    nonce: str = Form(...),
    frame: UploadFile = File(...),
    x_kiosk_key: str | None = Header(default=None),
    x_sfg_simulation: str | None = Header(default=None),
) -> dict[str, object]:
    store: MemoryStore = get_store(request)
    session = store.require_session(session_id, nonce=nonce, purpose="pay")
    store.verify_kiosk(session.kiosk_id or "", x_kiosk_key)
    session.identify_frames += 1
    if session.identify_frames > store.settings.max_identify_frames:
        session.status = "failed"
        raise ApiError(429, "identify_limit_reached", "Start a new payment session.")
    image = frame.file.read(store.settings.max_upload_bytes + 1)
    simulation = x_sfg_simulation is not None
    if simulation and store.settings.app_env != "test":
        del image
        frame.file.close()
        raise ApiError(400, "simulation_disabled", "Simulation controls are unavailable on this kiosk.")
    try:
        if simulation:
            engine: DevelopmentBiometricEngine = request.app.state.biometric_engine
            verdict = engine.analyse_identification(image, frame.content_type, x_sfg_simulation)
        else:
            identifier = getattr(request.app.state, "face_identification", None)
            if identifier is None or getattr(request.app.state, "supabase_kiosk", None) is None:
                raise ApiError(
                    503,
                    "real_kiosk_unavailable",
                    "Real face payment is temporarily unavailable. No wallet was charged.",
                )
            verdict = identifier.identify(image, frame.content_type)
    finally:
        del image
        frame.file.close()
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
        if verdict.match_status is MatchStatus.NO_MATCH:
            code = 404
        elif verdict.match_status is MatchStatus.ERROR:
            code = 503
        else:
            code = 409
        raise ApiError(
            code, "identity_not_confirmed", "No safe identity match was confirmed.",
            capture_status=CaptureStatus.READY.value,
            liveness_status=LivenessStatus.LIVE.value,
            match_status=(verdict.match_status or MatchStatus.ERROR).value,
        )
    if simulation:
        candidates = [
            user
            for user in store.users.values()
            if user.profile_state == "active" and user.consent_status.value == "CONSENT_GRANTED"
        ]
        if not candidates:
            session.status = "failed"
            session.match_status = MatchStatus.NO_MATCH
            raise ApiError(
                404,
                "identity_not_confirmed",
                "No safe identity match was confirmed.",
                match_status=MatchStatus.NO_MATCH.value,
            )
        user = candidates[0]
        citizen_id = user.citizen_id
        full_name = user.full_name
        ic_number = user.ic
    else:
        citizen_id = verdict.citizen_id
        if not citizen_id:
            session.status = "failed"
            raise ApiError(503, "real_kiosk_unavailable", "No safe identity match was confirmed.")
        identity = request.app.state.supabase_kiosk.profile_identity(citizen_id)
        full_name = identity.full_name
        ic_number = identity.ic_number
        session.identity_confirmation_status = IdentityConfirmationStatus.REQUIRED
    session.matched_user = citizen_id
    session.status = "matched"
    response = {
        "capture_status": CaptureStatus.READY.value,
        "liveness_status": LivenessStatus.LIVE.value,
        "match_status": MatchStatus.CONFIRMED.value,
        "citizen_display_name": display_mask_name(full_name),
        "subject_type": "main",
        "masked_ic": mask_ic(ic_number),
        "amount": money(session.amount or Decimal("0.00")),
    }
    if session.identity_confirmation_status is not None:
        response["identity_confirmation_status"] = session.identity_confirmation_status.value
    return response


@router.post("/identity/confirm")
def confirm_identity(
    payload: PayIdentityConfirmRequest,
    request: Request,
    x_kiosk_key: str | None = Header(default=None),
) -> dict[str, str]:
    store = get_store(request)
    session = store.require_session(
        payload.session_id,
        nonce=payload.nonce,
        purpose="pay",
        allowed_status=("matched",),
    )
    store.verify_kiosk(session.kiosk_id or "", x_kiosk_key)
    if session.identity_confirmation_status is not IdentityConfirmationStatus.REQUIRED:
        raise ApiError(409, "invalid_session_order", "Identity confirmation is not available.")
    if not payload.confirmed:
        session.identity_confirmation_status = IdentityConfirmationStatus.REJECTED
        session.authorization_status = AuthorizationStatus.DENIED
        session.status = "failed"
        return {
            "identity_confirmation_status": IdentityConfirmationStatus.REJECTED.value,
            "authorization_status": AuthorizationStatus.DENIED.value,
        }
    session.identity_confirmation_status = IdentityConfirmationStatus.CONFIRMED
    session.status = "identity_confirmed"
    return {"identity_confirmation_status": IdentityConfirmationStatus.CONFIRMED.value}


@router.post("/confirm")
async def confirm(
    payload: PayConfirmRequest,
    request: Request,
    x_kiosk_key: str | None = Header(default=None),
) -> dict[str, object]:
    store = get_store(request)
    session = store.require_session(
        payload.session_id,
        nonce=payload.nonce,
        purpose="pay",
        allowed_status=("matched", "identity_confirmed", "consumed"),
    )
    kiosk = store.verify_kiosk(session.kiosk_id or "", x_kiosk_key)
    real_payment = session.identity_confirmation_status is not None
    if session.status == "consumed":
        cache_key = (
            f"supabase-charge:{session.session_id}"
            if real_payment
            else f"charge:{session.session_id}"
        )
        cached = store.idempotency.get(cache_key)
        if cached is None or session.verification_completed_at is None:
            raise ApiError(409, "invalid_session_order", "The payment session is incomplete.")
        if real_payment:
            if not isinstance(cached, WalletCharge):
                raise ApiError(409, "invalid_session_order", "The payment session is incomplete.")
            transaction_id = cached.transaction_id
            reference = cached.reference
            amount = cached.amount
            merchant_name = cached.merchant_name
            balance_after = cached.balance_after
        else:
            transaction_id = cached.id
            reference = cached.reference
            amount = cached.amount
            merchant_name = kiosk.merchant_name
            balance_after = cached.balance_after
        return {
            "pin_status": PinStatus.ACCEPTED.value,
            "authorization_status": AuthorizationStatus.GRANTED.value,
            "verification_completed_at": iso(session.verification_completed_at),
            "transaction_id": transaction_id,
            "reference": reference,
            "amount": money(amount),
            "merchant_name": merchant_name,
            "balance_after": money(balance_after),
        }
    if real_payment and session.status != "identity_confirmed":
        raise ApiError(409, "identity_confirmation_required", "Confirm the proposed identity first.")
    if real_payment:
        matched_user = session.matched_user
        pin_accepted = bool(
            matched_user
            and request.app.state.supabase_kiosk.verify_pin(matched_user, payload.pin)
        )
    else:
        user = store.users.get(session.matched_user or "")
        pin_accepted = bool(user and verify_secret(payload.pin, user.pin_hash))
    if not pin_accepted:
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
        identity_confirmation_enabled=real_payment,
        pin_required=True if real_payment else not store.settings.face_only_mode,
    )
    if session.authorization_status is not AuthorizationStatus.GRANTED:
        session.status = "failed"
        raise ApiError(
            403, "authorization_denied", "The payment could not be authorized.",
            pin_status=session.pin_status.value,
            authorization_status=AuthorizationStatus.DENIED.value,
        )
    try:
        if real_payment:
            transaction = request.app.state.supabase_kiosk.charge_main_wallet(
                citizen_id=session.matched_user or "",
                kiosk_id=session.kiosk_id or "",
                amount=session.amount or Decimal("0.00"),
                idempotency_key=f"pay:{session.session_id}",
            )
            store.idempotency[f"supabase-charge:{session.session_id}"] = transaction
        else:
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
        "transaction_id": (
            transaction.transaction_id if real_payment else transaction.id
        ),
        "reference": transaction.reference,
        "amount": money(transaction.amount),
        "merchant_name": transaction.merchant_name if real_payment else kiosk.merchant_name,
        "balance_after": money(transaction.balance_after),
    }


@router.post("/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel(
    payload: SessionRequest,
    request: Request,
    x_kiosk_key: str | None = Header(default=None),
) -> Response:
    store = get_store(request)
    session = store.require_session(
        payload.session_id,
        purpose="pay",
        allowed_status=("open", "matched", "identity_confirmed"),
    )
    store.verify_kiosk(session.kiosk_id or "", x_kiosk_key)
    session.status = "failed"
    session.authorization_status = AuthorizationStatus.DENIED
    return Response(status_code=status.HTTP_204_NO_CONTENT)
