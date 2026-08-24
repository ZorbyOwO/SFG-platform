from __future__ import annotations

import logging

import cv2
import numpy as np
import pytest

from sfg_registration_core.ocr import (
    ImageValidationError,
    OCRService,
    validate_image_bytes,
)


def _encoded(extension: str = ".png") -> bytes:
    image = np.full((180, 640, 3), 255, dtype=np.uint8)
    ok, payload = cv2.imencode(extension, image)
    assert ok
    return payload.tobytes()


@pytest.mark.parametrize(
    ("media_type", "extension"),
    [("image/png", ".png"), ("image/jpeg", ".jpg")],
)
def test_valid_in_memory_png_and_jpeg(media_type: str, extension: str) -> None:
    decoded = validate_image_bytes(_encoded(extension), media_type=media_type)

    assert decoded.ndim == 3
    assert decoded.shape[2] == 3


@pytest.mark.parametrize(
    ("payload", "media_type", "code"),
    [
        (b"", "image/png", "IMAGE_EMPTY"),
        (b"not-an-image", "image/png", "IMAGE_MALFORMED"),
        (b"GIF89a", "image/gif", "MEDIA_TYPE_UNSUPPORTED"),
    ],
)
def test_invalid_image_inputs_fail_safely(payload: bytes, media_type: str, code: str) -> None:
    with pytest.raises(ImageValidationError) as caught:
        validate_image_bytes(payload, media_type=media_type)

    assert caught.value.code == code
    if payload:
        assert payload.decode("latin1", errors="ignore") not in repr(caught.value)


def test_oversized_input_is_rejected_before_decode() -> None:
    with pytest.raises(ImageValidationError) as caught:
        validate_image_bytes(b"x" * (5 * 1024 * 1024 + 1), media_type="image/jpeg")

    assert caught.value.code == "IMAGE_TOO_LARGE"


def test_declared_media_must_match_bytes() -> None:
    with pytest.raises(ImageValidationError) as caught:
        validate_image_bytes(_encoded(".png"), media_type="image/jpeg")

    assert caught.value.code == "MEDIA_TYPE_MISMATCH"


class CandidateBackend:
    def scan(self, image_bytes: bytes, *, media_type: str) -> dict[str, object]:
        return {"full_name": "ALICE TAN", "ic": "900101-01-1234", "requires_confirmation": True}


def test_ordinary_logs_do_not_expose_candidate_or_image(caplog: pytest.LogCaptureFixture) -> None:
    payload = _encoded()
    caplog.set_level(logging.INFO)

    result = OCRService(backend=CandidateBackend()).scan(payload, media_type="image/png")

    assert result["requires_confirmation"] is True
    captured = caplog.text
    for sensitive in ("ALICE TAN", "900101", payload[:16].hex()):
        assert sensitive not in captured
