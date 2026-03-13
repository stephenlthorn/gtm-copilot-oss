'use client';

import { useState, useCallback } from 'react';

const SOURCE_OPTIONS = [
  { value: '', label: 'All sources' },
  { value: 'google_drive', label: 'Google Drive' },
  { value: 'chorus', label: 'Call Transcripts' },
  { value: 'feishu', label: 'Feishu' },
  { value: 'official_docs_online', label: 'Official Docs' },
];

function sourceTag(type) {
  const map = {
    google_drive: { label: 'Drive', cls: 'tag-green' },
    chorus: { label: 'Call', cls: 'tag-blue' },
    feishu: { label: 'Feishu', cls: '' },
    official_docs_online: { label: 'Docs', cls: '' },
    memory: { label: 'Memory', cls: '' },
  };
  const s = map[type] || { label: type, cls: '' };
  return <span className={`tag ${s.cls}`} style={{ fontSize: '0.68rem' }}>{s.label}</span>;
}

function scoreBar(score) {
  const pct = Math.min(100, Math.round((score || 0) * 100));
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
      <div style={{ width: 60, height: 4, background: 'var(--border)', borderRadius: 2 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: 'var(--primary)', borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>{pct}%</span>
    </div>
  );
}

export default function KBBrowserPanel() {
  const [mode, setMode] = useState('browse'); // 'browse' | 'retrieval'
  const [query, setQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [account, setAccount] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(null);

  const search = useCallback(async () => {
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError('');
    setResults(null);
    setExpanded(null);
    try {
      if (mode === 'browse') {
        // Fulltext search — shows what's indexed
        const params = new URLSearchParams({ q, limit: '40' });
        if (sourceFilter) params.set('source_type', sourceFilter);
        const res = await fetch(`/api/kb/fulltext?${params}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data?.detail || 'Search failed');
        setResults({ type: 'fulltext', items: data.results || [] });
      } else {
        // Vector retrieval preview — exactly what LLM would get
        const params = new URLSearchParams({ q, top_k: '10' });
        if (sourceFilter) params.set('source_type', sourceFilter);
        if (account.trim()) params.set('account', account.trim());
        const res = await fetch(`/api/kb/search?${params}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data?.detail || 'Search failed');
        setResults({ type: 'vector', items: data.results || [] });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [query, mode, sourceFilter, account]);

  const handleKey = (e) => { if (e.key === 'Enter') search(); };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">KB Browser</span>
        {results && (
          <span className="tag">{results.items.length} result{results.items.length !== 1 ? 's' : ''}</span>
        )}
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>

        {/* Mode toggle */}
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          <button
            className={`btn ${mode === 'browse' ? 'btn-primary' : ''}`}
            style={{ fontSize: '0.78rem', padding: '0.25rem 0.7rem' }}
            onClick={() => { setMode('browse'); setResults(null); }}
          >
            Browse / Fulltext
          </button>
          <button
            className={`btn ${mode === 'retrieval' ? 'btn-primary' : ''}`}
            style={{ fontSize: '0.78rem', padding: '0.25rem 0.7rem' }}
            onClick={() => { setMode('retrieval'); setResults(null); }}
          >
            Retrieval Preview
          </button>
        </div>

        {mode === 'retrieval' && (
          <p style={{ fontSize: '0.78rem', color: 'var(--text-3)', margin: 0 }}>
            Shows the exact chunks the LLM would receive for a given query + account (vector similarity search).
          </p>
        )}

        {/* Search controls */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            className="input"
            style={{ flex: '1 1 200px', fontSize: '0.8rem', padding: '0.3rem 0.6rem' }}
            placeholder={mode === 'retrieval' ? 'Question / topic (e.g. "pricing objections")' : 'Search indexed content…'}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKey}
          />
          {mode === 'retrieval' && (
            <input
              className="input"
              style={{ flex: '1 1 160px', fontSize: '0.8rem', padding: '0.3rem 0.6rem' }}
              placeholder="Account name (optional)"
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              onKeyDown={handleKey}
            />
          )}
          <select
            className="input"
            style={{ fontSize: '0.8rem', padding: '0.3rem 0.5rem' }}
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
          >
            {SOURCE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <button
            className="btn btn-primary"
            style={{ fontSize: '0.8rem', padding: '0.3rem 0.9rem' }}
            onClick={search}
            disabled={loading || !query.trim()}
          >
            {loading ? 'Searching…' : 'Search'}
          </button>
        </div>

        {error && (
          <p style={{ color: 'var(--danger)', fontSize: '0.78rem', margin: 0 }}>✗ {error}</p>
        )}

        {/* Results */}
        {results && results.items.length === 0 && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-3)', margin: 0 }}>No results found.</p>
        )}

        {results && results.items.length > 0 && (
          <div style={{ display: 'grid', gap: '0.4rem' }}>
            {results.items.map((item, i) => {
              const key = item.chunk_id || `${item.source_id}-${i}`;
              const isOpen = expanded === key;
              return (
                <div
                  key={key}
                  style={{
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    overflow: 'hidden',
                    cursor: 'pointer',
                  }}
                  onClick={() => setExpanded(isOpen ? null : key)}
                >
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    padding: '0.5rem 0.75rem',
                    background: isOpen ? 'var(--surface-2)' : 'var(--surface)',
                  }}>
                    <span style={{ fontSize: '0.68rem', color: 'var(--text-3)', minWidth: '1.2rem' }}>
                      {i + 1}
                    </span>
                    {sourceTag(item.source_type)}
                    <span style={{ flex: 1, fontSize: '0.8rem', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.title || item.source_id}
                    </span>
                    {results.type === 'vector' && scoreBar(item.score)}
                    {item.url && (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        style={{ fontSize: '0.7rem', color: 'var(--primary)' }}
                      >
                        ↗
                      </a>
                    )}
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>{isOpen ? '▲' : '▼'}</span>
                  </div>
                  {isOpen && (
                    <div style={{ padding: '0.6rem 0.75rem', borderTop: '1px solid var(--border)', background: 'var(--surface-2)' }}>
                      <pre style={{
                        margin: 0,
                        fontSize: '0.73rem',
                        color: 'var(--text-2)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        maxHeight: 300,
                        overflowY: 'auto',
                      }}>
                        {item.text || item.snippet || '(no text)'}
                      </pre>
                      {item.metadata && Object.keys(item.metadata).length > 0 && (
                        <div style={{ marginTop: '0.4rem', fontSize: '0.68rem', color: 'var(--text-3)' }}>
                          {Object.entries(item.metadata).map(([k, v]) => (
                            <span key={k} style={{ marginRight: '1rem' }}>{k}: <b>{String(v)}</b></span>
                          ))}
                        </div>
                      )}
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
