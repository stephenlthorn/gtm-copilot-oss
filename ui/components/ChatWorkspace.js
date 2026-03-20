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
  const [ragEnabled, setRagEnabled] = useState(true);
  const [webSearchEnabled, setWebSearchEnabled] = useState(true);

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
        <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
          <button
            onClick={() => setRagEnabled(v => !v)}
            title="Toggle knowledge base retrieval"
            style={{ fontSize: '0.72rem', padding: '0.25rem 0.55rem', borderRadius: '4px', border: '1px solid var(--border)', cursor: 'pointer', background: ragEnabled ? 'var(--accent)' : 'transparent', color: ragEnabled ? '#fff' : 'var(--text-2)' }}
          >
            KB {ragEnabled ? 'On' : 'Off'}
          </button>
          <button
            onClick={() => setWebSearchEnabled(v => !v)}
            title="Toggle web search"
            style={{ fontSize: '0.72rem', padding: '0.25rem 0.55rem', borderRadius: '4px', border: '1px solid var(--border)', cursor: 'pointer', background: webSearchEnabled ? 'var(--accent)' : 'transparent', color: webSearchEnabled ? '#fff' : 'var(--text-2)' }}
          >
            Web {webSearchEnabled ? 'On' : 'Off'}
          </button>
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
      <PersistentChat draft={chatDraft} populateSignal={populateSignal} ragEnabled={ragEnabled} webSearchEnabled={webSearchEnabled} />
    </div>
    </div>
  );
}

// Hardcoded defaults (source of truth — also seeded to DB)
export const HARDCODED_DEFAULTS = {
  pre_call: `I'm preparing for a sales call with {prospect_name} at {account} ({website}). Please research this prospect and company thoroughly and complete each section below.

**Section 1 — Prospect Information**
Research {prospect_name} ({prospect_linkedin}) and document:
• Name: {prospect_name}
• Role / Title:
• Time at current company:
• Relevant previous company or role:

Example:
Prospect: John Smith
Role: Director of Platform Engineering
Time at company: 3 years
Previous company: Stripe – Senior Infrastructure Engineer

**Section 2 — Company Context**
Research {account} ({website}) and document:
• # of employees or revenue range:
• Industry:
• Product or service they provide:
• Key competitors:

**Section 3 — Current Architecture Hypothesis**
Based on job postings, GitHub, BuiltWith, Stackshare, and news — hypothesize:
• Databases they likely use:
• Applications or microservices:
• Cloud provider / infrastructure:

Example:
Databases: Aurora, Redis
Cloud: AWS
Architecture: microservices-based platform

**Section 4 — Pain Hypothesis**
Document at least two potential pains the prospect may have.
Examples: scaling database clusters, operational complexity, cost of infrastructure, analytics latency, MySQL sharding limits

1. Pain:
   Signal / evidence:
2. Pain:
   Signal / evidence:

**Section 5 — Relevant TiDB Value Propositions**
Match each pain to a specific TiDB capability:

Pain: [Pain 1]
Value Prop:

Pain: [Pain 2]
Value Prop:

Example:
Pain: operational complexity
Value Prop: No manual sharding; automatic recovery after failure; one system for OLTP and OLAP

**Section 6 — Meeting Goal**
Define the desired outcome of this meeting. Suggest one:
• Schedule architecture deep dive
• Obtain data for sizing exercise
• Introduce platform team stakeholders
• Confirm champion and access to economic buyer

Suggested goal based on research:

**Section 7 — Meeting Flow Agreement**
Document how the meeting will run:
• Who does introductions:
• Who leads discovery:
• Who handles technical questions:
• Time allocation (e.g. 5 min intro / 20 min discovery / 10 min TiDB overview / 5 min next steps):
• Who asks for next steps:`,

  post_call: `I just completed a sales call with {account}. Here are the call details:

{call_context}

Please analyze the call and produce a complete post-call brief:

**Call Summary**
Summarize the key topics discussed, decisions made, and overall tone of the call.

**Next Steps**
List all agreed-upon next steps with owners and target dates.

**Action Items by Person**

Rep:
•

SE:
•

{account} Contact:
•

**MEDDPICC Analysis**
For each element, note what was established on this call and what is still missing:

Metrics (quantifiable impact / value):
Economic Buyer (who controls budget):
Decision Criteria (what they will evaluate):
Decision Process (how they make the decision):
Paper Process (legal / procurement / security steps):
Implicate Pain (is the pain urgent enough to act?):
Champion (who is selling internally for us?):
Competition (what else are they evaluating?):

**Qualification Assessment**
• Is this deal actually qualified? (Yes / No / Conditional)
• Top 3 qualification gaps to close:
  1.
  2.
  3.
• Recommended next action to advance:`,

  follow_up: `Draft a follow-up email for my call with {account}.

To: {email_to}
CC: {email_cc}
Tone: {email_tone}

Call context:
{call_context}

The email should include:
1. A brief thank-you and summary of what was discussed
2. Agreed next steps with clear owners and dates
3. Any resources or materials promised during the call
4. A clear call-to-action for scheduling the next meeting

Keep it concise and professional. Match the {email_tone} tone:
• crisp = brief and direct
• executive = polished and high-level
• technical = detailed and specific`,

  tal: `Build a target account list based on the following criteria:

Reference account: {account}
Regions / Territory: {regions}
Industry vertical: {industry}
Revenue range: \${revenue_min}M – \${revenue_max}M
Additional context: {context}

Return the top {top_n} accounts most likely to benefit from TiDB. For each account provide:
• Company name
• Why they are a strong TiDB fit (specific signal)
• Estimated revenue or employee count
• Key pain signal (job postings, tech stack, news)
• Recommended entry point (who to target, what angle)

Prioritize companies showing signals of: MySQL/Aurora at scale, database sharding, high-volume OLTP, real-time analytics needs, or significant infrastructure investment.`,

  se_poc_plan: `Create a detailed technical POC evaluation roadmap for {account}.

Offering: {target_offering}
Call context: {call_context}

Produce a complete POC plan including:

**POC Objectives**
What success looks like for the customer and for us.

**Success Criteria**
Specific, measurable criteria the customer will use to evaluate TiDB. Include at least 3.

**Technical Requirements**
What we need from the customer to run the POC (access, data, team members, environments).

**4-Week Milestone Plan**
Week 1: Setup and baseline
Week 2: Core workload migration / test
Week 3: Performance and scale testing
Week 4: Results review and business case

**Resources Required**
From TiDB side and from customer side.

**Risk Factors & Mitigations**
Top 3 risks and how to address them.

**Recommended POC Kit**
Suggest relevant TiDB documentation, benchmarks, or migration tools.`,

  se_arch_fit: `Analyze TiDB architecture fit for {account}.

Call context: {call_context}

Produce a complete architecture fit analysis:

**Current State Assessment**
Based on call context and research — what database and infrastructure does {account} likely use today?

**Scalability Pain Signals**
What evidence suggests they are hitting scale limits with their current stack?

**MySQL / PostgreSQL / Oracle Compatibility**
How compatible is their existing workload with TiDB's MySQL compatibility layer?

**HTAP Opportunity**
Is there a real-time analytics or HTAP use case? Describe it if present.

**Migration Complexity Assessment**
Rate migration complexity (Low / Medium / High) and explain why.

**TiDB Placement Recommendation**
Where does TiDB fit in their architecture?
(Replace primary DB / Add as analytics layer / Modernize sharded MySQL / Greenfield new service)

**Target State Architecture**
Describe what the architecture would look like with TiDB in place.`,

  se_competitor: `Competitor coaching for {account} — primary competitor in this deal: {competitor}.

Call context: {call_context}

Produce a complete competitive coaching brief:

**Competitive Positioning vs {competitor}**
Where TiDB wins, where to be careful, and where it is a draw.

**Top 5 Objections & TiDB Responses**
1. Objection: | Response:
2. Objection: | Response:
3. Objection: | Response:
4. Objection: | Response:
5. Objection: | Response:

**{competitor} Weaknesses to Probe**
Key questions to ask the customer that expose {competitor} limitations.

**TiDB Proof Points**
Specific benchmarks, case studies, or technical references that counter {competitor}'s strengths.

**Recommended Demo or POC Focus**
What to show in a demo or POC that {competitor} cannot match.

**Deal Strategy Recommendation**
Given what we know about {account} and {competitor}, what is the recommended win strategy?`,
};
