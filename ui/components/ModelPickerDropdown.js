'use client';
import { useState, useEffect, useRef, useCallback } from 'react';

const MODELS = [
  { id: 'gpt-5.4',          label: '5.4',        reasoning: true  },
  { id: 'gpt-5.4-mini',     label: '5.4 Mini',   reasoning: true  },
  { id: 'gpt-5.4-nano',     label: '5.4 Nano',   reasoning: false },
  { id: 'gpt-5.3-codex',    label: '5.3 Codex',  reasoning: true  },
  { id: 'o4-mini',          label: 'o4-mini',     reasoning: true  },
  { id: 'o3',               label: 'o3',          reasoning: true  },
  { id: 'o3-pro',           label: 'o3 Pro',      reasoning: true  },
  { id: 'o3-mini',          label: 'o3 Mini',     reasoning: true  },
  { id: 'gpt-5.1-codex',    label: '5.1 Codex',  reasoning: true  },
  { id: 'gpt-5-codex-mini', label: 'Mini',        reasoning: false },
];

const THINKING = ['low', 'medium', 'high'];

const DEPTHS = [
  { k: 4,  label: 'Low',        sub: '4 chunks' },
  { k: 8,  label: 'Medium',     sub: '8 chunks' },
  { k: 12, label: 'High',       sub: '12 chunks' },
  { k: 20, label: 'Extra High', sub: '20 chunks' },
];

const DEFAULT_MODEL   = 'gpt-5.4';
const DEFAULT_THINK   = 'medium';
const DEFAULT_TOP_K   = 8;

export default function ModelPickerDropdown({ onTopKChange, onModelChange, onThinkingChange }) {
  const [open, setOpen]       = useState(false);
  const [model, setModel]     = useState(DEFAULT_MODEL);
  const [thinking, setThink]  = useState(DEFAULT_THINK);
  const [topK, setTopK]       = useState(DEFAULT_TOP_K);
  const [saving, setSaving]   = useState(false);
  const ref = useRef(null);

  // Load user prefs on mount
  useEffect(() => {
    fetch('/api/user/preferences')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        if (data.llm_model)        { setModel(data.llm_model); onModelChange?.(data.llm_model); }
        if (data.reasoning_effort) { setThink(data.reasoning_effort); onThinkingChange?.(data.reasoning_effort); }
        if (data.retrieval_top_k)  { setTopK(data.retrieval_top_k); onTopKChange?.(data.retrieval_top_k); }
      })
      .catch(() => {});
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const save = useCallback(async (patch) => {
    setSaving(true);
    try {
      await fetch('/api/user/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      });
    } catch { /* silent */ }
    finally { setSaving(false); }
  }, []);

  const pickModel = (id) => { setModel(id); onModelChange?.(id); save({ llm_model: id }); };
  const pickThink = (t)  => { setThink(t); onThinkingChange?.(t); save({ reasoning_effort: t }); };
  const pickDepth = (k)  => { setTopK(k); onTopKChange?.(k); save({ retrieval_top_k: k }); };

  const currentModel  = MODELS.find(m => m.id === model) || MODELS[0];
  const currentDepth  = DEPTHS.find(d => d.k === topK)   || DEPTHS[1];
  const showThinking  = currentModel.reasoning;

  const btnBase = {
    fontSize: '0.72rem', padding: '0.22rem 0.55rem', borderRadius: '4px',
    border: '1px solid var(--border)', cursor: 'pointer', transition: 'background 120ms',
  };
  const btnActive   = { ...btnBase, background: 'var(--accent)', color: '#fff', borderColor: 'var(--accent)' };
  const btnInactive = { ...btnBase, background: 'transparent', color: 'var(--text-2)' };

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          display: 'flex', alignItems: 'center', gap: '0.35rem',
          fontSize: '0.78rem', padding: '0.3rem 0.65rem', borderRadius: '6px',
          border: '1px solid var(--border)', background: open ? 'var(--bg-2)' : 'transparent',
          color: 'var(--text)', cursor: 'pointer', fontWeight: 500,
        }}
      >
        <span>{currentModel.label}</span>
        {showThinking && <span style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>· {thinking}</span>}
        <span style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>· {currentDepth.label}</span>
        <span style={{ fontSize: '0.62rem', color: 'var(--text-3)', marginLeft: '1px' }}>▾</span>
      </button>

      {/* Dropdown panel */}
      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 6px)', left: 0,
          background: 'var(--bg)', border: '1px solid var(--border)',
          borderRadius: '10px', boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
          padding: '1rem', zIndex: 100, minWidth: '320px',
          display: 'grid', gap: '1.1rem',
        }}>
          {saving && (
            <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', textAlign: 'right', marginTop: '-0.5rem' }}>saving…</div>
          )}

          {/* Model */}
          <div style={{ display: 'grid', gap: '0.45rem' }}>
            <div style={{ fontSize: '0.65rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
              LLM Model
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
              {MODELS.map(m => (
                <button key={m.id} onClick={() => pickModel(m.id)} style={model === m.id ? btnActive : btnInactive}>
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* Thinking level */}
          {showThinking && (
            <div style={{ display: 'grid', gap: '0.45rem' }}>
              <div style={{ fontSize: '0.65rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
                Thinking Level
              </div>
              <div style={{ display: 'flex', gap: '0.3rem' }}>
                {THINKING.map(t => (
                  <button key={t} onClick={() => pickThink(t)} style={thinking === t ? btnActive : btnInactive}>
                    {t}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Retrieval depth */}
          <div style={{ display: 'grid', gap: '0.45rem' }}>
            <div style={{ fontSize: '0.65rem', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-3)' }}>
              Retrieval Depth
            </div>
            <div style={{ display: 'flex', gap: '0.3rem' }}>
              {DEPTHS.map(d => (
                <button key={d.k} onClick={() => pickDepth(d.k)}
                  style={{ ...(topK === d.k ? btnActive : btnInactive), display: 'grid', textAlign: 'left', padding: '0.3rem 0.6rem' }}>
                  <span style={{ fontWeight: 500 }}>{d.label}</span>
                  <span style={{ fontSize: '0.62rem', opacity: 0.7 }}>{d.sub}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
