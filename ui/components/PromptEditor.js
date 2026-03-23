'use client';
import { useState } from 'react';
import PromptVersionHistory from './PromptVersionHistory';

export default function PromptEditor({ prompt, onBack, onSaved }) {
  const [content, setContent] = useState(prompt.current_content);
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [status, setStatus] = useState('');

  const variables = JSON.parse(prompt.variables || '[]');
  const isPersona = prompt.category === 'persona';
  const hasChanges = content !== prompt.current_content;

  const save = async () => {
    setSaving(true);
    const res = await fetch(`/api/prompts/${prompt.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, note: note || undefined }),
    });
    setSaving(false);
    if (res.ok) { setStatus('Saved'); setNote(''); onSaved(); }
    else setStatus('Save failed');
    setTimeout(() => setStatus(''), 3000);
  };

  const saveMyVersion = async () => {
    setSaving(true);
    const res = await fetch(`/api/prompts/${prompt.id}/my-override`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    setSaving(false);
    setStatus(res.ok ? 'Personal version saved' : 'Save failed');
    setTimeout(() => setStatus(''), 3000);
  };

  const reset = async () => {
    if (!confirm('Reset to factory default? This creates a new version.')) return;
    const res = await fetch(`/api/prompts/${prompt.id}/reset`, { method: 'POST' });
    if (res.ok) { onSaved(); setStatus('Reset to default'); }
    setTimeout(() => setStatus(''), 3000);
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button className="btn btn-ghost" onClick={onBack} style={{ fontSize: '0.72rem' }}>&larr; Back</button>
          <span className="panel-title">{prompt.name}</span>
          <span className="tag">{prompt.category.replace('_', ' ')}</span>
        </div>
        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
          {status && <span style={{ fontSize: '0.72rem', color: 'var(--accent)' }}>{status}</span>}
          <button className="btn" onClick={() => setShowHistory(!showHistory)} style={{ fontSize: '0.72rem' }}>
            {showHistory ? 'Hide History' : 'History'}
          </button>
        </div>
      </div>

      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>{prompt.description}</div>

        {variables.length > 0 && (
          <div style={{
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            borderRadius: '5px',
            padding: '0.5rem 0.75rem',
          }}>
            <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-3)', marginBottom: '0.3rem' }}>
              AVAILABLE VARIABLES
            </div>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
              {variables.map(v => (
                <code key={v} style={{
                  fontSize: '0.72rem',
                  background: 'rgba(57,255,20,0.08)',
                  color: 'var(--accent)',
                  padding: '0.15rem 0.4rem',
                  borderRadius: '3px',
                  cursor: 'pointer',
                }} onClick={() => navigator.clipboard.writeText(v)}>
                  {v}
                </code>
              ))}
            </div>
          </div>
        )}

        <textarea
          className="input"
          value={content}
          onChange={e => setContent(e.target.value)}
          style={{
            minHeight: '400px',
            maxHeight: '700px',
            resize: 'vertical',
            fontFamily: 'var(--font-mono, monospace)',
            fontSize: '0.78rem',
            lineHeight: '1.6',
          }}
        />

        <input
          className="input"
          value={note}
          onChange={e => setNote(e.target.value)}
          placeholder="Version note (optional) — e.g. 'improved MEDDPICC scoring'"
          style={{ fontSize: '0.78rem' }}
        />

        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={save} disabled={saving || !hasChanges}>
            {saving ? 'Saving…' : 'Save New Version'}
          </button>
          {isPersona && (
            <button className="btn" onClick={saveMyVersion} disabled={saving}>
              Save as My Version
            </button>
          )}
          <button className="btn" onClick={reset} disabled={saving}>
            Reset to Default
          </button>
        </div>

        {showHistory && (
          <PromptVersionHistory
            promptId={prompt.id}
            onRollback={() => { onSaved(); setShowHistory(false); }}
            onSelectVersion={(v) => setContent(v.content)}
          />
        )}
      </div>
    </div>
  );
}
