# Real Kiosk Supabase Payment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working trusted flow from a live kiosk face capture to one eligible Supabase citizen profile and an idempotent deduction from that profile's Supabase main wallet.

**Architecture:** FastAPI keeps the kiosk session and kiosk-key boundary, runs the unchanged frozen CoreCV mother in-process, decrypts only active front-pose templates inside the trusted tier, and performs 1:N SFace matching with the configured `0.40` application threshold and the mother's fail-closed rule that more than one threshold crossing is ambiguous. After a match, a separate yes/no identity-confirmation endpoint gates PIN entry; trusted service-role RPCs verify the matched profile's PIN and atomically charge its main wallet. Hosted enrolment persistence is changed first to replace all three sealed poses as one generation so matching never consumes partial or mixed template state.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, httpx/PostgREST RPC, PostgreSQL/Supabase PL/pgSQL, AES-256-GCM, frozen YuNet/Silent Face PAD/SFace CoreCV, vanilla kiosk HTML/CSS/JavaScript, pytest.

**Spec:** `AGENTS.md` product intent, biometric invariants, and source-of-truth rules; user request dated 2026-08-24 for real face identification -> Supabase profile -> Supabase wallet deduction.

## Global Constraints

- The frozen mother under `biometric/internal/biometric-core/` must not be edited.
- A face match identifies a person; it never authorizes payment without explicit identity confirmation and the correct six-digit PIN.
- Raw face frames are transient and must never enter logs, files, browser storage, analytics, or Supabase.
- Encrypted templates, decrypted embeddings, similarity scores, service credentials, and PINs must never be returned to the kiosk or browser.
- Hosted templates must use encryption version `sfg-aesgcm-v1` and compatibility fingerprint `a18bbbd47a57d14d` for the currently validated runtime.
- Matching uses `SFACE_MATCH_THRESHOLD=0.40` as the explicit POC application threshold and the frozen mother's `SFG_SHARED_BIOMETRIC_CORE_V1_1N_LINEAR` ambiguity policy; production calibration remains required. The legacy `SFACE_AMBIGUITY_MARGIN` setting is not substituted into the mother's policy.
- Supabase wallet mutation must remain exact-decimal, row-locked, atomic, and idempotent through trusted SQL.
- The feature supports active main citizen profiles; Family Member real-CoreCV identification stays excluded until its cross-tier ownership and template schema are approved.
- Existing user-owned uncommitted work must be preserved; no reset, broad cleanup, commit, push, hosted migration, or deployment occurs without the authority defined in `AGENTS.md`.
- Implementation runs on branch `codex/real-kiosk-supabase`; plan commit steps are intentionally replaced by verification checkpoints because the user did not request commits.

---

### Task 1: Atomic Three-Pose Hosted Template Generations

**Files:**
- Modify: `api/services/template_persister.py`
- Modify: `api/routers/biometric.py`
- Create: `db/migrations/014_real_kiosk_face_payment.sql`
- Create: `supabase/migrations/20260824013625_real_kiosk_face_payment.sql`
- Modify: `api/tests/test_template_persister.py`
- Modify: `api/tests/test_biometric_completion.py`

**Interfaces:**
- Consumes: `SealedTemplateBundle` from `api.services.template_sealer` and the existing staged pose records from `EncryptedTemplateStore.read_session_staged_templates(session_id, subject)`.
- Produces: `SupabaseTemplatePersister.persist_generation(*, citizen_id: str, generation_id: str, bundles: dict[str, SealedTemplateBundle]) -> tuple[str, ...]`; RPC `sfg_backend_replace_template_generation(p_citizen_id uuid, p_generation_id uuid, p_bundles jsonb) -> jsonb`; loader rows containing `capture_pose` and `generation_id`.

- [x] **Step 1: Write failing persister and completion tests**

```python
def test_persist_generation_sends_all_required_poses_in_one_rpc():
    ids = persister.persist_generation(
        citizen_id=CITIZEN_ID,
        generation_id=GENERATION_ID,
        bundles={"front": front, "right": right, "left": left},
    )
    assert ids == (FRONT_ID, RIGHT_ID, LEFT_ID)
    assert len(client.calls) == 1
    assert {row["capture_pose"] for row in client.calls[0]["json"]["p_bundles"]} == {"front", "right", "left"}
```

```python
def test_complete_uploads_one_atomic_generation_before_local_commit(client, scripted_persister):
    response = client.post("/biometric/complete", json={"session_id": session_id}, headers=auth)
    assert response.status_code == 200
    assert scripted_persister.generations[0].poses == {"front", "right", "left"}
    assert template_store.active_template_count(citizen_id) == 3
```

- [x] **Step 2: Run the focused tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest api\tests\test_template_persister.py api\tests\test_biometric_completion.py -q`

Expected: FAIL because `persist_generation` does not exist and completion still invokes three independent `persist` calls.

- [x] **Step 3: Add the migration contract**

```sql
alter table private.sfg_biometric_templates
  add column if not exists capture_pose text,
  add column if not exists generation_id uuid;

create unique index sfg_one_active_template_per_citizen_pose_idx
  on private.sfg_biometric_templates (citizen_id, capture_pose)
  where template_status = 'TEMPLATE_ACTIVE';
```

The migration revokes incompatible legacy active rows, removes the one-active-row index, constrains poses to `front/right/left`, validates exactly three distinct bundles in `sfg_backend_replace_template_generation`, revokes the prior generation and inserts the new generation inside one PL/pgSQL transaction, adds `sfg_backend_load_identification_gallery` to expose front-pose/generation rows only to `service_role`, filters to active/consented/completed profiles, and revokes execution from `public`, `anon`, and `authenticated`. The new RPC name makes an undeployed schema fail as unavailable instead of looking like an empty gallery through the legacy loader.

- [x] **Step 4: Implement one-call generation persistence**

```python
def persist_generation(
    self,
    *,
    citizen_id: str,
    generation_id: str,
    bundles: dict[str, SealedTemplateBundle],
) -> tuple[str, ...]:
    payload = _generation_rpc_payload(citizen_id, generation_id, bundles)
    response = self._request(payload)
    return _template_ids(response)
```

`api/routers/biometric.py` generates one UUID, seals all required poses, calls `persist_generation` once, and only then commits the local staged generation.

- [x] **Step 5: Run focused tests and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest api\tests\test_template_persister.py api\tests\test_biometric_completion.py -q`

Expected: PASS with one hosted call containing all three poses and no local commit after a refused hosted call.

- [x] **Step 6: Verification checkpoint**

Run: `git diff --check -- api/services/template_persister.py api/routers/biometric.py db/migrations/014_real_kiosk_face_payment.sql supabase/migrations/20260824013625_real_kiosk_face_payment.sql api/tests/test_template_persister.py api/tests/test_biometric_completion.py`

Expected: no whitespace errors; leave changes uncommitted for final user review.

### Task 2: Trusted Supabase Gallery, Profile, PIN, and Charge Client

**Files:**
- Create: `api/services/supabase_kiosk.py`
- Create: `api/tests/test_supabase_kiosk.py`
- Modify: `db/migrations/014_real_kiosk_face_payment.sql`
- Modify: `supabase/migrations/20260824013625_real_kiosk_face_payment.sql`

**Interfaces:**
- Consumes: service-role `SUPABASE_URL`, `SUPABASE_BACKEND_SECRET`, sealed template fields, citizen UUID, kiosk id, `Decimal` amount, and idempotency key.
- Produces: `HostedTemplate`, `CitizenIdentity`, and `WalletCharge` immutable dataclasses; `SupabaseKioskClient.load_templates()`, `profile_identity(citizen_id)`, `verify_pin(citizen_id, pin)`, and `charge_main_wallet(citizen_id, kiosk_id, amount, idempotency_key)`.

- [x] **Step 1: Write failing HTTP-boundary behavior tests**

```python
def test_load_templates_accepts_only_complete_front_rows():
    records = client.load_templates()
    assert records == (HostedTemplate(template_id=ID, citizen_id=CITIZEN, capture_pose="front", generation_id=GENERATION, encrypted_payload=PAYLOAD, nonce=NONCE, compatibility_fingerprint=FINGERPRINT),)
```

```python
def test_charge_main_wallet_returns_atomic_rpc_result():
    charge = client.charge_main_wallet(CITIZEN, KIOSK, Decimal("12.34"), "pay:session-123")
    assert charge.amount == Decimal("12.34")
    assert charge.balance_after == Decimal("87.66")
    assert charge.reference.startswith("SFG-")
```

Add separate tests for forbidden/missing RPC, malformed rows, mismatched fingerprint, PIN false, insufficient funds, inactive profile, and repeated idempotency returning the same transaction.

- [x] **Step 2: Run the new module tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest api\tests\test_supabase_kiosk.py -q`

Expected: collection FAIL because `api.services.supabase_kiosk` is absent.

- [x] **Step 3: Add trusted SQL RPCs**

```sql
create or replace function public.sfg_backend_profile_identity(p_citizen_id uuid) returns jsonb ...;
create or replace function public.sfg_backend_charge_profile_wallet(
  p_citizen_id uuid,
  p_amount numeric,
  p_kiosk_id text,
  p_idempotency_key text
) returns jsonb ...;
```

The identity RPC returns the full name and IC only for an eligible active citizen. The charge RPC resolves exactly the main wallet (`family_member_id is null`), derives the merchant from the active kiosk rather than client input, delegates mutation to `sfg_charge_wallet(..., 'face_pin', ...)`, and returns transaction id, reference, amount, merchant, and balance after. `sfg_backend_verify_pin` gains an explicit `profile_state='active'` requirement.

- [x] **Step 4: Implement the fail-closed PostgREST client**

```python
class SupabaseKioskClient:
    def load_templates(self) -> tuple[HostedTemplate, ...]: ...
    def profile_identity(self, citizen_id: str) -> CitizenIdentity: ...
    def verify_pin(self, citizen_id: str, pin: str) -> bool: ...
    def charge_main_wallet(self, citizen_id: str, kiosk_id: str, amount: Decimal, idempotency_key: str) -> WalletCharge: ...
```

Each method sends the secret only in authorization headers, limits logs to RPC name/status/exception type, rejects non-HTTPS remote URLs, validates UUID/base64/decimal response types, and maps trusted database error codes to stable `ApiError` responses without response-body logging.

- [x] **Step 5: Run the module tests and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest api\tests\test_supabase_kiosk.py -q`

Expected: PASS for success, malformed, authorization, inactive-profile, PIN, funds, and idempotency cases.

- [x] **Step 6: Verification checkpoint**

Run: `git diff --check -- api/services/supabase_kiosk.py api/tests/test_supabase_kiosk.py db/migrations/014_real_kiosk_face_payment.sql supabase/migrations/20260824013625_real_kiosk_face_payment.sql`

Expected: no whitespace errors; leave changes uncommitted for final user review.

### Task 3: Real CoreCV 1:N Identification Service

**Files:**
- Modify: `api/services/biometric_core.py`
- Create: `api/services/face_identification.py`
- Create: `api/tests/test_face_identification.py`

**Interfaces:**
- Consumes: a transient JPEG/PNG, `CoreCVBiometricEngine`, hosted front-pose `HostedTemplate` rows, AES key bytes, and application threshold `Decimal('0.40')`.
- Produces: `FaceIdentificationResult(capture_status, liveness_status, match_status, citizen_id)` with no template or score projection; `FaceIdentificationService.identify(image_bytes, content_type) -> FaceIdentificationResult`.

- [x] **Step 1: Write failing unique/no-match/ambiguous/tamper tests**

```python
def test_identify_returns_only_unique_matched_citizen():
    result = service.identify(LIVE_JPEG, "image/jpeg")
    assert result.match_status is MatchStatus.CONFIRMED
    assert result.citizen_id == CITIZEN_A
    assert not hasattr(result, "score")
```

Add cases where no candidate crosses `0.40`, two citizens both cross `0.40`, PAD is not live, hosted AAD decryption fails, fingerprints differ, and duplicate citizen rows appear. All fail without disclosing a candidate.

- [x] **Step 2: Run the identification tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest api\tests\test_face_identification.py -q`

Expected: collection FAIL because the service is absent.

- [x] **Step 3: Add trusted CoreCV matching methods without changing the mother**

```python
def deserialize_protected_template(self, payload_base64: str, fingerprint_id: str) -> Any: ...
def match_1_to_n(self, probe: Any, candidates: tuple[tuple[str, Any], ...], *, threshold: float) -> tuple[MatchStatus, str | None]: ...
```

The adapter imports the frozen mother's deserializer and matcher through its existing import boundary. Only front-pose rows enter the gallery so three poses from one person cannot create false cross-candidate ambiguity.

- [x] **Step 4: Implement decrypt -> deserialize -> match orchestration**

```python
class FaceIdentificationService:
    def identify(self, image_bytes: bytes, content_type: str | None) -> FaceIdentificationResult:
        verdict = self._engine.analyse_enrolment(image_bytes, content_type)
        if not verdict.accepted:
            return FaceIdentificationResult.from_capture(verdict)
        gallery = self._trusted.load_templates()
        return self._match_unique_citizen(verdict.protected_template_for_trusted_backend(), gallery)
```

Open each AES-GCM bundle with citizen/pose/fingerprint-bound AAD, compare only compatible front templates, collapse malformed or duplicate rows fail-closed, erase local references after matching, and return only canonical statuses plus the matched UUID inside server memory.

- [x] **Step 5: Run tests and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest api\tests\test_face_identification.py api\tests\test_biometric_core.py api\tests\test_corecv_integration.py -q`

Expected: PASS with the frozen-core integration tests unchanged.

- [x] **Step 6: Verification checkpoint**

Run: `.\.venv\Scripts\python.exe scripts\verify_biometric.py`

Expected: all six gates pass with mother SHA `37bbbf64` and runtime fingerprint `a18bbbd47a57d14d`; leave changes uncommitted.

### Task 4: Payment State Machine and Explicit Identity Confirmation

**Files:**
- Modify: `api/contracts.py`
- Modify: `api/routers/pay.py`
- Modify: `api/main.py`
- Modify: `api/models.py`
- Create: `api/tests/test_real_kiosk_payment.py`
- Modify: `api/tests/test_flows.py`

**Interfaces:**
- Consumes: `FaceIdentificationService.identify`, `SupabaseKioskClient.profile_identity`, `verify_pin`, `charge_main_wallet`, existing `VerificationSession`, kiosk key, session nonce, and price.
- Produces: `PayIdentityConfirmRequest(session_id: str, nonce: str, confirmed: bool)`; `POST /pay/identity/confirm`; payment states `open -> matched -> identity_confirmed -> consumed` or fail-closed termination.

- [x] **Step 1: Write failing end-to-end route tests**

```python
def test_real_payment_charges_only_the_face_matched_profile(client, trusted_backend):
    identified = identify_live_face(client)
    assert identified["identity_confirmation_status"] == "IDENTITY_CONFIRMATION_REQUIRED"
    assert client.post("/pay/confirm", json=pin_payload).status_code == 409
    assert confirm_identity(client, True).json()["identity_confirmation_status"] == "IDENTITY_CONFIRMED"
    receipt = client.post("/pay/confirm", json=pin_payload).json()
    assert trusted_backend.charges == [(MATCHED_CITIZEN, KIOSK_ID, Decimal("12.34"), session_id)]
    assert receipt["authorization_status"] == "AUTHORIZATION_GRANTED"
```

Add separate tests for liveness rejection, no templates, no match, ambiguity, profile disappearance after match, explicit No, wrong PIN attempt/lock, confirm-before-yes, insufficient funds, backend outage, and repeated confirm returning the same transaction without a second charge. Preserve one explicit simulation-header test for isolated legacy fixtures.

- [x] **Step 2: Run the route tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest api\tests\test_real_kiosk_payment.py -q`

Expected: collection or assertion FAIL because the identity-confirm endpoint and trusted real path do not exist.

- [x] **Step 3: Add the explicit confirmation DTO and state transition**

```python
class PayIdentityConfirmRequest(SessionRequest):
    nonce: str
    confirmed: bool
```

`POST /pay/identity/confirm` accepts only a matched live session. `false` sets `IDENTITY_REJECTED`, denies authorization, terminates the session, and never permits PIN. `true` sets `IDENTITY_CONFIRMED` and status `identity_confirmed`.

- [x] **Step 4: Replace default simulator behavior with trusted behavior**

`/pay/identify` uses `FaceIdentificationService` unless `APP_ENV=test` and an explicit `X-SFG-Simulation` header is present. It stores only the matched citizen UUID and returns masked identity fields. `/pay/confirm` accepts only `identity_confirmed` or an already consumed idempotent replay, verifies the PIN against that stored UUID, runs `authorization_decision(..., identity_confirmation_enabled=True, pin_required=True)`, and invokes the Supabase charge. No `FACE_ONLY_MODE` bypass applies to the real path.

- [x] **Step 5: Wire services and health state in `create_app`**

```python
app.state.supabase_kiosk = SupabaseKioskClient(...)
app.state.face_identification = FaceIdentificationService(...)
```

The app exposes `real_kiosk_payment: configured|unconfigured` in `/health`. Missing secret/core/key yields a truthful `503 real_kiosk_unavailable`; it never falls back to the simulator.

- [x] **Step 6: Run route and legacy regression tests and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest api\tests\test_real_kiosk_payment.py api\tests\test_flows.py api\tests\test_authorization.py -q`

Expected: PASS for the real flow, explicit confirmation, wrong-PIN lock, exact matched-citizen charge, idempotency, and explicit test-only simulator coverage.

- [x] **Step 7: Verification checkpoint**

Run: `git diff --check -- api/contracts.py api/routers/pay.py api/main.py api/models.py api/tests/test_real_kiosk_payment.py api/tests/test_flows.py`

Expected: no whitespace errors; leave changes uncommitted for final user review.

### Task 5: Kiosk UI Uses the Real Flow

**Files:**
- Modify: `kiosk/index.html`
- Modify: `kiosk/scan.html`
- Modify: `kiosk/confirm.html`
- Modify: `kiosk/receipt.html`
- Modify: `kiosk/js/kiosk.js`
- Modify: `kiosk/css/kiosk.css`

**Interfaces:**
- Consumes: `/pay/session`, `/pay/identify`, `/pay/identity/confirm`, `/pay/confirm`, `/pay/cancel`.
- Produces: a kiosk interaction that shows masked matched identity, requires Yes before displaying the PIN form, treats No as rejection/reset, and shows the Supabase transaction reference and balance after.

- [x] **Step 1: Establish the static UI RED check**

Run: `rg -n "X-SFG-Simulation|identity/confirm|IDENTITY_CONFIRMATION_REQUIRED" kiosk`

Expected: the simulation header exists and the identity-confirm API call/status are absent.

- [x] **Step 2: Implement explicit confirmation UI and remove simulation request**

```javascript
const result = await api("/pay/identify", { method: "POST", body: form });
await api("/pay/identity/confirm", {
  method: "POST",
  body: JSON.stringify({ session_id: current.session_id, nonce: current.nonce, confirmed: true }),
});
pinPanel.hidden = false;
```

The No button sends `confirmed:false`, clears sensitive inputs and session data, and returns to amount entry. The PIN form stays hidden until Yes succeeds. Page copy says live face identification and POC simulated payment settlement accurately; it does not claim certification or bank settlement.

- [x] **Step 3: Run static and frontend build checks**

Run: `rg -n "X-SFG-Simulation" kiosk`

Expected: zero matches.

Run: `rg -n "identity/confirm|confirmed: true|confirmed: false" kiosk/js/kiosk.js`

Expected: all three real confirmation contract markers are present.

Run: `Push-Location web; npm test -- --run; npm run build; Pop-Location`

Expected: frontend tests and production build pass; kiosk stays static with no bundler dependency.

- [x] **Step 4: Verification checkpoint**

Run: `git diff --check -- kiosk/index.html kiosk/scan.html kiosk/confirm.html kiosk/receipt.html kiosk/js/kiosk.js kiosk/css/kiosk.css`

Expected: no whitespace errors; leave changes uncommitted for final user review.

### Task 6: Deployment, End-to-End Verification, and Handoff Truth

**Files:**
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `CHANGELOGS.md`

**Interfaces:**
- Consumes: all completed feature tasks, hosted Supabase migration state, a consenting enrolled citizen, physical camera, active kiosk, and funded POC wallet.
- Produces: verified hosted schema parity, an end-to-end purchase receipt tied to the matched citizen, and documentation that distinguishes automated proof from the remaining physical human gate.

- [x] **Step 1: Run the complete automated verification**

Run: `$env:TEMP=(Resolve-Path 'api/.runtime/verify-temp'); $env:TMP=$env:TEMP; .\.venv\Scripts\python.exe scripts\verify_biometric.py`

Run: `$env:SUPABASE_URL=''; $env:SUPABASE_BACKEND_SECRET=''; .\.venv\Scripts\python.exe -m pytest api\tests -q`

Run: `Push-Location web; npm test -- --run; npm run build; Pop-Location`

Run: `git diff --check`

Expected: frozen verification, all backend tests, all frontend tests, production build, and whitespace check pass.

- [x] **Step 2: Validate and apply the hosted migration**

The local Windows CLI had no access token, so its dry run failed without changing hosted state. The authenticated Supabase management boundary then confirmed the functions/columns were absent and applied `real_kiosk_face_payment` transactionally. Supabase recorded version `20260824013625`; the local migration filename was aligned to that version.

Run: authenticated migration apply using `supabase/migrations/20260824013625_real_kiosk_face_payment.sql`.

Result: hosted migration list contains `20260824013625 real_kiosk_face_payment`.

- [x] **Step 3: Run hosted non-sensitive probes**

Confirmed all five new functions (including `sfg_backend_verify_pin`) exist; `anon/authenticated` are denied and `service_role` is allowed; both legacy one-row writers are denied to `service_role`; no invalid active template exists; wallet invariant violations are zero. The hosted gallery returned one eligible front row, which the configured FastAPI client loaded, decrypted, deserialized, and linked to its profile. PostgreSQL-wrapped Base64 exposed a fail-closed decoder incompatibility; a red regression test reproduced it and the trusted client now removes only CR/LF wrapping before strict decode. A MYR 0.01 matched-gallery-citizen charge validated the wallet and receipt inside an explicit transaction that was rolled back, leaving no balance or transaction change.

- [ ] **Step 4: Re-enrol an active POC citizen and run the physical camera purchase gate**

Use the citizen profile re-enrolment UI to capture a genuinely live front/right/left generation. At the kiosk enter a price, capture the same live person, approve the masked identity, enter that profile's PIN, and verify one purchase transaction and one exact wallet deduction. Do not save a screenshot or camera frame. This step is a human gate; if the person/camera is unavailable, state it as pending and rely only on automated integration evidence.

- [x] **Step 5: Update sources of truth**

`AGENTS.md` and `README.md` must state that main-citizen kiosk identification/payment is real only when the trusted backend and atomic-generation migration are configured; top-up and external settlement remain simulated; Family Member kiosk CV remains unsupported; the `0.40` threshold is a POC application policy pending calibration. Update this changelog entry from `IN PROGRESS` to `COMPLETED` only when code verification passes, and list hosted deployment/human-camera status precisely.

- [x] **Step 6: Final plan self-review and handoff**

Check every user requirement maps to a completed task, scan this plan for placeholder language, verify interface names match implementation, and report exact changed files, test counts, live migration status, and any physical camera gate still pending. Do not commit or push unless the user separately requests it.
