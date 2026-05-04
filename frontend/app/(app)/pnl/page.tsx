"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Bucket = {
  label: string;
  revenue_usd: number;
  cost_usd: number;
  profit_usd: number;
  orders: number;
  products: number;
};

type Winner = {
  id: number;
  title: string;
  url: string | null;
  product_type: string;
  revenue_usd: number;
  cost_usd: number;
  profit_usd: number;
  orders: number;
  views?: number;
};

type Summary = {
  days: number;
  since: string;
  until: string;
  revenue_usd: number;
  cost_usd: number;
  profit_usd: number;
  margin_pct: number;
  orders: number;
  products: number;
};

type DashboardBundle = {
  summary: Summary;
  by_day: Bucket[];
  by_campaign: Bucket[];
  by_product_type: Bucket[];
  top_winners: Winner[];
  top_losers: Winner[];
};

const RANGES = [
  { label: "7 ngày", value: 7 },
  { label: "30 ngày", value: 30 },
  { label: "90 ngày", value: 90 },
  { label: "180 ngày", value: 180 },
];

function fmt(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export default function PnlPage() {
  const [data, setData] = useState<DashboardBundle | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .get<DashboardBundle>(`/v1/pnl/dashboard?days=${days}`)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [days]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold">P&amp;L Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Doanh thu (từ webhook orders) − chi phí (AI sinh + upscale + Printify base) =
            lợi nhuận, theo ngày / chiến dịch / loại sản phẩm.
          </p>
        </div>
        <div className="flex gap-2">
          {RANGES.map((r) => (
            <button
              key={r.value}
              onClick={() => setDays(r.value)}
              className={
                "rounded-lg border px-3 py-1.5 text-sm " +
                (days === r.value
                  ? "border-brand-500 bg-brand-50 text-brand-700 dark:bg-brand-700/20 dark:text-brand-300"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300")
              }
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="text-sm text-slate-500">Đang tải…</p>}

      {!loading && data && (
        <>
          {/* KPI hero */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <Kpi label="Doanh thu" value={fmt(data.summary.revenue_usd)} sub={`${data.summary.orders} đơn`} />
            <Kpi label="Chi phí" value={fmt(data.summary.cost_usd)} sub={`${data.summary.products} listing`} />
            <Kpi
              label="Lợi nhuận"
              value={fmt(data.summary.profit_usd)}
              tone={data.summary.profit_usd >= 0 ? "good" : "bad"}
              sub={`${data.summary.since} → ${data.summary.until}`}
            />
            <Kpi
              label="Biên LN"
              value={`${data.summary.margin_pct.toFixed(1)}%`}
              tone={data.summary.margin_pct >= 30 ? "good" : data.summary.margin_pct >= 0 ? "warn" : "bad"}
            />
          </div>

          <Section title="Theo ngày">
            <BarTable rows={data.by_day} reverse />
          </Section>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <Section title="Theo chiến dịch">
              <BarTable rows={data.by_campaign} />
            </Section>
            <Section title="Theo loại sản phẩm">
              <BarTable rows={data.by_product_type} />
            </Section>
          </div>

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <Section title="Top 10 winner (lợi nhuận cao nhất)">
              <WinnerTable rows={data.top_winners} />
            </Section>
            <Section title="Top 10 loser (cân nhắc cut-loss)">
              <WinnerTable rows={data.top_losers} />
            </Section>
          </div>
        </>
      )}
    </div>
  );
}

function Kpi({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "good" | "bad" | "warn";
}) {
  const toneCls =
    tone === "good"
      ? "text-emerald-600 dark:text-emerald-400"
      : tone === "bad"
        ? "text-rose-600 dark:text-rose-400"
        : tone === "warn"
          ? "text-amber-600 dark:text-amber-400"
          : "text-slate-900 dark:text-slate-100";
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </div>
      <div className={"mt-1 text-2xl font-bold " + toneCls}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{sub}</div>}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
      <h2 className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-100">{title}</h2>
      {children}
    </div>
  );
}

function BarTable({ rows, reverse }: { rows: Bucket[]; reverse?: boolean }) {
  if (!rows.length) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">Chưa có dữ liệu.</p>;
  }
  const ordered = reverse ? [...rows].reverse() : rows;
  const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.profit_usd)));
  return (
    <div className="space-y-2">
      {ordered.map((r) => (
        <div key={r.label} className="flex items-center gap-3 text-sm">
          <div className="w-32 truncate text-slate-600 dark:text-slate-300">{r.label}</div>
          <div className="flex-1 overflow-hidden rounded-md bg-slate-100 dark:bg-slate-800">
            <div
              className={
                "h-5 " + (r.profit_usd >= 0 ? "bg-emerald-400/60" : "bg-rose-400/60")
              }
              style={{ width: `${(Math.abs(r.profit_usd) / maxAbs) * 100}%` }}
            />
          </div>
          <div className="w-24 text-right tabular-nums text-slate-700 dark:text-slate-200">
            {fmt(r.profit_usd)}
          </div>
          <div className="w-12 text-right text-xs text-slate-500 dark:text-slate-400">
            {r.orders}đ
          </div>
        </div>
      ))}
    </div>
  );
}

function WinnerTable({ rows }: { rows: Winner[] }) {
  if (!rows.length) {
    return <p className="text-sm text-slate-500 dark:text-slate-400">Chưa có dữ liệu.</p>;
  }
  return (
    <table className="w-full text-sm">
      <thead className="text-xs text-slate-500 dark:text-slate-400">
        <tr>
          <th className="pb-2 text-left font-medium">Sản phẩm</th>
          <th className="pb-2 text-right font-medium">Doanh thu</th>
          <th className="pb-2 text-right font-medium">Chi phí</th>
          <th className="pb-2 text-right font-medium">Lợi nhuận</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.id} className="border-t border-slate-100 dark:border-slate-800">
            <td className="py-2 pr-2">
              {r.url ? (
                <a href={r.url} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">
                  {r.title}
                </a>
              ) : (
                <span>{r.title}</span>
              )}
              <div className="text-xs text-slate-400">{r.product_type} · {r.orders} đơn</div>
            </td>
            <td className="py-2 text-right tabular-nums">{fmt(r.revenue_usd)}</td>
            <td className="py-2 text-right tabular-nums text-slate-500">{fmt(r.cost_usd)}</td>
            <td
              className={
                "py-2 text-right tabular-nums " +
                (r.profit_usd >= 0 ? "text-emerald-600" : "text-rose-600")
              }
            >
              {fmt(r.profit_usd)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
