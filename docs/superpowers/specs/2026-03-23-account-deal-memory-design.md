# Account Deal Memory — Design Spec

## Goal

Build a rolling per-account deal record that aggregates all calls (Chorus + manual) into a live MEDDPICC state, auto-updates after each call with rep review/approval, and feeds full account history into post-call analysis.

## Architecture

A new `account_deal_memory` table (keyed on account name) holds the live deal state. Manual calls are added to the existing `chorus_calls` table with `source_type="manual"`. After every call lands, a FastAPI BackgroundTask runs an LLM MEDDPICC delta extraction and writes it to a pending review slot. The rep approves via a diff UI. Post-call analysis always receives the full account memory as context.

## Tech Stack

Python/FastAPI, TiDB (MySQL dialect), SQLAlchemy, Alembic, Next.js, existing LLM service.

---

## Section 1 — Data Model

### New table: `account_deal_memory`

| Column | Type | Notes |
|---|---|---|
| `account` | VARCHAR(255) PK | Canonical key — stored lowercased and stripped |
| `deal_stage` | VARCHAR(128) nullable | e.g. "Discovery", "Technical Eval", "Negotiation" |
| `is_new_business` | BOOL default True | |
| `status` | VARCHAR(32) default "active" | active / closed_won / closed_lost / stalled |
| `meddpicc` | JSON | See MEDDPICC JSON schema below |
| `key_contacts` | JSON | `[{name, title, role, linkedin}]` |
| `tech_stack` | JSON | `{likely: [], possible: [], confirmed: [], unknown: []}` |
| `open_items` | JSON | `[{item, owner, due_date, priority}]` |
| `summary` | TEXT | Rolling 3–5 sentence account narrative, regenerated on every delta approval |
| `call_count` | INT default 0 | |
| `last_call_date` | DATE nullable | |
| `pending_review` | BOOL default False | True when AI proposed delta not yet approved |
| `pending_delta` | JSON nullable | Latest AI-proposed delta (see Delta JSON schema). Latest-wins if multiple calls land before review — known limitation |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

**Account canonicalization:** All account name lookups use `account.strip().lower()`. The stored value is always the lowercased, stripped form. This prevents "Brex" / "BREX" / "Brex " creating separate rows.

### MEDDPICC JSON schema

```json
{
  "metrics":         {"score": 0, "evidence": "", "missing": ""},
  "economic_buyer":  {"score": 0, "evidence": "", "missing": ""},
  "decision_criteria": {"score": 0, "evidence": "", "missing": ""},
  "decision_process":  {"score": 0, "evidence": "", "missing": ""},
  "identify_pain":   {"score": 0, "evidence": "", "missing": ""},
  "champion":        {"score": 0, "evidence": "", "missing": ""},
  "competition":     {"score": 0, "evidence": "", "missing": ""}
}
```

Scores: 0 = not yet assessed, 1–5 per rubric in system prompt.

### Delta JSON schema

```json
{
  "meddpicc_updates": {
    "metrics": {"score": 3, "evidence": "quote from call", "missing": "need dollar impact"},
    "champion": {"score": 2, "evidence": "...", "missing": "..."}
  },
  "key_contacts_add": [{"name": "Panos", "title": "Cloud Infra Lead", "role": "champion", "linkedin": ""}],
  "tech_stack_updates": {"confirmed": ["Vitess"], "likely": ["Aurora MySQL"]},
  "open_items_add": [{"item": "Send POC proposal", "owner": "rep", "due_date": "2026-03-28", "priority": "high"}],
  "deal_stage": "Discovery",
  "is_new_business": false,
  "summary": "Updated rolling summary..."
}
```

Only keys present in the delta are changed. Arrays in `key_contacts_add` and `open_items_add` are appended (not replaced). `meddpicc_updates` merges at element level (only keys present are updated). Approve endpoint applies this logic.

### Modified table: `chorus_calls`

Add column:

| Column | Type | Notes |
|---|---|---|
| `source_type` | VARCHAR(32) default "chorus" | "chorus" or "manual" |

Change `chorus_call_id`:
- Make nullable (`nullable=True`)
- Replace the simple UNIQUE constraint with a **partial unique index**: unique where `chorus_call_id IS NOT NULL`

Manual calls use `source_type="manual"`, `chorus_call_id=None`, generated UUID as `id`. `rep_email` is inferred from the authenticated session (request user email). All other pipeline steps (KBDocument indexing, artifact generation, delta pipeline) run unchanged.

### `call_artifacts` linkage for manual calls

For manual calls, `CallArtifact.chorus_call_id` stores the `chorus_calls.id` UUID string (since `chorus_call_id` is NULL). No schema change to `call_artifacts` is needed.

All call lookup code (routes and GTM modules) that currently does `WHERE chorus_call_id = :ref` must be updated to a two-step lookup:
1. Try `chorus_calls WHERE chorus_call_id = :ref` first
2. If no result, try `chorus_calls WHERE id = :ref` (covers manual calls accessed by UUID)

This applies to: `GET /calls/{chorus_call_id}`, `CallArtifact` lookups in `gtm_modules.py`, and `regenerate-draft`.

### `SourceType` enum

Manual calls use `SourceType.CHORUS` for KB indexing — no new enum value. The `source_type` column on `chorus_calls` is a plain VARCHAR, not tied to the `SourceType` enum.

---

## Section 2 — Update Pipeline

Triggered as a **FastAPI `BackgroundTasks`** task — fires after the call row is committed, non-blocking to the HTTP response.

**Step 1 — New vs existing detection** (priority order):
1. `chorus_calls.stage` populated → `is_new_business = False`
2. `account_deal_memory` row already exists for this account → `is_new_business = False`
3. Prior `chorus_calls` rows exist for this account (same canonical name) → `is_new_business = False`
4. Otherwise → `is_new_business = True`, create fresh `account_deal_memory` row with zeroed MEDDPICC

**Step 2 — MEDDPICC delta extraction**
LLM receives: (a) call transcript or notes, (b) current `account_deal_memory.meddpicc` snapshot as JSON, (c) instruction to produce a delta in the Delta JSON schema above. Returns structured JSON only.

**Step 3 — Write to pending state**
Delta written to `account_deal_memory.pending_delta`. `pending_review = True`. `call_count` and `last_call_date` updated immediately (not gated on review). Live MEDDPICC/contacts/tech_stack/open_items/summary are NOT changed until approved.

**Step 4 — Rep review**
Post-call UI shows yellow banner when `pending_review=True`: "Account memory updated — review proposed changes." Side panel shows diff: current vs proposed per field. Rep can:
- **Approve** — merges delta into live fields using the merge logic defined in Delta JSON schema. `pending_review = False`, `pending_delta = None`. Summary regenerated.
- **Edit then approve** — rep edits fields in the diff panel before approving.
- **Dismiss** — `pending_review = False`, `pending_delta = None`, live fields unchanged.

**Step 5 — Context injection into post-call analysis**
When post-call analysis runs, the full committed `account_deal_memory` snapshot is prepended to the LLM prompt as account history context: deal stage, MEDDPICC current state, contacts, tech stack, open items, summary, call count.

---

## Section 3 — Manual Call Input

### `POST /calls/manual`

Request body:
```json
{
  "account": "Brex",
  "date": "2026-03-23",
  "participants": ["panos@brex.com"],
  "stage": "Discovery",
  "notes": "Free-text — rep notes, copied transcript, voice memo transcription"
}
```

Required: `account`, `notes`. Optional: `date` (defaults to today), `participants`, `stage`.

`rep_email` is taken from the `X-User-Email` request header — the same pattern used throughout the codebase (see `_request_user_email` in `api/app/api/routes/admin.py`). Not a request body field.

On receipt:
1. Canonicalize account name (`strip().lower()`)
2. Create `chorus_calls` row: `source_type="manual"`, `id=uuid4()`, `chorus_call_id=None`, `rep_email` from session
3. Index notes as `KBDocument` + `KBChunks` with `SourceType.CHORUS` (reuses existing pipeline)
4. Generate `call_artifact` from notes via LLM
5. Trigger MEDDPICC delta pipeline as BackgroundTask

---

## Section 4 — API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/calls/manual` | Log a manual call |
| `GET` | `/accounts/{account}/memory` | Fetch current account deal memory (account param is canonicalized) |
| `POST` | `/accounts/{account}/memory/approve` | Approve pending delta — optional body `{edits: <partial delta JSON>}` for rep edits before approving |
| `PATCH` | `/accounts/{account}/memory` | Direct rep edit. Partial updates allowed. Accepted fields: `deal_stage`, `status`, `is_new_business`, `meddpicc` (element-level merge), `key_contacts` (full replace), `tech_stack` (full replace), `open_items` (full replace). Does not touch `pending_delta` or `pending_review`. |

**Auth:** All endpoints read `X-User-Email` header for `rep_email` (same pattern as `_request_user_email` in `admin.py`). Single-tenant — all reps share account deal memory. No per-user filter on reads.

**`GET /calls/{call_ref}` for manual calls:** The existing route must be updated to try `chorus_call_id = call_ref` first, then fall back to `id = call_ref`. The UI uses the call's UUID as the link target for manual calls.

---

## Section 5 — UI

### Post-call review banner
Yellow banner when `pending_review=True`: "Account memory updated for [Account] — review proposed changes." Opens side panel with current vs proposed diff per field.

### Account memory page (`/accounts`)
Per-account view:
- Deal stage + status badge (active / stalled / closed_won / closed_lost)
- New business vs existing flag
- MEDDPICC scorecard (score 1–5, evidence quote, missing note per element)
- Key contacts list
- Tech stack tiers (Likely / Possible / Confirmed / Unknown)
- Open items table (item, owner, due date, priority)
- Rolling summary paragraph
- Call history (Chorus + manual, date + rep + outcome)

### Manual call log
"Log call manually" button in Calls panel → modal with account, date, participants (optional), stage dropdown (optional), large notes textarea.

---

## Out of Scope

- Salesforce / CRM sync
- Automatic email sending after call
- Multi-user conflict resolution on pending delta (latest-wins is the defined behaviour)
- Per-element partial approval (approve all or nothing per delta)
