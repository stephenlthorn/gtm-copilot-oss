'use client';

import { useEffect, useState } from 'react';

const FREQUENCY_OPTIONS = [
  { value: 'every_hour', label: 'Every hour' },
  { value: 'every_4_hours', label: 'Every 4 hours' },
  { value: 'daily', label: 'Daily' },
];

export default function CalendarScanPanel() {
  const [frequency, setFrequency] = useState('every_4_hours');
  const [lookaheadDays, setLookaheadDays] = useState(7);
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
          const prefs = data?.preferences || {};
          if (prefs.calendar_scan_frequency) setFrequency(prefs.calendar_scan_frequency);
          if (prefs.prep_lookahead_days != null) setLookaheadDays(Number(prefs.prep_lookahead_days));
        }
      } catch {
        // silently use defaults
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const save = async () => {
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch('/api/auth/me/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          calendar_scan_frequency: frequency,
          prep_lookahead_days: Number(lookaheadDays),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || data?.error || 'Failed to save preferences.');
      setMessage('Saved.');
    } catch (err) {
      setMessage(String(err?.message || err));
    } finally {
      setSaving(false);
    }
  };

  const handleLookaheadChange = (e) => {
    const raw = Number(e.target.value);
    if (!Number.isNaN(raw)) setLookaheadDays(Math.min(30, Math.max(1, raw)));
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Calendar Scan Preferences</span>
        {loading && <span className="tag">Loading</span>}
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-2)' }}>
          Controls how often your calendar is scanned and how far ahead prep briefs are generated.
        </p>

        <div style={{ display: 'grid', gap: '0.35rem' }}>
          <label htmlFor="scan-frequency" style={{ color: 'var(--text-3)', fontSize: '0.74rem' }}>
            Scan frequency
          </label>
          <select
            id="scan-frequency"
            className="input"
            value={frequency}
            onChange={(e) => setFrequency(e.target.value)}
          >
            {FREQUENCY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: 'grid', gap: '0.35rem' }}>
          <label htmlFor="lookahead-days" style={{ color: 'var(--text-3)', fontSize: '0.74rem' }}>
            Prep lookahead (days, 1–30)
          </label>
          <input
            id="lookahead-days"
            type="number"
            className="input"
            min={1}
            max={30}
            value={lookaheadDays}
            onChange={handleLookaheadChange}
            style={{ maxWidth: '120px' }}
          />
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <button type="button" className="btn btn-primary" onClick={save} disabled={saving || loading}>
            {saving ? 'Saving…' : 'Save'}
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
