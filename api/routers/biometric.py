"""Real CoreCV enrolment and re-enrolment endpoints for the citizen browser.

Contract boundaries enforced here:

* The caller proves identity before a frame is read.
* A frame is decoded, processed, and released inside one request. Nothing writes
  an image anywhere.
* Only canonical statuses and progress counters leave this tier. A template, an
  embedding, a score, or a candidate identity never appears in a response.
* Face capture completes enrolment. It never authorizes anything; the PIN gate
  stays where it already is.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, Header, Request, Response, UploadFile, status
from pydantic import Field

from ..contracts import (
    CaptureStatus,
    EnrolmentStatus,
    LivenessStatus,
    SessionRequest,
    StrictDto,
    TemplateStatus,
)
from ..errors import ApiError
from ..services.biometric_core import CoreCaptureVerdict, CoreCVUnavailable, seal_template
from ..services.biometric_sessions import BiometricSession, BiometricSessionRegistry, ENROL, REENROL
from ..services.template_persister import TemplatePersistError
from ..services.template_sealer import TemplateSealError, seal_template_bundle


LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/biometric", tags=["biometric"])


class BiometricSessionRequest(StrictDto):
    purpose: str = Field(default=ENROL, pattern=f"^({ENROL}|{REENROL})$")


def _subject(request: Request, authorization: str | None) -> str:
    """Resolve the authenticated citizen before any frame is read.

    Two identity sources are accepted, in order: this tier's own session store
    (`api` data mode) and a Supabase access token re-verified upstream
    (`supabase` data mode). An unrecognised token never reaches a frame.
    """

    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError(401, "authentication_required", "Sign in to continue.")
    token = authorization[7:].strip()
    if not token:
        raise ApiError(401, "authentication_required", "Sign in to continue.")

    store = getattr(request.app.state, "store", None)
    if store is not None:
        native = store.user_for_access_token(token)
        if native is not None:
            return native.citizen_id

    verifier = getattr(request.app.state, "token_verifier", None)
    if verifier is None:
        raise ApiError(
            503,
            "identity_verification_unavailable",
            "Identity verification is not configured for this deployment.",
        )
    return verifier.subject_for(token)


def current_subject(request: Request, authorization: str | None = Header(default=None)) -> str:
    return _subject(request, authorization)


def _engine(request: Request):
    """Return the real pinned core, or fail closed. Never the kiosk simulator."""

    engine = getattr(request.app.state, "corecv_engine", None)
    if engine is None or not getattr(request.app.state, "corecv_available", False):
        raise ApiError(
            503,
            "models_unavailable",
            "The face recognition models are not installed on this server.",
        )
    return engine


def _registry(request: Request) -> BiometricSessionRegistry:
    return request.app.state.biometric_sessions


def _templates(request: Request):
    store = getattr(request.app.state, "template_store", None)
    if store is None:
        raise ApiError(503, "models_unavailable", "Template storage is unavailable on this server.")
    return store


def _persister(request: Request):
    persister = getattr(request.app.state, "template_persister", None)
    if persister is None:
        raise ApiError(
            503,
            "template_persistence_unavailable",
            "Secure template upload is not configured on this server. Try again later.",
        )
    return persister


def _seal_key(settings) -> bytes:
    from ..services.template_store import load_or_create_key

    return load_or_create_key(settings.biometric_key_file)


def _persist_hosted_bundles(
    request: Request,
    session: BiometricSession,
    subject: str,
) -> list[str]:
    """Seal every staged bundle for this session and upload it to the hosted store.

    Upload happens before any local commit: if the hosted store refuses the
    bundles the enrolment stays incomplete and the citizen's existing active
    generation is untouched. The subject bound into each bundle's additional
    authenticated data is the verified caller identity, so a staged record can
    never be uploaded under a different citizen.
    """

    templates = _templates(request)
    settings = request.app.state.settings
    key = _seal_key(settings)

    # The local store stages one row per pose. Re-seal from its decrypted
    # payloads so the hosted envelope carries exactly what was accepted.
    records = templates.read_session_staged_templates(session.session_id, subject)
    if not records:
        raise ApiError(422, "insufficient_templates", "Complete every required capture position.")
    persister = _persister(request)
    try:
        bundles = {}
        for record in records:
            bundles[record.pose] = seal_template_bundle(
                citizen_id=subject,
                pose=record.pose,
                payload_base64=record.payload_base64,
                fingerprint_id=record.fingerprint_id,
                key=key,
            )
        generation_id = str(uuid.uuid4())
        hosted_ids = persister.persist_generation(
            citizen_id=subject,
            generation_id=generation_id,
            bundles=bundles,
        )
    except TemplatePersistError as exc:
        LOGGER.warning("biometric persist=failed code=%s", exc.code)
        raise ApiError(
            503,
            "template_upload_failed",
            "The secure template store could not accept this enrolment. No changes were made; try again.",
        ) from None
    except TemplateSealError as exc:
        LOGGER.warning("biometric persist=seal_failed code=%s", exc.code)
        raise ApiError(
            500, "capture_not_secured", "The capture could not be secured. Try again."
        ) from None
    return list(hosted_ids)


def _progress(request: Request, session: BiometricSession) -> dict[str, object]:
    required = list(request.app.state.settings.enrol_required_positions)
    staged = _templates(request).staged_positions(session.session_id)
    session.positions = set(staged)
    return {
        "positions_complete": [pose for pose in required if pose in staged],
        "templates_accepted": len(staged),
        "required_positions": required,
    }


@router.post("/session")
def start_session(
    payload: BiometricSessionRequest,
    request: Request,
    subject: str = Depends(current_subject),
) -> dict[str, object]:
    _engine(request)
    session = _registry(request).create(subject, payload.purpose)
    LOGGER.info("biometric session=start purpose=%s", session.purpose)
    return {
        "session_id": session.session_id,
        "correlation_id": session.correlation_id,
        "nonce": session.nonce,
        "expires_at": session.expires_at.isoformat(),
        "purpose": session.purpose,
        "enrolment_status": EnrolmentStatus.STARTED.value,
        "required_positions": list(request.app.state.settings.enrol_required_positions),
        "positions_complete": [],
        "templates_accepted": 0,
    }


@router.post("/capture")
def capture_face(
    request: Request,
    session_id: str = Form(...),
    nonce: str = Form(...),
    pose: str = Form(...),
    frame: UploadFile = File(...),
    subject: str = Depends(current_subject),
) -> dict[str, object]:
    """Process one live frame through the frozen core and stage the result.

    Defined with `def` on purpose: FastAPI runs it in the threadpool, so the
    blocking CPU inference never stalls the event loop.
    """

    settings = request.app.state.settings
    engine = _engine(request)
    registry = _registry(request)
    templates = _templates(request)

    session = registry.require(session_id, subject, nonce=nonce)
    normalized_pose = pose.strip().lower()
    if normalized_pose not in settings.enrol_required_positions:
        raise ApiError(422, "invalid_capture", "Use one of the required capture positions.")

    image = frame.file.read(settings.max_upload_bytes + 1)
    try:
        verdict: CoreCaptureVerdict = engine.analyse_enrolment(image, frame.content_type)
    finally:
        del image
        frame.file.close()

    if not verdict.accepted:
        LOGGER.info(
            "biometric capture=rejected capture_status=%s liveness_status=%s",
            verdict.capture_status.value,
            verdict.liveness_status.value if verdict.liveness_status else None,
        )
        return {**verdict.safe_payload(), **_progress(request, session)}

    template = verdict.protected_template_for_trusted_backend()
    try:
        payload_base64, fingerprint_id = seal_template(template, corecv_root=settings.corecv_root)
        templates.stage_template(session.session_id, subject, normalized_pose, payload_base64, fingerprint_id)
    except CoreCVUnavailable:
        raise ApiError(503, "models_unavailable", "Face processing is unavailable on this server.") from None
    except Exception:
        LOGGER.warning("biometric capture=stage_failed code=TEMPLATE_STAGE_FAILED")
        raise ApiError(500, "capture_not_stored", "The capture could not be secured. Try again.") from None
    finally:
        del template

    LOGGER.info("biometric capture=accepted pose=%s", normalized_pose)
    return {
        "capture_status": CaptureStatus.READY.value,
        "liveness_status": LivenessStatus.LIVE.value,
        **_progress(request, session),
    }


@router.post("/complete")
def complete_session(
    payload: SessionRequest,
    request: Request,
    subject: str = Depends(current_subject),
) -> dict[str, object]:
    settings = request.app.state.settings
    registry = _registry(request)
    templates = _templates(request)

    session = registry.require(payload.session_id, subject)
    required = set(settings.enrol_required_positions)
    staged = templates.staged_positions(session.session_id)
    if not required.issubset(staged):
        raise ApiError(422, "insufficient_templates", "Complete every required capture position.")

    # Hosted persistence first: seal every staged bundle with the verified
    # subject bound as AAD and upload. Any failure aborts before the local
    # commit, leaving the citizen's previous active generation intact.
    _persist_hosted_bundles(request, session, subject)

    active = templates.commit_session(session.session_id, subject)
    registry.consume(session)
    LOGGER.info("biometric session=complete purpose=%s active_templates=%s", session.purpose, active)
    return {
        "enrolment_status": EnrolmentStatus.COMPLETED.value,
        "template_status": TemplateStatus.ACTIVE.value,
        "templates_stored": active,
        "purpose": session.purpose,
        "next_step": "dashboard" if session.purpose == REENROL else "set_pin",
    }


@router.post("/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_session(
    payload: SessionRequest,
    request: Request,
    subject: str = Depends(current_subject),
) -> Response:
    """Discard staged captures so an abandoned run changes nothing."""

    registry = _registry(request)
    session = registry.require(payload.session_id, subject)
    _templates(request).discard_session(session.session_id)
    registry.cancel(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/status")
def enrolment_status(request: Request, subject: str = Depends(current_subject)) -> dict[str, object]:
    """Report enrolment progress without revealing any biometric material."""

    active = _templates(request).active_positions(subject)
    required = list(request.app.state.settings.enrol_required_positions)
    return {
        "templates_stored": len(active),
        "template_status": TemplateStatus.ACTIVE.value if active else None,
        "enrolment_status": (
            EnrolmentStatus.COMPLETED.value if set(required).issubset(active) else EnrolmentStatus.STARTED.value
        ),
        "positions_complete": [pose for pose in required if pose in active],
        "required_positions": required,
    }
