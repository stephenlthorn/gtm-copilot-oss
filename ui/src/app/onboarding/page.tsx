'use client';

import { useState, useCallback } from 'react';
import Image from 'next/image';
import { useRouter } from 'next/navigation';
import { api } from '../../lib/api';

type UserRole = 'sales' | 'marketing' | 'se' | 'admin';

type RoleOption = {
  readonly value: UserRole;
  readonly label: string;
  readonly description: string;
  readonly icon: string;
};

const ROLES: ReadonlyArray<RoleOption> = [
  { value: 'sales', label: 'Sales Rep', description: 'Pre-call research, post-call analysis, pipeline management', icon: '◎' },
  { value: 'se', label: 'Sales Engineer', description: 'Technical deep dives, demo prep, POC planning', icon: '⬡' },
  { value: 'marketing', label: 'Marketing', description: 'Competitive intel, content engine, campaign analytics', icon: '◈' },
  { value: 'admin', label: 'Admin', description: 'System configuration, user management, integrations', icon: '⊞' },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [apiKey, setApiKey] = useState('');
  const [selectedRole, setSelectedRole] = useState<UserRole>('sales');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = useCallback(async () => {
    if (!apiKey.trim()) {
      setError('Please enter your OpenAI API key');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await api.post('/api/onboarding', {
        openai_api_key: apiKey.trim(),
        role: selectedRole,
      });
      router.push(`/${selectedRole}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Setup failed';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }, [apiKey, selectedRole, router]);

  return (
    <div className="login-shell">
      <div className="login-card" style={{ maxWidth: '520px' }}>
        <div className="login-brand">
          <Image alt="GTM Copilot" src="/logo.svg" width={28} height={28} />
          <div>
            <div className="login-brand-name">Welcome to GTM Copilot</div>
            <div className="login-brand-sub">Complete setup to get started</div>
          </div>
        </div>

        <div style={{ display: 'grid', gap: '1rem', marginTop: '1rem' }}>
          <div>
            <label style={{ display: 'block', color: 'var(--text-3)', fontSize: '0.72rem', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              OpenAI API Key
            </label>
            <input
              className="input"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
            />
            <div style={{ fontSize: '0.7rem', color: 'var(--text-3)', marginTop: '0.3rem' }}>
              Used for AI-powered research and analysis. Stored securely.
            </div>
          </div>

          <div>
            <label style={{ display: 'block', color: 'var(--text-3)', fontSize: '0.72rem', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Your Role
            </label>
            <div style={{ display: 'grid', gap: '0.4rem' }}>
              {ROLES.map((role) => (
                <button
                  key={role.value}
                  onClick={() => setSelectedRole(role.value)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.75rem',
                    padding: '0.6rem 0.75rem',
                    borderRadius: '6px',
                    border: `1px solid ${selectedRole === role.value ? 'var(--accent)' : 'var(--border)'}`,
                    background: selectedRole === role.value ? 'var(--accent-dim)' : 'var(--bg)',
                    cursor: 'pointer',
                    textAlign: 'left',
                    fontFamily: 'var(--font)',
                    width: '100%',
                    transition: 'border-color 0.1s, background 0.1s',
                  }}
                >
                  <span style={{ fontSize: '1.1rem', opacity: 0.7 }}>{role.icon}</span>
                  <div>
                    <div style={{ fontSize: '0.82rem', fontWeight: 600, color: selectedRole === role.value ? 'var(--accent)' : 'var(--text)' }}>
                      {role.label}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>
                      {role.description}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {error && <p className="error-text">{error}</p>}

          <button
            className="btn btn-primary"
            style={{ width: '100%', padding: '0.65rem 1rem', fontSize: '0.85rem' }}
            onClick={handleSubmit}
            disabled={submitting}
          >
            {submitting ? 'Setting up...' : 'Complete Setup'}
          </button>
        </div>
      </div>
    </div>
  );
}
