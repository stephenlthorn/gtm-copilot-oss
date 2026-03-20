import { NextResponse } from 'next/server';

const ROLE_DEFAULTS = {
  sales_rep: '/rep',
  se: '/se',
  marketing: '/marketing',
  admin: '/admin',
};

const VALID_ROLES = new Set(Object.keys(ROLE_DEFAULTS));
const FALLBACK_ROLE = 'sales_rep';

function getRole(request) {
  const roleCookie = request.cookies.get('oracle_role')?.value;
  if (VALID_ROLES.has(roleCookie)) return roleCookie;
  return FALLBACK_ROLE;
}

function isAuthenticated(request) {
  const raw = request.cookies.get('oracle_session')?.value;
  if (!raw) return false;
  try {
    const session = JSON.parse(raw);
    return Boolean(session?.access_token) && Date.now() < session.expires_at;
  } catch {
    return false;
  }
}

export function middleware(request) {
  const { pathname } = request.nextUrl;

  if (pathname === '/') {
    if (!isAuthenticated(request)) {
      return NextResponse.redirect(new URL('/login', request.url));
    }
    const role = getRole(request);
    return NextResponse.redirect(new URL(ROLE_DEFAULTS[role], request.url));
  }

  // Non-root paths: pass through — role only affects the default landing.
  return NextResponse.next();
}

export const config = {
  matcher: ['/', '/rep/:path*', '/se/:path*', '/marketing/:path*', '/admin/:path*', '/settings/:path*'],
};
