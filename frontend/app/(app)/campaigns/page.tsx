"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { api, type Campaign } from "@/lib/api";

export default function CampaignsPage() {
  const [items, setItems] = useState<Campaign[]>([]);

  async function load() {
    setItems(await api.get<Campaign[]>("/v1/campaigns"));
  }
  useEffect(() => {
    load().catch(() => {});
  }, []);

  async function run(id: number, full = false) {
    try {
      await api.post(`/v1/campaigns/${id}/run?force_auto=${full}`);
      toast.success(full ? "Đã xếp hàng chạy full-auto" : "Đã xếp hàng chạy (semi)");
    } catch (e: any) {
      toast.error(e?.message || "Lỗi");
    }
  }
  async function del(id: number) {
    if (!confirm("Xoá campaign?")) return;
    await api.del(`/v1/campaigns/${id}`);
    await load();
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Chiến dịch</h1>
        <Link href="/campaigns/new" className="btn-primary">+ Tạo mới</Link>
      </div>
      <div className="grid gap-3">
        {items.map((c) => (
          <div key={c.id} className="card flex items-center justify-between p-4">
            <div>
              <div className="text-lg font-semibold">{c.name}</div>
              <div className="text-sm text-slate-500">
                Niche: <b>{c.niche || "-"}</b> · AI: <b>{c.ai_engine}</b> · Chế độ: <b>{c.auto_mode}</b> ·
                Nguồn: {c.keyword_sources.join(", ") || "-"} · Platform: {c.target_platforms.join(", ") || "-"}
              </div>
              {c.last_run_at && (
                <div className="mt-1 text-xs text-slate-400">
                  Lần chạy gần nhất: {new Date(c.last_run_at).toLocaleString("vi-VN")}
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <button className="btn-outline" onClick={() => run(c.id, false)}>▶ Semi</button>
              <button className="btn-primary" onClick={() => run(c.id, true)}>🚀 Full auto</button>
              <button className="btn-ghost text-red-600" onClick={() => del(c.id)}>Xoá</button>
            </div>
          </div>
        ))}
        {!items.length && (
          <div className="card p-8 text-center text-slate-500">
            Chưa có chiến dịch nào.{" "}
            <Link href="/campaigns/new" className="text-brand-600 underline">Tạo đầu tiên →</Link>
          </div>
        )}
      </div>
    </div>
  );
}
