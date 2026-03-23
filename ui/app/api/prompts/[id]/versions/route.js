import { NextResponse } from 'next/server';
import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request, { params }) {
  const session = await getSession();
  const userEmail = session?.email || '';
  const { id } = await params;

  const headers = {
    'X-User-Email': userEmail,
  };

  const res = await fetch(`${API_BASE}/prompts/${encodeURIComponent(id)}/versions`, { headers });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
