import { NextResponse } from 'next/server';
import { getSession } from '../../../../lib/session';
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET() {
  const session = await getSession();
  const h = {};
  if (session?.access_token) h['X-OpenAI-Token'] = session.access_token;
  if (session?.email) h['X-User-Email'] = session.email;
  const res = await fetch(`${API_BASE}/chat/history?limit=100`, { headers: h });
  const data = await res.json().catch(() => []);
  return NextResponse.json(data, { status: res.status });
}
