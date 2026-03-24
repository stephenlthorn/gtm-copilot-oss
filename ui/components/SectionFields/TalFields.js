'use client';
function Field({ label, children }) { return <div style={{ display: 'grid', gap: '0.35rem' }}><label style={{ fontSize: '0.75rem', color: 'var(--text-2)', fontWeight: 500 }}>{label}</label>{children}</div>; }
export default function TalFields({ values, onChange }) {
  return (
    <>
      <Field label="ICP Description *">
        <textarea className="input" rows={3} value={values.icp_description || ''} onChange={e => onChange('icp_description', e.target.value)} placeholder="e.g. High-growth fintech and e-commerce companies likely hitting MySQL scaling limits — transactional workloads >10K QPS, MySQL sharding pain, or active HTAP requirements" style={{ minHeight: '72px' }} />
      </Field>
      <Field label="Regions / Territory *">
        <input className="input" value={values.regions || ''} onChange={e => onChange('regions', e.target.value)} placeholder="US West, APAC, EMEA…" />
      </Field>
      <Field label="Industry Vertical *">
        <input className="input" value={values.industry || ''} onChange={e => onChange('industry', e.target.value)} placeholder="FinTech, SaaS, E-commerce…" />
      </Field>
      <Field label="Revenue Min ($M)">
        <input className="input" type="number" value={values.revenue_min || ''} onChange={e => onChange('revenue_min', e.target.value)} placeholder="50" />
      </Field>
      <Field label="Revenue Max ($M)">
        <input className="input" type="number" value={values.revenue_max || ''} onChange={e => onChange('revenue_max', e.target.value)} placeholder="999" />
      </Field>
      <Field label="Additional Constraints (optional)">
        <textarea className="input" rows={2} value={values.context || ''} onChange={e => onChange('context', e.target.value)} placeholder="Rep capacity, must-win accounts, executive priorities, known competitors to displace…" style={{ minHeight: '56px' }} />
      </Field>
      <Field label="Top N Accounts">
        <input className="input" type="number" min={5} max={100} value={values.top_n || '25'} onChange={e => onChange('top_n', e.target.value)} />
      </Field>
    </>
  );
}
