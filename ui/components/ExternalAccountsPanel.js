'use client';

import { useEffect, useState } from 'react';

const PROVIDERS = [
  { id: 'salesforce', label: 'Salesforce', type: 'oauth' },
  { id: 'zoominfo', label: 'ZoomInfo', type: 'api_key' },
  { id: 'linkedin', label: 'LinkedIn', type: 'api_key' },
  { id: 'chorus', label: 'Chorus', type: 'api_key', hasBaseUrl: true },
];

function ProviderRow({ provider, initialConnected }) {
  const [connected, setConnected] = useState(initialConnected);
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [showInput, setShowInput] = useState(false);
  const [working, setWorking] = useState(false);
  const [message, setMessage] = useState('');

  const connectOAuth = () => {
    window.location.href = `/api/auth/connect/${provider.id}`;
  };

  const connectApiKey = async () => {
    if (!apiKey.trim()) {
      setMessage('Please enter an API key.');
      return;
    }
    if (provider.hasBaseUrl && !baseUrl.trim()) {
      setMessage('Please enter the API base URL.');
      return;
    }
    setWorking(true);
    setMessage('');
    const payload = { access_token: apiKey.trim() };
    if (provider.hasBaseUrl) payload.base_url = baseUrl.trim();
    try {
      const res = await fetch(`/api/auth/connect/${provider.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || data?.error || `Failed to connect ${provider.label}.`);
      setConnected(true);
      setApiKey('');
      setShowInput(false);
      setMessage('Connected.');
    } catch (err) {
      setMessage(String(err?.message || err));
    } finally {
      setWorking(false);
    }
  };

  const disconnect = async () => {
    setWorking(true);
    setMessage('');
    try {
      const res = await fetch(`/api/auth/connect/${provider.id}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || data?.error || `Failed to disconnect ${provider.label}.`);
      setConnected(false);
      setShowInput(false);
      setMessage('Disconnected.');
    } catch (err) {
      setMessage(String(err?.message || err));
    } finally {
      setWorking(false);
    }
  };

  return (
    <div
      style={{
        display: 'grid',
        gap: '0.4rem',
        paddingBottom: '0.75rem',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <span style={{ fontSize: '0.83rem', color: 'var(--text)', minWidth: '100px' }}>
          {provider.label}
        </span>
        <span className={`tag ${connected ? 'tag-green' : ''}`} style={{ minWidth: '90px', textAlign: 'center' }}>
          {connected ? 'Connected' : 'Not connected'}
        </span>
        {!connected ? (
          provider.type === 'oauth' ? (
            <button
              type="button"
              className="btn btn-primary"
              onClick={connectOAuth}
              disabled={working}
              style={{ fontSize: '0.78rem', padding: '0.3rem 0.75rem' }}
            >
              Connect
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowInput((prev) => !prev)}
              disabled={working}
              style={{ fontSize: '0.78rem', padding: '0.3rem 0.75rem' }}
            >
              {showInput ? 'Cancel' : 'Connect'}
            </button>
          )
        ) : (
          <button
            type="button"
            className="btn"
            onClick={disconnect}
            disabled={working}
            style={{ fontSize: '0.78rem', padding: '0.3rem 0.75rem' }}
          >
            Disconnect
          </button>
        )}
        {message && (
          <span
            style={{
              fontSize: '0.73rem',
              color: message === 'Connected.' || message === 'Disconnected.' ? 'var(--success)' : 'var(--danger)',
            }}
          >
            {message}
          </span>
        )}
      </div>

      {showInput && !connected && provider.type === 'api_key' && (
        <div style={{ display: 'grid', gap: '0.4rem', paddingLeft: '112px' }}>
          {provider.hasBaseUrl && (
            <input
              type="text"
              className="input"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder={`${provider.label} API base URL (e.g. https://chorus.example.com)`}
              autoComplete="off"
              style={{ maxWidth: '380px', fontFamily: 'monospace', fontSize: '0.78rem' }}
            />
          )}
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <input
              type="password"
              className="input"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={`${provider.label} API key`}
              autoComplete="off"
              style={{ flex: 1, maxWidth: '320px' }}
            />
            <button
              type="button"
              className="btn btn-primary"
              onClick={connectApiKey}
              disabled={working}
              style={{ fontSize: '0.78rem', padding: '0.3rem 0.75rem' }}
            >
              {working ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ExternalAccountsPanel() {
  const [statuses, setStatuses] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch('/api/auth/me', { cache: 'no-store' });
        if (res.ok) {
          const data = await res.json();
          const connected = data?.connected_providers || {};
          setStatuses(connected);
        }
      } catch {
        // silently ignore — treat all as not connected
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Connected External Accounts</span>
        {loading && <span className="tag">Loading</span>}
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.6rem' }}>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-2)', marginBottom: '0.25rem' }}>
          Connect third-party data sources used for account enrichment and call intelligence.
        </p>
        {PROVIDERS.map((provider) => (
          <ProviderRow
            key={provider.id}
            provider={provider}
            initialConnected={Boolean(statuses[provider.id])}
          />
        ))}
      </div>
    </div>
  );
}
