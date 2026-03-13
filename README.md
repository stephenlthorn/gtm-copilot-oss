# GTM Copilot — AI-Powered GTM Platform for TiDB

GTM Copilot is an AI-powered go-to-market platform built for TiDB's sales, marketing, and SE teams. It automates pre-call research, post-call follow-ups, competitive intelligence, and RAG-grounded chat — all grounded in company knowledge indexed from Google Drive, Feishu, TiDB docs, and TiDB GitHub. Users get role-specific dashboards (Sales Rep, Marketing, SE) backed by a shared account context, with AI that adapts over time through user feedback.

Built and maintained by Stephen Thorn.

---

## Architecture

[View interactive diagram](./docs/architecture.excalidraw)

```
┌─────────────────────────────────────────────────────┐
│                   Next.js Frontend                   │
│  (Sales Dashboard | Marketing Dashboard | SE Dashboard) │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                 FastAPI Backend                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │ Chat/RAG │ │ Research  │ │ Dashboard Services   │ │
│  │ Service  │ │ Pipeline  │ │ (Sales/Mktg/SE)      │ │
│  └──────────┘ └──────────┘ └──────────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────────┐ │
│  │ Auth     │ │ Source   │ │ Notification Service │ │
│  │ Service  │ │ Registry │ │ (Slack/Email)        │ │
│  └──────────┘ └──────────┘ └──────────────────────┘ │
└──────┬───────────┬───────────────┬──────────────────┘
       │           │               │
┌──────▼──┐ ┌──────▼─────┐ ┌──────▼──────────────────┐
│  TiDB   │ │  Celery +  │ │  External APIs          │
│  Cloud  │ │  Redis     │ │  (OpenAI, Firecrawl,    │
│         │ │  (Jobs)    │ │   Chorus, ZoomInfo,     │
│         │ │            │ │   Salesforce, etc.)     │
└─────────┘ └────────────┘ └─────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 / React 18 |
| Backend | Python 3.11 / FastAPI |
| Database | TiDB Cloud (vector search + full-text + relational) |
| Background Jobs | Celery + Redis |
| LLM | OpenAI (user-provided API key, extensible) |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dimensions) |
| Web Scraping | Firecrawl API |
| Containerization | Docker Compose |

---

## Quick Start

```bash
cp .env.example .env
# Fill in required keys (see Configuration section below)
docker compose -f infra/docker-compose.yml up -d
# Frontend: http://localhost:3000
# API docs: http://localhost:8000/docs
```

Trigger initial knowledge sync:

```bash
curl -X POST "http://localhost:8000/admin/sync/drive"
curl -X POST "http://localhost:8000/admin/sync/calls"
```

---

## Configuration

Copy `.env.example` to `.env` and fill in the values below.

### Core

| Variable | Description |
|---|---|
| `APP_ENV` | Environment (`dev` / `prod`) |
| `APP_PORT` | API port (default `8000`) |
| `CORS_ALLOW_ORIGINS` | Comma-separated allowed origins for CORS |

### Database

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (local dev fallback) |
| `DATABASE_PROVIDER` | `postgresql` or `tidb` |
| `TIDB_HOST` | TiDB Cloud host |
| `TIDB_PORT` | TiDB Cloud port (default `4000`) |
| `TIDB_USER` | TiDB Cloud username |
| `TIDB_PASSWORD` | TiDB Cloud password |
| `TIDB_DATABASE` | TiDB Cloud database name |
| `TIDB_SSL_CA` | Path to TiDB Cloud CA certificate |
| `REDIS_URL` | Redis connection string |

### LLM / Embeddings

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_BASE_URL` | Optional custom endpoint (Azure, self-hosted) |
| `OPENAI_MODEL` | Chat model (default `gpt-4.1`) |
| `OPENAI_EMBEDDING_MODEL` | Embedding model (default `text-embedding-3-small`) |
| `EMBEDDING_DIMENSIONS` | Embedding vector size (default `1536`) |
| `RETRIEVAL_TOP_K` | Number of chunks to retrieve per query (default `8`) |

### Security

| Variable | Description |
|---|---|
| `ENTERPRISE_MODE` | Enable enterprise security controls |
| `SECURITY_REQUIRE_PRIVATE_LLM_ENDPOINT` | Require non-public LLM base URL |
| `SECURITY_ALLOWED_LLM_BASE_URLS` | Allowlist of permitted LLM endpoints |
| `SECURITY_REDACT_BEFORE_LLM` | Redact PII before sending to LLM |
| `SECURITY_REDACT_AUDIT_LOGS` | Redact sensitive data in audit logs |
| `SECURITY_TRUSTED_HOST_ALLOWLIST` | Comma-separated trusted host headers |
| `INTERNAL_DOMAIN_ALLOWLIST` | Domains permitted for outbound messaging |

### Google Drive

| Variable | Description |
|---|---|
| `GOOGLE_DRIVE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_DRIVE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON` | Path to service account JSON (optional) |
| `GOOGLE_DRIVE_TOKEN_ENCRYPTION_KEY` | AES key for encrypting stored OAuth tokens |
| `GOOGLE_DRIVE_ROOT_FOLDER_ID` | Root folder to sync (optional) |
| `GOOGLE_DRIVE_FOLDER_IDS` | Comma-separated folder IDs to index |

### Feishu / Lark

| Variable | Description |
|---|---|
| `FEISHU_APP_ID` | Feishu app ID |
| `FEISHU_APP_SECRET` | Feishu app secret |
| `FEISHU_BASE_URL` | Feishu API base URL |

### Call Transcripts

| Variable | Description |
|---|---|
| `CALL_PROVIDER` | Provider name (`generic`, or Chorus-compatible) |
| `CALL_API_KEY` | API key for call transcript provider |
| `CALL_BASE_URL` | Base URL for call transcript provider |

### Messaging

| Variable | Description |
|---|---|
| `EMAIL_MODE` | `draft` (compose only) or `send` |
| `SMTP_HOST` | SMTP server hostname |
| `SMTP_PORT` | SMTP port (default `587`) |
| `SMTP_USERNAME` | SMTP username |
| `SMTP_FROM` | From address for outbound email |
| `SLACK_BOT_TOKEN` | Slack bot OAuth token |
| `SLACK_SIGNING_SECRET` | Slack signing secret for webhook verification |
| `SLACK_DEFAULT_CHANNEL` | Default channel for notifications |

---

## Features by Role

All users can access all dashboards. Role determines default landing page.

### Sales Rep
- Pre-call hub: upcoming meetings with auto-generated research status
- 7-section pre-call reports (prospect info, company context, architecture hypothesis, pain hypothesis, TiDB value props, meeting goal, meeting flow)
- Manual research trigger: enter a company name, verify, research
- Post-call hub: "What we heard / What it means / Next steps" + draft follow-up email
- Call coaching: AI reviews past calls for patterns and objection handling
- Deal health scoring, pipeline analytics, win/loss analysis
- Account 360: unified view of all research, calls, emails, deal history

### Marketing
- Competitive intelligence: auto-monitored competitor landscape (news, launches, pricing, G2 reviews)
- Battle card generator (auto-created and updated)
- Content engine: blog drafts, case studies, email campaigns, one-pagers
- Content gap analysis from rep questions with no matching content
- Market research: industry trends, ICP refinement

### SE
- Extended architecture analysis per prospect
- Tech stack mapping (BuiltWith, job posts, GitHub signals)
- Demo and POC prep scripts matched to prospect pain
- Technical objection handling with linked TiDB docs and GitHub issues
- POC status tracker with shared context to sales rep

### Admin
- User management: invite users, assign roles
- Source registry: add/remove/configure global research sources
- API key management: Firecrawl, ZoomInfo, BuiltWith, etc.
- Sync health: Drive, Feishu, Chorus, Salesforce status
- AI coaching panel: view all refinements across all users, promote to team, edit, disable, track effectiveness
- MCP server configuration: enable/disable per server, configure API keys
- API cost tracking: daily/weekly/monthly spend per external source

---

## MCP Integrations

MCP servers give the LLM direct tool access to live data during chat. Each enabled server registers its tools at startup; the LLM autonomously decides which to invoke based on the user's query.

| MCP Server | Purpose | Primary Users |
|---|---|---|
| TiDB Cloud MCP | Query accounts, deals, research reports, call history | All |
| TiDB Observability MCP | Cluster health, query performance, metrics | SE |
| Salesforce MCP | Live CRM pipeline, deals, contacts | Sales |
| Slack MCP | Search conversations, post messages | All |
| Google Drive MCP | Search and retrieve documents | All |
| Feishu MCP | Search and retrieve Feishu docs | All |
| Gmail MCP (read-only) | Search emails for context | Sales, SE |
| Google Calendar MCP (read-only) | Check schedules and meetings | Sales |
| ZoomInfo MCP | Live prospect and company lookup | Sales, Marketing |
| LinkedIn Sales Nav MCP | Prospect research, org mapping | Sales |
| Firecrawl MCP | On-demand web scraping in chat | All |
| GitHub MCP | TiDB repo search for technical depth | SE |
| Crunchbase MCP | Funding and growth signals | Sales, Marketing |

---

## Development

### Run API locally

```bash
cd api
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

### Run Celery worker and scheduler

```bash
cd api
celery -A app.worker.celery_app worker --loglevel=info
celery -A app.worker.celery_app beat --loglevel=info
```

### Run UI locally

```bash
cd ui
npm install
npm run dev
# http://localhost:3000
```

### Repository layout

```
/api
  /app
    /api/routes        # FastAPI route handlers
    /core              # Config, auth, security
    /db                # Database models and migrations
    /ingest            # Knowledge source connectors
    /models            # ORM models
    /prompts           # LLM prompt templates
    /retrieval         # Hybrid search service
    /schemas           # Pydantic request/response schemas
    /services          # Business logic (research, chat, notifications)
    /utils             # Shared utilities
  /alembic             # Database migrations
/workers               # Celery task definitions
/ui                    # Next.js frontend
/infra                 # Docker Compose files
/tests                 # Test suite
/data
  /fake_drive          # Local fixture documents for dev
  /fake_calls          # Local fixture call transcripts for dev
/scripts               # Utility scripts
/docs
  architecture.excalidraw  # System architecture diagram
```

### Adding a knowledge source connector

Implement a connector + ingestor pair in `api/app/ingest/` that outputs normalized documents and writes to `knowledge_index`. See `drive_connector.py` and `feishu_connector.py` for reference implementations.

---

## Security

- No secrets committed to source; all credentials come from environment variables.
- OAuth tokens encrypted at rest (AES-256, configurable key).
- OpenAI API keys stored per-user, AES-256 encrypted, decrypted only at runtime.
- Outbound messaging is domain-allowlisted (`INTERNAL_DOMAIN_ALLOWLIST`).
- `SECURITY_REDACT_BEFORE_LLM=true` strips PII before sending prompts to the LLM.
- All sync, chat, generation, and messaging actions are audit-logged.
- Enterprise mode (`ENTERPRISE_MODE=true`) enforces private LLM endpoint requirement and additional controls.

---

## License

MIT
