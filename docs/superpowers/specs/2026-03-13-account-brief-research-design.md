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
async GTMModuleService.rep_account_brief()   ← must be async def
  ├── AccountBriefResearcher.research()      ← concurrent Firecrawl scraping
  │     ├── {website}                        → company_homepage
  │     ├── {website}/about                  → company_about
  │     ├── crunchbase.com/organization/{slug}  → crunchbase
  │     ├── stackshare.io/{slug}             → stackshare (tech stack signals)
  │     ├── linkedin.com/jobs/search?keywords={account_name}  → job_signals
  │     └── {linkedin_url}                   → prospect_profile (best-effort)
  │
  ├── _collect_hits()                        ← existing KB/transcript search
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
    prospect_profile: str = ""   # best-effort; LinkedIn often blocks

class AccountBriefResearcher:
    def __init__(self, connector: FirecrawlConnector) -> None: ...
    async def research(
        self,
        account_name: str,
        website: str | None,
        linkedin_url: str | None,
    ) -> AccountBriefContext: ...
```

**Implementation notes:**
- Takes a `FirecrawlConnector` instance (reuses existing connector, does not re-wrap `FirecrawlApp` directly)
- All URLs scraped concurrently via `asyncio.gather()`
- Each `connector.scrape_url()` call wrapped in `asyncio.to_thread()` (Firecrawl SDK is sync)
- Per-scrape timeout: 10 seconds via `asyncio.wait_for()`
- Each field capped at 2000 chars before passing to LLM
- Failures are silent — field stays `""`, LLM fills from parametric knowledge

**URL construction:**
- `company_homepage`: provided website, or skip
- `company_about`: `{website}/about`, or skip if no website
- `crunchbase`: `https://www.crunchbase.com/organization/{slug}` where `slug = re.sub(r"[^a-z0-9]+", "-", account_name.lower()).strip("-")`. **Note:** slug frequently won't match the real Crunchbase URL — treat as best-effort, 404s are expected and silently ignored.
- `stackshare`: `https://stackshare.io/{slug}` — same slug caveat applies
- `job_signals`: `https://www.linkedin.com/jobs/search/?keywords={quote(account_name)}&f_TPR=r604800`
- `prospect_profile`: provided `linkedin_url`, or skip. **Note:** LinkedIn actively blocks scrapers. Firecrawl may retrieve public profiles inconsistently. The LinkedIn URL is always passed to the LLM as a string even when scraping fails, so the LLM can draw on its training knowledge for well-known individuals.

---

## Changes to Existing Files

### `api/app/schemas/gtm_modules.py`
- Add `linkedin_url: str | None = None` to `RepAccountBriefRequest`
- `website: str | None = None` already exists

### `api/app/services/gtm_modules.py` — `rep_account_brief()`
- Change signature to `async def rep_account_brief(self, *, user, account, chorus_call_id, website, linkedin_url)`
- If `settings.firecrawl_api_key` is set, construct `FirecrawlConnector(settings.firecrawl_api_key)`, then `await AccountBriefResearcher(connector).research(account, website, linkedin_url)`
- Remove the inline `httpx` homepage scrape added in the previous session (superseded by `AccountBriefResearcher`)
- Pass `research_context=context` to `answer_rep_account_brief()`; remove `website_content=...` call-site argument

### `api/app/services/llm.py` — `answer_rep_account_brief()`
- Replace `website_content: str | None`, `account_industry`, `account_employee_count` params with `research_context: AccountBriefContext | None = None`
- Build user prompt context block: iterate over non-empty `AccountBriefContext` fields, each becomes a labeled section
- If `linkedin_url` is known but `prospect_profile` is empty, include `"Prospect LinkedIn URL: {url}"` in the prompt so the LLM can draw on training knowledge
- System prompt: *"Where source data is sparse, draw on your knowledge of this company and industry. If you have web access, use it to fill gaps."*

### `api/app/api/routes/rep.py`
- Route handler must be `async def` to `await` the now-async service call
- Pass `linkedin_url=req.linkedin_url` and `website=req.website` to `service.rep_account_brief()`

### `ui/components/RepExecutionWidget.js`
- Add `linkedin_url` state (empty string default)
- Add LinkedIn URL input field below website field, labeled "Prospect LinkedIn URL (optional)"
- Include `linkedin_url: linkedin_url.trim() || null` in `basePayload`

---

## Error Handling

| Scenario | Behavior |
|---|---|
| No `firecrawl_api_key` configured | Skip `AccountBriefResearcher`; LLM uses KB hits + parametric knowledge |
| Individual scrape fails (404, blocked, timeout) | Field stays `""`; other scrapes continue unaffected |
| LinkedIn profile blocked by Firecrawl | `prospect_profile = ""`; LinkedIn URL still passed to LLM as a string hint |
| Crunchbase/StackShare slug mismatch (404) | Expected common case; silent field failure |
| No website provided | Skip homepage + about; Crunchbase + StackShare still attempted |
| LLM returns invalid JSON | `_responses_json()` returns `None`; existing fallback template used |
| Account not in DB | `account_record = None`; metadata from request fields only |

---

## Known Limitations

- **LinkedIn scraping:** Will fail for most users due to LinkedIn's bot detection. Section 1 (Prospect Information) relies on LLM parametric knowledge unless the rep provides a name directly or Firecrawl successfully retrieves the profile.
- **Crunchbase/StackShare slug:** Auto-generated slug frequently mismatches real URLs. These sources provide value when they hit but 404s are the common path.
- **No dedicated prospect name input:** The prospect name currently comes only from the LinkedIn URL (if Firecrawl can read it) or from LLM inference. A future improvement would add explicit `prospect_name`/`prospect_title` fields to the request.

---

## What This Does NOT Change

- `ResearchSourceRunner` in `sources.py` — not touched (its bugs remain, separate concern)
- `PreCallReportGenerator` — not touched
- ZoomInfo, Salesforce, LinkedIn API connectors — not used
- No result caching — each brief generates fresh research

---

## MiniMax Web Search Fallback

The system prompt instructs: *"Where source data is sparse or a field is unknown, draw on your knowledge of this company and industry. If you have web access, search for missing details."* This surfaces MiniMax's built-in retrieval without requiring tool-call plumbing changes.

---

## Success Criteria

- All 7 sections populated with specific, non-generic content when website is provided
- Concurrent scraping completes in under 12 seconds total
- Individual scrape failure does not surface as an error to the user
- LLM output is valid JSON matching `RepAccountBriefResponse` schema
- Route handler and service method are both `async def` (no sync/async mismatch)
