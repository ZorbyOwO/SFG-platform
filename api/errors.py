from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, error: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.extra = extra


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error, "message": exc.message, **exc.extra},
    )
