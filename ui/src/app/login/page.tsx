'use client';

import { useState } from 'react';
import Image from 'next/image';

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth/start');
      const { url } = await res.json();
      window.location.href = url;
    } catch {
      setError('Failed to start login. Is the server running?');
      setLoading(false);
    }
  };

  return (
    <div className="login-shell">
      <div className="login-card" style={{ maxWidth: '420px' }}>
        <div className="login-brand">
          <Image alt="GTM Copilot" src="/logo.svg" width={32} height={32} />
          <div>
            <div className="login-brand-name">GTM Copilot</div>
            <div className="login-brand-sub">AI-Powered GTM Workspace</div>
          </div>
        </div>

        <p className="login-heading">Sign in to continue</p>
        <p className="login-sub">
          Access your sales intelligence, marketing analytics, and SE tools.
        </p>

        {error && (
          <p className="error-text" style={{ marginBottom: '0.75rem' }}>{error}</p>
        )}

        <div style={{ display: 'grid', gap: '0.5rem', marginTop: '1rem' }}>
          <button
            className="btn btn-primary"
            style={{ width: '100%', padding: '0.65rem 1rem', fontSize: '0.85rem' }}
            onClick={handleGoogleLogin}
            disabled={loading}
          >
            {loading ? 'Redirecting...' : 'Continue with Google'}
          </button>
        </div>

        <div className="login-footer">
          OAuth tokens are stored in secure httpOnly cookies and never logged.
        </div>
      </div>
    </div>
  );
}
