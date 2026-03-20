'use client';

import { useState, useCallback } from 'react';
import { api } from '../../lib/api';

type RefineAIButtonProps = {
  readonly reportId?: string;
  readonly sectionId?: string;
  readonly context?: string;
  readonly onRefined?: (result: unknown) => void;
};

export default function RefineAIButton({ reportId, sectionId, context, onRefined }: RefineAIButtonProps) {
  const [open, setOpen] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = useCallback(async () => {
    if (!feedback.trim()) return;
    setSubmitting(true);
    setError('');
    try {
      const path = reportId
        ? `/api/research/reports/${reportId}/refine`
        : '/api/refinements';
      const body = {
        feedback: feedback.trim(),
        section_id: sectionId,
        context,
      };
      const { data } = await api.post(path, body);
      setSuccess(true);
      setFeedback('');
      onRefined?.(data);
      setTimeout(() => {
        setOpen(false);
        setSuccess(false);
      }, 1500);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }, [feedback, reportId, sectionId, context, onRefined]);

  if (!open) {
    return (
      <button
        className="btn btn-ghost"
        onClick={() => setOpen(true)}
        style={{ fontSize: '0.72rem', padding: '0.25rem 0.5rem' }}
      >
        Refine AI
      </button>
    );
  }

  return (
    <div style={{
      border: '1px solid var(--border-mid)',
      borderRadius: '6px',
      background: 'var(--bg-2)',
      padding: '0.75rem',
      marginTop: '0.5rem',
    }}>
      {success ? (
        <div style={{ color: 'var(--success)', fontSize: '0.8rem', fontWeight: 600 }}>
          Feedback saved
        </div>
      ) : (
        <>
          <textarea
            className="input"
            rows={3}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="How should the AI improve this section?"
            style={{ marginBottom: '0.5rem' }}
          />
          <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
            <button
              className="btn btn-primary"
              onClick={handleSubmit}
              disabled={submitting || !feedback.trim()}
              style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
            >
              {submitting ? 'Submitting...' : 'Submit Feedback'}
            </button>
            <button
              className="btn btn-ghost"
              onClick={() => { setOpen(false); setFeedback(''); setError(''); }}
              style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
            >
              Cancel
            </button>
          </div>
          {error && <div className="error-text">{error}</div>}
        </>
      )}
    </div>
  );
}

export type { RefineAIButtonProps };
