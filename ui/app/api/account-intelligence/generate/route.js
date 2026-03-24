import { NextResponse } from 'next/server';
import { getSession } from '../../../../lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request) {
  const session = await getSession();
  if (!session?.email) return NextResponse.json({ error: 'unauthenticated' }, { status: 401 });

  const { company, callSummaries = [], callCount = 0, contacts = [], lastStage = '' } = await request.json();

  // ── Step 1: Build call intelligence block ─────────────────────────────────
  let callIntelligence = '';
  if (callSummaries.length) {
    callIntelligence = `
═══════════════════════════════════════════════════════
INTERNAL CALL INTELLIGENCE — ${callCount} total calls on record
${callSummaries.length} calls with notes (newest first):
═══════════════════════════════════════════════════════
${callSummaries.map((s, i) => `── Call ${i + 1} ──\n${s}`).join('\n\n')}

MANDATORY CALL ANALYSIS — before writing any field, extract and weigh:
① RELATIONSHIP SENTIMENT: Is the customer engaged, lukewarm, frustrated, or hostile? Look for explicit language ("not interested", "concerned about X", "happy with the POC").
② OBJECTIONS & BLOCKERS: List every specific objection raised (security, compliance, price, performance, vendor lock-in, migration risk, team bandwidth).
③ TRUST SIGNALS: Did they give us access to their stack? Share internal architecture? Intro us to their team? These are positive trust signals.
④ COMPETITOR MENTIONS: Any database or cloud vendor mentioned as an alternative or incumbent.
⑤ CHAMPION STATUS: Is there a clear internal champion? Are they senior enough to drive a decision? Are they still engaged?
⑥ DEAL VELOCITY: Is the deal moving? Stalled? Getting colder based on call frequency and recency?

These extracted signals are the HIGHEST PRIORITY inputs. External research fills gaps — it does NOT override what we heard on calls.`;
  } else {
    callIntelligence = 'No internal call history — base full analysis on external research.';
  }

  const contactContext = contacts.length
    ? `Known contacts from our calls: ${contacts.join(', ')}`
    : '';

  const prompt = `You are a senior TiDB Cloud sales engineer and account strategist preparing a deep-research intelligence brief for "${company}".

${callIntelligence}

${contactContext ? `Known contacts: ${contactContext}` : ''}
${lastStage ? `Current deal stage: ${lastStage}` : ''}

═══════════════════════════════════════════════════════
RESEARCH INSTRUCTIONS
═══════════════════════════════════════════════════════
Conduct thorough external research across these signal sources:

COMPANY FUNDAMENTALS
• Official website, product pages, pricing pages
• Crunchbase / PitchBook for funding, investors, headcount trajectory
• LinkedIn for headcount, hiring velocity, key engineering hires
• Recent press releases, blog posts, customer announcements

TECHNICAL INTELLIGENCE (highest value signals)
• Engineering blog / tech blog — architecture decisions, scale numbers, DB migrations
• Job postings — search for database, infrastructure, data engineering, AND AI/ML roles. Keywords: "vector database", "embedding", "RAG", "LLM infrastructure", "feature store", "real-time ML", "recommendation engine". DB keywords reveal stack; AI keywords reveal new TiDB vector opportunity.
• GitHub org — open source repos reveal languages, frameworks, database dependencies, AI/ML tooling (LangChain, LlamaIndex, Hugging Face, OpenAI SDK)
• StackShare, DB-Engines, Siftery / G2 stack profiles
• Conference talks (QCon, ScaleConf, re:Invent, NeurIPS, MLOps World) where their engineers have presented
• Product features — does their product use personalization, search, recommendations, or generative AI? These are TiDB vector/HTAP opportunities.

GROWTH & SCALE SIGNALS
• Annual reports or S-1 (if public) — transaction volumes, user counts, data growth
• Case studies where they cite infrastructure scale (requests/sec, TPS, data size)
• Customer count, ARR estimates from analyst reports or press

COMPETITIVE CONTEXT
• Who else they're evaluating (AWS RDS, Aurora, PlanetScale, Vitess, CockroachDB, Neon, Yugabyte, SingleStore)
• Recent database migrations they've announced
• Cloud provider relationships (AWS credits, Google partnership, Azure committed spend)

═══════════════════════════════════════════════════════
OUTPUT REQUIREMENTS
═══════════════════════════════════════════════════════
Synthesize everything above into a single valid JSON object. No markdown. No code fences. No explanation. Just the JSON.

{
  "company": "Full legal or brand name",
  "domain": "primarydomain.com",
  "hq": "City, State/Country",
  "founded": "YYYY",
  "sector": "Primary sector / subsector",
  "funding": "Series X — $XXM raised (lead investor) OR NASDAQ: TICKER",
  "employees": "X,XXX (and trajectory: +20% YoY if known)",
  "fit_score": 7.2,
  "relationship_health": "strong | neutral | at-risk | negative",

  "overview_1": "2-3 sentences: what the company does, their scale (TPM/users/ARR if findable), and what makes them technically interesting to TiDB. Be specific — cite actual products, customer counts, or data volumes.",
  "overview_2": "2-3 sentences: honest deal status synthesis. Where do we stand based on calls + research? What is the single most important thing we need to address or capitalize on right now? Reference actual call themes or market moments.",

  "kpis": [
    { "value": "X,XXX", "label": "Employees" },
    { "value": "$XXXM", "label": "Raised" },
    { "value": "YYYY", "label": "Founded" },
    { "value": "Series X", "label": "Stage" }
  ],

  "stack": {
    "databases": ["MySQL 8.0", "Redis", "DynamoDB"],
    "cloud": ["AWS us-east-1", "GCP"],
    "ai": ["PyTorch", "OpenAI API"],
    "languages": ["Go", "Python", "TypeScript"],
    "compatibility": "One specific sentence: their primary DB, why it creates friction at their scale, and the exact TiDB Cloud migration path (e.g. 'MySQL 8.0 on RDS — zero-code migration via TiDB Cloud Starter, MySQL wire compatible, same drivers')"
  },

  "pain_points": [
    {
      "title": "Concise pain name (5 words max)",
      "pain": "Specific, technical pain their engineers actually feel at their current scale — cite evidence from job postings, blog posts, or calls. No generic statements.",
      "solution": "The exact TiDB Cloud capability that resolves this — be technically precise. Reference HTAP, TiFlash, auto-sharding, distributed transactions, TiCDC, TiProxy, or RU-based autoscaling as appropriate.",
      "severity": "high"
    },
    {
      "title": "Second pain",
      "pain": "Specific pain with evidence",
      "solution": "Precise TiDB solution",
      "severity": "high"
    },
    {
      "title": "Third pain",
      "pain": "Specific pain",
      "solution": "Precise TiDB solution",
      "severity": "medium"
    },
    {
      "title": "Fourth pain",
      "pain": "Specific pain",
      "solution": "Precise TiDB solution",
      "severity": "medium"
    }
  ],

  "buy_signals": [
    {
      "title": "Signal or risk name",
      "text": "One specific, evidence-backed sentence. For positive signals: cite the source (job posting, blog post, press release, call quote). For risks: quote or paraphrase the exact concern from calls.",
      "urgency": "high | medium | low | risk"
    }
  ],

  "workloads": [
    {
      "name": "Workload name",
      "desc": "Why this specific workload is painful for them at their current scale, and why TiDB Cloud handles it better than their current solution. Be technically specific.",
      "priority": "P1"
    },
    { "name": "Workload 2", "desc": "Specific technical rationale", "priority": "P1" },
    { "name": "Workload 3", "desc": "Specific technical rationale", "priority": "P2" }
  ],

  "contacts": [
    {
      "name": "Full Name (use real names from calls/LinkedIn if known, otherwise realistic title-based placeholder)",
      "initials": "XX",
      "title": "Exact title",
      "angle": "One sentence: what specifically to lead with for this person based on their role and what we know from calls. Tie to their likely KPIs or pain."
    }
  ],

  "next_steps": [
    "Specific action item #1 — who does what, referencing deal state and call history",
    "Specific action item #2",
    "Specific action item #3"
  ],

  "competitors": [
    { "name": "Competitor or incumbent DB name", "status": "incumbent | evaluating | preferred | eliminated", "note": "One sentence on their relationship with this vendor and how we position against it" }
  ],

  "opening_pitch": "3-4 sentences written as if you are the SE sending a follow-up email or opening a call. Must reflect the ACTUAL relationship state — if they raised security concerns, open by addressing them directly. If they're mid-POC, reference it. If they're cold, re-engage with a new angle. Never write as if the calls didn't happen. Sound like a human who read the notes, not a bot that ignored them.",

  "sources": [
    { "url": "https://actual-url.com/page", "label": "What this source revealed" }
  ]
}

═══════════════════════════════════════════════════════
FIT SCORE CALCULATION — show your work mentally, output only the final number
═══════════════════════════════════════════════════════
Start at 4.0. Apply ALL matching adjustments. Floor: 1.0. Cap: 9.9.

TECHNICAL FIT (add):
+2.0  MySQL or Aurora as primary OLTP DB
+1.8  Oracle Database (strong migration pain)
+1.2  PostgreSQL (compatible path)
+1.4  High transaction volume (>10K TPS or explicit scale language in job postings/blogs)
+1.5  Active AI/ML workloads needing real-time feature serving or vector search
+1.5  Building RAG pipelines, LLM applications, or embedding-based search (TiDB vector opportunity)
+1.0  Recommendation engine, personalization, or fraud detection use case (HTAP + vector fit)
+0.8  Job postings for AI/ML infra, embedding pipelines, or feature store engineering
+1.0  Real-time analytics alongside OLTP (classic HTAP use case)
+1.0  Multi-cloud or cloud portability requirement
+0.8  Microservices architecture with distributed transaction needs
+0.7  SaaS or multi-tenant product (row-level isolation, schema-per-tenant patterns)
+0.5  Active hiring for data infrastructure, DB engineering, or platform roles
+0.5  Recent funding or hypergrowth (scaling pain imminent)

RELATIONSHIP & DEAL RISK (subtract):
-3.0  Explicit "not interested" or "we're going another direction" in calls
-2.5  Active security, compliance, or data residency objection not yet resolved
-2.0  Competitor strongly preferred or actively being POC'd
-1.5  Customer expressed clear unhappiness, frustration, or distrust
-1.5  Deal stalled >90 days with no movement
-1.0  Champion left the company or lost influence
-1.0  Deal stalled 30-90 days
-0.5  Budget freeze or procurement blocker mentioned

RULE: If calls contradict the technical fit, calls win. A company with perfect MySQL stack but active security objections scores LOW. Never let a good stack mask a broken deal.`;


  try {
    const res = await fetch(`${API_BASE}/account-intelligence`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(session?.openai_key ? { 'X-OpenAI-Token': session.openai_key } : {}),
      },
      body: JSON.stringify({ user: session.email, prompt }),
    });

    if (!res.ok) {
      const err = await res.text();
      let detail = err.slice(0, 400);
      try { detail = JSON.parse(err)?.detail || detail; } catch {}
      return NextResponse.json({ error: `Backend error: ${detail}` }, { status: res.status });
    }

    const envelope = await res.json();
    const text = (envelope?.answer || '').trim();

    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return NextResponse.json({ error: 'AI did not return a valid profile. Try again.', raw: text.slice(0, 500) }, { status: 422 });
    }

    const profile = JSON.parse(jsonMatch[0]);
    return NextResponse.json({ profile });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
