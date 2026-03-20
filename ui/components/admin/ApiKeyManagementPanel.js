'use client';

import { useState, useEffect } from 'react';

const API_KEY_FIELDS = [
  { key: 'firecrawl_api_key', label: 'Firecrawl API Key' },
  { key: 'zoominfo_api_key', label: 'ZoomInfo API Key' },
  { key: 'builtwith_api_key', label: 'BuiltWith API Key' },
  { key: 'slack_bot_token', label: 'Slack Bot Token' },
  { key: 'slack_signing_secret', label: 'Slack Signing Secret' },
];

function maskValue(val) {
  if (!val) return '';
  if (val.length <= 4) return '****';
  return '••••••••' + val.slice(-4);
}

export default function ApiKeyManagementPanel() {
  const [config, setConfig] = useState({});
  const [edits, setEdits] = useState({});
  const [saving, setSaving] = useState({});
  const [messages, setMessages] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/admin/system-config')
      .then(r => r.json())
      .then(data => {
        setConfig(data || {});
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const saveKey = async (fieldKey) => {
    const value = edits[fieldKey];
    if (!value) return;
    setSaving(prev => ({ ...prev, [fieldKey]: true }));
    setMessages(prev => ({ ...prev, [fieldKey]: '' }));
    try {
      const res = await fetch('/api/admin/system-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [fieldKey]: value }),
      });
      if (!res.ok) throw new Error('Save failed');
      setConfig(prev => ({ ...prev, [fieldKey]: value }));
      setEdits(prev => ({ ...prev, [fieldKey]: '' }));
      setMessages(prev => ({ ...prev, [fieldKey]: 'Saved' }));
    } catch {
      setMessages(prev => ({ ...prev, [fieldKey]: 'Failed' }));
    } finally {
      setSaving(prev => ({ ...prev, [fieldKey]: false }));
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">API Key Management</span>
      </div>
      <div className="panel-body">
        {loading ? (
          <div className="status-row">Loading…</div>
        ) : (
          <div style={{ display: 'grid', gap: '1rem' }}>
            {API_KEY_FIELDS.map(({ key, label }) => (
              <div key={key} style={{ display: 'grid', gap: '0.35rem' }}>
                <label style={{ fontSize: '0.72rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  {label}
                </label>
                {config[key] && (
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-2)', fontFamily: 'monospace', marginBottom: '0.2rem' }}>
                    Current: <span style={{ color: 'var(--text-3)' }}>{maskValue(config[key])}</span>
                  </div>
                )}
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <input
                    className="input"
                    type="password"
                    placeholder={config[key] ? 'Enter new value to replace…' : 'Enter value…'}
                    value={edits[key] || ''}
                    onChange={e => setEdits(prev => ({ ...prev, [key]: e.target.value }))}
                    style={{ flex: 1 }}
                  />
                  <button
                    className="btn btn-primary"
                    onClick={() => saveKey(key)}
                    disabled={saving[key] || !edits[key]}
                    style={{ whiteSpace: 'nowrap' }}
                  >
                    {saving[key] ? 'Saving…' : 'Save'}
                  </button>
                  {messages[key] && (
                    <span style={{ fontSize: '0.75rem', color: messages[key] === 'Saved' ? 'var(--success)' : 'var(--danger)', whiteSpace: 'nowrap' }}>
                      {messages[key]}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
