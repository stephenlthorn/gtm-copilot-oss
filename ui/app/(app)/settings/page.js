import Link from 'next/link';
import { getSession } from '../../../lib/session';
import { apiGet } from '../../../lib/api';
import GTMFeaturePanel from '../../../components/GTMFeaturePanel';
import KnowledgeSourcesPanel from '../../../components/KnowledgeSourcesPanel';
import CallsPanel from '../../../components/CallsPanel';
import SourceProfilesPanel from '../../../components/SourceProfilesPanel';
import PromptStudio from '../../../components/PromptStudio';
import IntelBriefSettingsPanel from '../../../components/IntelBriefSettingsPanel';
import ExternalAccountsPanel from '../../../components/ExternalAccountsPanel';
import FeishuPanel from '../../../components/FeishuPanel';

const NAV = [
  ['#account', 'Account'],
  ['#connections', 'Connections'],
  ['#knowledge', 'Knowledge'],
  ['#ai', 'AI Behavior'],
  ['#prompts', 'Prompt Studio'],
  ['#data', 'Data'],
];

const SectionLabel = ({ id, children, first = false }) => (
  <div
    id={id}
    style={{
      fontSize: '0.7rem',
      fontWeight: 600,
      letterSpacing: '0.07em',
      textTransform: 'uppercase',
      color: 'var(--text-3)',
      margin: first ? '0 0 0.5rem' : '1.75rem 0 0.5rem',
      scrollMarginTop: '1rem',
    }}
  >
    {children}
  </div>
);

export default async function SettingsPage() {
  const session = await getSession();
  const hasSession = Boolean(session?.access_token);

  const expiresIn = session?.expires_at
    ? Math.max(0, Math.round((session.expires_at - Date.now()) / 1000 / 60))
    : 0;

  let sePocKitUrl = '';
  let featureFlags = {};
  let sourceProfiles = {};
  try {
    const cfg = await apiGet('/admin/kb-config');
    if (cfg?.se_poc_kit_url) sePocKitUrl = cfg.se_poc_kit_url;
    if (cfg?.feature_flags_json && typeof cfg.feature_flags_json === 'object') featureFlags = cfg.feature_flags_json;
    if (cfg?.source_profiles_json && typeof cfg.source_profiles_json === 'object') sourceProfiles = cfg.source_profiles_json;
  } catch { /* use defaults */ }

  const [docsRaw, allDocsRaw, auditsRaw, callsRaw, tidbExpertPrompt] = await Promise.all([
    apiGet('/kb/documents?limit=300').catch(() => []),
    apiGet('/kb/documents?limit=5000').catch(() => []),
    apiGet('/admin/audit?limit=30').catch(() => []),
    apiGet('/calls?limit=1000').catch(() => []),
    apiGet('/prompts/tidb_expert').catch(() => null),
  ]);

  const docsCount = Array.isArray(docsRaw) ? docsRaw.length : (docsRaw?.count ?? 0);
  const docs = docsRaw || [];
  const allDocs = allDocsRaw || docs;
  const audits = auditsRaw || [];
  const calls = callsRaw || [];

  const driveCount = allDocs.filter(d => d.source_type === 'google_drive').length;
  const chorusCount = allDocs.filter(d => d.source_type === 'chorus').length;

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar-title">Settings</div>
          <div className="topbar-meta">Account · knowledge · AI behavior · data</div>
        </div>
        <Link href="/chat" style={{ fontSize: '0.78rem', color: 'var(--text-2)', padding: '0.3rem 0.6rem', borderRadius: '4px', textDecoration: 'none', border: '1px solid var(--border)' }}>
          ← Back to Chat
        </Link>
      </div>

      {/* Jump nav */}
      <div style={{
        display: 'flex',
        gap: '0.25rem',
        padding: '0.5rem 1.5rem',
        borderBottom: '1px solid var(--border)',
        backgroundColor: 'var(--bg)',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}>
        {NAV.map(([href, label]) => (
          <a key={href} href={href} className="settings-nav-link">{label}</a>
        ))}
      </div>

      <div className="content">

        {/* ── Account ──────────────────────────────────────── */}
        <SectionLabel id="account" first>Account</SectionLabel>

        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">ChatGPT</span>
            <span className={`tag ${hasSession ? 'tag-green' : ''}`}>{hasSession ? 'Connected' : 'Not connected'}</span>
          </div>
          <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '0.35rem 1rem', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-3)' }}>Email</span>
              <span>{session?.email || '—'}</span>
              <span style={{ color: 'var(--text-3)' }}>Token expires</span>
              <span style={{ color: expiresIn < 10 ? 'var(--danger)' : 'var(--success)' }}>
                {expiresIn > 0 ? `~${expiresIn} min` : 'Expired'}
              </span>
            </div>
            <div>
              {hasSession ? (
                <form action="/api/auth/logout" method="POST">
                  <button type="submit" className="btn btn-danger">Sign out</button>
                </form>
              ) : (
                <a href="/login" className="btn btn-primary" style={{ display: 'inline-block', width: 'fit-content' }}>Login with ChatGPT</a>
              )}
            </div>
          </div>
        </div>

        {/* ── External Connections ─────────────────────────── */}
        <SectionLabel id="connections">External Connections</SectionLabel>
        <ExternalAccountsPanel />

        {/* ── Knowledge Sources ─────────────────────────────── */}
        <SectionLabel id="knowledge">Knowledge Sources</SectionLabel>

        <CallsPanel />
        <FeishuPanel />

        {/* ── AI Behavior ───────────────────────────────────── */}
        <SectionLabel id="ai">AI Behavior</SectionLabel>

        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Intelligence Search Profiles</span>
          </div>
          <div className="panel-body">
            <SourceProfilesPanel initialProfiles={sourceProfiles} />
          </div>
        </div>

        {/* TiDB Expert Mode panel */}
        <div className="panel" style={{ marginTop: '0.75rem' }}>
          <div className="panel-header">
            <span className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ color: '#7c3aed' }}>◎</span> TiDB Expert Mode
            </span>
            <span className="tag" style={{ background: '#7c3aed15', color: '#7c3aed', border: '1px solid #7c3aed30' }}>Auto</span>
          </div>
          <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-2)', lineHeight: 1.5 }}>
              TiDB Expert mode injects a comprehensive technical context block into every AI response, covering TiDB architecture, migration paths, and competitive differentiators. It is <strong>automatically activated</strong> when you switch to an SE section and deactivated for sales sections.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.78rem' }}>
              <div style={{ padding: '0.5rem 0.75rem', borderRadius: '6px', background: '#7c3aed10', border: '1px solid #7c3aed25' }}>
                <div style={{ fontWeight: 600, color: '#7c3aed', marginBottom: '0.3rem', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Auto-On (SE sections)</div>
                <div style={{ color: 'var(--text-2)', lineHeight: 1.5 }}>SE: POC Plan<br />SE: Architecture Fit<br />SE: Competitor Coach</div>
              </div>
              <div style={{ padding: '0.5rem 0.75rem', borderRadius: '6px', background: 'var(--bg-2)', border: '1px solid var(--border)' }}>
                <div style={{ fontWeight: 600, color: 'var(--text-2)', marginBottom: '0.3rem', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Off (Sales sections)</div>
                <div style={{ color: 'var(--text-3)', lineHeight: 1.5 }}>Pre-Call Intel<br />Post-Call Analysis<br />Follow-Up / TAL</div>
              </div>
            </div>

            <details>
              <summary style={{ fontSize: '0.75rem', color: 'var(--text-3)', cursor: 'pointer', padding: '0.2rem 0', listStyle: 'none', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <span style={{ fontSize: '0.65rem' }}>▶</span> View injected expert context
              </summary>
              <pre style={{
                marginTop: '0.6rem', padding: '0.75rem', borderRadius: '6px',
                background: 'var(--bg-2)', border: '1px solid var(--border)',
                fontSize: '0.72rem', lineHeight: 1.6, whiteSpace: 'pre-wrap',
                color: 'var(--text-2)', overflowY: 'auto', maxHeight: '340px',
              }}>{tidbExpertPrompt?.current_content || tidbExpertPrompt?.default_content || 'Loading...'}</pre>
            </details>
          </div>
        </div>

        {/* Intelligence Brief panel */}
        <div className="panel" style={{ marginTop: '0.75rem' }}>
          <div className="panel-header">
            <span className="panel-title">Intelligence Brief</span>
            <span className="tag">Pre-Call Intel</span>
          </div>
          <div className="panel-body">
            <IntelBriefSettingsPanel />
          </div>
        </div>

        <details style={{ marginTop: '0.5rem' }}>
          <summary style={{
            fontSize: '0.78rem',
            color: 'var(--text-3)',
            cursor: 'pointer',
            padding: '0.4rem 0',
            listStyle: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
          }}>
            <span style={{ fontSize: '0.7rem' }}>▶</span>
            Advanced / Developer Settings
          </summary>
          <div style={{ marginTop: '0.5rem' }}>
            <GTMFeaturePanel initialPocKitUrl={sePocKitUrl} initialFeatureFlags={featureFlags} />
          </div>
        </details>

        {/* ── Prompt Studio ─────────────────────────────────── */}
        <SectionLabel id="prompts">Prompt Studio</SectionLabel>

        <PromptStudio />

        {/* ── Data ─────────────────────────────────────────── */}
        <SectionLabel id="data">Data</SectionLabel>

        <div className="kpi-row">
          {[
            { label: 'Drive Docs', value: driveCount, sub: 'Google Drive indexed' },
            { label: 'Call Transcripts', value: chorusCount, sub: `${calls.length} calls total` },
            { label: 'Audit Events', value: audits.length, sub: 'Last 30 days' },
          ].map((k) => (
            <div className="kpi-card" key={k.label}>
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value">{k.value}</div>
              <div className="kpi-sub">{k.sub}</div>
            </div>
          ))}
        </div>

        <div className="two-col">
          <KnowledgeSourcesPanel docs={docs} />

          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Audit Log</span>
            </div>
            <table className="data-table">
              <thead>
                <tr><th>Action</th><th>Actor</th><th>Status</th><th>Time</th></tr>
              </thead>
              <tbody>
                {audits.slice(0, 10).map((a) => (
                  <tr key={a.id}>
                    <td className="row-title">{a.action}</td>
                    <td style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>{a.actor || a.actor_email || '—'}</td>
                    <td>
                      <span className={`tag ${a.status === 'ok' ? 'tag-green' : 'tag-red'}`}>{a.status}</span>
                    </td>
                    <td style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>
                      {new Date(a.ts || a.timestamp || 0).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div style={{ marginTop: '2rem', paddingTop: '1rem', borderTop: '1px solid var(--border)', display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '0.74rem', color: 'var(--text-3)' }}>
          {['Internal-only messaging enforced', 'All generation events audit-logged', 'Email: draft only, no auto-send'].map(item => (
            <span key={item}><span style={{ color: 'var(--success)', marginRight: '0.3rem' }}>✓</span>{item}</span>
          ))}
        </div>

      </div>
    </>
  );
}
