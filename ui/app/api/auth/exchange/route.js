import { NextResponse } from 'next/server';
import { exchangeCode, parseIdToken } from '../../../../lib/pkce';

const VALID_ROLES = new Set(['sales_rep', 'se', 'marketing', 'admin']);
const DEFAULT_ROLE = 'sales_rep';

function resolveRole(email) {
  const roleMapRaw = process.env.ROLE_MAP;
  if (roleMapRaw) {
    try {
      const map = JSON.parse(roleMapRaw);
      const mapped = map[email];
      if (VALID_ROLES.has(mapped)) return mapped;
    } catch {
      // malformed ROLE_MAP — fall through
    }
  }
  const envRole = process.env.USER_ROLE;
  if (VALID_ROLES.has(envRole)) return envRole;
  return DEFAULT_ROLE;
}

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get('code');
  const returnedState = searchParams.get('state');

  const pkceRaw = request.cookies.get('oracle_pkce')?.value;
  if (!pkceRaw) {
    return NextResponse.redirect(new URL('/login?error=no_pkce', request.url));
  }

  let pkce;
  try {
    pkce = JSON.parse(pkceRaw);
  } catch {
    return NextResponse.redirect(new URL('/login?error=bad_pkce', request.url));
  }

  if (pkce.state !== returnedState) {
    return NextResponse.redirect(new URL('/login?error=state_mismatch', request.url));
  }

  if (!code) {
    return NextResponse.redirect(new URL('/login?error=no_code', request.url));
  }

  let tokens;
  try {
    tokens = await exchangeCode(code, pkce.verifier);
  } catch (err) {
    console.error('Token exchange error:', err);
    return NextResponse.redirect(new URL('/login?error=exchange_failed', request.url));
  }

  const claims = tokens.id_token ? parseIdToken(tokens.id_token) : {};
  const email = claims.email || 'user@openai.com';
  const session = {
    access_token: tokens.access_token,
    refresh_token: tokens.refresh_token || null,
    expires_at: Date.now() + (tokens.expires_in || 3600) * 1000,
    email,
    name: claims.name || claims.email || 'ChatGPT User',
  };

  // Resolve role: check ROLE_MAP env (JSON mapping email→role), then USER_ROLE default.
  // Falls back to 'sales_rep' if neither is configured.
  const role = resolveRole(email);

  // Redirect to / so middleware handles the role-based landing page redirect.
  const res = NextResponse.redirect(new URL('/', request.url));
  res.cookies.set('oracle_session', JSON.stringify(session), {
    httpOnly: true,
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 8,
  });
  // oracle_role is not httpOnly so the Edge middleware can read it directly from the request.
  res.cookies.set('oracle_role', role, {
    httpOnly: false,
    sameSite: 'lax',
    path: '/',
    maxAge: 60 * 60 * 8,
  });
  res.cookies.set('oracle_pkce', '', { httpOnly: true, path: '/', maxAge: 0 });
  return res;
}
