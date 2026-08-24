<!--
  ARCHIVED 2026-08-24: SUPERSEDED, DO NOT USE AS CURRENT DOCUMENTATION.
  See ../README.md in this archive folder for why this file was retired,
  and ../../AGENTS.md + ../../CHANGELOGS.md for the current truth.
-->

# SFG implementation status

## Implemented

- Preserved the existing single-file UI prototype without redesigning or replacing it.
- Added the architecture-prescribed React citizen application with replaceable `mock`, `api`, and live `supabase` service adapters.
- Added exact canonical uppercase status families and snake_case DTO mappings.
- Added a FastAPI service with authentication, enrolment, wallet, transaction, Family Member, profile, kiosk payment, OCR-degradation, and health routes.
- Added server-owned opaque IDs, nonce/session expiry, order checks, PIN attempt limits, cancellation, idempotency, and fail-closed decision handling.
- Added a non-production in-memory repository and byte-discarding biometric simulator for the kiosk payment path and legacy demo routes.
- **Integrated the frozen SFG Shared Biometric Core into the platform.** Citizen registration and personal face re-enrolment now run real YuNet detection, Silent Face passive liveness, and SFace embedding in the trusted tier, keyed to a verified caller identity, returning only canonical statuses.
- Added AES-GCM encrypted template storage with staged captures and an atomic generation swap, so re-enrolment replaces the previous templates in one transaction and an abandoned run changes nothing.
- Applied PostgreSQL/Supabase migrations to the active `Sarawak Facial Gateway (SFG)` project with RLS, protected-table deny-all posture, indexed foreign keys, exact-decimal money, row locks, idempotency, and atomic two-sided transfers.
- Connected registration and IC/password login to Supabase Auth through a rate-limited registration Edge Function. Registration creates an Auth user, profile, and main wallet; dashboard/profile/family/transaction data now load from Supabase.
- Added a responsive top-up dialog with MYR 20/50/100/200/500 presets, custom MYR 1.00–5,000.00 entry, amount/balance review, and matching API/Supabase validation.
- Added mandatory, resumable Family Member face enrolment after profile creation. Front/right/left capture progress is enforced in Supabase before transfers are enabled; the current development adapter stores only position labels/status and no real face image.
- Added a static merchant kiosk client and local run scripts.
- Added frontend contract tests and backend flow/negative-gate tests.

## Explicitly not production-complete

- YuNet, SFace, and Silent-Face now execute for real in enrolment. PaddleOCR is still not installed and `POST /ocr/ic` degrades to `503 ocr_unavailable`.
- Templates are encrypted at rest in a local trusted-tier store, which is a development boundary rather than a deployment target. `public.face_templates` and its pgvector index remain defined but unwritten; the kiosk's 1:N search design is still unresolved.
- 1:N matching, threshold calibration, and the `0.363` versus `0.40` threshold mismatch remain open. Nothing matches yet, so the mismatch is currently inert.
- Family Member enrolment still uses the development capture flow, pending a cross-tier ownership proof.
- Silent Face PAD is prototype passive anti-spoofing: camera- and scene-sensitive, uncalibrated for SFG, with no certification or guarantee.
- The canonical `audit_event_type` value set remains human-approval-blocked. The schema does not accept client-supplied audit text, and the development backend does not pretend an invented enum is canonical.
- The trusted FastAPI/kiosk tier is not yet connected to Supabase because no server-side secret or approved production connection mechanism is configured. No secret or service-role credential is committed.
- No real payment gateway, real money, government identity lookup, document-authenticity verification, refund UI, or production-security claim exists.

## Continuation priorities

1. Continue the in-progress UI screen-by-screen in `web/`, using `SFG Prototype.dc.html` as the current behavior and visual reference.
2. Connect the trusted FastAPI/kiosk tier to Supabase through an approved server-side secret mechanism.
3. Resolve and approve template encryption/search before enabling real biometric persistence.
4. Approve the smallest canonical audit event type set.
5. Install model assets, replace the development biometric adapter, and measure thresholds on approved test data/hardware.
6. Run accessibility, responsive, privacy, security, concurrency, and hardware-camera acceptance checks.

## Verified in this implementation

- `python -m pytest api\tests -q`: 21 tests passed.
- `npm test -- --run`: 2 contract/mapping tests passed.
- `npm run build`: TypeScript and Vite production build passed.
- Live `GET /health`: returned `status: ok` with per-model unavailability and development-simulation limitations disclosed.
- Browser QA at 1440×900 and 390×844: Welcome, Login, Register, Dashboard, responsive navigation, no horizontal overflow, no framework overlay, and no console warnings/errors.
- Live mock top-up interaction updated the displayed balance once.
- Top-up picker QA on desktop, tablet, and phone verified every preset, custom cents, the resulting-balance preview, and responsive layout without submitting a financial action.
- Family Member browser QA on desktop and phone verified profile creation, consent, all three capture positions, completion, and transfer unlock with no framework overlay or new console warnings/errors.
- Live Supabase migration 008 accepted MYR 500 and MYR 123.45 through the amount gate and rejected MYR 0.99; the verification used a missing user and wrote no wallet data.
- Live Supabase migrations 009–010 enforce Family Member ownership and an expiring server-side front/right/left capture gate. Start, insufficient-capture rejection, position recording, completion, and anonymous denial were verified inside rolled-back transactions that left no test data.
- Live Supabase QA: disposable registration created one Auth user, profile, and wallet; IC/password login succeeded; enrolment/PIN/activation completed; duplicate top-up was idempotent; Family Member creation generated its wallet; wallet/history persisted; anonymous and cross-user profile/family/wallet/transaction access were blocked. All disposable QA accounts and cascaded data were deleted after verification.
- Supabase Edge Function logs recorded a successful `201` registration response. Security/performance advisors were run after the migrations; protected no-policy tables are intentionally deny-all, authenticated SECURITY DEFINER RPCs are intentionally exposed with `auth.uid()` ownership/state checks, and new-project unused-index notices are expected until real traffic exists.
