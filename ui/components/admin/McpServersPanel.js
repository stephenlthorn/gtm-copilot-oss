'use client';

import { useState, useEffect } from 'react';

const MCP_SERVERS = [
  'TiDB', 'Salesforce', 'Slack', 'Google Drive',
  'Gmail', 'Calendar', 'ZoomInfo', 'LinkedIn', 'Firecrawl', 'GitHub', 'Crunchbase',
];

export default function McpServersPanel() {
  const [servers, setServers] = useState({});
  const [expanded, setExpanded] = useState({});
  const [apiKeys, setApiKeys] = useState({});
  const [saving, setSaving] = useState({});
  const [messages, setMessages] = useState({});
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const res = await fetch('/api/admin/mcp-servers');
      if (!res.ok) throw new Error('Failed');
      const data = await res.json();
      const map = {};
      const initial = {};
      const servers = Array.isArray(data) ? data : data.servers || [];
      for (const s of servers) {
        map[s.name] = s;
        initial[s.name] = s.api_key || '';
      }
      setServers(map);
      setApiKeys(initial);
    } catch {
      // leave defaults
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const toggleEnabled = async (name) => {
    const current = servers[name]?.enabled ?? false;
    setSaving(prev => ({ ...prev, [name]: true }));
    setMessages(prev => ({ ...prev, [name]: '' }));
    try {
      const res = await fetch(`/api/admin/mcp-servers/${encodeURIComponent(name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !current }),
      });
      if (!res.ok) throw new Error('Failed');
      setServers(prev => ({ ...prev, [name]: { ...(prev[name] || { name }), enabled: !current } }));
    } catch {
      setMessages(prev => ({ ...prev, [name]: 'Failed' }));
    } finally {
      setSaving(prev => ({ ...prev, [name]: false }));
    }
  };

  const saveKey = async (name) => {
    setSaving(prev => ({ ...prev, [`${name}_key`]: true }));
    setMessages(prev => ({ ...prev, [name]: '' }));
    try {
      const res = await fetch(`/api/admin/mcp-servers/${encodeURIComponent(name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKeys[name] }),
      });
      if (!res.ok) throw new Error('Failed');
      setServers(prev => ({ ...prev, [name]: { ...(prev[name] || { name }), api_key: apiKeys[name] } }));
      setMessages(prev => ({ ...prev, [name]: 'Saved' }));
    } catch {
      setMessages(prev => ({ ...prev, [name]: 'Failed' }));
    } finally {
      setSaving(prev => ({ ...prev, [`${name}_key`]: false }));
    }
  };

  const toggleExpand = (name) => setExpanded(prev => ({ ...prev, [name]: !prev[name] }));

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">MCP Server Configuration</span>
      </div>
      <div className="panel-body">
        {loading ? (
          <div className="status-row">Loading…</div>
        ) : (
          <div style={{ display: 'grid', gap: '0.5rem' }}>
            {MCP_SERVERS.map(name => {
              const srv = servers[name] || { name, enabled: false };
              const isExpanded = expanded[name];
              const hasKey = !!srv.api_key;
              return (
                <div key={name} style={{ border: '1px solid var(--border)', borderRadius: '4px', background: 'var(--bg)' }}>
                  <div
                    style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem 0.75rem', cursor: 'pointer' }}
                    onClick={() => toggleExpand(name)}
                  >
                    <label
                      style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer' }}
                      onClick={e => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={!!srv.enabled}
                        onChange={() => toggleEnabled(name)}
                        disabled={saving[name]}
                      />
                    </label>
                    <span style={{ fontWeight: 600, fontSize: '0.82rem', color: srv.enabled ? 'var(--text)' : 'var(--text-3)', flex: 1 }}>
                      {name}
                    </span>
                    {hasKey && <span className="tag tag-green">key set</span>}
                    {messages[name] && (
                      <span style={{ fontSize: '0.72rem', color: messages[name] === 'Saved' ? 'var(--success)' : 'var(--danger)' }}>
                        {messages[name]}
                      </span>
                    )}
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>{isExpanded ? '▲' : '▼'}</span>
                  </div>

                  {isExpanded && (
                    <div style={{ padding: '0 0.75rem 0.75rem', borderTop: '1px solid var(--border)', marginTop: '0px', paddingTop: '0.6rem' }}>
                      <label style={{ fontSize: '0.72rem', color: 'var(--text-3)', display: 'block', marginBottom: '0.3rem', textTransform: 'uppercase' }}>
                        API Key
                      </label>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <input
                          className="input"
                          type="password"
                          placeholder={hasKey ? 'Enter new key to replace…' : 'Enter API key…'}
                          value={apiKeys[name] || ''}
                          onChange={e => setApiKeys(prev => ({ ...prev, [name]: e.target.value }))}
                        />
                        <button
                          className="btn btn-primary"
                          onClick={() => saveKey(name)}
                          disabled={saving[`${name}_key`] || !apiKeys[name]}
                          style={{ whiteSpace: 'nowrap' }}
                        >
                          {saving[`${name}_key`] ? 'Saving…' : 'Save Key'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
