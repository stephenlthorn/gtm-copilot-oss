'use client';

import { useState, useEffect } from 'react';

const PERIODS = ['daily', 'weekly', 'monthly'];

function fmt(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function fmtCost(n) {
  if (n == null) return '—';
  return `$${Number(n).toFixed(4)}`;
}

export default function IndexHealthPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('daily');

  useEffect(() => {
    fetch('/api/dashboard/api-usage')
      .then(r => r.json())
      .then(d => setData(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const rows = data?.[period] || data?.usage || [];
  const sources = Array.isArray(rows) ? rows : Object.entries(rows).map(([source, v]) => ({ source, ...v }));

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Index Health / API Usage</span>
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          {PERIODS.map(p => (
            <button
              key={p}
              className={`btn ${period === p ? 'btn-primary' : ''}`}
              style={{ fontSize: '0.72rem', padding: '0.2rem 0.55rem' }}
              onClick={() => setPeriod(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      <div className="panel-body">
        {loading ? (
          <div className="status-row">Loading…</div>
        ) : sources.length === 0 ? (
          <div className="status-row">No usage data available.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>API Source</th>
                <th>Tokens / Requests</th>
                <th>Cost</th>
                <th>Calls</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((row, i) => (
                <tr key={row.source || i}>
                  <td className="row-title">{row.source || '—'}</td>
                  <td style={{ color: 'var(--text-2)' }}>{fmt(row.tokens ?? row.requests)}</td>
                  <td style={{ color: 'var(--text-2)' }}>{fmtCost(row.cost)}</td>
                  <td style={{ color: 'var(--text-2)' }}>{fmt(row.calls ?? row.count)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
