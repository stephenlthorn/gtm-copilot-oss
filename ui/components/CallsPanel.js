'use client';

import { useState, useEffect } from 'react';

export default function CallsPanel() {
  const [config, setConfig] = useState(null);
  const [secSettings, setSecSettings] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState('');
  const [fullSyncDate, setFullSyncDate] = useState('2023-01-01');
  const [showFullSync, setShowFullSync] = useState(false);

  useEffect(() => {
    fetch('/api/admin/kb-config')
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setConfig(data); })
      .catch(() => {});

    fetch('/api/admin/security-settings')
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setSecSettings(data); })
      .catch(() => {});
  }, []);

  const toggleChorus = async (enabled) => {
    const next = { ...config, chorus_enabled: enabled };
    setConfig(next);
    try {
      const res = await fetch('/api/admin/kb-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chorus_enabled: enabled }),
      });
      if (!res.ok) throw new Error();
      const updated = await res.json();
      setConfig(updated);
    } catch {
      setConfig(config);
      setMessage('✗ Failed to update');
    }
  };

  const syncCalls = async (since = null) => {
    setSyncing(true);
    setMessage('');
    try {
      const url = since ? `/api/admin/sync/calls?since=${since}` : '/api/admin/sync/calls';
      const res = await fetch(url, { method: 'POST' });
      const text = await res.text();
      const data = text ? JSON.parse(text) : {};
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      const indexed = Number(data?.calls_seen || data?.added || data?.processed || 0);
      const skipped = Number(data?.skipped || 0);
      setMessage(`✓ Sync complete · ${indexed} calls fetched${skipped ? `, ${skipped} skipped` : ''}`);
      setShowFullSync(false);
    } catch (err) {
      setMessage(`✗ ${err.message || 'Sync failed'}`);
    } finally {
      setSyncing(false);
    }
  };

  const apiConfigured = secSettings?.call_api_configured ?? secSettings?.chorus_api_configured ?? null;

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Call Transcripts (Chorus)</span>
        {apiConfigured === true && <span className="tag tag-green">API configured</span>}
        {apiConfigured === false && <span className="tag">No API key</span>}
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-2)' }}>
          Syncs call transcripts from Chorus into the knowledge base.
          Set <code style={{ fontSize: '0.74rem' }}>CALL_API_KEY</code> and{' '}
          <code style={{ fontSize: '0.74rem' }}>CALL_BASE_URL</code> in the backend <code style={{ fontSize: '0.74rem' }}>.env</code>.
        </p>

        {secSettings && (
          <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '0.3rem 0.75rem', fontSize: '0.78rem' }}>
            <span style={{ color: 'var(--text-3)' }}>API key</span>
            <span>{apiConfigured ? '••••••••' : <span style={{ color: 'var(--text-3)' }}>not set</span>}</span>
            {secSettings.call_base_url && (
              <>
                <span style={{ color: 'var(--text-3)' }}>Base URL</span>
                <span style={{ fontFamily: 'monospace', fontSize: '0.74rem' }}>{secSettings.call_base_url}</span>
              </>
            )}
          </div>
        )}

        {config !== null && (
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={!!config?.chorus_enabled}
              onChange={e => toggleChorus(e.target.checked)}
            />
            Use call transcripts as a knowledge source
          </label>
        )}

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn btn-primary"
            onClick={() => syncCalls()}
            disabled={syncing || !config?.chorus_enabled}
          >
            {syncing ? 'Syncing…' : 'Sync New Calls'}
          </button>
          <button
            className="btn"
            onClick={() => setShowFullSync(v => !v)}
            disabled={syncing || !config?.chorus_enabled}
            style={{ fontSize: '0.78rem' }}
          >
            Full Sync…
          </button>
        </div>

        {showFullSync && (
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', padding: '0.6rem', background: 'var(--bg-soft)', borderRadius: '6px', fontSize: '0.8rem' }}>
            <span style={{ color: 'var(--text-2)' }}>Fetch all calls from:</span>
            <input
              type="date"
              className="input"
              value={fullSyncDate}
              onChange={e => setFullSyncDate(e.target.value)}
              style={{ width: '150px', fontSize: '0.8rem', padding: '0.2rem 0.4rem' }}
            />
            <button className="btn btn-primary" onClick={() => syncCalls(fullSyncDate)} disabled={syncing}>
              {syncing ? 'Syncing…' : 'Run Full Sync'}
            </button>
          </div>
        )}

        {message && (
          <span style={{ fontSize: '0.78rem', color: message.startsWith('✓') ? 'var(--accent)' : '#ef4444' }}>
            {message}
          </span>
        )}
      </div>
    </div>
  );
}
