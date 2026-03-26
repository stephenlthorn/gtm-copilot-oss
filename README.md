# GTM Copilot — AI-Powered GTM Platform

GTM Copilot is an AI-powered go-to-market platform built for sales, marketing, and SE teams. It automates pre-call research, post-call follow-ups, competitive intelligence, and RAG-grounded chat — all grounded in company knowledge indexed from Google Drive, Feishu, TiDB docs, and TiDB GitHub. Users get role-specific dashboards (Sales Rep, Marketing, SE) backed by a shared account context, with AI that adapts over time through user feedback.

Built and maintained by Stephen Thorn.

---

## How It Works

### Data Sources → AI Outputs

```mermaid
flowchart LR
    subgraph internal["Internal Data Sources"]
        GD["📁 Google Drive\nDocs · Slides · PDFs"]
        FS["🪶 Feishu / Lark\nWiki · Docs"]
        CT["📞 Call Transcripts\nChorus / Generic API"]
        SF["☁️ Salesforce\nAccounts · Deals"]
    end

    subgraph osint["Live OSINT (web_search_preview)"]
        LI["💼 LinkedIn\nExecs · Headcount"]
        CB["🏢 Crunchbase\nFunding · Investors"]
        NW["📰 News & Events\nGoogle News"]
        JP["🔍 Job Postings\nLinkedIn · Greenhouse"]
        TS["⚙️ Tech Stack\nBuiltWith · StackShare · GitHub"]
    end

    subgraph free_osint["Free OSINT (no key)"]
        ED["📋 SEC EDGAR\n10-K / 10-Q filings"]
        HN["🟧 Hacker News\nDev sentiment · infra signals"]
    end

    subgraph optional["Optional Connectors"]
        ZI["🔎 ZoomInfo\nContact enrichment"]
    end

    subgraph kb["TiDB Knowledge Base\nVector + Full-text + Relational"]
        VEC["Embeddings\n1536-dim vectors"]
        FT["Full-text index\nBM25-style scoring"]
        META["Metadata\naccounts · deals · calls"]
    end

    subgraph outputs["AI-Generated Outputs"]
        subgraph rep_out["Sales Rep"]
            AB["Account Brief\n7-section company analysis"]
            DQ["Discovery Questions\nTailored to tech & pain"]
            FS2["Full Solution\nPhases 1–3 combined"]
            DR["Deal Risk Analysis\nMEDDPICC-aligned"]
            FD["Follow-Up Draft\nPost-call email"]
            TAL["Target Account List\nBy territory · revenue · vertical"]
        end
        subgraph se_out["Sales Engineer"]
            PP["POC Plan\nTechnical eval roadmap"]
            AF["Architecture Fit\nTiDB placement analysis"]
            CC["Competitor Coach\nBattlecards & objection handling"]
        end
        subgraph mkt_out["Marketing"]
            MI["Market Intelligence\nBuying signals · TAM"]
            BC["Battle Card\nCompetitor positioning"]
        end
        subgraph chat_out["Oracle Chat"]
            OC["RAG-grounded answers\nwith citations"]
        end
    end

    GD & FS & CT & SF --> kb
    LI & CB & NW & JP & TS --> AB & FS2
    ED & HN --> AB & FS2
    ZI --> AB & FS2

    kb --> AB & DQ & FS2 & DR & FD & TAL
    kb --> PP & AF & CC
    kb --> MI & BC
    kb --> OC

    style internal fill:#1d3557,stroke:#457b9d,color:#fff
    style osint fill:#2d6a4f,stroke:#52b788,color:#fff
    style free_osint fill:#5c4033,stroke:#a1887f,color:#fff
    style optional fill:#4a4e69,stroke:#9a8c98,color:#fff
    style kb fill:#0d1b2a,stroke:#415a77,color:#fff
    style outputs fill:#1a1a2e,stroke:#533483,color:#fff
```

---

### How GTM Copilot Generates an Answer

```mermaid
flowchart TB
    Q(["User question\ne.g. 'What are the deal risks for Acme?'"])

    Q --> MODE{Chat mode?}

    MODE -->|"oracle (open Q&A)"| ORACLE_PATH["RAG retrieval (if enabled)\n+ web_search_preview + KB"]
    MODE -->|"call_assistant / rep / se"| RAG_PATH["Full RAG pipeline"]

    subgraph rag["RAG Pipeline"]
        RAG_PATH --> REWRITE["Query Rewriter\nDedup terms · append mode keywords\ne.g. + 'transcript risks next steps'"]

        REWRITE --> MULTI["Multi-Query HyDE\nGenerate 3–5 hypothetical\ndocument excerpts (gpt-5.4-mini)\nthen embed each"]

        MULTI --> HYBRID["Hybrid Retrieval (TiDB)\n━━━━━━━━━━━━━━━━━━━━━━\nVector: VEC_COSINE_DISTANCE()\ntop 20 per query\n+\nFull-text: MATCH AGAINST()\nMerged via Reciprocal Rank Fusion"]

        HYBRID --> SCORE["Scoring\n0.50 × vector\n0.30 × keyword\n0.10 × title match\n± source bias"]

        SCORE --> RERANK["LLM Reranker (GPT-4o-mini)\nScore 0–10 each candidate\nKeep top_k (default 8)"]
    end

    subgraph feedback_ctx["Feedback Injection"]
        RERANK --> FB["Retrieve past corrections\nfrom ai_feedback table\n(cosine similarity, rating=negative)"]
    end

    ORACLE_PATH --> COMPOSE
    FB --> COMPOSE["Prompt Composition\n━━━━━━━━━━━━━━━━━━━━━\nSystem persona (Rep / SE / Oracle)\n+ Source profile instructions\n+ Retrieved evidence chunks\n+ Past user corrections\n+ User question"]

    COMPOSE --> LLM["LLM Synthesis\nOpenAI Responses API\ngpt-5.4 / o3-pro / o3 / o4-mini / gpt-5.4-mini\n± reasoning effort (low / medium / high)\n± web_search_preview tool"]

    LLM --> ANS(["Structured answer\n+ Citations (chunk ID · title · quote)\n+ Follow-up questions\n+ Confidence signals"])

    ANS --> AUDIT["Audit Log → TiDB\nactor · query · retrieval · output"]

    style Q fill:#2d6a4f,stroke:#52b788,color:#fff
    style ANS fill:#1d3557,stroke:#457b9d,color:#fff
    style rag fill:#0d1b2a,stroke:#415a77,color:#fff
    style feedback_ctx fill:#4a4e69,stroke:#9a8c98,color:#fff
    style AUDIT fill:#3d3d3d,stroke:#666,color:#ccc
```

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
        KB_ROUTE["GET /kb/search<br/>GET /knowledge"]
        REP_ROUTE["POST /rep/account-brief<br/>POST /rep/follow-up-draft<br/>POST /rep/deal-risk"]
        SE_ROUTE["POST /se/poc-plan<br/>POST /se/architecture-fit<br/>POST /se/competitor-coach"]
        MKT_ROUTE["POST /marketing/intelligence<br/>POST /marketing/battle-card"]
        ADMIN_ROUTE["POST /admin/sync/*<br/>GET /admin/audit<br/>GET|PUT /admin/kb-config<br/>POST /admin/mcp/enable"]
        AUTH_ROUTE["POST /auth/google<br/>POST /auth/openai-key<br/>POST /auth/connect-provider"]
        MSG_ROUTE["POST /messages/draft"]
        SLACK_ROUTE["POST /slack/events<br/>POST /slack/actions"]
    end

    subgraph services["Core Services"]
        ORCH["ChatOrchestrator<br/>(oracle / call_assistant / research)"]
        REWRITER["QueryRewriter"]
        RETRIEVER_V1["HybridRetriever (v1)<br/>VEC_COSINE_DISTANCE()"]
        RETRIEVER_V2["HybridRetrievalService (v2)<br/>TiDB: VEC_COSINE_DISTANCE() + RRF"]
        EMBED["EmbeddingService"]
        LLM["LLMService<br/>(OpenAI + Anthropic/MiniMax + Codex)"]
        GTM["GTMModuleService<br/>(12+ role-specific modules)"]
        RESEARCH["AccountBriefResearcher<br/>PostCallPipeline<br/>RefinementService"]
        ARTIFACT["ArtifactGenerator"]
        MESSAGING["MessagingService"]
        AUDIT["AuditService"]
        TIDB_DOCS["TiDBDocsRetriever<br/>(live docs.pingcap.com)"]
    end

    subgraph mcp["MCP Server Integrations (15)"]
        MCP_TIDB["TiDB Cloud + Observability"]
        MCP_CRM["Salesforce"]
        MCP_INTEL["ZoomInfo / LinkedIn / Crunchbase"]
        MCP_COMM["Slack / Gmail / Calendar"]
        MCP_CONTENT["Drive / Feishu / GitHub"]
    end

    subgraph ingest["Ingestion Pipelines"]
        DRIVE_ING["DriveIngestor + DriveConnector"]
        FEISHU_ING["FeishuIngestor + FeishuConnector"]
        TRANSCRIPT_ING["TranscriptIngestor + CallConnector"]
        SF_SYNC["SalesforceSyncService"]
        CHUNKER["Chunking Utils<br/>(markdown / pdf / slides / turns)"]
    end

    subgraph storage["Storage Layer"]
        TIDB[("TiDB Cloud v8.5<br/>VEC_COSINE_DISTANCE()<br/>MATCH AGAINST fulltext<br/>MySQL protocol :4000")]
        REDIS[("Redis<br/>(Celery broker + sessions)")]
    end

    subgraph external["External Services"]
        GDRIVE["Google Drive API"]
        FEISHU_API["Feishu (Lark) API"]
        CALL_API["Call Transcript API"]
        OPENAI["OpenAI API<br/>(Chat + Embeddings)"]
        SMTP_SVC["SMTP Server"]
        SLACK_API["Slack API"]
        SALESFORCE["Salesforce API"]
    end

    subgraph worker["Celery Worker + Beat"]
        WORKER["sync_drive / sync_calls<br/>sync_salesforce / research_task<br/>market_intel_task"]
        BEAT["Daily Ingestion<br/>(every 24h)"]
    end

    UI --> CHAT_ROUTE & REP_ROUTE & SE_ROUTE & MKT_ROUTE & ADMIN_ROUTE
    CLI --> KB_ROUTE
    API_CLIENT --> CHAT_ROUTE

    CHAT_ROUTE --> ORCH
    REP_ROUTE --> GTM
    SE_ROUTE --> GTM
    MKT_ROUTE --> GTM
    KB_ROUTE --> RETRIEVER_V1 & RETRIEVER_V2
    MSG_ROUTE --> MESSAGING
    SLACK_ROUTE --> SLACK_API
    AUTH_ROUTE --> OPENAI

    ORCH --> REWRITER & LLM & AUDIT
    ORCH --> RETRIEVER_V1 & RETRIEVER_V2
    GTM --> RESEARCH
    RESEARCH --> RETRIEVER_V2 & LLM
    RETRIEVER_V1 --> EMBED & TIDB
    RETRIEVER_V2 --> EMBED & TIDB

    LLM --> OPENAI
    LLM --> mcp

    DRIVE_ING --> GDRIVE & CHUNKER & EMBED
    FEISHU_ING --> FEISHU_API & CHUNKER & EMBED
    TRANSCRIPT_ING --> CALL_API & CHUNKER & EMBED & ARTIFACT
    SF_SYNC --> SALESFORCE

    DRIVE_ING & FEISHU_ING & TRANSCRIPT_ING & SF_SYNC --> TIDB
    AUDIT --> TIDB

    BEAT --> WORKER
    WORKER --> REDIS
    WORKER --> DRIVE_ING & TRANSCRIPT_ING & SF_SYNC
```

### RAG Query Flow — Oracle Mode (General Chat)

```mermaid
sequenceDiagram
    participant C as Client
    participant R as POST /chat
    participant O as ChatOrchestrator
    participant G as Guardrail Check
    participant HR as HybridRetriever
    participant L as LLMService
    participant AI as OpenAI API
    participant A as AuditService
    participant DB as TiDB Cloud

    C->>R: {mode: "oracle", message: "Can TiDB X merge schema branches?", rag_enabled: true}
    R->>O: run(mode="oracle", message, user, top_k, filters, rag_enabled=true)
    O->>G: _guardrail_external_messaging(message)
    G-->>O: None (no external recipients detected)

    Note over O: rag_enabled=true and message is not conversational<br/>→ perform KB retrieval

    O->>HR: search(rewritten_query, top_k=8, filters={source_type: [drive, feishu, chorus, memory]})
    HR->>DB: Vector + Keyword SQL queries
    DB-->>HR: candidate chunks
    HR-->>O: top_k RetrievedChunks

    O->>L: answer_oracle(message, hits, allow_ungrounded=false, tools=[web_search_preview])
    L->>AI: responses.create(model="gpt-5.4", input=[SYSTEM_ORACLE, evidence+question], tools)

    Note over AI: SYSTEM_ORACLE adapts response style to question type.<br/>Technical questions → direct answer.<br/>Always searches docs.pingcap.com for TiDB questions.

    AI-->>L: {answer, follow_up_questions}
    L-->>O: {answer, citations, follow_up_questions}
    O-->>R: ({answer, citations, follow_up_questions}, retrieval_payload)

    R->>A: write_audit_log(actor, action="chat", input, retrieval, output, status=OK)
    A->>DB: INSERT INTO audit_logs

    R-->>C: {answer, citations, follow_up_questions}
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
    participant DB as TiDB Cloud

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

    Note over HR: Vector: VEC_COSINE_DISTANCE(embedding, query_vec)<br/>FROM knowledge_index<br/>WHERE org_id = :org_id ORDER BY distance ASC<br/>LIMIT 20<br/><br/>Keyword: MATCH(chunk_text) AGAINST<br/>(:query IN NATURAL LANGUAGE MODE)<br/><br/>Score = 0.50*vec + 0.30*kw<br/>+ 0.10*title + source_bias + domain_boost

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

    EMBED_Q --> VEC_TIDB["TiDB Vector Search<br/>SELECT *, VEC_COSINE_DISTANCE(embedding, query_vec)<br/>AS distance FROM knowledge_index<br/>ORDER BY distance ASC LIMIT 20"]
    EXTRACT --> KW_TIDB["TiDB Fulltext<br/>MATCH(chunk_text) AGAINST<br/>(:query IN NATURAL LANGUAGE MODE)"]

    VEC_TIDB --> MERGE["Merge candidates<br/>(Reciprocal Rank Fusion)"]
    KW_TIDB --> MERGE

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

#### V1 Tables (Knowledge Base + Calls)

```mermaid
erDiagram
    kb_documents {
        uuid id PK
        enum source_type "google_drive | feishu | chorus | tidb_docs_online"
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
        json embedding "1536-dim vector (JSON array)"
        jsonb metadata "heading page slide start_time_sec end_time_sec"
        varchar content_hash "SHA256"
        timestamptz created_at
    }

    chorus_calls {
        uuid id PK
        varchar chorus_call_id UK
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
        varchar chorus_call_id
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
        jsonb to_recipients
        jsonb cc_recipients
        varchar subject
        text body
        text reason_blocked
        varchar chorus_call_id
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
        bool chorus_enabled
        int retrieval_top_k "default 8"
        varchar llm_model "default gpt-5.4"
        bool web_search_enabled
        bool code_interpreter_enabled
        timestamptz updated_at
    }

    google_drive_user_credentials {
        uuid id PK
        varchar user_email UK
        text encrypted_token "AES-256"
        timestamptz created_at
        timestamptz updated_at
    }

    kb_documents ||--o{ kb_chunks : "has chunks"
    chorus_calls ||--o| call_artifacts : "generates artifact"
    call_artifacts ||--o{ outbound_messages : "sources draft"
    kb_documents }o--|| chorus_calls : "linked via source_id"
```

#### V2 Tables (Multi-Tenant GTM Platform)

```mermaid
erDiagram
    users {
        uuid id PK
        varchar email UK
        varchar name
        enum role "sales_rep | se | marketing | admin"
        int org_id FK
        text encrypted_openai_key "AES-256 per-user"
        timestamptz created_at
    }

    knowledge_index {
        uuid id PK
        int org_id FK
        varchar source_type
        varchar source_id
        varchar title
        text chunk_text
        json embedding "1536-dim vector (JSON array for TiDB)"
        jsonb metadata
        varchar content_hash
        timestamptz created_at
    }

    accounts {
        uuid id PK
        int org_id FK
        varchar name
        varchar industry
        varchar segment
        varchar territory
        varchar salesforce_id
        timestamptz created_at
    }

    deals {
        uuid id PK
        uuid account_id FK
        varchar name
        varchar stage
        decimal amount
        date close_date
        varchar salesforce_id
        timestamptz created_at
    }

    research_reports {
        uuid id PK
        int org_id FK
        uuid account_id FK
        varchar report_type "pre_call | post_call | competitive"
        jsonb sections "7-section account brief JSON"
        varchar model_info
        timestamptz created_at
    }

    ai_refinements {
        uuid id PK
        uuid user_id FK
        varchar scope "personal | team"
        text refinement_text
        float effectiveness_score
        bool active
        timestamptz created_at
    }

    conversations {
        uuid id PK
        uuid user_id FK
        uuid account_id FK
        varchar mode "oracle | call_assistant | research"
        timestamptz created_at
    }

    messages {
        uuid id PK
        uuid conversation_id FK
        enum role "user | assistant | tool"
        text content
        jsonb tool_calls
        jsonb tool_results
        timestamptz created_at
    }

    source_registry {
        uuid id PK
        int org_id FK
        varchar provider "salesforce | zoominfo | etc"
        jsonb config "encrypted credentials"
        bool enabled
        timestamptz created_at
    }

    api_usage_log {
        uuid id PK
        int org_id FK
        varchar provider
        varchar endpoint
        int tokens_used
        decimal cost_usd
        timestamptz created_at
    }

    sync_status {
        uuid id PK
        int org_id FK
        varchar source "drive | feishu | chorus | salesforce"
        enum status "ok | error | running"
        timestamptz last_sync
        text error_message
    }

    users ||--o{ conversations : "has"
    users ||--o{ ai_refinements : "creates"
    conversations ||--o{ messages : "contains"
    accounts ||--o{ deals : "has"
    accounts ||--o{ research_reports : "about"
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
| LLM | Codex OAuth (ChatGPT subscription) · OpenAI API key (optional fallback) · Anthropic/MiniMax |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dimensions) · SHA-256 hash fallback |
| Reverse Proxy | Caddy (automatic HTTPS via sslip.io) |
| Containerization | Docker Compose |
| Web Search | Built-in `web_search_preview` tool (no key required) |

---

## Quick Start (EC2 / Production)

```bash
# 1. Clone and enter the infra directory
git clone https://github.com/stephenlthorn/gtm-copilot-oss.git app
cd app/infra/aws

# 2. Configure environment
cp .env.example .env
nano .env   # fill in required values (see Configuration below)

# 3. Generate required secrets
SECRET_KEY=$(openssl rand -hex 32)
NEXTAUTH_SECRET=$(openssl rand -hex 32)
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "SECRET_KEY=$SECRET_KEY" >> .env
echo "NEXTAUTH_SECRET=$NEXTAUTH_SECRET" >> .env
echo "FERNET_KEY=$FERNET_KEY" >> .env

# 4. Start everything
docker compose -f docker-compose.prod.yml up -d --build
```

The UI is served at `https://<DOMAIN>` (port 443) and the API at `https://<DOMAIN>:8443`.

Trigger initial knowledge sync after startup:

```bash
curl -X POST "https://<DOMAIN>:8443/admin/sync/drive"
curl -X POST "https://<DOMAIN>:8443/admin/sync/calls"
```

For local development, see the [Development](#development) section below.

---

## Configuration

Copy `.env.example` to `.env` and fill in the values below.

### Required — Domain & Auth

| Variable | Description |
|---|---|
| `DOMAIN` | Your Elastic IP + `.sslip.io` — e.g. `34.56.78.90.sslip.io` |
| `SECRET_KEY` | Backend session secret — `openssl rand -hex 32` |
| `NEXTAUTH_SECRET` | NextAuth secret — `openssl rand -hex 32` |
| `FERNET_KEY` | Encryption key for stored OAuth tokens — `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID (login + Drive) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `ALLOWED_EMAIL_DOMAIN` | Restrict login to this email domain (e.g. `pingcap.com`) |

### Required — Database

| Variable | Description |
|---|---|
| `DATABASE_URL` | Full TiDB Cloud connection string: `mysql+pymysql://USER:PASS@gateway01.us-east-1.prod.aws.tidbcloud.com:4000/DB?ssl_verify_cert=true&ssl_verify_identity=true` |

> **Note:** The DB pool is configured for TiDB Cloud's 120-second cold-start timeout. Do not change `pool_timeout` without understanding this.

### LLM

The LLM layer supports three auth methods, tried in order:

1. **Codex OAuth** (primary) — user's ChatGPT subscription JWT forwarded per-request. No API key needed.
2. **OpenAI API Key** (fallback) — set `OPENAI_API_KEY` if you want a server-level key.
3. **MiniMax / Anthropic** — optional, set `MINIMAX_API_KEY` or `ANTHROPIC_API_KEY`.

The server also reads Codex CLI auth from `~/.codex/auth.json` (mounted into the container). Run `codex auth login` on the EC2 host to populate this.

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Optional OpenAI API key fallback (not required if using Codex OAuth) |
| `OPENAI_MODEL` | Default model (e.g. `gpt-5.4`; overridden per-request from the UI model picker) |

### Security

| Variable | Description |
|---|---|
| `CORS_ALLOW_ORIGINS` | Comma-separated allowed origins, e.g. `https://100.49.55.13.sslip.io` |
| `SECURITY_TRUSTED_HOST_ALLOWLIST` | Comma-separated trusted host headers |
| `INTERNAL_DOMAIN_ALLOWLIST` | Domains permitted for outbound messaging |
| `ENVIRONMENT` / `APP_ENV` | Set to `production` in prod |

### Google Drive Sync

| Variable | Description |
|---|---|
| `GOOGLE_DRIVE_FOLDER_IDS` | Comma-separated folder IDs to index (optional) |

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

## Chat Sections Reference

The chat interface has eight sections. Each maps to a dedicated system prompt in `api/app/prompts/templates.py`. Selecting a section changes the AI's persona, output format, and retrieval strategy for that conversation.

---

### 1. Oracle Chat (General)

**Prompt:** `SYSTEM_ORACLE`
**Best for:** Free-form questions — technical TiDB questions, product clarifications, quick research, anything that doesn't fit a structured template.

**What it does:**
- Adapts response style to the question type. Technical or factual questions ("How does TiFlash work?") get a direct, concise answer. Deal or account questions ("How should I position against CockroachDB for Acme?") get a structured Context / Insight / Recommendation format.
- Proactively searches **docs.pingcap.com** for any TiDB feature, SQL compatibility, configuration, or behavior question — official docs take precedence over training data.
- Applies TiDB's "database for AI agents" narrative when agent or AI topics come up.
- Performs KB retrieval (Google Drive, Feishu, call transcripts) when RAG is enabled. Short conversational inputs skip retrieval automatically.
- Web search toggle controls access to `web_search_preview`. Citations shown for all retrieved sources.

**Inputs needed:** Just type. No fields to fill.

**Outputs:**
- Direct answer, structured analysis, or a mix depending on question type
- Source citations (KB hits and/or web URLs)
- Follow-up question suggestions when relevant

**When to use instead:** If you're researching a specific company before a call, switch to Pre-Call Intel. If you're analyzing a transcript, use Post-Call Analysis.

---

### 2. Pre-Call Intel

**Prompt:** `SYSTEM_PRE_CALL_INTEL`
**Best for:** Preparing for any first or follow-up meeting with a prospect — company research, persona mapping, and generating ready-to-send outbound messages.

**What it does:**

Deep company intelligence brief across 10 sections:

| Section | What it produces |
|---|---|
| 1. Prospect | Name, role, tenure, LinkedIn URL — verified via live search |
| 2. Company | Industry, size, funding, investors, growth signals |
| 3. Architecture Hypothesis | Current databases (job postings, GitHub, BuiltWith, engineering blogs) with confidence ratings |
| 4. AI & Agent Signals | Is the company building agentic systems? Urgency rating: High / Medium / Low |
| 5. Pain Hypotheses | 3–5 ranked pains with signal source, what to listen for, TiDB connection |
| 6. ICP Persona Map | 2–3 most relevant personas for this company (Head of AI, CTO, Platform Eng), each with tailored value prop and engagement angle |
| 7. TiDB Value Props | 3 tailored props — leads with agent/AI framing if signals exist, falls back to database scaling |
| 8. Discovery Questions | 5 MEDDPICC-labeled questions with rationale |
| 9. Meeting Goal | One specific qualification milestone to achieve — not "learn their stack" |
| 10. Outbound Messaging | Cold email, LinkedIn CR, LinkedIn follow-up, voicemail script, and a full 16-step multi-channel sequence |

**Primary narrative:** Every output leads with "TiDB is the database for AI agents." Agent memory, agent state, multi-agent coordination, and agent-scale concurrency are surfaced before any database feature talk. GTM framework (pain → value prop → discovery) is applied second.

**Accuracy rules:**
- Executes live web searches (Crunchbase, LinkedIn, SEC filings, job boards, GitHub) before writing any section
- Marks any claim it cannot verify as `"Unverified — [what was searched]"`
- If a distributed SQL competitor is found (YugabyteDB, CockroachDB, Spanner, AlloyDB), a **COMPETITIVE ALERT** block appears at the top and the meeting goal is reframed as competitive displacement
- Will NOT invent financial data, employee counts, or technology stack

**Inputs needed:** Company name + contact name (or just company name — it will research the contact).

**Outputs:** Full 10-section brief + complete outbound messaging suite.

---

### 3. Post-Call Analysis (MEDDPICC Deal Coach)

**Prompt:** `SYSTEM_POST_CALL_ANALYSIS`
**Best for:** After any discovery, evaluation, or negotiation call — transcript analysis, deal qualification, coaching, and follow-up email draft.

**What it does:**

Full 8-section MEDDPICC Deal Coach output:

| Section | What it produces |
|---|---|
| 1. Executive Summary | 4–6 sentence deal snapshot: situation, key pains, business impact, urgency, current stage, qualification verdict (Qualified / Not Qualified / Conditional) |
| 2. MEDDPICC Breakdown | All 8 elements scored 1–5 with transcript evidence quote, what's missing, and exact action to close each gap |
| 3. Sales Process Stage Assessment | Maps to one of 7 stages (Identify → Qualify → Establish Value → Validate → Contracting → Close → Implement), lists exit criteria, and gives a ready/not-ready verdict |
| 4. Risks & Red Flags | All risks rated High / Medium / Low — weak champion, missing economic buyer, competitive exposure, deal structure risks |
| 5. Missing Discovery & Required Questions | Exact words of questions to ask, organized by MEDDPICC element |
| 6. Coaching Recommendations | Segmented: Qualification Gaps · Deal Strategy · Stakeholder & Champion Strategy · Next Call Plan (with exact phrasing, not descriptions) |
| 7. Recommended Next Steps | 3–5 actions: Owner + Deliverable + Date. Never vague. |
| 8. Follow-Up Email | Ready-to-send draft: opens with prospect's top pain, reflects call commitments, includes TiDB value prop aligned to their situation, one clear CTA |

**Stance:** Rigorous and critical. Calls out unqualified deals explicitly. Does not assume deal viability. Every coaching point uses SBI format (Situation → Behavior → Impact) and includes a transcript quote.

**Sales process stages understood:**
`Identify Opportunity` → `Qualify Opportunity` → `Establish Value` → `Validate` → `Contracting & Negotiations` → `Close` → `Implement`

**MEDDPICC scoring rubric:**
- 1 = Not mentioned
- 2 = Mentioned but vague
- 3 = Qualified — prospect described it (requires transcript quote)
- 4 = Documented — rep confirmed it (requires transcript quote)
- 5 = Confirmed with corroboration

**Inputs needed:** Paste the call transcript or call notes into the chat. The more detail the better — partial transcripts still produce a best-effort analysis with clear gap flags.

**Outputs:** All 8 sections above, ready to copy into CRM or share with deal team.

---

### 4. Follow-Up Email

**Prompt:** `SYSTEM_FOLLOW_UP_EMAIL`
**Best for:** Drafting a deal-specific follow-up email after any call — not a template, a specific email that gets replied to.

**What it does:**

Three-phase process before outputting anything:

1. **Pre-write analysis** — identifies the single most important call outcome, what the recipient needs to hear to take the next action, which MEDDPICC gaps the email can help close, and whether there's a deal risk to quietly address
2. **Email construction** — enforces strict quality rules: no pleasantries, no "great speaking with you" openers, subject line bans ("follow-up", "touching base"), one CTA only, every action item has owner + deliverable + date
3. **Quality check** — auto-rejects and rewrites if any of the banned patterns appear

**Subject line format:**
`[Account] — [topic 1] + [topic 2]` or `[Account] — [key outcome]: [next action]`

**Body structure:**
- Para 1: What this call established (specific language from the call, their exact terminology)
- Para 2: All committed actions — owner + action + date for every item
- Para 3 (when applicable): One MEDDPICC bridge question planted naturally (Champion, Decision Process, Decision Criteria, Competition, or Paper Process)
- Close: One ask only — specific date, person, or deliverable

**Tone modes:** Adapts between crisp/executive/technical based on the recipient role.

**Inputs needed:** Call notes or transcript pasted into the chat. Providing account history and deal stage improves output significantly.

**Outputs:** Subject line + ready-to-send email body. Plain text, no markdown headers.

---

### 5. Market Research / TAL

**Prompt:** `SYSTEM_MARKET_RESEARCH`
**Best for:** Building target account lists, territory planning, ICP scoring batches, and market opportunity analysis.

**What it does:**

ICP scoring engine + territory strategy. Scores each account across 5 criteria (1–5 each, total out of 25):

| Criterion | Signal | Top Score |
|---|---|---|
| Company size fit | 500–10K employees, $50M–$5B revenue | 5 |
| Industry fit | Fintech, Ad-tech, SaaS, Gaming, E-Commerce = Tier 1 | 5 |
| Tech stack match | MySQL / Aurora / Vitess in stack = direct migration path | 5 |
| Growth signal | Recent funding, hiring surge, IPO/M&A | 5 |
| Champion potential | Accessible engineering/platform leadership | 5 |
| AI/ML bonus | Active AI hiring, RAG, embedding pipelines, LLM apps | +1–2 |

**Signal weighting priority:**
1. Financial signal (funding, IPO, M&A) — budget confirmed
2. Hiring signal (DB/infra/AI engineer postings) — active investment
3. Tech stack signal (MySQL/Aurora at scale, sharding tools) — product-market fit
4. Competitive signal (evaluating CockroachDB, PlanetScale) — active buyer
5. AI/ML signal (vector DB, LLM infra) — TiDB vector + HTAP opportunity
6. News signal (scaling challenges, data infra announcements)

For each recommended account: ICP score breakdown, top signal with source, recommended entry point (specific role + specific angle), and why now vs in 6 months.

**Inputs needed:** A list of company names, a vertical/territory description, or a prompt like "find 10 fintech companies in Southeast Asia building AI products."

**Outputs:** Scored and ranked account list with entry points and next actions per account.

---

### 6. SE: POC Plan

**Prompt:** `SYSTEM_SE_ANALYSIS` (+ `TIDB_EXPERT_CONTEXT`)
**Best for:** SE-led POC planning — structured proof-of-concept proposal with measurable success criteria.

**What it does:**

Produces a technical POC plan grounded in the prospect's specific stack and use case. Requires explicit confirmation of all assumptions before producing recommendations.

Outputs include:
- Technical maturity classification (Starter / Intermediate / Advanced)
- At least 3 measurable POC success criteria with specific thresholds (e.g., "P99 read latency <10ms at 5K TPS") — vague criteria are rejected
- Migration complexity rating (Low / Medium / High) with top 3 reasons, timeline estimate, and required resources
- MySQL compatibility caveats proactively flagged: stored procedures (limited), triggers (not supported), AUTO_INCREMENT semantics, full-text search limits, FK enforcement differences — with mitigation for each
- TiDB Cloud tier recommendation (Starter / Essential / Dedicated) with rationale
- AI/vector capability positioning when AI/ML workloads are detected

**`TIDB_EXPERT_CONTEXT` appended:** Full TiDB technical knowledge base covering vector search, HTAP architecture, TiFlash, TiCDC, TiProxy, distributed SQL internals, and the "database for AI agents" category — including agent memory systems, multi-agent coordination, and autonomous workflow use cases.

**Inputs needed:** Customer's current stack (MySQL version, approximate data volume, peak TPS), use case description, and any specific evaluation criteria they've mentioned.

---

### 7. SE: Architecture Fit

**Prompt:** `SYSTEM_SE_ANALYSIS` (+ `TIDB_EXPERT_CONTEXT`)
**Best for:** SE-led architecture fit analysis — assessing whether and how TiDB fits the prospect's workload and design.

**What it does:**

Same prompt as POC Plan, oriented toward architecture evaluation:
- Workload classification (OLTP / HTAP / hybrid / vector)
- Fit assessment with specific evidence from the customer's stack
- Architecture recommendation with explicit assumption flagging (e.g., "Assumption: customer is on MySQL 8.0 — confirm before migration estimate")
- Integration points: TiCDC for CDC, TiFlash for analytics, TiProxy for connection management
- Competitor comparison when alternatives are in the deal
- Proof points: benchmark links, named customer references in similar verticals, Jepsen results — not generic talking points

**Inputs needed:** Customer's tech stack, workload description, scale requirements.

---

### 8. SE: Competitor Coach

**Prompt:** `SYSTEM_SE_ANALYSIS` (+ `TIDB_EXPERT_CONTEXT`)
**Best for:** Preparing specific competitive counter-positioning for a deal where a named alternative is in play.

**What it does:**

Same prompt, oriented toward competitive analysis:
- Specific objection responses with TiDB proof points for the named competitor
- Head-to-head positioning: vs Aurora (write scaling + HTAP), vs CockroachDB (MySQL compat + columnar analytics), vs PlanetScale (self-hostable + HTAP + vector), vs Vitess (no middleware, native distributed SQL), vs YugabyteDB (MySQL compat, TiFlash columnar)
- Flags where TiDB's MySQL wire compatibility is a decisive advantage (zero app rewrite for MySQL/Vitess shops)
- AI/vector differentiation when the competitor lacks native vector search

**Inputs needed:** Competitor name, what the prospect has said about why they're considering it, and any known evaluation criteria.

---

### Prompt Chaining Pattern

These sections work best in sequence:

```
Pre-Call Intel  →  Call  →  Post-Call Analysis  →  Follow-Up Email
     ↓                            ↓
Market Research              SE: POC Plan
(territory level)          (if technical validation starts)
```

Oracle Chat is always available as a companion for ad-hoc questions within any workflow.

---

## Features by Role

All users can access all dashboards. Role determines default landing page.

### Oracle Chat (all roles)
- RAG-grounded answers with citations from the knowledge base
- Per-chat model selector: choose from GPT-5.4, o3-pro, o3, o4-mini, GPT-5.4 mini, and more
- Per-chat thinking depth: High / Medium / Low (reasoning models only)
- Per-chat KB and web search toggles
- AI Power score updates live as you change settings

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
- API key management: ZoomInfo, BuiltWith, and other optional connectors
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
| GitHub MCP | TiDB repo search for technical depth | SE |
| Crunchbase MCP | Funding and growth signals | Sales, Marketing |

---

## Key Functions Reference

### ChatOrchestrator (`services/chat_orchestrator.py`)

```python
class ChatOrchestrator:
    def run(*, mode: str, user: str, message: str,
            top_k: int, filters: dict, context: dict) -> tuple[dict, dict]
    # mode="oracle": RAG retrieval (when rag_enabled=True) + web_search_preview, adapts response style to question type
    # mode="call_assistant": QueryRewriter -> HybridRetriever -> LLM with evidence
    # mode="research": GTMModuleService dispatch (account briefs, POC plans, etc.)
    # Returns (response_dict, retrieval_payload)
```

### HybridRetriever v1 (`retrieval/service.py`)

```python
class HybridRetriever:
    def search(query: str, *, top_k: int = 8,
               filters: dict | None = None) -> list[RetrievedChunk]
    # 1. Vector: VEC_COSINE_DISTANCE(embedding, query_vec) LIMIT top_k*40
    # 2. Keyword: MATCH(chunk_text) AGAINST(:query IN NATURAL LANGUAGE MODE)
    # 3. Score: 0.50*vec + 0.30*kw + 0.10*title + source_bias + domain_boost
    # 4. Filter by source_type, account; dedup by chunk_id
```

### HybridRetrievalService v2 (`services/indexing/retrieval.py`)

```python
class HybridRetrievalService:
    def search(query: str, org_id: int, *, top_k: int = 8,
               filters: dict | None = None) -> list[RetrievedChunk]
    # TiDB Cloud: VEC_COSINE_DISTANCE() + MATCH AGAINST fulltext
    # Merge via Reciprocal Rank Fusion (RRF)
    # Multi-tenant: all queries scoped by org_id
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
    # Multi-client: OpenAI (primary) + Anthropic/MiniMax (fallback) + Codex (JWT auth)
    def answer_oracle(message, hits, *, model=None, tools=None,
                      allow_ungrounded=False) -> dict
    # Returns {answer, follow_up_questions}
    # Fallback: _local_oracle_synthesis() (lexical ranking + heuristic response)

    def answer_call_assistant(message, hits, *, model=None, tools=None) -> dict
    # Returns {what_happened, risks, next_steps, questions_to_ask_next_call}
```

### GTMModuleService (`services/gtm_modules.py`)

```python
class GTMModuleService:
    # 12+ role-specific AI modules:
    # Sales: rep_account_brief, rep_discovery_questions, rep_follow_up_draft, rep_deal_risk
    # SE: se_poc_plan, se_poc_readiness, se_architecture_fit, se_competitor_coach
    # Marketing: marketing_intelligence, marketing_battle_card
    # Each module: retrieves from knowledge_index -> LLM generation -> stores result
```

### Key SQL Queries

**TiDB vector search (production)**:
```sql
SELECT *, VEC_COSINE_DISTANCE(embedding, :query_vec) AS distance
FROM knowledge_index
WHERE org_id = :org_id
ORDER BY distance ASC
LIMIT 20
```

**TiDB fulltext search**:
```sql
SELECT *, MATCH(chunk_text) AGAINST(:query IN NATURAL LANGUAGE MODE) AS relevance
FROM knowledge_index
WHERE org_id = :org_id AND MATCH(chunk_text) AGAINST(:query IN NATURAL LANGUAGE MODE)
ORDER BY relevance DESC
LIMIT 20
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
    /api/routes        # FastAPI endpoints: chat, kb, rep, se, marketing, admin, auth, slack
    /core              # Settings, constants, auth
    /db                # SQLAlchemy base, session factory (TiDB Cloud), init_db
    /ingest            # Drive + Feishu + Chorus connectors and ingestors
    /models            # ORM models: v1 (kb_documents, kb_chunks, chorus_calls, etc.)
                       #              v2 (users, accounts, deals, knowledge_index, etc.)
    /prompts           # System prompt templates (oracle, call coach)
    /retrieval         # HybridRetriever v1
    /schemas           # Pydantic request/response contracts
    /services
      /chat_orchestrator.py  # RAG orchestration (oracle / call_assistant / research)
      /llm.py               # Multi-client LLM (OpenAI + Anthropic + Codex)
      /embedding.py          # Embedding service (OpenAI + hash fallback)
      /gtm_modules.py        # 12+ role-specific AI modules
      /messaging.py           # Email draft/send with domain guard rails
      /slack.py               # Webhook verification + async posting
      /audit.py               # Action logging
      /query_rewrite.py       # Query rewriting
      /token_crypto.py        # AES-256 encryption for stored keys
      /indexing/
        retrieval.py          # HybridRetrievalService v2 (TiDB-aware, RRF)
      /research/
        account_brief_researcher.py  # 7-section pre-call research
        postcall_pipeline.py         # Post-call action extraction
        refinement_service.py        # User feedback + effectiveness tracking
      /connectors/
        salesforce_sync.py    # CRM account/deal sync
        zoominfo.py           # ZoomInfo prospect enrichment
      /auth/
        google_oauth.py       # Google OAuth + PKCE
      /mcp/                   # 15 MCP server integrations
    /utils             # Chunking, redaction, hashing, email utils
  /alembic             # DB migrations (TiDB Cloud)
/workers               # Celery task definitions
/ui                    # Next.js 14 frontend (Sales / Marketing / SE dashboards)
/infra                 # Docker Compose: TiDB v8.5 + Redis + API + Worker + Beat + UI
/tests                 # Unit + integration tests
/data
  /fake_drive          # Local fixture documents (+ optional GitHub repos)
  /fake_chorus         # Local fixture call transcripts
/scripts               # Utility scripts (sync_github_sources, seed_sqlite_mvp, etc.)
/docs
  architecture.excalidraw  # System architecture diagram
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

---

## Account Intelligence Dashboard

A standalone TiDB-fit-scored account intelligence view at `/account-intelligence`, accessible from the main nav.

**How it works:**

All accounts are auto-populated from Chorus call history — no manual entry required. Selecting an account shows call notes, known contacts, deal stage, and team. Clicking **Generate TiDB Intelligence Profile** triggers the AI to research the company (web search + RAG) and produce a full profile.

**Generated profile includes:**
- TiDB Fit Score (0–10 dial) using the rule-based scoring system (MySQL +2.0, Oracle +1.8, AI/ML +1.5, etc.)
- Company overview with KPIs (employees, funding, ARR, founded)
- 4 pain points mapped to TiDB solutions (HTAP, MySQL wire compat, distributed arch)
- 5 buy signals with urgency indicators (high/medium/low)
- Tech stack breakdown with TiDB-compatible databases highlighted
- Target workloads (P1/P2 priority)
- Key contacts with engagement angles
- Personalized opening pitch referencing actual stack and scale
- Source links from research

**How existing data improves profiles:**
- Call meeting summaries are injected into the AI prompt as internal context
- Known contacts from Chorus participants seed the contact prompt
- Deal stage informs the urgency framing
- ZoomInfo (if connected) enriches firmographics in real time

**Files:**
```
ui/app/(app)/account-intelligence/page.js     Server component — fetches calls, groups by account
ui/components/AccountIntelligenceClient.js    Interactive dashboard (search, cards, profile renderer)
ui/app/api/account-intelligence/generate/route.js  AI profile generation endpoint
```

---

## ZoomInfo Per-Rep Authentication

ZoomInfo uses each rep's individual web account credentials (email + password) rather than a shared org API key. The backend exchanges credentials for a JWT via ZoomInfo's `/authenticate` endpoint and stores the token.

**Flow:**
1. Rep goes to Settings → Connected External Accounts → ZoomInfo → Connect
2. Enters their ZoomInfo email and password
3. Backend calls `https://api.zoominfo.com/authenticate`, gets a JWT
4. JWT stored as the rep's `access_token` in `connected_accounts`
5. AI uses the rep's token for all ZoomInfo lookups during their session

**ZoomInfo tools available to AI:**
- `zi_company_search(name)` — firmographics (industry, employees, revenue, HQ)
- `zi_person_search(name, company)` — contact enrichment (email, phone, title, LinkedIn)
- `zi_technographics(company_name)` — tech stack from ZoomInfo's data

Each tool call = 1 ZoomInfo credit, on-demand only (no background jobs or bulk pulls).

---

## Production Deployment (AWS EC2)

The primary production environment runs on a single AWS EC2 `t4g.small` (ARM64) with an Elastic IP and free HTTPS via sslip.io.

**Stack:** Caddy (reverse proxy + TLS) + Next.js UI + FastAPI + Celery Worker + Celery Beat + Redis

### Auto-Deploy

Every push to `main` triggers a GitHub Actions workflow that SSHes to EC2 and rebuilds the UI and API containers. Requires three GitHub repository secrets:

| Secret | Value |
|--------|-------|
| `EC2_HOST` | `100.49.55.13` |
| `EC2_USER` | `ec2-user` |
| `EC2_SSH_KEY` | Contents of your EC2 `.pem` key file |

Workflow file: `.github/workflows/deploy.yml`

### Manual Deploy

```bash
ssh ec2-user@<EC2_HOST>
cd ~/app && git pull
cd infra/aws && docker compose -f docker-compose.prod.yml up -d --build
```

To rebuild only the UI (faster when only frontend changed):
```bash
docker compose -f docker-compose.prod.yml up -d --build ui
```

### Initial EC2 Setup

```bash
# 1. Install Docker (Amazon Linux 2023)
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# Log out and back in

# 2. Clone repo
git clone https://github.com/stephenlthorn/gtm-copilot-oss.git ~/app
cd ~/app/infra/aws

# 3. Configure and launch
cp .env.example .env && nano .env
docker compose -f docker-compose.prod.yml up -d --build
```

### Key Config (`infra/aws/.env`)

```
DOMAIN=100.49.55.13.sslip.io
DATABASE_URL=mysql+pymysql://USER:PASS@gateway01.us-east-1.prod.aws.tidbcloud.com:4000/DB?ssl_verify_cert=true&ssl_verify_identity=true
ALLOWED_EMAIL_DOMAIN=pingcap.com
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
SECRET_KEY=<openssl rand -hex 32>
NEXTAUTH_SECRET=<openssl rand -hex 32>
FERNET_KEY=<python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
SECURITY_TRUSTED_HOST_ALLOWLIST=100.49.55.13.sslip.io,localhost,api
CORS_ALLOW_ORIGINS=https://100.49.55.13.sslip.io
```

**Google Cloud Console** — add these to your OAuth client's authorized redirect URIs:
```
https://<DOMAIN>/api/auth/exchange
https://<DOMAIN>/api/auth/callback/google
```
