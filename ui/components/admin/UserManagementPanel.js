'use client';

import { useState, useEffect } from 'react';

const ROLES = ['sales_rep', 'se', 'marketing', 'admin'];

export default function UserManagementPanel() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});
  const [roleEdits, setRoleEdits] = useState({});
  const [messages, setMessages] = useState({});

  useEffect(() => {
    fetch('/api/admin/users')
      .then(r => r.json())
      .then(data => {
        const list = Array.isArray(data) ? data : data.users || [];
        setUsers(list);
        const initial = {};
        for (const u of list) { initial[u.id] = u.role; }
        setRoleEdits(initial);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const saveRole = async (userId) => {
    setSaving(prev => ({ ...prev, [userId]: true }));
    setMessages(prev => ({ ...prev, [userId]: '' }));
    try {
      const res = await fetch(`/api/admin/users/${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: roleEdits[userId] }),
      });
      if (!res.ok) throw new Error('Save failed');
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, role: roleEdits[userId] } : u));
      setMessages(prev => ({ ...prev, [userId]: 'Saved' }));
    } catch {
      setMessages(prev => ({ ...prev, [userId]: 'Failed' }));
    } finally {
      setSaving(prev => ({ ...prev, [userId]: false }));
    }
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">User Management</span>
        <span className="tag">{users.length} users</span>
      </div>
      <div className="panel-body">
        {loading ? (
          <div className="status-row">Loading…</div>
        ) : users.length === 0 ? (
          <div className="status-row">No users found.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Name</th>
                <th>Role</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td className="row-title">{u.email}</td>
                  <td style={{ color: 'var(--text-2)' }}>{u.name || '—'}</td>
                  <td>
                    <select
                      className="input"
                      style={{ width: 'auto', padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                      value={roleEdits[u.id] || u.role || ''}
                      onChange={e => setRoleEdits(prev => ({ ...prev, [u.id]: e.target.value }))}
                    >
                      {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td style={{ fontSize: '0.72rem', color: 'var(--text-3)' }}>
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <button
                      className="btn btn-primary"
                      style={{ fontSize: '0.72rem', padding: '0.25rem 0.6rem' }}
                      onClick={() => saveRole(u.id)}
                      disabled={saving[u.id] || roleEdits[u.id] === u.role}
                    >
                      {saving[u.id] ? 'Saving…' : 'Save'}
                    </button>
                    {messages[u.id] && (
                      <span style={{ fontSize: '0.72rem', color: messages[u.id] === 'Saved' ? 'var(--success)' : 'var(--danger)' }}>
                        {messages[u.id]}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
