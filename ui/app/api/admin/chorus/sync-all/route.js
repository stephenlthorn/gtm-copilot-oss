import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request) {
  const session = await getSession();
  const { searchParams } = new URL(request.url);
  const since = searchParams.get('since');
  const params = new URLSearchParams();
  if (since) params.set('since', since);
  const res = await fetch(`${API_BASE}/admin/chorus/sync-all?${params}`, {
    method: 'POST',
    headers: {
      ...(session ? { 'X-OpenAI-Token': session.access_token } : {}),
    },
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
