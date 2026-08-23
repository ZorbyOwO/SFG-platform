# SFG implementation status

## Implemented

- Preserved the existing single-file UI prototype without redesigning or replacing it.
- Added the architecture-prescribed React citizen application with replaceable `mock` and `api` service adapters.
- Added exact canonical uppercase status families and snake_case DTO mappings.
- Added a FastAPI service with authentication, enrolment, wallet, transaction, Family Member, profile, kiosk payment, OCR-degradation, and health routes.
- Added server-owned opaque IDs, nonce/session expiry, order checks, PIN attempt limits, cancellation, idempotency, and fail-closed decision handling.
- Added a non-production in-memory repository and byte-discarding biometric simulator for local development and automated tests.
- Added PostgreSQL/Supabase migrations with RLS, protected-table deny-all posture, indexed foreign keys, exact-decimal money, row locks, idempotency, and atomic two-sided transfers.
- Added a static merchant kiosk client and local run scripts.
- Added frontend contract tests and backend flow/negative-gate tests.

## Explicitly not production-complete

- Real YuNet, SFace, Silent-Face, and PaddleOCR execution requires approved model assets and runtime validation. Missing OCR degrades to `503 ocr_unavailable`.
- Encrypted facial-template persistence conflicts with searchable pgvector embeddings in architecture v0.3. `TemplateRepository` keeps that decision isolated; the development adapter stores no actual biometric template.
- The canonical `audit_event_type` value set remains human-approval-blocked. The schema does not accept client-supplied audit text, and the development backend does not pretend an invented enum is canonical.
- Supabase Auth/service-role integration requires approved credentials and a selected connection method. No secret or credential is committed.
- No real payment gateway, real money, government identity lookup, document-authenticity verification, refund UI, or production-security claim exists.

## Continuation priorities

1. Continue the in-progress UI screen-by-screen in `web/`, using `SFG Prototype.dc.html` as the current behavior and visual reference.
2. Apply and validate migrations in a non-production Supabase project.
3. Implement the production repository/Auth adapter behind the current interfaces.
4. Resolve and approve template encryption/search before enabling real biometric persistence.
5. Approve the smallest canonical audit event type set.
6. Install model assets, replace the development biometric adapter, and measure thresholds on approved test data/hardware.
7. Run accessibility, responsive, privacy, security, concurrency, and hardware-camera acceptance checks.

## Verified in this implementation

- `python -m pytest api\tests -q`: 20 tests passed.
- `npm test -- --run`: 2 contract/mapping tests passed.
- `npm run build`: TypeScript and Vite production build passed.
- Live `GET /health`: returned `status: ok` with per-model unavailability and development-simulation limitations disclosed.
- Browser QA at 1440×900 and 390×844: Welcome, Login, Register, Dashboard, responsive navigation, no horizontal overflow, no framework overlay, and no console warnings/errors.
- Live mock top-up interaction updated the displayed balance once.
