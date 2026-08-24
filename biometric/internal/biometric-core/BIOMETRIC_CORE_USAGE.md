# SFG Shared Biometric Core v1 Usage

## Purpose and boundary

This is a neutral in-process Python component for the same compatible facial
pipeline in assisted enrolment and kiosk verification:

`validated frame -> YuNet -> exactly one face -> Silent Face PAD -> SFace -> protected template/match`

It does not implement FastAPI, a database, persistence, encryption-key management,
PIN setup or verification, authorization, sessions, audit events, OCR, UI, camera
device policy, or deployment. `MATCH_CONFIRMED` is never authorization; the later
mandatory correct PIN remains a separate trusted-backend gate.

## Runtime and acquisition

Use a fresh Python 3.10 x64 environment without system-site packages. The exact
model sources, revisions, sizes, hashes, licenses, CPU-first runtime, and the
OpenCV/Silent Face compatibility rule are in [MODEL_MANIFEST.md](MODEL_MANIFEST.md).
Never replace a model with a latest download or a different quantized asset.

From the repository root, after acquiring the four ignored payloads at the exact
manifest paths:

```powershell
py -3.10 -m venv biometric-core/.venv
& biometric-core/.venv/Scripts/python.exe -m pip install -r biometric-core/requirements-biometric-core.lock.txt
$env:PYTHONPATH = 'biometric-core/src'
```

The package is intentionally usable through `PYTHONPATH`; no backend/web/database
package is required.

## Initialization

```python
from pathlib import Path

from sfg_biometric_core import BiometricCorePipeline
from sfg_biometric_core.sface import SFaceEngine
from sfg_biometric_core.silent_face_pad import SilentFacePAD
from sfg_biometric_core.yunet import YuNetDetector

root = Path("biometric-core")
detector = YuNetDetector.from_model_path(root / "models/face_detection_yunet_2023mar.onnx")
pad = SilentFacePAD.from_model_dir(root / "models/silent_face")
sface = SFaceEngine.from_model_path(root / "models/face_recognition_sface_2021dec.onnx")
core = BiometricCorePipeline(detector=detector, pad=pad, sface=sface)
```

All paths are checked against the pinned manifest before model loading. YuNet and
SFace use OpenCV CPU DNN. Silent Face weights are loaded once with weights-only
PyTorch loading and kept in CPU evaluation mode.

## Reference and fresh template generation

The trusted enrolment and kiosk callers pass an in-memory BGR `uint8` frame to the
same `core.process_frame(frame)` operation. The core validates rank, dimensions,
channels, dtype, and non-empty geometry; updates YuNet input size to the actual
frame; requires exactly one valid detection; runs both PAD models; and proceeds to
SFace only for `PAD_LIVE`.

On a live result, `PipelineResult.template` is a sensitive in-process value for a
trusted caller only. It is never a normal log field, UI value, error message, test
fixture, prompt, or documentation payload. The template is finite contiguous
float32 `(1,128)` and follows OpenCV 112x112 `alignCrop` and feature preprocessing.

Reference/enrolment and fresh/kiosk callers must use identical model hashes,
OpenCV baseline, CPU backend/target, landmark order, alignment, preprocessing,
dtype/shape, serialization, and comparison policy. The core has no separate
enrolment model and no final identity or access decision.

## Protected serialization and compatibility

Use `serialize_protected_template(template)` only across the later approved
protected backend envelope. Its binary payload is exactly 512 little-endian
float32 bytes and is represented as base64, never a JSON float list or pickle.
`deserialize_protected_template` validates the envelope fingerprint, byte length,
dtype, shape, and finiteness before returning a trusted in-process template. Any
fingerprint mismatch fails before comparison.

The internal fingerprint covers both model identities, runtime/backend, landmark
order, alignment, preprocessing, dtype/shape, serialization, metric, and comparison
policy. A template from another combination is not silently skipped or coerced.

## Protected 1:N comparison

The trusted backend later supplies a small eligible candidate set to
`match_1_to_n`. The operation is a pure linear comparison primitive and does not
query a database, decrypt persistence, or authorize. It validates every candidate
fingerprint before any comparison. Zero, one, or multiple candidates at or above
the provisional `SFACE_MATCH_THRESHOLD=0.363` map to `NO_MATCH`,
`MATCH_CONFIRMED`, or `AMBIGUOUS_MATCH`; comparison/numeric/compatibility failures
map to `MATCH_ERROR`. The threshold is sample-derived and provisional, not
SFG-calibrated. `SFACE_AMBIGUITY_MARGIN` is reserved and inactive.

`MatchOutcome.to_safe_outcome()` contains only the canonical status and a safe
diagnostic code. It does not expose candidate identities, rankings, candidate
counts, cosine scores, or templates. For exactly one match, trusted backend code
may explicitly call `matched_candidate_token_for_trusted_backend()` on the
protected in-process result; the opaque token is redacted from `repr` and omitted
from the safe projection. FastAPI must still require the correct PIN before
authorization.

## Canonical statuses

- `capture_status`: `CAPTURE_READY`, `NO_FACE`, `MULTIPLE_FACES`,
  `INVALID_CAPTURE`, `CAMERA_ERROR`
- `liveness_status`: `PAD_LIVE`, `PAD_REJECT`, `PAD_UNCERTAIN`, `PAD_ERROR`
- `match_status`: `MATCH_CONFIRMED`, `NO_MATCH`, `AMBIGUOUS_MATCH`, `MATCH_ERROR`

Only `CAPTURE_READY` and `PAD_LIVE` advance the locked pipeline. Rejected,
uncertain, malformed, missing, numeric, or model/runtime-error states fail closed.

## Data handling and limitations

Raw frames, PAD crops, fresh templates, decrypted enrolled templates, candidate
records, scores, and any PIN material are transient trusted-process data. The core
does not persist them or write images/results. Normal logs and errors contain only
canonical statuses and non-sensitive diagnostic codes; they do not contain arrays,
vectors, scores, candidates, identities, secrets, credentials, or stack traces.

Silent Face is prototype passive PAD. It is camera- and scene-sensitive and is not
certified, production-grade, universal, or guaranteed against printed photos,
replay screens, masks, lighting changes, compression, or unseen attacks. The
provisional SFace threshold and YuNet settings have not been SFG-calibrated.
1:N linear matching is suitable only for the small prototype candidate set.

## Verification gate

Automated tests and pinned model smoke checks do not replace physical camera
validation. A consenting human operator must run the locked A-J matrix with the
manual runner, record only safe canonical statuses and metadata, and retain no raw
frame/template by default. Core v1 is not accepted until the human camera gate and
remaining acceptance evidence are complete.

For manual D/E comparison, the preview uses `r` to capture one transient reference
and `f` to compare one fresh live template; the reference is cleared immediately.
Raw cosine output is disabled unless the operator explicitly adds
`--protected-calibration`, which is limited to D/E and must be treated as protected
transient evidence rather than ordinary/public output. Test J prints the required
human filesystem/log/Git inspection checklist without opening a camera or loading
models.
