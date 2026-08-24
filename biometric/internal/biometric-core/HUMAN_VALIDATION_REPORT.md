# SFG Shared Biometric Core v1 Human Validation Report

- **Validation date:** 23 August 2026 MYT
- **Validation scope:** Locked physical A-J human-observation matrix
- **Environment:** Actual target Windows host, Python 3.10.6, OpenCV camera index 0, observed frame geometry 640x480
- **Manifest fingerprint:** `a18bbbd47a57d14d`
- **Calibration mode:** Not used

**Overall verdict:** Human A-J gate accepted with the caveats and bounded claims recorded below

## Evidence boundary

This report reconciles the human operator's observations from the existing manual runner. It records canonical statuses and safe representation metadata only. No raw SFace values or similarity scores were intentionally exposed, no protected calibration mode was used, and no biometric performance rate was derived.

The evidence supports the Shared Biometric Core v1 only in the recorded prototype environment. It does not by itself authorize access: `MATCH_CONFIRMED` remains distinct from `AUTHORIZATION_GRANTED`, and the later correct PIN remains mandatory.

## Test A — Single live participant: PASS

- One consenting live participant repeatedly produced `CAPTURE_READY`, `PAD_LIVE`, and `template_status=GENERATED_TRANSIENTLY shape=(1,128) dtype=float32 bytes=512`.
- A transient `NO_FACE` during movement recovered correctly.
- The generated template remained transient.

## Test B — No face: PASS

- A blank wall observed for approximately 20 seconds produced `NO_FACE`, with liveness `NOT_REACHED` and template `NOT_GENERATED`.
- No PAD or SFace generation followed the no-face result.

## Test C — Multiple faces: PASS on attempt 2; attempt 1 INCONCLUSIVE

- Attempt 1 remains explicitly **INCONCLUSIVE**. One participant was near the camera and the second was substantially farther away; YuNet frequently resolved only the nearby participant, so reliable `MULTIPLE_FACES` was not observed.
- Attempt 2 used two consenting participants clearly visible at similar/near distance and repeatedly produced `MULTIPLE_FACES`, liveness `NOT_REACHED`, and template `NOT_GENERATED`.
- Scene transitions as participants moved, disappeared, and reappeared also produced the expected `CAPTURE_READY`, `INVALID_CAPTURE`, and `NO_FACE` states.
- The passing second attempt closes Test C for the defined human gate without erasing the first attempt's distance/framing limitation.

## Test D — Same person: PASS

- A transient reference and fresh comparison for the same consenting participant returned `MATCH_CONFIRMED` and `comparison_reference_status=CLEARED`.
- The operator accidentally pressed `r` several times; each new reference capture replaced the previous transient reference.
- This is functional same-person comparison evidence only. It is not a pose-robustness measurement and does not establish FAR, FRR, or general accuracy.

## Test E — Different people: PASS

- Person A's transient reference followed by Person B's fresh capture returned `NO_MATCH` and `comparison_reference_status=CLEARED`.
- During positioning, Person B temporarily produced `PAD_UNCERTAIN` and `PAD_REJECT` before a later `PAD_LIVE` observation.
- No template was generated in the fail-closed non-live states.

## Test F — Physical 2D presentation attack: PASS

- A consenting participant's physical passport/document portrait was presented while the real participant was absent from the camera frame; no printer was available.
- Repeated observations produced `CAPTURE_READY`, `PAD_REJECT`, and template `NOT_GENERATED`.
- Intermittent `NO_FACE` occurred because the portrait was relatively small.
- No `PAD_LIVE` or template generation was observed.
- This was a **physical passport/document portrait presentation attack**, not an A4 printed-selfie test.

## Test G — Phone/screen replay: PASS

- A consented facial image was displayed on a phone. Some displayed frames contained two faces.
- Single-face detections repeatedly produced `CAPTURE_READY`, `PAD_REJECT`, and template `NOT_GENERATED`.
- When both displayed faces were detected, the result was `MULTIPLE_FACES`, liveness `NOT_REACHED`, and template `NOT_GENERATED`.
- No `PAD_LIVE` or template generation was observed.

## Test H — Poor/edge capture: PASS WITH MIXED-RUN CAVEAT

- The operator deliberately moved a truncated/partial live face around frame boundaries, allowed distant faces to appear, and briefly presented a normal complete live face as a control.
- Poor/edge frames repeatedly produced `INVALID_CAPTURE` or `NO_FACE`, with liveness `NOT_REACHED` and template `NOT_GENERATED`.
- Normal full-face control periods produced `CAPTURE_READY`, `PAD_LIVE`, and a transiently generated template.
- The observation supports repeated fail-closed handling for the tested poor/edge captures. It does not show that every partial-face pose is rejected and does not establish a rejection rate.

## Test I — Unavailable camera: PASS

- Camera index 2 was selected as unavailable.
- DirectShow reported that it could not capture the device by index.
- The canonical result was `capture_status=CAMERA_ERROR`; no successful biometric processing followed.

## Test J — Data-handling audit: PASS, bounded to observed checks

- The runner requested human inspection.
- At the time of the human audit, `git status --short`, `git diff --stat`, and `git diff` were empty.
- A recursive media/template artifact search excluding virtual environments and model assets found no unexpected files.
- A suspicious-name search found only expected model, source, test, and `__pycache__` entries.
- Console output exposed only safe representation metadata such as `shape=(1,128)`, `dtype=float32`, and `bytes=512`.
- No template values, similarity scores, participant IDs, PINs, or secrets were intentionally printed.
- A read-only recursive scan of `$env:TEMP` for files modified within the preceding three hours whose names matched `(sfg|biometric|template|embedding|face|capture|probe|snapshot)` returned no rows. No files were deleted.
- The TEMP result means no matching recent artifact was found in that inspected location and time window. It does not prove absence beyond those locations or that time window.

## Manual-runner responsiveness observation

During one earlier run, `q`/Escape felt sluggish because synchronous CPU biometric inference completed before `cv2.waitKey` processed keyboard input. The operator eventually used Ctrl+C and observed `KeyboardInterrupt` inside PyTorch `conv2d`. This is a manual-runner responsiveness/usability observation, not a biometric model failure. Later runs stopped normally.

## Final A-J interpretation

- Tests A and B passed.
- Test C passed on attempt 2; attempt 1 remains explicitly inconclusive.
- Tests D, E, F, G, I, and J passed.
- Test H passed with the mixed-run caveat above.
- The locked Core v1 human A-J gate is accepted on this evidence, with all limitations and bounded claims preserved.

The resulting validated Git closure commit becomes the accepted/frozen SFG Shared Biometric Core v1 integration baseline only after the host operator independently verifies this documentation-only reconciliation, commits it, and pushes it. Assisted registration and kiosk integrations may vary UI, orchestration, capture guidance, API/session handling, and retry behavior, but they must consume this same compatibility-critical core. They must not independently fine-tune, retrain, or fork YuNet, Silent Face PAD, or SFace.

## Explicit non-claims and remaining limitations

- No FAR claim.
- No FRR claim.
- No general biometric accuracy percentage.
- No universal PAD or security guarantee.
- No certification.
- No production-readiness claim.
- `SFACE_MATCH_THRESHOLD=0.363` remains sample-derived and provisional unless separately calibrated and approved.
- The observed results are specific to the recorded host, camera index, 640x480 capture geometry, participants, presentation media, framing, lighting, and test runs.
- Test C attempt 1 demonstrates a distance/framing limitation for reliable multiple-face detection.
- Test F did not exercise an A4 printed-selfie attack.
- Test H did not exhaust partial-face, blur, pose, obstruction, illumination, or other poor-capture conditions.
- Test J is bounded to the inspected paths, output, repository state at audit time, and three-hour TEMP window.

## Next workstream boundary

PaddleOCR is not implemented by this validation closure. The next separately authorized workstream may cover registration/OCR/PaddleOCR, enrolment orchestration, and an adapter that consumes the frozen biometric core. PaddleOCR remains outside `biometric-core/` and `biometric-core/.venv/`; teammate-owned registration UI remains untouched without coordination.
