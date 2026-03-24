import { NextResponse } from 'next/server';
import { getSession } from '../../../../lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request) {
  const session = await getSession();
  if (!session?.email) return NextResponse.json({ error: 'unauthenticated' }, { status: 401 });

  const { company, callSummaries = [], callCount = 0, contacts = [], lastStage = '' } = await request.json();

  const callContext = callSummaries.length
    ? `INTERNAL CALL HISTORY (${callCount} total calls, ${callSummaries.length} with notes shown — most recent first):
${callSummaries.map((s, i) => `Call ${i + 1}: ${s}`).join('\n\n')}

CRITICAL: Analyze these calls carefully. Extract:
- Overall relationship sentiment (positive / neutral / at-risk / negative)
- Specific objections, blockers, or concerns raised by the customer
- Security, compliance, or trust issues mentioned
- Whether they expressed unhappiness, frustration, or intent to not proceed
- Champion strength and engagement level
- Any explicit statements about competing solutions or switching costs
These call signals MUST directly affect the fit_score, buy_signals, and opening_pitch.`
    : 'No internal call history available — base analysis on external research only.';

  const contactContext = contacts.length
    ? `Known contacts from our calls: ${contacts.join(', ')}`
    : '';

  const prompt = `You are a TiDB Cloud sales engineer preparing an honest, actionable account intelligence profile for "${company}".

${callContext}

${contactContext}
${lastStage ? `Current deal stage: ${lastStage}` : ''}

Research this company thoroughly. Then synthesize BOTH external research AND the internal call history above to produce a realistic assessment. Do NOT default to a high fit score if the calls show unhappiness, security concerns, or blockers — the calls are ground truth.

Return ONLY a valid JSON object (no markdown, no code fences, no explanation):

{
  "company": "full company name",
  "domain": "website domain",
  "hq": "City, State/Country",
  "founded": "year or ~year",
  "sector": "Technology / SaaS",
  "funding": "Series X, $XXM or Public: TICKER",
  "employees": "X,XXX",
  "fit_score": 8.5,
  "relationship_health": "strong | neutral | at-risk | negative",
  "overview_1": "2-3 sentence company description with specific products, scale, and what makes them technically interesting",
  "overview_2": "Honest assessment of where this deal stands — reference actual call themes, relationship status, and strategic relevance right now",
  "kpis": [
    { "value": "1,200", "label": "Employees" },
    { "value": "$150M", "label": "Raised" },
    { "value": "2015", "label": "Founded" },
    { "value": "Series C", "label": "Stage" }
  ],
  "stack": {
    "databases": ["MySQL", "Redis"],
    "cloud": ["AWS"],
    "ai": ["PyTorch"],
    "languages": ["Go", "Python"],
    "compatibility": "MySQL-compatible — zero-code migration path to TiDB Cloud Starter"
  },
  "pain_points": [
    { "title": "Short descriptive title", "pain": "Specific pain their engineers feel", "solution": "How TiDB Cloud directly resolves this", "severity": "high" },
    { "title": "Short descriptive title", "pain": "Specific pain", "solution": "TiDB Cloud solution", "severity": "high" },
    { "title": "Short descriptive title", "pain": "Specific pain", "solution": "TiDB Cloud solution", "severity": "medium" },
    { "title": "Short descriptive title", "pain": "Specific pain", "solution": "TiDB Cloud solution", "severity": "medium" }
  ],
  "buy_signals": [
    { "title": "Signal title", "text": "Specific evidence from research or calls", "urgency": "high" },
    { "title": "Risk or blocker title", "text": "Specific concern raised in calls that must be addressed", "urgency": "risk" },
    { "title": "Signal title", "text": "Specific evidence", "urgency": "medium" },
    { "title": "Signal title", "text": "Specific evidence", "urgency": "low" }
  ],
  "workloads": [
    { "name": "Workload name", "desc": "Why this workload matters for them", "priority": "P1" },
    { "name": "Workload name", "desc": "Description", "priority": "P1" },
    { "name": "Workload name", "desc": "Description", "priority": "P2" }
  ],
  "contacts": [
    { "name": "Full Name", "initials": "FN", "title": "VP Engineering", "angle": "Lead TiDB Cloud trial conversation here" },
    { "name": "Full Name", "initials": "FN", "title": "CTO", "angle": "Strategic infrastructure direction" }
  ],
  "opening_pitch": "A 3-4 sentence opener that reflects the REAL relationship state — if they raised concerns in calls, acknowledge and address them. If relationship is strong, build on that. Never pitch as if the calls didn't happen.",
  "sources": [
    { "url": "https://...", "label": "Source description" },
    { "url": "https://...", "label": "Source description" }
  ]
}

FIT SCORE RULES — apply all that match, cap at 9.9, floor at 1.0:
Base: 4.0
Stack signals (add): MySQL/Aurora +2.0, Oracle +1.8, PostgreSQL +1.2, high txn volume +1.4, AI/ML +1.5, real-time analytics +1.0, multi-cloud +1.0, microservices +0.8, SaaS/multi-tenant +0.7
Relationship penalties (subtract): active security/compliance objection -2.5, customer expressed unhappiness or frustration -1.5, deal stalled >60 days -0.5, lost champion -1.0, explicit no or not interested -3.0, competitor strongly preferred -1.5
If internal calls show the customer is NOT happy, the fit_score MUST reflect that reality regardless of how good their stack looks.

buy_signals urgency values: "high" (strong positive signal), "medium" (moderate signal), "low" (weak signal), "risk" (active blocker or concern from calls that needs addressing).
Always say "TiDB Cloud Starter" (never "TiDB Serverless"). Emphasize HTAP, MySQL wire compatibility, distributed architecture, auto-scale.
Be specific and honest. If the deal looks bad, say so. Reference real data from both research and calls.`;

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
