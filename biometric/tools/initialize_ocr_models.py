"""Acquire/initialize the two explicit PP-OCRv5 mobile models on CPU."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    model_root = Path(os.environ.get("PADDLEOCR_MODEL_DIR", package_root / ".paddleocr-models")).resolve()
    os.environ["PADDLEOCR_MODEL_DIR"] = str(model_root)
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(model_root)
    os.environ["PADDLE_PDX_MODEL_SOURCE"] = "bos"
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

    import cv2
    import numpy as np
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(
        device="cpu",
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="en_PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=False,
    )
    synthetic = np.full((120, 320, 3), 255, dtype=np.uint8)
    cv2.putText(synthetic, "OCR READY", (18, 72), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    list(ocr.predict(synthetic))
    print("paddleocr_models=PP-OCRv5_mobile_det,en_PP-OCRv5_mobile_rec status=INITIALIZED_CPU")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
