'use client';
import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { marked } from 'marked';
import FeedbackButtons from './FeedbackButtons';
import IntelMeter from './IntelMeter';

// Configure marked once — GFM tables, line breaks, no mangling
marked.setOptions({ gfm: true, breaks: true });

export default function PersistentChat({ draft, populateSignal, ragEnabled = true, webSearchEnabled = true, tidbExpert = false, topK = 8, model = 'gpt-5.4', thinking = 'medium', section }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    fetch('/api/chat/history?model=' + encodeURIComponent(model))
      .then(r => r.ok ? r.json() : [])
      .then(history => {
        setMessages(history.map(m => ({ id: m.id, role: m.role, content: m.content })));
        setHistoryLoaded(true);
      })
      .catch(() => setHistoryLoaded(true));
  }, [model]);

  useEffect(() => {
    if (populateSignal > 0 && draft) setInput(draft);
  }, [populateSignal]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const autoGrow = (el) => {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  };

  const send = async () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput('');
    if (textareaRef.current) { textareaRef.current.style.height = 'auto'; }

    const userMsg = { id: Date.now() + '-u', role: 'user', content: q };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch('/api/oracle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'oracle', message: q, top_k: topK, rag_enabled: ragEnabled, web_search_enabled: webSearchEnabled, tidb_expert: tidbExpert, section: section || 'oracle' }),
      });
      if (res.status === 401) {
        window.location.href = '/login';
        return;
      }
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || 'Request failed');
      const assistantMsg = {
        id: Date.now() + '-a',
        role: 'assistant',
        content: data.answer || '',
        citations: data.citations || [],
        queryText: q,
      };
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
        {!historyLoaded && <div className="rep-chat-empty">Loading history…</div>}
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
          ref={textareaRef}
          className="rep-chat-input"
          value={input}
          onChange={e => { setInput(e.target.value); autoGrow(e.target); }}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="Type a message or use Populate to draft from a template… (Enter to send, Shift+Enter for newline)"
          disabled={loading}
        />
        <button className="btn btn-primary rep-chat-send" onClick={send} disabled={loading || !input.trim()}>
          {loading ? '…' : '→'}
        </button>
      </div>
      <IntelMeter model={model} thinking={thinking} ragEnabled={ragEnabled} webSearchEnabled={webSearchEnabled} />
    </div>
  );
}

// Extract unique URLs from markdown text for source attribution
function extractUrls(text) {
  const urls = new Set();
  // Markdown links: [label](url)
  const mdLinks = text.matchAll(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g);
  for (const m of mdLinks) urls.add(m[2]);
  // Bare URLs
  const bareUrls = text.matchAll(/(?<!\()(https?:\/\/[^\s)>\]"]+)/g);
  for (const m of bareUrls) urls.add(m[1]);
  return [...urls];
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);
  return (
    <button onClick={copy} className="msg-copy-btn" title="Copy message">
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  );
}

function SlackShareButton({ text }) {
  const [state, setState] = useState('idle');
  const [channel, setChannel] = useState('');
  const [showInput, setShowInput] = useState(false);

  const share = useCallback(async () => {
    if (!channel.trim()) return;
    setState('sending');
    try {
      const res = await fetch('/api/share/slack', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel: channel.trim(), text }),
      });
      if (res.ok) {
        setState('sent');
        setTimeout(() => { setState('idle'); setShowInput(false); }, 2000);
      } else {
        setState('error');
        setTimeout(() => setState('idle'), 3000);
      }
    } catch {
      setState('error');
      setTimeout(() => setState('idle'), 3000);
    }
  }, [channel, text]);

  if (!showInput) {
    return (
      <button onClick={() => setShowInput(true)} className="msg-copy-btn" title="Share to Slack">
        Share
      </button>
    );
  }

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <input
        type="text"
        value={channel}
        onChange={e => setChannel(e.target.value)}
        placeholder="#channel"
        onKeyDown={e => e.key === 'Enter' && share()}
        style={{ fontSize: '0.72rem', padding: '2px 6px', borderRadius: 4, border: '1px solid var(--border)', background: 'var(--bg-2)', color: 'var(--text)', width: 120 }}
        autoFocus
      />
      <button onClick={share} className="msg-copy-btn" disabled={state === 'sending'}>
        {state === 'sending' ? '...' : state === 'sent' ? '✓ Sent' : state === 'error' ? '✗ Failed' : 'Send'}
      </button>
      <button onClick={() => setShowInput(false)} className="msg-copy-btn">✕</button>
    </span>
  );
}

function MarkdownBody({ content }) {
  const html = useMemo(() => {
    if (typeof window === 'undefined') return '';
    const raw = marked.parse(content || '');
    // Sanitize to prevent XSS — allow standard HTML but strip scripts/event handlers
    const DOMPurify = require('dompurify');
    return DOMPurify.sanitize(raw, { ADD_ATTR: ['target', 'rel'] });
  }, [content]);
  // eslint-disable-next-line react/no-danger
  return <div className="msg-markdown" dangerouslySetInnerHTML={{ __html: html }} />;
}

function ChatMessage({ msg, mode }) {
  if (msg.role === 'user') {
    return (
      <div className="rep-chat-msg rep-chat-msg--user">
        <span style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</span>
        <div className="msg-actions">
          <CopyButton text={msg.content} />
        </div>
      </div>
    );
  }
  if (msg.role === 'error') {
    return <div className="rep-chat-msg rep-chat-msg--error">{msg.content}</div>;
  }

  // Sources: KB citations + URLs extracted from response text
  const kbCitations = msg.citations || [];
  const inlineUrls = extractUrls(msg.content);
  // Deduplicate: remove URLs already represented by KB citations
  const extraUrls = inlineUrls.filter(u => !kbCitations.some(c => c.url === u));

  const hasSources = kbCitations.length > 0 || extraUrls.length > 0;

  return (
    <div className="rep-chat-msg rep-chat-msg--assistant">
      <MarkdownBody content={msg.content} />

      {hasSources && (
        <div className="msg-sources">
          <div className="msg-sources-label">Sources</div>
          <div className="msg-sources-list">
            {kbCitations.map((c, i) => (
              <div key={i} className="msg-source-item">
                <span className="msg-source-type">{c.source_type || 'kb'}</span>
                {c.url
                  ? <a href={c.url} target="_blank" rel="noreferrer" className="msg-source-link">{c.title || c.url}</a>
                  : <span className="msg-source-title">{c.title || 'Source'}</span>
                }
                {c.quote && <span className="msg-source-quote">"{c.quote}"</span>}
              </div>
            ))}
            {extraUrls.map((url, i) => (
              <div key={'u' + i} className="msg-source-item">
                <span className="msg-source-type">web</span>
                <a href={url} target="_blank" rel="noreferrer" className="msg-source-link">
                  {(() => { try { return new URL(url).hostname; } catch { return url; } })()}
                </a>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="msg-actions">
        <CopyButton text={msg.content} />
        <SlackShareButton text={msg.content} />
        <FeedbackButtons message={msg.content} query={msg.queryText || ''} mode={mode} />
      </div>
    </div>
  );
}
