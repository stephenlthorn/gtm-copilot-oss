import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET(request) {
  const session = await getSession();
  const { searchParams } = new URL(request.url);
  const days = searchParams.get('days') || '7';
  const res = await fetch(`${API_BASE}/admin/feedback-patterns?days=${days}`, {
    headers: session ? { 'X-OpenAI-Token': session.access_token } : {},
  });
  const data = await res.json();
  return Response.json(data, { status: res.status });
}
