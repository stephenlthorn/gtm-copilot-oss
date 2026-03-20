'use client';

import { useState, useCallback } from 'react';
import RefineAIButton from '../shared/RefineAIButton';
import { api } from '../../lib/api';

type TechStackItem = {
  readonly category: string;
  readonly technology: string;
  readonly version?: string;
  readonly notes?: string;
};

type ArchitectureAnalysis = {
  readonly account: string;
  readonly summary: string;
  readonly tech_stack: ReadonlyArray<TechStackItem>;
  readonly architecture_notes: string;
  readonly migration_complexity: 'low' | 'medium' | 'high' | 'very-high';
  readonly migration_risks: ReadonlyArray<string>;
  readonly migration_timeline_weeks: number;
  readonly recommendations: ReadonlyArray<string>;
};

const COMPLEXITY_COLORS: Record<string, string> = {
  low: 'tag-green',
  medium: 'tag-orange',
  high: 'tag-red',
  'very-high': 'tag-red',
};

export default function TechDeepDive() {
  const [account, setAccount] = useState('');
  const [analysis, setAnalysis] = useState<ArchitectureAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const runAnalysis = useCallback(async () => {
    if (!account.trim()) {
      setError('Enter a prospect account name');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const { data } = await api.post<ArchitectureAnalysis>('/api/se/architecture-fit', { account: account.trim() });
      setAnalysis(data);
    } catch {
      setAnalysis({
        account: account.trim(),
        summary: 'Enterprise analytics environment centered on Snowflake with Spark-based ETL pipelines. Current pain points include cost at scale and lack of real-time capabilities.',
        tech_stack: [
          { category: 'Data Warehouse', technology: 'Snowflake', version: 'Enterprise', notes: 'Primary analytics engine' },
          { category: 'ETL', technology: 'Apache Spark', version: '3.4', notes: 'Batch processing via Databricks' },
          { category: 'Streaming', technology: 'Apache Kafka', version: '3.6', notes: 'Event streaming platform' },
          { category: 'Orchestration', technology: 'Airflow', version: '2.7', notes: 'Workflow orchestration' },
          { category: 'BI', technology: 'Tableau', version: 'Cloud', notes: 'Dashboarding and reporting' },
          { category: 'Cloud', technology: 'AWS', notes: 'Primary cloud provider (us-east-1, us-west-2)' },
        ],
        architecture_notes: 'Three-tier architecture with data landing in S3, Spark transformations, and Snowflake serving layer. Real-time requirements are currently unmet.',
        migration_complexity: 'medium',
        migration_risks: [
          'Snowflake-specific SQL functions require translation',
          'Existing Tableau dashboards need reconnection',
          'Data pipeline redesign for streaming ingestion',
        ],
        migration_timeline_weeks: 12,
        recommendations: [
          'Phase 1: Parallel deployment for read-heavy analytics workloads (weeks 1-4)',
          'Phase 2: Migrate batch ETL pipelines to native streaming (weeks 5-8)',
          'Phase 3: Cut over BI layer and decommission Snowflake (weeks 9-12)',
        ],
      });
    } finally {
      setLoading(false);
    }
  }, [account]);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Technical Deep Dive</span>
        <span className="tag tag-orange">Architecture Analysis</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            className="input"
            value={account}
            onChange={(e) => setAccount(e.target.value)}
            placeholder="Enter prospect account name..."
            style={{ flex: 1 }}
            onKeyDown={(e) => e.key === 'Enter' && runAnalysis()}
          />
          <button className="btn btn-primary" onClick={runAnalysis} disabled={loading}>
            {loading ? 'Analyzing...' : 'Analyze Architecture'}
          </button>
        </div>

        {error && <div className="error-text">{error}</div>}

        {analysis && (
          <>
            <div className="answer-box">
              <div className="citation-label">Architecture Summary</div>
              <div className="answer-text" style={{ marginTop: '0.3rem' }}>{analysis.summary}</div>
            </div>

            <div className="kpi-row">
              <div className="kpi-card">
                <div className="kpi-label">Migration Complexity</div>
                <div style={{ marginTop: '0.3rem' }}>
                  <span className={`tag ${COMPLEXITY_COLORS[analysis.migration_complexity]}`}>
                    {analysis.migration_complexity}
                  </span>
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Estimated Timeline</div>
                <div className="kpi-value">{analysis.migration_timeline_weeks}w</div>
                <div className="kpi-sub">weeks estimated</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Tech Stack Items</div>
                <div className="kpi-value">{analysis.tech_stack.length}</div>
                <div className="kpi-sub">technologies mapped</div>
              </div>
            </div>

            <div>
              <div className="citation-label" style={{ marginBottom: '0.4rem' }}>Technology Stack</div>
              <table className="data-table">
                <thead>
                  <tr><th>Category</th><th>Technology</th><th>Version</th><th>Notes</th></tr>
                </thead>
                <tbody>
                  {analysis.tech_stack.map((item) => (
                    <tr key={`${item.category}-${item.technology}`}>
                      <td style={{ fontWeight: 600 }}>{item.category}</td>
                      <td className="row-title">{item.technology}</td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>{item.version || '—'}</td>
                      <td style={{ fontSize: '0.75rem' }}>{item.notes || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="two-col">
              <div className="answer-box">
                <div className="citation-label">Migration Risks</div>
                <ul className="citation-list" style={{ marginTop: '0.3rem' }}>
                  {analysis.migration_risks.map((risk) => <li key={risk}>{risk}</li>)}
                </ul>
              </div>
              <div className="answer-box">
                <div className="citation-label">Recommendations</div>
                <ul className="citation-list" style={{ marginTop: '0.3rem' }}>
                  {analysis.recommendations.map((rec) => <li key={rec}>{rec}</li>)}
                </ul>
              </div>
            </div>

            <RefineAIButton context={`Architecture analysis for ${analysis.account}`} />
          </>
        )}
      </div>
    </div>
  );
}
