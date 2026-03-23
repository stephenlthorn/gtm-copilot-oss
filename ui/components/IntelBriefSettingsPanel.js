'use client';
import { useState, useEffect } from 'react';

const MODELS = [
  'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.4-nano', 'gpt-5.3-codex',
  'o4-mini', 'o3', 'o3-pro', 'o3-mini', 'gpt-5.1-codex', 'gpt-5-codex-mini',
];
const EFFORT_OPTIONS = ['low', 'medium', 'high'];

export default function IntelBriefSettingsPanel() {
  const [enabled, setEnabled] = useState(true);
  const [summarizerModel, setSummarizerModel] = useState('gpt-5.4-mini');
  const [summarizerEffort, setSummarizerEffort] = useState('');
  const [synthesisModel, setSynthesisModel] = useState('gpt-5.4');
  const [synthesisEffort, setSynthesisEffort] = useState('medium');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch('/api/user/preferences')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        if (data.intel_brief_enabled != null) setEnabled(data.intel_brief_enabled);
        if (data.intel_brief_summarizer_model) setSummarizerModel(data.intel_brief_summarizer_model);
        setSummarizerEffort(data.intel_brief_summarizer_effort || '');
        if (data.intel_brief_synthesis_model) setSynthesisModel(data.intel_brief_synthesis_model);
        if (data.intel_brief_synthesis_effort) setSynthesisEffort(data.intel_brief_synthesis_effort);
      })
      .catch(() => {});
  }, []);

  const save = async (patch) => {
    setSaving(true);
    try {
      await fetch('/api/user/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      });
    } catch { /* silent */ } finally {
      setSaving(false);
    }
  };

  const handleToggle = () => {
    const next = !enabled;
    setEnabled(next);
    save({ intel_brief_enabled: next });
  };

  const labelStyle = { fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 };
  const selectStyle = { fontSize: '0.8rem' };

  return (
    <div style={{ display: 'grid', gap: '0.75rem' }}>
      {/* Toggle row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: '0.82rem', fontWeight: 500 }}>Two-stage summarization</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-3)', marginTop: '0.1rem' }}>
            GPT Mini extracts findings per search query, then synthesis model writes the brief
          </div>
        </div>
        <button
          onClick={handleToggle}
          disabled={saving}
          style={{
            width: '40px', height: '22px', borderRadius: '11px', border: 'none', cursor: 'pointer',
            background: enabled ? 'var(--accent, #7c3aed)' : 'var(--border)',
            position: 'relative', flexShrink: 0, transition: 'background 0.2s',
          }}
          aria-label={enabled ? 'Disable two-stage summarization' : 'Enable two-stage summarization'}
        >
          <span style={{
            position: 'absolute', top: '3px',
            left: enabled ? '21px' : '3px',
            width: '16px', height: '16px', borderRadius: '50%',
            background: 'white', transition: 'left 0.2s',
          }} />
        </button>
      </div>

      {/* Config controls — only shown when enabled */}
      {enabled && (
        <div style={{ display: 'grid', gap: '0.6rem', paddingLeft: '0.5rem', borderLeft: '2px solid var(--border)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
            <div style={{ display: 'grid', gap: '0.25rem' }}>
              <label style={labelStyle}>Summarizer model</label>
              <select
                className="input"
                style={selectStyle}
                value={summarizerModel}
                onChange={e => { setSummarizerModel(e.target.value); save({ intel_brief_summarizer_model: e.target.value }); }}
              >
                {MODELS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div style={{ display: 'grid', gap: '0.25rem' }}>
              <label style={labelStyle}>Summarizer thinking</label>
              <select
                className="input"
                style={selectStyle}
                value={summarizerEffort}
                onChange={e => { setSummarizerEffort(e.target.value); save({ intel_brief_summarizer_effort: e.target.value || null }); }}
              >
                <option value="">None</option>
                {EFFORT_OPTIONS.map(e => <option key={e} value={e}>{e.charAt(0).toUpperCase() + e.slice(1)}</option>)}
              </select>
            </div>
            <div style={{ display: 'grid', gap: '0.25rem' }}>
              <label style={labelStyle}>Synthesis model</label>
              <select
                className="input"
                style={selectStyle}
                value={synthesisModel}
                onChange={e => { setSynthesisModel(e.target.value); save({ intel_brief_synthesis_model: e.target.value }); }}
              >
                {MODELS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div style={{ display: 'grid', gap: '0.25rem' }}>
              <label style={labelStyle}>Synthesis thinking</label>
              <select
                className="input"
                style={selectStyle}
                value={synthesisEffort}
                onChange={e => { setSynthesisEffort(e.target.value); save({ intel_brief_synthesis_effort: e.target.value }); }}
              >
                {EFFORT_OPTIONS.map(e => <option key={e} value={e}>{e.charAt(0).toUpperCase() + e.slice(1)}</option>)}
              </select>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
