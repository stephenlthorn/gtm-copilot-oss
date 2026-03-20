'use client';

import { useState, useRef, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'oracle_chat_history';

function loadHistory() {
  if (typeof window === 'undefined') return [];
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveHistory(messages) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.slice(-100)));
  } catch {}
}

export default function OracleChat({ fullScreen = false, onMinimize, onExpand }) {
  const [messages, setMessages] = useState(() => loadHistory());
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  useEffect(() => {
    if (!loading) inputRef.current?.focus();
  }, [loading]);

  const send = useCallback(async () => {
    const q = input.trim();
    if (!q || loading) return;

    const userMsg = { role: 'user', text: q, ts: Date.now() };
    const updated = [...messages, userMsg];
    setMessages(updated);
    saveHistory(updated);
    setInput('');
    setLoading(true);
    setError('');

    try {
      const res = await fetch('/api/oracle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'oracle', message: q, top_k: 8 }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const assistantMsg = {
        role: 'assistant',
        text: data.answer || 'No answer returned.',
        citations: data.citations || [],
        ts: Date.now(),
      };
      const withReply = [...updated, assistantMsg];
      setMessages(withReply);
      saveHistory(withReply);
    } catch (err) {
      setError(String(err?.message || err));
    } finally {
      setLoading(false);
    }
  }, [input, loading, messages]);

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const clearHistory = () => {
    setMessages([]);
    saveHistory([]);
  };

  return (
    <div className={fullScreen ? 'oracle-chat oracle-chat--full' : 'oracle-chat oracle-chat--popup'}>
      <div className="oracle-chat-header">
        <span className="oracle-chat-title">
          <span style={{ marginRight: '0.4rem' }}>◎</span>
          Ask Oracle
        </span>
        <div className="oracle-chat-controls">
          {messages.length > 0 && (
            <button
              className="oracle-chat-ctrl"
              onClick={clearHistory}
              title="Clear history"
            >
              ✕ Clear
            </button>
          )}
          {!fullScreen && onExpand && (
            <button className="oracle-chat-ctrl" onClick={onExpand} title="Full screen">
              ⤢
            </button>
          )}
          {!fullScreen && onMinimize && (
            <button className="oracle-chat-ctrl" onClick={onMinimize} title="Minimize">
              −
            </button>
          )}
        </div>
      </div>

      <div className="oracle-chat-messages">
        {messages.length === 0 && (
          <div className="oracle-chat-empty">
            Ask any GTM or technical question — Oracle searches your knowledge base.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`oracle-msg oracle-msg--${m.role}`}>
            <div className="oracle-msg-text">{m.text}</div>
            {m.citations?.length > 0 && (
              <div className="oracle-msg-citations">
                {m.citations.slice(0, 4).map((c, j) => (
                  <span key={j} className="oracle-citation">
                    {c.title || c.source_id}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="oracle-msg oracle-msg--assistant oracle-msg--thinking">
            <span className="oracle-thinking-dots">
              <span /><span /><span />
            </span>
          </div>
        )}
        {error && (
          <div className="oracle-msg oracle-msg--error">{error}</div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="oracle-chat-input-row">
        <textarea
          ref={inputRef}
          className="oracle-chat-input"
          rows={2}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask a question... (Enter to send, Shift+Enter for newline)"
          disabled={loading}
        />
        <button
          className="btn btn-primary oracle-chat-send"
          onClick={send}
          disabled={loading || !input.trim()}
        >
          {loading ? '...' : '→'}
        </button>
      </div>
    </div>
  );
}
