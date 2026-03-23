'use client';

import { useState, useEffect } from 'react';

const MODELS = [
  { id: 'gpt-5.4', label: 'GPT-5.4' },
  { id: 'gpt-5.3-codex', label: 'GPT-5.3 Codex' },
  { id: 'o3', label: 'o3' },
  { id: 'o4-mini', label: 'o4-mini' },
  { id: 'gpt-5.1-codex', label: 'GPT-5.1 Codex' },
  { id: 'gpt-5-codex-mini', label: 'GPT-5 Mini' },
];

export default function KBConfigPanel() {
  const [config, setConfig] = useState(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetch('/api/admin/kb-config')
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => setConfig(data))
      .catch(() => setError('Could not load config.'));
  }, []);

  const save = async () => {
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch('/api/admin/kb-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error();
      setConfig(await res.json());
      setMessage('✓ Saved');
    } catch {
      setMessage('✗ Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (error) return <div style={{ fontSize: '0.8rem', color: 'var(--text-3)' }}>{error}</div>;
  if (!config) return <div style={{ fontSize: '0.8rem', color: 'var(--text-3)' }}>Loading…</div>;

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      <div style={{ display: 'grid', gap: '0.4rem' }}>
        <label style={{ fontSize: '0.74rem', color: 'var(--text-3)' }}>Default model (workspace)</label>
        <select
          className="input"
          value={config.llm_model || 'gpt-5.4'}
          onChange={e => setConfig(prev => ({ ...prev, llm_model: e.target.value }))}
          style={{ fontSize: '0.82rem', maxWidth: '220px' }}
        >
          {MODELS.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
        </select>
      </div>

      <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
        {message && (
          <span style={{ fontSize: '0.78rem', color: message.startsWith('✓') ? 'var(--accent)' : '#ef4444' }}>
            {message}
          </span>
        )}
      </div>
    </div>
  );
}
