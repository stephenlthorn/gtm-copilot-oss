'use client';

import { useState } from 'react';
import CompetitiveIntel from '../../../components/marketing/CompetitiveIntel';
import ContentEngine from '../../../components/marketing/ContentEngine';
import CampaignIntel from '../../../components/marketing/CampaignIntel';

type MarketingTab = 'competitive' | 'content' | 'campaign';

const TABS: ReadonlyArray<{ readonly id: MarketingTab; readonly label: string }> = [
  { id: 'competitive', label: 'Competitive Intel' },
  { id: 'content', label: 'Content Engine' },
  { id: 'campaign', label: 'Campaign Intel' },
];

export default function MarketingPage() {
  const [activeTab, setActiveTab] = useState<MarketingTab>('competitive');

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar-title">Marketing Dashboard</div>
          <div className="topbar-meta">Competitive intelligence, content generation, campaign analytics</div>
        </div>
        <div className="topbar-right">
          <span className="tag tag-orange">Marketing</span>
        </div>
      </div>

      <div style={{ padding: '0 1.25rem', borderBottom: '1px solid var(--border)', background: 'var(--bg)' }}>
        <div style={{ display: 'flex', gap: '0' }}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '0.6rem 1rem',
                fontSize: '0.8rem',
                fontWeight: activeTab === tab.id ? 600 : 500,
                color: activeTab === tab.id ? 'var(--accent)' : 'var(--text-2)',
                background: 'transparent',
                border: 'none',
                borderBottom: activeTab === tab.id ? '2px solid var(--accent)' : '2px solid transparent',
                cursor: 'pointer',
                fontFamily: 'var(--font)',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="content">
        {activeTab === 'competitive' && <CompetitiveIntel />}
        {activeTab === 'content' && <ContentEngine />}
        {activeTab === 'campaign' && <CampaignIntel />}
      </div>
    </>
  );
}
