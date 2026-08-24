"""Internal PaddleOCR subprocess; stdout is one minimal JSON result only."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from paddleocr import PaddleOCR

from .ic_parser import extract_ic_candidates


_DETECTION_MODEL = "PP-OCRv5_mobile_det"
_RECOGNITION_MODEL = "en_PP-OCRv5_mobile_rec"


def _model_paths() -> tuple[Path, Path]:
    model_root = Path(os.environ["PADDLEOCR_MODEL_DIR"]).resolve()
    official = model_root / "official_models"
    detection = official / _DETECTION_MODEL
    recognition = official / _RECOGNITION_MODEL
    if not detection.is_dir() or not recognition.is_dir():
        raise RuntimeError("OCR_MODELS_MISSING")
    return detection, recognition


def _recognized_lines(results: list[object]) -> list[str]:
    lines: list[str] = []
    for item in results:
        data = item.json if hasattr(item, "json") else {}
        payload = data.get("res", data) if isinstance(data, dict) else {}
        texts = payload.get("rec_texts", []) if isinstance(payload, dict) else []
        if isinstance(texts, (list, tuple)):
            lines.extend(text for text in texts if isinstance(text, str))
    return lines


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"image/jpeg", "image/png"}:
        return 2
    payload = sys.stdin.buffer.read(5 * 1024 * 1024 + 1)
    if not payload or len(payload) > 5 * 1024 * 1024:
        return 2
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return 2
    detection, recognition = _model_paths()
    ocr = PaddleOCR(
        device="cpu",
        text_detection_model_name=_DETECTION_MODEL,
        text_detection_model_dir=str(detection),
        text_recognition_model_name=_RECOGNITION_MODEL,
        text_recognition_model_dir=str(recognition),
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
    )
    candidates = extract_ic_candidates(_recognized_lines(list(ocr.predict(image))))
    sys.stdout.write(json.dumps(candidates.to_dict(), separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
