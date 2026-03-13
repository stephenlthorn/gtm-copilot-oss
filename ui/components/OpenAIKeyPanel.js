'use client';

import { useEffect, useState } from 'react';

export default function OpenAIKeyPanel() {
  const [apiKey, setApiKey] = useState('');
  const [hasKey, setHasKey] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch('/api/auth/me', { cache: 'no-store' });
        if (res.ok) {
          const data = await res.json();
          setHasKey(Boolean(data?.has_openai_key));
        }
      } catch {
        // silently ignore — treat as no key set
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const save = async () => {
    if (!apiKey.trim()) {
      setMessage('Please enter an API key.');
      return;
    }
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch('/api/auth/openai-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || data?.error || 'Failed to save API key.');
      setHasKey(true);
      setApiKey('');
      setMessage('Key saved.');
    } catch (err) {
      setMessage(String(err?.message || err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">OpenAI API Key</span>
        {!loading && (
          <span className={`tag ${hasKey ? 'tag-green' : ''}`}>
            {hasKey ? '✓ Key saved' : 'Not set'}
          </span>
        )}
        {loading && <span className="tag">Loading</span>}
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-2)' }}>
          Used for all LLM calls when no server-side key is configured.
        </p>

        <div style={{ display: 'grid', gap: '0.35rem' }}>
          <label htmlFor="openai-key-input" style={{ color: 'var(--text-3)', fontSize: '0.74rem' }}>
            API Key
          </label>
          <input
            id="openai-key-input"
            type="password"
            className="input"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={hasKey ? 'Enter new key to replace existing' : 'sk-…'}
            autoComplete="off"
          />
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button type="button" className="btn btn-primary" onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save Key'}
          </button>
          {message && (
            <span
              style={{
                fontSize: '0.75rem',
                color: message === 'Key saved.' ? 'var(--success)' : 'var(--danger)',
              }}
            >
              {message}
            </span>
          )}
        </div>

        <p style={{ fontSize: '0.74rem', color: 'var(--text-3)', margin: 0 }}>
          Your key is encrypted at rest. Never shared.
        </p>
      </div>
    </div>
  );
}
