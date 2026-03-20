'use client';

import { useState, useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import OracleChat from './OracleChat';

export default function OracleChatOverlay() {
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  // Close popup when navigating to the dedicated oracle page
  useEffect(() => {
    if (pathname === '/oracle') {
      setOpen(false);
      setMinimized(false);
    }
  }, [pathname]);

  const handleExpand = () => {
    router.push('/oracle');
    setOpen(false);
    setMinimized(false);
  };

  if (pathname === '/oracle') return null;

  return (
    <>
      {open && !minimized && (
        <div className="oracle-overlay">
          <OracleChat
            onMinimize={() => setMinimized(true)}
            onExpand={handleExpand}
          />
        </div>
      )}

      <button
        className={`oracle-fab${minimized ? ' oracle-fab--badge' : ''}`}
        onClick={() => {
          if (minimized) {
            setMinimized(false);
            setOpen(true);
          } else {
            setOpen((v) => !v);
          }
        }}
        title="Ask Oracle"
      >
        {minimized ? '◎ Oracle' : open ? '✕' : '◎'}
      </button>
    </>
  );
}
