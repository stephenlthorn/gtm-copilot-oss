# GTM Copilot Usage Guide

A practical guide to all GTM Copilot system prompts, their primary functions, required inputs, and expected outputs.

---

## System Prompts Overview

The GTM Copilot consists of 12 core system prompts designed for sales, sales engineering, marketing, and leadership roles at PingCAP (TiDB).

### **1. Oracle (system_oracle)**

**Purpose:** General-purpose assistant for TiDB sales, SE, and marketing teams. Answers technical questions, deal strategy, and research queries.

**Primary Function:** Provide expert guidance on TiDB capabilities, positioning, competitive differentiation, and deal strategy.

**Expected Input:**
- Technical questions: "What is TiDB's vector search capability?"
- Deal questions: "How should I position against CockroachDB for this prospect?"
- Research questions: "What are the AI infrastructure requirements for this type of workload?"

**Expected Output:**
- Technical answers: Direct, clear explanations with source citations
- Deal guidance: Structured Context → Insight → Recommendation format
- Research summaries: Concise, fact-based analysis with web search citations

**Key Features:**
- Mandatory web search for AI/agent topics, TiDB features, and version-specific details
- Always cites source URLs
- Product knowledge: "TiDB Cloud Starter" (not "Serverless"), horizontal write scaling, HTAP, native vector search, MySQL 8.0 compatibility
- Competitive positioning framework: vs Aurora, CockroachDB, PlanetScale, Vitess, YugabyteDB

---

### **2. Pre-Call Intel (system_pre_call_intel)**

**Purpose:** Generate research-grade pre-call intelligence briefs with outbound messaging ready to send.

**Primary Function:** Research prospect and company deeply, identify pain signals, map personas, and draft cold outreach messaging.

**Expected Input:**
- Prospect name, LinkedIn URL
- Account/company name, website
- Desired outcome (discovery, competitive displacement, etc.)

**Expected Output:**
- 10-section research brief including:
  1. Prospect background (verified via LinkedIn)
  2. Company financials and growth signals
  3. Current architecture hypothesis (databases, cloud, microservices)
  4. AI/agent initiative signals
  5. Pain hypotheses ranked by probability
  6. ICP persona map with engagement angles
  7. Tailored TiDB value propositions
  8. MEDDPICC discovery questions
  9. Meeting goal
  10. Ready-to-send outbound messaging (cold email, LinkedIn message, voicemail, 16-step sequence)

**Key Accuracy Rules:**
- DO NOT use training data for company facts (search first)
- DO NOT fabricate financial data, employee counts, or tech stacks
- Always cite sources (Crunchbase, LinkedIn, SEC filings, GitHub, BuiltWith)
- If competitive alert found, add at top before Section 1

**Sample Inputs:**
```
Prospect: Sarah Chen (VP Engineering)
LinkedIn: linkedin.com/in/sarah-chen-engineering
Account: Acme Fintech (acmefintech.com)
Context: They're building real-time payment processing systems at scale
```

---

### **3. Post-Call Analysis (system_post_call_analysis)**

**Purpose:** Analyze call transcripts and produce MEDDPICC deal coaching briefs with evidence-backed insights.

**Primary Function:** Score deal qualification, identify gaps, provide coaching recommendations, and draft follow-up emails.

**Expected Input:**
- Call transcript (or call summary)
- Account name and context
- Deal stage (Discovery, Evaluation, Negotiation, Closing)
- Current MEDDPICC state (if known)

**Expected Output:**
- 8-section coaching brief:
  1. Executive summary (4–6 sentences): deal snapshot, qualification verdict
  2. MEDDPICC breakdown (M/E/D/D/P/I/C/C scored 1–5 with evidence)
  3. Sales process stage assessment (current stage + exit criteria)
  4. Risks & red flags (severity: High/Medium/Low)
  5. Missing discovery & required questions
  6. Coaching recommendations (4 segments: qualification gaps, deal strategy, stakeholder strategy, next call plan)
  7. Recommended next steps (3–5 actions with owner + deliverable + date)
  8. Ready-to-send follow-up email (150–250 words)

**MEDDPICC Scoring Rules:**
- 1 = Not mentioned
- 2 = Mentioned but not qualified
- 3 = Qualified (cite exact transcript quote)
- 4 = Documented (rep confirmed, cite quote)
- 5 = Confirmed with evidence (corroborated by second source)

**Anti-Hallucination:**
- DO NOT fabricate transcript quotes
- Score conservatively when ambiguous
- Flag unverified elements

**Sample Input:**
```
Call: [Account] — Sales call with CTO and VP of Engineering
Attendees: Sarah Chen (CTO), Mike Wong (VP Eng), [Your team]
Duration: 45 minutes
Key topics: MySQL scaling pain, considering horizontal sharding
Deal stage: Discovery
Transcript: [paste transcript or summary]
```

---

### **4. SE Analysis (system_se_analysis)**

**Purpose:** Produce technical evaluation plans, architecture fit analyses, and competitive coaching briefs for sales engineers.

**Primary Function:** Ground technical recommendations in the customer's actual tech stack and define measurable POC success criteria.

**Expected Input:**
- Customer tech stack (verified via job postings, GitHub, BuiltWith, call transcript)
- Use case description or pain statement
- Competitive context (if applicable)
- Current architecture

**Expected Output:**
- Technical deliverables:
  - POC plan with 4-week milestone timeline and 3+ measurable success criteria
  - Architecture fit analysis with migration complexity rating (Low/Medium/High)
  - Compatibility caveats and mitigations (stored procedures, triggers, AUTO_INCREMENT, full-text search)
  - Competitive coaching brief with specific objections + TiDB responses
  - Technical requirements and risk assessments

**Technical Standards:**
- Always cite evidence: job posting, GitHub link, blog post, or call transcript
- Be specific about migration complexity and estimated timeline
- Proactively flag MySQL behavior differences in TiDB
- For POC: define measurable thresholds (e.g., "P99 read latency <10ms at 5K TPS")
- AI/Vector capability: fetch and cite AI sources when vector search is mentioned

**Sample Input:**
```
Account: Acme Fintech
Current Stack: Aurora MySQL 8.0, Redis, separate analytics DB (Redshift)
Workload: Payment transaction processing (10K TPS), real-time analytics
Pain: Sharding complexity, analytics latency (16-hour ETL cycle)
Goal: Evaluate TiDB for direct replacement of Aurora + consolidation with analytics
```

---

### **5. Call Coach (system_call_coach)**

**Purpose:** Provide specific, evidence-backed coaching on call performance using SBI format (Situation → Behavior → Impact).

**Primary Function:** Coach reps on MEDDPICC coverage, objection handling, competitive differentiation, and call execution.

**Expected Input:**
- Call transcript (required for evidence)
- Deal stage
- Current MEDDPICC state

**Expected Output:**
- Call coaching brief:
  1. Call summary
  2. Coaching points (3+ points, each in SBI format)
     - "Good practice — reinforce": behavior that worked, why, encourage repetition
     - "Improvement opportunity": exact alternative phrasing (not description, the actual words)
  3. MEDDPICC gap analysis (for each element: established + missing + question for next call)
  4. Questions for next call (prioritized with MEDDPICC element and business reason)
  5. Recommended resources (specific doc names/URLs, not vague portals)
  6. Top 3 next actions (person + deliverable + date)

**Coaching Point Requirements:**
- Every point requires transcript timestamp or direct quote
- MEDDPICC-focused: flag missed opportunities to qualify each element
- TiDB-specific: flag missed differentiation on HTAP, horizontal scaling, MySQL compatibility, vector search

**Sample Input:**
```
Call Transcript: [paste full transcript with timestamps]
Deal Stage: Discovery
Rep: [Name]
Account: [Account name]
Current MEDDPICC: Metrics (3/5), Economic Buyer (1/5), Pain (4/5)...
```

---

### **6. Messaging Guardrail (system_messaging_guardrail)**

**Purpose:** Enforce email security policy for outbound messaging.

**Primary Function:** Validate recipient domain allowlist, flag confidential content, and ensure messages are policy-compliant.

**Expected Input:**
- Recipient email address(es)
- Email body and subject line
- Tone specification (crisp, executive, technical)

**Expected Output:**
- BLOCKED or APPROVED status
- If blocked: exact reason and which recipient failed validation
- If approved: message ready to review/send or flagged content issues

**Security Rules:**
- Recipient allowlist enforced (only internal domain addresses allowed)
- Default to DRAFT mode (requires manual review before send)
- Block any confidential data: deal values, MEDDPICC scores, internal strategy notes, pricing/discounts
- Flag if message references internal-only information

---

### **7. Market Research / TAL (system_market_research)**

**Purpose:** Generate territory-specific strategic account plans and target account lists (TALs).

**Primary Function:** Score accounts on ICP fit and identify priority targets with timing triggers.

**Expected Input:**
- Territory or region
- ICP criteria (industry, company size, revenue range)
- Optional constraints (e.g., "no active deals", "strong AI signal")
- Number of recommendations requested

**Expected Output:**
- Prioritized account list with:
  1. Account name and ICP score breakdown (5 criteria, max 25 total)
  2. Top signal with source URL
  3. Recommended entry point (specific role + angle)
  4. Suggested first action
  5. Time-sensitive trigger (why NOW vs 6 months)

**ICP Scoring Criteria (1–5 each):**
- Company size fit: headcount and revenue (500–10K employees, $50M–$5B revenue = sweet spot)
- Industry fit: Tier 1 = fintech, ad-tech, SaaS, gaming, e-commerce (5 pts); Tier 2 = logistics, healthcare, media (3–4 pts); Tier 3 = gov, education (1–2 pts)
- Tech stack match: MySQL/Aurora/Vitess = 5; PostgreSQL = 3; Oracle = 4; NoSQL-only = 1
- Growth signal: Recent funding/IPO/M&A = 5; DB/infra hiring = 4; expansion announcement = 3; no recent signal = 1
- Champion potential: Accessible eng/platform leadership = 5; only C-suite = 2; no known contacts = 1
- AI/ML signal (bonus +1–2): active AI hiring, RAG pipelines, LLM applications

**Signal Weighting Priority:**
1. Financial signal (funding, IPO, M&A)
2. Hiring signal (database/infra/AI postings)
3. Tech stack signal (MySQL/Aurora at scale, sharding)
4. Competitive signal (evaluating CockroachDB, PlanetScale, Yugabyte)
5. AI/ML signal (vector DB, LLM infrastructure)
6. News signal (scaling announcements)

**Sample Input:**
```
Territory: EMEA - Northern Europe
ICP Industry: Fintech, SaaS
Company Size: $200M–$2B revenue, 1K–5K employees
Top 20 accounts requested
Constraint: Must have active hiring in database/infrastructure roles
```

---

### **8. Rep Execution (system_rep_execution)**

**Purpose:** Provide deal-stage-aware sales execution guidance, MEDDPICC recommendations, and deal progression strategies.

**Primary Function:** Convert call transcripts and account context into practical rep actions and discovery questions.

**Expected Input:**
- Call transcript or call notes
- Account name and CRM data
- Deal stage (Discovery, Evaluation, Negotiation, Closing)
- Current MEDDPICC state (optional)

**Expected Output:**
- Execution brief:
  1. Deal summary (stage, key pains, MEDDPICC gaps)
  2. Next discovery questions (prioritized by deal stage and MEDDPICC gaps)
  3. TiDB positioning recommendations (stage-specific value props)
  4. Account brief with action items
  5. Next steps (3–5 specific actions with owner + deliverable + date)

**Product Positioning by Pain Signal:**
- MySQL/Aurora at scale → horizontal write scaling + MySQL wire compatibility
- Sharding complexity → native distributed SQL (no Vitess/ProxySQL middleware)
- Separate analytics DB → TiDB HTAP (eliminates ETL, single system for OLTP + analytics)
- AI/ML workloads → native vector search (eliminates separate Pinecone/Weaviate)
- Operational overhead → TiDB Cloud managed service with auto-scaling

**Deal-Stage Awareness:**
- Discovery: focus on qualification gaps and MEDDPICC coverage
- Evaluation/Technical Validation: focus on differentiation and competitive positioning
- Negotiation: focus on risk/value balance and stakeholder alignment
- Closing: focus on urgency, mutual close plan, paper process acceleration

---

### **9. SE Execution (system_se_execution)**

**Purpose:** Provide SE-focused technical validation, POC readiness assessment, and architecture fit guidance.

**Primary Function:** Assess technical maturity, score POC readiness, and identify architecture fit risks.

**Expected Input:**
- Customer tech stack and current architecture
- Use case and performance requirements
- Deal stage and prospect maturity level
- Existing POC plans (if any)

**Expected Output:**
- SE brief:
  1. Technical maturity assessment (Starter / Intermediate / Advanced)
  2. POC readiness score (0–10) with top 3 gaps
  3. Architecture fit analysis
  4. Migration complexity assessment (Low/Medium/High)
  5. Competitive coaching (if applicable)
  6. Recommended next actions (person + deliverable + date)

**POC Readiness Criteria (1 point each, 0–10 total):**
1. Clear, written success criteria agreed by customer
2. Named technical champion with authority to evaluate
3. Access to representative production workload/data
4. Defined timeline with start and end dates
5. Named executive sponsor aware of POC
6. Test environment provisioned or on schedule
7. Competitive context understood
8. Migration complexity assessed (Low/Medium/High)
9. Internal team bandwidth confirmed
10. Business case owner identified

**Technical Maturity Levels:**
- **Starter:** Small team, limited DB expertise, needs managed/serverless, prefers low operational overhead
- **Intermediate:** Dedicated platform/infra team, comfortable with distributed systems, evaluating alternatives
- **Advanced:** Large-scale DB infrastructure, deep MySQL expertise, evaluating for specific scale/HTAP use case

---

### **10. Marketing Execution (system_marketing_execution)**

**Purpose:** Convert demand signals and pipeline data into prioritized, measurable campaign actions.

**Primary Function:** Map marketing content to pipeline stages and recommend vertical-specific campaigns.

**Expected Input:**
- Pipeline data (accounts, deal stage, signals)
- Vertical/industry context
- Current campaigns or content gaps
- Target segments

**Expected Output:**
- Campaign recommendations:
  1. Content-to-signal matching (hiring signal → operational complexity content, funding signal → scaling content, etc.)
  2. Vertical narrative framing (fintech = compliance + write scale; ad-tech = throughput + real-time analytics; etc.)
  3. Funnel mapping (MQL → awareness, SQL → consideration, SAL → evaluation, Opportunity → closing)
  4. Measurable success metrics per campaign
  5. Next actions (specific campaign tasks with owner + timeline)

**Funnel Mapping:**
- **MQL (Marketing Qualified Lead):** Awareness content—blog, SEO, benchmarks, comparison guides
- **SQL (Sales Qualified Lead):** Consideration content—case studies, architecture diagrams, TCO calculators
- **SAL (Sales Accepted Lead):** Evaluation content—technical deep dives, migration guides, POC playbooks
- **Opportunity (Active Deal):** Closing content—customer references, competitive battlecards, ROI models

---

### **11. TiDB Expert Skill (tidb_expert)**

**Purpose:** Deep technical expertise on TiDB internals, performance tuning, and architecture.

**Primary Function:** Answer complex technical questions with systems-level depth (Raft consensus, region splitting, query optimization, etc.).

**Expected Input:**
- Technical questions ranging from "Why is my query slow?" to "How does region splitting work?"
- Context: workload type, scale, config, observed behavior
- Desired depth: practical guidance vs. deep systems explanation

**Expected Output:**
- Precise, context-aware answers:
  - For operational questions: focused, actionable guidance
  - For architecture questions: deep explanations referencing code paths, algorithms, and observable behavior
  - Always state what assumptions you're making and what data you'd look at to confirm

**Key Principles:**
- Adapt depth to the question
- Always be precise; avoid "it depends" without follow-up
- Reference TiDB codebase, tuning parameters, and monitoring metrics
- Connect abstract concepts to observable behavior

---

### **12. Follow-Up Email Template (tpl_follow_up)**

**Purpose:** Draft specific, deal-advancing follow-up emails.

**Primary Function:** Convert call records and notes into ready-to-send emails with deal progression language.

**Expected Input:**
- Call record (date, attendees, topics, stage)
- Additional notes from rep (key moments, commitments)
- Tone specification: crisp / executive / technical
- Email recipient (To/CC)
- Evidence (call transcript chunks if available)

**Expected Output:**
- Complete follow-up email:
  1. **Subject line:** [Account] — [specific topics or outcome]: [next action]
  2. **Opening (1–2 sentences):** Most important result or commitment from call (no filler like "Great speaking with you")
  3. **Body Paragraph 1:** What the call established (specific language from call, their terminology)
  4. **Body Paragraph 2:** All committed actions with owner, action, and date
  5. **Body Paragraph 3 (optional):** MEDDPICC bridge question (only if gaps exist)
  6. **Close/CTA:** One specific ask (confirm next call, approve timeline, request decision, etc.)

**Email Quality Rules:**
- Ban these phrases: "follow-up", "touching base", "great speaking", "hope you're well", "as discussed"
- Every next step needs: owner + action + date
- Subject line avoids vague words ("next steps" alone, "following up")
- Tone adapts to deal stage (crisp for list items, executive for business impact, technical for architecture questions)

**Sample Output:**
```
Subject: Acme Pay — MySQL sharding challenges + TiDB POC timeline: Q2 start

We confirmed that your 10K TPS Aurora workload is hitting sharding bottlenecks, and you're interested in a 4-week evaluation of TiDB as a direct replacement with zero app changes.

Next steps:
• Sarah Chen (CTO): Confirm POC success criteria and environment access by March 15
• Your team: Review TiDB Cloud documentation and run a quick sizing exercise by March 20
• Our team: Prepare POC kit (migration tools, benchmarks, architecture diagrams) by March 22

One question as you move toward the POC: Is there a formal evaluation committee we should be designing the POC results presentation around, or will it be a technical team decision?

Can we confirm a POC kickoff call for March 25 at 10am PT?
```

---

## How to Use These Prompts

### **Workflow Examples**

#### **Pre-Call Preparation:**
1. Use **Pre-Call Intel** to research prospect and generate outreach messaging
2. Use **Rep Execution** to draft discovery questions and account strategy
3. Use **Oracle** to answer any TiDB positioning questions that arise

#### **Post-Call Analysis:**
1. Use **Post-Call Analysis** to score MEDDPICC and identify gaps
2. Use **Call Coach** to review rep performance and coaching points
3. Use **Follow-Up Email** to draft the response email
4. Use **Rep Execution** to plan next steps and strategy

#### **Technical Evaluation:**
1. Use **SE Analysis** to plan POC and address technical objections
2. Use **SE Execution** to assess readiness and identify migration risks
3. Use **TiDB Expert** to answer deep technical questions

#### **Territory Planning:**
1. Use **Market Research / TAL** to generate target account lists
2. Use **Rep Execution** to draft account plans and first actions
3. Use **Marketing Execution** to plan content and campaigns

---

## Key Principles Across All Prompts

### **1. Always Cite Sources**
- For web search: include URL
- For call transcripts: include timestamp or direct quote
- For internal data: reference the source system

### **2. No Hallucination**
- Do NOT fabricate financial data, company details, or transcript quotes
- If you don't have evidence, mark it "Unverified — [what you searched]"
- State assumptions explicitly and flag what needs confirmation

### **3. Be Specific**
- "It depends" is not a complete answer — state what it depends on and how to figure it out
- Recommendations must include: owner + action + date
- Questions must serve the prospect while advancing the deal

### **4. Deal-Stage Awareness**
- Adapt all guidance to current deal stage (Discovery, Evaluation, Negotiation, Closing)
- Discovery: focus on qualification and MEDDPICC coverage
- Evaluation: focus on differentiation and technical validation
- Negotiation: focus on value and risk balance
- Closing: focus on urgency and timeline

### **5. TiDB Positioning Framework**
Always lead with: **"TiDB is the database for AI agents"**
- Databases are evolving: systems of record → systems of thought
- AI agents need infrastructure for: agent memory, agent state, multi-agent coordination, massive concurrent workloads
- Proof points: horizontal write scaling, HTAP, MySQL compatibility, native vector search

---

## Common Input/Output Formats

### **Call Record Format**
```json
{
  "account": "Acme Fintech",
  "date": "2026-03-15",
  "attendees": ["Sarah Chen (CTO)", "Mike Wong (VP Eng)"],
  "duration_minutes": 45,
  "deal_stage": "Discovery",
  "topics": ["MySQL scaling pain", "Real-time analytics need"],
  "transcript": "[paste transcript or summary]"
}
```

### **Account Context Format**
```json
{
  "account_name": "Acme Fintech",
  "industry": "Fintech",
  "size": "2500 employees, $800M revenue",
  "website": "acmepay.com",
  "tech_stack": "Aurora MySQL 8.0, Redis, Redshift",
  "current_pain": "Sharding complexity, analytics latency",
  "deal_stage": "Discovery",
  "meddpicc_state": {
    "metrics": 0,
    "economic_buyer": 1,
    "pain": 4,
    "decision_process": 0,
    "decision_criteria": 0,
    "paper_process": 0,
    "champion": 2,
    "competition": 1
  }
}
```

---

## Quick Reference: Which Prompt for Each Task

| Task | Prompt | Input | Output |
|------|--------|-------|--------|
| Research prospect + draft cold outreach | **Pre-Call Intel** | Prospect name, company, LinkedIn | 10-section brief + ready-to-send emails |
| Analyze call, score MEDDPICC | **Post-Call Analysis** | Transcript, account, deal stage | 8-section coaching brief + follow-up email |
| Coach rep on call performance | **Call Coach** | Transcript + timestamps, MEDDPICC state | SBI-format coaching points + next call plan |
| Plan POC and technical approach | **SE Analysis** | Tech stack, use case, goals | POC plan + architecture fit + competitive coaching |
| Assess POC readiness | **SE Execution** | Tech stack, POC plans, maturity level | Readiness score + top 3 gaps + next actions |
| Answer TiDB technical questions | **Oracle** or **TiDB Expert** | Technical question, context | Precise answer with sources/citations |
| Generate target account list | **Market Research** | Territory, ICP criteria | Prioritized accounts with ICP scores + entry points |
| Draft deal strategy and next steps | **Rep Execution** | Call transcript, account context, stage | Account brief + discovery questions + next actions |
| Plan campaigns and content | **Marketing Execution** | Pipeline data, vertical, signals | Content recommendations + funnel mapping + campaigns |
| Validate email before send | **Messaging Guardrail** | Email, recipient, content | Approved/Blocked + compliance notes |

---

## Examples of Effective Prompts

### **Example 1: Pre-Call Intel Request**
```
Research and prepare a pre-call brief for:
- Prospect: Sarah Chen, VP of Engineering
- Company: TechScale (scale.tech, Series C fintech startup)
- LinkedIn: linkedin.com/in/sarahchen-engineering
- Context: They're building real-time payment processing systems and mentioned they're evaluating distributed databases for scaling

Prepare the full 10-section brief with all outbound messaging ready to send.
```

### **Example 2: Post-Call Analysis Request**
```
Call: March 15 discovery call with Acme Fintech
Attendees: Sarah Chen (CTO), Mike Wong (VP Eng), our sales team
Duration: 45 minutes
Deal stage: Discovery
Transcript: [paste transcript]

Analyze this call and provide:
- MEDDPICC scoring with evidence
- Coaching recommendations for our rep
- Next steps and follow-up email
- Qualification verdict
```

### **Example 3: SE Analysis Request**
```
Account: TechScale Inc.
Current Stack: MySQL 8.0 on AWS RDS, Redis (cache layer), Redshift (analytics)
Workload: Real-time payments (5K TPS), nightly analytics batch job
Pain: MySQL sharding complexity, slow analytics (12-hour ETL)
Competitor: They're considering CockroachDB

Produce:
- POC plan with 4-week timeline and measurable success criteria
- Architecture fit analysis (migration complexity assessment)
- Competitive positioning vs CockroachDB
- Migration risk assessment
```

---

## Feedback & Iteration

These prompts are designed to be iterative:
1. Generate initial output
2. Review with your team
3. Ask for refinements: "More aggressive on competitive positioning" or "Focus on the HTAP benefit more"
4. Use the outputs as-is or refine and save for future iterations

Every prompt supports:
- Specific sources and citations
- Anti-hallucination safeguards
- Deal-stage awareness
- Action-oriented recommendations

---

**Last Updated:** April 2026  
**Version:** 1.0  
**Repository:** gtm-copilot-oss
