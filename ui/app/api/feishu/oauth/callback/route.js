import { NextResponse } from 'next/server';
import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request) {
  const session = await getSession();
  const publicBase = (process.env.NEXT_PUBLIC_APP_URL || process.env.NEXTAUTH_URL || new URL('/', request.url).origin).replace(/\/$/, '');

  if (!session?.email) {
    return NextResponse.redirect(`${publicBase}/login`);
  }

  const url = new URL(request.url);
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const error = url.searchParams.get('error');
  const redirectUri = `${publicBase}/api/feishu/oauth/callback`;

  if (error) {
    return NextResponse.redirect(`${publicBase}/settings?feishu=error&reason=${encodeURIComponent(error)}`);
  }
  if (!code || !state) {
    return NextResponse.redirect(`${publicBase}/settings?feishu=error&reason=missing_code_or_state`);
  }

  const res = await fetch(`${API_BASE}/admin/feishu/oauth/exchange`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Email': session.email,
      ...(session.access_token ? { 'X-OpenAI-Token': session.access_token } : {}),
    },
    body: JSON.stringify({
      code,
      state,
      redirect_uri: redirectUri,
      user_email: session.email,
    }),
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    console.error('Feishu OAuth exchange failed:', res.status, detail);
    return NextResponse.redirect(`${publicBase}/settings?feishu=error&reason=token_exchange_failed`);
  }
  return NextResponse.redirect(`${publicBase}/settings?feishu=connected`);
}
