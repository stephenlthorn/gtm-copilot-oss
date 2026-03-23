import { NextResponse } from 'next/server';
import { getSession } from '../../../../lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request) {
  const session = await getSession();
  const body = await request.json();
  const res = await fetch(`${API_BASE}/calls/manual`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(session?.access_token ? { 'X-OpenAI-Token': session.access_token } : {}),
      ...(session?.email ? { 'X-User-Email': session.email } : {}),
    },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let payload;
  try { payload = JSON.parse(text); } catch { payload = { error: text }; }
  return NextResponse.json(payload, { status: res.status });
}
