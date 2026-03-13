import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST() {
  const session = await getSession();
  try {
    const res = await fetch(`${API_BASE}/admin/restart-api`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(session ? { 'X-OpenAI-Token': session.access_token } : {}),
      },
    });
    const data = await res.json().catch(() => ({ ok: true, message: 'Restarting…' }));
    return Response.json(data, { status: 200 });
  } catch {
    // The API may close the connection mid-restart — that's fine
    return Response.json({ ok: true, message: 'API container restarting…' }, { status: 200 });
  }
}
