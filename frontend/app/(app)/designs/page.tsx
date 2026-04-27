"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, mediaURL, type Design } from "@/lib/api";

export default function DesignsPage() {
  const [items, setItems] = useState<Design[]>([]);
  async function load() { setItems(await api.get<Design[]>("/v1/designs")); }
  useEffect(() => { load().catch(() => {}); }, []);

  async function act(id: number, action: "approve" | "reject") {
    await api.post(`/v1/designs/${id}/${action}`);
    toast.success("OK"); load();
  }
  async function publish(id: number, platform: string) {
    try {
      const r = await api.post<any>(`/v1/designs/${id}/publish?platform=${platform}`);
      r.ok ? toast.success(`Đăng thành công: ${r.url || ""}`) : toast.error(r.error || "Thất bại");
    } catch (e: any) { toast.error(e?.message || "Lỗi"); }
  }

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Designs</h1>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {items.map((d) => (
          <div key={d.id} className="card overflow-hidden">
            <div className="aspect-square bg-slate-100">
              <img src={mediaURL(d.file_path)} alt={d.title} className="h-full w-full object-cover" />
            </div>
            <div className="p-3">
              <div className="truncate font-medium">{d.title}</div>
              <div className="mb-2 text-xs text-slate-500">{d.engine} · {d.status}</div>
              <div className="flex gap-2">
                {d.status !== "approved" && (
                  <button className="btn-outline flex-1" onClick={() => act(d.id, "approve")}>✓ Duyệt</button>
                )}
                <select className="input text-xs" onChange={(e) => e.target.value && publish(d.id, e.target.value)} defaultValue="">
                  <option value="">Đăng...</option>
                  <option value="printify">Printify</option>
                  <option value="printful">Printful</option>
                  <option value="etsy">Etsy</option>
                </select>
              </div>
            </div>
          </div>
        ))}
        {!items.length && <div className="card col-span-full p-8 text-center text-slate-500">Chưa có design nào. Chạy một campaign để AI tạo design.</div>}
      </div>
    </div>
  );
}
