'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import FeedbackButtons from './FeedbackButtons';

// ── Small helpers ────────────────────────────────────────────────────────────

function PhaseModule({ number, title, subtitle, children }) {
  return (
    <div className="rep-phase">
      <div className="rep-phase-header">
        <div className="rep-phase-num">{number}</div>
        <div>
          <div className="rep-phase-title">{title}</div>
          {subtitle && <div className="rep-phase-sub">{subtitle}</div>}
        </div>
      </div>
      <div className="rep-phase-body">{children}</div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ display: 'grid', gap: '0.3rem' }}>
      <label style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>{label}</label>
      {children}
    </div>
  );
}

function ResultSection({ title, children }) {
  return (
    <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.65rem' }}>
      <div className="citation-label" style={{ marginBottom: '0.4rem' }}>{title}</div>
      {children}
    </div>
  );
}

// ── Call selector with hourly auto-sync ───────────────────────────────────────

const SYNC_INTERVAL_MS = 60 * 60 * 1000; // 1 hour

function CallSelector({ account, selectedIds, onChange }) {
  const [allCalls, setAllCalls] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('date'); // 'date' | 'company'
  const [sortDir, setSortDir] = useState('desc'); // 'asc' | 'desc'
  const timerRef = useRef(null);

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortDir(field === 'date' ? 'desc' : 'asc');
    }
  };

  const fetchCalls = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/calls?limit=200');
      if (!res.ok) throw new Error('Failed to load calls');
      const data = await res.json();
      setAllCalls(Array.isArray(data) ? data : []);
      setLastSync(new Date());
    } catch {
      setAllCalls([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load all calls on mount; auto-sync hourly
  useEffect(() => {
    fetchCalls();
    timerRef.current = setInterval(fetchCalls, SYNC_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [fetchCalls]);

  // Filter
  const filterTerm = search.trim() || account?.trim() || '';
  const filtered = filterTerm
    ? allCalls.filter((c) =>
        (c.account || '').toLowerCase().includes(filterTerm.toLowerCase()) ||
        (c.opportunity || '').toLowerCase().includes(filterTerm.toLowerCase())
      )
    : allCalls;

  // Sort
  const calls = [...filtered].sort((a, b) => {
    let av, bv;
    if (sortBy === 'date') {
      av = a.date || '';
      bv = b.date || '';
    } else {
      av = (a.account || '').toLowerCase();
      bv = (b.account || '').toLowerCase();
    }
    if (av < bv) return sortDir === 'asc' ? -1 : 1;
    if (av > bv) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });

  const toggle = (id) => {
    onChange(
      selectedIds.includes(id)
        ? selectedIds.filter((x) => x !== id)
        : [...selectedIds, id]
    );
  };

  if (loading && allCalls.length === 0) {
    return <div style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>Loading calls…</div>;
  }

  const SortBtn = ({ field, label }) => (
    <button
      className={`oracle-chat-ctrl${sortBy === field ? ' oracle-chat-ctrl--active' : ''}`}
      onClick={() => toggleSort(field)}
      style={{ fontSize: '0.68rem', whiteSpace: 'nowrap' }}
    >
      {label} {sortBy === field ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}
    </button>
  );

  return (
    <div style={{ display: 'grid', gap: '0.45rem' }}>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
        <input
          className="input"
          style={{ flex: 1, fontSize: '0.8rem' }}
          placeholder={account?.trim() ? `Filtering by "${account}" — type to override` : 'Search by account or opportunity…'}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <SortBtn field="date" label="Date" />
        <SortBtn field="company" label="Company" />
        <button
          className="oracle-chat-ctrl"
          onClick={fetchCalls}
          disabled={loading}
          style={{ fontSize: '0.68rem', whiteSpace: 'nowrap' }}
        >
          {loading ? '…' : '↻'}
        </button>
      </div>

      <div style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>
        {calls.length} of {allCalls.length} call{allCalls.length !== 1 ? 's' : ''}
        {lastSync && ` · synced ${lastSync.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
        {selectedIds.length > 0 && ` · ${selectedIds.length} selected`}
      </div>

      {calls.length === 0 && !loading && (
        <div style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>No calls match "{filterTerm}".</div>
      )}

      <div className="call-list">
        {calls.map((c) => {
          const id = c.chorus_call_id;
          const checked = selectedIds.includes(id);
          return (
            <label key={id} className={`call-item${checked ? ' call-item--selected' : ''}`}>
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(id)}
                style={{ marginRight: '0.5rem', flexShrink: 0 }}
              />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '0.82rem', fontWeight: checked ? 600 : 400, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.account || 'Unknown account'}
                  {c.opportunity ? ` — ${c.opportunity}` : ''}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>
                  {c.date ? new Date(c.date).toLocaleDateString() : 'No date'}
                  {c.stage ? ` · ${c.stage}` : ''}
                  {c.rep_email ? ` · ${c.rep_email}` : ''}
                </div>
              </div>
            </label>
          );
        })}
      </div>
    </div>
  );
}

// ── Main widget ───────────────────────────────────────────────────────────────

export default function RepExecutionWidget() {
  // Phase 1 — Research Company
  const [account, setAccount] = useState('');
  const [website, setWebsite] = useState('');

  // Phase 2 — Research Prospect
  const [prospectName, setProspectName] = useState('');
  const [prospectLinkedin, setProspectLinkedin] = useState('');

  // Phase 3 — Market Research / TAL
  const [regions, setRegions] = useState('');
  const [industry, setIndustry] = useState('');
  const [revenueMin, setRevenueMin] = useState('');
  const [revenueMax, setRevenueMax] = useState('');
  const [talContext, setTalContext] = useState('');
  const [talCount, setTalCount] = useState(25);

  // Call context
  const [selectedCallIds, setSelectedCallIds] = useState([]);
  const [emailTo, setEmailTo] = useState('');
  const [emailCc, setEmailCc] = useState('');
  const [emailTone, setEmailTone] = useState('crisp');

  // Results
  const [brief, setBrief] = useState(null);
  const [questions, setQuestions] = useState(null);
  const [risk, setRisk] = useState(null);
  const [draft, setDraft] = useState(null);
  const [talResult, setTalResult] = useState(null);
  const [fullSolution, setFullSolution] = useState(null);

  const [loadingAction, setLoadingAction] = useState('');
  const [error, setError] = useState('');

  const run = async (action) => {
    if (!account.trim()) { setError('Enter an account name in Phase 1.'); return; }
    setError('');
    setLoadingAction(action);
    try {
      const base = {
        account: account.trim(),
        website: website.trim() || null,
        prospect_name: prospectName.trim() || null,
        prospect_linkedin: prospectLinkedin.trim() || null,
        chorus_call_ids: selectedCallIds.length > 0 ? selectedCallIds : null,
        chorus_call_id: selectedCallIds[0] || null,
      };

      let path, payload;

      if (action === 'brief') {
        path = '/api/rep/account-brief';
        payload = base;
      } else if (action === 'questions') {
        path = '/api/rep/discovery-questions';
        payload = { ...base, count: 6 };
      } else if (action === 'full') {
        path = '/api/rep/full-solution';
        payload = { ...base, count: 6, tone: emailTone };
      } else if (action === 'risk') {
        path = '/api/rep/deal-risk';
        payload = base;
      } else if (action === 'draft') {
        path = '/api/rep/follow-up-draft';
        payload = {
          ...base,
          to: emailTo.split(',').map((s) => s.trim()).filter(Boolean),
          cc: emailCc.split(',').map((s) => s.trim()).filter(Boolean),
          tone: emailTone,
          mode: 'draft',
        };
      } else if (action === 'tal') {
        path = '/api/rep/market-research';
        payload = {
          account: account.trim(),
          regions: regions.split(',').map((s) => s.trim()).filter(Boolean),
          industry: industry.trim() || null,
          revenue_min: revenueMin ? Number(revenueMin) : null,
          revenue_max: revenueMax ? Number(revenueMax) : null,
          context: talContext.trim() || null,
          top_n: Number(talCount) || 25,
        };
      }

      const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || data?.error || 'Request failed');

      if (action === 'brief') setBrief(data);
      if (action === 'questions') setQuestions(data);
      if (action === 'risk') setRisk(data);
      if (action === 'draft') setDraft(data);
      if (action === 'tal') setTalResult(data);
      if (action === 'full') {
        setFullSolution(data);
        if (data.account_brief) setBrief(data.account_brief);
        if (data.discovery_questions) setQuestions(data.discovery_questions);
      }
    } catch (err) {
      setError(String(err?.message || err));
    } finally {
      setLoadingAction('');
    }
  };

  const busy = Boolean(loadingAction);

  return (
    <div style={{ display: 'grid', gap: '1.25rem' }}>

      {/* ── Phase 1 ── */}
      <PhaseModule number="1" title="Research Company" subtitle="Account name and website for OSINT + knowledge base lookup">
        <div className="two-col" style={{ gap: '0.65rem' }}>
          <Field label="Account Name *">
            <input className="input" value={account} onChange={(e) => setAccount(e.target.value)} placeholder="e.g. Acme Corp" />
          </Field>
          <Field label="Website (optional)">
            <input className="input" value={website} onChange={(e) => setWebsite(e.target.value)} placeholder="e.g. acmecorp.com" />
          </Field>
        </div>
      </PhaseModule>

      {/* ── Phase 2 ── */}
      <PhaseModule number="2" title="Research Prospect" subtitle="Key contact details for personalized discovery questions">
        <div className="two-col" style={{ gap: '0.65rem' }}>
          <Field label="Prospect Name">
            <input className="input" value={prospectName} onChange={(e) => setProspectName(e.target.value)} placeholder="e.g. Jane Smith" />
          </Field>
          <Field label="LinkedIn URL (optional)">
            <input className="input" value={prospectLinkedin} onChange={(e) => setProspectLinkedin(e.target.value)} placeholder="linkedin.com/in/..." />
          </Field>
        </div>
      </PhaseModule>

      {/* ── Phase 3 ── */}
      <PhaseModule number="3" title="Market Research / Target Account List" subtitle="Territory and filters for TAL generation">
        <div className="two-col" style={{ gap: '0.65rem' }}>
          <Field label="Regions / Territory">
            <input className="input" value={regions} onChange={(e) => setRegions(e.target.value)} placeholder="e.g. US West, APAC" />
          </Field>
          <Field label="Industry Vertical">
            <input className="input" value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="e.g. FinTech, SaaS" />
          </Field>
          <Field label="Revenue Min ($M)">
            <input className="input" type="number" value={revenueMin} onChange={(e) => setRevenueMin(e.target.value)} placeholder="e.g. 50" />
          </Field>
          <Field label="Revenue Max ($M)">
            <input className="input" type="number" value={revenueMax} onChange={(e) => setRevenueMax(e.target.value)} placeholder="e.g. 500" />
          </Field>
        </div>
        <div style={{ marginTop: '0.65rem', display: 'grid', gap: '0.65rem' }}>
          <Field label="Additional Context">
            <textarea className="input" rows={2} value={talContext} onChange={(e) => setTalContext(e.target.value)} placeholder="e.g. Companies using MySQL at scale, evaluating cloud DB migration" />
          </Field>
          <Field label="Top N accounts">
            <input className="input" type="number" min={5} max={100} style={{ maxWidth: '100px' }} value={talCount} onChange={(e) => setTalCount(e.target.value)} />
          </Field>
        </div>
      </PhaseModule>

      {/* ── Action buttons ── */}
      <div className="rep-actions">
        <div className="rep-actions-label">Generate</div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={() => run('full')} disabled={busy}>
            {loadingAction === 'full' ? 'Generating…' : 'Generate Full Solution (1–3)'}
          </button>
          <button className="btn" onClick={() => run('brief')} disabled={busy}>
            {loadingAction === 'brief' ? 'Generating…' : 'Account Brief'}
          </button>
          <button className="btn" onClick={() => run('questions')} disabled={busy}>
            {loadingAction === 'questions' ? 'Generating…' : 'Discovery Questions'}
          </button>
          <button className="btn" onClick={() => run('tal')} disabled={busy}>
            {loadingAction === 'tal' ? 'Generating…' : 'Target Account List'}
          </button>
        </div>
      </div>

      {/* ── Call context ── */}
      <div className="rep-phase">
        <div className="rep-phase-header">
          <div className="rep-phase-num" style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-2)' }}>📞</div>
          <div>
            <div className="rep-phase-title">Call Context</div>
            <div className="rep-phase-sub">Select one or more Chorus calls — syncs automatically every hour</div>
          </div>
        </div>
        <div className="rep-phase-body" style={{ display: 'grid', gap: '0.75rem' }}>
          <CallSelector account={account} selectedIds={selectedCallIds} onChange={setSelectedCallIds} />

          {/* Email fields — shown when at least one call selected */}
          {selectedCallIds.length > 0 && (
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.65rem', display: 'grid', gap: '0.65rem' }}>
              <div className="two-col" style={{ gap: '0.65rem' }}>
                <Field label="To (comma-separated emails)">
                  <input className="input" value={emailTo} onChange={(e) => setEmailTo(e.target.value)} placeholder="rep@company.com" />
                </Field>
                <Field label="CC (optional)">
                  <input className="input" value={emailCc} onChange={(e) => setEmailCc(e.target.value)} placeholder="se@company.com" />
                </Field>
              </div>
              <Field label="Email Tone">
                <select className="input" style={{ maxWidth: '160px' }} value={emailTone} onChange={(e) => setEmailTone(e.target.value)}>
                  <option value="crisp">Crisp</option>
                  <option value="executive">Executive</option>
                  <option value="technical">Technical</option>
                </select>
              </Field>
            </div>
          )}

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button className="btn btn-primary" onClick={() => run('risk')} disabled={busy || selectedCallIds.length === 0}>
              {loadingAction === 'risk' ? 'Analyzing…' : 'Generate Deal Risk'}
            </button>
            <button className="btn" onClick={() => run('draft')} disabled={busy || selectedCallIds.length === 0}>
              {loadingAction === 'draft' ? 'Drafting…' : 'Generate Follow-Up Draft'}
            </button>
          </div>
          {selectedCallIds.length === 0 && (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>Select at least one call to enable post-call actions.</div>
          )}
        </div>
      </div>

      {error && <div className="error-text">{error}</div>}

      {/* ── Results ── */}
      {(fullSolution || brief || questions || risk || draft || talResult) && (
        <div className="answer-box" style={{ display: 'grid', gap: '0.65rem' }}>

          {fullSolution && (
            <ResultSection title="Full Solution">
              {fullSolution.phase_2_execution_focus?.length > 0 && (
                <ul className="citation-list">
                  {fullSolution.phase_2_execution_focus.map((item) => <li key={item}>{item}</li>)}
                </ul>
              )}
              {fullSolution.phase_3_automation_next_steps?.length > 0 && (
                <>
                  <div className="citation-label" style={{ margin: '0.5rem 0 0.3rem' }}>Next Steps</div>
                  <ul className="citation-list">
                    {fullSolution.phase_3_automation_next_steps.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </>
              )}
            </ResultSection>
          )}

          {brief && (
            <ResultSection title="Account Brief">
              <p className="answer-text">{brief.summary}</p>
              {brief.next_meeting_agenda?.length > 0 && (
                <ul className="citation-list" style={{ marginTop: '0.4rem' }}>
                  {brief.next_meeting_agenda.map((item) => <li key={item}>{item}</li>)}
                </ul>
              )}
            </ResultSection>
          )}

          {questions && (
            <ResultSection title="Discovery Questions">
              <ul className="citation-list">
                {(questions.questions || []).map((q) => <li key={q}>{q}</li>)}
              </ul>
            </ResultSection>
          )}

          {risk && (
            <ResultSection title={`Deal Risk${risk.risk_level ? ` — ${risk.risk_level}` : ''}`}>
              {risk.risks?.length > 0 && (
                <ul className="citation-list">
                  {risk.risks.map((r, i) => (
                    <li key={i}><strong>{r.signal}</strong>{r.mitigation ? ` — ${r.mitigation}` : ''}</li>
                  ))}
                </ul>
              )}
              {risk.agreed_next_steps?.length > 0 && (
                <>
                  <div className="citation-label" style={{ margin: '0.5rem 0 0.3rem' }}>Agreed Next Steps</div>
                  <ul className="citation-list">
                    {risk.agreed_next_steps.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </>
              )}
              {risk.open_items?.length > 0 && (
                <>
                  <div className="citation-label" style={{ margin: '0.5rem 0 0.3rem' }}>Open Items</div>
                  <ul className="citation-list">
                    {risk.open_items.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </>
              )}
            </ResultSection>
          )}

          {draft && (
            <ResultSection title={`Follow-Up Draft${draft.mode ? ` (${draft.mode})` : ''}`}>
              {draft.subject && <div style={{ fontWeight: 600, marginBottom: '0.3rem', fontSize: '0.85rem' }}>{draft.subject}</div>}
              {draft.reason_blocked ? (
                <div className="error-text" style={{ marginTop: 0 }}>{draft.reason_blocked}</div>
              ) : (
                <pre style={{ marginTop: '0.2rem' }}>{draft.body}</pre>
              )}
            </ResultSection>
          )}

          {talResult && (
            <ResultSection title="Target Account List">
              {talResult.accounts?.length > 0 ? (
                <ul className="citation-list">
                  {talResult.accounts.map((a, i) => (
                    <li key={i}>
                      <strong>{a.name || a.company}</strong>
                      {a.reason ? ` — ${a.reason}` : ''}
                    </li>
                  ))}
                </ul>
              ) : (
                <pre style={{ fontSize: '0.78rem' }}>{JSON.stringify(talResult, null, 2)}</pre>
              )}
            </ResultSection>
          )}

          <FeedbackButtons
            mode="rep"
            queryText={account}
            originalResponse={JSON.stringify(fullSolution || brief || questions || risk || draft || talResult)}
          />
        </div>
      )}
    </div>
  );
}
