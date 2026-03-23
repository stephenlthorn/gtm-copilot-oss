'use client';
import { useState } from 'react';

const FAILURE_CATEGORIES = [
  { slug: 'wrong_info',    label: '❌ Factually wrong' },
  { slug: 'missing_info',  label: '🔍 Missing info' },
  { slug: 'wrong_context', label: '❌ Wrong context' },
  { slug: 'outdated_info', label: '📅 Outdated info' },
  { slug: 'too_generic',   label: '🎯 Too generic' },
  { slug: 'wrong_tone',    label: '📝 Wrong tone' },
  { slug: 'incomplete',    label: '✂️ Incomplete' },
];

export default function FeedbackButtons({ message, query, mode = 'oracle' }) {
  const [rating, setRating] = useState(null); // 'positive' | 'negative' | null
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [correction, setCorrection] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const submit = async (r, correctionText = '', category = null) => {
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
          failure_category: category || null,
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
          onClick={() => {
            setRating(rating === 'negative' ? null : 'negative');
            setSelectedCategory(null);
          }}
          disabled={submitting}
          title="Needs improvement"
          style={{ fontSize: '0.72rem', background: 'transparent', border: 'none', cursor: 'pointer', color: rating === 'negative' ? 'var(--danger)' : 'var(--text-3)', padding: '0.1rem 0.25rem', borderRadius: '3px' }}
        >👎</button>
      </div>

      {rating === 'negative' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
          {/* Category chip picker */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
            {FAILURE_CATEGORIES.map(({ slug, label }) => (
              <button
                key={slug}
                onClick={() => setSelectedCategory(selectedCategory === slug ? null : slug)}
                style={{
                  fontSize: '0.68rem',
                  padding: '0.2rem 0.45rem',
                  borderRadius: '12px',
                  cursor: 'pointer',
                  border: selectedCategory === slug
                    ? '1.5px solid var(--accent, #4f8ef7)'
                    : '1px solid var(--border)',
                  background: selectedCategory === slug
                    ? 'var(--accent-bg, rgba(79,142,247,0.1))'
                    : 'var(--bg-2)',
                  color: selectedCategory === slug
                    ? 'var(--accent, #4f8ef7)'
                    : 'var(--text-2)',
                  fontWeight: selectedCategory === slug ? '600' : '400',
                  transition: 'all 0.12s ease',
                }}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Correction textarea + submit */}
          <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'flex-start' }}>
            <textarea
              placeholder="What should the correct answer have been? (optional)"
              value={correction}
              onChange={e => setCorrection(e.target.value)}
              rows={2}
              style={{ flex: 1, fontSize: '0.72rem', padding: '0.3rem 0.5rem', border: '1px solid var(--border)', borderRadius: '4px', background: 'var(--bg)', color: 'var(--text)', resize: 'vertical', fontFamily: 'var(--font)' }}
            />
            <button
              onClick={() => submit('negative', correction, selectedCategory)}
              disabled={submitting || !selectedCategory}
              className="btn btn-primary"
              style={{ fontSize: '0.72rem', padding: '0.25rem 0.55rem', alignSelf: 'flex-end', opacity: selectedCategory ? 1 : 0.45 }}
            >
              {submitting ? '…' : 'Submit'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
