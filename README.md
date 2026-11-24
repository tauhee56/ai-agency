# Autonomous AI Company OS

Monorepo for the company OS platform (Phases 1–6 on this VM; OpenHands/MetaGPT partial).

```
apps/
  api/                      FastAPI platform (no MetaGPT/CrewAI/OpenHands imports)
  web/                      Next.js dark enterprise dashboard
  workers/crewai_adapter/   Separate CrewAI protocol worker
  workers/openhands_adapter Stub/OpenHands worker (Docker blocked here)
  workers/metagpt_adapter/  Optional Py3.11 worker (disabled)
```

## Prerequisites

- Node.js 20+
- Python 3.12+
- PostgreSQL 16
- Redis 7
- Docker (optional, for `docker compose`)

## Quick start (local processes)

### 1. Database & Redis

```bash
# create role/db (example)
createuser aicos -P   # password: aicos
createdb aicos -O aicos
psql -d aicos -c "CREATE EXTENSION IF NOT EXISTS citext;"

redis-server --daemonize yes
```

Or use Compose infra only:

```bash
docker compose up -d postgres redis
```

### 2. API

```bash
cp .env.example .env
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export $(grep -v '^#' ../../.env | xargs)
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

### 3. Web

```bash
cd apps/web
cp ../../.env.example .env.local   # or set NEXT_PUBLIC_* vars
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 NEXT_PUBLIC_WS_URL=ws://localhost:8000 npm run dev
```

UI: http://localhost:3000

## Docker Compose (full stack)

```bash
cp .env.example .env
docker compose up --build
```

- Web: http://localhost:3000  
- API: http://localhost:8000  

## Phase 1 verification

1. Open http://localhost:3000 → **Create company** (signup).
2. Confirm Overview shows company name + DB/Redis chips.
3. **Settings → Models**: add a provider (API key optional). Without a key, CEO returns an offline structured stub.
4. On Overview, ask the **AI CEO** — expect acknowledgment + plan JSON.
5. Confirm **Live activity** WebSocket receives `ceo.advised` / `model.created`.
6. Restart API + reload UI — company/models still present.
7. Invalid/live model key → clear error string (no stack trace in UI).

## Security notes

- Model API keys are Fernet-encrypted with `ENCRYPTION_KEY` (never hardcoded).
- JWT auth via `JWT_SECRET`.
- No MetaGPT / CrewAI / OpenHands packages in `apps/api/requirements.txt`.

## Workers

```bash
# CrewAI adapter (mock by default)
REDIS_URL=redis://localhost:6379/0 CREWAI_FORCE_MOCK=1 OTEL_SDK_DISABLED=true \
  python apps/workers/crewai_adapter/worker.py

# OpenHands stub (Docker not required)
REDIS_URL=redis://localhost:6379/0 OPENHANDS_STUB=1 \
  python apps/workers/openhands_adapter/worker.py
```

## Phase docs

Ship notes live under the Project store: `docs/ai-company-os/PHASE{1-6}_SHIPPED.md`.

## Licenses

See `NOTICE` and `THIRD_PARTY_LICENSES.md`.
