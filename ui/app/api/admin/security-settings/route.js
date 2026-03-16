import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function GET() {
  const session = await getSession();
  const res = await fetch(`${API_BASE}/admin/security/settings`, {
    headers: session ? { 'X-OpenAI-Token': session.access_token } : {},
  });
  if (!res.ok) return Response.json({}, { status: res.status });
  const data = await res.json();
  return Response.json(data);
}
