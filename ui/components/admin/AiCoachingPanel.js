'use client';

import { useState, useEffect } from 'react';

function scopeTag(scope) {
  return scope === 'team' ? 'tag-green' : '';
}

export default function AiCoachingPanel() {
  const [refinements, setRefinements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState({});
  const [messages, setMessages] = useState({});

  const load = async () => {
    try {
      const res = await fetch('/api/admin/refinements');
      if (!res.ok) throw new Error('Failed');
      const data = await res.json();
      setRefinements(Array.isArray(data) ? data : data.refinements || []);
    } catch {
      // leave empty
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const promote = async (id) => {
    setActing(prev => ({ ...prev, [id]: 'promoting' }));
    setMessages(prev => ({ ...prev, [id]: '' }));
    try {
      const res = await fetch(`/api/admin/refinements/${id}/promote`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed');
      setMessages(prev => ({ ...prev, [id]: 'Promoted' }));
      await load();
    } catch {
      setMessages(prev => ({ ...prev, [id]: 'Failed' }));
    } finally {
      setActing(prev => ({ ...prev, [id]: null }));
    }
  };

  const disable = async (id) => {
    setActing(prev => ({ ...prev, [id]: 'disabling' }));
    setMessages(prev => ({ ...prev, [id]: '' }));
    try {
      const res = await fetch(`/api/admin/refinements/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed');
      setMessages(prev => ({ ...prev, [id]: 'Disabled' }));
      await load();
    } catch {
      setMessages(prev => ({ ...prev, [id]: 'Failed' }));
    } finally {
      setActing(prev => ({ ...prev, [id]: null }));
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">AI Coaching Management</span>
        <span className="tag">{refinements.length} refinements</span>
      </div>
      <div className="panel-body">
        {loading ? (
          <div className="status-row">Loading…</div>
        ) : refinements.length === 0 ? (
          <div className="status-row">No refinements found.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Type</th>
                <th>Feedback</th>
                <th>Scope</th>
                <th>Active</th>
                <th>Effectiveness</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {refinements.map(r => (
                <tr key={r.id}>
                  <td className="row-title" style={{ fontSize: '0.75rem' }}>{r.user_email || r.user || '—'}</td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-2)' }}>{r.output_type || '—'}</td>
                  <td style={{ fontSize: '0.72rem', color: 'var(--text-3)', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {r.feedback_text || '—'}
                  </td>
                  <td><span className={`tag ${scopeTag(r.scope)}`}>{r.scope || 'personal'}</span></td>
                  <td>
                    <span className={`tag ${r.active ? 'tag-green' : 'tag-red'}`}>
                      {r.active ? 'yes' : 'no'}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-2)', fontSize: '0.75rem' }}>
                    {r.effectiveness != null ? Number(r.effectiveness).toFixed(2) : '—'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                      {r.scope !== 'team' && (
                        <button
                          className="btn"
                          style={{ fontSize: '0.72rem', padding: '0.2rem 0.55rem' }}
                          onClick={() => promote(r.id)}
                          disabled={!!acting[r.id]}
                        >
                          {acting[r.id] === 'promoting' ? '…' : 'Promote'}
                        </button>
                      )}
                      <button
                        className="btn btn-danger"
                        style={{ fontSize: '0.72rem', padding: '0.2rem 0.55rem' }}
                        onClick={() => disable(r.id)}
                        disabled={!!acting[r.id]}
                      >
                        {acting[r.id] === 'disabling' ? '…' : 'Disable'}
                      </button>
                      {messages[r.id] && (
                        <span style={{ fontSize: '0.72rem', color: messages[r.id] === 'Failed' ? 'var(--danger)' : 'var(--success)' }}>
                          {messages[r.id]}
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
