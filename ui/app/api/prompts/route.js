import { NextResponse } from 'next/server';
import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request) {
  const session = await getSession();
  const userEmail = session?.email || '';

  const headers = {
    'X-User-Email': userEmail,
  };

  const res = await fetch(`${API_BASE}/prompts`, { headers });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
