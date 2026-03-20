import { getSession } from '../../../lib/session';
import { apiGet } from '../../../lib/api';
import GoogleDrivePanel from '../../../components/GoogleDrivePanel';
import FeishuPanel from '../../../components/FeishuPanel';
import PersonaPromptPanel from '../../../components/PersonaPromptPanel';
import GTMFeaturePanel from '../../../components/GTMFeaturePanel';
import KBConfigPanel from '../../../components/KBConfigPanel';
import KnowledgeSourcesPanel from '../../../components/KnowledgeSourcesPanel';
import CallsPanel from '../../../components/CallsPanel';
import SourceProfilesPanel from '../../../components/SourceProfilesPanel';
import TemplatesPanel from '../../../components/TemplatesPanel';

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

  let liveModel = 'gpt-4o';
  let personaName = 'sales_representative';
  let personaPrompt = '';
  let sePocKitUrl = '';
  let featureFlags = {};
  let sourceProfiles = {};
  try {
    const cfg = await apiGet('/admin/kb-config');
    if (cfg?.llm_model) liveModel = cfg.llm_model;
    if (cfg?.persona_name) personaName = cfg.persona_name;
    if (cfg?.persona_prompt) personaPrompt = cfg.persona_prompt;
    if (cfg?.se_poc_kit_url) sePocKitUrl = cfg.se_poc_kit_url;
    if (cfg?.feature_flags_json && typeof cfg.feature_flags_json === 'object') featureFlags = cfg.feature_flags_json;
    if (cfg?.source_profiles_json && typeof cfg.source_profiles_json === 'object') sourceProfiles = cfg.source_profiles_json;
  } catch { /* use defaults */ }

  const [docsRaw, auditsRaw, callsRaw] = await Promise.all([
    apiGet('/kb/documents?limit=300').catch(() => []),
    apiGet('/admin/audit?limit=30').catch(() => []),
    apiGet('/calls?limit=300').catch(() => []),
  ]);

  const docs = docsRaw || [];
  const audits = auditsRaw || [];
  const calls = callsRaw || [];
  const liveMode = docs.length > 0 || audits.length > 0 || calls.length > 0;

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar-title">Settings</div>
          <div className="topbar-meta">Account · knowledge · AI · data</div>
        </div>
        <div className="topbar-right">
          <span className={`tag ${liveMode ? 'tag-green' : ''}`}>{liveMode ? 'Live data' : 'No data yet'}</span>
        </div>
      </div>

      {/* Section jump nav */}
      <div style={{
        display: 'flex',
        gap: '0.25rem',
        padding: '0.5rem 1.5rem',
        borderBottom: '1px solid var(--border)',
        backgroundColor: 'var(--bg)',
        position: 'sticky',
        top: 0,
        zIndex: 10,
        flexWrap: 'wrap',
      }}>
        {[
          ['#account', 'Account'],
          ['#knowledge', 'Knowledge & Integrations'],
          ['#model', 'Model & Retrieval'],
          ['#persona', 'AI Persona'],
          ['#templates', 'Templates'],
          ['#data', 'Data & Sync'],
          ['#system', 'System'],
        ].map(([href, label]) => (
          <a key={href} href={href} className="settings-nav-link">{label}</a>
        ))}
      </div>

      <div className="content">

        {/* ── Account ─────────────────────────────── */}
        <SectionLabel id="account" first>Account</SectionLabel>

        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">ChatGPT Account</span>
            <span className={`tag ${hasSession ? 'tag-green' : ''}`}>{hasSession ? 'Connected' : 'Not connected'}</span>
          </div>
          <div className="panel-body" style={{ display: 'grid', gap: '0.5rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '130px 1fr', gap: '0.35rem 1rem', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-3)' }}>Email</span>
              <span>{session?.email || '—'}</span>
              <span style={{ color: 'var(--text-3)' }}>Token expires</span>
              <span style={{ color: expiresIn < 10 ? 'var(--danger)' : 'var(--success)' }}>
                {expiresIn > 0 ? `~${expiresIn} min` : 'Expired'}
              </span>
              <span style={{ color: 'var(--text-3)' }}>LLM model</span>
              <span>{liveModel}</span>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
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

        {/* ── Knowledge Sources ───────────────────── */}
        <SectionLabel id="knowledge">Knowledge Sources</SectionLabel>
        <GoogleDrivePanel />
        <FeishuPanel />
        <CallsPanel />

        {/* ── Model & Retrieval ────────────────────── */}
        <SectionLabel id="model">Model &amp; Retrieval</SectionLabel>
        <KBConfigPanel />

        {/* ── AI Persona ───────────────────────────── */}
        <SectionLabel id="persona">AI Persona</SectionLabel>
        <PersonaPromptPanel initialPersona={personaName} initialPrompt={personaPrompt} />
        <GTMFeaturePanel initialPocKitUrl={sePocKitUrl} initialFeatureFlags={featureFlags} />
        <SourceProfilesPanel initialProfiles={sourceProfiles} />

        {/* ── Templates ────────────────────────────── */}
        <SectionLabel id="templates">Templates</SectionLabel>
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Prompt Templates</span>
          </div>
          <div className="panel-body">
            <TemplatesPanel />
          </div>
        </div>

        {/* ── Data & Sync ──────────────────────────── */}
        <SectionLabel id="data">Data &amp; Sync</SectionLabel>

        <div className="kpi-row">
          {[
            { label: 'Docs Indexed', value: docs.length, sub: docs[0]?.title || '—' },
            { label: 'Calls Indexed', value: calls.length, sub: calls[0]?.account || '—' },
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

        {/* ── System ──────────────────────────────── */}
        <SectionLabel id="system">System</SectionLabel>

        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Guardrails</span>
          </div>
          <div className="panel-body" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem 1.5rem', fontSize: '0.78rem' }}>
            {[
              'Internal-only messaging (domain allowlist)',
              'All generation events audit-logged',
              'Email mode: draft only, no auto-send',
            ].map((item) => (
              <span key={item} style={{ color: 'var(--text-2)' }}>
                <span style={{ color: 'var(--success)', marginRight: '0.3rem' }}>✓</span>{item}
              </span>
            ))}
          </div>
        </div>

      </div>
    </>
  );
}
