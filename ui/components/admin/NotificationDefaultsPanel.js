'use client';

import { useState, useEffect } from 'react';

const DEFAULT_FORM = {
  pre_call_minutes: 30,
  post_call_minutes: 60,
};

export default function NotificationDefaultsPanel() {
  const [form, setForm] = useState(DEFAULT_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetch('/api/admin/system-config')
      .then(r => r.json())
      .then(data => {
        const defaults = data?.['notification.defaults'];
        if (defaults) {
          setForm({
            pre_call_minutes: defaults.pre_call_minutes ?? DEFAULT_FORM.pre_call_minutes,
            post_call_minutes: defaults.post_call_minutes ?? DEFAULT_FORM.post_call_minutes,
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch('/api/admin/system-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 'notification.defaults': form }),
      });
      if (!res.ok) throw new Error('Save failed');
      setMessage('Saved');
    } catch {
      setMessage('Save failed');
    } finally {
      setSaving(false);
    }
  };

  const set = (key, value) => setForm(prev => ({ ...prev, [key]: value }));

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Notification Defaults</span>
      </div>
      <div className="panel-body">
        {loading ? (
          <div className="status-row">Loading…</div>
        ) : (
          <div style={{ display: 'grid', gap: '1rem', maxWidth: '400px' }}>
            <div style={{ display: 'grid', gap: '0.35rem' }}>
              <label style={{ fontSize: '0.72rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Default Pre-Call Notification (minutes before)
              </label>
              <input
                className="input"
                type="number"
                min={0}
                value={form.pre_call_minutes}
                onChange={e => set('pre_call_minutes', Number(e.target.value))}
              />
            </div>
            <div style={{ display: 'grid', gap: '0.35rem' }}>
              <label style={{ fontSize: '0.72rem', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Default Post-Call Notification (minutes after)
              </label>
              <input
                className="input"
                type="number"
                min={0}
                value={form.post_call_minutes}
                onChange={e => set('post_call_minutes', Number(e.target.value))}
              />
            </div>
            <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
              <button className="btn btn-primary" onClick={save} disabled={saving}>
                {saving ? 'Saving…' : 'Save Defaults'}
              </button>
              {message && (
                <span style={{ fontSize: '0.78rem', color: message === 'Saved' ? 'var(--success)' : 'var(--danger)' }}>
                  {message}
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
