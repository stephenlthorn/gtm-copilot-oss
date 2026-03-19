# GTM Copilot — AI-Powered GTM Platform

GTM Copilot is an AI-powered go-to-market platform built for sales, marketing, and SE teams. It automates pre-call research, post-call follow-ups, competitive intelligence, and RAG-grounded chat — all grounded in company knowledge indexed from Google Drive, Feishu, TiDB docs, and TiDB GitHub. Users get role-specific dashboards (Sales Rep, Marketing, SE) backed by a shared account context, with AI that adapts over time through user feedback.

Built and maintained by Stephen Thorn.

---

## Architecture

### System Overview

```mermaid
graph TB
    subgraph clients["Clients"]
        UI["Next.js 14 Frontend<br/>(Sales / Marketing / SE Dashboards)"]
        CLI["KB CLI<br/>(kb sync / search / inspect)"]
        API_CLIENT["API Consumer<br/>(curl / Postman)"]
    end

    subgraph api_layer["FastAPI Backend (Python 3.11)"]
        CHAT_ROUTE["POST /chat"]
        KB_ROUTE["GET /kb/search<br/>GET /kb/inspect/:id"]
        ADMIN_ROUTE["POST /admin/sync/drive<br/>POST /admin/sync/calls<br/>POST /admin/sync/feishu<br/>GET /admin/health<br/>GET /admin/audit<br/>GET|PUT /admin/kb-config<br/>GET /admin/security/settings"]
        CALLS_ROUTE["GET /calls<br/>GET /calls/:id<br/>POST /calls/:id/regenerate-draft"]
        MSG_ROUTE["POST /messages/draft"]
        AUTH_ROUTE["Auth Service<br/>(OAuth / PKCE)"]
    end

    subgraph services["Core Services"]
        ORCH["ChatOrchestrator"]
        REWRITER["QueryRewriter"]
        RETRIEVER["HybridRetriever"]
        EMBED["EmbeddingService"]
        LLM["LLMService"]
        ARTIFACT["ArtifactGenerator"]
        MESSAGING["MessagingService"]
        AUDIT["AuditService"]
        TIDB_DOCS["TiDBDocsRetriever<br/>(live docs.pingcap.com)"]
    end

    subgraph ingest["Ingestion Pipelines"]
        DRIVE_CONN["DriveConnector"]
        DRIVE_ING["DriveIngestor"]
        FEISHU_CONN["FeishuConnector"]
        FEISHU_ING["FeishuIngestor"]
        CHORUS_CONN["CallConnector"]
        TRANSCRIPT_ING["TranscriptIngestor"]
        CHUNKER["Chunking Utils<br/>(markdown / pdf / slides / turns)"]
    end

    subgraph storage["Storage Layer"]
        PG[("PostgreSQL 16<br/>+ pgvector")]
        REDIS[("Redis<br/>(Celery broker)")]
    end

    subgraph external["External Services"]
        GDRIVE["Google Drive API"]
        FEISHU_API["Feishu (Lark) API"]
        CALL_API["Call Transcript API"]
        OPENAI["OpenAI API<br/>(Chat + Embeddings)"]
        DDG["DuckDuckGo<br/>(docs.pingcap.com search)"]
        SMTP_SVC["SMTP Server"]
        SLACK_API["Slack API"]
        FIRECRAWL["Firecrawl API"]
    end

    subgraph worker["Celery Worker + Beat"]
        WORKER["Background Tasks"]
        BEAT["Daily Ingestion Schedule<br/>(every 24h)"]
    end

    UI --> CHAT_ROUTE
    UI --> KB_ROUTE
    UI --> ADMIN_ROUTE
    UI --> CALLS_ROUTE
    UI --> MSG_ROUTE
    CLI --> KB_ROUTE
    API_CLIENT --> CHAT_ROUTE

    CHAT_ROUTE --> ORCH
    KB_ROUTE --> RETRIEVER
    ADMIN_ROUTE --> DRIVE_ING
    ADMIN_ROUTE --> TRANSCRIPT_ING
    ADMIN_ROUTE --> FEISHU_ING
    CALLS_ROUTE --> ARTIFACT
    MSG_ROUTE --> MESSAGING

    ORCH --> REWRITER
    ORCH --> RETRIEVER
    ORCH --> LLM
    ORCH --> AUDIT
    RETRIEVER --> EMBED
    RETRIEVER --> PG

    DRIVE_ING --> DRIVE_CONN
    DRIVE_ING --> CHUNKER
    DRIVE_ING --> EMBED
    DRIVE_CONN --> GDRIVE
    FEISHU_ING --> FEISHU_CONN
    FEISHU_ING --> CHUNKER
    FEISHU_ING --> EMBED
    FEISHU_CONN --> FEISHU_API
    TRANSCRIPT_ING --> CHORUS_CONN
    TRANSCRIPT_ING --> CHUNKER
    TRANSCRIPT_ING --> EMBED
    TRANSCRIPT_ING --> ARTIFACT
    CHORUS_CONN --> CALL_API

    EMBED --> OPENAI
    LLM --> OPENAI
    TIDB_DOCS --> DDG
    MESSAGING --> SMTP_SVC
    MESSAGING --> SLACK_API

    DRIVE_ING --> PG
    FEISHU_ING --> PG
    TRANSCRIPT_ING --> PG
    AUDIT --> PG

    WORKER --> DRIVE_ING
    WORKER --> TRANSCRIPT_ING
    BEAT --> WORKER
    WORKER --> REDIS
```

### RAG Query Flow — Oracle Mode (Direct LLM)

```mermaid
sequenceDiagram
    participant C as Client
    participant R as POST /chat
    participant O as ChatOrchestrator
    participant G as Guardrail Check
    participant L as LLMService
    participant AI as OpenAI API
    participant A as AuditService
    participant DB as PostgreSQL

    C->>R: {mode: "oracle", message: "How to position TiDB vs SingleStore?"}
    R->>O: run(mode="oracle", message, user, top_k, filters, context)
    O->>G: _guardrail_external_messaging(message)
    G-->>O: None (no external recipients detected)

    Note over O: Oracle mode: skip DB retrieval

    O->>L: answer_oracle(message, hits=[], allow_ungrounded=True, tools=[web_search_preview])
    L->>AI: responses.create(model="gpt-4.1", input=[SYSTEM_ORACLE, user_msg], tools)

    Note over AI: SYSTEM_ORACLE: "You are an internal<br/>GTM oracle. Use web_search<br/>when needed. Give direct recommendations."

    AI-->>L: {answer, follow_up_questions}
    L-->>O: {answer, follow_up_questions}
    O-->>R: ({answer, citations: [], follow_up_questions}, {})

    R->>A: write_audit_log(actor, action="chat", input, retrieval={}, output, status=OK)
    A->>DB: INSERT INTO audit_logs

    R-->>C: {answer, citations: [], follow_up_questions}
```

### RAG Query Flow — Call Assistant Mode (Grounded RAG)

```mermaid
sequenceDiagram
    participant C as Client
    participant R as POST /chat
    participant O as ChatOrchestrator
    participant QR as QueryRewriter
    participant HR as HybridRetriever
    participant ES as EmbeddingService
    participant AI as OpenAI API
    participant L as LLMService
    participant A as AuditService
    participant DB as PostgreSQL

    C->>R: {mode: "call_assistant", message: "What risks from the Acme call?"}
    R->>O: run(mode="call_assistant", ...)

    Note over O: Resolve kb_config:<br/>retrieval_top_k, llm_model,<br/>allowed_sources=[calls]

    O->>QR: rewrite("What risks from the Acme call?", mode="call_assistant")

    Note over QR: Dedup terms, append:<br/>["transcript", "next steps", "risks"]

    QR-->>O: "What risks Acme call transcript next steps risks"

    O->>HR: search(rewritten_query, top_k=8, filters={source_type: [calls]})

    HR->>ES: embed(rewritten_query)
    ES->>AI: embeddings.create(model="text-embedding-3-small", input=query)
    AI-->>ES: vector[1536]
    ES-->>HR: query_vec

    Note over HR: 1. Vector search:<br/>SELECT ... FROM kb_chunks kc<br/>JOIN kb_documents kd ON kd.id = kc.document_id<br/>ORDER BY kc.embedding <=> query_vec<br/>LIMIT 320<br/><br/>2. Keyword search:<br/>regex word boundary matching<br/><br/>3. Score = 0.50*vec + 0.30*kw<br/>+ 0.10*title + source_bias<br/>+ domain_boost

    HR->>DB: Vector + Keyword SQL queries
    DB-->>HR: candidate chunks
    HR-->>O: top_k RetrievedChunks (sorted by score)

    O->>L: answer_call_assistant(message, hits, model, tools)

    Note over L: Build evidence string:<br/>[source_id:chunk_id] text[:1200]<br/>for each hit

    L->>AI: responses.create(model, input=[SYSTEM_CALL_COACH, evidence + question])
    AI-->>L: {what_happened, risks, next_steps, questions_to_ask_next_call}
    L-->>O: structured response

    Note over O: Build citations (top 8):<br/>{title, source_type, source_id,<br/>chunk_id, quote (25 words),<br/>relevance, file_id, timestamp}

    O-->>R: (response, retrieval_payload)
    R->>A: write_audit_log(action="chat", input, retrieval, output)
    A->>DB: INSERT INTO audit_logs
    R-->>C: {what_happened, risks, next_steps, questions_to_ask_next_call, citations}
```

### Ingestion Pipelines

#### Google Drive Ingestion

```mermaid
flowchart TB
    TRIGGER["POST /admin/sync/drive?since=ISO_TS<br/>or Celery daily_ingestion task"]

    TRIGGER --> DI["DriveIngestor.sync(since)"]
    DI --> DC["DriveConnector.list_files(since)"]

    DC --> CREDS{Google API<br/>creds set?}
    CREDS -->|Yes| GAPI["Google Drive API<br/>(drive.readonly scope)"]
    CREDS -->|No| FAKE["Scan data/fake_drive/<br/>recursively"]

    GAPI --> FILES["list of DriveFile"]
    FAKE --> FILES

    FILES --> LOOP["For each DriveFile"]

    LOOP --> UPSERT["_upsert_document()<br/>INSERT/UPDATE kb_documents<br/>ON CONFLICT (source_type, source_id)"]

    UPSERT --> CHANGED{modified_time or<br/>permissions_hash<br/>changed?}
    CHANGED -->|No| SKIP["Skip (increment skipped)"]
    CHANGED -->|Yes| CHUNK["_to_chunks() based on MIME type"]

    CHUNK --> MIME{MIME type?}
    MIME -->|Slides| SLIDE_CHUNK["chunk_slides()<br/>Split by --- separator<br/>metadata: slide N"]
    MIME -->|PDF| PDF_CHUNK["chunk_pdf_pages()<br/>Split by form-feed<br/>metadata: page N"]
    MIME -->|Markdown/Text| MD_CHUNK["chunk_markdown_heading_aware()<br/>Split by H1-H6 headers<br/>700-word blocks, 100-word overlap<br/>metadata: heading, section_index"]

    SLIDE_CHUNK --> EMBED
    PDF_CHUNK --> EMBED
    MD_CHUNK --> EMBED

    EMBED["EmbeddingService.batch_embed(chunk_texts)"]

    EMBED --> OPENAI_EMB{OPENAI_API_KEY<br/>set?}
    OPENAI_EMB -->|Yes| REAL_EMB["OpenAI text-embedding-3-small<br/>vector 1536 dims"]
    OPENAI_EMB -->|No| HASH_EMB["Deterministic hash embedding<br/>SHA256 normalized vector 1536 dims"]

    REAL_EMB --> STORE
    HASH_EMB --> STORE

    STORE["INSERT INTO kb_chunks<br/>(document_id, chunk_index, text,<br/>embedding, metadata, content_hash)"]

    STORE --> AUDIT["AuditLog<br/>action=sync_drive<br/>output: files_seen, indexed, skipped"]

    style TRIGGER fill:#2d6a4f,stroke:#1b4332,color:#fff
    style STORE fill:#1d3557,stroke:#0d1b2a,color:#fff
    style AUDIT fill:#6c757d,stroke:#495057,color:#fff
```

#### Call Transcript Ingestion

```mermaid
flowchart TB
    TRIGGER["POST /admin/sync/calls?since=YYYY-MM-DD<br/>or Celery daily_ingestion task"]

    TRIGGER --> TI["TranscriptIngestor.sync(since)"]
    TI --> CC["CallConnector.fetch_calls(since)"]

    CC --> CREDS{CALL_API_KEY<br/>set?}
    CREDS -->|Yes| CAPI["Call Transcript API<br/>(Bearer token auth)"]
    CREDS -->|No| FAKE["Load data/fake_calls/*.json"]

    CAPI --> CALLS["list of raw calls"]
    FAKE --> CALLS

    CALLS --> LOOP["For each raw call"]

    LOOP --> NORM["_normalize(payload)<br/>Standardize speaker_map, turns, metadata"]

    NORM --> UPSERT_CALL["_upsert_call()<br/>INSERT/UPDATE call records<br/>(call_id, date, account,<br/>opportunity, stage, rep_email,<br/>se_email, participants)"]

    UPSERT_CALL --> UPSERT_DOC["_upsert_document()<br/>INSERT/UPDATE kb_documents<br/>source_type=calls"]

    UPSERT_DOC --> CHUNK["_replace_chunks()<br/>chunk_transcript_turns()"]

    CHUNK --> CHUNK_DETAIL["Accumulate turns into chunks:<br/>45-90 second windows or 700 tokens<br/>Include speaker name + role + HH:MM:SS<br/>metadata: start_time_sec, end_time_sec"]

    CHUNK_DETAIL --> EMBED["EmbeddingService.batch_embed(chunk_texts)"]
    EMBED --> STORE_CHUNKS["DELETE old chunks for document<br/>INSERT new kb_chunks with embeddings"]

    STORE_CHUNKS --> GEN_ART["_replace_artifact()<br/>ArtifactGenerator.generate()"]

    GEN_ART --> HEURISTIC["Heuristic extraction:<br/>- Competitors detected<br/>- Objections flagged<br/>- Risks: standard set + LLM-generated<br/>- Next steps: standard set + LLM-generated<br/>- Recommended collateral links"]

    HEURISTIC --> STORE_ART["INSERT/UPDATE call_artifacts<br/>(summary, objections, competitors_mentioned,<br/>risks, next_steps, recommended_collateral,<br/>follow_up_questions, model_info)"]

    STORE_ART --> AUDIT["AuditLog<br/>action=sync_calls<br/>output: calls_seen, processed"]

    style TRIGGER fill:#2d6a4f,stroke:#1b4332,color:#fff
    style STORE_CHUNKS fill:#1d3557,stroke:#0d1b2a,color:#fff
    style STORE_ART fill:#1d3557,stroke:#0d1b2a,color:#fff
    style AUDIT fill:#6c757d,stroke:#495057,color:#fff
```

### Hybrid Retrieval Scoring

```mermaid
flowchart TB
    QUERY["User query string"]

    QUERY --> EMBED_Q["EmbeddingService.embed(query)<br/>query_vec 1536 dims"]
    QUERY --> EXTRACT["Extract query terms<br/>(3+ chars, filter stop words)"]

    EMBED_Q --> VEC_SEARCH["Vector Search (pgvector)<br/>ORDER BY embedding <=> query_vec<br/>LIMIT max(200, top_k * 40)"]
    EXTRACT --> KW_SEARCH["Keyword Search<br/>regex word-boundary match<br/>on chunk text"]

    VEC_SEARCH --> MERGE["Merge candidates"]
    KW_SEARCH --> MERGE

    MERGE --> SCORE["Score each chunk"]

    SCORE --> FORMULA["With semantic embeddings:<br/>score = 0.50 * vec_score<br/>+ 0.30 * kw_score<br/>+ 0.10 * title_score<br/>+ source_bias<br/>+ domain_boost"]

    SCORE --> FORMULA2["Without embeddings (hash mode):<br/>score = 0.05 * vec_score<br/>+ 0.68 * kw_score<br/>+ 0.17 * title_score<br/>+ source_bias<br/>+ domain_boost<br/>Skip if kw less than 0.18 AND title less than 0.25"]

    FORMULA --> BIAS["Source Bias:<br/>+0.08 GitHub docs<br/>+0.03 Markdown/text<br/>-0.05 Code files<br/>-0.10 Changelogs<br/>-0.20 Test files"]

    FORMULA2 --> BIAS

    BIAS --> FILTER["Apply filters:<br/>source_type (case-insensitive)<br/>account (from document tags)"]

    FILTER --> DEDUP["Deduplicate by chunk_id"]
    DEDUP --> SORT["Sort by score DESC<br/>Return top_k"]

    style QUERY fill:#2d6a4f,stroke:#1b4332,color:#fff
    style SORT fill:#1d3557,stroke:#0d1b2a,color:#fff
```

### Database Schema

```mermaid
erDiagram
    kb_documents {
        uuid id PK
        enum source_type "google_drive | feishu | calls | tidb_docs_online"
        varchar source_id "file ID or call ID"
        varchar title
        text url
        varchar mime_type
        timestamptz modified_time
        varchar owner
        varchar path
        varchar permissions_hash "SHA256"
        jsonb tags "owner source_type account date"
        timestamptz created_at
    }

    kb_chunks {
        uuid id PK
        uuid document_id FK
        int chunk_index
        text text
        int token_count
        vector_1536 embedding "pgvector cosine"
        jsonb metadata "heading page slide start_time_sec end_time_sec"
        varchar content_hash "SHA256"
        timestamptz created_at
    }

    call_records {
        uuid id PK
        varchar call_id UK
        date date
        varchar account
        varchar opportunity
        varchar stage
        varchar rep_email
        varchar se_email
        jsonb participants "name role email"
        text recording_url
        text transcript_url
        timestamptz created_at
    }

    call_artifacts {
        uuid id PK
        varchar call_id
        text summary
        jsonb objections
        jsonb competitors_mentioned
        jsonb risks
        jsonb next_steps
        jsonb recommended_collateral "title drive_file_id reason"
        jsonb follow_up_questions
        jsonb model_info "provider model prompt_hash"
        timestamptz created_at
    }

    outbound_messages {
        uuid id PK
        timestamptz created_at
        enum mode "draft | sent | blocked"
        enum channel "email | slack"
        jsonb to
        jsonb cc
        varchar subject
        text body
        text reason_blocked
        varchar call_id
        uuid artifact_id FK
        varchar content_hash
    }

    audit_logs {
        uuid id PK
        timestamptz timestamp
        varchar actor
        varchar action "chat | kb_search | sync_drive | sync_calls | draft_message | send_message"
        jsonb input
        jsonb retrieval "top_k results with chunk_id document_id score"
        jsonb output
        enum status "ok | error"
        text error_message
    }

    kb_config {
        int id PK "singleton"
        bool google_drive_enabled
        text google_drive_folder_ids
        bool feishu_enabled
        varchar feishu_folder_token
        bool calls_enabled
        int retrieval_top_k "default 8"
        varchar llm_model "default gpt-4.1"
        bool web_search_enabled
        bool code_interpreter_enabled
        timestamptz updated_at
    }

    kb_documents ||--o{ kb_chunks : "has chunks"
    call_records ||--o| call_artifacts : "generates artifact"
    call_artifacts ||--o{ outbound_messages : "sources draft"
    kb_documents }o--|| call_records : "linked via source_id"
```

### Messaging Guard Rails

```mermaid
flowchart TB
    REQ["POST /messages/draft<br/>to, cc, mode, tone, call_id"]

    REQ --> VALIDATE["MessagingService.validate_recipients(to, cc)"]

    VALIDATE --> CHECK{All recipients match<br/>INTERNAL_DOMAIN_ALLOWLIST?}

    CHECK -->|No| BLOCKED["mode = BLOCKED<br/>reason: Outbound messages<br/>restricted to internal recipients"]

    CHECK -->|Yes| BUILD["Build email:<br/>subject: account call takeaways + next-step questions<br/>body: summary + next_steps + questions + collateral"]

    BUILD --> MODE{EMAIL_MODE setting<br/>AND requested mode?}

    MODE -->|"EMAIL_MODE=draft<br/>(always)"| DRAFT["mode = DRAFT<br/>Store in outbound_messages"]
    MODE -->|"EMAIL_MODE=send<br/>AND mode=send"| SEND["Send via SMTP (STARTTLS)<br/>mode = SENT"]

    BLOCKED --> AUDIT["AuditLog"]
    DRAFT --> AUDIT
    SEND --> AUDIT

    style BLOCKED fill:#c0392b,stroke:#922b21,color:#fff
    style DRAFT fill:#f39c12,stroke:#d68910,color:#fff
    style SEND fill:#27ae60,stroke:#1e8449,color:#fff
```

[View interactive Excalidraw diagram](./docs/architecture.excalidraw)

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

## Key Functions Reference

### ChatOrchestrator (`services/chat_orchestrator.py`)

```python
class ChatOrchestrator:
    def run(*, mode: str, user: str, message: str,
            top_k: int, filters: dict, context: dict) -> tuple[dict, dict]
    # mode="oracle": LLM-direct (no DB), allow_ungrounded=True
    # mode="call_assistant": QueryRewriter -> HybridRetriever -> LLM with evidence
    # Returns (response_dict, retrieval_payload)
```

### HybridRetriever (`retrieval/service.py`)

```python
class HybridRetriever:
    def search(query: str, *, top_k: int = 8,
               filters: dict | None = None) -> list[RetrievedChunk]
    # 1. Vector: ORDER BY embedding <=> query_vec LIMIT max(200, top_k*40)
    # 2. Keyword: regex word-boundary match on chunk text
    # 3. Score: 0.50*vec + 0.30*kw + 0.10*title + source_bias + domain_boost
    # 4. Filter by source_type, account
    # 5. Dedup by chunk_id, sort by score DESC, return top_k
```

### EmbeddingService (`services/embedding.py`)

```python
class EmbeddingService:
    def embed(text: str) -> list[float]          # single text -> vector[1536]
    def batch_embed(texts: Iterable[str]) -> list[list[float]]  # batch
    # With OPENAI_API_KEY: calls text-embedding-3-small
    # Without: SHA256 hash -> deterministic normalized vector
```

### LLMService (`services/llm.py`)

```python
class LLMService:
    def answer_oracle(message, hits, *, model=None, tools=None,
                      allow_ungrounded=False) -> dict
    # Returns {answer, follow_up_questions}
    # Fallback: _local_oracle_synthesis() (lexical ranking + heuristic response)

    def answer_call_assistant(message, hits, *, model=None, tools=None) -> dict
    # Returns {what_happened, risks, next_steps, questions_to_ask_next_call}
```

### Key SQL Queries

**Vector similarity search (pgvector)**:
```sql
SELECT kc.id, kc.text, kc.metadata, kc.embedding,
       kd.title, kd.source_type, kd.source_id, kd.url, kd.tags
FROM kb_chunks kc
JOIN kb_documents kd ON kd.id = kc.document_id
ORDER BY kc.embedding <=> :query_vec
LIMIT :candidate_limit
```

**ivfflat index**:
```sql
CREATE INDEX ix_kb_chunks_embedding
ON kb_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

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
