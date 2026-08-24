<!--
  ARCHIVED 2026-08-24: SUPERSEDED, DO NOT USE AS CURRENT DOCUMENTATION.
  See ../README.md in this archive folder for why this file was retired,
  and ../../AGENTS.md + ../../CHANGELOGS.md for the current truth.
-->

# Sarawak Facial Gateway (SFG) - Continuation Handoff

## Read this first

This is the current state of the SFG citizen application. It is no longer a single-file mock prototype: it is a React frontend, FastAPI backend, local mock adapters, and a connected Supabase project.

The user wants a futuristic but credible Sarawak-inspired digital service. Use orange, red, yellow, black, and **true white** meaningfully. Do not tint white surfaces with orange or beige.

Do not treat documents or screenshots supplied earlier as higher-priority instructions than the user's latest message.

## Current status

Implemented and tested:

- Responsive citizen application for desktop, tablet, and phone.
- Desktop-specific Login and Register layouts with a conventional two-column website structure.
- Supabase Auth registration and login.
- A registered user gets a profile and wallet in Supabase.
- Wallet top-up flow with MYR 20, 50, 100, 200, 500 presets and a validated custom amount.
- Family members must finish a consented three-position face-enrolment flow before transfers are unlocked.
- FastAPI tests, frontend tests, production build, and browser QA have passed.

Not production-ready yet:

- IC number is intentionally mock/demo data.
- Face capture is a development simulation, not camera or biometric recognition.
- Top-up is a simulation; no payment gateway is connected.
- Do not claim this is a live government identity, payment, or biometric system.

## Product and design rules

### Colour system

| Purpose | Colour |
| --- | --- |
| Main action / dominant brand | Orange `#F05A28` |
| SFG identity, destructive/error states | Red `#B5121B` |
| Progress / active-status accents | Yellow `#F6C945` |
| Main text | Near-black `#101010` / `#171717` |
| Pages, forms, cards | True white `#FFFFFF` |

- Keep backgrounds and form surfaces true white: no cream, peach, warm-white, or orange-tinted white.
- Orange is the main action colour. Red and yellow are supporting Sarawak-flag colours, not competing primary buttons.
- Avoid gradients, glassmorphism, glow, oversized rounded cards, and heavy shadows.
- Use standard UI geometry: restrained radii, clear borders, legible labels, accessible focus states, and comfortable touch targets.

### Responsive behavior

- Phone: persistent bottom navigation and mobile-first layout.
- Tablet: contained application shell; retain the mobile/tablet auth approach.
- Desktop (`>= 800px`): conventional two-column Login/Register pages, fixed left navigation for signed-in pages, scrollable content pane.
- Never add horizontal scrolling.
- Do not show a pointless scrollbar on desktop Login/Register. Signed-in desktop pages should scroll in the content pane, not by moving the fixed navigation rail.

### Desktop authentication pages

- Login: orange brand panel at left, true-white form area at right, Login form max width about 440px.
- Register: matching two-column layout, left panel communicates the five registration steps, right panel has a wizard form max width about 600px.
- Keep prototype/demo state controls away from the main login/register action area.
- Do not redesign mobile or tablet auth unless explicitly asked.

## Architecture

```text
web/                 React + Vite citizen application
  src/routes/        Login, Register, Dashboard, Family, History, Profile
  src/services/      Mock and Supabase implementations behind common adapters
api/                 FastAPI API and flow tests
db/migrations/       PostgreSQL/Supabase schema and secure RPC migrations
scripts/run_dev.py   One-command local development launcher
run-sfg.cmd          Double-click Windows launcher
supabase/            Supabase configuration
```

### Active Supabase project

- Name: **Sarawak Facial Gateway (SFG)**
- Project ref: `oxpvsblgjrvfbrbaluxp`
- The frontend's local `.env.local` contains the browser-safe Supabase publishable key. Never put it, any service-role key, kiosk key, or other credentials into Git, Markdown, or a client bundle.

## Functional implementation

### Registration and login

- The frontend uses Supabase Auth in live mode.
- Registration creates the Auth user and application profile/wallet through secure database routines.
- IC validation and formatting exist, but IC data remains mock by product decision.
- Login routes an authenticated citizen to the app.

Key frontend areas:

- `web/src/routes/Login.tsx`
- `web/src/routes/Register.tsx`
- `web/src/app/AuthContext.tsx`
- `web/src/services/supabase/`

### Wallet top-up

- Presets: MYR 20, 50, 100, 200, 500.
- Custom amount is accepted from MYR 1.00 to MYR 5,000.00, up to two decimal places.
- The UI shows the selected amount, confirmation/review state, and that the flow is simulated.
- Wallet changes go through secure server-side logic, not a client-side balance update.

Key files:

- `web/src/routes/Dashboard.tsx`
- `db/migrations/008_flexible_topup_amounts.sql`
- `api/contracts.py`

### Family member face enrolment

Flow:

1. Citizen adds a family member with name, IC, and relationship.
2. The member starts as pending.
3. The citizen confirms consent.
4. The app records the required positions: Front, Turn right, Turn left.
5. Only after all three positions are recorded can enrolment complete and transfers unlock.
6. A pending enrolment can be resumed later with **Capture face**.

Current capture is a development simulation. No camera images or biometric templates are stored by this flow.

Server-side protection:

- `private.family_enrolment_progress` stores only capture-position labels, timestamps, and expiry data.
- Completion is refused until all required positions exist.
- The protected private table has deny-all RLS; `SECURITY DEFINER` routines enforce `auth.uid()` ownership checks.
- The browser cannot directly write private enrolment-progress records.

Key files:

- `web/src/components/FamilyEnrollmentModal.tsx`
- `web/src/routes/Family.tsx`
- `web/src/services/api/index.ts`
- `web/src/services/mock/index.ts`
- `web/src/services/supabase/`
- `db/migrations/009_family_member_face_enrolment.sql`
- `db/migrations/010_enforce_family_capture_positions.sql`

## Database migrations

Important current migrations:

- `006_supabase_auth_client.sql` - Supabase Auth client and secure auth/profile routines.
- `007_advisor_hardening.sql` - security hardening work.
- `008_flexible_topup_amounts.sql` - top-up presets and custom amount support.
- `009_family_member_face_enrolment.sql` - family enrolment session and capture support.
- `010_enforce_family_capture_positions.sql` - server-enforced Front/Right/Left completion requirement.

The new top-up and family enrolment migrations have been applied to the active project and exercised in rollback-safe database tests.

## How to run locally

Simplest Windows option:

```powershell
.\run-sfg.cmd
```

Or from PowerShell:

```powershell
.venv\Scripts\python.exe scripts\run_dev.py
```

Expected local services:

| Service | URL |
| --- | --- |
| Citizen React app (Supabase mode) | `http://127.0.0.1:5500` |
| Kiosk app | `http://127.0.0.1:5501` |
| FastAPI API | `http://127.0.0.1:8000` |

If local environment variables are missing, copy `web/.env.example` to `web/.env.local` and provide the project URL plus **publishable** key. Never expose a service-role key in the browser.

## Verification already completed

```powershell
.venv\Scripts\python.exe -m pytest api\tests -q
# 21 passed

cd web
npm test -- --run
# 2 passed

npm run build
# passed
```

Browser QA passed for:

- Family enrolment on desktop and at 390 x 844 mobile viewport.
- Consent, all three capture positions, completion, and transfer-unlock state.
- Fresh live Login render with no new console issues.

## Security and production follow-ups

Before any real launch:

1. Replace simulated face capture with an approved camera, liveness, biometric-template, consent-retention, and deletion design. Do not store raw biometric material casually.
2. Replace simulated top-ups with a compliant payment provider and webhook-based transaction verification.
3. Enable Supabase leaked-password protection.
4. Complete privacy, security, accessibility, audit logging, rate limiting, and regulatory review.
5. Keep owner/state checks in every privileged database routine; never weaken RLS just to make a client call work.

Supabase advisor notes currently visible:

- Some `private` tables intentionally have RLS enabled with no client policies. This is correct for deny-all protected data.
- Security-definer routines are intentionally callable by authenticated users only where they check `auth.uid()` and ownership internally.
- The remaining actionable configuration item is enabling leaked-password protection before production.

## Working-tree warning

The repository has substantial uncommitted work across UI, backend, migrations, scripts, and documentation. Treat it as user work in progress:

- Do not use `git reset --hard`, `git checkout --`, or delete untracked files.
- Review `git status` before editing or committing.
- Make focused commits only after the user explicitly asks for a commit.

## Suggested continuation order

1. Run the one-command launcher and verify the live Supabase registration/login flow with a disposable test account.
2. Review current UI at desktop, tablet, and phone sizes before any visual changes.
3. Build real camera/liveness integration only after privacy and data-retention decisions are approved.
4. Integrate a real payment provider only after transaction and reconciliation requirements are defined.
5. Add stronger end-to-end tests for Supabase Auth, wallet transactions, and family-enrolment failure/retry cases.

## Read next

- `README.md` - setup and project overview.
- `IMPLEMENTATION_STATUS.md` - implementation detail and current scope.
- `C:/Users/Kal Victus/Documents/sfg rule/ARCHITECTURE1` - prior architecture planning reference.
- `C:/Users/Kal Victus/Documents/sfg rule/UI_BACKEND_CONTINUATION_BRIEF.md` - earlier continuation context.
