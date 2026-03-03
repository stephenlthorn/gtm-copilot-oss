import Link from 'next/link';
import { apiGet } from '../../../lib/api';

export default async function CallPage({ params }) {
  const { id } = await params;
  const payload = await apiGet(`/calls/${encodeURIComponent(id)}`).catch(() => null);
  const call = payload?.call || null;
  const artifact = payload?.artifact || null;
  const chunks = payload?.chunks || [];

  if (!call) {
    return (
      <div style={{ padding: '2rem' }}>
        <p style={{ color: 'var(--text-3)', marginBottom: '1rem' }}>Call not found: {id}</p>
        <Link href="/rep">← Back to Rep</Link>
      </div>
    );
  }

  return (
    <div style={{ padding: '1.25rem', display: 'grid', gap: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <Link href="/rep" style={{ color: 'var(--text-3)', fontSize: '0.78rem' }}>← Back</Link>
        <span className="tag">{call.stage || 'Call'}</span>
        <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{call.chorus_call_id}</span>
      </div>

      <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text)' }}>
        {call.account || 'Unknown Account'} — {call.date || 'Unknown date'}
      </div>

      <div className="two-col">
        <div className="panel">
          <div className="panel-header"><span className="panel-title">Call Summary</span></div>
          <div className="panel-body" style={{ fontSize: '0.82rem', color: 'var(--text-2)', lineHeight: 1.6 }}>
            {artifact?.summary || 'No generated summary available yet.'}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header"><span className="panel-title">Metadata</span></div>
          <div className="panel-body" style={{ display: 'grid', gap: '0.4rem', fontSize: '0.8rem' }}>
            {[
              { label: 'Call ID', value: call.chorus_call_id },
              { label: 'Rep', value: call.rep_email || '—' },
              { label: 'SE', value: call.se_email || '—' },
              {
                label: 'Participants',
                value: Array.isArray(call.participants) && call.participants.length
                  ? call.participants.map((p) => p.name || p.email || p.role || 'Participant').join(', ')
                  : '—',
              },
            ].map(({ label, value }) => (
              <div key={label} style={{ display: 'grid', gridTemplateColumns: '90px 1fr' }}>
                <span style={{ color: 'var(--text-3)' }}>{label}</span>
                <span style={{ color: 'var(--text)' }}>{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="three-col">
        <div className="panel">
          <div className="panel-header"><span className="panel-title">Risks</span></div>
          <div className="panel-body">
            <ul style={{ listStyle: 'none', display: 'grid', gap: '0.45rem' }}>
              {(artifact?.risks || []).map((r) => (
                <li key={r} style={{ fontSize: '0.78rem', color: 'var(--danger)' }}>⚠ {r}</li>
              ))}
              {(!artifact?.risks || artifact.risks.length === 0) && (
                <li style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>No risks extracted yet.</li>
              )}
            </ul>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header"><span className="panel-title">Next Steps</span></div>
          <div className="panel-body">
            <ul style={{ listStyle: 'none', display: 'grid', gap: '0.45rem' }}>
              {(artifact?.next_steps || []).map((s) => (
                <li key={s} style={{ fontSize: '0.78rem', color: 'var(--text-2)' }}>→ {s}</li>
              ))}
              {(!artifact?.next_steps || artifact.next_steps.length === 0) && (
                <li style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>No next steps extracted yet.</li>
              )}
            </ul>
          </div>
        </div>

        <div className="panel">
          <div className="panel-header"><span className="panel-title">Collateral</span></div>
          <div className="panel-body">
            <ul style={{ listStyle: 'none', display: 'grid', gap: '0.45rem' }}>
              {(artifact?.recommended_collateral || []).map((c) => (
                <li key={c.title} style={{ fontSize: '0.78rem' }}>
                  <span style={{ color: 'var(--accent)' }}>↗ {c.title}</span>
                </li>
              ))}
              {(!artifact?.recommended_collateral || artifact.recommended_collateral.length === 0) && (
                <li style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>No collateral recommendations yet.</li>
              )}
            </ul>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header"><span className="panel-title">Transcript</span></div>
        <div className="panel-body">
          <pre style={{ maxHeight: '320px' }}>
            {chunks.length
              ? chunks.map((c) => c.text || '').join('\n\n')
              : 'No transcript chunks indexed yet.'}
          </pre>
        </div>
      </div>
    </div>
  );
}
