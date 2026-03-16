import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET() {
  const session = await getSession();
  if (!session?.email) return Response.json({ error: 'unauthorized' }, { status: 401 });
  try {
    const res = await fetch(`${API_BASE}/user/preferences`, {
      headers: { 'X-User-Email': session.email },
      cache: 'no-store',
    });
    if (!res.ok) {
      return Response.json({ llm_model: null, reasoning_effort: null });
    }
    const data = await res.json();
    return Response.json(data);
  } catch {
    return Response.json({ llm_model: null, reasoning_effort: null });
  }
}

export async function PUT(request) {
  const session = await getSession();
  if (!session?.email) return Response.json({ error: 'unauthorized' }, { status: 401 });
  const body = await request.json();
  try {
    const res = await fetch(`${API_BASE}/user/preferences`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Email': session.email,
      },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch (err) {
    return Response.json({ error: err.message }, { status: 500 });
  }
}
