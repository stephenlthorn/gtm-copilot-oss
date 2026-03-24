import { NextResponse } from 'next/server';

export async function POST(request) {
  const origin = process.env.NEXT_PUBLIC_APP_URL || `https://${request.headers.get('host')}`;
  const res = NextResponse.redirect(new URL('/login', origin));
  res.cookies.set('oracle_session', '', { httpOnly: true, path: '/', maxAge: 0 });
  return res;
}
