import { NextResponse } from 'next/server';
import { getSession } from '../../../lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request) {
  const session = await getSession();
  const { searchParams } = new URL(request.url);

  const params = new URLSearchParams();
  const account = searchParams.get('account');
  const limit = searchParams.get('limit');
  if (account) params.set('account', account);
  if (limit) params.set('limit', limit);

  const headers = {};
  if (session?.access_token) {
    headers['X-OpenAI-Token'] = session.access_token;
  }

  const res = await fetch(`${API_BASE}/calls?${params}`, { headers });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
