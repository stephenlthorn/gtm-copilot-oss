import { getSession } from '../../../lib/session';
import { apiGet } from '../../../lib/api';

// Shared
import KBConfigPanel from '../../../components/KBConfigPanel';

// Account & auth
import OpenAIKeyPanel from '../../../components/OpenAIKeyPanel';
import ExternalAccountsPanel from '../../../components/ExternalAccountsPanel';

// Data sources
import GoogleDrivePanel from '../../../components/GoogleDrivePanel';
import FeishuPanel from '../../../components/FeishuPanel';
import ChorusCallsPanel from '../../../components/admin/ChorusCallsPanel';

// Integrations
import CalendarScanPanel from '../../../components/CalendarScanPanel';
import SlackNotificationsPanel from '../../../components/SlackNotificationsPanel';

// Persona & features
import PersonaPromptPanel from '../../../components/PersonaPromptPanel';
import GTMFeaturePanel from '../../../components/GTMFeaturePanel';
import AiCoachingPanel from '../../../components/admin/AiCoachingPanel';

// Knowledge base
import KnowledgeSourcesPanel from '../../../components/KnowledgeSourcesPanel';
import SourceRegistryPanel from '../../../components/admin/SourceRegistryPanel';
import SyncStatusPanel from '../../../components/admin/SyncStatusPanel';
import IndexHealthPanel from '../../../components/admin/IndexHealthPanel';
import KBBrowserPanel from '../../../components/admin/KBBrowserPanel';

// System
import UserManagementPanel from '../../../components/admin/UserManagementPanel';
import ApiKeyManagementPanel from '../../../components/admin/ApiKeyManagementPanel';
import McpServersPanel from '../../../components/admin/McpServersPanel';
import NotificationDefaultsPanel from '../../../components/admin/NotificationDefaultsPanel';
import TiDBConfigPanel from '../../../components/admin/TiDBConfigPanel';

function SectionHeader({ title }) {
  return (
    <div style={{
      fontSize: '0.7rem',
      fontWeight: 600,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      color: 'var(--text-3)',
      padding: '0.25rem 0',
      borderBottom: '1px solid var(--border)',
      marginTop: '0.5rem',
    }}>
      {title}
    </div>
  );
}

export default async function SettingsPage() {
  const session = await getSession();
  const hasSession = Boolean(session?.access_token);
  const expiresIn = session?.expires_at
    ? Math.max(0, Math.round((session.expires_at - Date.now()) / 1000 / 60))
    : 0;

  const [docsRaw, auditsRaw, callsRaw, cfg] = await Promise.all([
    apiGet('/kb/documents?limit=300').catch(() => []),
    apiGet('/admin/audit?limit=30').catch(() => []),
    apiGet('/calls?limit=300').catch(() => []),
    apiGet('/admin/kb-config').catch(() => ({})),
  ]);

  const docs = docsRaw || [];
  const audits = auditsRaw || [];
  const calls = callsRaw || [];
  const liveMode = docs.length > 0 || audits.length > 0 || calls.length > 0;

  const personaName = cfg?.persona_name || 'sales_representative';
  const personaPrompt = cfg?.persona_prompt || '';
  const sePocKitUrl = cfg?.se_poc_kit_url || '';
  const featureFlags = cfg?.feature_flags_json || {};

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar-title">Settings</div>
          <div className="topbar-meta">Account · AI · data sources · system</div>
        </div>
        <div className="topbar-right">
          <span className={`tag ${liveMode ? 'tag-green' : ''}`}>
            {liveMode ? 'Live data' : 'No data indexed'}
          </span>
        </div>
      </div>

      <div className="content">

        {/* ── Account ─────────────────────────────────────────── */}
        <SectionHeader title="Account" />

        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">ChatGPT Session</span>
            <span className={`tag ${hasSession ? 'tag-green' : ''}`}>
              {hasSession ? 'Connected' : 'Not connected'}
            </span>
          </div>
          <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '0.5rem 1rem', fontSize: '0.82rem' }}>
              <span style={{ color: 'var(--text-3)' }}>Email</span>
              <span>{session?.email || '—'}</span>
              <span style={{ color: 'var(--text-3)' }}>Name</span>
              <span>{session?.name || '—'}</span>
              <span style={{ color: 'var(--text-3)' }}>Token expires</span>
              <span style={{ color: expiresIn < 10 ? 'var(--danger)' : 'var(--success)' }}>
                {expiresIn > 0 ? `~${expiresIn} min` : 'Expired'}
              </span>
              <span style={{ color: 'var(--text-3)' }}>Auth method</span>
              <span>{hasSession ? 'ChatGPT OAuth PKCE' : 'None'}</span>
            </div>
            {hasSession ? (
              <form action="/api/auth/logout" method="POST" style={{ marginTop: '0.25rem' }}>
                <button type="submit" className="btn btn-danger">Sign out</button>
              </form>
            ) : (
              <a href="/login" className="btn btn-primary" style={{ display: 'inline-block', width: 'fit-content' }}>
                Login with ChatGPT
              </a>
            )}
          </div>
        </div>

        <OpenAIKeyPanel />
        <ExternalAccountsPanel />

        {/* ── AI & Model ──────────────────────────────────────── */}
        <SectionHeader title="AI & Model" />
        <KBConfigPanel />

        {/* ── Data Sources ────────────────────────────────────── */}
        <SectionHeader title="Data Sources" />
        <GoogleDrivePanel />
        <FeishuPanel />
        <ChorusCallsPanel />

        {/* ── Integrations ────────────────────────────────────── */}
        <SectionHeader title="Integrations" />
        <CalendarScanPanel />
        <SlackNotificationsPanel />

        {/* ── Persona & Coaching ──────────────────────────────── */}
        <SectionHeader title="Persona & Coaching" />
        <PersonaPromptPanel initialPersona={personaName} initialPrompt={personaPrompt} />
        <AiCoachingPanel />
        <GTMFeaturePanel initialPocKitUrl={sePocKitUrl} initialFeatureFlags={featureFlags} />

        {/* ── Knowledge Base ──────────────────────────────────── */}
        <SectionHeader title="Knowledge Base" />

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

        <KBBrowserPanel />
        <SourceRegistryPanel />
        <SyncStatusPanel />
        <IndexHealthPanel />

        {/* ── System ──────────────────────────────────────────── */}
        <SectionHeader title="System" />
        <UserManagementPanel />
        <ApiKeyManagementPanel />
        <McpServersPanel />
        <NotificationDefaultsPanel />
        <TiDBConfigPanel />

        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Guardrails</span>
          </div>
          <div className="panel-body" style={{ display: 'grid', gap: '0.5rem', fontSize: '0.82rem' }}>
            {[
              { label: 'Internal-only messaging', value: 'Enabled — allowlist enforced by INTERNAL_DOMAIN_ALLOWLIST' },
              { label: 'Audit logging', value: 'All generation events logged' },
              { label: 'Email mode', value: 'Draft (no auto-send)' },
            ].map(({ label, value }) => (
              <div key={label} style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '0.5rem' }}>
                <span style={{ color: 'var(--text-3)' }}>{label}</span>
                <span style={{ color: 'var(--success)' }}>✓ {value}</span>
              </div>
            ))}
          </div>
        </div>

      </div>
    </>
  );
}
