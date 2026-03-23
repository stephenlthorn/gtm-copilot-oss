'use client';
function Field({ label, children }) { return <div style={{ display: 'grid', gap: '0.35rem' }}><label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>{label}</label>{children}</div>; }
export default function PreCallFields({ values, onChange }) {
  return (
    <>
      <Field label="Account Name *">
        <input className="input" value={values.account || ''} onChange={e => onChange('account', e.target.value)} placeholder="e.g. Acme Corp" />
      </Field>
      <Field label="Website">
        <input className="input" value={values.website || ''} onChange={e => onChange('website', e.target.value)} placeholder="acmecorp.com" />
      </Field>
      <Field label="Prospect Name">
        <input className="input" value={values.prospect_name || ''} onChange={e => onChange('prospect_name', e.target.value)} placeholder="Jane Smith" />
      </Field>
      <Field label="LinkedIn URL">
        <input className="input" value={values.prospect_linkedin || ''} onChange={e => onChange('prospect_linkedin', e.target.value)} placeholder="linkedin.com/in/…" />
      </Field>
    </>
  );
}
