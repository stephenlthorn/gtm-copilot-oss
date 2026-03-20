'use client';
import { useState } from 'react';

export default function FeedbackButtons({ mode, queryText, originalResponse }) {
  const [rating, setRating] = useState(null);
  const [correction, setCorrection] = useState('');
  const [showCorrection, setShowCorrection] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function submit(selectedRating) {
    if (submitting) return;
    setSubmitting(true);
    setRating(selectedRating);

    const payload = {
      mode,
      query_text: queryText,
      original_response: typeof originalResponse === 'string' ? originalResponse : JSON.stringify(originalResponse),
      rating: selectedRating,
    };
    if (selectedRating === 'negative' && correction.trim()) {
      payload.correction = correction.trim();
    }

    try {
      await fetch('/api/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setSubmitted(true);
    } catch {
      // Silently fail - feedback is best-effort
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <span style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
        {rating === 'positive' ? '\uD83D\uDC4D' : '\uD83D\uDC4E'} Feedback recorded
      </span>
    );
  }

  if (showCorrection) {
    return (
      <div style={{ marginTop: '0.5rem' }}>
        <textarea
          value={correction}
          onChange={(e) => setCorrection(e.target.value)}
          placeholder="What should the correct answer be?"
          rows={3}
          style={{
            width: '100%',
            background: 'var(--panel)',
            border: '1px solid var(--border)',
            borderRadius: '6px',
            color: 'var(--fg)',
            padding: '0.5rem',
            fontSize: '0.85rem',
            resize: 'vertical',
          }}
        />
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.4rem' }}>
          <button
            onClick={() => submit('negative')}
            disabled={submitting}
            style={{
              background: 'var(--accent)',
              color: '#000',
              border: 'none',
              borderRadius: '6px',
              padding: '0.3rem 0.8rem',
              fontSize: '0.8rem',
              cursor: 'pointer',
            }}
          >
            {submitting ? 'Sending...' : 'Submit'}
          </button>
          <button
            onClick={() => setShowCorrection(false)}
            style={{
              background: 'transparent',
              color: 'var(--muted)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              padding: '0.3rem 0.8rem',
              fontSize: '0.8rem',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
      <button
        onClick={() => submit('positive')}
        disabled={submitting}
        title="Good response"
        style={{
          background: 'transparent',
          border: '1px solid var(--border)',
          borderRadius: '6px',
          padding: '0.25rem 0.5rem',
          cursor: 'pointer',
          fontSize: '0.85rem',
          color: 'var(--muted)',
        }}
      >
        {'\uD83D\uDC4D'}
      </button>
      <button
        onClick={() => setShowCorrection(true)}
        disabled={submitting}
        title="Bad response - provide correction"
        style={{
          background: 'transparent',
          border: '1px solid var(--border)',
          borderRadius: '6px',
          padding: '0.25rem 0.5rem',
          cursor: 'pointer',
          fontSize: '0.85rem',
          color: 'var(--muted)',
        }}
      >
        {'\uD83D\uDC4E'}
      </button>
    </div>
  );
}
