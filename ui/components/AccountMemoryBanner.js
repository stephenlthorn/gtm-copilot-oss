'use client';
import { useState } from 'react';

export default function AccountMemoryBanner({ account, memory, onUpdate }) {
  const [open, setOpen] = useState(false);
  const [approving, setApproving] = useState(false);

  if (!memory?.pending_review) return null;

  async function handleApprove() {
    setApproving(true);
    try {
      const res = await fetch(`/api/accounts/${encodeURIComponent(account)}/memory/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ edits: null }),
      });
      if (res.ok) onUpdate?.();
    } finally {
      setApproving(false);
      setOpen(false);
    }
  }

  async function handleDismiss() {
    await fetch(`/api/accounts/${encodeURIComponent(account)}/memory/dismiss`, { method: 'POST' });
    onUpdate?.();
  }

  const delta = memory.pending_delta || {};

  return (
    <div style={{ background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '6px', padding: '0.75rem 1rem', marginBottom: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#92400e' }}>
          ⚡ Account memory updated for {account} — review proposed changes
        </span>
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          <button onClick={() => setOpen(o => !o)} className="btn" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}>
            {open ? 'Hide' : 'Review'}
          </button>
          <button onClick={handleApprove} disabled={approving} className="btn btn-primary" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}>
            {approving ? '…' : 'Approve'}
          </button>
          <button onClick={handleDismiss} className="btn" style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', color: 'var(--text-3)' }}>
            Dismiss
          </button>
        </div>
      </div>
      {open && (
        <pre style={{ marginTop: '0.75rem', fontSize: '0.72rem', background: '#fff', border: '1px solid #f59e0b', borderRadius: '4px', padding: '0.5rem', whiteSpace: 'pre-wrap', maxHeight: '300px', overflowY: 'auto' }}>
          {JSON.stringify(delta, null, 2)}
        </pre>
      )}
    </div>
  );
}
