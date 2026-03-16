'use client';

import { useState, useEffect } from 'react';

const MODELS = [
  { id: 'gpt-5.4',           label: '5.4',        reasoning: true  },
  { id: 'gpt-5.3-codex',     label: '5.3 Codex',  reasoning: true  },
  { id: 'o3',                label: 'o3',          reasoning: true  },
  { id: 'o4-mini',           label: 'o4-mini',     reasoning: true  },
  { id: 'gpt-5.1-codex',     label: '5.1 Codex',  reasoning: true  },
  { id: 'gpt-5-codex-mini',  label: 'Mini',        reasoning: false },
];

const THINKING_LEVELS = ['low', 'medium', 'high'];

export default function UserModelPicker() {
  const [prefs, setPrefs] = useState({ llm_model: null, reasoning_effort: null });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch('/api/user/preferences')
      .then(r => r.json())
      .then(data => {
        setPrefs({
          llm_model: data.llm_model || null,
          reasoning_effort: data.reasoning_effort || null,
        });
      })
      .catch(() => {});
  }, []);

  const update = async (patch) => {
    const next = { ...prefs, ...patch };
    setPrefs(next);
    setSaving(true);
    try {
      const res = await fetch('/api/user/preferences', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          llm_model: next.llm_model || '',
          reasoning_effort: next.reasoning_effort || '',
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setPrefs({
          llm_model: data.llm_model || null,
          reasoning_effort: data.reasoning_effort || null,
        });
      }
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  };

  const selectedModel = MODELS.find(m => m.id === prefs.llm_model);
  const showThinking = selectedModel?.reasoning ?? false;

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <h3 style={{ margin: 0, fontSize: '0.9rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--dim)' }}>
        Your Model Preferences
      </h3>

      <div>
        <label style={{ fontSize: '0.8rem', color: 'var(--dim)', display: 'block', marginBottom: '0.5rem' }}>
          MODEL {saving && <span style={{ color: 'var(--accent)', marginLeft: '0.5rem' }}>saving...</span>}
        </label>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            className={prefs.llm_model === null ? 'btn btn-primary' : 'btn'}
            style={{ fontSize: '0.75rem' }}
            onClick={() => update({ llm_model: null, reasoning_effort: null })}
          >
            Workspace default
          </button>
          {MODELS.map(m => (
            <button
              key={m.id}
              className={prefs.llm_model === m.id ? 'btn btn-primary' : 'btn'}
              style={{ fontSize: '0.75rem' }}
              onClick={() => update({ llm_model: m.id })}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {showThinking && (
        <div>
          <label style={{ fontSize: '0.8rem', color: 'var(--dim)', display: 'block', marginBottom: '0.5rem' }}>
            THINKING LEVEL
          </label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className={prefs.reasoning_effort === null ? 'btn btn-primary' : 'btn'}
              style={{ fontSize: '0.75rem' }}
              onClick={() => update({ reasoning_effort: null })}
            >
              Workspace default
            </button>
            {THINKING_LEVELS.map(level => (
              <button
                key={level}
                className={prefs.reasoning_effort === level ? 'btn btn-primary' : 'btn'}
                style={{ fontSize: '0.75rem', textTransform: 'capitalize' }}
                onClick={() => update({ reasoning_effort: level })}
              >
                {level}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
