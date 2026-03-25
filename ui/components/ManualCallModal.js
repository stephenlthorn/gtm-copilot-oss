'use client';
import { useState } from 'react';

export default function ManualCallModal({ onClose, onSuccess }) {
  const [form, setForm] = useState({ account: '', notes: '', date: '', stage: '', participants: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.account || !form.notes) { setError('Account and notes are required.'); return; }
    if (form.date && isNaN(new Date(form.date).getTime())) { setError('Please enter a valid date.'); return; }
    setSaving(true);
    setError('');
    try {
      const res = await fetch('/api/calls/manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account: form.account,
          notes: form.notes,
          date: form.date || undefined,
          stage: form.stage || undefined,
          participants: form.participants ? form.participants.split(',').map(s => s.trim()).filter(Boolean) : [],
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: '8px', padding: '1.5rem', width: '480px', maxWidth: '95vw' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <span style={{ fontWeight: 600 }}>Log a call manually</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)' }}>✕</button>
        </div>
        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: '0.75rem' }}>
          <div>
            <label style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>Account *</label>
            <input className="input" value={form.account} onChange={e => setForm(f => ({...f, account: e.target.value}))} placeholder="e.g. Brex" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>Date</label>
              <input className="input" type="date" value={form.date} onChange={e => setForm(f => ({...f, date: e.target.value}))} />
            </div>
            <div>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>Stage</label>
              <select className="input" value={form.stage} onChange={e => setForm(f => ({...f, stage: e.target.value}))}>
                <option value="">— select —</option>
                {['Prospecting','Discovery','Technical Eval','Proposal','Negotiation','Closed Won','Closed Lost'].map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>Participants (comma-separated emails)</label>
            <input className="input" value={form.participants} onChange={e => setForm(f => ({...f, participants: e.target.value}))} placeholder="contact@prospect.com, se@yourcompany.com" />
          </div>
          <div>
            <label style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>Notes * (paste transcript, voice memo, or your own notes)</label>
            <textarea className="input" rows={6} value={form.notes} onChange={e => setForm(f => ({...f, notes: e.target.value}))} placeholder="Paste call notes, transcript, or summary here..." style={{ resize: 'vertical' }} />
          </div>
          {error && <div style={{ color: 'var(--danger)', fontSize: '0.78rem' }}>{error}</div>}
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button type="button" onClick={onClose} className="btn">Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save call'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
