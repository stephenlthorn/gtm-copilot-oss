import { apiGet } from '../../../lib/api';
import KBConfigPanel from '../../../components/KBConfigPanel';
import KnowledgeSourcesPanel from '../../../components/KnowledgeSourcesPanel';

export default async function AdminPage() {
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
          <div className="topbar-title">Admin</div>
          <div className="topbar-meta">Data coverage · audit log · sync status</div>
        </div>
        <div className="topbar-right">
          <span className={`tag ${liveMode ? 'tag-green' : ''}`}>{liveMode ? 'Live data' : 'No data indexed yet'}</span>
        </div>
      </div>

      <div className="content">
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

        <KBConfigPanel />

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
                      <span className={`tag ${a.status === 'ok' ? 'tag-green' : 'tag-red'}`}>
                        {a.status}
                      </span>
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
      </div>
    </>
  );
}
