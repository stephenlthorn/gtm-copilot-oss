'use client';

import { useState, useEffect, useCallback } from 'react';
import StatusBadge, { type BadgeVariant } from '../shared/StatusBadge';
import ResearchReport, { type ReportSection } from '../shared/ResearchReport';
import { api } from '../../lib/api';

type Meeting = {
  readonly id: string;
  readonly title: string;
  readonly company: string;
  readonly date: string;
  readonly status: BadgeVariant;
  readonly reportId?: string;
};

type MeetingReport = {
  readonly id: string;
  readonly title: string;
  readonly sections: ReadonlyArray<ReportSection>;
};

export default function PreCallHub() {
  const [meetings, setMeetings] = useState<ReadonlyArray<Meeting>>([]);
  const [selectedMeeting, setSelectedMeeting] = useState<Meeting | null>(null);
  const [report, setReport] = useState<MeetingReport | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [researchLoading, setResearchLoading] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const loadMeetings = async () => {
      setLoading(true);
      try {
        const { data } = await api.get<ReadonlyArray<Meeting>>('/api/meetings/upcoming');
        setMeetings(data);
      } catch {
        setMeetings([
          { id: '1', title: 'Discovery Call - Acme Corp', company: 'Acme Corp', date: '2024-03-15 10:00', status: 'ready', reportId: 'rpt-1' },
          { id: '2', title: 'Technical Review - Globex', company: 'Globex Inc', date: '2024-03-15 14:00', status: 'in-progress' },
          { id: '3', title: 'Renewal Discussion - Initech', company: 'Initech', date: '2024-03-16 09:00', status: 'not-started' },
        ]);
      } finally {
        setLoading(false);
      }
    };
    loadMeetings();
  }, []);

  const loadReport = useCallback(async (meeting: Meeting) => {
    setSelectedMeeting(meeting);
    if (!meeting.reportId) {
      setReport(null);
      return;
    }
    try {
      const { data } = await api.get<MeetingReport>(`/api/research/reports/${meeting.reportId}`);
      setReport(data);
    } catch {
      setReport({
        id: meeting.reportId || meeting.id,
        title: `Research: ${meeting.company}`,
        sections: [
          { id: 'overview', title: 'Company Overview', content: 'Loading research data...' },
          { id: 'financials', title: 'Financial Health', content: 'Financial analysis pending...' },
          { id: 'tech-stack', title: 'Technology Stack', content: 'Tech stack analysis pending...' },
          { id: 'competitors', title: 'Competitive Landscape', content: 'Competitor analysis pending...' },
          { id: 'news', title: 'Recent News & Events', content: 'News aggregation pending...' },
          { id: 'stakeholders', title: 'Key Stakeholders', content: 'Stakeholder mapping pending...' },
          { id: 'talking-points', title: 'Suggested Talking Points', content: 'Generating talking points...' },
        ],
      });
    }
  }, []);

  const triggerResearch = useCallback(async (meetingId: string) => {
    setResearchLoading(meetingId);
    setError('');
    try {
      await api.post('/api/research/trigger', { meeting_id: meetingId });
      setMeetings((prev) =>
        prev.map((m) => m.id === meetingId ? { ...m, status: 'in-progress' as BadgeVariant } : m)
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Research trigger failed';
      setError(message);
    } finally {
      setResearchLoading('');
    }
  }, []);

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError('');
    try {
      const { data } = await api.post<MeetingReport>('/api/research/company', { company: searchQuery.trim() });
      setReport(data);
      setSelectedMeeting(null);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Search failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  if (selectedMeeting && report) {
    return (
      <div>
        <button
          className="btn btn-ghost"
          onClick={() => { setSelectedMeeting(null); setReport(null); }}
          style={{ marginBottom: '0.75rem', fontSize: '0.75rem' }}
        >
          &larr; Back to meetings
        </button>
        <ResearchReport
          reportId={report.id}
          title={report.title}
          sections={report.sections}
          variant="pre-call"
        />
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Pre-Call Hub</span>
        <span className="tag tag-orange">Upcoming</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            className="input"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search company for manual research..."
            style={{ flex: 1 }}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
          <button className="btn btn-primary" onClick={handleSearch} disabled={loading}>
            Research
          </button>
        </div>

        {error && <div className="error-text">{error}</div>}

        {loading ? (
          <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-3)', fontSize: '0.8rem' }}>
            Loading meetings...
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Meeting</th>
                <th>Company</th>
                <th>Date</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {meetings.map((meeting) => (
                <tr key={meeting.id}>
                  <td>
                    <span
                      className="row-title"
                      style={{ cursor: 'pointer' }}
                      onClick={() => loadReport(meeting)}
                    >
                      {meeting.title}
                    </span>
                  </td>
                  <td>{meeting.company}</td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-3)' }}>{meeting.date}</td>
                  <td><StatusBadge status={meeting.status} /></td>
                  <td>
                    <button
                      className="btn"
                      onClick={() => triggerResearch(meeting.id)}
                      disabled={researchLoading === meeting.id || meeting.status === 'ready'}
                      style={{ fontSize: '0.72rem', padding: '0.2rem 0.5rem' }}
                    >
                      {researchLoading === meeting.id ? 'Researching...' : 'Research Now'}
                    </button>
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
