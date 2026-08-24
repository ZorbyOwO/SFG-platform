"""Safe Paddle runtime gate; real OCR inference is covered by package tests."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    package_root = Path(__file__).resolve().parents[1]
    model_root = Path(os.environ.get("PADDLEOCR_MODEL_DIR", package_root / ".paddleocr-models")).resolve()
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(model_root)
    import cv2
    import numpy
    import paddle
    import paddleocr

    paddle.utils.run_check()
    required = (
        model_root / "official_models" / "PP-OCRv5_mobile_det",
        model_root / "official_models" / "en_PP-OCRv5_mobile_rec",
    )
    if not all(path.is_dir() for path in required):
        print("paddle_runtime=FAIL models_missing")
        return 1
    print(
        "paddle_runtime=PASS device=cpu "
        f"paddle={paddle.__version__} paddleocr={paddleocr.__version__} "
        f"opencv={cv2.__version__} numpy={numpy.__version__} models=2"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
