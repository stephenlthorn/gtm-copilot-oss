import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request, { params }) {
  const session = await getSession();
  const { callId } = params;
  const res = await fetch(`${API_BASE}/admin/chorus/probe/${encodeURIComponent(callId)}`, {
    headers: session
      ? { 'X-OpenAI-Token': session.access_token, 'X-User-Email': session.email || '' }
      : {},
    cache: 'no-store',
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
