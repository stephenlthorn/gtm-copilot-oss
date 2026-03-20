# GTM Copilot: Chat Workspace + Template System Design

**Date:** 2026-03-20
**Status:** Approved for implementation planning
**Scope:** URL restructure, unified chat workspace, section picker with populate flow, persistent chat history in TiDB, per-user template system in settings

---

## 1. Overview

Replace the current multi-page Sales Rep widget with a single persistent chat workspace at `/chat`. The left panel becomes a section picker with dynamic input fields and a Populate button that drafts filled templates into the chat input. The right panel is a persistent, growing chat thread (stored in TiDB) shared with Oracle. Settings gains a full template management section.

---

## 2. URL / Routing

| Route | Behaviour |
|---|---|
| `/chat` | Main workspace (replaces `/rep`) |
| `/settings` | Settings page (unchanged path) |
| `/se`, `/oracle`, `/rep` | Redirect → `/chat` |
| `/` (authenticated) | Redirect → `/chat` |
| `/` (unauthenticated) | Redirect → `/login` |

**Auth exchange** (`ui/app/api/auth/exchange/route.js`): change post-login redirect from `/rep` to `/chat`.

---

## 3. Left Panel — Section Picker

A single dropdown at the top of the left panel controls which section is active. Only that section's fields are visible.

### Sections & Fields

| Section Key | Display Name | Fields |
|---|---|---|
| `pre_call` | Pre-Call Intel | Account Name, Website, Prospect Name, LinkedIn URL |
| `post_call` | Post-Call Analysis | Account Name, Call selector (multi-select) |
| `follow_up` | Follow-Up Email | Account Name, Call selector, To, CC, Email Tone |
| `tal` | Market Research / TAL | Account Name, Regions, Industry, Revenue Min/Max, Context, Top N |
| `se_poc_plan` | SE: POC Plan | Account Name, Target Offering, Call selector |
| `se_arch_fit` | SE: Architecture Fit | Account Name, Call selector |
| `se_competitor` | SE: Competitor Coach | Account Name, Competitor, Call selector |

### Populate Button

Each section has a **Populate** button at the bottom of its fields.

Clicking Populate:
1. Reads the active section's template (user's custom if set, else default)
2. Substitutes `{field_name}` placeholders with the values from the input fields (e.g. `{account}` → "Acme Corp")
   - **Empty fields**: left as visible markers, e.g. `{account}` stays as `[account]` in the output so the user can see what's missing
   - **Account Name** is the only required field — Populate is disabled (button grayed) if account is blank
3. For sections with a call selector: calls the existing `/api/calls/{id}` endpoint to resolve each selected call into a short summary string that replaces `{call_context}`. If no call is selected, `{call_context}` renders as `[no call selected]`
4. Places the resulting text into the **chat input textarea** on the right (as an editable draft)
5. Does NOT send — user reads, edits, then hits Send

### Template Picker (above Populate)

A secondary dropdown below the section picker: **"Template:"** — lists `Default` plus any user who has saved a custom template for this section key. Selecting a different user's template uses theirs for the next Populate action.

Custom templates created with a new `section_key` (from Settings) only appear in the picker when the section dropdown is set to a matching key. They do not appear in the picker for a different section's built-in fields — they are standalone templates the user invokes by switching the section dropdown to that custom key.

---

## 4. Right Panel — Persistent Chat

### Chat Thread

- One thread per user (single global thread, extendable to per-account threads later)
- Stored in TiDB `chat_messages` table
- Loaded from backend on page mount (last 100 messages)
- Each sent message auto-persists
- Populate appends draft to input; Send appends message to thread

### Input Area

- Large editable textarea (minimum 4 rows, grows to 10)
- Enter = send, Shift+Enter = newline
- When Populate fires, the textarea is set to the filled template text (user can then edit before sending)
- Send posts to Oracle (`POST /api/oracle` with `mode: 'oracle'`)

### Message Rendering

Existing chat message components (BriefMsg, RiskMsg, etc.) are removed — all outputs are plain Oracle responses since the LLM now fills everything in. Messages render as:
- **User messages**: right-aligned, styled bubble, shows the prompt text
- **Assistant messages**: left-aligned, markdown-rendered Oracle response
- **Loading**: thinking dots animation
- **Error**: error bubble

---

## 5. Template System

### Storage

New DB table `user_templates`:

```sql
CREATE TABLE user_templates (
  id          CHAR(36) PRIMARY KEY,
  user_email  VARCHAR(255) NOT NULL,
  section_key VARCHAR(64) NOT NULL,
  template_name VARCHAR(128) NOT NULL,
  content     TEXT NOT NULL,
  is_default  BOOLEAN DEFAULT FALSE,
  updated_at  DATETIME NOT NULL,
  UNIQUE KEY uq_user_section (user_email, section_key),
  INDEX idx_user_templates_section (section_key)
);
```

`is_default = TRUE` rows have `user_email = 'system'` and are seeded, never editable. Each real user can have one custom row per section key (enforced by the `UNIQUE KEY`). `PUT /user/templates/{section_key}` uses `INSERT ... ON DUPLICATE KEY UPDATE content = ...`.

### API Routes

**Backend (FastAPI):**
- `GET /user/templates` — returns authenticated user's templates (all sections)
- `PUT /user/templates/{section_key}` — upsert user's custom template for a section
- `GET /templates/all` — returns all users' custom templates (for the picker dropdown); response includes `user_email`, `section_key`, `template_name`, `content`

**Frontend proxies (Next.js):**
- `ui/app/api/user/templates/route.js` — GET/PUT proxy
- `ui/app/api/templates/all/route.js` — GET proxy

### Default Templates

Seeded at startup. Placeholders use `{curly_brace}` syntax.

**`pre_call`** — Pre-Call Intel:
```
I'm preparing for a call with {prospect_name} at {account} ({website}).

Please provide:
1. Company overview and recent news for {account}
2. LinkedIn background on {prospect_name}: {prospect_linkedin}
3. Technology stack signals (database, infrastructure)
4. Funding, headcount, and growth trajectory
5. Likely pain points relevant to TiDB
```

**`post_call`** — Post-Call Analysis:
```
I just completed a call with {account}. Here are the call details: {call_context}

Please analyze and produce:
1. **Call Summary** — key topics discussed, decisions made
2. **Next Steps** — agreed actions with owners (Rep, SE, Prospect)
3. **Action Items** — broken out per person: Rep / SE / {account} contact
4. **MEDDPICC Analysis** — for each element (Metrics, Economic Buyer, Decision Criteria, Decision Process, Paper Process, Implicate Pain, Champion, Competition): what was established vs. what is missing
5. **Qualification Assessment** — is this deal actually qualified? What are the top 3 gaps to close?
```

**`follow_up`** — Follow-Up Email:
```
Draft a follow-up email for my call with {account}.

Recipients: To: {email_to} | CC: {email_cc}
Tone: {email_tone}
Call context: {call_context}

Include: summary of what was discussed, agreed next steps with owners, clear CTA for the next meeting.
```

**`tal`** — Market Research / TAL:
```
Build a target account list for the following criteria:
- Regions: {regions}
- Industry: {industry}
- Revenue range: ${revenue_min}M – ${revenue_max}M
- Reference account: {account}
- Additional context: {context}

Return the top {top_n} accounts most likely to need TiDB. For each: company name, why they're a fit, estimated revenue, and key signal.
```

**`se_poc_plan`** — SE: POC Plan:
```
Create a technical POC evaluation roadmap for {account}.
Offering: {target_offering}
Call context: {call_context}

Include: POC objectives, success criteria, technical requirements, 4-week milestone plan, resources needed, risk factors.
```

**`se_arch_fit`** — SE: Architecture Fit:
```
Analyze TiDB architecture fit for {account}.
Call context: {call_context}

Cover: current database signals, scalability pain, MySQL/Oracle compatibility needs, HTAP potential, migration complexity, TiDB placement recommendation.
```

**`se_competitor`** — SE: Competitor Coach:
```
Competitor coaching for {account} — primary competitor: {competitor}.
Call context: {call_context}

Provide: competitive positioning vs {competitor}, top 5 objections and TiDB responses, where TiDB wins and where to be careful, recommended proof points.
```

### Settings UI — Templates Section

New section in `ui/app/(app)/settings/page.js`: **"Templates"**

Contains a `TemplatesPanel` component:
- Tabs across the top for each section key (Pre-Call, Post-Call, Follow-Up, TAL, SE: POC Plan, SE: Arch Fit, SE: Competitor)
- Each tab shows:
  - **Default** (read-only code block showing system template)
  - **My Custom** (editable textarea, Save button — persists to DB)
  - **Use another user's template:** dropdown listing all users with a custom template for this section (selecting one loads their content into the editor for adoption/forking)
- A **+ New Template** button lets users create templates with a custom `section_key` and name — these appear in the Template Picker on `/chat`

---

## 6. Persistent Chat History

### Storage

New DB table `chat_messages`:

```sql
CREATE TABLE chat_messages (
  id          CHAR(36) PRIMARY KEY,
  user_email  VARCHAR(255) NOT NULL,
  role        VARCHAR(16) NOT NULL,  -- 'user' | 'assistant'
  content     TEXT NOT NULL,
  created_at  DATETIME NOT NULL,
  INDEX idx_chat_messages_user_created (user_email, created_at)
);
```

### API Routes

**Backend:**
- `GET /chat/history?limit=100` — returns last N messages for authenticated user, ordered `created_at ASC`
  - Response: `[{ id, role, content, created_at }]`
- `POST /chat` — existing Oracle endpoint (`api/app/api/routes/chat.py`); extend to also write both the user message and the assistant response to `chat_messages` before returning. Request shape: `{ mode, message, top_k }`. Response shape: `{ answer: string, citations: [{title, url, score}] }`.

**Frontend proxy:**
- `ui/app/api/chat/history/route.js` — GET proxy
- The existing `ui/app/api/oracle/route.js` proxies to `POST /chat` — no new proxy needed for sending

**Citations rendering in PersistentChat:** if the Oracle response includes `citations`, render them as a collapsed "Sources" disclosure below the assistant message (list of title + URL links).

### Behaviour

- On `/chat` page mount: fetch history, render in chat panel
- On send: optimistically add user message to UI, POST to Oracle, append assistant response
- Both user and assistant messages saved to `chat_messages`
- No localStorage dependency for chat (can be removed)

---

## 7. Migration: New DB Table

New Alembic migration `api/alembic/versions/20260320_000001_add_templates_and_chat_history.py`:
- Creates `user_templates` table
- Creates `chat_messages` table
- Seeds default templates (`is_default = TRUE`) for all 7 section keys

---

## 8. Component Map

| New / Changed | What it does |
|---|---|
| `ui/app/(app)/chat/page.js` | New main workspace page (replaces rep) |
| `ui/components/ChatWorkspace.js` | Full split layout — section picker left, chat right |
| `ui/components/SectionPicker.js` | Dropdown + dynamic field panels + Populate button |
| `ui/components/SectionFields/PreCallFields.js` | Fields for pre_call section |
| `ui/components/SectionFields/PostCallFields.js` | Fields for post_call section |
| `ui/components/SectionFields/FollowUpFields.js` | Fields for follow_up section |
| `ui/components/SectionFields/TalFields.js` | Fields for tal section |
| `ui/components/SectionFields/SEPocPlanFields.js` | Fields for se_poc_plan section |
| `ui/components/SectionFields/SEArchFitFields.js` | Fields for se_arch_fit section |
| `ui/components/SectionFields/SECompetitorFields.js` | Fields for se_competitor section |
| `ui/components/PersistentChat.js` | Chat panel — loads history, sends messages, renders thread |
| `ui/components/TemplatesPanel.js` | Settings template editor component |
| `ui/app/(app)/rep/page.js` | Redirect → `/chat` |
| `ui/app/(app)/se/page.js` | Redirect → `/chat` |
| `ui/app/(app)/oracle/page.js` | Redirect → `/chat` |
| `ui/app/(app)/settings/page.js` | Add Templates section (TemplatesPanel imported as `'use client'` leaf component) |
| `ui/app/api/chat/history/route.js` | New proxy |
| `ui/app/api/user/templates/route.js` | New proxy (GET/PUT) |
| `ui/app/api/templates/all/route.js` | New proxy (GET) |
| Backend: `api/app/api/routes/templates.py` | Template CRUD |
| Backend: `api/app/api/routes/chat.py` | Extend to persist messages |
| Backend: `api/app/models/entities.py` | Add UserTemplate, ChatMessage models |
| Alembic migration | Two new tables + seed data |

---

## 9. Out of Scope (explicit YAGNI)

- Multiple named chat threads per user (single thread to start)
- Template versioning / history
- Template sharing controls (all custom templates readable by all users)
- RAG injection of chat history into Oracle context (separate feature)
- The legacy "Generate" action buttons (replaced entirely by Populate + Oracle)

---

## 10. Implementation Order

1. DB migration (tables + seed)
2. Backend: template routes + chat history persistence
3. Frontend: `/chat` page + ChatWorkspace + PersistentChat
4. Frontend: SectionPicker + SectionFields
5. Frontend: template resolution + Populate logic
6. Frontend: Settings TemplatesPanel
7. URL redirects + auth exchange update
