'use client';
function Field({ label, children }) { return <div style={{ display: 'grid', gap: '0.35rem' }}><label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>{label}</label>{children}</div>; }
export default function TalFields({ values, onChange }) {
  return (
    <>
      <Field label="Reference Account *">
        <input className="input" value={values.account || ''} onChange={e => onChange('account', e.target.value)} placeholder="e.g. Acme Corp" />
      </Field>
      <Field label="Regions / Territory">
        <input className="input" value={values.regions || ''} onChange={e => onChange('regions', e.target.value)} placeholder="US West, APAC" />
      </Field>
      <Field label="Industry Vertical">
        <input className="input" value={values.industry || ''} onChange={e => onChange('industry', e.target.value)} placeholder="FinTech, SaaS…" />
      </Field>
      <Field label="Revenue Min ($M)">
        <input className="input" type="number" value={values.revenue_min || ''} onChange={e => onChange('revenue_min', e.target.value)} placeholder="50" />
      </Field>
      <Field label="Revenue Max ($M)">
        <input className="input" type="number" value={values.revenue_max || ''} onChange={e => onChange('revenue_max', e.target.value)} placeholder="500" />
      </Field>
      <Field label="Additional Context">
        <textarea className="input" rows={2} value={values.context || ''} onChange={e => onChange('context', e.target.value)} placeholder="Companies using MySQL at scale…" style={{ minHeight: '56px' }} />
      </Field>
      <Field label="Top N Accounts">
        <input className="input" type="number" min={5} max={100} value={values.top_n || '25'} onChange={e => onChange('top_n', e.target.value)} />
      </Field>
    </>
  );
}
