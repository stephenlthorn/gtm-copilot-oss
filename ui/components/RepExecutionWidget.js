'use client';

import { useMemo, useState } from 'react';

function Section({ title, children }) {
  return (
    <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.7rem', marginTop: '0.2rem' }}>
      <div className="citation-label" style={{ marginBottom: '0.45rem' }}>{title}</div>
      {children}
    </div>
  );
}

export default function RepExecutionWidget() {
  const [account, setAccount] = useState('');
  const [chorusCallId, setChorusCallId] = useState('');
  const [website, setWebsite] = useState('');
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [count, setCount] = useState(6);
  const [tone, setTone] = useState('crisp');
  const [to, setTo] = useState('rep.one@example.com');
  const [cc, setCc] = useState('se.one@example.com');
  const [mode, setMode] = useState('draft');

  const [brief, setBrief] = useState(null);
  const [questions, setQuestions] = useState(null);
  const [risk, setRisk] = useState(null);
  const [draft, setDraft] = useState(null);
  const [fullSolution, setFullSolution] = useState(null);

  const [loadingAction, setLoadingAction] = useState('');
  const [error, setError] = useState('');

  const basePayload = useMemo(
    () => ({
      account: account.trim(),
      chorus_call_id: chorusCallId || null,
      website: website.trim() || null,
      linkedin_url: linkedinUrl.trim() || null,
    }),
    [account, chorusCallId, website, linkedinUrl]
  );

  const run = async (action) => {
    if (!basePayload.account) {
      setError('Enter an account name.');
      return;
    }
    setError('');
    setLoadingAction(action);
    try {
      let path = '';
      let payload = { ...basePayload };

      if (action === 'brief') {
        path = '/api/rep/account-brief';
      } else if (action === 'questions') {
        path = '/api/rep/discovery-questions';
        payload.count = Number(count) || 6;
      } else if (action === 'risk') {
        path = '/api/rep/deal-risk';
      } else if (action === 'draft') {
        path = '/api/rep/follow-up-draft';
        payload.to = to.split(',').map((s) => s.trim()).filter(Boolean);
        payload.cc = cc.split(',').map((s) => s.trim()).filter(Boolean);
        payload.mode = mode;
        payload.tone = tone;
      } else if (action === 'full') {
        path = '/api/rep/full-solution';
        payload.count = Number(count) || 6;
        payload.to = to.split(',').map((s) => s.trim()).filter(Boolean);
        payload.cc = cc.split(',').map((s) => s.trim()).filter(Boolean);
        payload.mode = mode;
        payload.tone = tone;
      }

      const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || data?.error || 'Request failed');
      }

      if (action === 'brief') setBrief(data);
      if (action === 'questions') setQuestions(data);
      if (action === 'risk') setRisk(data);
      if (action === 'draft') setDraft(data);
      if (action === 'full') {
        setFullSolution(data);
        setBrief(data.account_brief || null);
        setQuestions(data.discovery_questions || null);
        setRisk(data.deal_risk || null);
        setDraft(data.follow_up_draft || null);
      }
    } catch (err) {
      setError(String(err?.message || err));
    } finally {
      setLoadingAction('');
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Rep Automation</span>
        <span className="tag">Phase 1-3</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div className="two-col" style={{ gap: '0.75rem' }}>
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Account</label>
            <input
              className="input"
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              placeholder="Enter account name"
            />
          </div>
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Call ID (optional)</label>
            <input
              className="input"
              value={chorusCallId}
              onChange={(e) => setChorusCallId(e.target.value)}
              placeholder="Leave blank to use latest call for this account"
            />
          </div>
        </div>
        <div className="two-col" style={{ gap: '0.75rem' }}>
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Company Website (optional)</label>
            <input
              className="input"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              placeholder="e.g. https://example.com"
            />
          </div>
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Prospect LinkedIn URL (optional)</label>
            <input
              className="input"
              value={linkedinUrl}
              onChange={(e) => setLinkedinUrl(e.target.value)}
              placeholder="e.g. https://linkedin.com/in/john-doe"
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={() => run('full')} disabled={Boolean(loadingAction)}>
            {loadingAction === 'full' ? 'Generating…' : 'Generate Full Solution (Phases 1-3)'}
          </button>
          <button className="btn" onClick={() => run('brief')} disabled={Boolean(loadingAction)}>
            {loadingAction === 'brief' ? 'Generating…' : 'Generate Account Brief'}
          </button>
          <button className="btn" onClick={() => run('questions')} disabled={Boolean(loadingAction)}>
            {loadingAction === 'questions' ? 'Generating…' : 'Generate Discovery Questions'}
          </button>
          <button className="btn" onClick={() => run('risk')} disabled={Boolean(loadingAction)}>
            {loadingAction === 'risk' ? 'Generating…' : 'Generate Deal Risk'}
          </button>
          <button className="btn btn-primary" onClick={() => run('draft')} disabled={Boolean(loadingAction)}>
            {loadingAction === 'draft' ? 'Generating…' : 'Generate Follow-Up Draft'}
          </button>
        </div>

        <div className="two-col" style={{ gap: '0.75rem' }}>
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Question Count</label>
            <input className="input" type="number" min={3} max={12} value={count} onChange={(e) => setCount(e.target.value)} />
          </div>
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Draft Tone</label>
            <select className="input" value={tone} onChange={(e) => setTone(e.target.value)}>
              <option value="crisp">Crisp</option>
              <option value="executive">Executive</option>
              <option value="technical">Technical</option>
            </select>
          </div>
        </div>

        <div className="two-col" style={{ gap: '0.75rem' }}>
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>To (comma-separated)</label>
            <input className="input" value={to} onChange={(e) => setTo(e.target.value)} />
          </div>
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>CC (comma-separated)</label>
            <input className="input" value={cc} onChange={(e) => setCc(e.target.value)} />
          </div>
        </div>

        <div style={{ display: 'grid', gap: '0.35rem', maxWidth: '220px' }}>
          <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Draft Mode</label>
          <select className="input" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="draft">Draft</option>
            <option value="send">Send</option>
          </select>
        </div>

        {error ? <div className="error-text">{error}</div> : null}

        {(fullSolution || brief || questions || risk || draft) && (
          <div className="answer-box" style={{ display: 'grid', gap: '0.6rem' }}>
            {fullSolution && (
              <Section title="Full Solution Summary">
                <ul className="citation-list">
                  {(fullSolution.phase_2_execution_focus || []).map((item) => <li key={item}>{item}</li>)}
                </ul>
                <div className="citation-label" style={{ marginTop: '0.6rem', marginBottom: '0.35rem' }}>
                  Phase 3 Automation
                </div>
                <ul className="citation-list">
                  {(fullSolution.phase_3_automation_next_steps || []).map((item) => <li key={item}>{item}</li>)}
                </ul>
              </Section>
            )}

            {brief && (
              <Section title="Account Brief">
                <div className="answer-text" style={{ marginBottom: '0.75rem' }}>{brief.summary}</div>

                {brief.prospect_information?.name && (
                  <div style={{ marginBottom: '0.6rem' }}>
                    <div className="citation-label" style={{ marginBottom: '0.25rem' }}>1. Prospect Information</div>
                    <ul className="citation-list">
                      {brief.prospect_information.name && <li><strong>Name:</strong> {brief.prospect_information.name}</li>}
                      {brief.prospect_information.title && <li><strong>Title:</strong> {brief.prospect_information.title}</li>}
                      {brief.prospect_information.time_at_company && <li><strong>Tenure:</strong> {brief.prospect_information.time_at_company}</li>}
                      {brief.prospect_information.previous_role && <li><strong>Previous Role:</strong> {brief.prospect_information.previous_role}</li>}
                    </ul>
                  </div>
                )}

                {(brief.company_context?.industry || brief.company_context?.product_service) && (
                  <div style={{ marginBottom: '0.6rem' }}>
                    <div className="citation-label" style={{ marginBottom: '0.25rem' }}>2. Company Context</div>
                    <ul className="citation-list">
                      {brief.company_context.industry && <li><strong>Industry:</strong> {brief.company_context.industry}</li>}
                      {brief.company_context.employee_count && <li><strong>Employees:</strong> {brief.company_context.employee_count.toLocaleString()}</li>}
                      {brief.company_context.revenue && <li><strong>Revenue:</strong> {brief.company_context.revenue}</li>}
                      {brief.company_context.product_service && <li><strong>Product/Service:</strong> {brief.company_context.product_service}</li>}
                      {(brief.company_context.competitors || []).length > 0 && (
                        <li><strong>Competitors:</strong> {brief.company_context.competitors.join(', ')}</li>
                      )}
                    </ul>
                  </div>
                )}

                {(brief.architecture_hypothesis?.databases?.length > 0 || brief.architecture_hypothesis?.cloud_infrastructure) && (
                  <div style={{ marginBottom: '0.6rem' }}>
                    <div className="citation-label" style={{ marginBottom: '0.25rem' }}>3. Architecture Hypothesis</div>
                    <ul className="citation-list">
                      {(brief.architecture_hypothesis.databases || []).length > 0 && (
                        <li><strong>Databases:</strong> {brief.architecture_hypothesis.databases.join(', ')}</li>
                      )}
                      {brief.architecture_hypothesis.apps_microservices && (
                        <li><strong>Apps/Services:</strong> {brief.architecture_hypothesis.apps_microservices}</li>
                      )}
                      {brief.architecture_hypothesis.cloud_infrastructure && (
                        <li><strong>Cloud/Infra:</strong> {brief.architecture_hypothesis.cloud_infrastructure}</li>
                      )}
                    </ul>
                  </div>
                )}

                {(brief.pain_hypothesis || []).length > 0 && (
                  <div style={{ marginBottom: '0.6rem' }}>
                    <div className="citation-label" style={{ marginBottom: '0.25rem' }}>4. Pain Hypothesis</div>
                    <ul className="citation-list">
                      {brief.pain_hypothesis.map((p, i) => (
                        <li key={i}><strong>{p.pain}</strong> — {p.evidence}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {(brief.tidb_value_propositions || []).length > 0 && (
                  <div style={{ marginBottom: '0.6rem' }}>
                    <div className="citation-label" style={{ marginBottom: '0.25rem' }}>5. TiDB Value Propositions</div>
                    <ul className="citation-list">
                      {brief.tidb_value_propositions.map((v, i) => (
                        <li key={i}><strong>{v.pain}:</strong> {v.value_prop}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {brief.meeting_goal && (
                  <div style={{ marginBottom: '0.6rem' }}>
                    <div className="citation-label" style={{ marginBottom: '0.25rem' }}>6. Meeting Goal</div>
                    <div className="answer-text">{brief.meeting_goal}</div>
                  </div>
                )}

                {(brief.meeting_flow?.agenda || []).length > 0 && (
                  <div style={{ marginBottom: '0.6rem' }}>
                    <div className="citation-label" style={{ marginBottom: '0.25rem' }}>7. Meeting Flow</div>
                    <ul className="citation-list">
                      {brief.meeting_flow.agenda.map((item, i) => <li key={i}>{item}</li>)}
                    </ul>
                  </div>
                )}

                {(brief.next_meeting_agenda || []).length > 0 && (
                  <div>
                    <div className="citation-label" style={{ marginBottom: '0.25rem' }}>Next Steps</div>
                    <ul className="citation-list">
                      {brief.next_meeting_agenda.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </div>
                )}
              </Section>
            )}

            {questions && (
              <Section title="Discovery Questions">
                <ul className="citation-list">
                  {(questions.questions || []).map((item) => <li key={item}>{item}</li>)}
                </ul>
              </Section>
            )}

            {risk && (
              <Section title={`Deal Risk (${risk.risk_level || 'n/a'})`}>
                <ul className="citation-list">
                  {(risk.risks || []).map((item, idx) => (
                    <li key={`${item.signal}-${idx}`}>{item.signal} — {item.mitigation}</li>
                  ))}
                </ul>
              </Section>
            )}

            {draft && (
              <Section title={`Follow-Up Draft (${draft.mode})`}>
                <div className="answer-text" style={{ fontWeight: 600, marginBottom: '0.35rem' }}>{draft.subject}</div>
                {draft.reason_blocked ? (
                  <div className="error-text" style={{ marginTop: 0 }}>{draft.reason_blocked}</div>
                ) : (
                  <pre style={{ marginTop: '0.25rem' }}>{draft.body}</pre>
                )}
              </Section>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
