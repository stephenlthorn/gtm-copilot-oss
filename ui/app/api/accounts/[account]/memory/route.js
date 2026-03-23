import { NextResponse } from 'next/server';
import { getSession } from '../../../../../lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request, { params }) {
  const session = await getSession();
  const headers = {};
  if (session?.access_token) headers['X-OpenAI-Token'] = session.access_token;
  const res = await fetch(`${API_BASE}/accounts/${params.account}/memory`, { headers });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
