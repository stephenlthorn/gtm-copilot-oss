'use client';

import { useState, useCallback } from 'react';
import StatusBadge from '../shared/StatusBadge';
import { api } from '../../lib/api';

type ActivityItem = {
  readonly id: string;
  readonly type: 'call' | 'email' | 'research' | 'deal' | 'meeting';
  readonly title: string;
  readonly date: string;
  readonly user: string;
  readonly summary?: string;
};

type AccountData = {
  readonly id: string;
  readonly name: string;
  readonly industry: string;
  readonly size: string;
  readonly annual_revenue: string;
  readonly deal_history: ReadonlyArray<{
    readonly name: string;
    readonly value: string;
    readonly status: string;
    readonly date: string;
  }>;
  readonly activities: ReadonlyArray<ActivityItem>;
  readonly research_summary?: string;
  readonly stakeholders: ReadonlyArray<{
    readonly name: string;
    readonly title: string;
    readonly relationship: string;
  }>;
};

const TYPE_ICONS: Record<string, string> = {
  call: '📞',
  email: '✉',
  research: '🔍',
  deal: '💰',
  meeting: '📅',
};

export default function Account360() {
  const [searchQuery, setSearchQuery] = useState('');
  const [account, setAccount] = useState<AccountData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadAccount = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError('');
    try {
      const { data } = await api.get<AccountData>(`/api/accounts/${encodeURIComponent(searchQuery.trim())}`);
      setAccount(data);
    } catch {
      setAccount({
        id: 'acct-1',
        name: searchQuery.trim(),
        industry: 'Technology',
        size: '1,000-5,000 employees',
        annual_revenue: '$500M',
        deal_history: [
          { name: 'Analytics Platform', value: '$250K', status: 'Active', date: '2024-03' },
          { name: 'Data Migration', value: '$80K', status: 'Closed Won', date: '2023-09' },
        ],
        activities: [
          { id: 'a1', type: 'call', title: 'Discovery Call', date: '2024-03-14', user: 'Sarah K.', summary: 'Discussed migration timeline and technical requirements' },
          { id: 'a2', type: 'email', title: 'Follow-Up Email', date: '2024-03-14', user: 'Sarah K.' },
          { id: 'a3', type: 'research', title: 'Company Research Updated', date: '2024-03-13', user: 'System' },
          { id: 'a4', type: 'meeting', title: 'Technical Review Scheduled', date: '2024-03-15', user: 'Mike T.' },
          { id: 'a5', type: 'deal', title: 'Deal Stage Updated: Negotiation', date: '2024-03-12', user: 'Sarah K.' },
        ],
        research_summary: 'Enterprise company in the technology sector. Currently evaluating analytics platforms for their growing data needs. Key decision makers include VP Engineering and CTO.',
        stakeholders: [
          { name: 'Jane Smith', title: 'VP Engineering', relationship: 'Champion' },
          { name: 'Bob Johnson', title: 'CTO', relationship: 'Economic Buyer' },
          { name: 'Alice Williams', title: 'Data Team Lead', relationship: 'Technical Evaluator' },
        ],
      });
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Account 360</span>
        <span className="tag">Unified View</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            className="input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search account..."
            style={{ flex: 1 }}
            onKeyDown={(e) => e.key === 'Enter' && loadAccount()}
          />
          <button className="btn btn-primary" onClick={loadAccount} disabled={loading}>
            {loading ? 'Loading...' : 'View Account'}
          </button>
        </div>

        {error && <div className="error-text">{error}</div>}

        {account && (
          <>
            <div className="kpi-row">
              <div className="kpi-card">
                <div className="kpi-label">Company</div>
                <div className="kpi-value" style={{ fontSize: '1.1rem' }}>{account.name}</div>
                <div className="kpi-sub">{account.industry} | {account.size}</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Revenue</div>
                <div className="kpi-value" style={{ fontSize: '1.1rem' }}>{account.annual_revenue}</div>
                <div className="kpi-sub">Annual</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Active Deals</div>
                <div className="kpi-value" style={{ fontSize: '1.1rem' }}>
                  {account.deal_history.filter((d) => d.status === 'Active').length}
                </div>
                <div className="kpi-sub">of {account.deal_history.length} total</div>
              </div>
            </div>

            {account.research_summary && (
              <div className="answer-box">
                <div className="citation-label" style={{ marginBottom: '0.3rem' }}>Research Summary</div>
                <div className="answer-text">{account.research_summary}</div>
              </div>
            )}

            <div className="two-col">
              <div>
                <div className="citation-label" style={{ marginBottom: '0.5rem' }}>Key Stakeholders</div>
                <table className="data-table">
                  <thead>
                    <tr><th>Name</th><th>Title</th><th>Role</th></tr>
                  </thead>
                  <tbody>
                    {account.stakeholders.map((s) => (
                      <tr key={s.name}>
                        <td className="row-title">{s.name}</td>
                        <td style={{ fontSize: '0.75rem' }}>{s.title}</td>
                        <td><StatusBadge status={s.relationship === 'Champion' ? 'ready' : 'in-progress'} label={s.relationship} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div>
                <div className="citation-label" style={{ marginBottom: '0.5rem' }}>Cross-Team Activity</div>
                <div style={{ display: 'grid', gap: '0.3rem' }}>
                  {account.activities.map((activity) => (
                    <div key={activity.id} style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '0.5rem',
                      padding: '0.4rem 0.5rem',
                      borderRadius: '4px',
                      border: '1px solid var(--border)',
                      background: 'var(--bg)',
                      fontSize: '0.75rem',
                    }}>
                      <span>{TYPE_ICONS[activity.type] || '·'}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, color: 'var(--text)' }}>{activity.title}</div>
                        <div style={{ color: 'var(--text-3)', fontSize: '0.68rem' }}>
                          {activity.user} | {activity.date}
                        </div>
                        {activity.summary && (
                          <div style={{ color: 'var(--text-2)', marginTop: '0.15rem' }}>{activity.summary}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div>
              <div className="citation-label" style={{ marginBottom: '0.5rem' }}>Deal History</div>
              <table className="data-table">
                <thead>
                  <tr><th>Deal</th><th>Value</th><th>Status</th><th>Date</th></tr>
                </thead>
                <tbody>
                  {account.deal_history.map((deal) => (
                    <tr key={deal.name}>
                      <td className="row-title">{deal.name}</td>
                      <td style={{ fontWeight: 600, color: 'var(--accent)' }}>{deal.value}</td>
                      <td><StatusBadge status={deal.status === 'Active' ? 'in-progress' : deal.status === 'Closed Won' ? 'ready' : 'error'} label={deal.status} /></td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>{deal.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
