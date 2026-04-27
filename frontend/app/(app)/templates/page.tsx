"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type ArtTemplate = {
  id: string;
  name: string;
  family: string;
  preview: string;
  reference: string;
  era: string;
  palette_hint: string;
};

type TemplatesResp = { families: string[]; templates: ArtTemplate[] };

const FAMILY_LABELS: Record<string, string> = {
  cinematic: "Cinematic",
  vintage: "Vintage",
  cultural: "Cultural / Architecture",
  botanical: "Botanical / Scientific",
  brutalist: "Brutalist / Typographic",
};

export default function TemplatesPage() {
  const [data, setData] = useState<TemplatesResp | null>(null);
  const [family, setFamily] = useState<string>("");
  const [niche, setNiche] = useState("cat lovers");
  const [keyword, setKeyword] = useState("vintage cat mom");
  const [activeId, setActiveId] = useState<string | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<TemplatesResp>("/v1/templates").then(setData).catch(console.error);
  }, []);

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.templates.filter((t) => !family || t.family === family);
  }, [data, family]);

  const renderPreview = async (id: string) => {
    setActiveId(id);
    setLoading(true);
    try {
      const res = await api.post<{ rendered: string }>("/v1/templates/preview", {
        template_id: id,
        niche,
        keyword,
      });
      setPreview(res.rendered);
    } catch (e) {
      setPreview(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Prompt Templates</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          20 templates "xưởng thiết kế" theo trường phái nghệ thuật. Mỗi template có
          reference artist + era + bảng màu — design ra sẽ có gu rõ rệt thay vì AI generic.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <label className="text-xs font-medium text-slate-500">Niche</label>
            <input
              value={niche}
              onChange={(e) => setNiche(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500">Keyword</label>
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500">Family</label>
            <select
              value={family}
              onChange={(e) => setFamily(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
            >
              <option value="">Tất cả</option>
              {data?.families.map((f) => (
                <option key={f} value={f}>
                  {FAMILY_LABELS[f] ?? f}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {filtered.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => renderPreview(t.id)}
            className={`rounded-xl border p-4 text-left transition ${
              activeId === t.id
                ? "border-brand-500 ring-2 ring-brand-500/40"
                : "border-slate-200 hover:border-brand-400 dark:border-slate-700"
            } bg-white dark:bg-slate-900`}
          >
            <div className="flex items-center justify-between">
              <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700 dark:bg-brand-700/20 dark:text-brand-300">
                {FAMILY_LABELS[t.family] ?? t.family}
              </span>
              <span className="text-[10px] text-slate-400">{t.era}</span>
            </div>
            <h3 className="mt-2 text-base font-semibold text-slate-900 dark:text-slate-100">
              {t.name}
            </h3>
            <p className="mt-1 line-clamp-3 text-xs text-slate-500 dark:text-slate-400">
              {t.preview}
            </p>
            <div className="mt-2 text-[11px] text-slate-400">
              Ref: {t.reference}
              <br />
              Palette: {t.palette_hint}
            </div>
          </button>
        ))}
      </div>

      {activeId && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
          <h3 className="font-semibold">Rendered prompt</h3>
          {loading ? (
            <p className="mt-2 text-sm text-slate-500">Đang render…</p>
          ) : (
            <pre className="mt-2 whitespace-pre-wrap break-words text-xs text-slate-700 dark:text-slate-200">
              {preview}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
