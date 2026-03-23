# Prompt Studio — Design Spec

**Date:** 2026-03-23
**Status:** Approved
**Scope:** Full prompt management system with UI editor, version history, TiDB Expert skill, and prompt quality overhaul

---

## 1. Overview

GTM Copilot's prompts (system prompts, section templates, personas, source profiles, and the TiDB Expert knowledge base) are currently hardcoded in Python files on the API side. This design introduces a **Prompt Studio** — a full prompt management system accessible from the Settings page — that makes every prompt editable, versionable, and customizable per-user.

### Goals
- Surface all 24+ prompts in a single UI for editing
- Version history with diffs and one-click rollback
- Per-user persona overrides (Sales, SE, Marketing can each customize their view)
- TiDB Expert as a loadable skill (Claude-style: full content injected on-demand)
- Overhaul every prompt for production-grade quality
- Factory defaults as a safety net (always restorable)

---

## 2. Prompt Inventory

### System Prompts (11)
| Key | Name | Used By |
|-----|------|---------|
| `system_oracle` | Oracle | General chat |
| `system_pre_call_intel` | Pre-Call Intel | Pre-call section |
| `system_post_call_analysis` | Post-Call Analysis | Post-call + follow-up sections |
| `system_se_analysis` | SE Analysis | All SE sections |
| `system_call_coach` | Call Coach | Call coaching |
| `system_messaging_guardrail` | Messaging Guardrail | Email send/draft |
| `system_market_research` | Market Research | TAL section |
| `system_rep_execution` | Rep Execution | Rep automation |
| `system_se_execution` | SE Execution | SE automation |
| `system_marketing_execution` | Marketing Execution | Marketing automation |
| `tidb_expert` | TiDB Expert Skill | Injected when toggle is on |

### Section Templates (7)
| Key | Name |
|-----|------|
| `pre_call` | Pre-Call Intel |
| `post_call` | Post-Call Analysis |
| `follow_up` | Follow-Up Email |
| `tal` | Market Research / TAL |
| `se_poc_plan` | SE: POC Plan |
| `se_arch_fit` | SE: Architecture Fit |
| `se_competitor` | SE: Competitor Coach |

### Personas (3)
| Key | Name |
|-----|------|
| `persona_sales` | Sales |
| `persona_se` | SE |
| `persona_marketing` | Marketing |

### Source Profiles (3)
| Key | Name |
|-----|------|
| `sources_pre_call` | Pre-Call Sources (13 sources) |
| `sources_post_call` | Post-Call Sources |
| `sources_poc_technical` | POC Technical Sources |

---

## 3. Data Model

### Table: `prompt_registry`
| Column | Type | Description |
|--------|------|-------------|
| `id` | VARCHAR PK | Unique prompt key (e.g., `system_oracle`) |
| `category` | ENUM | `system_prompt`, `template`, `persona`, `source_profile` |
| `name` | VARCHAR | Display name |
| `description` | TEXT | What it does / where it's used |
| `default_content` | TEXT | Factory default (immutable, used for Reset) |
| `current_content` | TEXT | Active shared version |
| `variables` | JSON | Available placeholders (e.g., `["{account}", "{call_context}"]`) |
| `updated_by` | VARCHAR | Email of last editor |
| `updated_at` | TIMESTAMP | Last edit time |

### Table: `prompt_versions`
| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGINT PK AUTO | Version record ID |
| `prompt_id` | VARCHAR FK | References `prompt_registry.id` |
| `version` | INT | Auto-incrementing per prompt |
| `content` | TEXT | Full prompt text at this version |
| `edited_by` | VARCHAR | Who made this edit |
| `edited_at` | TIMESTAMP | When |
| `note` | TEXT | Optional commit message |

### Table: `prompt_user_overrides`
| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGINT PK AUTO | Override record ID |
| `prompt_id` | VARCHAR FK | References `prompt_registry.id` |
| `user_email` | VARCHAR | User who customized |
| `content` | TEXT | Their custom version |
| `updated_at` | TIMESTAMP | Last edit time |

**Unique constraint:** `(prompt_id, user_email)` on `prompt_user_overrides`.

---

## 4. Prompt Resolution Order

When the API needs a prompt at runtime:

1. Check `prompt_user_overrides` for `(prompt_id, user_email)` — if exists, use it
2. Use `current_content` from `prompt_registry`
3. If DB query fails, fall back to hardcoded Python defaults in `templates.py`

**TiDB Expert injection:** When the toggle is on, query the `tidb_expert` prompt from `prompt_registry` and append it to the system prompt. Same behavior as today, but content comes from DB.

**Caching:** In-memory cache with 5-minute TTL. Any save from the Prompt Studio invalidates the cache.

---

## 5. API Endpoints

All endpoints under `/api/prompts`. Authentication required.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/prompts` | List all prompts with metadata (no content body) |
| `GET` | `/api/prompts/:id` | Get prompt with current content |
| `PUT` | `/api/prompts/:id` | Save new version (creates `prompt_versions` entry) |
| `POST` | `/api/prompts/:id/reset` | Reset to factory default |
| `GET` | `/api/prompts/:id/versions` | List version history |
| `GET` | `/api/prompts/:id/versions/:version` | Get specific version content |
| `POST` | `/api/prompts/:id/rollback/:version` | Rollback to a specific version |
| `GET` | `/api/prompts/:id/my-override` | Get current user's personal override |
| `PUT` | `/api/prompts/:id/my-override` | Save current user's personal override |
| `DELETE` | `/api/prompts/:id/my-override` | Delete override (revert to shared) |

---

## 6. UI Design — Prompt Studio

### Location
New **"Prompt Studio"** tab in the Settings page.

### Layout
**Left panel:** Prompt browser organized by category
- System Prompts (11) — with TiDB Expert prominently at top with on/off toggle
- Section Templates (7)
- Personas (3) — Sales, SE, Marketing
- Source Profiles (3)

Each card shows: name, category badge, version number, last edited by/when.

**Right panel (on click):** Full-screen prompt editor
- Large, resizable syntax-highlighted textarea
- Available variables sidebar (shows `{account}`, `{call_context}`, etc. for the selected prompt)
- Action buttons: Save (creates new version), Reset to Default, Cancel
- For personas: additional "Save as My Version" / "Reset to Shared" buttons
- Version history drawer: list of versions with timestamps, diffs between any two versions, one-click rollback

### Section-to-System-Prompt Mapping
Displayed as a reference in the Prompt Studio so users understand which system prompt drives which section:

```
pre_call      → system_pre_call_intel
post_call     → system_post_call_analysis
follow_up     → system_post_call_analysis
tal           → system_market_research
se_poc_plan   → system_se_analysis
se_arch_fit   → system_se_analysis
se_competitor → system_se_analysis
chat/oracle   → system_oracle + persona
```

---

## 7. Backend Integration

### Current State
`llm.py` imports prompts from `templates.py` and uses `SECTION_SYSTEM_PROMPTS` dict.

### New State
- New `PromptService` class that resolves prompts via DB with caching and fallback
- `llm.py` calls `PromptService.resolve(section, user_email, tidb_expert_enabled)` instead of importing constants
- `templates.py` remains as fallback defaults (never deleted)
- Seed migration populates `prompt_registry` from current hardcoded values

### Resolution Flow (per LLM call)
1. Receive request with `section` + `user_email`
2. `PromptService` checks cache → DB → hardcoded fallback
3. If TiDB Expert enabled, append skill content to system prompt
4. Pass resolved system prompt + user template to LLM

---

## 8. TiDB Expert Skill — Full Knowledge Base

Expanded from ~25 lines to a complete knowledge base. Stored as prompt `tidb_expert` in `prompt_registry`. Injected in full when the toggle is on (Claude skill pattern).

### Sections

1. **Core Architecture** — TiDB Server (stateless SQL), TiKV (Raft KV), TiFlash (columnar HTAP), PD (TSO + scheduling). Region splitting, Raft Learner, MPP engine.

2. **Deployment Modes** — Cloud Serverless (auto-scale, pay-per-use, vector search), Cloud Dedicated (fixed compute, VPC peering, BYOC), Self-Hosted (TiUP, TiDB Operator/K8s, air-gapped).

3. **MySQL Compatibility** — MySQL 8.0 wire protocol, supported/unsupported syntax, triggers/stored procedure caveats, foreign keys (v6.6+), driver/ORM compatibility (Hibernate, Sequelize, GORM, Django).

4. **HTAP Deep Dive** — TiFlash architecture, Raft Learner replication, sub-second freshness, MPP execution, auto query routing, optimizer hints.

5. **Transactions & Consistency** — Percolator 2PC, optimistic vs pessimistic locking, snapshot isolation, stale reads, TSO ordering.

6. **Scaling Patterns** — Online node add, auto region splitting/rebalancing, hot region handling, capacity planning.

7. **Migration Playbooks** — MySQL/Aurora (DM + binlog), Vitess/ProxySQL (middleware elimination), Oracle (SQL translation + OGG), PostgreSQL (schema translation), MongoDB (document-to-relational).

8. **Competitive Battlecards** — vs CockroachDB, PlanetScale/Vitess, Aurora/RDS, AlloyDB, Spanner, YugabyteDB. Each with: where TiDB wins, where to be careful, proof points, landmine questions.

9. **Pricing & Packaging** — Cloud Serverless (RU-based), Cloud Dedicated (node-based), Self-Hosted (subscription tiers), typical deal sizes by workload.

10. **Real-World Patterns** — High-volume OLTP (fintech, gaming), real-time analytics (ad-tech, logistics), MySQL consolidation (SaaS), multi-tenant architectures.

11. **Objection Handling** — "Happy on Aurora," "CockroachDB is more mature," "PostgreSQL shop," "Too risky to migrate," "Open source = no support," "Already use Vitess."

---

## 9. Prompt Quality Overhaul

### System Prompts

| Prompt | Upgrade |
|--------|---------|
| Oracle | Add structured output expectations, citation requirements, confidence scoring |
| Pre-Call Intel | Move accuracy rules to top of prompt (LLMs weight early instructions more), add explicit DO NOT list |
| Post-Call Analysis | Add MEDDPICC scoring rubric (1-5 per element), require transcript quote evidence for each rating |
| SE Analysis | Expand with technical depth expectations, POC success/fail patterns, migration risk scoring |
| Call Coach | Expand with coaching framework (situation → behavior → impact), require specific timestamps/quotes |
| Market Research | Add ICP scoring criteria, signal weighting, territory planning structure |
| Rep Execution | Add deal stage awareness (discovery vs negotiation vs closing produce different outputs) |
| SE Execution | Add technical maturity assessment, POC readiness scoring methodology |
| Marketing Execution | Add funnel stage mapping, content-to-signal matching |
| Messaging Guardrail | No change needed |

### Section Templates

| Template | Upgrade |
|----------|---------|
| Pre-Call | Replace generic examples with TiDB-specific patterns, add competitive alert trigger |
| Post-Call | Add guiding sub-questions under each MEDDPICC element |
| Follow-Up | Add tone-specific structural guidance, executive vs technical email patterns |
| TAL | Add ICP fit scoring, signal prioritization weights |
| SE POC Plan | Add go/no-go gate criteria per week, standard TiDB POC toolkit references |
| SE Arch Fit | Add compatibility matrix prompting, migration effort estimation framework |
| SE Competitor | Add landmine questions section (questions that expose competitor weaknesses naturally) |

### Personas

| Persona | Upgrade |
|---------|---------|
| Sales | Add deal-stage awareness, MEDDPICC lens, next-action bias |
| SE | Add technical rigor expectations, migration risk default framing, POC pattern library reference |
| Marketing | Add funnel awareness, vertical narrative framing, measurable outcome bias |

### Source Profiles

- Add confidence scoring per source (SEC filing = high, Reddit = low)
- Add recency weighting (last 6 months > older)

---

## 10. Migration Plan

1. Create 3 new tables in TiDB
2. Seed `prompt_registry` with all 24 current hardcoded prompts
3. Each seeded prompt: `default_content` = `current_content` = current hardcoded value
4. Deploy API with new `PromptService` + fallback to hardcoded
5. Deploy UI with Prompt Studio tab
6. Apply prompt quality upgrades via the Prompt Studio UI (eat our own dogfood)

---

## 11. Not In Scope

- Prompt A/B testing or analytics
- Prompt sharing/export between instances
- Prompt marketplace
- Automated prompt optimization
