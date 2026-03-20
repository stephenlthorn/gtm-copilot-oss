'use client';
import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import PersistentChat from './PersistentChat';
import PreCallFields from './SectionFields/PreCallFields';
import PostCallFields from './SectionFields/PostCallFields';
import FollowUpFields from './SectionFields/FollowUpFields';
import TalFields from './SectionFields/TalFields';
import SEPocPlanFields from './SectionFields/SEPocPlanFields';
import SEArchFitFields from './SectionFields/SEArchFitFields';
import SECompetitorFields from './SectionFields/SECompetitorFields';

const SECTIONS = [
  { key: 'pre_call', label: 'Pre-Call Intel' },
  { key: 'post_call', label: 'Post-Call Analysis' },
  { key: 'follow_up', label: 'Follow-Up Email' },
  { key: 'tal', label: 'Market Research / TAL' },
  { key: 'se_poc_plan', label: 'SE: POC Plan' },
  { key: 'se_arch_fit', label: 'SE: Architecture Fit' },
  { key: 'se_competitor', label: 'SE: Competitor Coach' },
];

const FIELD_COMPONENTS = {
  pre_call: PreCallFields,
  post_call: PostCallFields,
  follow_up: FollowUpFields,
  tal: TalFields,
  se_poc_plan: SEPocPlanFields,
  se_arch_fit: SEArchFitFields,
  se_competitor: SECompetitorFields,
};

export default function ChatWorkspace() {
  const [section, setSection] = useState('pre_call');
  const [fieldValues, setFieldValues] = useState({});
  const [templates, setTemplates] = useState({}); // { section_key: { default: '...', users: [{user_email, content, template_name}] } }
  const [allUserTemplates, setAllUserTemplates] = useState([]); // [{user_email, section_key, template_name, content}]
  const [selectedTemplateUser, setSelectedTemplateUser] = useState('default'); // 'default' or email
  const [chatDraft, setChatDraft] = useState(''); // what gets pasted into PersistentChat input
  const [populateSignal, setPopulateSignal] = useState(0); // increment to trigger populate

  // Fetch templates on mount
  useEffect(() => {
    async function loadTemplates() {
      try {
        const [ownRes, allRes] = await Promise.all([
          fetch('/api/user/templates'),
          fetch('/api/templates/all'),
        ]);
        const own = ownRes.ok ? await ownRes.json() : [];
        const all = allRes.ok ? await allRes.json() : [];

        // Build templates map: section_key -> { default: content, custom: content, users: [] }
        const map = {};
        for (const t of own) {
          if (!map[t.section_key]) map[t.section_key] = { default: null, custom: null };
          if (t.is_default) map[t.section_key].default = t.content;
          else map[t.section_key].custom = t.content;
        }
        setTemplates(map);
        setAllUserTemplates(all);
      } catch { /* use hardcoded defaults */ }
    }
    loadTemplates();
  }, []);

  const updateField = (key, value) => setFieldValues(prev => ({ ...prev, [key]: value }));

  const getTemplate = () => {
    if (selectedTemplateUser === 'default') {
      return templates[section]?.default || HARDCODED_DEFAULTS[section] || '';
    }
    // Another user's template
    const found = allUserTemplates.find(t => t.section_key === section && t.user_email === selectedTemplateUser);
    return found?.content || HARDCODED_DEFAULTS[section] || '';
  };

  const handlePopulate = () => {
    const account = fieldValues.account?.trim() || '';
    if (!account) return; // account required

    let tpl = getTemplate();

    // Resolve {call_context} from selected calls
    const selectedCalls = fieldValues.selectedCalls || [];
    const callContext = selectedCalls.length > 0
      ? selectedCalls.map(c => `${c.account || 'Unknown'} (${c.date ? new Date(c.date).toLocaleDateString() : '—'}${c.stage ? ', ' + c.stage : ''}${c.rep_email ? ', rep: ' + c.rep_email : ''})`).join('\n')
      : '[no call selected]';

    // Substitute all fields
    const substitutions = {
      account,
      website: fieldValues.website || '[website]',
      prospect_name: fieldValues.prospect_name || '[prospect_name]',
      prospect_linkedin: fieldValues.prospect_linkedin || '[prospect_linkedin]',
      call_context: callContext,
      email_to: fieldValues.email_to || '[email_to]',
      email_cc: fieldValues.email_cc || '',
      email_tone: fieldValues.email_tone || 'crisp',
      regions: fieldValues.regions || '[regions]',
      industry: fieldValues.industry || '[industry]',
      revenue_min: fieldValues.revenue_min || '[revenue_min]',
      revenue_max: fieldValues.revenue_max || '[revenue_max]',
      context: fieldValues.context || '',
      top_n: fieldValues.top_n || '25',
      target_offering: fieldValues.target_offering || 'Managed Distributed SQL',
      competitor: fieldValues.competitor || '[competitor]',
    };

    for (const [k, v] of Object.entries(substitutions)) {
      tpl = tpl.replaceAll(`{${k}}`, v);
    }

    setChatDraft(tpl);
    setPopulateSignal(s => s + 1);
  };

  const FieldComponent = FIELD_COMPONENTS[section];

  // Template picker options for current section
  const pickerOptions = [
    { value: 'default', label: 'Default' },
    ...allUserTemplates
      .filter(t => t.section_key === section)
      .map(t => ({ value: t.user_email, label: `${t.user_email.split('@')[0]} — ${t.template_name}` })),
  ];

  const canPopulate = Boolean(fieldValues.account?.trim());

  const [loggingOut, setLoggingOut] = useState(false);
  const handleLogout = async () => {
    setLoggingOut(true);
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.45rem 1rem', borderBottom: '1px solid var(--border)', background: 'var(--bg-2)', flexShrink: 0, gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text)' }}>GTM Copilot</span>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>Revenue Intelligence</span>
        </div>
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          <Link href="/settings" style={{ fontSize: '0.78rem', color: 'var(--text-2)', padding: '0.3rem 0.6rem', borderRadius: '4px', textDecoration: 'none', border: '1px solid var(--border)' }}>⚙ Settings</Link>
          <button onClick={handleLogout} disabled={loggingOut} style={{ fontSize: '0.78rem', color: 'var(--text-2)', padding: '0.3rem 0.6rem', borderRadius: '4px', background: 'transparent', border: '1px solid var(--border)', cursor: 'pointer' }}>
            {loggingOut ? 'Signing out…' : '→ Sign out'}
          </button>
        </div>
      </div>

    <div className="rep-split" style={{ flex: 1, minHeight: 0 }}>
      {/* LEFT */}
      <div className="rep-inputs">
        <div className="rep-inputs-scroll">
          {/* Section picker */}
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>Section</label>
            <select className="input" value={section} onChange={e => { setSection(e.target.value); setSelectedTemplateUser('default'); }}>
              {SECTIONS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </div>

          {/* Template picker */}
          {pickerOptions.length > 1 && (
            <div style={{ display: 'grid', gap: '0.35rem' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>Template</label>
              <select className="input" value={selectedTemplateUser} onChange={e => setSelectedTemplateUser(e.target.value)}>
                {pickerOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          )}

          {/* Dynamic section fields */}
          <FieldComponent values={fieldValues} onChange={updateField} />

          {/* Populate button */}
          <button
            className="btn btn-primary"
            onClick={handlePopulate}
            disabled={!canPopulate}
            style={{ width: '100%', marginTop: '0.25rem' }}
          >
            {canPopulate ? '⬇ Populate Template' : 'Enter account name to populate'}
          </button>
        </div>
      </div>

      {/* RIGHT */}
      <PersistentChat draft={chatDraft} populateSignal={populateSignal} />
    </div>
    </div>
  );
}

// Hardcoded defaults (fallback when backend unavailable)
const HARDCODED_DEFAULTS = {
  pre_call: `I'm preparing for a call with {prospect_name} at {account} ({website}). Research the following and fill in each section completely.

**Section 1 — Prospect Information**
- Name: {prospect_name}
- LinkedIn: {prospect_linkedin}
- Role / Title: [find from LinkedIn or web]
- Time at current company: [find from LinkedIn]
- Relevant previous company or role: [find from LinkedIn]

**Section 2 — Company Context**
- Company: {account}
- # of employees or revenue range: [find from web/Crunchbase]
- Industry: [identify]
- Product or service they provide: [summarize]
- Key competitors: [list 2-3]

**Section 3 — Current Architecture Hypothesis**
Based on job postings, GitHub, BuiltWith, and news:
- Databases they likely use: [e.g. Aurora, MySQL, PostgreSQL]
- Applications or microservices: [describe if known]
- Cloud provider / infrastructure: [AWS / GCP / Azure / hybrid]

**Section 4 — Pain Hypothesis**
Identify at least two likely pains (e.g. scaling database clusters, operational complexity, cost of infrastructure, analytics latency, MySQL sharding limits):
1. [Pain 1 + evidence or signal]
2. [Pain 2 + evidence or signal]

**Section 5 — Relevant TiDB Value Propositions**
Match each pain to a specific TiDB capability:
- Pain: [Pain 1] → Value Prop: [TiDB capability]
- Pain: [Pain 2] → Value Prop: [TiDB capability]

**Section 6 — Meeting Goal**
Suggested desired outcome of the meeting (e.g. schedule architecture deep dive, obtain data for sizing exercise, introduce platform team stakeholders):
[Suggest based on company stage and pain]

**Section 7 — Meeting Flow Agreement**
Suggest how the meeting should run:
- Who does introductions: [Rep / SE]
- Who leads discovery: [Rep]
- Who handles technical questions: [SE]
- Suggested time allocation: [e.g. 5 min intro, 20 min discovery, 15 min demo/overview, 5 min next steps]
- Who asks for next steps: [Rep]`,

  post_call: `I just completed a call with {account}. Here are the call details:

{call_context}

Please analyze and produce:
1. **Call Summary** — key topics discussed, decisions made
2. **Next Steps** — agreed actions with owners (Rep, SE, Prospect)
3. **Action Items** — broken out per person: Rep / SE / {account} contact
4. **MEDDPICC Analysis** — for each element (Metrics, Economic Buyer, Decision Criteria, Decision Process, Paper Process, Implicate Pain, Champion, Competition): what was established vs. what is missing
5. **Qualification Assessment** — is this deal actually qualified? What are the top 3 gaps to close?`,

  follow_up: `Draft a follow-up email for my call with {account}.

Recipients: To: {email_to} | CC: {email_cc}
Tone: {email_tone}
Call context: {call_context}

Include: summary of what was discussed, agreed next steps with owners, clear CTA for the next meeting.`,

  tal: `Build a target account list for the following criteria:
- Regions: {regions}
- Industry: {industry}
- Revenue range: \${revenue_min}M – \${revenue_max}M
- Reference account: {account}
- Additional context: {context}

Return the top {top_n} accounts most likely to need TiDB. For each: company name, why they're a fit, estimated revenue, and key signal.`,

  se_poc_plan: `Create a technical POC evaluation roadmap for {account}.
Offering: {target_offering}
Call context: {call_context}

Include: POC objectives, success criteria, technical requirements, 4-week milestone plan, resources needed, risk factors.`,

  se_arch_fit: `Analyze TiDB architecture fit for {account}.
Call context: {call_context}

Cover: current database signals, scalability pain, MySQL/Oracle compatibility needs, HTAP potential, migration complexity, TiDB placement recommendation.`,

  se_competitor: `Competitor coaching for {account} — primary competitor: {competitor}.
Call context: {call_context}

Provide: competitive positioning vs {competitor}, top 5 objections and TiDB responses, where TiDB wins and where to be careful, recommended proof points.`,
};
