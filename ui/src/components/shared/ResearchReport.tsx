'use client';

import { useState, useCallback } from 'react';
import RefineAIButton from './RefineAIButton';

type ReportSection = {
  readonly id: string;
  readonly title: string;
  readonly content: string;
  readonly citations?: ReadonlyArray<string>;
};

type ResearchReportProps = {
  readonly reportId?: string;
  readonly title: string;
  readonly sections: ReadonlyArray<ReportSection>;
  readonly variant?: 'pre-call' | 'post-call';
};

function CollapsibleSection({
  section,
  reportId,
  defaultOpen = true,
}: {
  readonly section: ReportSection;
  readonly reportId?: string;
  readonly defaultOpen?: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultOpen);

  const toggle = useCallback(() => {
    setExpanded((prev) => !prev);
  }, []);

  return (
    <div style={{
      borderTop: '1px solid var(--border)',
      paddingTop: '0.6rem',
      marginTop: '0.4rem',
    }}>
      <div
        onClick={toggle}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          padding: '0.3rem 0',
        }}
      >
        <span className="citation-label" style={{ margin: 0 }}>
          {expanded ? '▾' : '▸'} {section.title}
        </span>
      </div>

      {expanded && (
        <div style={{ marginTop: '0.4rem' }}>
          <div className="answer-text" style={{ whiteSpace: 'pre-wrap' }}>
            {section.content}
          </div>

          {section.citations && section.citations.length > 0 && (
            <div className="answer-citations" style={{ marginTop: '0.5rem' }}>
              <div className="citation-label">Sources</div>
              <ul className="citation-list">
                {section.citations.map((c, i) => (
                  <li key={`${section.id}-cite-${i}`}>{c}</li>
                ))}
              </ul>
            </div>
          )}

          <RefineAIButton
            reportId={reportId}
            sectionId={section.id}
            context={section.title}
          />
        </div>
      )}
    </div>
  );
}

export default function ResearchReport({ reportId, title, sections, variant = 'pre-call' }: ResearchReportProps) {
  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">{title}</span>
        <span className={`tag ${variant === 'pre-call' ? 'tag-orange' : 'tag-green'}`}>
          {variant === 'pre-call' ? 'Pre-Call Report' : 'Post-Call Analysis'}
        </span>
      </div>
      <div className="panel-body">
        {sections.map((section, i) => (
          <CollapsibleSection
            key={section.id}
            section={section}
            reportId={reportId}
            defaultOpen={i < 3}
          />
        ))}
      </div>
    </div>
  );
}

export type { ReportSection, ResearchReportProps };
