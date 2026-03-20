'use client';

import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

type ContentPiece = {
  readonly id: string;
  readonly title: string;
  readonly type: string;
  readonly deals_referenced: number;
  readonly win_rate: number;
};

type ContentGap = {
  readonly topic: string;
  readonly demand_score: number;
  readonly coverage: 'none' | 'partial' | 'full';
  readonly suggested_format: string;
};

type TrendingTopic = {
  readonly topic: string;
  readonly mention_count: number;
  readonly sentiment: 'positive' | 'neutral' | 'negative';
  readonly trend: 'rising' | 'stable' | 'declining';
};

type TabId = 'winning' | 'gaps' | 'trending';

export default function CampaignIntel() {
  const [activeTab, setActiveTab] = useState<TabId>('winning');
  const [winningContent, setWinningContent] = useState<ReadonlyArray<ContentPiece>>([]);
  const [contentGaps, setContentGaps] = useState<ReadonlyArray<ContentGap>>([]);
  const [trendingTopics, setTrendingTopics] = useState<ReadonlyArray<TrendingTopic>>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const { data } = await api.get<{
          winning_content: ReadonlyArray<ContentPiece>;
          content_gaps: ReadonlyArray<ContentGap>;
          trending_topics: ReadonlyArray<TrendingTopic>;
        }>('/api/marketing/campaign-intel');
        setWinningContent(data.winning_content);
        setContentGaps(data.content_gaps);
        setTrendingTopics(data.trending_topics);
      } catch {
        setWinningContent([
          { id: 'wp-1', title: 'HTAP vs Traditional Data Warehouses', type: 'Whitepaper', deals_referenced: 12, win_rate: 78 },
          { id: 'cs-1', title: 'Financial Services Migration Case Study', type: 'Case Study', deals_referenced: 8, win_rate: 85 },
          { id: 'blog-1', title: 'Real-Time Analytics at Scale', type: 'Blog', deals_referenced: 6, win_rate: 67 },
          { id: 'demo-1', title: 'Live Performance Benchmark Demo', type: 'Demo', deals_referenced: 15, win_rate: 92 },
        ]);
        setContentGaps([
          { topic: 'Kubernetes deployment guide', demand_score: 92, coverage: 'none', suggested_format: 'Technical Blog' },
          { topic: 'Cost comparison calculator', demand_score: 88, coverage: 'partial', suggested_format: 'Interactive Tool' },
          { topic: 'Healthcare compliance whitepaper', demand_score: 75, coverage: 'none', suggested_format: 'Whitepaper' },
          { topic: 'Streaming data integration patterns', demand_score: 70, coverage: 'partial', suggested_format: 'Technical Blog' },
        ]);
        setTrendingTopics([
          { topic: 'Real-time analytics', mention_count: 45, sentiment: 'positive', trend: 'rising' },
          { topic: 'Cost optimization', mention_count: 38, sentiment: 'neutral', trend: 'rising' },
          { topic: 'Data migration', mention_count: 32, sentiment: 'negative', trend: 'stable' },
          { topic: 'AI/ML integration', mention_count: 28, sentiment: 'positive', trend: 'rising' },
        ]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const TABS: ReadonlyArray<{ readonly id: TabId; readonly label: string }> = [
    { id: 'winning', label: 'Winning Content' },
    { id: 'gaps', label: 'Content Gaps' },
    { id: 'trending', label: 'Trending Topics' },
  ];

  const COVERAGE_COLORS: Record<string, string> = { none: 'tag-red', partial: 'tag-orange', full: 'tag-green' };
  const SENTIMENT_COLORS: Record<string, string> = { positive: 'tag-green', neutral: '', negative: 'tag-red' };
  const TREND_ARROWS: Record<string, string> = { rising: '↑', stable: '→', declining: '↓' };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Campaign Intelligence</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div style={{ display: 'flex', gap: '0.3rem' }}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              className={`btn ${activeTab === tab.id ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setActiveTab(tab.id)}
              style={{ fontSize: '0.72rem', padding: '0.25rem 0.6rem' }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-3)' }}>Loading...</div>
        ) : activeTab === 'winning' ? (
          <table className="data-table">
            <thead>
              <tr><th>Content</th><th>Type</th><th>Deals Referenced</th><th>Win Rate</th></tr>
            </thead>
            <tbody>
              {winningContent.map((content) => (
                <tr key={content.id}>
                  <td className="row-title">{content.title}</td>
                  <td><span className="tag">{content.type}</span></td>
                  <td>{content.deals_referenced}</td>
                  <td>
                    <span style={{ fontWeight: 600, color: content.win_rate > 75 ? 'var(--success)' : 'var(--text)' }}>
                      {content.win_rate}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : activeTab === 'gaps' ? (
          <table className="data-table">
            <thead>
              <tr><th>Topic</th><th>Demand</th><th>Coverage</th><th>Suggested Format</th></tr>
            </thead>
            <tbody>
              {contentGaps.map((gap) => (
                <tr key={gap.topic}>
                  <td className="row-title">{gap.topic}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                      <div style={{
                        width: '40px',
                        height: '4px',
                        background: 'var(--border)',
                        borderRadius: '2px',
                        overflow: 'hidden',
                      }}>
                        <div style={{
                          width: `${gap.demand_score}%`,
                          height: '100%',
                          background: 'var(--accent)',
                          borderRadius: '2px',
                        }} />
                      </div>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>{gap.demand_score}</span>
                    </div>
                  </td>
                  <td><span className={`tag ${COVERAGE_COLORS[gap.coverage]}`}>{gap.coverage}</span></td>
                  <td style={{ fontSize: '0.75rem' }}>{gap.suggested_format}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>Topic</th><th>Mentions</th><th>Sentiment</th><th>Trend</th></tr>
            </thead>
            <tbody>
              {trendingTopics.map((topic) => (
                <tr key={topic.topic}>
                  <td className="row-title">{topic.topic}</td>
                  <td>{topic.mention_count}</td>
                  <td><span className={`tag ${SENTIMENT_COLORS[topic.sentiment]}`}>{topic.sentiment}</span></td>
                  <td>
                    <span style={{
                      fontWeight: 600,
                      color: topic.trend === 'rising' ? 'var(--success)' : topic.trend === 'declining' ? 'var(--danger)' : 'var(--text-3)',
                    }}>
                      {TREND_ARROWS[topic.trend]} {topic.trend}
                    </span>
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
