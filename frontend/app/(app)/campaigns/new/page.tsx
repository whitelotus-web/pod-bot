"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { api } from "@/lib/api";

const ALL_KEYWORD_SOURCES = [
  { id: "google_trends", label: "Google Trends" },
  { id: "etsy", label: "Etsy best-sellers" },
  { id: "amazon", label: "Amazon Merch BSR" },
  { id: "pinterest", label: "Pinterest Trends" },
  { id: "tiktok", label: "TikTok Creative Center" },
];

const ALL_PLATFORMS = [
  { id: "printify", label: "Printify", ok: true },
  { id: "printful", label: "Printful", ok: true },
  { id: "etsy", label: "Etsy", ok: true },
  { id: "redbubble", label: "Redbubble (Selenium)", ok: false },
  { id: "teespring", label: "Teespring / Spring (Selenium)", ok: false },
  { id: "merch_amazon", label: "Merch by Amazon (Selenium)", ok: false },
];

export default function NewCampaignPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    name: "",
    niche: "cat lovers",
    style_prompt: "vintage retro cartoon, bold outline, 4 color palette",
    keyword_sources: ["google_trends", "etsy"] as string[],
    ai_engine: "gemini",
    designs_per_keyword: 2,
    product_types: ["tshirt"] as string[],
    base_price_usd: 19.99,
    auto_mode: "semi" as "semi" | "full",
    target_platforms: ["printify"] as string[],
    schedule_cron: "",
  });

  function toggle(field: "keyword_sources" | "target_platforms", id: string) {
    setForm((f) => ({
      ...f,
      [field]: f[field].includes(id) ? f[field].filter((x) => x !== id) : [...f[field], id],
    }));
  }

  async function submit() {
    try {
      await api.post("/v1/campaigns", form);
      toast.success("Đã tạo chiến dịch");
      router.push("/campaigns");
    } catch (e: any) {
      toast.error(e?.message || "Lỗi");
    }
  }

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold">Chiến dịch mới</h1>

      <div className="card space-y-4 p-5">
        <div>
          <label className="label">Tên chiến dịch</label>
          <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Niche / từ khoá gốc</label>
            <input className="input" value={form.niche} onChange={(e) => setForm({ ...form, niche: e.target.value })} />
          </div>
          <div>
            <label className="label">Phong cách design (prompt style)</label>
            <input className="input" value={form.style_prompt} onChange={(e) => setForm({ ...form, style_prompt: e.target.value })} />
          </div>
        </div>

        <div>
          <label className="label">Nguồn keyword</label>
          <div className="flex flex-wrap gap-2">
            {ALL_KEYWORD_SOURCES.map((s) => {
              const on = form.keyword_sources.includes(s.id);
              return (
                <button key={s.id} type="button"
                  onClick={() => toggle("keyword_sources", s.id)}
                  className={`rounded-full px-3 py-1 text-sm ${on ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-700"}`}>
                  {s.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label className="label">AI engine</label>
            <select className="input" value={form.ai_engine} onChange={(e) => setForm({ ...form, ai_engine: e.target.value })}>
              <option value="gemini">Gemini</option>
              <option value="openai">OpenAI DALL-E</option>
              <option value="replicate">Replicate (SDXL)</option>
            </select>
          </div>
          <div>
            <label className="label">Số design / keyword</label>
            <input type="number" min={1} max={5} className="input"
              value={form.designs_per_keyword}
              onChange={(e) => setForm({ ...form, designs_per_keyword: Number(e.target.value) })} />
          </div>
          <div>
            <label className="label">Giá (USD)</label>
            <input type="number" step="0.01" className="input"
              value={form.base_price_usd}
              onChange={(e) => setForm({ ...form, base_price_usd: Number(e.target.value) })} />
          </div>
        </div>

        <div>
          <label className="label">Platform đăng bán</label>
          <div className="flex flex-wrap gap-2">
            {ALL_PLATFORMS.map((p) => {
              const on = form.target_platforms.includes(p.id);
              return (
                <button key={p.id} type="button"
                  title={p.ok ? "Có API chính thức" : "Chưa có public API — cần Selenium"}
                  onClick={() => toggle("target_platforms", p.id)}
                  className={`rounded-full px-3 py-1 text-sm ${on ? "bg-brand-500 text-white" : p.ok ? "bg-slate-100 text-slate-700" : "bg-amber-50 text-amber-700"}`}>
                  {p.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Chế độ tự động</label>
            <select className="input" value={form.auto_mode} onChange={(e) => setForm({ ...form, auto_mode: e.target.value as any })}>
              <option value="semi">Semi — chờ duyệt</option>
              <option value="full">Full — tự đăng</option>
            </select>
          </div>
          <div>
            <label className="label">Lịch chạy (cron, để trống nếu chạy thủ công)</label>
            <input className="input" placeholder="0 3 * * *  (3 giờ sáng mỗi ngày)"
              value={form.schedule_cron}
              onChange={(e) => setForm({ ...form, schedule_cron: e.target.value })} />
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <button className="btn-outline" onClick={() => router.back()}>Huỷ</button>
          <button className="btn-primary" onClick={submit}>Tạo chiến dịch</button>
        </div>
      </div>
    </div>
  );
}
