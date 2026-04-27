"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash2, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { api, type AIKey, type AIKeyTestResponse } from "@/lib/api";

const ENGINES = [
  {
    id: "gemini",
    label: "Google Gemini",
    tagline: "Image-gen miễn phí mỗi ngày, recommended.",
    setup_url: "https://aistudio.google.com/apikey",
  },
  {
    id: "openai",
    label: "OpenAI DALL-E / GPT Image",
    tagline: "Chất lượng cao, trả phí.",
    setup_url: "https://platform.openai.com/api-keys",
  },
  {
    id: "replicate",
    label: "Replicate (SDXL / Flux)",
    tagline: "Hosted open-source models, pay per second.",
    setup_url: "https://replicate.com/account/api-tokens",
  },
] as const;

type EngineId = (typeof ENGINES)[number]["id"];

export default function AISettingsPage() {
  const [keys, setKeys] = useState<AIKey[]>([]);
  const [busy, setBusy] = useState(false);
  const [drafts, setDrafts] = useState<Record<EngineId, string>>({
    gemini: "",
    openai: "",
    replicate: "",
  });
  const [testing, setTesting] = useState<EngineId | null>(null);

  async function load() {
    try {
      setKeys(await api.get<AIKey[]>("/v1/ai-keys"));
    } catch (e: any) {
      toast.error(e?.message || "Không tải được AI keys");
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function save(engine: EngineId) {
    const v = drafts[engine].trim();
    if (!v) return toast.error("Hãy paste API key");
    setBusy(true);
    try {
      await api.post<AIKey>("/v1/ai-keys", { engine, api_key: v, label: ENGINES.find(e => e.id === engine)?.label || engine });
      setDrafts((d) => ({ ...d, [engine]: "" }));
      toast.success("Đã lưu key");
      load();
    } catch (e: any) {
      toast.error(e?.message || "Lỗi");
    } finally {
      setBusy(false);
    }
  }

  async function test(engine: EngineId, apiKey?: string) {
    setTesting(engine);
    try {
      const r = await api.post<AIKeyTestResponse>("/v1/ai-keys/test", {
        engine,
        api_key: apiKey ?? null,
      });
      r.ok
        ? toast.success(`${engine} OK`)
        : toast.error(`${engine} thất bại: ${r.message}`);
    } catch (e: any) {
      toast.error(e?.message || "Lỗi");
    } finally {
      setTesting(null);
    }
  }

  async function remove(id: number) {
    if (!confirm("Xoá key này?")) return;
    try {
      await api.del(`/v1/ai-keys/${id}`);
      toast.success("Đã xoá");
      load();
    } catch (e: any) {
      toast.error(e?.message || "Lỗi");
    }
  }

  const keysByEngine = keys.reduce<Record<string, AIKey[]>>((acc, k) => {
    (acc[k.engine] ||= []).push(k);
    return acc;
  }, {});

  return (
    <div className="max-w-4xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold">AI Keys</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Paste API key cho từng AI engine. Key được mã hoá AES trước khi lưu DB —
          không cần sửa <code>.env</code> hay restart Docker.
        </p>
      </div>

      <div className="grid gap-4">
        {ENGINES.map((eng) => {
          const saved = keysByEngine[eng.id] || [];
          return (
            <div key={eng.id} className="card p-5">
              <div className="mb-2 flex items-center justify-between">
                <div>
                  <div className="font-semibold">{eng.label}</div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    {eng.tagline}{" "}
                    <a
                      href={eng.setup_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-brand-600 hover:underline dark:text-brand-400"
                    >
                      Lấy API key ↗
                    </a>
                  </p>
                </div>
              </div>

              <div className="mb-3 flex gap-2">
                <input
                  type="password"
                  className="input"
                  placeholder={`Paste ${eng.label} API key...`}
                  value={drafts[eng.id]}
                  onChange={(e) =>
                    setDrafts((d) => ({ ...d, [eng.id]: e.target.value }))
                  }
                />
                <button
                  className="btn-outline whitespace-nowrap"
                  disabled={!drafts[eng.id] || testing === eng.id}
                  onClick={() => test(eng.id, drafts[eng.id])}
                >
                  {testing === eng.id ? <Loader2 className="animate-spin" size={14} /> : "Test"}
                </button>
                <button
                  className="btn-primary whitespace-nowrap"
                  disabled={!drafts[eng.id] || busy}
                  onClick={() => save(eng.id)}
                >
                  Lưu
                </button>
              </div>

              {saved.length === 0 ? (
                <div className="rounded border border-dashed border-slate-300 p-3 text-xs text-slate-500 dark:border-slate-600">
                  Chưa có key cho {eng.label}. Bot sẽ fallback dùng env <code>{eng.id.toUpperCase()}_API_KEY</code> nếu có.
                </div>
              ) : (
                <ul className="space-y-2">
                  {saved.map((k) => (
                    <li
                      key={k.id}
                      className="flex items-center justify-between rounded border border-slate-200 px-3 py-2 text-sm dark:border-slate-700"
                    >
                      <div className="flex items-center gap-2">
                        <span className="pill">{k.engine}</span>
                        <code className="text-xs text-slate-700 dark:text-slate-300">{k.masked_key}</code>
                        <span className="text-xs text-slate-500">{k.label}</span>
                      </div>
                      <div className="flex gap-2">
                        <button
                          className="btn-outline px-2 py-1 text-xs"
                          disabled={testing === k.engine}
                          onClick={() => test(k.engine)}
                        >
                          {testing === k.engine ? (
                            <Loader2 className="animate-spin" size={14} />
                          ) : (
                            <CheckCircle2 size={14} />
                          )}
                        </button>
                        <button
                          className="btn-outline px-2 py-1 text-xs"
                          onClick={() => remove(k.id)}
                          aria-label="Xoá"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>

      <div className="card border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
        <div className="mb-1 flex items-center gap-2 font-semibold">
          <XCircle size={16} /> Bảo mật
        </div>
        Key được mã hoá bằng <code>cryptography.Fernet</code> với app{" "}
        <code>SECRET_KEY</code>. Nếu đổi <code>SECRET_KEY</code> trong{" "}
        <code>.env</code>, các key cũ sẽ không giải mã được — phải nhập lại.
      </div>
    </div>
  );
}
