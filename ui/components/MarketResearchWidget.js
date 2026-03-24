'use client';

import { useState } from 'react';
import FeedbackButtons from './FeedbackButtons';

const TEMPLATE_CURRENT_CUSTOMERS = 'account,region,industry,current_platform,use_case,arr';
const TEMPLATE_PIPELINE = 'account,region,stage,industry,workload,est_arr,close_quarter,competing_vendor';

export default function MarketResearchWidget() {
  const [goal, setGoal] = useState('Build an execution-ready strategic account list for this territory.');
  const [territory, setTerritory] = useState('');
  const [currentCsv, setCurrentCsv] = useState('');
  const [pipelineCsv, setPipelineCsv] = useState('');
  const [additionalContext, setAdditionalContext] = useState('');
  const [topN, setTopN] = useState(8);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const fillSample = () => {
    setCurrentCsv(TEMPLATE_CURRENT_CUSTOMERS);
    setPipelineCsv(TEMPLATE_PIPELINE);
    setAdditionalContext(
      'Rep capacity, must-win accounts, and executive priorities.'
    );
    setError('');
  };

  const generate = async () => {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const regions = territory.split(',').map(r => r.trim()).filter(Boolean);
      const res = await fetch('/api/rep/market-research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategic_goal: goal,
          regions,
          current_customers_csv: currentCsv,
          pipeline_csv: pipelineCsv,
          additional_context: additionalContext,
          top_n: Number(topN) || 8,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || data?.error || 'Failed to generate strategy');
      setResult(data);
    } catch (err) {
      setError(String(err?.message || err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Market Research Strategist</span>
        <span className="tag tag-orange">Sales Rep</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <p style={{ color: 'var(--text-2)', fontSize: '0.78rem' }}>
          Use this to turn customer + pipeline data into an East/Central strategic execution list.
        </p>

        <div style={{ border: '1px solid var(--border)', borderRadius: '4px', padding: '0.6rem' }}>
          <div style={{ color: 'var(--text-3)', fontSize: '0.72rem', marginBottom: '0.45rem' }}>Input Checklist</div>
          <ul style={{ margin: 0, paddingLeft: '1rem', display: 'grid', gap: '0.2rem', color: 'var(--text-2)', fontSize: '0.75rem' }}>
            <li>Current customers CSV: account, region, industry, current_platform, use_case, arr</li>
            <li>Pipeline CSV: account, region, stage, industry, workload, est_arr, close_quarter, competing_vendor</li>
            <li>Strategic goal and optional context (team capacity, must-win deals, executive asks)</li>
          </ul>
        </div>

        <div style={{ display: 'grid', gap: '0.35rem' }}>
          <label htmlFor="strategy-goal" style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Strategic Goal</label>
          <textarea
            id="strategy-goal"
            className="input"
            rows={2}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ display: 'grid', gap: '0.3rem', flex: 1 }}>
            <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Territory (comma-separated)</label>
            <input
              className="input"
              value={territory}
              onChange={(e) => setTerritory(e.target.value)}
              placeholder="East, Central, APAC, EMEA…"
            />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.76rem', whiteSpace: 'nowrap' }}>
            Top N
            <input
              className="input"
              type="number"
              min={1}
              max={20}
              value={topN}
              onChange={(e) => setTopN(e.target.value)}
              style={{ width: '4.5rem' }}
            />
          </label>
        </div>

        <div className="two-col">
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label htmlFor="current-customers" style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Current Customers CSV</label>
            <textarea
              id="current-customers"
              className="input"
              rows={8}
              value={currentCsv}
              onChange={(e) => setCurrentCsv(e.target.value)}
              placeholder="Paste CSV with required headers..."
            />
          </div>
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label htmlFor="pipeline-csv" style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Pipeline CSV</label>
            <textarea
              id="pipeline-csv"
              className="input"
              rows={8}
              value={pipelineCsv}
              onChange={(e) => setPipelineCsv(e.target.value)}
              placeholder="Paste CSV with required headers..."
            />
          </div>
        </div>

        <div style={{ display: 'grid', gap: '0.35rem' }}>
          <label htmlFor="additional-context" style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Additional Context (optional)</label>
          <textarea
            id="additional-context"
            className="input"
            rows={3}
            value={additionalContext}
            onChange={(e) => setAdditionalContext(e.target.value)}
            placeholder="Capacity constraints, must-win accounts, leadership asks, etc."
          />
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button className="btn" onClick={fillSample}>Insert CSV Templates</button>
          <button className="btn btn-primary" onClick={generate} disabled={loading}>
            {loading ? 'Generating…' : 'Generate Strategic List'}
          </button>
        </div>

        {error && <div className="error-text">{error}</div>}

        {result && (
          <div className="answer-box" style={{ display: 'grid', gap: '0.65rem' }}>
            <div className="answer-text">{result.summary}</div>

            {Array.isArray(result.required_inputs) && result.required_inputs.length > 0 && (
              <div>
                <div className="citation-label">Still Needed</div>
                <ul className="citation-list">
                  {result.required_inputs.map((item, idx) => <li key={idx}>{item}</li>)}
                </ul>
              </div>
            )}

            {Array.isArray(result.priority_accounts) && result.priority_accounts.length > 0 && (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Account</th>
                      <th>Type</th>
                      <th>Region</th>
                      <th>Priority</th>
                      <th>Why Now + Actions</th>
                      <th>Suggested Assets</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.priority_accounts.map((item, idx) => (
                      <tr key={`${item.account}-${idx}`}>
                        <td className="row-title">{item.account}</td>
                        <td>{item.motion_type}</td>
                        <td>{item.region}</td>
                        <td style={{ color: item.priority === 'High' ? 'var(--accent)' : 'var(--text-2)' }}>{item.priority}</td>
                        <td style={{ minWidth: '300px' }}>
                          <div style={{ marginBottom: '0.3rem' }}>{item.why_now}</div>
                          {Array.isArray(item.actions) && item.actions.length > 0 && (
                            <ul style={{ margin: '0.25rem 0 0 1rem', padding: 0, fontSize: '0.72rem', color: 'var(--text-3)' }}>
                              {item.actions.slice(0, 3).map((a, i) => <li key={i}>{a}</li>)}
                            </ul>
                          )}
                        </td>
                        <td style={{ minWidth: '180px', fontSize: '0.72rem', color: 'var(--text-3)' }}>
                          {Array.isArray(item.suggested_assets) && item.suggested_assets.length > 0
                            ? item.suggested_assets.slice(0, 3).join(', ')
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {Array.isArray(result.execution_plan) && result.execution_plan.length > 0 && (
              <div>
                <div className="citation-label">Execution Plan</div>
                <ul className="citation-list">
                  {result.execution_plan.map((item, idx) => <li key={idx}>{item}</li>)}
                </ul>
              </div>
            )}
            <FeedbackButtons mode="oracle" queryText={goal} originalResponse={result} />
          </div>
        )}
      </div>
    </div>
  );
}
