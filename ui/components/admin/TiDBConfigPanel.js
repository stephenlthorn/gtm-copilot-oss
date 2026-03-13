'use client';

import { useEffect, useState } from 'react';

export default function TiDBConfigPanel() {
  const [cfg, setCfg] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/admin/db-config')
      .then((r) => r.json())
      .then((data) => setCfg(data))
      .catch(() => setCfg(null))
      .finally(() => setLoading(false));
  }, []);

  const isTiDB = cfg?.database_provider === 'tidb';

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Database Configuration</span>
        {loading ? (
          <span className="tag">Loading</span>
        ) : (
          <span className={`tag ${isTiDB ? 'tag-green' : ''}`}>
            {cfg?.database_provider ?? '—'}
          </span>
        )}
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.5rem', fontSize: '0.82rem' }}>
        {cfg && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: '0.4rem 1rem' }}>
              <span style={{ color: 'var(--text-3)' }}>Provider</span>
              <span style={{ color: 'var(--text)' }}>{cfg.database_provider}</span>
              <span style={{ color: 'var(--text-3)' }}>Connected to</span>
              <span style={{ color: 'var(--text)', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                {cfg.database_url_preview}
              </span>
            </div>

            {isTiDB && (
              <>
                <hr style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '0.25rem 0' }} />
                <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: '0.4rem 1rem' }}>
                  {[
                    ['Host', cfg.tidb_host || '—'],
                    ['Port', cfg.tidb_port],
                    ['User', cfg.tidb_user || '—'],
                    ['Password', cfg.tidb_password || '—'],
                    ['Database', cfg.tidb_database],
                    ['SSL CA', cfg.tidb_ssl_ca || '(none)'],
                  ].map(([label, value]) => (
                    <>
                      <span key={`l-${label}`} style={{ color: 'var(--text-3)' }}>{label}</span>
                      <span key={`v-${label}`} style={{ color: 'var(--text)', fontFamily: 'monospace', fontSize: '0.75rem' }}>{value}</span>
                    </>
                  ))}
                </div>
              </>
            )}

            {!isTiDB && (
              <p style={{ color: 'var(--text-3)', fontSize: '0.78rem', marginTop: '0.25rem' }}>
                Using PostgreSQL. To switch to TiDB Cloud, set <code>DATABASE_PROVIDER=tidb</code> and
                configure <code>TIDB_HOST</code>, <code>TIDB_USER</code>, <code>TIDB_PASSWORD</code>,
                and <code>TIDB_DATABASE</code> in your <code>.env</code>, then restart the containers.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
