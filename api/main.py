from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .errors import ApiError, api_error_handler
from .repositories.memory import MemoryStore
from .repositories.template_repository import CountingTemplateRepository
from .routers import auth, biometric, enrol, family, ocr, pay, profile, wallet
from .services.biometric import DevelopmentBiometricEngine
from .services.biometric_core import CoreCVBiometricEngine, CoreCVUnavailable
from .services.biometric_sessions import BiometricSessionRegistry
from .services.face_identification import FaceIdentificationService
from .services.identity import SupabaseTokenVerifier, supabase_user_endpoint
from .services.rate_limit import SlidingWindowLimiter
from .services.supabase_kiosk import SupabaseKioskClient
from .services.template_persister import SupabaseTemplatePersister
from .services.template_store import EncryptedTemplateStore, load_or_create_key


class SensitiveDataFilter(logging.Filter):
    """Remove accidental structured values with prohibited field names."""

    BLOCKED = {
        "password", "password_confirm", "pin", "pin_confirm", "current_pin", "new_pin",
        "authorization", "access_token", "refresh_token", "facial_template", "frame",
        "database_url", "biometric_template_encryption_key",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, dict):
            record.args = {
                key: "[REDACTED]" if str(key).lower() in self.BLOCKED else value
                for key, value in record.args.items()
            }
        return True


def _load_core_engine(settings: Settings) -> tuple[object | None, bool]:
    """Load the real pinned core for registration and re-enrolment.

    A failure is reported honestly through /health and turns the /biometric
    routes into an explicit 503. It never silently becomes a fake match, and it
    never degrades into the kiosk simulator.
    """

    try:
        engine = CoreCVBiometricEngine.from_package(
            settings.corecv_root, max_upload_bytes=settings.max_upload_bytes
        )
    except CoreCVUnavailable as exc:
        logging.getLogger(__name__).warning("biometric_core code=%s", exc.code)
        return None, False
    return engine, True


def create_app(
    settings: Settings | None = None,
    *,
    kiosk_key: str | None = None,
    corecv_engine: object | None = None,
    token_verifier: object | None = None,
    template_store: object | None = None,
    template_persister: object | None = None,
    face_identification: object | None = None,
    supabase_kiosk: object | None = None,
) -> FastAPI:
    resolved = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved
        app.state.store = MemoryStore(resolved, kiosk_key=kiosk_key)
        app.state.template_repository = CountingTemplateRepository()
        app.state.rate_limiter = SlidingWindowLimiter()
        app.state.biometric_sessions = BiometricSessionRegistry(
            timeout_seconds=resolved.enrol_session_timeout_seconds
        )

        # The kiosk payment scaffold and the legacy /enrol demo routes keep the
        # explicitly labelled simulator. Registration and re-enrolment run on the
        # real pinned core through /biometric. The two never substitute for each other.
        app.state.biometric_engine = DevelopmentBiometricEngine(resolved)
        if corecv_engine is not None:
            app.state.corecv_engine = corecv_engine
            app.state.corecv_available = True
        else:
            engine, available = _load_core_engine(resolved)
            app.state.corecv_engine = engine
            app.state.corecv_available = available

        if template_store is not None:
            app.state.template_store = template_store
        else:
            app.state.template_store = EncryptedTemplateStore(
                resolved.biometric_template_db, load_or_create_key(resolved.biometric_key_file)
            )

        if token_verifier is not None:
            app.state.token_verifier = token_verifier
        elif resolved.supabase_url and resolved.supabase_publishable_key:
            app.state.token_verifier = SupabaseTokenVerifier(
                resolve_subject=supabase_user_endpoint(
                    resolved.supabase_url, resolved.supabase_publishable_key
                )
            )
        else:
            app.state.token_verifier = None

        # Trusted-tier upload path for completed enrolments. Built only when the
        # approved server-side secret exists; without it, /biometric/complete
        # reports template_persistence_unavailable instead of pretending.
        if template_persister is not None:
            app.state.template_persister = template_persister
        elif resolved.supabase_url and resolved.supabase_backend_secret:
            try:
                app.state.template_persister = SupabaseTemplatePersister(
                    supabase_url=resolved.supabase_url,
                    backend_secret=resolved.supabase_backend_secret,
                )
            except Exception:
                logging.getLogger(__name__).warning("biometric persist=not_built")
                app.state.template_persister = None
        else:
            app.state.template_persister = None

        # Real kiosk path: the trusted tier alone may load/decrypt the hosted
        # gallery, resolve a matched profile, verify its PIN, and charge its
        # wallet. Missing configuration fails closed and never selects the
        # development simulator.
        if supabase_kiosk is not None:
            app.state.supabase_kiosk = supabase_kiosk
        elif resolved.supabase_url and resolved.supabase_backend_secret:
            try:
                fingerprint = getattr(app.state.corecv_engine, "fingerprint_id", None)
                app.state.supabase_kiosk = SupabaseKioskClient(
                    supabase_url=resolved.supabase_url,
                    backend_secret=resolved.supabase_backend_secret,
                    compatibility_fingerprint=fingerprint or "",
                )
            except Exception:
                logging.getLogger(__name__).warning("real_kiosk backend=not_built")
                app.state.supabase_kiosk = None
        else:
            app.state.supabase_kiosk = None

        if face_identification is not None:
            app.state.face_identification = face_identification
        elif (
            app.state.corecv_available
            and app.state.corecv_engine is not None
            and app.state.supabase_kiosk is not None
        ):
            try:
                app.state.face_identification = FaceIdentificationService(
                    engine=app.state.corecv_engine,
                    trusted_client=app.state.supabase_kiosk,
                    template_key=load_or_create_key(resolved.biometric_key_file),
                    threshold=float(resolved.sface_match_threshold),
                )
            except Exception:
                logging.getLogger(__name__).warning("real_kiosk matcher=not_built")
                app.state.face_identification = None
        else:
            app.state.face_identification = None
        yield

    app = FastAPI(
        title="Sarawak Facial Gateway API",
        version="0.3.0",
        docs_url="/docs" if resolved.app_env in {"development", "test"} else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Kiosk-Key", "X-SFG-Simulation"],
    )
    app.add_exception_handler(ApiError, api_error_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        code = "invalid_request"
        for error in exc.errors():
            if str(error.get("ctx", {}).get("error", "")) == "invalid_amount":
                code = "invalid_amount"
        return JSONResponse(
            status_code=422,
            content={"error": code, "message": "Check the submitted fields and try again."},
        )

    @app.get("/health", tags=["operational"])
    async def health(request: Request) -> dict[str, object]:
        state = request.app.state
        corecv_available = bool(getattr(state, "corecv_available", False))
        core = getattr(state, "corecv_engine", None)
        biometric_core = (
            {"state": "loaded", **core.health()}
            if corecv_available and core is not None
            else {"state": "unavailable", "adapter": "none"}
        )
        return {
            "status": "ok",
            "mode": "development_in_memory" if resolved.app_env in {"development", "test"} else "configured",
            # Kiosk payment identification remains an explicit simulation.
            "models": state.biometric_engine.health(),
            # Registration and re-enrolment run on the pinned frozen core.
            "biometric_core": biometric_core,
            "identity_verification": "configured" if getattr(state, "token_verifier", None) else "unconfigured",
            # Hosted sealed-template upload path for completed enrolments.
            "template_persistence": (
                "configured" if getattr(state, "template_persister", None) else "unconfigured"
            ),
            "real_kiosk_payment": (
                "configured"
                if getattr(state, "face_identification", None)
                and getattr(state, "supabase_kiosk", None)
                else "unconfigured"
            ),
            "database": "configured" if resolved.database_url else "development_in_memory",
            "limitations": [
                "Kiosk main-citizen 1:N identification and Supabase wallet payment require the trusted backend configuration.",
                "Registration and re-enrolment use the pinned core; reusable templates are encrypted"
                " at rest in the trusted tier and are never returned to a client.",
                "The 0.40 SFace threshold and PAD are POC policies; no FAR, FRR, or PAD guarantee is claimed.",
                "Family Member kiosk identification and external bank settlement are not implemented.",
            ],
        }

    for router in (
        auth.router,
        enrol.router,
        biometric.router,
        pay.router,
        wallet.router,
        family.router,
        profile.router,
        ocr.router,
    ):
        app.include_router(router)
    return app


logging.basicConfig(level=logging.INFO)
for handler in logging.getLogger().handlers:
    handler.addFilter(SensitiveDataFilter())

app = create_app()
