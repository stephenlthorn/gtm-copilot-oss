import Link from 'next/link';
import { apiGet } from '../../../lib/api';
import AccountIntelligenceClient from '../../../components/AccountIntelligenceClient';

export default async function AccountIntelligencePage() {
  const callsRaw = await apiGet('/calls?limit=1000').catch(() => []);
  const calls = Array.isArray(callsRaw) ? callsRaw : [];

  // Group calls by account
  const accountMap = {};
  for (const call of calls) {
    const name = (call.account || 'Unknown').trim();
    if (!accountMap[name]) {
      accountMap[name] = { name, calls: [], contacts: new Set(), stages: new Set(), reps: new Set() };
    }
    accountMap[name].calls.push(call);
    if (call.stage) accountMap[name].stages.add(call.stage);
    if (call.rep_email) accountMap[name].reps.add(call.rep_email);
    if (Array.isArray(call.participants)) {
      for (const p of call.participants) {
        const email = typeof p === 'string' ? p : p.email || p.name;
        if (email) accountMap[name].contacts.add(email);
      }
    }
  }

  const accounts = Object.values(accountMap)
    .map(a => ({
      name: a.name,
      callCount: a.calls.length,
      lastCallDate: a.calls.sort((x, y) => (y.date > x.date ? 1 : -1))[0]?.date || null,
      lastStage: Array.from(a.stages).pop() || null,
      contacts: Array.from(a.contacts).slice(0, 8),
      reps: Array.from(a.reps),
      callCount: a.calls.length,
      summaries: a.calls
        .filter(c => c.meeting_summary)
        .sort((x, y) => (y.date > x.date ? 1 : -1))
        .slice(0, 10)
        .map(c => `[${c.date}] ${c.meeting_summary}`),
    }))
    .sort((a, b) => (b.lastCallDate || '') > (a.lastCallDate || '') ? 1 : -1);

  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar-title">Account Intelligence</div>
          <div className="topbar-meta">{accounts.length} accounts · auto-populated from call history</div>
        </div>
        <Link
          href="/chat"
          style={{ fontSize: '0.78rem', color: 'var(--text-2)', padding: '0.3rem 0.6rem', borderRadius: '4px', textDecoration: 'none', border: '1px solid var(--border)' }}
        >
          ← Back to Chat
        </Link>
      </div>
      <AccountIntelligenceClient accounts={accounts} />
    </>
  );
}
