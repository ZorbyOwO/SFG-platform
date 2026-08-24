# Sarawak Facial Gateway

This repository contains the architecture v0.3 implementation and integrated
development system: `web/`, `api/`, `db/`, `kiosk/`, and `scripts/`.

The retired single-file UI prototype and superseded early documents are kept in
`archive/`, clearly labeled. They are history only; do not use them to understand
current behavior.

The active profile is the payment/wallet prototype. It uses face matching to identify and the main account holder's six-digit PIN to authorize. It never maps payment success to `SERVICE_ACCESS_GRANTED`.

## Current implementation boundary

The React citizen app is connected to the active `Sarawak Facial Gateway (SFG)` Supabase project. Supabase Auth owns password hashes and sessions; registered profile, wallet, Family Member, and transaction data persist in PostgreSQL under RLS. IC numbers are login identifiers only and are not checked against a government system.

**Face recognition is real for citizen enrolment and main-citizen kiosk identification.** Registration, personal face re-enrolment, and the kiosk capture live camera frames and process them in the trusted FastAPI tier with the frozen SFG Shared Biometric Core in `biometric/`: YuNet detection, Silent Face passive liveness, and SFace embedding. Accepted enrolment captures become AES-GCM-sealed private templates. Kiosk identification decrypts eligible front templates only inside the trusted tier, runs the mother's protected linear 1:N policy, proposes one masked identity, requires an explicit Yes, then verifies that Supabase profile's six-digit PIN before invoking an idempotent server-side Supabase wallet deduction. A frame is decoded, processed, and discarded inside one request; no image is written to disk, browser storage, or a log, and no template, embedding, or score is ever returned to a browser or kiosk.

Only a genuinely live person passes the liveness check. Photos, screens, and rendered images are refused by design.

The real kiosk path requires `db/migrations/014_real_kiosk_face_payment.sql` (hosted copy `supabase/migrations/20260824013625_real_kiosk_face_payment.sql`), the trusted service credential, an active kiosk, and a citizen with a current three-pose generation. Migration `014` is applied to the active Supabase project, and the trusted gallery/profile/decryption probes currently pass for one eligible generation. It fails closed with `real_kiosk_unavailable` when any hosted dependency is absent or malformed. Still simulated or incomplete: external bank/card settlement, top-ups, Family Member face capture/identification, and document OCR. No government identity system is connected, and no accuracy, FAR, FRR, PAD, or certification claim is made. The kiosk uses the explicit POC application threshold `0.40`; target-hardware calibration remains required.

## Prerequisites

- Node.js 22+
- Python 3.13+
- About 300 MB of disk for the face recognition runtime and pinned models, downloaded on first run
- Access to the configured Supabase project when testing persistent citizen data

## Run the complete system

On Windows, double-click `run-sfg.cmd`, or run this one command from the repository root:

```powershell
.\run-sfg.cmd
```

On macOS or Linux, run:

```bash
python3 scripts/run_dev.py
```

The launcher automatically creates the Python environment, installs missing backend and frontend dependencies, installs the face recognition runtime, downloads and hash-verifies the four commit-pinned biometric models, generates the local secrets, starts all three services, and opens the citizen app. First-time setup downloads roughly 300 MB and may take several minutes; later starts are fast. Press `Ctrl+C` once in the launcher window to stop everything.

- Citizen app: `http://127.0.0.1:5500`
- Merchant kiosk: `http://127.0.0.1:5501`
- API documentation: `http://127.0.0.1:8000/docs`
- API health: `http://127.0.0.1:8000/health`

The launcher connects the citizen app and trusted FastAPI tier to the active Supabase project when the required server-only configuration exists. Registration profiles, authenticated sessions, wallets, Family Members, sealed citizen face generations, and transaction records persist across restarts. A Family Member must record front, right, and left development-capture positions before their profile becomes active and transfers are enabled. IC numbers are mock POC login identifiers and are not government-verified; no face image is stored and top-ups do not connect to a bank or card. The in-memory biometric simulator is now restricted to explicit automated test scenarios and is not requested by the kiosk UI.

The generated development kiosk key is written to the git-ignored `api/.runtime/kiosk.key`; enter it into the kiosk setup field. Do not paste that value into source, documentation, screenshots, chat, or Git. The launcher creates the git-ignored `web/.env.local` from `web/.env.example` when needed. The checked-in Supabase value is a browser-safe publishable key; never place a secret or service-role key in a `VITE_` variable.

Optional launcher commands:

```powershell
# Prepare dependencies without starting the services
python scripts\run_dev.py --setup-only

# Start without opening a browser tab
python scripts\run_dev.py --no-open
```

## Test and build

```powershell
python -m pytest api\tests -q
.\.venv\Scripts\python.exe scripts\verify_biometric.py
Set-Location web
npm test -- --run
npm run build
```

`scripts/verify_biometric.py` checks that the vendored core still matches its frozen baseline, that the v1.2 contract and the four pinned model payloads are intact, and that the runtime compatibility fingerprint is unchanged. Run it after touching anything under `biometric/` or the pins in `api/requirements-biometric.txt`; a changed OpenCV runtime invalidates every stored template.

## Database

Apply migrations in filename order:

```text
db/migrations/001_extensions.sql
db/migrations/002_tables.sql
db/migrations/003_rls.sql
db/migrations/004_functions.sql
db/migrations/005_seed_kiosks.sql
db/migrations/006_supabase_auth_client.sql
db/migrations/007_advisor_hardening.sql
db/migrations/008_flexible_topup_amounts.sql
db/migrations/009_family_member_face_enrolment.sql
db/migrations/010_enforce_family_capture_positions.sql
db/migrations/011_profile_security_actions.sql
db/migrations/012_sfg_backend_complete_reenrolment.sql
db/migrations/013_fix_first_time_pin_chain.sql
db/migrations/014_real_kiosk_face_payment.sql
```

Migration `014` replaces all front/right/left sealed bundles as one atomic generation, adds the trusted front-template gallery and matched-profile lookup/PIN/charge RPCs, and disables the old service-role one-row replacement path. It was applied to the hosted project as version `20260824013625`; citizens with only legacy templates must complete one three-pose personal re-enrolment before kiosk identification can match them.

After any wallet operation, `db/invariant_check.sql` must return zero rows.

## Handoff package

Give the next developer or coding agent all of the following together:

1. This complete Git repository, including any uncommitted work.
2. `AGENTS.md` and `CHANGELOGS.md` as the current operating guide and timeline.
3. This README.
4. The package manager and commands above.
5. Credentials only through approved local secret files or a secret manager; never through prompts, fixtures, documentation, screenshots, or Git.

`archive/` holds superseded documents and the retired prototype; consult it only for historical design intent.
