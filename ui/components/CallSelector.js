'use client';
import { useEffect, useRef, useState, useCallback } from 'react';

const SYNC_MS = 60 * 60 * 1000;

// onChange receives array of full call objects
export default function CallSelector({ account, selectedCalls = [], onChange }) {
  const [allCalls, setAllCalls] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastSync, setLastSync] = useState(null);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [sortDir, setSortDir] = useState('desc');
  const timer = useRef(null);

  const fetchCalls = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/calls?limit=200');
      const data = await res.json();
      setAllCalls(Array.isArray(data) ? data : []);
      setLastSync(new Date());
    } catch { setAllCalls([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchCalls();
    timer.current = setInterval(fetchCalls, SYNC_MS);
    return () => clearInterval(timer.current);
  }, [fetchCalls]);

  const toggleSort = (field) => {
    if (sortBy === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(field); setSortDir(field === 'date' ? 'desc' : 'asc'); }
  };

  const filterTerm = search.trim() || account?.trim() || '';
  const filtered = filterTerm
    ? allCalls.filter(c =>
        (c.account || '').toLowerCase().includes(filterTerm.toLowerCase()) ||
        (c.opportunity || '').toLowerCase().includes(filterTerm.toLowerCase()))
    : allCalls;

  const calls = [...filtered].sort((a, b) => {
    const av = sortBy === 'date' ? (a.date || '') : (a.account || '').toLowerCase();
    const bv = sortBy === 'date' ? (b.date || '') : (b.account || '').toLowerCase();
    return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
  });

  const selectedIds = selectedCalls.map(c => c.chorus_call_id);

  const toggle = call => {
    const id = call.chorus_call_id;
    const already = selectedCalls.find(c => c.chorus_call_id === id);
    onChange(already ? selectedCalls.filter(c => c.chorus_call_id !== id) : [...selectedCalls, call]);
  };

  const SortBtn = ({ field, label }) => (
    <button className={`rep-sort-btn${sortBy === field ? ' rep-sort-btn--active' : ''}`} onClick={() => toggleSort(field)}>
      {label}{sortBy === field ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
    </button>
  );

  return (
    <div style={{ display: 'grid', gap: '0.4rem' }}>
      <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
        <input className="input" style={{ flex: 1, fontSize: '0.78rem', padding: '0.3rem 0.5rem' }}
          placeholder={account?.trim() ? `"${account}" — type to override` : 'Search account or opportunity…'}
          value={search} onChange={e => setSearch(e.target.value)} />
        <SortBtn field="date" label="Date" />
        <SortBtn field="company" label="Co." />
        <button className="rep-sort-btn" onClick={fetchCalls} disabled={loading}>{loading ? '…' : '↻'}</button>
      </div>
      <div style={{ fontSize: '0.68rem', color: 'var(--text-3)' }}>
        {calls.length}/{allCalls.length} calls
        {lastSync && ` · ${lastSync.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
        {selectedIds.length > 0 && ` · ${selectedIds.length} selected`}
      </div>
      {loading && allCalls.length === 0 ? (
        <div style={{ fontSize: '0.78rem', color: 'var(--text-3)', padding: '0.5rem 0' }}>Loading…</div>
      ) : (
        <div className="call-list">
          {calls.length === 0 && <div style={{ fontSize: '0.78rem', color: 'var(--text-3)' }}>No calls found.</div>}
          {calls.map(c => {
            const checked = Boolean(selectedCalls.find(sc => sc.chorus_call_id === c.chorus_call_id));
            return (
              <label key={c.chorus_call_id} className={`call-item${checked ? ' call-item--selected' : ''}`}>
                <input type="checkbox" checked={checked} onChange={() => toggle(c)} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: checked ? 600 : 400, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {c.account || 'Unknown'}{c.opportunity ? ` — ${c.opportunity}` : ''}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-3)' }}>
                    {c.date ? new Date(c.date).toLocaleDateString() : '—'}
                    {c.stage ? ` · ${c.stage}` : ''}
                    {c.rep_email ? ` · ${c.rep_email}` : ''}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}
