'use client';
import { useState, useEffect } from 'react';

// ---------------------------------------------------------------------------
// Category display labels
// ---------------------------------------------------------------------------
const CATEGORY_LABELS = {
  wrong_info:    '❌ Factually wrong',
  missing_info:  '🔍 Missing info',
  wrong_context: '❌ Wrong context',
  outdated_info: '📅 Outdated info',
  too_generic:   '🎯 Too generic',
  wrong_tone:    '📝 Wrong tone',
  incomplete:    '✂️ Incomplete',
};

// ---------------------------------------------------------------------------
// Simple word-diff implementation (no external library)
// ---------------------------------------------------------------------------
function computeInlineDiff(oldText, newText) {
  const oldWords = oldText.split(/(\s+)/);
  const newWords = newText.split(/(\s+)/);

  // Build LCS table
  const m = oldWords.length;
  const n = newWords.length;
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldWords[i - 1] === newWords[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack to produce diff tokens
  const result = [];
  let i = m;
  let j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldWords[i - 1] === newWords[j - 1]) {
      result.unshift({ text: oldWords[i - 1], type: 'unchanged' });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ text: newWords[j - 1], type: 'added' });
      j--;
    } else {
      result.unshift({ text: oldWords[i - 1], type: 'removed' });
      i--;
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Inline diff renderer
// ---------------------------------------------------------------------------
function InlineDiff({ oldText, newText }) {
  const tokens = computeInlineDiff(oldText, newText);
  return (
    <pre style={{
      fontFamily: 'var(--font-mono, monospace)',
      fontSize: '0.75rem',
      lineHeight: 1.6,
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-word',
      background: 'var(--bg-2)',
      border: '1px solid var(--border)',
      borderRadius: '6px',
      padding: '0.75rem 1rem',
      margin: 0,
    }}>
      {tokens.map((token, idx) => {
        if (token.type === 'added') {
          return (
            <mark key={idx} style={{
              background: 'rgba(34, 197, 94, 0.2)',
              color: 'var(--text)',
              borderRadius: '2px',
            }}>{token.text}</mark>
          );
        }
        if (token.type === 'removed') {
          return (
            <del key={idx} style={{
              background: 'rgba(239, 68, 68, 0.15)',
              color: 'var(--text-3)',
              textDecorationColor: 'rgba(239, 68, 68, 0.6)',
            }}>{token.text}</del>
          );
        }
        return <span key={idx}>{token.text}</span>;
      })}
    </pre>
  );
}

// ---------------------------------------------------------------------------
// Suggestion panel (expands inline below a table row)
// ---------------------------------------------------------------------------
function SuggestionPanel({ suggestion, onApplied, onDismissed }) {
  const [applying, setApplying] = useState(false);
  const [dismissing, setDismissing] = useState(false);
  const [copyDone, setCopyDone] = useState(false);

  const handleApply = async () => {
    setApplying(true);
    try {
      const res = await fetch(`/api/admin/feedback-suggestions/${suggestion.id}/apply`, {
        method: 'POST',
      });
      if (res.ok) onApplied(suggestion.id);
    } finally {
      setApplying(false);
    }
  };

  const handleDismiss = async () => {
    setDismissing(true);
    try {
      const res = await fetch(`/api/admin/feedback-suggestions/${suggestion.id}/dismiss`, {
        method: 'POST',
      });
      if (res.ok) onDismissed(suggestion.id);
    } finally {
      setDismissing(false);
    }
  };

  const handleCopyAdvisory = () => {
    const advisory = `PROMPT ADVISORY\nMode: ${suggestion.mode}\nCategory: ${suggestion.failure_category}\nFile: api/app/prompts/templates.py\n\nReasoning:\n${suggestion.reasoning}\n\nSuggested prompt:\n${suggestion.suggested_prompt}`;
    navigator.clipboard.writeText(advisory);
    setCopyDone(true);
    setTimeout(() => setCopyDone(false), 2000);
  };

  const isBuiltin = suggestion.prompt_type === 'builtin';

  return (
    <div style={{
      padding: '1rem 1.25rem',
      background: 'var(--bg-2)',
      borderTop: '1px solid var(--border)',
      borderBottom: '1px solid var(--border)',
    }}>
      {/* Reasoning block */}
      <div style={{
        borderLeft: '3px solid var(--accent, #4f8ef7)',
        paddingLeft: '0.75rem',
        marginBottom: '1rem',
        fontSize: '0.82rem',
        color: 'var(--text-2)',
        lineHeight: 1.5,
      }}>
        <strong style={{ color: 'var(--text)' }}>GPT-4o Analysis</strong>
        <p style={{ margin: '0.25rem 0 0' }}>{suggestion.reasoning}</p>
      </div>

      {/* Built-in advisory */}
      {isBuiltin && (
        <div style={{
          border: '1px solid var(--border)',
          borderRadius: '6px',
          padding: '0.6rem 0.85rem',
          marginBottom: '1rem',
          background: 'var(--bg)',
          fontSize: '0.78rem',
          color: 'var(--text-2)',
        }}>
          <strong>Built-in prompt — requires code change</strong>
          <p style={{ margin: '0.2rem 0 0' }}>
            Constant: <code>BUILTIN_PROMPT_MAP["{suggestion.mode}"]</code> →{' '}
            <code>api/app/prompts/templates.py</code>
          </p>
        </div>
      )}

      {/* Inline diff */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginBottom: '0.4rem', fontWeight: 500 }}>
          Proposed changes
        </div>
        <InlineDiff
          oldText={suggestion.current_prompt}
          newText={suggestion.suggested_prompt}
        />
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <button
          onClick={handleApply}
          disabled={applying || isBuiltin}
          className="btn btn-primary"
          style={{
            fontSize: '0.78rem',
            padding: '0.3rem 0.7rem',
            opacity: isBuiltin ? 0.4 : 1,
            cursor: isBuiltin ? 'not-allowed' : 'pointer',
          }}
          title={isBuiltin ? 'Built-in prompts require a code change' : 'Apply to persona prompt'}
        >
          {applying ? '…' : 'Apply to persona prompt'}
        </button>
        <button
          onClick={handleCopyAdvisory}
          className="btn"
          style={{ fontSize: '0.78rem', padding: '0.3rem 0.7rem' }}
        >
          {copyDone ? '✓ Copied' : 'Copy advisory'}
        </button>
        <button
          onClick={handleDismiss}
          disabled={dismissing}
          className="btn"
          style={{ fontSize: '0.78rem', padding: '0.3rem 0.7rem', color: 'var(--text-3)' }}
        >
          {dismissing ? '…' : 'Dismiss'}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function FeedbackDashboard() {
  const [alerts, setAlerts] = useState([]);
  const [patterns, setPatterns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedRow, setExpandedRow] = useState(null); // { rowKey, suggestion }
  const [generatingSuggestion, setGeneratingSuggestion] = useState(null); // rowKey

  useEffect(() => {
    Promise.all([
      fetch('/api/admin/feedback-alerts').then(r => r.json()).catch(() => []),
      fetch('/api/admin/feedback-patterns').then(r => r.json()).catch(() => []),
    ]).then(([alertsData, patternsData]) => {
      setAlerts(Array.isArray(alertsData) ? alertsData : []);
      setPatterns(Array.isArray(patternsData) ? patternsData : []);
      setLoading(false);
    });
  }, []);

  const handleSuggestFix = async (mode, failureCategory, promptType = 'persona') => {
    const rowKey = `${mode}::${failureCategory}`;
    setGeneratingSuggestion(rowKey);
    try {
      const res = await fetch('/api/admin/feedback-suggestions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, failure_category: failureCategory, prompt_type: promptType }),
      });
      if (!res.ok) {
        const err = await res.json();
        alert(`Error generating suggestion: ${err.detail || res.statusText}`);
        return;
      }
      const suggestion = await res.json();
      setExpandedRow(prev =>
        prev?.rowKey === rowKey ? null : { rowKey, suggestion }
      );
    } finally {
      setGeneratingSuggestion(null);
    }
  };

  const handleApplied = (suggestionId) => {
    setExpandedRow(null);
  };

  const handleDismissed = (suggestionId) => {
    setExpandedRow(null);
    // Refresh alerts after dismiss
    fetch('/api/admin/feedback-alerts').then(r => r.json()).then(data => {
      setAlerts(Array.isArray(data) ? data : []);
    });
  };

  // Derived KPIs
  const totalNegative = patterns.reduce((sum, p) => sum + p.count, 0);
  const topMode = patterns.length > 0 ? patterns[0].mode : '—';
  const topCategory = patterns.length > 0 ? (CATEGORY_LABELS[patterns[0].failure_category] || patterns[0].failure_category) : '—';

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar-title">Feedback Analytics</div>
          <div className="topbar-meta">Failure patterns · prompt suggestions · last 7 days</div>
        </div>
      </div>

      <div className="content">
        {loading && (
          <p style={{ color: 'var(--text-3)', fontSize: '0.82rem' }}>Loading…</p>
        )}

        {/* Alert banners */}
        {alerts.map((alert, idx) => (
          <div key={idx} style={{
            background: 'rgba(234, 179, 8, 0.12)',
            border: '1px solid rgba(234, 179, 8, 0.35)',
            borderRadius: '6px',
            padding: '0.65rem 1rem',
            marginBottom: '0.6rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            fontSize: '0.82rem',
          }}>
            <span>
              ⚠️ <strong>{alert.count} failures</strong> in <strong>{alert.mode}</strong> —
              "{CATEGORY_LABELS[alert.failure_category] || alert.failure_category}" since last analysis
            </span>
            <button
              className="btn btn-primary"
              style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem', whiteSpace: 'nowrap' }}
              onClick={() => handleSuggestFix(alert.mode, alert.failure_category, 'persona')}
              disabled={generatingSuggestion === `${alert.mode}::${alert.failure_category}`}
            >
              {generatingSuggestion === `${alert.mode}::${alert.failure_category}` ? '…' : 'View suggestion'}
            </button>
          </div>
        ))}

        {/* KPI row */}
        <div className="kpi-row" style={{ marginBottom: '1.5rem' }}>
          {[
            { label: 'Negative Feedback (7d)', value: totalNegative, sub: 'across all modes' },
            { label: 'Top Failing Mode', value: topMode, sub: 'by volume' },
            { label: 'Most Common Failure', value: topCategory, sub: 'by count' },
            { label: 'Patterns Tracked', value: patterns.length, sub: 'active categories' },
          ].map((k) => (
            <div className="kpi-card" key={k.label}>
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value">{k.value}</div>
              <div className="kpi-sub">{k.sub}</div>
            </div>
          ))}
        </div>

        {/* Failure patterns table */}
        {!loading && patterns.length === 0 && (
          <p style={{ color: 'var(--text-3)', fontSize: '0.82rem' }}>
            No failure patterns in the last 7 days.
          </p>
        )}

        {patterns.length > 0 && (
          <div style={{ border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ background: 'var(--bg-2)', borderBottom: '1px solid var(--border)' }}>
                  {['Mode', 'Category', 'Count (7d)', 'Last seen', 'Action'].map(h => (
                    <th key={h} style={{ padding: '0.55rem 0.85rem', textAlign: 'left', fontWeight: 600, color: 'var(--text-2)', fontSize: '0.75rem' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {patterns.map((pattern, idx) => {
                  const rowKey = `${pattern.mode}::${pattern.failure_category}`;
                  const isExpanded = expandedRow?.rowKey === rowKey;
                  const isGenerating = generatingSuggestion === rowKey;
                  return (
                    <>
                      <tr key={rowKey} style={{
                        borderBottom: isExpanded ? 'none' : '1px solid var(--border)',
                        background: isExpanded ? 'var(--bg-2)' : 'var(--bg)',
                      }}>
                        <td style={{ padding: '0.55rem 0.85rem', fontWeight: 500 }}>{pattern.mode}</td>
                        <td style={{ padding: '0.55rem 0.85rem' }}>
                          {CATEGORY_LABELS[pattern.failure_category] || pattern.failure_category}
                        </td>
                        <td style={{ padding: '0.55rem 0.85rem', fontWeight: 600 }}>{pattern.count}</td>
                        <td style={{ padding: '0.55rem 0.85rem', color: 'var(--text-3)' }}>
                          {pattern.last_seen ? new Date(pattern.last_seen).toLocaleDateString() : '—'}
                        </td>
                        <td style={{ padding: '0.55rem 0.85rem' }}>
                          <button
                            className="btn"
                            style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem' }}
                            onClick={() => isExpanded
                              ? setExpandedRow(null)
                              : handleSuggestFix(pattern.mode, pattern.failure_category, 'persona')
                            }
                            disabled={isGenerating}
                          >
                            {isGenerating ? '…' : isExpanded ? 'Close' : 'Suggest fix'}
                          </button>
                        </td>
                      </tr>
                      {isExpanded && expandedRow?.suggestion && (
                        <tr key={`${rowKey}-panel`}>
                          <td colSpan={5} style={{ padding: 0 }}>
                            <SuggestionPanel
                              suggestion={expandedRow.suggestion}
                              onApplied={handleApplied}
                              onDismissed={handleDismissed}
                            />
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
