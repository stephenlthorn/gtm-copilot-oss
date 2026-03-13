'use client';

import { useState, useCallback } from 'react';
import RefineAIButton from '../shared/RefineAIButton';
import { api } from '../../lib/api';

type ContentType = 'blog' | 'case_study' | 'email' | 'social_media';

type ContentTemplate = {
  readonly id: ContentType;
  readonly label: string;
  readonly description: string;
  readonly icon: string;
};

const TEMPLATES: ReadonlyArray<ContentTemplate> = [
  { id: 'blog', label: 'Blog Post', description: 'Long-form thought leadership content', icon: '📝' },
  { id: 'case_study', label: 'Case Study', description: 'Customer success stories', icon: '📊' },
  { id: 'email', label: 'Email Campaign', description: 'Outreach and nurture emails', icon: '✉' },
  { id: 'social_media', label: 'Social Media', description: 'LinkedIn, Twitter posts', icon: '📱' },
];

export default function ContentEngine() {
  const [selectedTemplate, setSelectedTemplate] = useState<ContentType>('blog');
  const [topic, setTopic] = useState('');
  const [targetAudience, setTargetAudience] = useState('');
  const [generatedContent, setGeneratedContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const generateContent = useCallback(async () => {
    if (!topic.trim()) {
      setError('Please enter a topic');
      return;
    }
    setLoading(true);
    setError('');
    setGeneratedContent('');
    try {
      const { data } = await api.post<{ content: string }>('/api/marketing/content/generate', {
        template: selectedTemplate,
        topic: topic.trim(),
        target_audience: targetAudience.trim() || undefined,
      });
      setGeneratedContent(data.content);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Content generation failed';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [selectedTemplate, topic, targetAudience]);

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Content Engine</span>
        <span className="tag tag-orange">AI-Powered</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '0.75rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.4rem' }}>
          {TEMPLATES.map((tmpl) => (
            <button
              key={tmpl.id}
              onClick={() => setSelectedTemplate(tmpl.id)}
              style={{
                padding: '0.55rem 0.6rem',
                border: `1px solid ${selectedTemplate === tmpl.id ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: '6px',
                background: selectedTemplate === tmpl.id ? 'var(--accent-dim)' : 'var(--bg)',
                cursor: 'pointer',
                textAlign: 'left',
                fontFamily: 'var(--font)',
                transition: 'border-color 0.1s',
              }}
            >
              <div style={{ fontSize: '0.9rem', marginBottom: '0.1rem' }}>{tmpl.icon}</div>
              <div style={{
                fontSize: '0.78rem',
                fontWeight: 600,
                color: selectedTemplate === tmpl.id ? 'var(--accent)' : 'var(--text)',
              }}>
                {tmpl.label}
              </div>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>{tmpl.description}</div>
            </button>
          ))}
        </div>

        <div className="two-col" style={{ gap: '0.75rem' }}>
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Topic / Theme</label>
            <input
              className="input"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g., Real-time analytics for financial services"
            />
          </div>
          <div style={{ display: 'grid', gap: '0.35rem' }}>
            <label style={{ color: 'var(--text-3)', fontSize: '0.72rem' }}>Target Audience (optional)</label>
            <input
              className="input"
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              placeholder="e.g., CTOs at mid-market fintech companies"
            />
          </div>
        </div>

        <button className="btn btn-primary" onClick={generateContent} disabled={loading}>
          {loading ? 'Generating...' : 'Generate Content'}
        </button>

        {error && <div className="error-text">{error}</div>}

        {generatedContent && (
          <div className="answer-box">
            <div className="citation-label" style={{ marginBottom: '0.35rem' }}>
              Generated {TEMPLATES.find((t) => t.id === selectedTemplate)?.label}
            </div>
            <textarea
              className="input"
              rows={12}
              value={generatedContent}
              onChange={(e) => setGeneratedContent(e.target.value)}
              style={{ marginBottom: '0.5rem' }}
            />
            <div style={{ display: 'flex', gap: '0.4rem' }}>
              <button className="btn btn-primary" style={{ fontSize: '0.75rem' }}>
                Copy
              </button>
              <RefineAIButton context={`${selectedTemplate} content about ${topic}`} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
