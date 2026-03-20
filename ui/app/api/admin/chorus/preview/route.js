import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request) {
  const session = await getSession();
  const { searchParams } = new URL(request.url);
  const params = new URLSearchParams();
  if (searchParams.get('since')) params.set('since', searchParams.get('since'));
  if (searchParams.get('until')) params.set('until', searchParams.get('until'));

  const res = await fetch(`${API_BASE}/admin/chorus/preview?${params}`, {
    headers: session ? { 'X-OpenAI-Token': session.access_token } : {},
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
