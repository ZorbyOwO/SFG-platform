# THIS IS THE SFG REGISTRATION BASE PACKAGE

Use this folder as **ONE unit**. It contains the validated SFG Shared Biometric Core
v1 plus PaddleOCR-assisted registration. There is no choice between base models.
Do not independently modify YuNet, Silent Face PAD, or SFace; configure only through
the provided setup/configuration path.

## 1. Setup and verify

From Windows Command Prompt:

```bat
setup.cmd
verify.cmd
```

`setup.cmd` creates both internal Python 3.10 environments, installs their exact
locks, acquires/verifies the pinned biometric assets, initializes the two explicit
PaddleOCR models, and runs verification. Paddle stays outside the mother's runtime.

## 2. Import the one facade

```python
from sfg_registration_core import SFGRegistrationCore

registration = SFGRegistrationCore.from_package()
```

Run with these package paths on `PYTHONPATH`:

```bat
set "PYTHONPATH=%CD%\src;%CD%\internal\biometric-core\src"
```

## 3. Scan an IC document in memory

```python
candidates = registration.scan_ic(image_bytes, media_type="image/jpeg")
# {"full_name": str | None, "ic": str | None, "requires_confirmation": True}
```

Only JPEG/PNG up to 5 MiB is accepted. The document is not persisted. OCR returns
no full text by default, and uncertain fields are `None`. Show candidates for human
confirmation and always offer manual entry.

For the teammate FastAPI seam, `POST /ocr/ic` should read the authenticated upload
in memory, call `scan_ic(payload, image.content_type)`, close the upload, return only
the three candidate fields, and keep the existing manual-entry fallback. Do not log
the payload, name, IC, or full OCR output.

## 4. Process a live face

```python
safe_face = registration.process_face(frame)
```

`process_face` delegates to the unchanged mother and returns only safe statuses,
diagnostic code, and whether a transient template was generated. It never returns
the template to an untrusted UI. Trusted in-process/backend code may use
`registration.biometric`, which is the actual accepted `sfg_biometric_core`
pipeline--not a second implementation.

## Safe results and boundaries

- OCR is authorized-registration assistance only; it does not authenticate,
  authorize, verify a PIN, prove document authenticity/ownership, or link the
  document portrait to the live person.
- `ic` is never `citizen_id`; an OCR name is never authoritative
  `citizen_display_name` until human-confirmed trusted orchestration maps it.
- The live camera, not the document portrait, supplies the enrolment biometric.
- `MATCH_CONFIRMED != AUTHORIZATION_GRANTED`; the later correct backend PIN remains
  mandatory.
- `SFACE_MATCH_THRESHOLD=0.363` remains provisional. The ambiguity and PAD scalar
  thresholds remain inactive.

## Do not change

- `internal/biometric-core/src/sfg_biometric_core/` or its fingerprint/manifest;
- YuNet landmarks, Silent Face crops/classes, SFace `alignCrop`, preprocessing,
  float32 `(1,128)` template, 512-byte serialization, cosine metric, or 1:N policy;
- the exact v1.2 22-variable/32-status/18-config contract;
- PIN, authorization, audit, persistence, or UI behavior inside this package.

The package is a verified hackathon integration base, not a production-readiness,
accuracy, FAR/FRR, certification, or universal PAD claim.
