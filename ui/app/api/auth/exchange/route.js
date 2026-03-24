import { NextResponse } from 'next/server';
import { exchangeCode, parseIdToken } from '../../../../lib/pkce';

const ALLOWED_DOMAIN = process.env.ALLOWED_EMAIL_DOMAIN;
const APP_BASE = process.env.NEXT_PUBLIC_APP_URL || process.env.NEXTAUTH_URL || 'http://localhost:3000';

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get('code');
  const returnedState = searchParams.get('state');

  const pkceRaw = request.cookies.get('oracle_pkce')?.value;
  if (!pkceRaw) {
    return NextResponse.redirect(new URL('/login?error=no_pkce', APP_BASE));
  }

  let pkce;
  try {
    pkce = JSON.parse(pkceRaw);
  } catch {
    return NextResponse.redirect(new URL('/login?error=bad_pkce', APP_BASE));
  }

  if (pkce.state !== returnedState) {
    return NextResponse.redirect(new URL('/login?error=state_mismatch', APP_BASE));
  }

  if (!code) {
    return NextResponse.redirect(new URL('/login?error=no_code', APP_BASE));
  }

  let tokens;
  try {
    tokens = await exchangeCode(code, pkce.verifier);
  } catch (err) {
    console.error('Token exchange error:', err);
    return NextResponse.redirect(new URL('/login?error=exchange_failed', APP_BASE));
  }

  const claims = tokens.id_token ? parseIdToken(tokens.id_token) : {};
  const email = claims.email || '';

  if (!ALLOWED_DOMAIN) {
    return NextResponse.redirect(new URL('/login?error=domain_not_configured', APP_BASE));
  }

  if (!email.endsWith(`@${ALLOWED_DOMAIN}`)) {
    return NextResponse.redirect(new URL('/login?error=unauthorized_domain', APP_BASE));
  }

  const session = {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token || null,
    expires_at: Date.now() + (tokens.expires_in || 3600) * 1000,
    email,
    name: claims.name || email,
  };

  const res = NextResponse.redirect(new URL('/chat', APP_BASE));
  res.cookies.set('oracle_session', JSON.stringify(session), {
    httpOnly: true,
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 8,
  });
  res.cookies.set('oracle_pkce', '', { httpOnly: true, path: '/', maxAge: 0 });

  // Fire-and-forget incremental Chorus sync — crowd-sources new calls from every rep who logs in
  fetch(`${APP_BASE}/api/admin/sync/calls/background`, { method: 'POST' }).catch(() => {});

  return res;
}
