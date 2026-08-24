from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from ..contracts import ConsentStatus, DeleteProfileRequest, EnrolmentStatus, ProfilePatchRequest
from ..dependencies import current_user, get_store
from ..errors import ApiError
from ..models import User
from ..repositories.template_repository import TemplateRepository
from ..security import verify_secret
from ..serializers import profile_dto, session_dto


router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def get_profile(user: User = Depends(current_user)) -> dict[str, object]:
    return profile_dto(user)


@router.patch("")
async def update_profile(payload: ProfilePatchRequest, user: User = Depends(current_user)) -> dict[str, object]:
    user.full_name = payload.full_name
    return profile_dto(user)


@router.post("/face-reenrol/session")
async def start_reenrol(request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    if user.profile_state != "active" or not user.pin_hash:
        raise ApiError(409, "profile_not_ready_for_reenrolment", "Finish account activation before re-enrolling your face.")
    templates: TemplateRepository = request.app.state.template_repository
    await templates.revoke_subject(user.citizen_id)
    user.templates_stored = 0
    user.profile_state = "pending_face"
    user.enrolment_status = EnrolmentStatus.STARTED
    # The client presents and records renewed consent immediately before this call.
    user.consent_status = ConsentStatus.GRANTED
    session = get_store(request).create_session("enrol", user_id=user.citizen_id)
    return {**session_dto(session), "enrolment_status": user.enrolment_status.value}


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    payload: DeleteProfileRequest, request: Request, user: User = Depends(current_user)
) -> Response:
    if not verify_secret(payload.password, user.password_hash):
        raise ApiError(401, "invalid_credentials", "The password was not accepted.")
    templates: TemplateRepository = request.app.state.template_repository
    await templates.revoke_subject(user.citizen_id)
    for member in get_store(request).list_family(user.citizen_id):
        await templates.revoke_subject(member.id)
    await get_store(request).delete_user(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
