'use client';

const MODEL_SCORES = {
  'gpt-5.4':          60,
  'o3-pro':           60,
  'o3':               55,
  'gpt-5.3-codex':    50,
  'gpt-5.1-codex':    48,
  'o4-mini':          42,
  'o3-mini':          40,
  'gpt-5.4-mini':     35,
  'gpt-5-codex-mini': 30,
  'gpt-5.4-nano':     22,
};

const REASONING_MODELS = new Set([
  'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.3-codex', 'o4-mini',
  'o3', 'o3-pro', 'o3-mini', 'gpt-5.1-codex',
]);

const THINKING_BONUS = { high: 15, medium: 8, low: 2 };

function computeScore(model, thinking, ragEnabled, webSearchEnabled) {
  const base = MODEL_SCORES[model] ?? 35;
  const thinkBonus = REASONING_MODELS.has(model) ? (THINKING_BONUS[thinking] ?? 8) : 0;
  const kbBonus = ragEnabled ? 15 : 0;
  const webBonus = webSearchEnabled ? 10 : 0;
  return Math.min(100, base + thinkBonus + kbBonus + webBonus);
}

function scoreColor(score) {
  if (score >= 71) return '#22c55e';
  if (score >= 41) return '#eab308';
  return '#ef4444';
}

export default function IntelMeter({ model = 'gpt-5.4', thinking = 'medium', ragEnabled = true, webSearchEnabled = true }) {
  const score = computeScore(model, thinking, ragEnabled, webSearchEnabled);
  const color = scoreColor(score);
  const isReasoning = REASONING_MODELS.has(model);

  const dimColor = 'var(--text-3)';
  const dimDot = 'var(--border-hi)';

  const seg = (label, value, active) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
      <div style={{ width: 5, height: 5, borderRadius: '50%', background: active ? color : dimDot, flexShrink: 0 }} />
      <span style={{ color: dimColor, fontSize: '0.68rem' }}>{label}</span>
      <span style={{
        fontSize: '0.68rem',
        color: active ? color : 'var(--text-3)',
        textDecoration: active ? 'none' : 'line-through',
      }}>{value}</span>
    </div>
  );

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '0.6rem',
      padding: '4px 1rem',
      borderTop: '1px solid var(--border)',
      background: 'var(--bg)',
      flexShrink: 0,
    }}>
      {/* Label */}
      <span style={{ fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-3)', fontWeight: 600, flexShrink: 0 }}>
        AI Power
      </span>

      {/* Pill: bar + score */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '5px',
        border: `1px solid ${color}40`,
        background: `${color}0d`,
        borderRadius: '4px',
        padding: '2px 7px',
        flexShrink: 0,
      }}>
        <div style={{ width: 36, height: 3, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ width: `${score}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.4s ease, background 0.3s' }} />
        </div>
        <span style={{ fontSize: '0.72rem', fontWeight: 700, color, lineHeight: 1 }}>{score}</span>
      </div>

      {/* Divider */}
      <div style={{ width: 1, height: 10, background: 'var(--border)', flexShrink: 0 }} />

      {/* Segments */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'nowrap' }}>
        {seg('Model', model, true)}
        <div style={{ width: 1, height: 10, background: 'var(--border)' }} />
        {isReasoning
          ? seg('Think', thinking, true)
          : seg('Think', 'n/a', false)
        }
        <div style={{ width: 1, height: 10, background: 'var(--border)' }} />
        {seg('KB', ragEnabled ? 'on' : 'off', ragEnabled)}
        <div style={{ width: 1, height: 10, background: 'var(--border)' }} />
        {seg('Web', webSearchEnabled ? 'on' : 'off', webSearchEnabled)}
      </div>
    </div>
  );
}
