'use client';

import { useState, useEffect } from 'react';

const PROVIDERS = ['google_drive', 'feishu', 'confluence', 'notion', 'github', 'slack', 'custom'];
const SCOPES = ['global', 'account'];

const EMPTY_FORM = { provider: PROVIDERS[0], config: '{}', scope: 'global' };

export default function SourceRegistryPanel() {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/sources');
      if (!res.ok) throw new Error('Failed to load');
      const data = await res.json();
      setSources(Array.isArray(data) ? data : data.sources || []);
    } catch {
      setMessage('Failed to load sources');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const addSource = async () => {
    setSaving(true);
    setMessage('');
    try {
      let config;
      try { config = JSON.parse(form.config); } catch { throw new Error('Config must be valid JSON'); }
      const res = await fetch('/api/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: form.provider, config, scope: form.scope }),
      });
      if (!res.ok) throw new Error('Failed to add source');
      setForm(EMPTY_FORM);
      setShowForm(false);
      setMessage('Source added');
      await load();
    } catch (err) {
      setMessage(err.message || 'Failed to add source');
    } finally {
      setSaving(false);
    }
  };

  const deleteSource = async (id) => {
    setMessage('');
    try {
      const res = await fetch(`/api/sources/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Delete failed');
      setMessage('Source removed');
      await load();
    } catch {
      setMessage('Delete failed');
    }
  };

  const set = (key, value) => setForm(prev => ({ ...prev, [key]: value }));

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Source Registry</span>
        <button className="btn" onClick={() => setShowForm(v => !v)}>
          {showForm ? 'Cancel' : 'Add Source'}
        </button>
      </div>

      {showForm && (
        <div className="panel-body" style={{ borderBottom: '1px solid var(--border)', display: 'grid', gap: '0.6rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
            <div>
              <label style={{ fontSize: '0.72rem', color: 'var(--dim)', display: 'block', marginBottom: '0.3rem' }}>PROVIDER</label>
              <select className="input" value={form.provider} onChange={e => set('provider', e.target.value)}>
                {PROVIDERS.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div>
              <label style={{ fontSize: '0.72rem', color: 'var(--dim)', display: 'block', marginBottom: '0.3rem' }}>SCOPE</label>
              <select className="input" value={form.scope} onChange={e => set('scope', e.target.value)}>
                {SCOPES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label style={{ fontSize: '0.72rem', color: 'var(--dim)', display: 'block', marginBottom: '0.3rem' }}>CONFIG (JSON)</label>
            <textarea
              className="input"
              rows={4}
              value={form.config}
              onChange={e => set('config', e.target.value)}
              placeholder='{"folder_id": "..."}'
            />
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button className="btn btn-primary" onClick={addSource} disabled={saving}>
              {saving ? 'Adding…' : 'Add Source'}
            </button>
            {message && (
              <span style={{ fontSize: '0.78rem', color: message.startsWith('Failed') || message.startsWith('Config') ? 'var(--danger)' : 'var(--success)' }}>
                {message}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="panel-body">
        {!showForm && message && (
          <div style={{ fontSize: '0.78rem', marginBottom: '0.6rem', color: message.startsWith('Failed') ? 'var(--danger)' : 'var(--success)' }}>
            {message}
          </div>
        )}
        {loading ? (
          <div className="status-row">Loading…</div>
        ) : sources.length === 0 ? (
          <div className="status-row">No sources configured.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Provider</th>
                <th>Scope</th>
                <th>Config</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {sources.map(s => (
                <tr key={s.id}>
                  <td className="row-title">{s.provider}</td>
                  <td><span className="tag">{s.scope || 'global'}</span></td>
                  <td style={{ fontFamily: 'monospace', fontSize: '0.72rem', color: 'var(--text-3)', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {typeof s.config === 'object' ? JSON.stringify(s.config) : s.config || '—'}
                  </td>
                  <td>
                    <button className="btn btn-danger" onClick={() => deleteSource(s.id)}>Delete</button>
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
