'use client';
import CallSelector from '../CallSelector';
function Field({ label, hint, children }) {
  return (
    <div style={{ display: 'grid', gap: '0.35rem' }}>
      <label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>
        {label}
        {hint && <span style={{ fontWeight: 400, color: 'var(--text-3)', marginLeft: '0.4rem' }}>{hint}</span>}
      </label>
      {children}
    </div>
  );
}
export default function FollowUpFields({ values, onChange }) {
  return (
    <>
      <Field label="Account Name *">
        <input className="input" value={values.account || ''} onChange={e => onChange('account', e.target.value)} placeholder="e.g. Acme Corp" />
      </Field>
      <Field label="To">
        <input className="input" value={values.email_to || ''} onChange={e => onChange('email_to', e.target.value)} placeholder="contact@prospect.com" />
      </Field>
      <Field label="CC">
        <input className="input" value={values.email_cc || ''} onChange={e => onChange('email_cc', e.target.value)} placeholder="se@yourcompany.com" />
      </Field>
      <Field label="Tone">
        <select className="input" value={values.email_tone || 'crisp'} onChange={e => onChange('email_tone', e.target.value)}>
          <option value="crisp">Crisp</option>
          <option value="executive">Executive</option>
          <option value="technical">Technical</option>
        </select>
      </Field>
      <Field label="Select Calls">
        <CallSelector account={values.account} selectedCalls={values.selectedCalls || []} onChange={calls => onChange('selectedCalls', calls)} />
      </Field>
      <Field label="Additional call notes" hint="(optional — paste highlights, key moments, or anything not in the transcript)">
        <textarea
          className="input"
          rows={4}
          value={values.call_notes || ''}
          onChange={e => onChange('call_notes', e.target.value)}
          placeholder="E.g. Alice confirmed they want to avoid a full migration — need a parallel-run option. Tim mentioned the board review is April 15."
          style={{ resize: 'vertical' }}
        />
      </Field>
    </>
  );
}
