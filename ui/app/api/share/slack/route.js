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

  try {
    const res = await fetch(`${API_BASE}/slack/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel: cleanChannel,
        text: `*Shared by ${session.name || session.email}:*\n\n${text}`,
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      return NextResponse.json({ error: err.slice(0, 300) }, { status: res.status });
    }

    return NextResponse.json({ ok: true });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
