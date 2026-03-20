'use client';

import { useEffect, useState } from 'react';

const NOTIFICATION_TYPES = [
  { id: 'pre_call_ready', label: 'Pre-call brief ready' },
  { id: 'post_call_ready', label: 'Post-call summary ready' },
  { id: 'deal_risk', label: 'Deal risk alert' },
  { id: 'competitive_intel', label: 'Competitive intel update' },
];

const TIMING_OPTIONS = [
  { value: 'immediate', label: 'Immediate' },
  { value: '15_min_before', label: '15 min before' },
  { value: '30_min_before', label: '30 min before' },
  { value: '1_hour_before', label: '1 hour before' },
];

function makeDefaultPrefs() {
  return Object.fromEntries(
    NOTIFICATION_TYPES.map((t) => [
      t.id,
      { enabled: false, timing: 'immediate', channel: '' },
    ])
  );
}

export default function SlackNotificationsPanel() {
  const [prefs, setPrefs] = useState(makeDefaultPrefs());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch('/api/notifications/preferences', { cache: 'no-store' });
        if (res.ok) {
          const data = await res.json();
          if (data && typeof data === 'object') {
            setPrefs((prev) => {
              const merged = { ...prev };
              for (const type of NOTIFICATION_TYPES) {
                if (data[type.id]) {
                  merged[type.id] = {
                    enabled: Boolean(data[type.id].enabled ?? false),
                    timing: data[type.id].timing ?? 'immediate',
                    channel: data[type.id].channel ?? '',
                  };
                }
              }
              return merged;
            });
          }
        }
      } catch {
        // silently use defaults
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const updatePref = (typeId, field, value) => {
    setPrefs((prev) => ({
      ...prev,
      [typeId]: { ...prev[typeId], [field]: value },
    }));
  };

  const saveAll = async () => {
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch('/api/notifications/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(prefs),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || data?.error || 'Failed to save notification preferences.');
      setMessage('Saved.');
    } catch (err) {
      setMessage(String(err?.message || err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Slack Notification Preferences</span>
        {loading && <span className="tag">Loading</span>}
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-2)' }}>
          Configure which events trigger a Slack notification, when to send it, and which channel to use.
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 90px 160px 180px',
            gap: '0.35rem 0.75rem',
            fontSize: '0.74rem',
            color: 'var(--text-3)',
          }}
        >
          <span>Notification type</span>
          <span>Enabled</span>
          <span>Timing</span>
          <span>Channel</span>

          {NOTIFICATION_TYPES.map((type) => {
            const pref = prefs[type.id];
            return [
              <span
                key={`${type.id}-label`}
                style={{ color: 'var(--text)', fontSize: '0.8rem', display: 'flex', alignItems: 'center' }}
              >
                {type.label}
              </span>,

              <div
                key={`${type.id}-enabled`}
                style={{ display: 'flex', alignItems: 'center' }}
              >
                <input
                  type="checkbox"
                  checked={pref.enabled}
                  onChange={(e) => updatePref(type.id, 'enabled', e.target.checked)}
                  aria-label={`Enable ${type.label}`}
                />
              </div>,

              <select
                key={`${type.id}-timing`}
                className="input"
                value={pref.timing}
                onChange={(e) => updatePref(type.id, 'timing', e.target.value)}
                disabled={!pref.enabled}
                style={{ fontSize: '0.78rem' }}
              >
                {TIMING_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>,

              <input
                key={`${type.id}-channel`}
                type="text"
                className="input"
                value={pref.channel}
                onChange={(e) => updatePref(type.id, 'channel', e.target.value)}
                disabled={!pref.enabled}
                placeholder="#channel"
                style={{ fontSize: '0.78rem' }}
              />,
            ];
          })}
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button type="button" className="btn btn-primary" onClick={saveAll} disabled={saving || loading}>
            {saving ? 'Saving…' : 'Save All'}
          </button>
          {message && (
            <span
              style={{
                fontSize: '0.75rem',
                color: message === 'Saved.' ? 'var(--success)' : 'var(--danger)',
              }}
            >
              {message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
