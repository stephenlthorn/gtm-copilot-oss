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

Synthetic demo data is included in `data/fake_drive` and `data/fake_calls`.
