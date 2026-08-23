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
from .routers import auth, enrol, family, ocr, pay, profile, wallet
from .services.biometric import DevelopmentBiometricEngine
from .services.rate_limit import SlidingWindowLimiter


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


def create_app(settings: Settings | None = None, *, kiosk_key: str | None = None) -> FastAPI:
    resolved = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = resolved
        app.state.store = MemoryStore(resolved, kiosk_key=kiosk_key)
        app.state.template_repository = CountingTemplateRepository()
        app.state.biometric_engine = DevelopmentBiometricEngine(resolved)
        app.state.rate_limiter = SlidingWindowLimiter()
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
            if error.get("ctx", {}).get("error") == "invalid_denomination":
                code = "invalid_denomination"
        return JSONResponse(
            status_code=422,
            content={"error": code, "message": "Check the submitted fields and try again."},
        )

    @app.get("/health", tags=["operational"])
    async def health(request: Request) -> dict[str, object]:
        models = request.app.state.biometric_engine.health()
        return {
            "status": "ok",
            "mode": "development_in_memory" if resolved.app_env in {"development", "test"} else "configured",
            "models": models,
            "database": "configured" if resolved.database_url else "development_in_memory",
            "limitations": [
                "No real biometric decision is performed by the development adapter.",
                "Template encryption and pgvector search remain an unresolved architecture decision.",
            ],
        }

    for router in (auth.router, enrol.router, pay.router, wallet.router, family.router, profile.router, ocr.router):
        app.include_router(router)
    return app


logging.basicConfig(level=logging.INFO)
for handler in logging.getLogger().handlers:
    handler.addFilter(SensitiveDataFilter())

app = create_app()
