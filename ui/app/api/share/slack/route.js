import { NextResponse } from 'next/server';
import { getSession } from '../../../../lib/session';

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000';

export async function POST(request) {
  const session = await getSession();
  if (!session?.email) return NextResponse.json({ error: 'unauthenticated' }, { status: 401 });

  const { channel, text } = await request.json();
  if (!channel || !text) {
    return NextResponse.json({ error: 'channel and text are required' }, { status: 400 });
  }

  const cleanChannel = channel.replace(/^#/, '').trim();
  if (!cleanChannel) {
    return NextResponse.json({ error: 'invalid channel name' }, { status: 400 });
  }

  const sanitizeSlack = (s) => String(s).replace(/[<>&]/g, '');

  try {
    const res = await fetch(`${API_BASE}/slack/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel: cleanChannel,
        text: `*Shared by ${sanitizeSlack(session.name || session.email)}:*\n\n${text}`,
      }),
    });

    if (!res.ok) {
      return NextResponse.json({ error: 'Failed to send message' }, { status: res.status });
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    console.error('Slack share error:', err.message || 'Unknown error');
    return NextResponse.json({ error: 'Failed to send message' }, { status: 500 });
  }
}
