'use client';

import { useState } from 'react';

const DEFAULT_PROFILES = {
  pre_call: {
    name: 'Pre-Call Intelligence',
    sources: [
      { name: 'SEC EDGAR', search: 'site:sec.gov {company} 10-K OR 10-Q', priority: 1, why: 'Technology strategy, infrastructure spend, vendor mentions' },
      { name: 'Earnings Transcripts', search: '{company} earnings call transcript', priority: 1, why: 'CTO/CFO discuss infrastructure modernization plans' },
      { name: 'LinkedIn', search: 'site:linkedin.com {company} {contact}', priority: 1, why: 'Job titles, tenure, career history, connections' },
      { name: 'Crunchbase', search: 'site:crunchbase.com {company}', priority: 2, why: 'Funding, investors, leadership, acquisition history' },
      { name: 'BuiltWith/StackShare', search: '{company} technology stack OR site:stackshare.io {company}', priority: 1, why: 'Identify MySQL, PostgreSQL, Oracle usage — migration opportunity' },
      { name: 'GitHub', search: 'site:github.com {company} mysql OR database OR migration', priority: 2, why: 'Sharding code, Vitess/ProxySQL = scale pain signals' },
      { name: 'G2/TrustRadius', search: 'site:g2.com OR site:trustradius.com {company} database review', priority: 2, why: 'Pain with incumbent DB vendors' },
      { name: 'Job Postings', search: '{company} hiring database engineer OR DBA OR platform engineer', priority: 2, why: 'Hiring for DB roles = infrastructure investment signal' },
      { name: 'Google News', search: '{company} expansion OR funding OR acquisition OR migration', priority: 2, why: 'Recent events affecting buying decisions' },
      { name: 'Reddit/HN', search: 'site:reddit.com OR site:news.ycombinator.com {company} database', priority: 3, why: 'Unfiltered developer sentiment' },
    ],
  },
  post_call: {
    name: 'Post-Call Coaching',
    sources: [
      { name: 'MEDDPICC Validation', type: 'framework', priority: 1, why: 'Validate: Metrics, Economic Buyer, Decision Criteria/Process, Paper Process, Implicate Pain, Champion, Competition' },
      { name: 'Competitor Battlecards', search: '{competitor} vs TiDB OR distributed SQL comparison', priority: 1, why: 'Counter competitor claims from the call' },
      { name: 'Technical Verification', search: '{technical_claim} benchmark OR documentation', priority: 2, why: 'Verify technical claims made during the call' },
      { name: 'Deal Qualification', type: 'framework', priority: 1, why: 'Score: Champion strength, access to EB, compelling event, decision timeline' },
    ],
  },
  poc_technical: {
    name: 'POC & Technical Evaluation',
    sources: [
      { name: 'TiDB Docs', search: 'site:docs.pingcap.com {topic}', priority: 1, why: 'Official documentation for architecture, compatibility, migration guides' },
      { name: 'DB-Engines', search: 'site:db-engines.com {database} vs TiDB', priority: 2, why: 'Ranking, trend data, system properties comparison' },
      { name: 'Jepsen', search: 'site:jepsen.io tidb', priority: 2, why: 'Consistency/correctness test results — strong proof point' },
      { name: 'GitHub pingcap', search: 'site:github.com/pingcap {topic}', priority: 1, why: 'Source code, issues, release notes, community activity' },
      { name: 'PingCAP Blog', search: 'site:pingcap.com/blog {topic}', priority: 1, why: 'Case studies, benchmarks, migration stories' },
      { name: 'Percona Community', search: 'site:percona.com {topic} MySQL', priority: 3, why: 'MySQL ecosystem context — Percona users are TiDB prospects' },
      { name: 'Stack Overflow', search: 'site:stackoverflow.com tidb OR distributed SQL {topic}', priority: 2, why: 'Developer Q&A, common issues, community solutions' },
      { name: 'Competitor Docs', search: 'site:cockroachlabs.com OR site:planetscale.com OR docs.aws.amazon.com/AmazonRDS {topic}', priority: 3, why: 'Comparison selling — understand competitor capabilities' },
    ],
  },
};

const PRIORITY_LABELS = { 1: 'HIGH', 2: 'MEDIUM', 3: 'LOW' };
const PRIORITY_COLORS = { 1: 'var(--success)', 2: 'var(--accent)', 3: 'var(--dim)' };

const SECTION_KEYS = [
  { key: 'pre_call', label: 'Pre-Call Intelligence', description: 'Oracle / Rep / Marketing modes' },
  { key: 'post_call', label: 'Post-Call Coaching', description: 'Call Assistant mode' },
  { key: 'poc_technical', label: 'POC & Technical Evaluation', description: 'SE mode' },
];

function SourceRow({ source, onChange, onRemove }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr 80px 32px', gap: '0.5rem', alignItems: 'start', fontSize: '0.8rem' }}>
      <input
        className="input"
        style={{ fontSize: '0.78rem' }}
        value={source.name}
        placeholder="Source name"
        onChange={e => onChange({ ...source, name: e.target.value })}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        <input
          className="input"
          style={{ fontSize: '0.78rem' }}
          value={source.search || ''}
          placeholder="Search pattern (optional)"
          onChange={e => onChange({ ...source, search: e.target.value })}
        />
        <input
          className="input"
          style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}
          value={source.why || ''}
          placeholder="Description / why"
          onChange={e => onChange({ ...source, why: e.target.value })}
        />
      </div>
      <select
        className="input"
        style={{ fontSize: '0.78rem' }}
        value={source.priority}
        onChange={e => onChange({ ...source, priority: Number(e.target.value) })}
      >
        <option value={1}>HIGH</option>
        <option value={2}>MED</option>
        <option value={3}>LOW</option>
      </select>
      <button
        className="btn"
        style={{ padding: '0.2rem 0.4rem', fontSize: '0.75rem', color: '#ef4444' }}
        title="Remove source"
        onClick={onRemove}
      >
        x
      </button>
    </div>
  );
}

function SourceSection({ sectionKey, label, description, profiles, onChange }) {
  const [open, setOpen] = useState(false);
  const profile = profiles[sectionKey] || DEFAULT_PROFILES[sectionKey];
  const sources = profile?.sources || [];

  const updateSources = (newSources) => {
    onChange({
      ...profiles,
      [sectionKey]: { ...profile, sources: newSources },
    });
  };

  const addSource = () => {
    updateSources([...sources, { name: '', search: '', priority: 2, why: '' }]);
    if (!open) setOpen(true);
  };

  return (
    <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
      <div
        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', userSelect: 'none' }}
        onClick={() => setOpen(!open)}
      >
        <span style={{ fontSize: '0.75rem', color: 'var(--dim)', width: '1rem' }}>{open ? '\u25BC' : '\u25B6'}</span>
        <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>{label}</span>
        <span style={{ fontSize: '0.72rem', color: 'var(--dim)' }}>({sources.length} sources) — {description}</span>
      </div>
      {open && (
        <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', paddingLeft: '1.5rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr 80px 32px', gap: '0.5rem', fontSize: '0.7rem', color: 'var(--dim)', textTransform: 'uppercase' }}>
            <span>Name</span>
            <span>Search / Description</span>
            <span>Priority</span>
            <span></span>
          </div>
          {sources.map((source, idx) => (
            <SourceRow
              key={idx}
              source={source}
              onChange={(updated) => {
                const next = [...sources];
                next[idx] = updated;
                updateSources(next);
              }}
              onRemove={() => updateSources(sources.filter((_, i) => i !== idx))}
            />
          ))}
          <button
            className="btn"
            style={{ fontSize: '0.75rem', width: 'fit-content' }}
            onClick={addSource}
          >
            + Add Source
          </button>
        </div>
      )}
    </div>
  );
}

export default function SourceProfilesPanel({ initialProfiles }) {
  const [profiles, setProfiles] = useState(() => {
    const init = initialProfiles && typeof initialProfiles === 'object' && Object.keys(initialProfiles).length > 0
      ? initialProfiles
      : {};
    const merged = {};
    for (const { key } of SECTION_KEYS) {
      merged[key] = init[key] || DEFAULT_PROFILES[key];
    }
    return merged;
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  const save = async () => {
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch('/api/admin/kb-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source_profiles_json: profiles }),
      });
      if (!res.ok) throw new Error('Save failed');
      setMessage('Saved');
    } catch {
      setMessage('Save failed');
    } finally {
      setSaving(false);
    }
  };

  const resetToDefaults = () => {
    const merged = {};
    for (const { key } of SECTION_KEYS) {
      merged[key] = JSON.parse(JSON.stringify(DEFAULT_PROFILES[key]));
    }
    setProfiles(merged);
    setMessage('Reset to defaults (save to apply)');
  };

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <h3 style={{ margin: 0, fontSize: '0.9rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--dim)' }}>
        Intelligence Sources
      </h3>
      <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-3)' }}>
        Configure which web sources the AI prioritizes for each sales phase. Sources are injected into LLM prompts when web search is enabled.
      </p>

      {SECTION_KEYS.map(({ key, label, description }) => (
        <SourceSection
          key={key}
          sectionKey={key}
          label={label}
          description={description}
          profiles={profiles}
          onChange={setProfiles}
        />
      ))}

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.75rem', display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <button className="btn btn-primary" onClick={save} disabled={saving}>
          {saving ? 'Saving...' : 'Save Sources'}
        </button>
        <button className="btn" onClick={resetToDefaults}>
          Reset to Defaults
        </button>
        {message && (
          <span style={{ fontSize: '0.8rem', color: message === 'Saved' ? 'var(--accent)' : message.includes('failed') ? '#ef4444' : 'var(--dim)' }}>
            {message}
          </span>
        )}
      </div>
    </div>
  );
}
