'use client';
import { useState, useEffect } from 'react';
import PromptEditor from './PromptEditor';

const CATEGORIES = [
  { key: 'system_prompt', label: 'System Prompts' },
  { key: 'template', label: 'Templates' },
  { key: 'persona', label: 'Personas' },
  { key: 'source_profile', label: 'Source Profiles' },
];

export default function PromptStudio() {
  const [prompts, setPrompts] = useState([]);
  const [activeCategory, setActiveCategory] = useState('system_prompt');
  const [selectedId, setSelectedId] = useState(null);
  const [selectedPrompt, setSelectedPrompt] = useState(null);

  useEffect(() => {
    fetch('/api/prompts').then(r => r.json()).then(setPrompts).catch(() => {});
  }, []);

  const loadPrompt = async (id) => {
    setSelectedId(id);
    const res = await fetch(`/api/prompts/${id}`);
    if (res.ok) setSelectedPrompt(await res.json());
  };

  const filtered = prompts.filter(p => p.category === activeCategory);

  if (selectedPrompt) {
    return (
      <PromptEditor
        prompt={selectedPrompt}
        onBack={() => { setSelectedPrompt(null); setSelectedId(null); }}
        onSaved={() => {
          fetch('/api/prompts').then(r => r.json()).then(setPrompts);
          loadPrompt(selectedId);
        }}
      />
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Prompt Studio</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
          {CATEGORIES.map(c => (
            <button
              key={c.key}
              className={`btn ${activeCategory === c.key ? 'btn-primary' : ''}`}
              onClick={() => setActiveCategory(c.key)}
              style={{ fontSize: '0.75rem' }}
            >
              {c.label}
            </button>
          ))}
        </div>

        {filtered.length === 0 && (
          <div style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>
            {prompts.length === 0 ? 'Loading prompts…' : 'No prompts in this category.'}
          </div>
        )}

        {filtered.map(p => (
          <div
            key={p.id}
            onClick={() => loadPrompt(p.id)}
            style={{
              padding: '0.6rem 0.75rem',
              border: '1px solid var(--border)',
              borderRadius: '5px',
              cursor: 'pointer',
              background: selectedId === p.id ? 'rgba(57,255,20,0.06)' : 'var(--bg)',
              transition: 'background 0.1s',
            }}
          >
            <div style={{ fontWeight: 600, fontSize: '0.82rem', color: 'var(--text)' }}>{p.name}</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: '0.2rem' }}>{p.description}</div>
            {p.updated_by && (
              <div style={{ fontSize: '0.68rem', color: 'var(--text-3)', marginTop: '0.2rem' }}>
                Last edited by {p.updated_by}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
