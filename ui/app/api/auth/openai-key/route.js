import { NextResponse } from 'next/server';
import { getSession } from '@/lib/session';

const COOKIE_NAME = 'oracle_session';
const MAX_AGE = 60 * 60 * 8; // 8 hours

export async function POST(request) {
  const session = await getSession();
  if (!session) return NextResponse.json({ error: 'unauthenticated' }, { status: 401 });

  const body = await request.json();
  const api_key = body?.api_key?.trim();
  if (!api_key) return NextResponse.json({ error: 'api_key is required' }, { status: 400 });

  const updated = { ...session, openai_key: api_key };
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE_NAME, JSON.stringify(updated), {
    httpOnly: true,
    sameSite: 'lax',
    path: '/',
    maxAge: MAX_AGE,
  });
  return res;
}
