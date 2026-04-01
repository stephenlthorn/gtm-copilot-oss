'use client';

import { useState, useEffect } from 'react';

const SOURCES = ['google_drive', 'chorus', 'tidb_docs', 'tidb_github'];

function statusTagClass(status) {
  if (status === 'ok' || status === 'completed') return 'tag-green';
  if (status === 'error' || status === 'failed') return 'tag-red';
  if (status === 'running' || status === 'syncing') return 'tag-orange';
  return '';
}

function safeDate(val) {
  if (!val) return '—';
  const d = new Date(val);
  if (isNaN(d)) return '—';
  return d.toLocaleString();
}

export default function SyncStatusPanel() {
  const [statuses, setStatuses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState({});
  const [messages, setMessages] = useState({});

  const load = async () => {
    try {
      const res = await fetch('/api/knowledge/sync-status');
      if (!res.ok) throw new Error('Failed');
      const data = await res.json();
      setStatuses(Array.isArray(data) ? data : data.sources || []);
    } catch {
      // show empty state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const syncNow = async (source) => {
    setSyncing(prev => ({ ...prev, [source]: true }));
    setMessages(prev => ({ ...prev, [source]: '' }));
    try {
      const res = await fetch(`/api/knowledge/sync/${source}`, { method: 'POST' });
      if (!res.ok) throw new Error('Sync failed');
      setMessages(prev => ({ ...prev, [source]: 'Sync started' }));
      await load();
    } catch {
      setMessages(prev => ({ ...prev, [source]: 'Failed' }));
    } finally {
      setSyncing(prev => ({ ...prev, [source]: false }));
    }
  };

  const rowMap = {};
  for (const s of statuses) { rowMap[s.source] = s; }

  const rows = SOURCES.map(source => rowMap[source] || { source, status: 'unknown' });

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Sync Status</span>
        <button className="btn" onClick={load}>Refresh</button>
      </div>
      <div className="panel-body">
        {loading ? (
          <div className="status-row">Loading…</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Status</th>
                <th>Docs</th>
                <th>Chunks</th>
                <th>Last Sync</th>
                <th>Error</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.source}>
                  <td className="row-title">{row.source}</td>
                  <td>
                    <span className={`tag ${statusTagClass(row.status)}`}>
                      {row.status || 'unknown'}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-2)' }}>{row.docs_indexed ?? '—'}</td>
                  <td style={{ color: 'var(--text-2)' }}>{row.chunks_indexed ?? '—'}</td>
                  <td style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>{safeDate(row.last_sync_at)}</td>
                  <td style={{ fontSize: '0.72rem', color: 'var(--danger)', maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {row.error || '—'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                      <button
                        className="btn"
                        style={{ fontSize: '0.72rem', padding: '0.25rem 0.6rem' }}
                        onClick={() => syncNow(row.source)}
                        disabled={syncing[row.source]}
                      >
                        {syncing[row.source] ? 'Starting…' : 'Sync Now'}
                      </button>
                      {messages[row.source] && (
                        <span style={{ fontSize: '0.72rem', color: messages[row.source] === 'Sync started' ? 'var(--success)' : 'var(--danger)' }}>
                          {messages[row.source]}
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
