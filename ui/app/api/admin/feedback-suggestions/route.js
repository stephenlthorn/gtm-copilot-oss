import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request) {
  const session = await getSession();
  const body = await request.json();
  const res = await fetch(`${API_BASE}/admin/feedback-suggestions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(session ? { 'X-OpenAI-Token': session.access_token } : {}),
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
