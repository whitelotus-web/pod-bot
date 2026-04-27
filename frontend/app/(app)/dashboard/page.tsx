"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Campaign, type Product, type RunLog } from "@/lib/api";
import { Onboarding } from "@/components/Onboarding";

export default function DashboardPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [runs, setRuns] = useState<RunLog[]>([]);

  useEffect(() => {
    (async () => {
      try {
        setCampaigns(await api.get<Campaign[]>("/v1/campaigns"));
        setProducts(await api.get<Product[]>("/v1/products"));
        setRuns(await api.get<RunLog[]>("/v1/runs?limit=10"));
      } catch (e) { /* noop */ }
    })();
  }, []);

  const published = products.filter((p) => p.status === "published").length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Link href="/campaigns/new" className="btn-primary">+ Chiến dịch mới</Link>
      </div>
      <Onboarding />
      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Chiến dịch" value={campaigns.length} />
        <Stat label="Đang chạy" value={campaigns.filter(c => c.is_active).length} />
        <Stat label="Sản phẩm đã đăng" value={published} />
        <Stat label="Pipeline runs (10 gần nhất)" value={runs.length} />
      </div>

      <section className="card p-5">
        <h2 className="mb-3 text-lg font-semibold">Runs gần đây</h2>
        <div className="space-y-2 text-sm">
          {runs.map((r) => (
            <div key={r.id} className="flex items-center justify-between rounded border border-slate-100 p-2">
              <div>
                <span className="pill mr-2">{r.stage}</span>
                <span className="text-slate-700">campaign #{r.campaign_id}</span>
              </div>
              <span className={
                r.status === "success" ? "text-green-600" :
                r.status === "failed" ? "text-red-600" : "text-slate-500"
              }>
                {r.status}
              </span>
            </div>
          ))}
          {!runs.length && <div className="text-slate-500">Chưa có run nào.</div>}
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="card p-4">
      <div className="text-xs uppercase text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-bold">{value}</div>
    </div>
  );
}
