'use client';
import { useState, useEffect } from 'react';

export default function PromptVersionHistory({ promptId, onRollback, onSelectVersion }) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [diffA, setDiffA] = useState(null);
  const [diffB, setDiffB] = useState(null);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/prompts/${promptId}/versions`)
      .then(r => r.json())
      .then(data => { setVersions(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [promptId]);

  const rollback = async (version) => {
    if (!confirm(`Rollback to version ${version}? This creates a new version with the old content.`)) return;
    const res = await fetch(`/api/prompts/${promptId}/rollback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version }),
    });
    if (res.ok) onRollback();
  };

  const computeDiff = (textA, textB) => {
    const linesA = (textA || '').split('\n');
    const linesB = (textB || '').split('\n');
    const maxLen = Math.max(linesA.length, linesB.length);
    const result = [];
    for (let i = 0; i < maxLen; i++) {
      const a = linesA[i] ?? '';
      const b = linesB[i] ?? '';
      if (a === b) result.push({ type: 'same', text: a });
      else {
        if (a) result.push({ type: 'removed', text: a });
        if (b) result.push({ type: 'added', text: b });
      }
    }
    return result;
  };

  if (loading) return <div style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>Loading history…</div>;
  if (versions.length === 0) return <div style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>No version history yet.</div>;

  return (
    <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.75rem' }}>
      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-2)', marginBottom: '0.5rem' }}>
        Version History ({versions.length})
      </div>
      <div style={{ display: 'grid', gap: '0.3rem', marginBottom: '0.75rem' }}>
        {versions.map(v => (
          <div key={v.version} style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.4rem 0.6rem', border: '1px solid var(--border)',
            borderRadius: '4px', fontSize: '0.75rem',
            background: (diffA?.version === v.version || diffB?.version === v.version)
              ? 'rgba(57,255,20,0.06)' : 'var(--bg)',
          }}>
            <span style={{ fontWeight: 600, color: 'var(--accent)', minWidth: '30px' }}>v{v.version}</span>
            <span style={{ color: 'var(--text-2)', flex: 1 }}>
              {v.edited_by?.split('@')[0]} — {v.note || 'no note'}
            </span>
            <span style={{ color: 'var(--text-3)', fontSize: '0.68rem' }}>
              {v.edited_at ? new Date(v.edited_at).toLocaleString() : ''}
            </span>
            <button className="btn" style={{ fontSize: '0.68rem', padding: '0.15rem 0.4rem' }}
              onClick={() => onSelectVersion(v)}>Load</button>
            <button className="btn" style={{ fontSize: '0.68rem', padding: '0.15rem 0.4rem' }}
              onClick={() => rollback(v.version)}>Rollback</button>
            <button className="btn" style={{ fontSize: '0.68rem', padding: '0.15rem 0.4rem' }}
              onClick={() => diffA ? setDiffB(v) : setDiffA(v)}>
              {!diffA ? 'Diff A' : !diffB ? 'Diff B' : 'Diff A'}
            </button>
          </div>
        ))}
      </div>
      {diffA && diffB && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-2)' }}>
              Comparing v{diffA.version} → v{diffB.version}
            </span>
            <button className="btn" style={{ fontSize: '0.68rem' }}
              onClick={() => { setDiffA(null); setDiffB(null); }}>Clear Diff</button>
          </div>
          <pre style={{
            fontSize: '0.72rem', lineHeight: 1.5, maxHeight: '300px',
            overflow: 'auto', background: 'var(--bg)', border: '1px solid var(--border)',
            borderRadius: '5px', padding: '0.5rem',
          }}>
            {computeDiff(diffA.content, diffB.content).map((line, i) => (
              <div key={i} style={{
                color: line.type === 'added' ? '#39ff14' : line.type === 'removed' ? '#f87171' : 'var(--text-2)',
                background: line.type === 'added' ? 'rgba(57,255,20,0.06)' :
                  line.type === 'removed' ? 'rgba(248,113,113,0.06)' : 'transparent',
              }}>
                {line.type === 'added' ? '+ ' : line.type === 'removed' ? '- ' : '  '}{line.text}
              </div>
            ))}
          </pre>
        </div>
      )}
    </div>
  );
}
