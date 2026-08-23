from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile

from ..dependencies import current_user
from ..errors import ApiError
from ..models import User


router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/ic")
async def scan_ic(
    request: Request, image: UploadFile = File(...), _: User = Depends(current_user)
) -> dict[str, object]:
    # Import-guarded by design. No document image is written to disk or storage.
    await image.close()
    if not request.app.state.settings.paddleocr_model_dir:
        raise ApiError(503, "ocr_unavailable", "Document scanning is unavailable. Enter the details manually.")
    raise ApiError(503, "ocr_unavailable", "The optional OCR runtime has not been installed.")
