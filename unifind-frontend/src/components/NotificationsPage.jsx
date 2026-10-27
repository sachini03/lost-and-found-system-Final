import React, { useCallback, useEffect, useState } from "react";
import { BellOff, CheckCircle2, Clock3, MessageCircle } from "lucide-react";
import { getNotifications, markAllNotificationsRead, markNotificationRead } from "../api";
import { timeAgo } from "../utils";

const ICONS = {
  message: { icon: <MessageCircle />, tone: "blue" },
  resolved: { icon: <CheckCircle2 />, tone: "green" },
};

export default function NotificationsPage({ onOpenChat, onChanged, onError }) {
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setList(await getNotifications());
    } catch (err) {
      onError?.(err.message);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => {
      if (!document.hidden) load();
    }, 15000);
    return () => clearInterval(t);
  }, [load]);

  const open = async (n) => {
    if (!n.is_read) {
      setList((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
      markNotificationRead(n.id).then(onChanged).catch(() => {});
    }
    if (n.conversation_id) onOpenChat(n.conversation_id);
  };

  const readAll = async () => {
    try {
      await markAllNotificationsRead();
      setList((prev) => prev.map((x) => ({ ...x, is_read: true })));
      onChanged();
    } catch (err) {
      onError?.(err.message);
    }
  };

  const unread = list.filter((n) => !n.is_read).length;

  return (
    <main className="wrap notifications-page">
      <div className="page-title-row">
        <div>
          <span className="section-kicker">STAY IN THE LOOP</span>
          <h1>Notifications</h1>
          <p>Messages and updates about your reports.</p>
        </div>
        <button className="text-action" onClick={readAll} disabled={!unread}>
          Mark all as read
        </button>
      </div>
      {loading ? (
        <p className="chat-hint">Loading…</p>
      ) : list.length ? (
        <div className="notification-list">
          {list.map((n) => {
            const look = ICONS[n.type] || ICONS.message;
            return (
              <button
                key={n.id}
                className={`notification-row clickable ${n.is_read ? "" : "unread"}`}
                onClick={() => open(n)}
              >
                <span className={`notification-icon ${look.tone}`}>{look.icon}</span>
                <div>
                  <strong>{n.title}</strong>
                  <p>{n.body}</p>
                  <small>
                    <Clock3 size={12} />
                    {timeAgo(n.created_at)}
                  </small>
                </div>
                {!n.is_read && <span className="unread-dot" />}
              </button>
            );
          })}
        </div>
      ) : (
        <div className="empty-state">
          <BellOff size={38} />
          <h3>No notifications yet</h3>
          <p>When someone messages you about a report, you will see it here.</p>
        </div>
      )}
    </main>
  );
}
