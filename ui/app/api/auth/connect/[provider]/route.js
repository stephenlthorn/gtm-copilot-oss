import { NextResponse } from 'next/server';
import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request, { params }) {
  const session = await getSession();
  if (!session?.email) return NextResponse.json({ error: 'unauthenticated' }, { status: 401 });

  const { provider } = await params;
  const body = await request.json();

  const res = await fetch(`${API_BASE}/auth/connect/${provider}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Email': session.email,
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(request, { params }) {
  const session = await getSession();
  if (!session?.email) return NextResponse.json({ error: 'unauthenticated' }, { status: 401 });

  const { provider } = await params;

  const res = await fetch(`${API_BASE}/auth/connect/${provider}`, {
    method: 'DELETE',
    headers: { 'X-User-Email': session.email },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
