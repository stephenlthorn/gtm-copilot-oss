import { apiGet } from '../../../lib/api';
import Link from 'next/link';

export default async function AccountsPage({ searchParams }) {
  const account = searchParams?.account;
  let memory = null;
  let calls = [];

  if (account) {
    [memory, calls] = await Promise.all([
      apiGet(`/accounts/${encodeURIComponent(account)}/memory`).catch(() => null),
      apiGet(`/calls?account=${encodeURIComponent(account)}&limit=50`).catch(() => []),
    ]);
  }

  const MEDDPICC_LABELS = {
    metrics: 'Metrics', economic_buyer: 'Economic Buyer', decision_criteria: 'Decision Criteria',
    decision_process: 'Decision Process', identify_pain: 'Identify Pain', champion: 'Champion', competition: 'Competition',
  };
  const scoreColor = s => s >= 4 ? 'var(--success)' : s >= 2 ? '#f59e0b' : 'var(--text-3)';

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar-title">Account Memory</div>
          <div className="topbar-meta">Rolling MEDDPICC state across all calls</div>
        </div>
        <Link href="/chat" style={{ fontSize: '0.78rem', color: 'var(--text-2)', padding: '0.3rem 0.6rem', borderRadius: '4px', textDecoration: 'none', border: '1px solid var(--border)' }}>← Back to Chat</Link>
      </div>

      <div className="content">
        <form method="GET" style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
          <input name="account" defaultValue={account || ''} placeholder="Search account name…" className="input" style={{ flex: 1 }} />
          <button type="submit" className="btn btn-primary">Load</button>
        </form>

        {memory && (
          <>
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">{memory.account}</span>
                <span className={`tag ${memory.status === 'active' ? 'tag-green' : ''}`}>{memory.status}</span>
                <span className="tag">{memory.is_new_business ? 'New Business' : 'Existing'}</span>
                {memory.deal_stage && <span className="tag">{memory.deal_stage}</span>}
              </div>
              <div className="panel-body">
                {memory.summary && <p style={{ margin: '0 0 1rem', fontSize: '0.82rem', color: 'var(--text-2)', lineHeight: 1.6 }}>{memory.summary}</p>}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.5rem' }}>
                  {Object.entries(MEDDPICC_LABELS).map(([key, label]) => {
                    const el = memory.meddpicc?.[key];
                    const score = el?.score || 0;
                    return (
                      <div key={key} style={{ padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--bg-2)' }}>
                        <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-3)', marginBottom: '0.2rem' }}>{label}</div>
                        <div style={{ fontSize: '1rem', fontWeight: 700, color: scoreColor(score) }}>{score}/5</div>
                        {el?.evidence && <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginTop: '0.2rem', lineHeight: 1.4 }}>{el.evidence.slice(0, 80)}</div>}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginTop: '0.75rem' }}>
              <div className="panel">
                <div className="panel-header"><span className="panel-title">Key Contacts</span></div>
                <div className="panel-body">
                  {(memory.key_contacts || []).length === 0 && <span style={{ color: 'var(--text-3)', fontSize: '0.78rem' }}>None recorded yet</span>}
                  {(memory.key_contacts || []).map((c, i) => (
                    <div key={i} style={{ fontSize: '0.8rem', borderBottom: '1px solid var(--border)', padding: '0.4rem 0' }}>
                      <strong>{c.name}</strong> — {c.title} <span className="tag" style={{ fontSize: '0.68rem' }}>{c.role}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="panel">
                <div className="panel-header"><span className="panel-title">Open Items</span></div>
                <div className="panel-body">
                  {(memory.open_items || []).length === 0 && <span style={{ color: 'var(--text-3)', fontSize: '0.78rem' }}>None recorded yet</span>}
                  {(memory.open_items || []).map((item, i) => (
                    <div key={i} style={{ fontSize: '0.78rem', borderBottom: '1px solid var(--border)', padding: '0.4rem 0' }}>
                      {item.item} <span style={{ color: 'var(--text-3)' }}>— {item.owner} · {item.due_date || 'no date'}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="panel" style={{ marginTop: '0.75rem' }}>
              <div className="panel-header"><span className="panel-title">Call History ({calls.length})</span></div>
              <table className="data-table">
                <thead><tr><th>Date</th><th>Stage</th><th>Rep</th><th>Source</th></tr></thead>
                <tbody>
                  {calls.map(c => (
                    <tr key={c.chorus_call_id || c.id}>
                      <td>{c.date}</td>
                      <td>{c.stage || '—'}</td>
                      <td style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>{c.rep_email}</td>
                      <td><span className="tag">{c.source_type || 'chorus'}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  );
}
