'use client';

import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { type ReactNode } from 'react';
import { AuthProvider, useAuth } from '../../contexts/AuthContext';

type NavTab = {
  readonly href: string;
  readonly label: string;
  readonly icon: string;
};

const TABS: ReadonlyArray<NavTab> = [
  { href: '/sales', label: 'Sales', icon: '◎' },
  { href: '/marketing', label: 'Marketing', icon: '◈' },
  { href: '/se', label: 'SE', icon: '⬡' },
  { href: '/admin', label: 'Admin / Settings', icon: '⊞' },
];

function TopNav() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 1.25rem',
      borderBottom: '1px solid var(--border)',
      background: 'var(--bg)',
      height: '48px',
      position: 'sticky',
      top: 0,
      zIndex: 20,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
        <Link href="/sales" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none' }}>
          <Image alt="GTM Copilot" src="/logo.svg" width={20} height={20} />
          <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--text)' }}>GTM Copilot</span>
        </Link>

        <nav style={{ display: 'flex', gap: '2px' }}>
          {TABS.map((tab) => {
            const active = pathname.startsWith(tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.4rem 0.75rem',
                  borderRadius: '4px',
                  fontSize: '0.8rem',
                  fontWeight: active ? 600 : 500,
                  color: active ? 'var(--accent)' : 'var(--text-2)',
                  background: active ? 'var(--accent-dim)' : 'transparent',
                  textDecoration: 'none',
                  transition: 'color 0.1s, background 0.1s',
                  fontFamily: 'var(--font)',
                }}
              >
                <span style={{ opacity: active ? 1 : 0.6, fontSize: '0.75rem' }}>{tab.icon}</span>
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        {user && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <div style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: 'var(--success)',
            }} />
            <span style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>
              {user.name || user.email}
            </span>
            <span className="tag" style={{ fontSize: '0.62rem' }}>
              {user.role}
            </span>
          </div>
        )}
        <Link
          href="/admin"
          style={{
            fontSize: '0.72rem',
            color: 'var(--text-3)',
            textDecoration: 'none',
          }}
        >
          Settings
        </Link>
        {user && (
          <button
            className="btn btn-ghost"
            onClick={logout}
            style={{ fontSize: '0.72rem', padding: '0.2rem 0.4rem' }}
          >
            Sign out
          </button>
        )}
      </div>
    </div>
  );
}

function DashboardContent({ children }: { readonly children: ReactNode }) {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <TopNav />
      <div className="internal-reminder">
        Internal data only. Do not share externally.
      </div>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {children}
      </div>
    </div>
  );
}

export default function DashboardLayout({ children }: { readonly children: ReactNode }) {
  return (
    <AuthProvider>
      <DashboardContent>{children}</DashboardContent>
    </AuthProvider>
  );
}
