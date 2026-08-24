# Dependency and model acquisition record

- Target: Windows x64, Python 3.10.6, CPU-first.
- Frozen mother baseline: `37bbbf64ecb79bb2d8598ea3c3a0243b33e7ef31`.
- Primary registration environment: exact unchanged mother lock at
  `internal/biometric-core/requirements-biometric-core.lock.txt`.
- OCR environment: exact `requirements-ocr.lock.txt` with PaddlePaddle 3.3.1,
  PaddleOCR 3.7.0, PaddleX 3.7.2, OpenCV contrib 4.10.0.84, NumPy 2.2.6, and
  Pillow 12.3.0.

## Isolation decision

The combined dry-run required `opencv-contrib-python` in addition to the mother's
exact `opencv-python==4.10.0.84`. Both distributions install the same `cv2` module,
so accepting both would replace/overlap the frozen runtime package identity. The
package therefore uses hidden process isolation: `.venv` remains the exact mother
runtime and `.venv-ocr` owns PaddleOCR. Both are created by the single `setup.cmd`
and consumed behind `SFGRegistrationCore`.

Paddle 3.3.1 `paddle.utils.run_check()` passed on one CPU. Initial PP-OCRv5 inference
with oneDNN enabled failed with Paddle's
`ConvertPirAttribute2RuntimeAttribute` unimplemented error. The OCR-only worker now
sets `enable_mkldnn=False`; explicit CPU initialization and inference then passed.

## Acquisition

- Biometric payloads: exact commit-pinned URLs, sizes, and SHA-256 values enforced
  by `tools/acquire_biometric_models.py`; payloads are absent from the ZIP.
- OCR models: explicit official names `PP-OCRv5_mobile_det` and
  `en_PP-OCRv5_mobile_rec`, acquired by Paddle into the ignored canonical
  `PADDLEOCR_MODEL_DIR`; model cache is absent from the ZIP.
- No manual model hunting is required: run `setup.cmd` once.
