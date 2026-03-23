import { NextResponse } from 'next/server';
import { getSession } from '../../../../lib/session';
const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

async function headers(session) {
  const h = { 'Content-Type': 'application/json' };
  if (session?.access_token) h['X-OpenAI-Token'] = session.access_token;
  if (session?.email) h['X-User-Email'] = session.email;
  return h;
}

export async function GET() {
  const session = await getSession();
  const res = await fetch(`${API_BASE}/user/templates`, { headers: await headers(session) });
  const data = await res.json().catch(() => []);
  return NextResponse.json(data, { status: res.status });
}

export async function PUT(request) {
  const session = await getSession();
  const { section_key, ...body } = await request.json();
  const res = await fetch(`${API_BASE}/user/templates/${section_key}`, {
    method: 'PUT',
    headers: await headers(session),
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}
