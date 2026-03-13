'use client';

import { useState } from 'react';
import PreCallHub from '../../../components/sales/PreCallHub';
import PostCallHub from '../../../components/sales/PostCallHub';
import Pipeline from '../../../components/sales/Pipeline';
import Account360 from '../../../components/sales/Account360';

type SalesTab = 'pre-call' | 'post-call' | 'pipeline' | 'account360';

const TABS: ReadonlyArray<{ readonly id: SalesTab; readonly label: string }> = [
  { id: 'pre-call', label: 'Pre-Call Hub' },
  { id: 'post-call', label: 'Post-Call Hub' },
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'account360', label: 'Account 360' },
];

export default function SalesPage() {
  const [activeTab, setActiveTab] = useState<SalesTab>('pre-call');

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar-title">Sales Dashboard</div>
          <div className="topbar-meta">Pre-call research, post-call analysis, pipeline management</div>
        </div>
        <div className="topbar-right">
          <span className="tag tag-orange">Sales</span>
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
                transition: 'color 0.1s',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="content">
        {activeTab === 'pre-call' && <PreCallHub />}
        {activeTab === 'post-call' && <PostCallHub />}
        {activeTab === 'pipeline' && <Pipeline />}
        {activeTab === 'account360' && <Account360 />}
      </div>
    </>
  );
}
