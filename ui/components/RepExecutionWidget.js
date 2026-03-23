'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

// ── Helpers ──────────────────────────────────────────────────────────────────

function Field({ label, children }) {
  return (
    <div style={{ display: 'grid', gap: '0.35rem' }}>
      <label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>{label}</label>
      {children}
    </div>
  );
}

function PhaseBlock({ number, title, children }) {
  return (
    <div className="rep-phase">
      <div className="rep-phase-header">
        <span className="rep-phase-num">{number}</span>
        <span className="rep-phase-title">{title}</span>
      </div>
      <div className="rep-phase-body">{children}</div>
    </div>
  );
}

// ── Call Selector ─────────────────────────────────────────────────────────────

const SYNC_MS = 60 * 60 * 1000;

function CallSelector({ account, selectedIds, onChange }) {
  const [allCalls, setAllCalls] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [sortDir, setSortDir] = useState('desc');
  const timer = useRef(null);

  const fetchCalls = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/calls?limit=200');
      const data = await res.json();
      setAllCalls(Array.isArray(data) ? data : []);
      setLastSync(new Date());
    } catch { setAllCalls([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchCalls();
    timer.current = setInterval(fetchCalls, SYNC_MS);
    return () => clearInterval(timer.current);
  }, [fetchCalls]);

  const toggleSort = (field) => {
    if (sortBy === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(field); setSortDir(field === 'date' ? 'desc' : 'asc'); }
  };

  const filterTerm = search.trim() || account?.trim() || '';
  const filtered = filterTerm
    ? allCalls.filter(c =>
        (c.account || '').toLowerCase().includes(filterTerm.toLowerCase()) ||
        (c.opportunity || '').toLowerCase().includes(filterTerm.toLowerCase()))
    : allCalls;

  const calls = [...filtered].sort((a, b) => {
    const av = sortBy === 'date' ? (a.date || '') : (a.account || '').toLowerCase();
    const bv = sortBy === 'date' ? (b.date || '') : (b.account || '').toLowerCase();
    return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
  });

  const toggle = id => onChange(selectedIds.includes(id) ? selectedIds.filter(x => x !== id) : [...selectedIds, id]);

  const SortBtn = ({ field, label }) => (
    <button
      className={`rep-sort-btn${sortBy === field ? ' rep-sort-btn--active' : ''}`}
      onClick={() => toggleSort(field)}
    >
      {label}{sortBy === field ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
    </button>
  );

  return (
    <div style={{ display: 'grid', gap: '0.4rem' }}>
      <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
        <input
          className="input"
          style={{ flex: 1, fontSize: '0.78rem', padding: '0.3rem 0.5rem' }}
          placeholder={account?.trim() ? `"${account}" — type to override` : 'Search account or opportunity…'}
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <SortBtn field="date" label="Date" />
        <SortBtn field="company" label="Co." />
        <button className="rep-sort-btn" onClick={fetchCalls} disabled={loading}>{loading ? '…' : '↻'}</button>
      </div>
      <div style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>
        {calls.length}/{allCalls.length} calls
        {lastSync && ` · ${lastSync.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
        {selectedIds.length > 0 && ` · ${selectedIds.length} selected`}
      </div>
      {loading && allCalls.length === 0 ? (
        <div style={{ fontSize: '0.78rem', color: 'var(--text-3)', padding: '0.5rem 0' }}>Loading…</div>
      ) : (
        <div className="call-list">
          {calls.length === 0 && <div style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>No calls found.</div>}
          {calls.map(c => {
            const id = c.chorus_call_id;
            const checked = selectedIds.includes(id);
            return (
              <label key={id} className={`call-item${checked ? ' call-item--selected' : ''}`}>
                <input type="checkbox" checked={checked} onChange={() => toggle(id)} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: checked ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {c.account || 'Unknown'}{c.opportunity ? ` — ${c.opportunity}` : ''}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>
                    {c.date ? new Date(c.date).toLocaleDateString() : '—'}
                    {c.stage ? ` · ${c.stage}` : ''}
                    {c.rep_email ? ` · ${c.rep_email}` : ''}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Chat message renderers ────────────────────────────────────────────────────

function BriefMsg({ data }) {
  return (
    <div className="chat-result">
      {data.summary && <p style={{ marginBottom: '0.5rem' }}>{data.summary}</p>}
      {data.next_meeting_agenda?.length > 0 && (
        <>
          <div className="chat-result-label">Meeting Agenda</div>
          <ul className="chat-result-list">{data.next_meeting_agenda.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </>
      )}
    </div>
  );
}

function QuestionsMsg({ data }) {
  return (
    <div className="chat-result">
      <ul className="chat-result-list">{(data.questions || []).map((q, i) => <li key={i}>{q}</li>)}</ul>
    </div>
  );
}

function RiskMsg({ data }) {
  return (
    <div className="chat-result">
      {data.risk_level && <div className="chat-result-label" style={{ marginBottom: '0.4rem' }}>Risk Level: {data.risk_level}</div>}
      {data.risks?.length > 0 && (
        <ul className="chat-result-list">
          {data.risks.map((r, i) => <li key={i}><strong>{r.signal}</strong>{r.mitigation ? ` — ${r.mitigation}` : ''}</li>)}
        </ul>
      )}
      {data.agreed_next_steps?.length > 0 && (
        <>
          <div className="chat-result-label" style={{ marginTop: '0.6rem', marginBottom: '0.3rem' }}>Agreed Next Steps</div>
          <ul className="chat-result-list">{data.agreed_next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul>
        </>
      )}
      {data.open_items?.length > 0 && (
        <>
          <div className="chat-result-label" style={{ marginTop: '0.6rem', marginBottom: '0.3rem' }}>Open Items</div>
          <ul className="chat-result-list">{data.open_items.map((s, i) => <li key={i}>{s}</li>)}</ul>
        </>
      )}
    </div>
  );
}

function DraftMsg({ data }) {
  return (
    <div className="chat-result">
      {data.subject && <div style={{ fontWeight: 600, marginBottom: '0.35rem' }}>{data.subject}</div>}
      {data.reason_blocked
        ? <div style={{ color: 'var(--danger)', fontSize: '0.8rem' }}>{data.reason_blocked}</div>
        : <pre style={{ margin: 0, fontSize: '0.78rem' }}>{data.body}</pre>}
    </div>
  );
}

function TalMsg({ data }) {
  if (!data.accounts?.length) return <pre style={{ fontSize: '0.75rem' }}>{JSON.stringify(data, null, 2)}</pre>;
  return (
    <div className="chat-result">
      <ul className="chat-result-list">
        {data.accounts.map((a, i) => <li key={i}><strong>{a.name || a.company}</strong>{a.reason ? ` — ${a.reason}` : ''}</li>)}
      </ul>
    </div>
  );
}

function FullSolutionMsg({ data }) {
  return (
    <div className="chat-result">
      {data.phase_2_execution_focus?.length > 0 && (
        <>
          <div className="chat-result-label" style={{ marginBottom: '0.3rem' }}>Execution Focus</div>
          <ul className="chat-result-list">{data.phase_2_execution_focus.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </>
      )}
      {data.phase_3_automation_next_steps?.length > 0 && (
        <>
          <div className="chat-result-label" style={{ margin: '0.6rem 0 0.3rem' }}>Next Steps</div>
          <ul className="chat-result-list">{data.phase_3_automation_next_steps.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </>
      )}
    </div>
  );
}

function PocPlanMsg({ data }) {
  return (
    <div className="chat-result">
      <div className="chat-result-label" style={{ marginBottom: '0.3rem' }}>
        {data.status} · Readiness {data.readiness_score}/100
      </div>
      {data.readiness_summary && <p style={{ marginBottom: '0.4rem' }}>{data.readiness_summary}</p>}
      {data.poc_kit_url && (
        <div style={{ fontSize: '0.75rem' }}>
          POC kit: <a href={data.poc_kit_url} target="_blank" rel="noreferrer">{data.poc_kit_url}</a>
        </div>
      )}
    </div>
  );
}

function ReadinessMsg({ data }) {
  return (
    <div className="chat-result">
      {data.readiness_summary && <p>{data.readiness_summary}</p>}
    </div>
  );
}

function ArchitectureMsg({ data }) {
  return (
    <div className="chat-result">
      {data.fit_summary && <p>{data.fit_summary}</p>}
    </div>
  );
}

function CoachMsg({ data }) {
  return (
    <div className="chat-result">
      {data.positioning?.length > 0 && (
        <ul className="chat-result-list">
          {data.positioning.slice(0, 5).map((x, i) => <li key={i}>{x}</li>)}
        </ul>
      )}
    </div>
  );
}

function SEFullMsg({ data }) {
  return (
    <div className="chat-result">
      {data.phase_2_validation_matrix?.length > 0 && (
        <>
          <div className="chat-result-label" style={{ marginBottom: '0.3rem' }}>Validation Matrix</div>
          <ul className="chat-result-list">
            {data.phase_2_validation_matrix.map((item, i) => (
              <li key={i}>{item.check}: {item.target} ({item.owner})</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

const ACTION_LABELS = {
  brief: 'Account Brief',
  questions: 'Discovery Questions',
  risk: 'Deal Risk Analysis',
  draft: 'Follow-Up Draft',
  tal: 'Target Account List',
  full: 'Full Solution (Phases 1–3)',
  'se-poc-plan': 'POC Plan',
  'se-poc-readiness': 'POC Readiness',
  'se-architecture-fit': 'Architecture Fit',
  'se-competitor-coach': 'Competitor Coach',
  'se-full': 'SE Full Solution',
};

function ChatMessage({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="rep-chat-msg rep-chat-msg--user">
        <span>{msg.text}</span>
      </div>
    );
  }
  if (msg.role === 'loading') {
    return (
      <div className="rep-chat-msg rep-chat-msg--assistant">
        <div className="oracle-thinking-dots"><span /><span /><span /></div>
      </div>
    );
  }
  if (msg.role === 'error') {
    return <div className="rep-chat-msg rep-chat-msg--error">{msg.text}</div>;
  }

  const ResultComponent = {
    brief: BriefMsg,
    questions: QuestionsMsg,
    risk: RiskMsg,
    draft: DraftMsg,
    tal: TalMsg,
    full: FullSolutionMsg,
    'se-poc-plan': PocPlanMsg,
    'se-poc-readiness': ReadinessMsg,
    'se-architecture-fit': ArchitectureMsg,
    'se-competitor-coach': CoachMsg,
    'se-full': SEFullMsg,
  }[msg.action];

  return (
    <div className="rep-chat-msg rep-chat-msg--assistant">
      <div className="rep-chat-msg-label">{ACTION_LABELS[msg.action] || msg.action}</div>
      {ResultComponent ? <ResultComponent data={msg.data} /> : <pre style={{ fontSize: '0.75rem' }}>{JSON.stringify(msg.data, null, 2)}</pre>}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function RepExecutionWidget() {
  // Phase 1
  const [account, setAccount] = useState('');
  const [website, setWebsite] = useState('');
  // Phase 2
  const [prospectName, setProspectName] = useState('');
  const [prospectLinkedin, setProspectLinkedin] = useState('');
  // Phase 3
  const [regions, setRegions] = useState('');
  const [industry, setIndustry] = useState('');
  const [revenueMin, setRevenueMin] = useState('');
  const [revenueMax, setRevenueMax] = useState('');
  const [talContext, setTalContext] = useState('');
  const [talCount, setTalCount] = useState(25);
  // SE inputs
  const [targetOffering, setTargetOffering] = useState('Managed Distributed SQL');
  const [competitor, setCompetitor] = useState('');
  // Call context
  const [selectedCallIds, setSelectedCallIds] = useState([]);
  const [emailTo, setEmailTo] = useState('');
  const [emailCc, setEmailCc] = useState('');
  const [emailTone, setEmailTone] = useState('crisp');
  // Chat
  const [messages, setMessages] = useState([]);
  const [freeInput, setFreeInput] = useState('');
  const [loadingAction, setLoadingAction] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addMsg = (msg) => setMessages(prev => [...prev, { ...msg, id: Date.now() + Math.random() }]);
  const replaceLoading = (msg) => setMessages(prev => prev[prev.length - 1]?.role === 'loading' ? [...prev.slice(0, -1), { ...msg, id: Date.now() + Math.random() }] : [...prev, { ...msg, id: Date.now() + Math.random() }]);

  const run = async (action, label) => {
    if (!account.trim()) { addMsg({ role: 'error', text: 'Enter an account name in Phase 1 first.' }); return; }
    addMsg({ role: 'user', text: label || ACTION_LABELS[action] });
    addMsg({ role: 'loading' });
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

      const seBase = { account: account.trim(), chorus_call_id: selectedCallIds[0] || null };
      const routes = {
        brief: ['/api/rep/account-brief', base],
        questions: ['/api/rep/discovery-questions', { ...base, count: 6 }],
        full: ['/api/rep/full-solution', { ...base, count: 6, tone: emailTone }],
        risk: ['/api/rep/deal-risk', base],
        draft: ['/api/rep/follow-up-draft', {
          ...base,
          to: emailTo.split(',').map(s => s.trim()).filter(Boolean),
          cc: emailCc.split(',').map(s => s.trim()).filter(Boolean),
          tone: emailTone,
          mode: 'draft',
        }],
        tal: ['/api/rep/market-research', {
          account: account.trim(),
          regions: regions.split(',').map(s => s.trim()).filter(Boolean),
          industry: industry.trim() || null,
          revenue_min: revenueMin ? Number(revenueMin) : null,
          revenue_max: revenueMax ? Number(revenueMax) : null,
          context: talContext.trim() || null,
          top_n: Number(talCount) || 25,
        }],
        'se-poc-plan': ['/api/se/poc-plan', { ...seBase, target_offering: targetOffering }],
        'se-poc-readiness': ['/api/se/poc-readiness', seBase],
        'se-architecture-fit': ['/api/se/architecture-fit', seBase],
        'se-competitor-coach': ['/api/se/competitor-coach', { ...seBase, competitor: competitor || 'Unknown' }],
        'se-full': ['/api/se/full-solution', { ...seBase, target_offering: targetOffering, competitor: competitor || 'Unknown' }],
      };

      const [path, payload] = routes[action];
      const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || data?.error || 'Request failed');

      replaceLoading({ role: 'assistant', action, data });

      // Also unpack full solution sub-items
      if (action === 'full') {
        if (data.account_brief) addMsg({ role: 'assistant', action: 'brief', data: data.account_brief });
        if (data.discovery_questions) addMsg({ role: 'assistant', action: 'questions', data: data.discovery_questions });
      }
    } catch (err) {
      replaceLoading({ role: 'error', text: String(err?.message || err) });
    } finally {
      setLoadingAction('');
    }
  };

  const sendFree = async () => {
    const q = freeInput.trim();
    if (!q || loadingAction) return;
    setFreeInput('');
    addMsg({ role: 'user', text: q });
    addMsg({ role: 'loading' });
    setLoadingAction('oracle');
    try {
      const res = await fetch('/api/oracle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'oracle', message: q, top_k: 8 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || 'Request failed');
      replaceLoading({ role: 'assistant', action: 'oracle', data: { answer: data.answer, citations: data.citations } });
    } catch (err) {
      replaceLoading({ role: 'error', text: String(err?.message || err) });
    } finally {
      setLoadingAction('');
    }
  };

  const busy = Boolean(loadingAction);
  const hasCallSelected = selectedCallIds.length > 0;

  return (
    <div className="rep-split">

      {/* ── LEFT: input panel ── */}
      <div className="rep-inputs">
        <div className="rep-inputs-scroll">

          <PhaseBlock number="1" title="Research Company">
            <Field label="Account Name">
              <input className="input" value={account} onChange={e => setAccount(e.target.value)} placeholder="e.g. Acme Corp" />
            </Field>
            <Field label="Website">
              <input className="input" value={website} onChange={e => setWebsite(e.target.value)} placeholder="acmecorp.com" />
            </Field>
          </PhaseBlock>

          <PhaseBlock number="2" title="Research Prospect">
            <Field label="Prospect Name">
              <input className="input" value={prospectName} onChange={e => setProspectName(e.target.value)} placeholder="Jane Smith" />
            </Field>
            <Field label="LinkedIn URL">
              <input className="input" value={prospectLinkedin} onChange={e => setProspectLinkedin(e.target.value)} placeholder="linkedin.com/in/…" />
            </Field>
          </PhaseBlock>

          <PhaseBlock number="3" title="Market Research / TAL">
            <Field label="Regions / Territory">
              <input className="input" value={regions} onChange={e => setRegions(e.target.value)} placeholder="US West, APAC" />
            </Field>
            <Field label="Industry Vertical">
              <input className="input" value={industry} onChange={e => setIndustry(e.target.value)} placeholder="FinTech, SaaS…" />
            </Field>
            <Field label="Revenue Min ($M)">
              <input className="input" type="number" value={revenueMin} onChange={e => setRevenueMin(e.target.value)} placeholder="50" />
            </Field>
            <Field label="Revenue Max ($M)">
              <input className="input" type="number" value={revenueMax} onChange={e => setRevenueMax(e.target.value)} placeholder="500" />
            </Field>
            <Field label="Additional Context">
              <textarea className="input" rows={2} value={talContext} onChange={e => setTalContext(e.target.value)} placeholder="Companies using MySQL at scale…" style={{ minHeight: '56px' }} />
            </Field>
            <Field label="Top N Accounts">
              <input className="input" type="number" min={5} max={100} value={talCount} onChange={e => setTalCount(e.target.value)} />
            </Field>
          </PhaseBlock>

          {/* Rep generate buttons */}
          <div className="rep-action-group">
            <div className="rep-action-label">Sales Rep</div>
            <button className="btn btn-primary" onClick={() => run('full')} disabled={busy}>
              {loadingAction === 'full' ? 'Generating…' : '⚡ Full Solution (1–3)'}
            </button>
            <button className="btn" onClick={() => run('brief')} disabled={busy}>Account Brief</button>
            <button className="btn" onClick={() => run('questions')} disabled={busy}>Discovery Questions</button>
            <button className="btn" onClick={() => run('tal')} disabled={busy}>Target Account List</button>
          </div>

          {/* SE section */}
          <PhaseBlock number="⬡" title="Sales Engineer">
            <Field label="Target Offering">
              <select className="input" value={targetOffering} onChange={e => setTargetOffering(e.target.value)}>
                <option>Managed Distributed SQL</option>
                <option>Self-Managed Distributed SQL</option>
                <option>Enterprise Cluster Edition</option>
              </select>
            </Field>
            <Field label="Competitor">
              <input className="input" value={competitor} onChange={e => setCompetitor(e.target.value)} placeholder="e.g. CockroachDB, Aurora" />
            </Field>
            <div className="rep-action-group" style={{ paddingTop: 0 }}>
              <button className="btn btn-primary" onClick={() => run('se-full')} disabled={busy}>
                {loadingAction === 'se-full' ? 'Generating…' : '⚡ SE Full Solution'}
              </button>
              <button className="btn" onClick={() => run('se-poc-plan')} disabled={busy}>POC Plan</button>
              <button className="btn" onClick={() => run('se-poc-readiness')} disabled={busy}>Readiness</button>
              <button className="btn" onClick={() => run('se-architecture-fit')} disabled={busy}>Architecture Fit</button>
              <button className="btn" onClick={() => run('se-competitor-coach')} disabled={busy}>Competitor Coach</button>
            </div>
          </PhaseBlock>

          {/* Call context */}
          <PhaseBlock number="📞" title="Call Context">
            <CallSelector account={account} selectedIds={selectedCallIds} onChange={setSelectedCallIds} />
            {hasCallSelected && (
              <>
                <Field label="To">
                  <input className="input" value={emailTo} onChange={e => setEmailTo(e.target.value)} placeholder="rep@company.com" />
                </Field>
                <Field label="CC">
                  <input className="input" value={emailCc} onChange={e => setEmailCc(e.target.value)} placeholder="se@company.com" />
                </Field>
                <Field label="Email Tone">
                  <select className="input" value={emailTone} onChange={e => setEmailTone(e.target.value)}>
                    <option value="crisp">Crisp</option>
                    <option value="executive">Executive</option>
                    <option value="technical">Technical</option>
                  </select>
                </Field>
              </>
            )}
            <div className="rep-action-group" style={{ paddingTop: 0 }}>
              <button className="btn btn-primary" onClick={() => run('risk')} disabled={busy || !hasCallSelected}>Deal Risk</button>
              <button className="btn" onClick={() => run('draft')} disabled={busy || !hasCallSelected}>Follow-Up Draft</button>
              {!hasCallSelected && <span style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>Select a call to enable</span>}
            </div>
          </PhaseBlock>

        </div>
      </div>

      {/* ── RIGHT: chat panel ── */}
      <div className="rep-chat">
        <div className="rep-chat-messages">
          {messages.length === 0 && (
            <div className="rep-chat-empty">
              <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>◎</div>
              Fill in the phases and click Generate, or ask a follow-up question below.
            </div>
          )}
          {messages.map(msg => <ChatMessage key={msg.id} msg={msg} />)}
          <div ref={messagesEndRef} />
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

        <div className="rep-chat-input-row">
          <textarea
            className="rep-chat-input"
            rows={2}
            value={freeInput}
            onChange={e => setFreeInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendFree(); }}}
            placeholder="Ask a follow-up question… (Enter to send)"
            disabled={busy}
          />
          <button className="btn btn-primary rep-chat-send" onClick={sendFree} disabled={busy || !freeInput.trim()}>
            {loadingAction === 'oracle' ? '…' : '→'}
          </button>
        </div>
      </div>

    </div>
  );
}
