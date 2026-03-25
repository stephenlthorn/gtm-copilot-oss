'use client';

import { useState, useMemo } from 'react';

const STAGE_COLORS = {
  discovery: '#58a6ff',
  demo: '#79c0ff',
  poc: '#bc8cff',
  negotiation: '#ffa657',
  closed: '#3fb950',
  churned: '#f85149',
};

function stageColor(stage) {
  if (!stage) return 'var(--text-3)';
  const key = stage.toLowerCase().replace(/\s+/g, '');
  for (const [k, v] of Object.entries(STAGE_COLORS)) {
    if (key.includes(k)) return v;
  }
  return '#58a6ff';
}

function formatDate(d) {
  if (!d) return '—';
  const date = new Date(d);
  if (isNaN(date)) return d;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function initials(name) {
  return name.split(/\s+/).map(w => w[0]?.toUpperCase() || '').join('').slice(0, 2) || '?';
}

function scoreDashoffset(score) {
  return Math.round((1 - score / 10) * 251.2 * 100) / 100;
}

function scoreColor(score) {
  if (score >= 8) return '#3fb950';
  if (score >= 6.5) return '#58a6ff';
  if (score >= 5) return '#ffa657';
  return '#f85149';
}

// ── Profile sharing helpers ──────────────────────────────────────────────────

function profileToText(profile, company) {
  const name = profile.company || company;
  const lines = [
    `${name} — TiDB Account Intelligence Profile`,
    `Fit Score: ${profile.fit_score}/10 | Relationship: ${profile.relationship_health || 'N/A'}`,
    '',
    profile.overview_1 || '',
    profile.overview_2 || '',
    '',
    'Stack: ' + (profile.stack?.databases || []).join(', '),
    'Cloud: ' + (profile.stack?.cloud || []).join(', '),
    profile.stack?.compatibility || '',
  ];
  if (profile.pain_points?.length) {
    lines.push('', 'Pain Points:');
    profile.pain_points.forEach(p => lines.push(`- [${p.severity}] ${p.title}: ${p.pain} → ${p.solution}`));
  }
  if (profile.buy_signals?.length) {
    lines.push('', 'Buy Signals:');
    profile.buy_signals.forEach(s => lines.push(`- [${s.urgency}] ${s.title}: ${s.text}`));
  }
  if (profile.next_steps?.length) {
    lines.push('', 'Next Steps:');
    profile.next_steps.forEach(s => lines.push(`- ${s}`));
  }
  if (profile.opening_pitch) {
    lines.push('', 'Opening Pitch:', profile.opening_pitch);
  }
  return lines.join('\n');
}

function CopyProfileButton({ profile, company }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(profileToText(profile, company)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <button onClick={copy} style={{ background: copied ? 'rgba(63,185,80,0.2)' : 'transparent', border: '1px solid #30363d', color: copied ? '#3fb950' : '#8b949e', padding: '0.3rem 0.75rem', borderRadius: 6, cursor: 'pointer', fontSize: '0.78rem' }}>
      {copied ? '✓ Copied' : 'Copy Brief'}
    </button>
  );
}

function SlackProfileButton({ profile, company }) {
  const [state, setState] = useState('idle');
  const [channel, setChannel] = useState('');
  const [showInput, setShowInput] = useState(false);

  const share = async () => {
    if (!channel.trim()) return;
    setState('sending');
    try {
      const res = await fetch('/api/share/slack', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel: channel.trim(), text: profileToText(profile, company) }),
      });
      setState(res.ok ? 'sent' : 'error');
      setTimeout(() => { setState('idle'); setShowInput(false); }, 2000);
    } catch {
      setState('error');
      setTimeout(() => setState('idle'), 3000);
    }
  };

  if (!showInput) {
    return (
      <button onClick={() => setShowInput(true)} style={{ background: 'transparent', border: '1px solid #30363d', color: '#8b949e', padding: '0.3rem 0.75rem', borderRadius: 6, cursor: 'pointer', fontSize: '0.78rem' }}>
        Share to Slack
      </button>
    );
  }

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <input
        type="text" value={channel} onChange={e => setChannel(e.target.value)}
        placeholder="#channel" onKeyDown={e => e.key === 'Enter' && share()}
        style={{ fontSize: '0.72rem', padding: '3px 8px', borderRadius: 4, border: '1px solid #30363d', background: '#0d1117', color: '#e6edf3', width: 120 }}
        autoFocus
      />
      <button onClick={share} style={{ background: 'transparent', border: '1px solid #30363d', color: state === 'sent' ? '#3fb950' : state === 'error' ? '#f85149' : '#8b949e', padding: '0.3rem 0.5rem', borderRadius: 6, cursor: 'pointer', fontSize: '0.72rem' }} disabled={state === 'sending'}>
        {state === 'sending' ? '...' : state === 'sent' ? '✓ Sent' : state === 'error' ? '✗ Failed' : 'Send'}
      </button>
      <button onClick={() => setShowInput(false)} style={{ background: 'transparent', border: 'none', color: '#8b949e', cursor: 'pointer', fontSize: '0.78rem' }}>✕</button>
    </span>
  );
}

// ── Profile View (rendered when AI generates a profile) ──────────────────────

function ProfileView({ profile, company, onClose }) {
  if (!profile) return null;
  const color = scoreColor(profile.fit_score || 5);
  const offset = scoreDashoffset(profile.fit_score || 5);

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000, overflow: 'auto',
      background: '#0d1117', color: '#e6edf3',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
    }}>
      {/* Profile topbar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 1.5rem', borderBottom: '1px solid #30363d', background: '#161b27', position: 'sticky', top: 0, zIndex: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: `linear-gradient(135deg, ${color}, #1f6feb)`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900, fontSize: 14, color: '#fff' }}>{initials(profile.company || company)}</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.95rem' }}>{profile.company || company}</div>
            <div style={{ fontSize: '0.72rem', color: '#8b949e' }}>TiDB Account Intelligence Profile</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <CopyProfileButton profile={profile} company={company} />
          <SlackProfileButton profile={profile} company={company} />
          <button onClick={onClose} style={{ background: 'transparent', border: '1px solid #30363d', color: '#8b949e', padding: '0.3rem 0.75rem', borderRadius: 6, cursor: 'pointer', fontSize: '0.78rem' }}>
            ✕ Close
          </button>
        </div>
      </div>

      {/* Hero */}
      <div style={{ background: 'linear-gradient(135deg, #0d1117 0%, #161b27 50%, #1c2333 100%)', borderBottom: '1px solid #30363d', padding: '2rem 2.5rem 1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 24, flexWrap: 'wrap' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 32, fontWeight: 800, letterSpacing: '-0.5px', lineHeight: 1.1 }}>{profile.company || company}</div>
            <div style={{ color: '#8b949e', fontSize: '0.88rem', marginTop: 6 }}>{[profile.domain, profile.hq, profile.founded ? `Founded ${profile.founded}` : null].filter(Boolean).join(' · ')}</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
              {profile.sector && <span style={{ background: 'rgba(88,166,255,0.12)', border: '1px solid rgba(88,166,255,0.3)', color: '#58a6ff', fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 20 }}>{profile.sector}</span>}
              {profile.funding && <span style={{ background: 'rgba(63,185,80,0.12)', border: '1px solid rgba(63,185,80,0.3)', color: '#3fb950', fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 20 }}>{profile.funding}</span>}
              {profile.stack?.databases?.[0] && <span style={{ background: 'rgba(188,140,255,0.12)', border: '1px solid rgba(188,140,255,0.3)', color: '#bc8cff', fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 20 }}>{profile.stack.databases[0]}</span>}
            </div>
          </div>
          {/* Score dial */}
          <div style={{ textAlign: 'center', flexShrink: 0 }}>
            <div style={{ width: 100, height: 100, position: 'relative' }}>
              <svg width="100" height="100" viewBox="0 0 100 100" style={{ transform: 'rotate(-90deg)' }}>
                <circle cx="50" cy="50" r="40" fill="none" stroke="#30363d" strokeWidth="8" />
                <circle cx="50" cy="50" r="40" fill="none" stroke={color} strokeWidth="8" strokeLinecap="round" strokeDasharray="251.2" strokeDashoffset={offset} />
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', fontSize: 26, fontWeight: 900, color, lineHeight: 1 }}>
                {profile.fit_score}<span style={{ fontSize: 10, color: '#8b949e', fontWeight: 500, marginTop: 2 }}>/ 10</span>
              </div>
            </div>
            <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600, marginTop: 8 }}>TiDB Fit Score</div>
            {profile.relationship_health && (() => {
              const h = profile.relationship_health.toLowerCase();
              const rColor = h === 'strong' ? '#3fb950' : h === 'neutral' ? '#58a6ff' : h === 'at-risk' ? '#d29922' : '#f85149';
              return <div style={{ marginTop: 6, fontSize: 11, fontWeight: 700, color: rColor, background: `${rColor}18`, border: `1px solid ${rColor}40`, borderRadius: 20, padding: '2px 10px', textTransform: 'capitalize' }}>{profile.relationship_health}</div>;
            })()}
          </div>
        </div>

        {/* KPIs */}
        {profile.kpis?.length > 0 && (
          <div style={{ display: 'flex', gap: 0, borderTop: '1px solid #30363d', marginTop: 24, paddingTop: 18, flexWrap: 'wrap' }}>
            {profile.kpis.map((k, i) => (
              <div key={i} style={{ flex: 1, minWidth: 100, paddingLeft: i > 0 ? 20 : 0, paddingRight: 20, borderLeft: i > 0 ? '1px solid #30363d' : 'none' }}>
                <div style={{ fontSize: 20, fontWeight: 800 }}>{k.value}</div>
                <div style={{ fontSize: 11, color: '#8b949e', textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: 2 }}>{k.label}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Body */}
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '2rem 2.5rem', display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24 }}>
        <div>
          {/* Overview */}
          <div style={{ background: '#161b27', border: '1px solid #30363d', borderRadius: 12, overflow: 'hidden', marginBottom: 20 }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid #30363d', display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 14 }}>🏢</span>
              <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e' }}>Company Overview</span>
            </div>
            <div style={{ padding: '18px', display: 'grid', gap: 12 }}>
              {profile.overview_1 && <p style={{ fontSize: 13, color: '#8b949e', lineHeight: 1.75 }}>{profile.overview_1}</p>}
              {profile.overview_2 && <p style={{ fontSize: 13, color: '#8b949e', lineHeight: 1.75 }}>{profile.overview_2}</p>}
            </div>
          </div>

          {/* Pain → Solution */}
          {profile.pain_points?.length > 0 && (
            <div style={{ background: '#161b27', border: '1px solid #30363d', borderRadius: 12, overflow: 'hidden', marginBottom: 20 }}>
              <div style={{ padding: '14px 18px', borderBottom: '1px solid #30363d', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 14 }}>⚡</span>
                <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e' }}>Pain Points → TiDB Solution</span>
              </div>
              <div style={{ padding: '4px 18px' }}>
                {profile.pain_points.map((p, i) => (
                  <div key={i} style={{ borderBottom: i < profile.pain_points.length - 1 ? '1px solid #30363d' : 'none', padding: '16px 0' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e', marginBottom: 4 }}>
                      {p.severity === 'high' ? '🔴' : '🟡'} {p.title}
                    </div>
                    <p style={{ fontSize: 13, color: '#e6edf3', lineHeight: 1.6 }}>{p.pain}</p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '10px 0' }}>
                      <div style={{ flex: 1, height: 1, background: 'linear-gradient(to right, #f85149, #3fb950)', opacity: 0.5 }} />
                      <span style={{ fontSize: 16 }}>↓</span>
                      <div style={{ flex: 1, height: 1, background: 'linear-gradient(to right, #f85149, #3fb950)', opacity: 0.5 }} />
                    </div>
                    <p style={{ fontSize: 13, color: '#79c0ff', lineHeight: 1.6 }}>{p.solution}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Buy Signals */}
          {profile.buy_signals?.length > 0 && (
            <div style={{ background: '#161b27', border: '1px solid #30363d', borderRadius: 12, overflow: 'hidden', marginBottom: 20 }}>
              <div style={{ padding: '14px 18px', borderBottom: '1px solid #30363d', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 14 }}>📡</span>
                <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e' }}>Buy Signals</span>
              </div>
              <div style={{ padding: '4px 18px' }}>
                {profile.buy_signals.map((s, i) => (
                  <div key={i} style={{ display: 'flex', gap: 12, padding: '14px 0', borderBottom: i < profile.buy_signals.length - 1 ? '1px solid #30363d' : 'none' }}>
                    <div style={{
                      width: 10, height: 10, borderRadius: '50%', marginTop: 5, flexShrink: 0,
                      background: s.urgency === 'risk' ? '#ff7b72' : s.urgency === 'high' ? '#f85149' : s.urgency === 'medium' ? '#d29922' : '#3fb950',
                      boxShadow: `0 0 6px ${s.urgency === 'risk' ? 'rgba(255,123,114,0.6)' : s.urgency === 'high' ? 'rgba(248,81,73,0.5)' : s.urgency === 'medium' ? 'rgba(210,153,34,0.5)' : 'rgba(63,185,80,0.5)'}`,
                    }} />
                    <div style={{ fontSize: 13, lineHeight: 1.65, color: '#8b949e' }}>
                      <strong style={{ color: '#e6edf3' }}>{s.title}</strong> — {s.text}
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 16, padding: '10px 18px', background: '#1c2333', borderTop: '1px solid #30363d', fontSize: 11, color: '#8b949e' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff7b72', display: 'inline-block' }} /> Risk / Blocker</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f85149', display: 'inline-block' }} /> High urgency</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#d29922', display: 'inline-block' }} /> Medium urgency</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#3fb950', display: 'inline-block' }} /> Low urgency</span>
              </div>
            </div>
          )}

          {/* Workloads */}
          {profile.workloads?.length > 0 && (
            <div style={{ background: '#161b27', border: '1px solid #30363d', borderRadius: 12, overflow: 'hidden' }}>
              <div style={{ padding: '14px 18px', borderBottom: '1px solid #30363d', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 14 }}>🎯</span>
                <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e' }}>Target Workloads</span>
              </div>
              <div style={{ padding: 18, display: 'grid', gap: 10 }}>
                {profile.workloads.map((w, i) => (
                  <div key={i} style={{ padding: '12px 14px', background: '#1c2333', border: '1px solid #30363d', borderRadius: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                      <span style={{ fontSize: 13, fontWeight: 700 }}>{w.name}</span>
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 10, textTransform: 'uppercase', letterSpacing: '0.06em',
                        background: w.priority === 'P1' ? 'rgba(248,81,73,0.15)' : 'rgba(210,153,34,0.15)',
                        color: w.priority === 'P1' ? '#f85149' : '#d29922',
                        border: `1px solid ${w.priority === 'P1' ? 'rgba(248,81,73,0.3)' : 'rgba(210,153,34,0.3)'}`,
                      }}>{w.priority}</span>
                    </div>
                    <div style={{ fontSize: 12, color: '#8b949e', lineHeight: 1.5 }}>{w.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right column */}
        <div>
          {/* Tech Stack */}
          {profile.stack && (
            <div style={{ background: '#161b27', border: '1px solid #30363d', borderRadius: 12, overflow: 'hidden', marginBottom: 20 }}>
              <div style={{ padding: '14px 18px', borderBottom: '1px solid #30363d', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 14 }}>🔧</span>
                <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e' }}>Tech Stack</span>
              </div>
              <div style={{ padding: 18, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                {[['Databases', profile.stack.databases], ['Cloud', profile.stack.cloud], ['AI / Data', profile.stack.ai], ['Languages', profile.stack.languages]].map(([label, tags]) => tags?.length > 0 && (
                  <div key={label}>
                    <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e', marginBottom: 6 }}>{label}</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {tags.map((t, i) => (
                        <span key={i} style={{ background: label === 'Databases' ? 'rgba(88,166,255,0.08)' : '#1c2333', border: `1px solid ${label === 'Databases' ? 'rgba(88,166,255,0.4)' : '#30363d'}`, borderRadius: 6, padding: '3px 8px', fontSize: 11, color: label === 'Databases' ? '#58a6ff' : '#e6edf3', fontFamily: 'monospace' }}>{t}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {profile.stack.compatibility && (
                <div style={{ margin: '0 18px 18px', paddingTop: 14, borderTop: '1px solid #30363d' }}>
                  <div style={{ fontSize: 11, color: '#8b949e', marginBottom: 6 }}>★ TiDB Compatible</div>
                  <div style={{ fontSize: 12, color: '#58a6ff', opacity: 0.8 }}>{profile.stack.compatibility}</div>
                </div>
              )}
            </div>
          )}

          {/* Contacts */}
          {profile.contacts?.length > 0 && (
            <div style={{ background: '#161b27', border: '1px solid #30363d', borderRadius: 12, overflow: 'hidden', marginBottom: 20 }}>
              <div style={{ padding: '14px 18px', borderBottom: '1px solid #30363d', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 14 }}>👤</span>
                <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e' }}>Key Contacts</span>
              </div>
              <div style={{ padding: '4px 18px' }}>
                {profile.contacts.map((c, i) => (
                  <div key={i} style={{ display: 'flex', gap: 14, padding: '14px 0', borderBottom: i < profile.contacts.length - 1 ? '1px solid #30363d' : 'none' }}>
                    <div style={{ width: 38, height: 38, borderRadius: '50%', background: 'linear-gradient(135deg, #1f6feb, #58a6ff)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 800, color: '#fff', flexShrink: 0 }}>{c.initials || initials(c.name)}</div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700 }}>{c.name}</div>
                      <div style={{ fontSize: 11, color: '#8b949e', marginBottom: 4 }}>{c.title}</div>
                      <div style={{ fontSize: 12, color: '#79c0ff', lineHeight: 1.5, fontStyle: 'italic' }}>{c.angle}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Opening Pitch */}
          {profile.opening_pitch && (
            <div style={{ background: '#161b27', border: '1px solid #30363d', borderRadius: 12, overflow: 'hidden', marginBottom: 20 }}>
              <div style={{ padding: '14px 18px', borderBottom: '1px solid #30363d', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 14 }}>💬</span>
                <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e' }}>Your Opening Pitch</span>
              </div>
              <div style={{ padding: 18 }}>
                <div style={{ background: 'linear-gradient(135deg, rgba(88,166,255,0.08), rgba(88,166,255,0.03))', border: '1px solid rgba(88,166,255,0.25)', borderRadius: 10, padding: 16 }}>
                  <p style={{ fontSize: 13, color: '#8b949e', lineHeight: 1.7 }}>{profile.opening_pitch}</p>
                </div>
              </div>
            </div>
          )}

          {/* Sources */}
          {profile.sources?.length > 0 && (
            <div style={{ background: '#161b27', border: '1px solid #30363d', borderRadius: 12, overflow: 'hidden' }}>
              <div style={{ padding: '14px 18px', borderBottom: '1px solid #30363d', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 14 }}>🔗</span>
                <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#8b949e' }}>Sources</span>
              </div>
              <div style={{ padding: '4px 18px' }}>
                {profile.sources.map((s, i) => (
                  <div key={i} style={{ padding: '10px 0', borderBottom: i < profile.sources.length - 1 ? '1px solid #30363d' : 'none' }}>
                    <a href={s.url} target="_blank" rel="noopener noreferrer" style={{ color: '#58a6ff', textDecoration: 'none', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 11, opacity: 0.6 }}>↗</span> {s.label}
                    </a>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div style={{ textAlign: 'center', padding: 24, color: '#8b949e', fontSize: 12, borderTop: '1px solid #30363d', marginTop: 8 }}>
        Generated by <span style={{ color: '#58a6ff' }}>GTM Copilot Account Intelligence</span> · {profile.company || company} · {new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
      </div>
    </div>
  );
}

// ── Account Card ─────────────────────────────────────────────────────────────

function AccountCard({ account, onSelect, isSelected }) {
  return (
    <div
      onClick={() => onSelect(account)}
      style={{
        background: isSelected ? 'var(--bg-2)' : 'var(--surface)',
        border: `1px solid ${isSelected ? 'var(--accent, #58a6ff)' : 'var(--border)'}`,
        borderRadius: 10,
        padding: '1rem',
        cursor: 'pointer',
        transition: 'border-color 0.15s',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: 8, background: 'linear-gradient(135deg, #1f6feb, #58a6ff)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 800, color: '#fff', flexShrink: 0 }}>
            {initials(account.name)}
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.88rem', lineHeight: 1.2 }}>{account.name}</div>
            {account.lastStage && (
              <span style={{ fontSize: '0.68rem', fontWeight: 600, color: stageColor(account.lastStage) }}>{account.lastStage}</span>
            )}
          </div>
        </div>
        <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontWeight: 600 }}>{account.callCount} call{account.callCount !== 1 ? 's' : ''}</div>
          <div>{formatDate(account.lastCallDate)}</div>
        </div>
      </div>

      {account.contacts.length > 0 && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginTop: 6 }}>
          {account.contacts.slice(0, 2).join(', ')}{account.contacts.length > 2 ? ` +${account.contacts.length - 2}` : ''}
        </div>
      )}
    </div>
  );
}

// ── Account Detail Panel ─────────────────────────────────────────────────────

function AccountDetail({ account, onGenerate, generating }) {
  if (!account) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-3)', gap: 12 }}>
        <div style={{ fontSize: 32 }}>◎</div>
        <div style={{ fontSize: '0.85rem' }}>Select an account to view details</div>
      </div>
    );
  }

  return (
    <div style={{ padding: '1.25rem', overflowY: 'auto', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: '1rem' }}>
        <div style={{ width: 48, height: 48, borderRadius: 12, background: 'linear-gradient(135deg, #1f6feb, #58a6ff)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, fontWeight: 900, color: '#fff' }}>
          {initials(account.name)}
        </div>
        <div>
          <div style={{ fontWeight: 800, fontSize: '1.1rem' }}>{account.name}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>{account.callCount} calls · last {formatDate(account.lastCallDate)}</div>
        </div>
      </div>

      {/* Stage */}
      {account.lastStage && (
        <div style={{ marginBottom: '0.75rem' }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-3)', marginBottom: 4 }}>Deal Stage</div>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: stageColor(account.lastStage), background: `${stageColor(account.lastStage)}18`, border: `1px solid ${stageColor(account.lastStage)}40`, padding: '3px 10px', borderRadius: 20 }}>{account.lastStage}</span>
        </div>
      )}

      {/* Contacts */}
      {account.contacts.length > 0 && (
        <div style={{ marginBottom: '0.75rem' }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-3)', marginBottom: 6 }}>Known Contacts</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {account.contacts.slice(0, 6).map((c, i) => (
              <div key={i} style={{ fontSize: '0.78rem', color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 22, height: 22, borderRadius: '50%', background: 'linear-gradient(135deg, #1f6feb, #58a6ff)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 9, fontWeight: 800, color: '#fff', flexShrink: 0 }}>{initials(c)}</div>
                {c}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Reps */}
      {account.reps.length > 0 && (
        <div style={{ marginBottom: '0.75rem' }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-3)', marginBottom: 4 }}>Team</div>
          <div style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>{account.reps.join(', ')}</div>
        </div>
      )}

      {/* Call Summaries */}
      {account.summaries.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <div style={{ fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-3)', marginBottom: 6 }}>Recent Call Notes</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {account.summaries.slice(0, 3).map((s, i) => (
              <div key={i} style={{ background: 'var(--bg-2)', borderRadius: 6, padding: '0.5rem 0.75rem', fontSize: '0.75rem', color: 'var(--text-2)', lineHeight: 1.5, borderLeft: '2px solid var(--border)' }}>
                {s}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Generate button */}
      <button
        onClick={() => onGenerate(account)}
        disabled={generating}
        style={{
          width: '100%',
          padding: '0.65rem',
          background: generating ? 'var(--bg-2)' : 'linear-gradient(135deg, #1f6feb, #388bfd)',
          color: generating ? 'var(--text-3)' : '#fff',
          border: 'none',
          borderRadius: 8,
          fontWeight: 700,
          fontSize: '0.85rem',
          cursor: generating ? 'not-allowed' : 'pointer',
          letterSpacing: '0.02em',
        }}
      >
        {generating ? '⏳ Generating TiDB Profile…' : '◎ Generate TiDB Intelligence Profile'}
      </button>
      {generating && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', textAlign: 'center', marginTop: 8 }}>
          Researching {account.name} · analyzing tech stack · scoring TiDB fit…
        </div>
      )}
    </div>
  );
}

// ── Main Dashboard Component ─────────────────────────────────────────────────

export default function AccountIntelligenceClient({ accounts }) {
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [profile, setProfile] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  const filtered = useMemo(() => {
    if (!search.trim()) return accounts;
    const q = search.toLowerCase();
    return accounts.filter(a => a.name.toLowerCase().includes(q));
  }, [accounts, search]);

  const handleGenerate = async (account) => {
    setGenerating(true);
    setError('');
    setProfile(null);
    try {
      const res = await fetch('/api/account-intelligence/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company: account.name,
          callSummaries: account.summaries,
          callCount: account.callCount,
          contacts: account.contacts,
          lastStage: account.lastStage,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || 'Generation failed');
      setProfile(data.profile);
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <>
      {/* Full-page profile overlay */}
      {profile && (
        <ProfileView
          profile={profile}
          company={selected?.name || ''}
          onClose={() => setProfile(null)}
        />
      )}

      <div style={{ display: 'flex', height: 'calc(100vh - 56px)' }}>
        {/* Account list */}
        <div style={{ width: 280, borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
          <div style={{ padding: '0.75rem', borderBottom: '1px solid var(--border)' }}>
            <input
              type="text"
              className="input"
              placeholder="Search accounts…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ width: '100%', fontSize: '0.8rem' }}
            />
          </div>
          <div style={{ overflowY: 'auto', flex: 1, padding: '0.5rem' }}>
            {filtered.length === 0 ? (
              <div style={{ fontSize: '0.78rem', color: 'var(--text-3)', textAlign: 'center', padding: '2rem 1rem' }}>
                {accounts.length === 0 ? 'No call data yet.\nSync Chorus calls to populate accounts.' : 'No accounts match your search.'}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                {filtered.map(a => (
                  <AccountCard
                    key={a.name}
                    account={a}
                    onSelect={acc => { setSelected(acc); setProfile(null); setError(''); }}
                    isSelected={selected?.name === a.name}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Detail pane */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          {error && (
            <div style={{ margin: '1rem', padding: '0.75rem 1rem', background: 'rgba(248,81,73,0.1)', border: '1px solid rgba(248,81,73,0.3)', borderRadius: 8, fontSize: '0.8rem', color: '#f85149' }}>
              ⚠ {error}
            </div>
          )}
          <AccountDetail
            account={selected}
            onGenerate={handleGenerate}
            generating={generating}
          />
        </div>
      </div>
    </>
  );
}
