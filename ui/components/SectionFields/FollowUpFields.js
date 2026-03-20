'use client';
import CallSelector from '../CallSelector';
function Field({ label, children }) { return <div style={{ display: 'grid', gap: '0.35rem' }}><label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>{label}</label>{children}</div>; }
export default function FollowUpFields({ values, onChange }) {
  return (
    <>
      <Field label="Account Name *">
        <input className="input" value={values.account || ''} onChange={e => onChange('account', e.target.value)} placeholder="e.g. Acme Corp" />
      </Field>
      <Field label="To">
        <input className="input" value={values.email_to || ''} onChange={e => onChange('email_to', e.target.value)} placeholder="rep@company.com" />
      </Field>
      <Field label="CC">
        <input className="input" value={values.email_cc || ''} onChange={e => onChange('email_cc', e.target.value)} placeholder="se@company.com" />
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
    </>
  );
}
