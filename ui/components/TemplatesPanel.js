'use client';
import { useState, useEffect } from 'react';

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
  const [ownTemplates, setOwnTemplates] = useState({});  // section_key -> {content, template_name}
  const [allTemplates, setAllTemplates] = useState([]);   // [{user_email, section_key, content, template_name}]
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
    setEditContent(own?.content || '');
    setEditName(own?.template_name || `${SECTION_LABELS[activeSection]} (Custom)`);
    setSelectedOtherUser('');
    setSaveMsg('');
  }, [activeSection, ownTemplates]);

  const loadOtherUser = (email) => {
    setSelectedOtherUser(email);
    const found = allTemplates.find(t => t.user_email === email && t.section_key === activeSection);
    if (found) setEditContent(found.content);
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
        setTimeout(() => setSaveMsg(''), 2000);
      } else {
        setSaveMsg('Save failed.');
      }
    } finally {
      setSaving(false);
    }
  };

  const otherUsersForSection = allTemplates.filter(t => t.section_key === activeSection);

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      {/* Section tabs */}
      <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
        {Object.entries(SECTION_LABELS).map(([key, label]) => (
          <button
            key={key}
            className={`btn${activeSection === key ? ' btn-primary' : ''}`}
            style={{ fontSize: '0.78rem', padding: '0.3rem 0.65rem' }}
            onClick={() => setActiveSection(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Load other user's template */}
      {otherUsersForSection.length > 0 && (
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <label style={{ fontSize: '0.75rem', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>Load from:</label>
          <select className="input" style={{ flex: 1 }} value={selectedOtherUser} onChange={e => loadOtherUser(e.target.value)}>
            <option value="">— select a teammate —</option>
            {otherUsersForSection.map(t => (
              <option key={t.user_email} value={t.user_email}>{t.user_email.split('@')[0]} — {t.template_name}</option>
            ))}
          </select>
        </div>
      )}

      {/* Template name */}
      <div style={{ display: 'grid', gap: '0.35rem' }}>
        <label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>Template Name</label>
        <input className="input" value={editName} onChange={e => setEditName(e.target.value)} />
      </div>

      {/* Template content */}
      <div style={{ display: 'grid', gap: '0.35rem' }}>
        <label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>Template Content</label>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginBottom: '0.25rem' }}>
          Use {'{account}'}, {'{prospect_name}'}, {'{call_context}'}, {'{competitor}'}, etc. as placeholders.
        </div>
        <textarea
          className="input"
          rows={12}
          value={editContent}
          onChange={e => setEditContent(e.target.value)}
          style={{ fontFamily: 'monospace', fontSize: '0.8rem', minHeight: '220px', resize: 'vertical' }}
        />
      </div>

      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        <button className="btn btn-primary" onClick={save} disabled={saving || !editContent.trim()}>
          {saving ? 'Saving…' : 'Save My Template'}
        </button>
        {saveMsg && <span style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>{saveMsg}</span>}
      </div>
    </div>
  );
}
