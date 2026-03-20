'use client';
import { useState } from 'react';

export default function FeedbackButtons({ message, query, mode = 'oracle' }) {
  const [rating, setRating] = useState(null); // 'positive' | 'negative' | null
  const [correction, setCorrection] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const submit = async (r, correctionText = '') => {
    setSubmitting(true);
    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          query_text: query,
          original_response: message,
          rating: r,
          correction: correctionText || null,
        }),
      });
      setRating(r);
      setSubmitted(true);
    } catch { /* silent */ }
    finally { setSubmitting(false); }
  };

  if (submitted) {
    return <span style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>✓ feedback saved</span>;
  }

  return (
    <div style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
      <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
        <button
          onClick={() => submit('positive')}
          disabled={submitting}
          title="Good response"
          style={{ fontSize: '0.72rem', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: '0.1rem 0.25rem', borderRadius: '3px' }}
        >👍</button>
        <button
          onClick={() => setRating(rating === 'negative' ? null : 'negative')}
          disabled={submitting}
          title="Needs improvement"
          style={{ fontSize: '0.72rem', background: 'transparent', border: 'none', cursor: 'pointer', color: rating === 'negative' ? 'var(--danger)' : 'var(--text-3)', padding: '0.1rem 0.25rem', borderRadius: '3px' }}
        >👎</button>
      </div>
      {rating === 'negative' && (
        <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'flex-start' }}>
          <textarea
            placeholder="What should the correct answer have been? (optional)"
            value={correction}
            onChange={e => setCorrection(e.target.value)}
            rows={2}
            style={{ flex: 1, fontSize: '0.72rem', padding: '0.3rem 0.5rem', border: '1px solid var(--border)', borderRadius: '4px', background: 'var(--bg)', color: 'var(--text)', resize: 'vertical', fontFamily: 'var(--font)' }}
          />
          <button
            onClick={() => submit('negative', correction)}
            disabled={submitting}
            className="btn btn-primary"
            style={{ fontSize: '0.72rem', padding: '0.25rem 0.55rem', alignSelf: 'flex-end' }}
          >
            {submitting ? '…' : 'Submit'}
          </button>
        </div>
      )}
    </div>
  );
}
