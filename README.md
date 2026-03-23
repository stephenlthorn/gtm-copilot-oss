# GTM Copilot

Open-source GTM copilot for grounded Q&A, call coaching, asset generation, and searchable knowledge.

Built and maintained by Stephen Thorn.

## What it does

- FastAPI backend for RAG chat (`oracle`, `call_assistant`) with citations and follow-up questions.
- Pluggable knowledge ingestion from docs/workspaces and call transcript providers.
- Built-in connectors for:
  - Google Drive (OAuth, permission-inherited per user)
  - Feishu/Lark docs (app token or per-user OAuth)
  - Generic call transcript feed (JSON fixtures or API)
- Vector + keyword hybrid retrieval with metadata filtering.
- Audit logging for sync, chat, generation, and messaging actions.
- Optional Slack command endpoint.
- Next.js admin UI.

## Security posture for OSS

- No secrets are committed; credentials come from environment variables.
- Token storage is encrypted at rest (configurable key).
- Outbound messaging is domain-allowlisted (`INTERNAL_DOMAIN_ALLOWLIST`).
- Prompt/response events are auditable.
- Transcript data is used for retrieval-time context only (no model fine-tuning path).

## Repository layout

```text
/api
  /app
    /api/routes
    /core
    /db
    /ingest
    /models
    /prompts
    /retrieval
    /schemas
    /services
    /utils
  /alembic
/workers
/ui
/infra
/tests
/data
  /fake_drive
  /fake_calls
/scripts
```

## Stack

- Backend: Python 3.11 + FastAPI
- DB: Postgres 16 + pgvector (or MySQL-compatible deployment)
- Jobs: Celery + Redis
- UI: Next.js
- LLM/Embeddings: OpenAI-compatible provider interface

## Quick start (Docker)

1. Create env file:

```bash
cp .env.example .env
```

2. Start services:

```bash
cd infra
docker compose up --build
```

3. Trigger initial sync:

```bash
curl -X POST "http://localhost:8000/admin/sync/drive"
curl -X POST "http://localhost:8000/admin/sync/calls"
```

4. Open:

- API docs: <http://localhost:8000/docs>
- UI: <http://localhost:3000>

## Local development

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload
```

Optional worker shell:

```bash
cd api
celery -A app.worker.celery_app worker --loglevel=info
celery -A app.worker.celery_app beat --loglevel=info
```

## Connector model (extensible)

This repo is intentionally connector-friendly:

- `api/app/ingest/drive_connector.py`: document workspace ingestion
- `api/app/ingest/feishu_connector.py`: Feishu/Lark adapter
- `api/app/ingest/`: call transcript adapter interface + normalization pipeline

To add a source, implement a new connector + ingestor pair that outputs normalized documents/transcripts and writes `kb_documents` + `kb_chunks`.

## Environment config

See `.env.example` for full variables.

Core sections:

- DB/Redis
- LLM/embedding provider
- Google Drive OAuth
- Feishu/Lark OAuth
- Call transcript API
- Messaging + Slack
- Security controls

## API examples

Ask Oracle:

```bash
curl -X POST "http://localhost:8000/chat" \
  -H 'Content-Type: application/json' \
  -d '{
    "mode": "oracle",
    "user": "rep@example.com",
    "message": "What are the top risks in this opportunity?",
    "top_k": 8
  }'
```

Sync calls:

```bash
curl -X POST "http://localhost:8000/admin/sync/calls"
```

No demo transcripts or documents are bundled. Use `data/fake_drive` and `data/fake_calls` only for local, non-sensitive fixtures.

## Account Deal Memory

Rolling per-account MEDDPICC state that aggregates all calls (Chorus + manual) and keeps building after every interaction.

**How it works:**

After each call sync or manual call log, a background pipeline extracts a MEDDPICC delta using the LLM and writes it to `pending_delta`. The rep sees a yellow review banner, can expand the diff, approve (with optional edits), or dismiss. Approved deltas merge into the live account state. Every post-call analysis automatically receives the full account history as context.

**Features:**
- Auto-detects new business vs. existing (Chorus stage → prior call history → manual override)
- LLM-extracts MEDDPICC delta (scores 1–5 with evidence + missing) after every call
- Pending-review banner: rep approves, edits, or dismisses proposed changes before they land
- Manual call logging — paste notes, transcript, or voice memo; AI extracts MEDDPICC automatically
- Full account history (MEDDPICC scores, contacts, tech stack, open items, summary) injected into post-call and follow-up analysis prompts
- Direct rep override via PATCH for any field

**Endpoints:**
```
POST   /calls/manual                          Log a call not recorded in Chorus
GET    /accounts/{account}/memory             Current deal state
POST   /accounts/{account}/memory/approve     Approve AI-proposed update (optional edits)
POST   /accounts/{account}/memory/dismiss     Dismiss without applying
PATCH  /accounts/{account}/memory             Direct rep edit
```

**UI:** `/accounts` page — MEDDPICC scorecard with evidence, key contacts, open items, call history. "Log call manually" button in Settings → Knowledge Sources.

**Schema (account_deal_memory):**
- `account` (PK, VARCHAR 255, canonicalized lowercase)
- `meddpicc` JSON — one entry per element: `{score, evidence, missing}`
- `key_contacts` JSON array — `{name, title, role, linkedin}`
- `tech_stack` JSON — `{confirmed, likely, possible, unknown}` lists
- `open_items` JSON array — `{item, owner, due_date, priority}`
- `pending_delta` JSON — AI-proposed update awaiting rep review
- `pending_review` BOOL — true when a delta is waiting
- `call_count`, `last_call_date`, `deal_stage`, `is_new_business`, `status`
