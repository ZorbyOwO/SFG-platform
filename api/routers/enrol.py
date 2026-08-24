from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile

from ..contracts import (
    ActivateRequest,
    AuthorizationStatus,
    CaptureStatus,
    ConsentStatus,
    EnrolmentStatus,
    LivenessStatus,
    PinSetupRequest,
    SessionRequest,
    TemplateStatus,
)
from ..dependencies import current_user, get_store
from ..errors import ApiError
from ..models import User
from ..repositories.memory import MemoryStore
from ..repositories.template_repository import TemplateRepository
from ..security import hash_secret, validate_pin
from ..serializers import session_dto
from ..services.biometric import DevelopmentBiometricEngine


router = APIRouter(prefix="/enrol", tags=["enrolment"])


@router.post("/session")
async def start_session(request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    if user.enrolment_status is EnrolmentStatus.COMPLETED:
        raise ApiError(409, "already_enrolled", "This account is already enrolled.")
    user.consent_status = ConsentStatus.GRANTED
    session = get_store(request).create_session("enrol", user_id=user.citizen_id)
    return {**session_dto(session), "enrolment_status": EnrolmentStatus.STARTED.value}


@router.post("/face")
async def capture_face(
    request: Request,
    session_id: str = Form(...),
    nonce: str = Form(...),
    pose: str = Form(...),
    frame: UploadFile = File(...),
    x_sfg_simulation: str = Header(default="pad_error"),
    user: User = Depends(current_user),
) -> dict[str, object]:
    store: MemoryStore = get_store(request)
    session = store.require_session(session_id, nonce=nonce, purpose="enrol")
    if session.user_id != user.citizen_id:
        raise ApiError(404, "session_not_found", "This session is no longer available.")
    if user.consent_status is not ConsentStatus.GRANTED:
        raise ApiError(403, "consent_required", "Biometric consent is required before capture.")
    normalized_pose = pose.lower()
    if normalized_pose not in store.settings.enrol_required_positions:
        raise ApiError(422, "invalid_capture", "Use one of the required capture positions.")
    image = await frame.read(store.settings.max_upload_bytes + 1)
    engine: DevelopmentBiometricEngine = request.app.state.biometric_engine
    verdict = engine.analyse_enrolment(image, frame.content_type, x_sfg_simulation)
    del image
    session.capture_status = verdict.capture_status
    session.liveness_status = verdict.liveness_status
    if verdict.capture_status is not CaptureStatus.READY or verdict.liveness_status is not LivenessStatus.LIVE:
        return {
            "capture_status": verdict.capture_status.value,
            **({"liveness_status": verdict.liveness_status.value} if verdict.liveness_status else {}),
            "templates_accepted": len(session.positions),
            "positions_complete": sorted(session.positions),
        }
    session.positions.add(normalized_pose)
    templates: TemplateRepository = request.app.state.template_repository
    count = await templates.record_development_acceptance(user.citizen_id, normalized_pose)
    return {
        "capture_status": CaptureStatus.READY.value,
        "liveness_status": LivenessStatus.LIVE.value,
        "frame_index": count,
        "templates_accepted": len(session.positions),
        "positions_complete": sorted(session.positions),
    }


@router.post("/complete")
async def complete_session(payload: SessionRequest, request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    session = get_store(request).require_session(payload.session_id, purpose="enrol")
    if session.user_id != user.citizen_id:
        raise ApiError(404, "session_not_found", "This session is no longer available.")
    required = set(get_store(request).settings.enrol_required_positions)
    if len(session.positions) < get_store(request).settings.enrol_frames_required or not required.issubset(session.positions):
        raise ApiError(422, "insufficient_templates", "Complete every required capture position.")
    session.status = "consumed"
    user.templates_stored = len(session.positions)
    # A re-enrolling citizen already has a valid PIN. Keep it and restore the
    # active account after the replacement face capture; first-time enrolment
    # still continues to PIN setup.
    is_reenrolment = user.pin_hash is not None
    user.profile_state = "active" if is_reenrolment else "pending_pin"
    user.enrolment_status = EnrolmentStatus.COMPLETED if is_reenrolment else EnrolmentStatus.STARTED
    return {
        "enrolment_status": user.enrolment_status.value,
        "template_status": TemplateStatus.ACTIVE.value,
        "templates_stored": user.templates_stored,
        "next_step": "dashboard" if is_reenrolment else "set_pin",
    }


@router.post("/pin")
async def set_pin(payload: PinSetupRequest, user: User = Depends(current_user)) -> dict[str, str]:
    if user.profile_state != "pending_pin":
        raise ApiError(409, "invalid_enrolment_order", "Complete face enrolment before setting a PIN.")
    if payload.pin != payload.pin_confirm:
        raise ApiError(422, "pin_mismatch", "The PIN confirmation does not match.")
    validate_pin(payload.pin, user.ic)
    user.pin_hash = hash_secret(payload.pin)
    user.profile_state = "pending_review"
    return {"enrolment_status": EnrolmentStatus.STARTED.value, "next_step": "review"}


@router.post("/activate")
async def activate(payload: ActivateRequest, user: User = Depends(current_user)) -> dict[str, str]:
    if user.profile_state != "pending_review" or not user.pin_hash or user.templates_stored < 3:
        raise ApiError(409, "enrolment_incomplete", "Complete face and PIN enrolment before activation.")
    user.profile_state = "active"
    user.enrolment_status = EnrolmentStatus.COMPLETED
    return {"enrolment_status": user.enrolment_status.value}
