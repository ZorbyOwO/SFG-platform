from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from sfg_registration_core.ocr import IsolatedPaddleOCRBackend, OCRService


@pytest.mark.skipif(os.environ.get("SFG_RUN_REAL_OCR") != "1", reason="real OCR gate is opt-in")
def test_synthetic_ic_style_image_reaches_minimal_candidates() -> None:
    package_root = Path(__file__).resolve().parents[1]
    image = np.full((420, 1000, 3), 255, dtype=np.uint8)
    cv2.putText(image, "NAME: ALICE TAN", (40, 140), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(image, "IC: 900101-01-1234", (40, 260), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 0), 3, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    service = OCRService(backend=IsolatedPaddleOCRBackend(package_root=package_root))

    result = service.scan(encoded.tobytes(), media_type="image/png")

    assert result == {
        "full_name": "ALICE TAN",
        "ic": "900101-01-1234",
        "requires_confirmation": True,
    }
