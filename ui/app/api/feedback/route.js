import { apiGet } from '../../../lib/api';
import { getSession } from '../../../lib/session';

function getApiBase() {
  return process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
}

export async function POST(request) {
  const session = await getSession();
  if (!session?.email) return Response.json({ error: 'unauthorized' }, { status: 401 });
  const body = await request.json();
  const res = await fetch(`${getApiBase()}/feedback`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Email': session.email,
    },
    body: JSON.stringify(body),
    cache: 'no-store',
  });
  if (!res.ok) {
    const msg = await res.text();
    return Response.json({ error: msg }, { status: res.status });
  }
  const data = await res.json();
  return Response.json(data, { status: 201 });
}

export async function GET(request) {
  const session = await getSession();
  if (!session?.email) return Response.json({ error: 'unauthorized' }, { status: 401 });
  const { searchParams } = new URL(request.url);
  const mode = searchParams.get('mode');
  const limit = searchParams.get('limit') || '20';
  const qs = mode ? `?mode=${mode}&limit=${limit}` : `?limit=${limit}`;
  const data = await apiGet(`/feedback${qs}`);
  return Response.json(data);
}
