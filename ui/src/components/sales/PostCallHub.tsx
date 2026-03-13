'use client';

import { useState, useEffect, useCallback } from 'react';
import StatusBadge, { type BadgeVariant } from '../shared/StatusBadge';
import RefineAIButton from '../shared/RefineAIButton';
import { api } from '../../lib/api';

type CallRecord = {
  readonly id: string;
  readonly title: string;
  readonly account: string;
  readonly date: string;
  readonly status: BadgeVariant;
  readonly duration?: string;
};

type CallSummary = {
  readonly id: string;
  readonly what_we_heard: string;
  readonly what_it_means: string;
  readonly next_steps: ReadonlyArray<string>;
  readonly follow_up_email: string;
};

function SummarySection({ title, content, callId, sectionId }: {
  readonly title: string;
  readonly content: string;
  readonly callId: string;
  readonly sectionId: string;
}) {
  return (
    <div style={{
      borderTop: '1px solid var(--border)',
      paddingTop: '0.6rem',
      marginTop: '0.4rem',
    }}>
      <div className="citation-label" style={{ marginBottom: '0.35rem' }}>{title}</div>
      <div className="answer-text" style={{ whiteSpace: 'pre-wrap' }}>{content}</div>
      <RefineAIButton reportId={callId} sectionId={sectionId} context={title} />
    </div>
  );
}

export default function PostCallHub() {
  const [calls, setCalls] = useState<ReadonlyArray<CallRecord>>([]);
  const [selectedCall, setSelectedCall] = useState<CallRecord | null>(null);
  const [summary, setSummary] = useState<CallSummary | null>(null);
  const [emailDraft, setEmailDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadCalls = async () => {
      setLoading(true);
      try {
        const { data } = await api.get<ReadonlyArray<CallRecord>>('/api/calls/recent');
        setCalls(data);
      } catch {
        setCalls([
          { id: 'c1', title: 'Discovery Call - Acme Corp', account: 'Acme Corp', date: '2024-03-14', status: 'ready', duration: '32 min' },
          { id: 'c2', title: 'Technical Deep Dive - Globex', account: 'Globex Inc', date: '2024-03-13', status: 'processing', duration: '48 min' },
          { id: 'c3', title: 'Pricing Discussion - Initech', account: 'Initech', date: '2024-03-12', status: 'ready', duration: '25 min' },
        ]);
      } finally {
        setLoading(false);
      }
    };
    loadCalls();
  }, []);

  const loadSummary = useCallback(async (call: CallRecord) => {
    setSelectedCall(call);
    setError('');
    try {
      const { data } = await api.get<CallSummary>(`/api/calls/${call.id}/summary`);
      setSummary(data);
      setEmailDraft(data.follow_up_email || '');
    } catch {
      const fallback: CallSummary = {
        id: call.id,
        what_we_heard: 'The prospect expressed interest in our analytics capabilities, specifically around real-time processing. Key concerns include migration complexity and integration with their existing Snowflake setup.',
        what_it_means: 'Strong buying signals around performance improvements. The technical team is aligned but the CFO needs ROI justification. Timeline: Q2 decision expected.',
        next_steps: [
          'Schedule POC environment setup call',
          'Send ROI calculator with their specific workload data',
          'Connect SE team for architecture review',
        ],
        follow_up_email: `Hi Team,\n\nThank you for the productive discussion today. As discussed, here are the next steps:\n\n1. We'll set up a POC environment for your team to test\n2. I'll send over the ROI analysis based on your 40TB workload\n3. Our SE team will reach out to schedule the architecture review\n\nLooking forward to moving this forward.\n\nBest regards`,
      };
      setSummary(fallback);
      setEmailDraft(fallback.follow_up_email);
    }
  }, []);

  if (selectedCall && summary) {
    return (
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">{selectedCall.title}</span>
          <button
            className="btn btn-ghost"
            onClick={() => { setSelectedCall(null); setSummary(null); }}
            style={{ fontSize: '0.72rem' }}
          >
            &larr; Back
          </button>
        </div>
        <div className="panel-body" style={{ display: 'grid', gap: '0.5rem' }}>
          <SummarySection
            title="What We Heard"
            content={summary.what_we_heard}
            callId={summary.id}
            sectionId="what_we_heard"
          />

          <SummarySection
            title="What It Means"
            content={summary.what_it_means}
            callId={summary.id}
            sectionId="what_it_means"
          />

          <div style={{
            borderTop: '1px solid var(--border)',
            paddingTop: '0.6rem',
            marginTop: '0.4rem',
          }}>
            <div className="citation-label" style={{ marginBottom: '0.35rem' }}>Next Steps</div>
            <ul className="citation-list">
              {summary.next_steps.map((step, i) => (
                <li key={`step-${i}`}>{step}</li>
              ))}
            </ul>
            <RefineAIButton reportId={summary.id} sectionId="next_steps" context="Next Steps" />
          </div>

          <div style={{
            borderTop: '1px solid var(--border)',
            paddingTop: '0.6rem',
            marginTop: '0.4rem',
          }}>
            <div className="citation-label" style={{ marginBottom: '0.35rem' }}>Follow-Up Email Draft</div>
            <textarea
              className="input"
              rows={8}
              value={emailDraft}
              onChange={(e) => setEmailDraft(e.target.value)}
            />
            <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.5rem' }}>
              <button className="btn btn-primary" style={{ fontSize: '0.75rem' }}>
                Copy to Clipboard
              </button>
              <RefineAIButton
                reportId={summary.id}
                sectionId="follow_up_email"
                context="Follow-Up Email"
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Post-Call Hub</span>
        <span className="tag">Recent Calls</span>
      </div>
      <div className="panel-body">
        {loading ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-3)', fontSize: '0.8rem' }}>
            Loading calls...
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Call</th>
                <th>Account</th>
                <th>Date</th>
                <th>Duration</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((call) => (
                <tr key={call.id} style={{ cursor: 'pointer' }} onClick={() => loadSummary(call)}>
                  <td className="row-title">{call.title}</td>
                  <td>{call.account}</td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>{call.date}</td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>{call.duration || '—'}</td>
                  <td><StatusBadge status={call.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {error && <div className="error-text">{error}</div>}
      </div>
    </div>
  );
}
