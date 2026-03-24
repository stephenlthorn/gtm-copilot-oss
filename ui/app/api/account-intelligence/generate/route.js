import { NextResponse } from 'next/server';
import { getSession } from '../../../../lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request) {
  const session = await getSession();
  if (!session?.email) return NextResponse.json({ error: 'unauthenticated' }, { status: 401 });

  const { company, callSummaries = [], contacts = [], lastStage = '' } = await request.json();

  const callContext = callSummaries.length
    ? `Internal call history:\n${callSummaries.map(s => `- ${s}`).join('\n')}`
    : 'No internal call history.';

  const contactContext = contacts.length
    ? `Known contacts from our calls: ${contacts.join(', ')}`
    : '';

  const prompt = `You are a TiDB Cloud sales engineer preparing an account intelligence profile for "${company}".

${callContext}
${contactContext}
${lastStage ? `Current deal stage: ${lastStage}` : ''}

Research this company thoroughly and return ONLY a valid JSON object (no markdown, no code fences, no explanation) with this exact structure:

{
  "company": "full company name",
  "domain": "website domain",
  "hq": "City, State/Country",
  "founded": "year or ~year",
  "sector": "Technology / SaaS",
  "funding": "Series X, $XXM or Public: TICKER",
  "employees": "X,XXX",
  "fit_score": 8.5,
  "overview_1": "2-3 sentence company description with specific products, scale, and what makes them interesting",
  "overview_2": "Why TiDB Cloud is strategically relevant right now — reference their actual growth/product direction",
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
    { "title": "Signal title", "text": "Specific evidence from research", "urgency": "high" },
    { "title": "Signal title", "text": "Specific evidence", "urgency": "high" },
    { "title": "Signal title", "text": "Specific evidence", "urgency": "medium" },
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
  "opening_pitch": "A 3-4 sentence personalized opener referencing their actual stack, scale, and a specific recent signal. Sound like a sales engineer who did their homework, not generic AI.",
  "sources": [
    { "url": "https://...", "label": "Source description" },
    { "url": "https://...", "label": "Source description" }
  ]
}

TiDB fit score: base 4.0. Add: MySQL/Aurora +2.0, Oracle +1.8, PostgreSQL +1.2, high txn volume +1.4, AI/ML +1.5, real-time analytics +1.0, multi-cloud +1.0, microservices +0.8, SaaS/multi-tenant +0.7. Cap at 9.9.
Always say "TiDB Cloud Starter" (never "TiDB Serverless"). Emphasize HTAP, MySQL wire compatibility, distributed architecture, auto-scale.
Be specific and assertive. No "may benefit from" hedging. Reference real data found in research.`;

  try {
    const res = await fetch(`${API_BASE}/account-intelligence`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(session.access_token ? { 'X-OpenAI-Token': session.access_token } : {}),
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
