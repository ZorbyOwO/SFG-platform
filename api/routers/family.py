from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile

from ..contracts import CaptureStatus, ConsentStatus, EnrolmentStatus, FamilyCreateRequest, LivenessStatus, SessionRequest
from ..dependencies import current_user, get_store
from ..errors import ApiError
from ..models import User
from ..repositories.template_repository import TemplateRepository
from ..security import normalize_ic
from ..serializers import family_dto, session_dto, transaction_dto
from ..services.biometric import DevelopmentBiometricEngine


router = APIRouter(prefix="/family-members", tags=["family members"])


@router.get("")
async def list_members(request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    store = get_store(request)
    return {
        "items": [family_dto(item, store.family_wallet(user.citizen_id, item.id)) for item in store.list_family(user.citizen_id)]
    }


@router.post("", status_code=201)
async def create_member(
    payload: FamilyCreateRequest, request: Request, user: User = Depends(current_user)
) -> dict[str, object]:
    member = await get_store(request).create_family_member(
        user.citizen_id,
        normalize_ic(payload.ic),
        payload.full_name,
        payload.relationship,
        payload.idempotency_key,
    )
    return family_dto(member, get_store(request).family_wallet(user.citizen_id, member.id))


@router.get("/{member_id}")
async def get_member(member_id: str, request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    store = get_store(request)
    member = store.get_family(user.citizen_id, member_id)
    return family_dto(member, store.family_wallet(user.citizen_id, member.id))


@router.post("/{member_id}/enrol/session")
async def start_member_enrolment(member_id: str, request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    store = get_store(request)
    member = store.get_family(user.citizen_id, member_id)
    member.consent_status = ConsentStatus.GRANTED
    session = store.create_session("family_enrol", user_id=user.citizen_id, family_member_id=member.id)
    return {**session_dto(session), "enrolment_status": member.enrolment_status.value}


@router.post("/{member_id}/enrol/face")
async def capture_member_face(
    member_id: str,
    request: Request,
    session_id: str = Form(...),
    nonce: str = Form(...),
    pose: str = Form(...),
    frame: UploadFile = File(...),
    x_sfg_simulation: str = Header(default="pad_error"),
    user: User = Depends(current_user),
) -> dict[str, object]:
    store = get_store(request)
    member = store.get_family(user.citizen_id, member_id)
    session = store.require_session(session_id, nonce=nonce, purpose="family_enrol")
    if session.user_id != user.citizen_id or session.family_member_id != member.id:
        raise ApiError(404, "session_not_found", "This session is no longer available.")
    normalized_pose = pose.lower()
    if normalized_pose not in store.settings.enrol_required_positions:
        raise ApiError(422, "invalid_capture", "Use one of the required capture positions.")
    image = await frame.read(store.settings.max_upload_bytes + 1)
    engine: DevelopmentBiometricEngine = request.app.state.biometric_engine
    verdict = engine.analyse_enrolment(image, frame.content_type, x_sfg_simulation)
    del image
    session.capture_status = verdict.capture_status
    session.liveness_status = verdict.liveness_status
    if verdict.capture_status is CaptureStatus.READY and verdict.liveness_status is LivenessStatus.LIVE:
        session.positions.add(normalized_pose)
        templates: TemplateRepository = request.app.state.template_repository
        await templates.record_development_acceptance(member.id, normalized_pose)
    return {
        "capture_status": verdict.capture_status.value,
        **({"liveness_status": verdict.liveness_status.value} if verdict.liveness_status else {}),
        "templates_accepted": len(session.positions),
        "positions_complete": sorted(session.positions),
    }


@router.post("/{member_id}/enrol/complete")
async def complete_member_enrolment(
    member_id: str, payload: SessionRequest, request: Request, user: User = Depends(current_user)
) -> dict[str, str | int]:
    store = get_store(request)
    member = store.get_family(user.citizen_id, member_id)
    session = store.require_session(payload.session_id, purpose="family_enrol")
    required = set(store.settings.enrol_required_positions)
    if session.family_member_id != member.id or session.user_id != user.citizen_id:
        raise ApiError(404, "session_not_found", "This session is no longer available.")
    if len(session.positions) < store.settings.enrol_frames_required or not required.issubset(session.positions):
        raise ApiError(422, "insufficient_templates", "Complete every required capture position.")
    session.status = "consumed"
    member.templates_stored = len(session.positions)
    member.profile_state = "active"
    member.enrolment_status = EnrolmentStatus.COMPLETED
    return {"enrolment_status": member.enrolment_status.value, "templates_stored": member.templates_stored}


@router.get("/{member_id}/transactions")
async def member_transactions(member_id: str, request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    store = get_store(request)
    store.get_family(user.citizen_id, member_id)
    return {"items": [transaction_dto(item) for item in store.list_transactions(user.citizen_id, member_id)]}


@router.post("/{member_id}/deactivate")
async def deactivate(member_id: str, request: Request, user: User = Depends(current_user)) -> dict[str, str]:
    member = get_store(request).get_family(user.citizen_id, member_id)
    member.profile_state = "deactivated"
    member.enrolment_status = EnrolmentStatus.CANCELLED
    templates: TemplateRepository = request.app.state.template_repository
    await templates.revoke_subject(member.id)
    return {"enrolment_status": member.enrolment_status.value, "profile_state": member.profile_state}


@router.post("/{member_id}/reactivate")
async def reactivate(member_id: str, request: Request, user: User = Depends(current_user)) -> dict[str, str]:
    member = get_store(request).get_family(user.citizen_id, member_id)
    member.profile_state = "pending_face"
    member.enrolment_status = EnrolmentStatus.STARTED
    member.templates_stored = 0
    return {"enrolment_status": member.enrolment_status.value, "next_step": "face_enrolment"}
