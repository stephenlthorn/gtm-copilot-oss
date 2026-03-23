'use client';

import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

const NAV = [
  { href: '/rep',    label: 'Sales Rep',      icon: '◎' },
  { href: '/se',     label: 'Sales Engineer', icon: '⬡' },
  { href: '/oracle', label: 'Ask Oracle',     icon: '◈' },
];

export default function Sidebar({ email, hasSession = false }) {
  const pathname = usePathname();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    setLoggingOut(true);
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <Image alt="GTM Copilot" src="/logo.svg" width={22} height={22} />
        <div>
          <div className="sidebar-brand-name">GTM Copilot</div>
          <div className="sidebar-brand-sub">Revenue Intelligence</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {NAV.map(({ href, label, icon }) => (
          <Link
            key={href}
            href={href}
            className={`nav-link${pathname === href || pathname.startsWith(href + '/') ? ' active' : ''}`}
          >
            <span className="nav-link-icon">{icon}</span>
            {label}
          </Link>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="user-row">
          <div className="user-dot" />
          <div className="user-email">{email}</div>
        </div>
        <Link
          href="/settings"
          className={`nav-link${pathname === '/settings' ? ' active' : ''}`}
          style={{ width: '100%' }}
        >
          <span className="nav-link-icon">⚙</span>
          Settings
        </Link>
        {hasSession ? (
          <button
            className="nav-link btn-ghost"
            onClick={handleLogout}
            disabled={loggingOut}
            style={{ width: '100%' }}
          >
            <span className="nav-link-icon">→</span>
            {loggingOut ? 'Signing out...' : 'Sign out'}
          </button>
        ) : (
          <Link href="/login" className="nav-link btn-ghost" style={{ width: '100%' }}>
            <span className="nav-link-icon">→</span>
            Login
          </Link>
        )}
      </div>
    </aside>
  );
}
