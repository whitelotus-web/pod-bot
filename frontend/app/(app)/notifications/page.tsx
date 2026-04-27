"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Notification = {
  id: number;
  kind: string;
  severity: "info" | "warn" | "critical";
  title: string;
  body: string | null;
  payload: Record<string, unknown> | null;
  read: boolean;
  created_at: string;
};

const SEV_BADGE: Record<string, string> = {
  info: "bg-sky-50 text-sky-700 dark:bg-sky-700/10 dark:text-sky-300",
  warn: "bg-amber-50 text-amber-700 dark:bg-amber-700/10 dark:text-amber-300",
  critical: "bg-rose-50 text-rose-700 dark:bg-rose-700/10 dark:text-rose-300",
};

export default function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "unread">("all");

  const load = () => {
    setLoading(true);
    const path = filter === "unread" ? "/v1/notifications?unread_only=true" : "/v1/notifications";
    api
      .get<Notification[]>(path)
      .then(setItems)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const markRead = async (id: number) => {
    await api.post(`/v1/notifications/${id}/read`);
    load();
  };

  const markAll = async () => {
    await api.post("/v1/notifications/read-all");
    load();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Thông báo</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Sự kiện hệ thống: trademark hit, hết quota, account paused, sale đầu tiên…
          </p>
        </div>
        <div className="flex gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as "all" | "unread")}
            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
          >
            <option value="all">Tất cả</option>
            <option value="unread">Chưa đọc</option>
          </select>
          <button
            onClick={markAll}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            Đánh dấu đã đọc tất cả
          </button>
        </div>
      </div>

      {loading && <p className="text-sm text-slate-500">Đang tải…</p>}

      {!loading && items.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700">
          Chưa có thông báo nào.
        </div>
      )}

      <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white dark:divide-slate-700 dark:border-slate-700 dark:bg-slate-900">
        {items.map((n) => (
          <li
            key={n.id}
            className={`flex items-start justify-between gap-4 p-4 ${
              !n.read ? "bg-slate-50/50 dark:bg-slate-800/30" : ""
            }`}
          >
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    SEV_BADGE[n.severity] ?? SEV_BADGE.info
                  }`}
                >
                  {n.severity}
                </span>
                <span className="text-xs text-slate-400">{n.kind}</span>
                {!n.read && (
                  <span className="rounded-full bg-brand-500 px-1.5 py-0.5 text-[9px] font-bold text-white">
                    NEW
                  </span>
                )}
              </div>
              <h3 className="mt-1 font-semibold text-slate-900 dark:text-slate-100">
                {n.title}
              </h3>
              {n.body && (
                <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{n.body}</p>
              )}
              <p className="mt-1 text-[10px] text-slate-400">
                {new Date(n.created_at).toLocaleString()}
              </p>
            </div>
            {!n.read && (
              <button
                onClick={() => markRead(n.id)}
                className="text-xs text-brand-600 hover:underline"
              >
                Đã đọc
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
