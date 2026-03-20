export default function AppLayout({ children }) {
  return (
    <div className="shell">
      <div className="main">
        {children}
      </div>
    </div>
  );
}
