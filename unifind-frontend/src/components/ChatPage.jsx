import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  CalendarDays,
  CheckCircle2,
  Inbox,
  LockKeyhole,
  MapPin,
  Send,
  ShieldCheck,
} from "lucide-react";
import { getConversations, getMessages, sendMessage } from "../api";
import { formatClock, timeAgo } from "../utils";

const MESSAGE_POLL_MS = 4000; // how often an open chat checks for new messages
const LIST_POLL_MS = 8000; // how often the conversation list refreshes

function TypeTag({ type }) {
  return <span className={`status ${type.toLowerCase()}`}>{type} Item</span>;
}

export default function ChatPage({
  user,
  activeConvId,
  setActiveConvId,
  seedConv, // the chat that was just opened (so the header shows before the list loads)
  draft, // optional first message suggested by the "I think this is mine" button
  onDraftUsed,
  onActivity, // called when messages were read/sent, so the nav badges refresh
  onResolve, // (itemId) => Promise, marks the report as resolved
  onBack,
  onError,
}) {
  const [convs, setConvs] = useState(seedConv ? [seedConv] : []);
  const [listLoading, setListLoading] = useState(true);
  const [messages, setMessages] = useState([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const lastIdRef = useRef(0);
  const scrollRef = useRef(null);

  // keep the newest callbacks without re-starting the polling timers
  const cb = useRef({});
  cb.current = { onActivity, onError, onDraftUsed };

  const active =
    convs.find((c) => c.id === activeConvId) ||
    (seedConv && seedConv.id === activeConvId ? seedConv : null);

  // ---- conversation list (left column) ----
  const refreshList = useCallback(async () => {
    try {
      setConvs(await getConversations());
    } catch {
      /* offline or token expired: keep what we have */
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshList();
    const t = setInterval(() => {
      if (!document.hidden) refreshList();
    }, LIST_POLL_MS);
    return () => clearInterval(t);
  }, [refreshList]);

  // ---- messages of the open chat ----
  const merge = useCallback((incoming) => {
    if (!incoming.length) return;
    setMessages((prev) => {
      const seen = new Set(prev.map((m) => m.id));
      const fresh = incoming.filter((m) => !seen.has(m.id));
      if (!fresh.length) return prev;
      const next = [...prev, ...fresh].sort((a, b) => a.id - b.id);
      lastIdRef.current = next[next.length - 1].id;
      return next;
    });
  }, []);

  useEffect(() => {
    setMessages([]);
    lastIdRef.current = 0;
    setText(draft || "");
    if (draft) cb.current.onDraftUsed?.();
    if (!activeConvId) return undefined;

    let cancelled = false;
    let busy = false;
    const load = async (initial) => {
      if (busy) return;
      busy = true;
      if (initial) setMsgLoading(true);
      try {
        const rows = await getMessages(activeConvId, lastIdRef.current);
        if (cancelled) return;
        if (rows.length) {
          merge(rows);
          cb.current.onActivity?.(); // opening/reading clears the unread badges
          refreshList();
        }
      } catch (err) {
        if (initial && !cancelled) cb.current.onError?.(err.message);
      } finally {
        busy = false;
        if (initial && !cancelled) setMsgLoading(false);
      }
    };
    load(true);
    const t = setInterval(() => {
      if (!document.hidden) load(false);
    }, MESSAGE_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeConvId]);

  // stay scrolled to the newest message
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, activeConvId]);

  const submit = async (e) => {
    e.preventDefault();
    const body = text.trim();
    if (!body || sending || !active) return;
    setSending(true);
    try {
      merge([await sendMessage(active.id, body)]);
      setText("");
      refreshList();
    } catch (err) {
      cb.current.onError?.(err.message);
    } finally {
      setSending(false);
    }
  };

  const resolve = async () => {
    if (!active) return;
    if (!window.confirm("Mark this report as resolved? It will be removed from public search.")) return;
    try {
      await onResolve(active.item.id);
      refreshList();
    } catch (err) {
      cb.current.onError?.(err.message);
    }
  };

  const resolved = active?.item.status === "Resolved";

  return (
    <main className="wrap chat-page">
      <button className="back-link" onClick={onBack}>
        <ArrowLeft size={16} /> Back to items
      </button>
      <div className={`chat-layout with-inbox ${active ? "has-active" : ""}`}>
        {/* ---------- left: all my conversations ---------- */}
        <aside className="inbox">
          <div className="inbox-head">
            <h3>Messages</h3>
          </div>
          {listLoading && !convs.length ? (
            <p className="inbox-empty">Loading…</p>
          ) : convs.length ? (
            <ul className="inbox-list">
              {convs.map((c) => (
                <li key={c.id}>
                  <button
                    className={`inbox-row ${c.id === activeConvId ? "current" : ""}`}
                    onClick={() => setActiveConvId(c.id)}
                  >
                    <img src={c.item.image} alt="" />
                    <span className="inbox-text">
                      <strong>{c.item.title}</strong>
                      <small>
                        {c.other_name}
                        {c.last_message ? `: ${c.last_message.body}` : " · no messages yet"}
                      </small>
                    </span>
                    <span className="inbox-meta">
                      {c.last_message && <small>{timeAgo(c.last_message.created_at)}</small>}
                      {c.unread_count > 0 && <em className="count-badge static">{c.unread_count}</em>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="inbox-empty">
              No conversations yet. Open a report and choose <b>Message reporter</b> to start one.
            </p>
          )}
        </aside>

        {/* ---------- middle: the open chat ---------- */}
        <section className="chat-panel">
          {active ? (
            <>
              <div className="chat-header">
                <button className="icon-button thread-back" onClick={() => setActiveConvId(null)} aria-label="Back to messages">
                  <ArrowLeft size={18} />
                </button>
                <div className="chat-avatar letter">{active.other_name.slice(0, 1).toUpperCase()}</div>
                <div>
                  <h2>{active.other_name}</h2>
                  <p>
                    About “{active.item.title}” ·{" "}
                    {active.i_am_item_owner ? "your report" : "their report"}
                  </p>
                </div>
              </div>
              <div className="chat-safety">
                <LockKeyhole size={16} /> Your email and phone number are never shown here. Share
                personal details only when you feel sure.
              </div>
              <div className="messages" ref={scrollRef}>
                {msgLoading && !messages.length && <p className="chat-hint">Loading messages…</p>}
                {!msgLoading && !messages.length && (
                  <p className="chat-hint">
                    No messages yet. Say hello and describe the item so they know it is you.
                  </p>
                )}
                {messages.map((m) => (
                  <div key={m.id} className={`message ${m.sender_id === user.id ? "mine" : "other"}`}>
                    {m.body}
                    <small>{formatClock(m.created_at)}</small>
                  </div>
                ))}
              </div>
              {resolved && (
                <div className="chat-resolved">
                  <CheckCircle2 size={15} /> This report is resolved. You can still use this chat to
                  arrange the hand-over.
                </div>
              )}
              <form className="chat-compose" onSubmit={submit}>
                <input
                  placeholder="Type your message..."
                  value={text}
                  maxLength={1000}
                  onChange={(e) => setText(e.target.value)}
                  aria-label="Message"
                />
                <button className="send-btn" disabled={sending || !text.trim()} aria-label="Send">
                  <Send size={17} />
                </button>
              </form>
            </>
          ) : (
            <div className="chat-empty">
              <Inbox size={38} />
              <h3>Select a conversation</h3>
              <p>Your chats with people about lost and found items appear here.</p>
            </div>
          )}
        </section>

        {/* ---------- right: the item being discussed ---------- */}
        {active && (
          <aside className="chat-item">
            <h3>Item information</h3>
            <img src={active.item.image} alt={active.item.title} />
            <strong>{active.item.title}</strong>
            <TypeTag type={active.item.type} />
            <p>
              <CalendarDays size={14} />
              {active.item.date}
            </p>
            <p>
              <MapPin size={14} />
              {active.item.district}
            </p>
            {active.i_am_item_owner && !resolved && (
              <button className="btn btn-primary resolve-btn" onClick={resolve}>
                <CheckCircle2 size={16} /> Mark as resolved
              </button>
            )}
            <div className="privacy-card">
              <ShieldCheck />
              <p>
                Meet in a public place and check the item together before handing it over. Never
                send money.
              </p>
            </div>
          </aside>
        )}
      </div>
    </main>
  );
}
