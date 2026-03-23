'use client';
import CallSelector from '../CallSelector';
function Field({ label, children }) { return <div style={{ display: 'grid', gap: '0.35rem' }}><label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>{label}</label>{children}</div>; }
export default function SECompetitorFields({ values, onChange }) {
  return (
    <>
      <Field label="Account Name *">
        <input className="input" value={values.account || ''} onChange={e => onChange('account', e.target.value)} placeholder="e.g. Acme Corp" />
      </Field>
      <Field label="Competitor">
        <input className="input" value={values.competitor || ''} onChange={e => onChange('competitor', e.target.value)} placeholder="e.g. CockroachDB, Aurora" />
      </Field>
      <Field label="Select Calls">
        <CallSelector account={values.account} selectedCalls={values.selectedCalls || []} onChange={calls => onChange('selectedCalls', calls)} />
      </Field>
    </>
  );
}
