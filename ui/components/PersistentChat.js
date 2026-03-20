'use client';
import { useState, useEffect, useRef } from 'react';
import FeedbackButtons from './FeedbackButtons';

export default function PersistentChat({ draft, populateSignal, ragEnabled = true, webSearchEnabled = true, topK = 8, model = 'gpt-5.4', section }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const messagesEndRef = useRef(null);

  // Load history on mount
  useEffect(() => {
    fetch('/api/chat/history?model=' + encodeURIComponent(model))
      .then(r => r.ok ? r.json() : [])
      .then(history => {
        setMessages(history.map(m => ({ id: m.id, role: m.role, content: m.content })));
        setHistoryLoaded(true);
      })
      .catch(() => setHistoryLoaded(true));
  }, []);

  // When draft changes (populate fired), set input to the draft
  useEffect(() => {
    if (populateSignal > 0 && draft) {
      setInput(draft);
    }
  }, [populateSignal]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const send = async () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput('');

    const userMsg = { id: Date.now() + '-u', role: 'user', content: q };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch('/api/oracle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'oracle', message: q, top_k: topK, rag_enabled: ragEnabled, web_search_enabled: webSearchEnabled, section: section || 'oracle' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || 'Request failed');
      const assistantMsg = { id: Date.now() + '-a', role: 'assistant', content: data.answer || '', citations: data.citations || [], queryText: q };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      setMessages(prev => [...prev, { id: Date.now() + '-e', role: 'error', content: String(err?.message || err) }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rep-chat">
      <div className="rep-chat-messages">
        {!historyLoaded && (
          <div className="rep-chat-empty">Loading history…</div>
        )}
        {historyLoaded && messages.length === 0 && (
          <div className="rep-chat-empty">
            <div style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>◎</div>
            Select a section, fill in the fields, then click Populate to draft a prompt — or ask anything below.
          </div>
        )}
        {messages.map(msg => <ChatMessage key={msg.id} msg={msg} mode={section || 'oracle'} />)}
        {loading && (
          <div className="rep-chat-msg rep-chat-msg--assistant">
            <div className="oracle-thinking-dots"><span /><span /><span /></div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="rep-chat-input-row">
        <textarea
          className="rep-chat-input"
          rows={4}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }}}
          placeholder="Type a message or use Populate to draft from a template… (Enter to send, Shift+Enter for newline)"
          disabled={loading}
        />
        <button className="btn btn-primary rep-chat-send" onClick={send} disabled={loading || !input.trim()}>
          {loading ? '…' : '→'}
        </button>
      </div>
    </div>
  );
}

function ChatMessage({ msg, mode }) {
  if (msg.role === 'user') {
    return (
      <div className="rep-chat-msg rep-chat-msg--user">
        <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
      </div>
    );
  }
  if (msg.role === 'error') {
    return <div className="rep-chat-msg rep-chat-msg--error">{msg.content}</div>;
  }
  return (
    <div className="rep-chat-msg rep-chat-msg--assistant">
      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{msg.content}</div>
      {msg.citations?.length > 0 && (
        <details style={{ marginTop: '0.5rem' }}>
          <summary style={{ fontSize: '0.72rem', color: 'var(--text-3)', cursor: 'pointer' }}>
            {msg.citations.length} source{msg.citations.length !== 1 ? 's' : ''}
          </summary>
          <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1rem', fontSize: '0.72rem', color: 'var(--text-2)' }}>
            {msg.citations.map((c, i) => (
              <li key={i}>
                {c.url ? <a href={c.url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)' }}>{c.title || c.url}</a> : (c.title || 'Source')}
              </li>
            ))}
          </ul>
        </details>
      )}
      <FeedbackButtons message={msg.content} query={msg.queryText || ''} mode={mode} />
    </div>
  );
}
