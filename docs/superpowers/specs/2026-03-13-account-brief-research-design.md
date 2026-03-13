# Account Brief Research — Design Spec

**Date:** 2026-03-13
**Status:** Approved
**Scope:** Firecrawl-powered 7-section pre-call research report

---

## Problem

The current account brief generates a 3-sentence LLM summary from KB transcript hits only. It does zero web research, does not know the prospect's name or background, and produces generic output that is not useful for pre-call preparation.

---

## Goal

When a rep clicks "Generate Account Brief", the system autonomously researches the prospect and company across multiple web sources, then uses the LLM to synthesize a complete 7-section pre-call brief that is specific, evidence-backed, and immediately actionable.

---

## 7-Section Output

1. **Prospect Information** — Name, title, tenure at company, previous role/company
2. **Company Context** — Employee count, revenue range, industry, product/service, key competitors
3. **Current Architecture Hypothesis** — Databases, apps/microservices, cloud/infra (inferred from job postings and StackShare)
4. **Pain Hypothesis** — At least 2 specific pains with evidence
5. **TiDB Value Propositions** — Each pain matched to a specific TiDB value prop
6. **Meeting Goal** — Desired outcome of the next meeting
7. **Meeting Flow Agreement** — Who does introductions, discovery, tech questions, next steps; time allocation

---

## Data Flow

```
UI (RepExecutionWidget)
  account_name + website + linkedin_url + chorus_call_id
       │
       ▼
POST /api/rep/account-brief  →  RepAccountBriefRequest
       │
       ▼
GTMModuleService.rep_account_brief()
  ├── AccountBriefResearcher.research()    ← concurrent Firecrawl scraping
  │     ├── {website}                      → company_homepage
  │     ├── {website}/about                → company_about
  │     ├── crunchbase.com/organization/{slug}  → crunchbase
  │     ├── stackshare.io/{slug}           → stackshare (tech stack signals)
  │     ├── linkedin.com/jobs/search?keywords={account_name}  → job_signals
  │     └── {linkedin_url}                 → prospect_profile
  │
  ├── _collect_hits()                      ← existing KB/transcript search
  │
  └── LLMService.answer_rep_account_brief()
        inputs: AccountBriefContext + KB hits + account metadata
        output: 7-section JSON → RepAccountBriefResponse
```

---

## New Component: `AccountBriefResearcher`

**File:** `api/app/services/research/account_brief_researcher.py`

```python
@dataclass
class AccountBriefContext:
    company_homepage: str = ""
    company_about: str = ""
    crunchbase: str = ""
    stackshare: str = ""
    job_signals: str = ""
    prospect_profile: str = ""

class AccountBriefResearcher:
    def __init__(self, firecrawl_key: str) -> None: ...
    async def research(
        self,
        account_name: str,
        website: str | None,
        linkedin_url: str | None,
    ) -> AccountBriefContext: ...
```

- All URLs scraped concurrently via `asyncio.gather()`
- Each scrape wrapped in `asyncio.to_thread()` (Firecrawl SDK is sync)
- Per-scrape timeout: 10 seconds via `asyncio.wait_for()`
- Each field capped at 2000 chars before passing to LLM
- Failures are silent — field stays empty, LLM fills from parametric knowledge

**URL construction:**
- `company_homepage`: provided website or skip
- `company_about`: `{website}/about` or skip
- `crunchbase`: `https://www.crunchbase.com/organization/{slug}` where slug = `re.sub(r"[^a-z0-9]+", "-", account_name.lower())`
- `stackshare`: `https://stackshare.io/{slug}`
- `job_signals`: `https://www.linkedin.com/jobs/search/?keywords={quote(account_name)}&f_TPR=r604800` (jobs posted in last week)
- `prospect_profile`: provided `linkedin_url` or skip

---

## Changes to Existing Files

### `api/app/schemas/gtm_modules.py`
- Add `linkedin_url: str | None = None` to `RepAccountBriefRequest`
- `website: str | None = None` already added in previous session

### `api/app/services/gtm_modules.py` — `rep_account_brief()`
- Accept `linkedin_url` param
- If `settings.firecrawl_api_key` is set, instantiate `AccountBriefResearcher` and `await researcher.research(...)`
- Pass resulting `AccountBriefContext` to `answer_rep_account_brief()`
- Remove the inline `httpx` homepage scrape added in previous session (replaced by `AccountBriefResearcher`)

### `api/app/services/llm.py` — `answer_rep_account_brief()`
- Accept `research_context: AccountBriefContext | None = None`
- Build context block from research: each non-empty field becomes a labeled section in the user prompt
- System prompt instruction: *"Where source data is sparse, draw on your knowledge of this company and industry. Use web access if available to fill gaps."*
- Remove `website_content` param (now comes via `AccountBriefContext`)

### `api/app/api/routes/rep.py`
- Pass `linkedin_url=req.linkedin_url` to `service.rep_account_brief()`

### `ui/components/RepExecutionWidget.js`
- Add `linkedin_url` state
- Add LinkedIn URL input field (below website field)
- Include `linkedin_url` in `basePayload`

---

## Error Handling

| Scenario | Behavior |
|---|---|
| No `firecrawl_api_key` configured | Skip `AccountBriefResearcher`; LLM uses KB hits + parametric knowledge |
| Individual scrape fails (404, blocked, timeout) | Field stays `""`; other scrapes continue |
| LinkedIn profile blocked by Firecrawl | `prospect_profile = ""`; LLM infers from name if provided |
| No website provided | Skip homepage + about; Crunchbase + StackShare still run |
| LLM returns invalid JSON | Existing `_responses_json()` returns `None`; fallback template used |
| Account not in DB | `account_record = None`; metadata sourced from request fields only |

---

## What This Does NOT Change

- `ResearchSourceRunner` in `sources.py` — not touched (its bugs remain, separate concern)
- `PreCallReportGenerator` — not touched
- ZoomInfo, Salesforce, LinkedIn API connectors — not used
- No result caching — each brief generates fresh research

---

## MiniMax Web Search Fallback

The system prompt instructs: *"Where source data is sparse or a field is unknown, draw on your knowledge of this company and industry. If you have web access, search for missing details."* This surfaces MiniMax's built-in retrieval for gaps without requiring tool-call plumbing changes.

---

## Success Criteria

- All 7 sections populated with specific, non-generic content when website + LinkedIn URL provided
- Concurrent scraping completes in under 12 seconds total
- Individual scrape failure does not surface as an error to the user
- LLM output is valid JSON matching `RepAccountBriefResponse` schema
