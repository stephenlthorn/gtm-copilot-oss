'use client';

import { useState, useEffect } from 'react';

export default function CallsPanel() {
  const [config, setConfig] = useState(null);
  const [secSettings, setSecSettings] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [message, setMessage] = useState('');

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
      setConfig(config); // revert
      setMessage('✗ Failed to update');
    }
  };

  const syncCalls = async () => {
    setSyncing(true);
    setMessage('');
    try {
      const res = await fetch('/api/admin/sync/calls', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || 'Sync failed');
      const indexed = Number(data?.added || 0) + Number(data?.updated || 0);
      setMessage(`✓ Sync complete · ${indexed} indexed, ${Number(data?.skipped || 0)} skipped`);
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
          Syncs call transcripts from your Chorus (or compatible) API into the knowledge base.
          Set <code style={{ fontSize: '0.74rem' }}>CALL_API_KEY</code> and{' '}
          <code style={{ fontSize: '0.74rem' }}>CALL_BASE_URL</code> in the backend <code style={{ fontSize: '0.74rem' }}>.env</code>.
        </p>

        {config !== null && (
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={!!config?.chorus_enabled}
              onChange={e => toggleChorus(e.target.checked)}
            />
            Enable call transcript source
          </label>
        )}

        {secSettings && (
          <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: '0.3rem 0.75rem', fontSize: '0.78rem' }}>
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

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn btn-primary"
            onClick={syncCalls}
            disabled={syncing || !config?.chorus_enabled}
          >
            {syncing ? 'Syncing…' : 'Sync Calls Now'}
          </button>
          {message && (
            <span style={{ fontSize: '0.78rem', color: message.startsWith('✓') ? 'var(--accent)' : '#ef4444' }}>
              {message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
