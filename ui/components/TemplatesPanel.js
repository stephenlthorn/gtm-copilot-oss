'use client';
import { useState, useEffect } from 'react';
import { HARDCODED_DEFAULTS } from './ChatWorkspace';

const SECTION_LABELS = {
  pre_call: 'Pre-Call Intel',
  post_call: 'Post-Call Analysis',
  follow_up: 'Follow-Up Email',
  tal: 'Market Research / TAL',
  se_poc_plan: 'SE: POC Plan',
  se_arch_fit: 'SE: Architecture Fit',
  se_competitor: 'SE: Competitor Coach',
};

export default function TemplatesPanel() {
  const [activeSection, setActiveSection] = useState('pre_call');
  const [view, setView] = useState('default'); // 'default' | 'custom'
  const [ownTemplates, setOwnTemplates] = useState({});
  const [allTemplates, setAllTemplates] = useState([]);
  const [editContent, setEditContent] = useState('');
  const [editName, setEditName] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [selectedOtherUser, setSelectedOtherUser] = useState('');

  useEffect(() => {
    Promise.all([
      fetch('/api/user/templates').then(r => r.json()).catch(() => []),
      fetch('/api/templates/all').then(r => r.json()).catch(() => []),
    ]).then(([own, all]) => {
      const ownMap = {};
      for (const t of own) {
        if (!t.is_default) ownMap[t.section_key] = { content: t.content, template_name: t.template_name };
      }
      setOwnTemplates(ownMap);
      setAllTemplates(all);
    });
  }, []);

  useEffect(() => {
    const own = ownTemplates[activeSection];
    setEditContent(own?.content || HARDCODED_DEFAULTS[activeSection] || '');
    setEditName(own?.template_name || `${SECTION_LABELS[activeSection]} (Custom)`);
    setSelectedOtherUser('');
    setSaveMsg('');
  }, [activeSection, ownTemplates]);

  const loadOtherUser = (email) => {
    setSelectedOtherUser(email);
    const found = allTemplates.find(t => t.user_email === email && t.section_key === activeSection);
    if (found) { setEditContent(found.content); setView('custom'); }
  };

  const loadDefault = () => {
    setEditContent(HARDCODED_DEFAULTS[activeSection] || '');
    setSaveMsg('');
  };

  const save = async () => {
    setSaving(true);
    try {
      const res = await fetch('/api/user/templates', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section_key: activeSection, template_name: editName, content: editContent }),
      });
      if (res.ok) {
        setOwnTemplates(prev => ({ ...prev, [activeSection]: { content: editContent, template_name: editName } }));
        setSaveMsg('Saved.');
        setTimeout(() => setSaveMsg(''), 2500);
      } else {
        setSaveMsg('Save failed.');
      }
    } finally {
      setSaving(false);
    }
  };

  const otherUsersForSection = allTemplates.filter(t => t.section_key === activeSection);
  const defaultContent = HARDCODED_DEFAULTS[activeSection] || '';
  const hasCustom = Boolean(ownTemplates[activeSection]);

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      {/* Section tabs */}
      <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
        {Object.entries(SECTION_LABELS).map(([key, label]) => (
          <button
            key={key}
            className={`btn${activeSection === key ? ' btn-primary' : ''}`}
            style={{ fontSize: '0.78rem', padding: '0.3rem 0.65rem' }}
            onClick={() => { setActiveSection(key); setView('default'); }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Default / Custom toggle */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.65rem' }}>
        <button
          className={`btn${view === 'default' ? ' btn-primary' : ''}`}
          style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
          onClick={() => setView('default')}
        >
          Default
        </button>
        <button
          className={`btn${view === 'custom' ? ' btn-primary' : ''}`}
          style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
          onClick={() => setView('custom')}
        >
          {hasCustom ? 'My Custom ✓' : 'My Custom'}
        </button>
      </div>

      {view === 'default' ? (
        /* ── Default view (read-only) ── */
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>
            This is the system default template for <strong>{SECTION_LABELS[activeSection]}</strong>. Read-only — create a custom version to override it.
          </div>
          <pre style={{
            background: 'var(--bg-2)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            padding: '0.85rem 1rem',
            fontSize: '0.78rem',
            lineHeight: 1.65,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            color: 'var(--text)',
            maxHeight: '520px',
            overflowY: 'auto',
            margin: 0,
          }}>
            {defaultContent}
          </pre>
          <button
            className="btn btn-primary"
            style={{ alignSelf: 'start' }}
            onClick={() => { loadDefault(); setView('custom'); }}
          >
            Use as starting point →
          </button>
        </div>
      ) : (
        /* ── Custom editor ── */
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {/* Load another user's template */}
          {otherUsersForSection.length > 0 && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <label style={{ fontSize: '0.75rem', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>Load from teammate:</label>
              <select className="input" style={{ flex: 1 }} value={selectedOtherUser} onChange={e => loadOtherUser(e.target.value)}>
                <option value="">— select —</option>
                {otherUsersForSection.map(t => (
                  <option key={t.user_email} value={t.user_email}>{t.user_email.split('@')[0]} — {t.template_name}</option>
                ))}
              </select>
            </div>
          )}

          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>Template Name</label>
            <input className="input" value={editName} onChange={e => setEditName(e.target.value)} />
          </div>

          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>Template Content</label>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>
              Placeholders: {'{account}'} {'{prospect_name}'} {'{prospect_linkedin}'} {'{website}'} {'{call_context}'} {'{competitor}'} {'{email_to}'} {'{email_tone}'}
            </div>
            <textarea
              className="input"
              rows={16}
              value={editContent}
              onChange={e => setEditContent(e.target.value)}
              style={{ fontFamily: 'monospace', fontSize: '0.78rem', minHeight: '300px', resize: 'vertical' }}
            />
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <button className="btn btn-primary" onClick={save} disabled={saving || !editContent.trim()}>
              {saving ? 'Saving…' : 'Save My Template'}
            </button>
            <button className="btn" onClick={() => { loadDefault(); }} style={{ fontSize: '0.75rem' }}>
              Reset to Default
            </button>
            {saveMsg && <span style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>{saveMsg}</span>}
          </div>
        </div>
      )}
    </div>
  );
}
