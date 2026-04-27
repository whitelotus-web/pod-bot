"use client";
import { useEffect, useState } from "react";
import { Loader2, RefreshCw, Scissors, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, mediaURL, type Design, type SEOContent } from "@/lib/api";

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
  async function removeBg(id: number) {
    setBusy(id);
    try {
      await api.post(`/v1/designs/${id}/remove-bg`);
      toast.success("Đã tách nền");
      load();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Lỗi");
    } finally {
      setBusy(null);
    }
  }
  async function previewSeo(designId: number) {
    const productId = prompt(
      "Sản phẩm nào? (vd: tshirt_unisex, hoodie, mug_11oz)",
      "tshirt_unisex"
    );
    if (!productId) return;
    setBusy(designId);
    try {
      const seo = await api.post<SEOContent>(`/v1/seo/designs/${designId}`, {
        product_id: productId,
      });
      alert(
        `Tiêu đề (${seo.source}):\n${seo.title}\n\nTags: ${seo.tags.join(", ")}\n\n${seo.description}`
      );
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : "Lỗi");
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
              {d.bg_removed_path && (
                <div className="mb-1 inline-flex items-center gap-1 rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                  <Scissors size={10} /> Nền trong suốt
                </div>
              )}
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
                <button
                  className="btn-outline text-xs"
                  onClick={() => removeBg(d.id)}
                  disabled={busy === d.id}
                  title="Tách nền (rembg / alpha threshold)"
                >
                  <Scissors size={12} />
                </button>
                <button
                  className="btn-outline text-xs"
                  onClick={() => previewSeo(d.id)}
                  disabled={busy === d.id}
                  title="Xem SEO sinh ra cho sản phẩm"
                >
                  <Sparkles size={12} />
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
