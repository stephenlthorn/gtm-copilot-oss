import RepExecutionWidget from '../../../components/RepExecutionWidget';

export default function RepPage() {
  return (
    <>
      <div className="topbar">
        <div>
          <div className="topbar-title">Sales Rep</div>
          <div className="topbar-meta">Account execution · follow-ups · strategic planning</div>
        </div>
      </div>
      <div className="content">
        <RepExecutionWidget />
      </div>
    </>
  );
}
