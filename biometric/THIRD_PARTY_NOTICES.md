# Third-party notices

The package embeds the exact tracked SFG Shared Biometric Core v1 from frozen Git
baseline `37bbbf64ecb79bb2d8598ea3c3a0243b33e7ef31`. Its upstream YuNet, SFace, and
Silent Face notices are preserved unchanged at
`internal/biometric-core/THIRD_PARTY_NOTICES.md` and its exact model provenance is
preserved at `internal/biometric-core/MODEL_MANIFEST.md`.

The model payloads are deliberately absent from the distributable ZIP because the
frozen manifest records redistribution review as pending. `setup.cmd` acquires only
the four commit-pinned payloads and verifies their exact sizes and SHA-256 values.

The isolated OCR runtime uses:

- PaddlePaddle 3.3.1 - Apache Software License; installed metadata homepage
  `https://www.paddlepaddle.org.cn/`; exact installed license copied to
  `licenses/PADDLEPADDLE_LICENSE.txt`.
- PaddleOCR 3.7.0 - Apache License 2.0; installed metadata homepage
  `https://github.com/PaddlePaddle/PaddleOCR`; exact installed license copied to
  `licenses/PADDLEOCR_LICENSE.txt`.
- PaddleX 3.7.2 - Apache-2.0; exact installed license copied to
  `licenses/PADDLEX_LICENSE.txt`.

The two OCR models initialized by setup are the PaddleOCR 3.7 explicit official
model names `PP-OCRv5_mobile_det` and `en_PP-OCRv5_mobile_rec`. They are acquired
into the ignored local `PADDLEOCR_MODEL_DIR` cache and are not included in the ZIP.
Package dependencies retain their own installed metadata and license obligations;
this notice does not replace those upstream terms.
