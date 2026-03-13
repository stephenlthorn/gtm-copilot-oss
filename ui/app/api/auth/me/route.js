import { NextResponse } from 'next/server';
import { getSession } from '../../../../lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET() {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: 'unauthenticated' }, { status: 401 });

  let connected_providers = {};
  try {
    const res = await fetch(`${API_BASE}/auth/me`, {
      headers: { 'X-User-Email': session.email },
    });
    if (res.ok) {
      const data = await res.json();
      connected_providers = data.connected_providers || {};
    }
  } catch {
    // backend unavailable — return session data without connected_providers
  }

  return NextResponse.json({
    email: session.email,
    name: session.name,
    expires_at: session.expires_at,
    connected_providers,
    has_openai_key: Boolean(session.openai_key),
  });
}
