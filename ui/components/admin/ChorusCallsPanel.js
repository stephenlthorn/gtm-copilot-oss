'use client';

import { useState } from 'react';

function today() {
  return new Date().toISOString().slice(0, 10);
}
function daysAgo(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export default function ChorusCallsPanel() {
  const [since, setSince] = useState(daysAgo(30));
  const [until, setUntil] = useState(today());
  const [calls, setCalls] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState('');

  const search = async () => {
    setLoading(true);
    setMessage('');
    setCalls(null);
    setSelected(new Set());
    try {
      const params = new URLSearchParams();
      if (since) params.set('since', since);
      if (until) params.set('until', until);
      const res = await fetch(`/api/admin/chorus/preview?${params}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || 'Failed to fetch calls');
      setCalls(data);
    } catch (err) {
      setMessage(`✗ ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const toggleAll = () => {
    if (!calls) return;
    if (selected.size === calls.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(calls.map((c) => c.call_id)));
    }
  };

  const toggle = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const syncSelected = async () => {
    if (!selected.size) return;
    setSyncing(true);
    setMessage('');
    try {
      const res = await fetch('/api/admin/chorus/sync-selected', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ call_ids: [...selected] }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || 'Sync failed');
      const errs = data.errors?.length ? ` (${data.errors.length} errors)` : '';
      setMessage(`✓ Synced ${data.synced} calls, ${data.transcripts_indexed} transcripts indexed${errs}`);
      setSelected(new Set());
    } catch (err) {
      setMessage(`✗ ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  const syncAll = async () => {
    setSyncing(true);
    setMessage('');
    try {
      const params = new URLSearchParams();
      if (since) params.set('since', since);
      const res = await fetch(`/api/admin/chorus/sync-all?${params}`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || 'Sync failed');
      const errs = data.errors?.length ? ` (${data.errors.length} errors)` : '';
      setMessage(`✓ Fetched ${data.calls_fetched}, synced ${data.calls_stored}, ${data.transcripts_indexed} transcripts indexed${errs}`);
    } catch (err) {
      setMessage(`✗ ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Chorus Calls</span>
        {calls !== null && (
          <span className="tag">{calls.length} call{calls.length !== 1 ? 's' : ''}</span>
        )}
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>

        {/* Date range row */}
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            From
            <input
              type="date"
              className="input"
              value={since}
              onChange={(e) => setSince(e.target.value)}
              style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem' }}
            />
          </label>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-3)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            To
            <input
              type="date"
              className="input"
              value={until}
              onChange={(e) => setUntil(e.target.value)}
              style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem' }}
            />
          </label>
          <button
            className="btn btn-primary"
            onClick={search}
            disabled={loading}
            style={{ fontSize: '0.8rem', padding: '0.3rem 0.9rem' }}
          >
            {loading ? 'Fetching…' : 'Search'}
          </button>
          <button
            className="btn"
            onClick={syncAll}
            disabled={syncing}
            style={{ fontSize: '0.8rem', padding: '0.3rem 0.9rem', marginLeft: 'auto' }}
          >
            {syncing ? 'Syncing…' : 'Sync All'}
          </button>
          {selected.size > 0 && (
            <button
              className="btn btn-primary"
              onClick={syncSelected}
              disabled={syncing}
              style={{ fontSize: '0.8rem', padding: '0.3rem 0.9rem' }}
            >
              {syncing ? 'Syncing…' : `Sync ${selected.size} selected`}
            </button>
          )}
        </div>

        {message && (
          <p style={{ fontSize: '0.78rem', color: message.startsWith('✓') ? 'var(--success)' : 'var(--danger)', margin: 0 }}>
            {message}
          </p>
        )}

        {/* Call list */}
        {calls !== null && (
          calls.length === 0 ? (
            <p style={{ fontSize: '0.8rem', color: 'var(--text-3)' }}>No calls found in this date range.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '2rem' }}>
                      <input
                        type="checkbox"
                        checked={selected.size === calls.length}
                        onChange={toggleAll}
                      />
                    </th>
                    <th>Date</th>
                    <th>Account</th>
                    <th>Opportunity</th>
                    <th>Stage</th>
                    <th>Rep</th>
                    <th>Transcript</th>
                  </tr>
                </thead>
                <tbody>
                  {calls.map((c) => (
                    <tr key={c.call_id} onClick={() => toggle(c.call_id)} style={{ cursor: 'pointer' }}>
                      <td>
                        <input
                          type="checkbox"
                          checked={selected.has(c.call_id)}
                          onChange={() => toggle(c.call_id)}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </td>
                      <td style={{ fontSize: '0.75rem' }}>{c.date?.slice(0, 10)}</td>
                      <td className="row-title">{c.account}</td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>{c.opportunity || '—'}</td>
                      <td>
                        {c.stage && <span className="tag">{c.stage}</span>}
                      </td>
                      <td style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>{c.rep_email || '—'}</td>
                      <td>
                        <span className={`tag ${c.has_transcript ? 'tag-green' : ''}`}>
                          {c.has_transcript ? 'Yes' : 'No'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>
    </div>
  );
}
