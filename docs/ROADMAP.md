# GTM Copilot — Product Roadmap

**Updated:** 2026-03-20
**Stack:** Next.js · FastAPI · TiDB Cloud Serverless · OpenAI Responses API

---

## Current State (✅ Live in main)

- Google Drive + Feishu knowledge base sync (4,431 docs indexed)
- Oracle chat with RAG retrieval (vector + lexical hybrid)
- Chorus call ingestion + call assistant mode
- Per-user model selector + reasoning effort overrides
- AI feedback coaching loop (thumbs up/down → RAG injection)
- Web search intelligence source profiles
- TiDB Cloud Serverless backend (vector search via `VEC_COSINE_DISTANCE`)
- Audit logging, guardrails, internal-only messaging policy

---

## Phase 1 — Sales Rep Workflow (Pre-call → Call → Post-call → POC → Close)

**Goal:** Ship a v1 to live sales reps on Vercel. Focus entirely on the rep journey.

### 1.1 Data Sources

| Source | Integration | Priority |
|--------|-------------|----------|
| Chorus | ✅ Done — call transcripts + artifacts | Live |
| ZoomInfo | Company/contact enrichment API | High |
| Salesforce | Opportunity stage, close date, ARR, history | High |
| LinkedIn (via scrape/API) | Prospect profile enrichment | Medium |
| 6sense / Bombora | Intent signal injection | Low |

**ZoomInfo integration plan:**
- `api/app/connectors/zoominfo.py` — company + person lookup by domain/name
- New `zoominfo_enrichments` table — cached enrichments (TTL 7 days)
- Enrich account context automatically when rep opens a call/account view
- Surface in oracle context: company size, tech stack, funding, key contacts

**Salesforce integration plan:**
- `api/app/connectors/salesforce.py` — OAuth2 connected app
- Pull: opportunity name, stage, ARR, close date, account owner, next steps
- New `salesforce_opportunities` table — synced on demand or nightly
- Used in pre-call brief and POC readiness scoring

### 1.2 Rep Workflow Modules

#### Pre-call Brief
**Endpoint:** `GET /rep/pre-call-brief?account=X`
**Returns:** Account summary · key contacts · open opportunities · recent activity · suggested talk tracks · competitive context
**Sources:** ZoomInfo + Salesforce + Drive KB + Chorus history
**UI:** `PreCallBriefWidget.js` — one-click brief on account name

#### Live Call Assistant (exists, enhance)
**Enhancements:**
- Real-time objection surfacing with suggested responses
- Competitive battle card injection when competitor mentioned
- "Next best question" suggestions based on conversation stage
- Auto-detect deal stage from transcript language

#### Post-call Summary + Follow-up
**Endpoint:** `POST /rep/post-call` (extends existing `CallArtifact`)
**Returns:** Summary · action items · email draft · Slack message draft · CRM update suggestion
**UI:** `PostCallWidget.js` — shown after call ends, one-click send

#### POC Kit & Readiness
**Endpoint:** `POST /rep/poc-readiness` (extends existing `GTMPOCPlan`)
**Enhancements:**
- Pull SE availability from calendar (Google Calendar API)
- Generate POC success criteria from conversation history
- Track POC milestone completion
- `POCKitWidget.js` — visual checklist with doc links

#### Closing Steps
**Endpoint:** `POST /rep/closing-brief?opportunity=X`
**Returns:** Mutual action plan · legal/security checklist · champion letter template · risk flags
**UI:** `ClosingWidget.js`

### 1.3 Vercel Deployment

- [ ] Add `vercel.json` with API proxy rewrites
- [ ] Set env vars in Vercel dashboard (API_BASE_URL, OPENAI_API_KEY, session secret, TiDB creds)
- [ ] Configure Google OAuth callback URL for Vercel domain
- [ ] Set `NEXTAUTH_URL` / `NEXT_PUBLIC_APP_URL` for production domain
- [ ] Add `TIDB_SSL_CA` cert to Vercel env (base64 encoded)
- [ ] Smoke test all routes post-deploy

---

## Phase 2 — SE Dashboard + Feishu (While Phase 1 is in Prod)

**Goal:** SE-specific views + Feishu as primary knowledge source for China team.

### 2.1 SE Dashboard

**Modules:**
- **Account health** — risk signals, replication lag alerts, POC status
- **Technical prep** — architecture review, known issues, relevant docs surfaced
- **PoC tracker** — milestone view across all active POCs
- **Competitive intel** — latest battlecard updates, win/loss analysis
- **TiDB expert mode** — deep technical Q&A with systems tables, HTAP, TiFlash context

**New routes:**
- `GET /se/dashboard?se_email=X` — aggregated view
- `GET /se/account-health/:account` — risk signals + POC status
- `POST /se/tech-prep` — pre-meeting technical brief

### 2.2 Feishu Integration (China Team)

- Feishu OAuth already scaffolded — complete the sync pipeline
- `api/app/ingest/feishu_ingestor.py` — mirror of drive_ingestor pattern
- Handle Feishu doc formats: wiki pages, sheets, files
- Bilingual search (Chinese + English) — ensure embeddings handle CJK
- Map Feishu spaces → KB folders with permission inheritance

### 2.3 Additional Intelligence Sources

| Source | Use Case |
|--------|----------|
| G2 / TrustRadius | Competitive reviews, customer sentiment |
| TiDB blog / changelog | Product updates injected into oracle |
| GitHub issues (pingcap/tidb) | Known bugs for SE technical prep |
| Internal Notion/Confluence | Runbooks, escalation paths |

---

## Phase 3 — Production Hardening + Analytics

**Goal:** Make it reliable and measurable at scale.

- Feedback analytics dashboard — track correction frequency by topic
- Response quality scoring — thumbs up/down rate per module
- Usage analytics — most asked questions, coverage gaps
- Multi-tenant support — per-workspace TiDB schema isolation
- Rate limiting + per-user quotas
- Admin dashboard improvements — model cost tracking, latency p99
- Incremental Drive sync — delta sync on schedule (not full re-index)
- Webhook-based Chorus sync — real-time vs nightly batch

---

## Immediate Next Actions

1. **Vercel deploy** — get Phase 1 live for reps
2. **ZoomInfo connector** — company enrichment for pre-call brief
3. **Salesforce connector** — opportunity data for close/POC modules
4. **`PreCallBriefWidget`** — first new rep-facing UI module
5. **SE Dashboard v1** — aggregate view for SEs

---

## Architecture Notes

- All new connectors follow the `BaseConnector` pattern in `api/app/connectors/`
- New data sources get their own ingestor (like `drive_ingestor.py`) or direct DB table
- All new LLM calls go through `LLMService` — never direct OpenAI calls in routes
- New UI widgets follow the `'use client'` pattern with SWR for data fetching
- Every new module gets an audit log entry via `GTMModuleRun`
