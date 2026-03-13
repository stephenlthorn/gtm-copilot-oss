'use client';

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';

type UserRole = 'sales' | 'marketing' | 'se' | 'admin';

type User = {
  readonly id: string;
  readonly email: string;
  readonly name: string;
  readonly role: UserRole;
  readonly avatar_url?: string;
};

type AuthState = {
  readonly user: User | null;
  readonly loading: boolean;
  readonly error: string | null;
};

type AuthContextValue = AuthState & {
  readonly login: () => Promise<void>;
  readonly logout: () => Promise<void>;
  readonly refreshUser: () => Promise<void>;
  readonly defaultRoute: string;
};

const ROLE_ROUTES: Record<UserRole, string> = {
  sales: '/sales',
  marketing: '/marketing',
  se: '/se',
  admin: '/admin',
};

const AuthContext = createContext<AuthContextValue | null>(null);

function createInitialState(): AuthState {
  return {
    user: null,
    loading: true,
    error: null,
  };
}

export function AuthProvider({ children }: { readonly children: ReactNode }) {
  const [state, setState] = useState<AuthState>(createInitialState);

  const fetchUser = useCallback(async () => {
    try {
      const res = await fetch('/api/auth/me');
      if (!res.ok) {
        setState({ user: null, loading: false, error: null });
        return;
      }
      const data = await res.json();
      const user: User = {
        id: data.id || data.sub || '',
        email: data.email || '',
        name: data.name || data.email || '',
        role: data.role || 'sales',
        avatar_url: data.avatar_url || data.picture,
      };
      setState({ user, loading: false, error: null });
    } catch {
      setState({ user: null, loading: false, error: null });
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = useCallback(async () => {
    try {
      const res = await fetch('/api/auth/start');
      const { url } = await res.json();
      window.location.href = url;
    } catch {
      setState((prev) => ({ ...prev, error: 'Failed to start login' }));
    }
  }, []);

  const logout = useCallback(async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    setState({ user: null, loading: false, error: null });
    window.location.href = '/login';
  }, []);

  const defaultRoute = state.user ? ROLE_ROUTES[state.user.role] : '/sales';

  const value: AuthContextValue = {
    ...state,
    login,
    logout,
    refreshUser: fetchUser,
    defaultRoute,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export type { User, UserRole, AuthContextValue };
