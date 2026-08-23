# Sarawak Facial Gateway

This repository now contains two deliberately separate layers:

- `SFG Prototype.dc.html` is the preserved UI/UX prototype already under development.
- `web/`, `api/`, `db/`, `kiosk/`, and `scripts/` are the architecture v0.3 implementation scaffold and integrated development system.

The active profile is the payment/wallet prototype. It uses face matching to identify and the main account holder's six-digit PIN to authorize. It never maps payment success to `SERVICE_ACCESS_GRANTED`.

## Current implementation boundary

The React citizen app and the FastAPI development backend are runnable without Supabase credentials. The backend development repository is in-memory and resets when the process restarts. It exists for contract and flow integration only; it does not claim real biometric, identity, banking, or payment processing.

The PostgreSQL/Supabase schema, RLS policies, and atomic wallet functions are in `db/`. Applying them to a real project requires an approved `DATABASE_URL`/secret mechanism. Real biometric matching also remains blocked until model assets are installed and the architecture's encrypted-template versus pgvector-search conflict is approved. The development biometric adapter discards uploaded bytes and stores no face frame or embedding.

## Prerequisites

- Node.js 22+
- Python 3.13+
- PostgreSQL/Supabase only when testing the database migrations

## First run

Create a Python environment and install the backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r api\requirements.txt
Copy-Item api\.env.example api\.env
python scripts\create_dev_secrets.py
python -m uvicorn api.main:app --reload --port 8000
```

In another terminal, start the React citizen app:

```powershell
Set-Location web
npm install
npm run dev
```

The default frontend mode is `mock`. To use the FastAPI adapter, create `web/.env.local` with:

```text
VITE_DATA_MODE=api
VITE_API_BASE_URL=http://localhost:8000
```

Start the merchant kiosk in a third terminal:

```powershell
python -m http.server 5501 -d kiosk
```

Open `http://localhost:5500` for the citizen app and `http://localhost:5501` for the kiosk. The generated development kiosk key is written to the git-ignored `api/.runtime/kiosk.key`; enter it into the kiosk setup field. Do not paste that value into source, documentation, screenshots, chat, or Git.

## Test and build

```powershell
python -m pytest api\tests -q
Set-Location web
npm test -- --run
npm run build
```

## Database

Apply migrations in filename order:

```text
db/migrations/001_extensions.sql
db/migrations/002_tables.sql
db/migrations/003_rls.sql
db/migrations/004_functions.sql
db/migrations/005_seed_kiosks.sql
```

After any wallet operation, `db/invariant_check.sql` must return zero rows.

## Handoff package

Give the next developer or coding agent all of the following together:

1. This complete Git repository, including the preserved prototype and any uncommitted UI work.
2. `ARCHITECTURE1` as architecture v0.3 and `UI_BACKEND_CONTINUATION_BRIEF.md` from the adjacent `sfg rule` folder.
3. This README and `IMPLEMENTATION_STATUS.md`.
4. The package manager and commands above.
5. Credentials only through approved local secret files or a secret manager; never through prompts, fixtures, documentation, screenshots, or Git.

See `IMPLEMENTATION_STATUS.md` for completed areas, verified commands, and unresolved architecture decisions.
