'use client';

import { useState, useEffect } from 'react';

export default function KBConfigPanel() {
  const [config, setConfig] = useState(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [driveSyncing, setDriveSyncing] = useState(false);
  const [driveJob, setDriveJob] = useState(null);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetch('/api/admin/kb-config')
      .then(r => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(data => setConfig(data))
      .catch(() => setError('Could not load KB config. Is the backend running?'));

    fetch('/api/admin/sync/drive/jobs/latest')
      .then(r => r.json())
      .then(data => { if (data?.job) setDriveJob(data.job); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!driveJob?.job_id) return;
    if (!['queued', 'running'].includes(driveJob.status)) return;

    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/admin/sync/drive/jobs/${driveJob.job_id}`, { cache: 'no-store' });
        const data = await res.json();
        if (data?.job) {
          setDriveJob(data.job);
          if (!['queued', 'running'].includes(data.job.status)) setDriveSyncing(false);
        }
      } catch { /* keep polling */ }
    }, 2000);

    return () => clearInterval(timer);
  }, [driveJob?.job_id, driveJob?.status]);

  const save = async () => {
    setSaving(true);
    setMessage('');
    try {
      const res = await fetch('/api/admin/kb-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error('Save failed');
      const updated = await res.json();
      setConfig(updated);
      setMessage('✓ Saved');
    } catch {
      setMessage('✗ Save failed');
    } finally {
      setSaving(false);
    }
  };

  const startDriveSync = async () => {
    setDriveSyncing(true);
    setMessage('');
    try {
      const res = await fetch('/api/admin/sync/drive/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ since: null }),
      });
      const data = await res.json();
      if (data?.job) setDriveJob(data.job);
      if (data?.accepted === false && data?.reason === 'already_running') {
        setMessage('Drive sync already running.');
      } else {
        setMessage('✓ Drive sync started');
      }
    } catch {
      setMessage('✗ Failed to start Drive sync');
      setDriveSyncing(false);
    }
  };

  const set = (key, value) => setConfig(prev => ({ ...prev, [key]: value }));

  if (error) {
    return (
      <div className="panel">
        <div className="panel-header"><span className="panel-title">Knowledge Base</span></div>
        <div className="panel-body" style={{ fontSize: '0.8rem', color: 'var(--text-3)' }}>{error}</div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="panel">
        <div className="panel-header"><span className="panel-title">Knowledge Base</span></div>
        <div className="panel-body" style={{ fontSize: '0.8rem', color: 'var(--text-3)' }}>Loading…</div>
      </div>
    );
  }

  const driveProgress = driveJob?.progress || {};
  const filesSeen = Number(driveProgress.files_seen || 0);
  const processed = Number(driveProgress.processed || 0);
  const pct = filesSeen > 0 ? Math.min(100, Math.round((processed / filesSeen) * 100)) : 0;

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Knowledge Base</span>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '1.25rem' }}>

        {/* Tools */}
        <div style={{ display: 'grid', gap: '0.4rem' }}>
          <label style={{ fontSize: '0.74rem', color: 'var(--text-3)' }}>Tools</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.82rem' }}>
              <input
                type="checkbox"
                checked={!!config.web_search_enabled}
                onChange={e => set('web_search_enabled', e.target.checked)}
              />
              Web Search
              <span style={{ fontSize: '0.74rem', color: 'var(--text-3)' }}>— searches the web when relevant</span>
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.82rem' }}>
              <input
                type="checkbox"
                checked={!!config.code_interpreter_enabled}
                onChange={e => set('code_interpreter_enabled', e.target.checked)}
              />
              Code Interpreter
              <span style={{ fontSize: '0.74rem', color: 'var(--text-3)' }}>— run Python, analyse data</span>
            </label>
          </div>
        </div>

        {/* Sources */}
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.74rem', color: 'var(--text-3)' }}>Sources</label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.82rem' }}>
            <input
              type="checkbox"
              checked={!!config.google_drive_enabled}
              onChange={e => set('google_drive_enabled', e.target.checked)}
            />
            Google Drive
          </label>
          {config.google_drive_enabled && (
            <input
              className="input"
              placeholder="Folder IDs to index (comma-separated, leave blank for all)"
              value={config.google_drive_folder_ids || ''}
              onChange={e => set('google_drive_folder_ids', e.target.value)}
              style={{ fontSize: '0.78rem' }}
            />
          )}
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.82rem' }}>
            <input
              type="checkbox"
              checked={!!config.feishu_enabled}
              onChange={e => set('feishu_enabled', e.target.checked)}
            />
            Feishu / Lark
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontSize: '0.82rem' }}>
            <input
              type="checkbox"
              checked={!!config.chorus_enabled}
              onChange={e => set('chorus_enabled', e.target.checked)}
            />
            Call Transcripts (Chorus)
          </label>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', flexWrap: 'wrap', paddingTop: '0.25rem' }}>
          <button className="btn btn-primary" onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
          <button
            className="btn"
            onClick={startDriveSync}
            disabled={driveSyncing || driveJob?.status === 'running' || driveJob?.status === 'queued'}
          >
            {driveSyncing || driveJob?.status === 'running' || driveJob?.status === 'queued'
              ? 'Syncing Drive…'
              : 'Sync Drive'}
          </button>
          {message && (
            <span style={{ fontSize: '0.78rem', color: message.startsWith('✓') ? 'var(--accent)' : '#ef4444' }}>
              {message}
            </span>
          )}
        </div>

        {/* Drive sync job status */}
        {driveJob && (
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: '0.75rem', display: 'grid', gap: '0.4rem' }}>
            <div style={{ fontSize: '0.74rem', color: 'var(--text-3)', textTransform: 'uppercase' }}>Drive Sync Job</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span className={`tag ${driveJob.status === 'completed' ? 'tag-green' : driveJob.status === 'failed' ? 'tag-red' : ''}`}>
                {driveJob.status}
              </span>
              <span style={{ fontSize: '0.74rem', color: 'var(--text-3)', fontFamily: 'monospace' }}>
                {driveJob.job_id?.slice(0, 8)}
              </span>
              {filesSeen > 0 && (
                <span style={{ fontSize: '0.74rem', color: 'var(--text-3)' }}>
                  {processed}/{filesSeen} ({pct}%)
                </span>
              )}
            </div>
            {(driveJob.status === 'running' || driveJob.status === 'queued') && (
              <div style={{ height: '5px', background: 'var(--bg-soft)', borderRadius: '999px', overflow: 'hidden' }}>
                <div style={{
                  width: `${filesSeen > 0 ? pct : 15}%`,
                  height: '100%',
                  background: 'var(--accent)',
                  transition: 'width 300ms ease',
                }} />
              </div>
            )}
            {driveJob.result && (
              <div style={{ fontSize: '0.76rem', color: 'var(--text-2)' }}>
                Indexed: {driveJob.result.indexed ?? 0} · Skipped: {driveJob.result.skipped ?? 0} · Files: {driveJob.result.files_seen ?? 0}
              </div>
            )}
            {driveJob.error && (
              <div style={{ fontSize: '0.76rem', color: '#ef4444' }}>{driveJob.error}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
