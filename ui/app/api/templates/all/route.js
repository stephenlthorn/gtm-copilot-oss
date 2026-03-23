import { NextResponse } from 'next/server';
import { getSession } from '../../../../lib/session';
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET() {
  const session = await getSession();
  const h = {};
  if (session?.access_token) h['X-OpenAI-Token'] = session.access_token;
  const res = await fetch(`${API_BASE}/templates/all`, { headers: h });
  const data = await res.json().catch(() => []);
  return NextResponse.json(data, { status: res.status });
}
