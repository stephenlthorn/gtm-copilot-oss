import { getSession } from '../../lib/session';
import Sidebar from '../../components/Sidebar';

export default async function AppLayout({ children }) {
  const session = await getSession();
  const email = session?.email || 'oracle@company.local';
  const hasSession = Boolean(session?.access_token);

  return (
    <div className="shell">
      <Sidebar email={email} hasSession={hasSession} />
      <div className="main">
        <div className="internal-reminder">
          Internal data only. Do not share externally.
        </div>
        {children}
      </div>
    </div>
  );
}
