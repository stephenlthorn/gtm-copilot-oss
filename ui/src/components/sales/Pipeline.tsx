'use client';

import { useState, useEffect } from 'react';
import StatusBadge from '../shared/StatusBadge';
import { api } from '../../lib/api';

type Deal = {
  readonly id: string;
  readonly name: string;
  readonly account: string;
  readonly value: number;
  readonly stage: string;
  readonly probability: number;
  readonly close_date: string;
  readonly risk_flags: ReadonlyArray<string>;
  readonly owner: string;
  readonly velocity_days: number;
};

type PipelineStats = {
  readonly total_value: number;
  readonly deals_at_risk: number;
  readonly avg_velocity: number;
  readonly total_deals: number;
};

type ViewMode = 'table' | 'kanban';

const STAGES = ['Prospecting', 'Discovery', 'Proposal', 'Negotiation', 'Closed Won', 'Closed Lost'] as const;

function formatCurrency(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`;
  return `$${value}`;
}

function KanbanView({ deals }: { readonly deals: ReadonlyArray<Deal> }) {
  const dealsByStage = STAGES.map((stage) => ({
    stage,
    deals: deals.filter((d) => d.stage === stage),
    total: deals.filter((d) => d.stage === stage).reduce((sum, d) => sum + d.value, 0),
  }));

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${STAGES.length}, minmax(180px, 1fr))`,
      gap: '0.5rem',
      overflowX: 'auto',
    }}>
      {dealsByStage.map(({ stage, deals: stagDeals, total }) => (
        <div key={stage} style={{
          border: '1px solid var(--border)',
          borderRadius: '6px',
          background: 'var(--bg)',
          minHeight: '200px',
        }}>
          <div style={{
            padding: '0.5rem 0.6rem',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text)' }}>{stage}</span>
            <span style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>{formatCurrency(total)}</span>
          </div>
          <div style={{ padding: '0.4rem', display: 'grid', gap: '0.35rem' }}>
            {stagDeals.map((deal) => (
              <div key={deal.id} style={{
                padding: '0.45rem 0.55rem',
                border: '1px solid var(--border)',
                borderRadius: '4px',
                background: 'var(--panel)',
                fontSize: '0.75rem',
              }}>
                <div style={{ fontWeight: 600, color: 'var(--text)', marginBottom: '0.15rem' }}>{deal.name}</div>
                <div style={{ color: 'var(--text-3)', fontSize: '0.68rem' }}>{deal.account}</div>
                <div style={{ color: 'var(--accent)', fontWeight: 600, marginTop: '0.2rem' }}>
                  {formatCurrency(deal.value)}
                </div>
                {deal.risk_flags.length > 0 && (
                  <div style={{ marginTop: '0.2rem' }}>
                    {deal.risk_flags.map((flag) => (
                      <span key={flag} className="tag tag-red" style={{ fontSize: '0.6rem', marginRight: '0.2rem' }}>
                        {flag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Pipeline() {
  const [deals, setDeals] = useState<ReadonlyArray<Deal>>([]);
  const [stats, setStats] = useState<PipelineStats>({ total_value: 0, deals_at_risk: 0, avg_velocity: 0, total_deals: 0 });
  const [viewMode, setViewMode] = useState<ViewMode>('table');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadPipeline = async () => {
      setLoading(true);
      try {
        const { data } = await api.get<{ deals: ReadonlyArray<Deal>; stats: PipelineStats }>('/api/pipeline');
        setDeals(data.deals);
        setStats(data.stats);
      } catch {
        const fallbackDeals: ReadonlyArray<Deal> = [
          { id: 'd1', name: 'Enterprise Analytics', account: 'Acme Corp', value: 250000, stage: 'Negotiation', probability: 75, close_date: '2024-04-15', risk_flags: ['Champion left'], owner: 'Sarah K.', velocity_days: 45 },
          { id: 'd2', name: 'Platform Migration', account: 'Globex Inc', value: 180000, stage: 'Proposal', probability: 50, close_date: '2024-05-01', risk_flags: [], owner: 'Mike T.', velocity_days: 30 },
          { id: 'd3', name: 'Data Warehouse', account: 'Initech', value: 420000, stage: 'Discovery', probability: 30, close_date: '2024-06-01', risk_flags: ['No technical eval', 'Budget TBD'], owner: 'Sarah K.', velocity_days: 15 },
          { id: 'd4', name: 'Real-Time Pipeline', account: 'Umbrella Corp', value: 95000, stage: 'Prospecting', probability: 15, close_date: '2024-07-01', risk_flags: [], owner: 'James R.', velocity_days: 5 },
          { id: 'd5', name: 'Analytics Expansion', account: 'Wayne Ent', value: 320000, stage: 'Closed Won', probability: 100, close_date: '2024-03-01', risk_flags: [], owner: 'Mike T.', velocity_days: 60 },
        ];
        setDeals(fallbackDeals);
        const atRisk = fallbackDeals.filter((d) => d.risk_flags.length > 0).length;
        const avgVel = Math.round(fallbackDeals.reduce((s, d) => s + d.velocity_days, 0) / fallbackDeals.length);
        setStats({
          total_value: fallbackDeals.reduce((s, d) => s + d.value, 0),
          deals_at_risk: atRisk,
          avg_velocity: avgVel,
          total_deals: fallbackDeals.length,
        });
      } finally {
        setLoading(false);
      }
    };
    loadPipeline();
  }, []);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Pipeline</span>
        <div style={{ display: 'flex', gap: '0.3rem' }}>
          <button
            className={`btn ${viewMode === 'table' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setViewMode('table')}
            style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          >
            Table
          </button>
          <button
            className={`btn ${viewMode === 'kanban' ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setViewMode('kanban')}
            style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
          >
            Kanban
          </button>
        </div>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div className="kpi-row">
          <div className="kpi-card">
            <div className="kpi-label">Total Pipeline</div>
            <div className="kpi-value">{formatCurrency(stats.total_value)}</div>
            <div className="kpi-sub">{stats.total_deals} deals</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Deals at Risk</div>
            <div className="kpi-value" style={{ color: stats.deals_at_risk > 0 ? 'var(--danger)' : 'var(--success)' }}>
              {stats.deals_at_risk}
            </div>
            <div className="kpi-sub">flagged deals</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Avg Velocity</div>
            <div className="kpi-value">{stats.avg_velocity}d</div>
            <div className="kpi-sub">days in pipeline</div>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-3)' }}>Loading pipeline...</div>
        ) : viewMode === 'kanban' ? (
          <KanbanView deals={deals} />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Deal</th>
                <th>Account</th>
                <th>Value</th>
                <th>Stage</th>
                <th>Probability</th>
                <th>Close Date</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {deals.map((deal) => (
                <tr key={deal.id}>
                  <td className="row-title">{deal.name}</td>
                  <td>{deal.account}</td>
                  <td style={{ fontWeight: 600, color: 'var(--accent)' }}>{formatCurrency(deal.value)}</td>
                  <td><StatusBadge status={deal.stage === 'Closed Won' ? 'ready' : deal.stage === 'Closed Lost' ? 'error' : 'in-progress'} label={deal.stage} /></td>
                  <td>{deal.probability}%</td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>{deal.close_date}</td>
                  <td>
                    {deal.risk_flags.length > 0 ? (
                      deal.risk_flags.map((flag) => (
                        <span key={flag} className="tag tag-red" style={{ fontSize: '0.6rem', marginRight: '0.2rem', display: 'inline-block', marginBottom: '0.15rem' }}>
                          {flag}
                        </span>
                      ))
                    ) : (
                      <span style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
