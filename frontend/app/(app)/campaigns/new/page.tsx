"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api, mediaURL, type GenerateResponse, type PromptTemplate } from "@/lib/api";

const ALL_KEYWORD_SOURCES = [
  { id: "google_trends", label: "Google Trends" },
  { id: "etsy", label: "Etsy best-sellers" },
  { id: "amazon", label: "Amazon Merch BSR" },
  { id: "pinterest", label: "Pinterest Trends" },
  { id: "tiktok", label: "TikTok Creative Center" },
];

const ALL_PLATFORMS = [
  { id: "printify", label: "Printify", tagline: "Core — rẻ nhất, mockup miễn phí" },
  { id: "printful", label: "Printful", tagline: "Premium — chất lượng cao" },
  { id: "etsy", label: "Etsy", tagline: "Marketplace — 95M người mua/tháng" },
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

  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [previewPrompt, setPreviewPrompt] = useState<string>("");
  const [previewBusy, setPreviewBusy] = useState(false);

  const [genBusy, setGenBusy] = useState(false);
  const [genResult, setGenResult] = useState<GenerateResponse | null>(null);

  useEffect(() => {
    api.get<PromptTemplate[]>("/v1/prompts/templates").then(setTemplates).catch(() => {});
  }, []);

  function applyTemplate(id: string) {
    setSelectedTemplate(id);
    const t = templates.find((x) => x.id === id);
    if (t) setForm((f) => ({ ...f, style_prompt: t.style }));
  }

  async function refreshPreview() {
    setPreviewBusy(true);
    try {
      const r = await api.post<{ final_prompt: string }>("/v1/prompts/preview", {
        keyword: form.niche.split(",")[0]?.trim() || form.niche,
        niche: form.niche,
        style: form.style_prompt,
      });
      setPreviewPrompt(r.final_prompt);
    } catch (e: any) {
      toast.error(e?.message || "Lỗi");
    } finally {
      setPreviewBusy(false);
    }
  }

  async function generateTest() {
    setGenBusy(true);
    setGenResult(null);
    try {
      const r = await api.post<GenerateResponse>("/v1/prompts/generate", {
        keyword: form.niche.split(",")[0]?.trim() || form.niche,
        niche: form.niche,
        style: form.style_prompt,
        engine: form.ai_engine,
        persist: true,
      });
      setGenResult(r);
      toast.success("Đã sinh design thử");
    } catch (e: any) {
      toast.error(e?.message || "Lỗi");
    } finally {
      setGenBusy(false);
    }
  }

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
          <label className="label">Mẫu prompt (tuỳ chọn)</label>
          <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
            Click 1 mẫu → tự fill phong cách. Bạn có thể sửa lại sau.
          </p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {templates.map((t) => {
              const on = selectedTemplate === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => applyTemplate(t.id)}
                  className={`rounded-lg p-2 text-left text-xs transition ${
                    on
                      ? "bg-brand-500 text-white"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
                  }`}
                >
                  <div className="font-semibold">{t.label}</div>
                  <div className={`mt-0.5 ${on ? "text-white/80" : "text-slate-500 dark:text-slate-400"}`}>
                    {t.description}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs dark:border-slate-700 dark:bg-slate-800/40">
          <div className="mb-1 flex items-center justify-between">
            <span className="font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-1">
              <Eye size={14} /> Prompt cuối gửi cho AI
            </span>
            <div className="flex gap-1">
              <button
                type="button"
                className="btn-outline px-2 py-1 text-xs"
                onClick={refreshPreview}
                disabled={previewBusy}
              >
                {previewBusy ? <Loader2 size={12} className="animate-spin" /> : "Xem trước"}
              </button>
              <button
                type="button"
                className="btn-primary flex items-center gap-1 px-2 py-1 text-xs"
                onClick={generateTest}
                disabled={genBusy}
                title="Sinh thử 1 design để xem kết quả AI thực tế trước khi chạy full campaign"
              >
                {genBusy ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Sparkles size={12} />
                )}
                Generate thử
              </button>
            </div>
          </div>
          <pre className="whitespace-pre-wrap break-words text-slate-600 dark:text-slate-400">
            {previewPrompt || "(bấm 'Xem trước' để render prompt cuối — bao gồm style + keyword + negative prompt)"}
          </pre>
          {genResult?.file_path && (
            <div className="mt-2 flex items-center gap-2 rounded border border-emerald-300 bg-white p-2 dark:border-emerald-700 dark:bg-slate-900">
              <img
                src={mediaURL(genResult.file_path)}
                alt="generated"
                className="h-20 w-20 rounded object-cover"
              />
              <div className="text-xs">
                <div className="font-semibold text-emerald-700 dark:text-emerald-400">
                  ✓ Sinh thành công
                </div>
                <div className="text-slate-500">engine: {genResult.engine} · model: {genResult.model || "default"}</div>
                <div className="text-slate-500">design_id: {genResult.design_id} (xem trong tab Designs)</div>
              </div>
            </div>
          )}
        </div>

        <div>
          <label className="label">Nguồn keyword</label>
          <div className="flex flex-wrap gap-2">
            {ALL_KEYWORD_SOURCES.map((s) => {
              const on = form.keyword_sources.includes(s.id);
              return (
                <button key={s.id} type="button"
                  onClick={() => toggle("keyword_sources", s.id)}
                  className={`rounded-full px-3 py-1 text-sm ${on ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"}`}>
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
          <p className="mb-2 text-xs text-slate-500 dark:text-slate-400">
            💡 Khuyến nghị: chọn <b>Printify</b> + kết nối Etsy shop trong Printify dashboard →
            sản phẩm sẽ tự đồng bộ sang Etsy sau khi bot đăng.
          </p>
          <div className="grid gap-2 sm:grid-cols-3">
            {ALL_PLATFORMS.map((p) => {
              const on = form.target_platforms.includes(p.id);
              return (
                <button key={p.id} type="button"
                  onClick={() => toggle("target_platforms", p.id)}
                  className={`rounded-lg p-3 text-left text-sm transition ${on ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"}`}>
                  <div className="font-semibold">{p.label}</div>
                  <div className={`text-xs ${on ? "text-white/80" : "text-slate-500 dark:text-slate-400"}`}>{p.tagline}</div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label">Chế độ tự động</label>
            <select className="input" value={form.auto_mode} onChange={(e) => setForm({ ...form, auto_mode: e.target.value as "semi" | "full" })}>
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
