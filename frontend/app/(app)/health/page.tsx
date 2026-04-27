"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type AccountHealth = {
  id: number;
  platform: string;
  label: string;
  shop_id: string | null;
  is_active: boolean;
  health_status: string;
  health_note: string | null;
  paused_until: string | null;
  age_days: number;
  tier: string;
  daily_cap: number;
  today_publish_count: number;
  today_remaining: number;
  last_publish_at: string | null;
  proxy_configured: boolean;
  now: string;
};

const STATUS_BADGE: Record<string, string> = {
  healthy: "bg-emerald-50 text-emerald-700 dark:bg-emerald-700/10 dark:text-emerald-300",
  warn: "bg-amber-50 text-amber-700 dark:bg-amber-700/10 dark:text-amber-300",
  paused: "bg-slate-100 text-slate-700 dark:bg-slate-700/30 dark:text-slate-300",
  banned: "bg-rose-50 text-rose-700 dark:bg-rose-700/10 dark:text-rose-300",
};

export default function HealthPage() {
  const [data, setData] = useState<AccountHealth[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<AccountHealth[]>("/v1/health/accounts")
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Account Health & Warm-up</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Theo dõi trạng thái từng shop: warm-up cap, proxy, fingerprint. Account mới sẽ
          bị giới hạn 3 listing/ngày trong tuần đầu, tăng dần theo thời gian.
        </p>
      </div>

      {loading && <p className="text-sm text-slate-500">Đang tải…</p>}

      {!loading && data.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700">
          Chưa có platform account nào. Vào trang{" "}
          <a href="/platforms" className="text-brand-600 underline">
            Platform
          </a>{" "}
          để thêm shop.
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {data.map((a) => {
          const pct = a.daily_cap > 0 ? Math.min(100, (a.today_publish_count / a.daily_cap) * 100) : 0;
          return (
            <div
              key={a.id}
              className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-semibold">{a.label || `${a.platform} #${a.id}`}</h3>
                  <p className="text-xs text-slate-500">
                    {a.platform}
                    {a.shop_id ? ` · ${a.shop_id}` : ""}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    STATUS_BADGE[a.health_status] || STATUS_BADGE.healthy
                  }`}
                >
                  {a.health_status}
                </span>
              </div>

              <div className="mt-4">
                <div className="flex justify-between text-xs text-slate-500">
                  <span>
                    Hôm nay: {a.today_publish_count} / {a.daily_cap} listing
                  </span>
                  <span>
                    {a.tier} · {a.age_days}d
                  </span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                  <div className="h-full bg-brand-500" style={{ width: `${pct}%` }} />
                </div>
                <p className="mt-1 text-[11px] text-slate-400">
                  Còn lại {a.today_remaining} listing được phép trong hôm nay.
                </p>
              </div>

              {a.health_note && (
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">💬 {a.health_note}</p>
              )}
              {a.paused_until && (
                <p className="mt-1 text-xs text-rose-600">
                  Paused đến: {new Date(a.paused_until).toLocaleString()}
                </p>
              )}

              <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-500 dark:text-slate-400">
                <div>
                  <div className="font-medium text-slate-600 dark:text-slate-300">Proxy</div>
                  <div>{a.proxy_configured ? "✅ đã cấu hình" : "—"}</div>
                </div>
                <div>
                  <div className="font-medium text-slate-600 dark:text-slate-300">Last publish</div>
                  <div>{a.last_publish_at ? new Date(a.last_publish_at).toLocaleString() : "—"}</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
