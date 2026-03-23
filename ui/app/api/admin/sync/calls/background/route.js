import { getSession } from '@/lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST() {
  const session = await getSession();
  try {
    await fetch(`${API_BASE}/admin/sync/calls/background`, {
      method: 'POST',
      headers: session ? { 'X-OpenAI-Token': session.access_token } : {},
    });
  } catch {
    // best-effort — don't block login
  }
  return Response.json({ accepted: true });
}
