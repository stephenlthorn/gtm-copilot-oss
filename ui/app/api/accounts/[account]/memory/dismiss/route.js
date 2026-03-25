import { NextResponse } from 'next/server';
import { getSession } from '../../../../../../lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request, { params }) {
  const session = await getSession();
  const { account } = await params;
  const res = await fetch(`${API_BASE}/accounts/${account}/memory/dismiss`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(session?.access_token ? { 'X-OpenAI-Token': session.access_token } : {}),
      ...(session?.email ? { 'X-User-Email': session.email } : {}),
    },
    body: '{}',
  });
  const text = await res.text();
  let payload;
  try { payload = JSON.parse(text); } catch { payload = { error: text }; }
  return NextResponse.json(payload, { status: res.status });
}
