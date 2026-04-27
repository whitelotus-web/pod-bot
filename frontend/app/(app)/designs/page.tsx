"use client";
import { useEffect, useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { api, mediaURL, type Design } from "@/lib/api";

export default function DesignsPage() {
  const [items, setItems] = useState<Design[]>([]);
  const [busy, setBusy] = useState<number | null>(null);

  async function load() {
    setItems(await api.get<Design[]>("/v1/designs"));
  }
  useEffect(() => {
    load().catch(() => {});
  }, []);

  async function act(id: number, action: "approve" | "reject") {
    await api.post(`/v1/designs/${id}/${action}`);
    toast.success("OK");
    load();
  }
  async function regenerate(id: number) {
    setBusy(id);
    try {
      await api.post(`/v1/designs/${id}/regenerate`);
      toast.success("Đã sinh lại design");
      load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Lỗi";
      toast.error(msg);
    } finally {
      setBusy(null);
    }
  }
  async function publish(id: number, platform: string) {
    try {
      const r = await api.post<{ ok: boolean; url?: string; error?: string }>(
        `/v1/designs/${id}/publish?platform=${platform}`
      );
      r.ok ? toast.success(`Đăng thành công: ${r.url || ""}`) : toast.error(r.error || "Thất bại");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Lỗi";
      toast.error(msg);
    }
  }

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Designs</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {items.map((d) => (
          <div key={d.id} className="card overflow-hidden">
            <div className="aspect-square bg-slate-100 dark:bg-slate-800">
              <img
                src={mediaURL(d.file_path)}
                alt={d.title}
                className="h-full w-full object-cover"
                key={`${d.id}-${d.file_path}-${d.status}`}
              />
            </div>
            <div className="p-3">
              <div className="truncate font-medium">{d.title}</div>
              <div className="mb-2 text-xs text-slate-500 dark:text-slate-400">
                {d.engine} · {d.status}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  className="btn-outline flex-1 text-xs"
                  onClick={() => regenerate(d.id)}
                  disabled={busy === d.id}
                  title="Sinh lại với cùng prompt"
                >
                  {busy === d.id ? (
                    <Loader2 className="animate-spin" size={12} />
                  ) : (
                    <RefreshCw size={12} />
                  )}
                  <span className="ml-1">Sinh lại</span>
                </button>
                {d.status !== "approved" && (
                  <button className="btn-outline flex-1 text-xs" onClick={() => act(d.id, "approve")}>
                    ✓ Duyệt
                  </button>
                )}
                <select
                  className="input text-xs"
                  onChange={(e) => e.target.value && publish(d.id, e.target.value)}
                  defaultValue=""
                >
                  <option value="">Đăng...</option>
                  <option value="printify">Printify</option>
                  <option value="printful">Printful</option>
                  <option value="etsy">Etsy</option>
                </select>
              </div>
            </div>
          </div>
        ))}
        {!items.length && (
          <div className="card col-span-full p-8 text-center text-slate-500 dark:text-slate-400">
            Chưa có design nào. Chạy một campaign hoặc bấm “Generate thử” trong{" "}
            <a href="/campaigns/new" className="text-brand-600 hover:underline dark:text-brand-400">
              tạo chiến dịch mới
            </a>{" "}
            để AI tạo design.
          </div>
        )}
      </div>
    </div>
  );
}
