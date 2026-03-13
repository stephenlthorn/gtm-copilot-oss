'use client';

import { useEffect, useState } from 'react';

const FIELDS = [
  { key: 'host', label: 'Host', placeholder: 'gateway01.us-east-1.prod.aws.tidbcloud.com', secret: false },
  { key: 'port', label: 'Port', placeholder: '4000', secret: false },
  { key: 'user', label: 'User', placeholder: 'your-tidb-user', secret: false },
  { key: 'password', label: 'Password', placeholder: '••••••••', secret: true },
  { key: 'database', label: 'Database', placeholder: 'gtm_copilot', secret: false },
  { key: 'ssl_ca', label: 'SSL CA path', placeholder: '/etc/ssl/certs/ca-certificates.crt', secret: false },
];

export default function TiDBConfigPanel() {
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState({ host: '', port: '', user: '', password: '', database: '', ssl_ca: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [message, setMessage] = useState('');
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    fetch('/api/admin/db-config')
      .then((r) => r.json())
      .then((data) => {
        setCfg(data);
        setForm({
          host: data.tidb_host || '',
          port: data.tidb_port || '4000',
          user: data.tidb_user || '',
          password: data.tidb_password === '***' ? '' : (data.tidb_password || ''),
          database: data.tidb_database || '',
          ssl_ca: data.tidb_ssl_ca || '',
        });
      })
      .catch(() => setCfg(null))
      .finally(() => setLoading(false));
  }, []);

  const restartApi = async () => {
    setRestarting(true);
    setMessage('');
    try {
      await fetch('/api/admin/restart-api', { method: 'POST' });
      setMessage('✓ API restarting — page will reload in 10 seconds…');
      setTimeout(() => window.location.reload(), 10000);
    } catch {
      setMessage('✓ API restarting…');
      setTimeout(() => window.location.reload(), 10000);
    } finally {
      setRestarting(false);
    }
  };

  const save = async () => {
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch('/api/admin/tidb-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || 'Save failed');
      setMessage(`✓ ${data.message}`);
      setEditing(false);
      // Refresh display
      const fresh = await fetch('/api/admin/db-config').then((r) => r.json());
      setCfg(fresh);
    } catch (err) {
      setMessage(`✗ ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const isTiDB = cfg?.database_provider === 'tidb';

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">TiDB Cloud Connection</span>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {loading ? (
            <span className="tag">Loading</span>
          ) : (
            <span className={`tag ${isTiDB ? 'tag-green' : ''}`}>
              {cfg?.database_provider ?? '—'}
            </span>
          )}
          {!loading && (
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <button
                className="btn"
                style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}
                onClick={restartApi}
                disabled={restarting}
              >
                {restarting ? 'Restarting…' : 'Restart API'}
              </button>
              <button
                className="btn"
                style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}
                onClick={() => { setEditing((e) => !e); setMessage(''); }}
              >
                {editing ? 'Cancel' : 'Edit'}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem', fontSize: '0.82rem' }}>
        {cfg && !editing && (
          <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '0.4rem 1rem' }}>
            {[
              ['Host', cfg.tidb_host || '—'],
              ['Port', cfg.tidb_port || '—'],
              ['User', cfg.tidb_user || '—'],
              ['Password', cfg.tidb_password ? '••••••••' : '—'],
              ['Database', cfg.tidb_database || '—'],
              ['SSL CA', cfg.tidb_ssl_ca || '(none)'],
            ].map(([label, value]) => (
              <>
                <span key={`l-${label}`} style={{ color: 'var(--text-3)' }}>{label}</span>
                <span key={`v-${label}`} style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{value}</span>
              </>
            ))}
          </div>
        )}

        {editing && (
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            {FIELDS.map(({ key, label, placeholder, secret }) => (
              <label key={key} style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '0.5rem', alignItems: 'center' }}>
                <span style={{ color: 'var(--text-3)', fontSize: '0.8rem' }}>{label}</span>
                <input
                  className="input"
                  type={secret ? 'password' : 'text'}
                  placeholder={placeholder}
                  value={form[key]}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  style={{ fontSize: '0.8rem', padding: '0.3rem 0.5rem', fontFamily: secret ? 'inherit' : 'monospace' }}
                />
              </label>
            ))}
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
              <button className="btn btn-primary" onClick={save} disabled={saving} style={{ fontSize: '0.8rem' }}>
                {saving ? 'Saving…' : 'Save credentials'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-3)', margin: 0 }}>
                After saving, restart the API container for the new connection to take effect.
              </p>
              <button
                className="btn"
                onClick={restartApi}
                disabled={restarting}
                style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem', whiteSpace: 'nowrap' }}
              >
                {restarting ? 'Restarting…' : 'Restart API now'}
              </button>
            </div>
          </div>
        )}

        {message && (
          <p style={{ fontSize: '0.78rem', color: message.startsWith('✓') ? 'var(--success)' : 'var(--danger)', margin: 0 }}>
            {message}
          </p>
        )}

        {!isTiDB && !editing && (
          <p style={{ color: 'var(--text-3)', fontSize: '0.78rem', margin: 0 }}>
            Currently using <strong>{cfg?.database_provider || 'unknown'}</strong>. Enter TiDB Cloud credentials above and set{' '}
            <code>DATABASE_PROVIDER=tidb</code> in your environment to switch.
          </p>
        )}
      </div>
    </div>
  );
}
