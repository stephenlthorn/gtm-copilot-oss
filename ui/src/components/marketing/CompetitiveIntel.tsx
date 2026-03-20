'use client';

import { useState, useEffect } from 'react';
import RefineAIButton from '../shared/RefineAIButton';
import { api } from '../../lib/api';

type Competitor = {
  readonly id: string;
  readonly name: string;
  readonly category: string;
  readonly strengths: ReadonlyArray<string>;
  readonly weaknesses: ReadonlyArray<string>;
  readonly recent_moves: ReadonlyArray<string>;
  readonly threat_level: 'high' | 'medium' | 'low';
};

type BattleCard = {
  readonly competitor: string;
  readonly when_they_lead: string;
  readonly when_we_win: string;
  readonly key_differentiators: ReadonlyArray<string>;
  readonly objection_handlers: ReadonlyArray<{ readonly objection: string; readonly response: string }>;
};

type ViewMode = 'landscape' | 'battlecard' | 'alerts';

const THREAT_COLORS: Record<string, string> = {
  high: 'tag-red',
  medium: 'tag-orange',
  low: 'tag-green',
};

export default function CompetitiveIntel() {
  const [competitors, setCompetitors] = useState<ReadonlyArray<Competitor>>([]);
  const [selectedCompetitor, setSelectedCompetitor] = useState<string | null>(null);
  const [battleCard, setBattleCard] = useState<BattleCard | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('landscape');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const { data } = await api.get<ReadonlyArray<Competitor>>('/api/marketing/competitors');
        setCompetitors(data);
      } catch {
        setCompetitors([
          {
            id: 'comp-1', name: 'Snowflake', category: 'Cloud Data Warehouse',
            strengths: ['Market leader', 'Strong ecosystem', 'Easy scaling'],
            weaknesses: ['Cost at scale', 'Limited real-time', 'No HTAP'],
            recent_moves: ['Launched new Cortex AI features', 'Partnership with Nvidia'],
            threat_level: 'high',
          },
          {
            id: 'comp-2', name: 'Databricks', category: 'Lakehouse Platform',
            strengths: ['Unified analytics', 'Open source roots', 'Strong ML'],
            weaknesses: ['Complexity', 'Cost management', 'Query performance'],
            recent_moves: ['Released Unity Catalog', 'Expanded AI integrations'],
            threat_level: 'high',
          },
          {
            id: 'comp-3', name: 'BigQuery', category: 'Cloud Analytics',
            strengths: ['Google ecosystem', 'Serverless', 'ML integration'],
            weaknesses: ['Vendor lock-in', 'Cost visibility', 'Limited OLTP'],
            recent_moves: ['Duet AI integration', 'Pricing model changes'],
            threat_level: 'medium',
          },
        ]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const loadBattleCard = async (competitorName: string) => {
    setSelectedCompetitor(competitorName);
    try {
      const { data } = await api.get<BattleCard>(`/api/marketing/battlecard/${encodeURIComponent(competitorName)}`);
      setBattleCard(data);
    } catch {
      setBattleCard({
        competitor: competitorName,
        when_they_lead: 'When customer is deeply invested in their ecosystem and has limited real-time requirements.',
        when_we_win: 'When customer needs HTAP capabilities, real-time analytics, and cost-effective scaling for large datasets.',
        key_differentiators: [
          'True HTAP: transactional + analytical in one system',
          'Horizontal scalability without data resharding',
          'Lower TCO at scale (40TB+ workloads)',
          'Real-time analytics with sub-second latency',
        ],
        objection_handlers: [
          { objection: 'We already use their ecosystem', response: 'Our platform integrates seamlessly and can serve as the analytical layer alongside existing systems.' },
          { objection: 'They have more market presence', response: 'We focus on specific use cases where we deliver 3-5x better performance at 40% lower cost.' },
        ],
      });
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Competitive Intelligence</span>
        <div style={{ display: 'flex', gap: '0.3rem' }}>
          {(['landscape', 'battlecard', 'alerts'] as const).map((mode) => (
            <button
              key={mode}
              className={`btn ${viewMode === mode ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setViewMode(mode)}
              style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem', textTransform: 'capitalize' }}
            >
              {mode === 'battlecard' ? 'Battle Cards' : mode === 'alerts' ? 'Alerts' : 'Landscape'}
            </button>
          ))}
        </div>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        {loading ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-3)' }}>Loading competitive data...</div>
        ) : viewMode === 'landscape' ? (
          <div className="three-col">
            {competitors.map((comp) => (
              <div key={comp.id} style={{
                border: '1px solid var(--border)',
                borderRadius: '6px',
                background: 'var(--bg)',
                padding: '0.75rem',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--text)' }}>{comp.name}</div>
                  <span className={`tag ${THREAT_COLORS[comp.threat_level]}`}>{comp.threat_level}</span>
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-3)', marginBottom: '0.5rem' }}>{comp.category}</div>

                <div className="citation-label" style={{ marginBottom: '0.2rem' }}>Strengths</div>
                <ul className="citation-list" style={{ marginBottom: '0.4rem' }}>
                  {comp.strengths.map((s) => <li key={s}>{s}</li>)}
                </ul>

                <div className="citation-label" style={{ marginBottom: '0.2rem' }}>Weaknesses</div>
                <ul className="citation-list" style={{ marginBottom: '0.4rem' }}>
                  {comp.weaknesses.map((w) => <li key={w}>{w}</li>)}
                </ul>

                <button
                  className="btn"
                  onClick={() => loadBattleCard(comp.name)}
                  style={{ width: '100%', marginTop: '0.3rem', fontSize: '0.72rem' }}
                >
                  View Battle Card
                </button>
              </div>
            ))}
          </div>
        ) : viewMode === 'battlecard' ? (
          battleCard ? (
            <div style={{ display: 'grid', gap: '0.6rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text)' }}>
                  vs {battleCard.competitor}
                </span>
                <button className="btn btn-ghost" onClick={() => setBattleCard(null)} style={{ fontSize: '0.72rem' }}>
                  &larr; Back
                </button>
              </div>

              <div className="two-col">
                <div className="answer-box">
                  <div className="citation-label">When They Lead</div>
                  <div className="answer-text" style={{ marginTop: '0.3rem' }}>{battleCard.when_they_lead}</div>
                </div>
                <div className="answer-box">
                  <div className="citation-label">When We Win</div>
                  <div className="answer-text" style={{ marginTop: '0.3rem' }}>{battleCard.when_we_win}</div>
                </div>
              </div>

              <div className="answer-box">
                <div className="citation-label">Key Differentiators</div>
                <ul className="citation-list" style={{ marginTop: '0.3rem' }}>
                  {battleCard.key_differentiators.map((d) => <li key={d}>{d}</li>)}
                </ul>
              </div>

              <div className="answer-box">
                <div className="citation-label">Objection Handlers</div>
                {battleCard.objection_handlers.map((oh) => (
                  <div key={oh.objection} style={{ marginTop: '0.4rem' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.8rem', color: 'var(--text)' }}>Q: {oh.objection}</div>
                    <div className="answer-text" style={{ marginTop: '0.15rem' }}>A: {oh.response}</div>
                  </div>
                ))}
              </div>

              <RefineAIButton context={`Battle card for ${battleCard.competitor}`} />
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '0.4rem' }}>
              <div style={{ color: 'var(--text-3)', fontSize: '0.8rem' }}>Select a competitor to view battle card:</div>
              {competitors.map((comp) => (
                <button key={comp.id} className="btn" onClick={() => loadBattleCard(comp.name)} style={{ textAlign: 'left' }}>
                  {comp.name}
                </button>
              ))}
            </div>
          )
        ) : (
          <div>
            <div className="citation-label" style={{ marginBottom: '0.5rem' }}>Recent Competitive Moves</div>
            {competitors.flatMap((comp) =>
              comp.recent_moves.map((move, i) => ({
                competitor: comp.name,
                move,
                threat_level: comp.threat_level,
                key: `${comp.id}-${i}`,
              }))
            ).map((alert) => (
              <div key={alert.key} style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.5rem',
                padding: '0.5rem',
                borderBottom: '1px solid var(--border)',
              }}>
                <span className={`tag ${THREAT_COLORS[alert.threat_level]}`} style={{ flexShrink: 0 }}>
                  {alert.competitor}
                </span>
                <span className="answer-text">{alert.move}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
