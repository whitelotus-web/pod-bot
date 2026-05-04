"use client";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Trash2, ChevronUp, ChevronDown, Loader2, ShieldCheck, Pencil } from "lucide-react";
import { api, type AIKey, type AIKeyTestResponse, type AIRole, type AIRoleMeta } from "@/lib/api";

const ENGINE_META: Record<string, { label: string; setup: string; tagline: string }> = {
  gemini: {
    label: "Google Gemini",
    setup: "https://aistudio.google.com/apikey",
    tagline: "Free tier hào phóng, recommended cho cả image & text.",
  },
  openai: {
    label: "OpenAI",
    setup: "https://platform.openai.com/api-keys",
    tagline: "GPT-4o-mini text + DALL-E image, trả phí.",
  },
  replicate: {
    label: "Replicate (SDXL / Flux)",
    setup: "https://replicate.com/account/api-tokens",
    tagline: "Hosted open-source models, pay-per-second.",
  },
};

export default function AISettingsPage() {
  const [keys, setKeys] = useState<AIKey[]>([]);
  const [roles, setRoles] = useState<AIRoleMeta[]>([]);
  const [activeRole, setActiveRole] = useState<AIRole>("image_generation");
  const [draftEngine, setDraftEngine] = useState<string>("gemini");
  const [draftKey, setDraftKey] = useState("");
  const [draftLabel, setDraftLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [testingId, setTestingId] = useState<number | null>(null);

  async function loadAll() {
    try {
      const [k, r] = await Promise.all([
        api.get<AIKey[]>("/v1/ai-keys"),
        api.get<{ roles: AIRoleMeta[] }>("/v1/ai-keys/roles"),
      ]);
      setKeys(k);
      setRoles(r.roles);
    } catch (e: unknown) {
      toast.error((e as Error)?.message || "Không tải được AI keys");
    }
  }
  useEffect(() => {
    loadAll();
  }, []);

  const currentRoleMeta = roles.find((r) => r.id === activeRole);
  const allowedEngines = currentRoleMeta?.engines ?? Object.keys(ENGINE_META);

  // Reset engine select if user switches to a role where current engine isn't allowed
  useEffect(() => {
    if (allowedEngines.length && !allowedEngines.includes(draftEngine)) {
      setDraftEngine(allowedEngines[0]);
    }
  }, [activeRole, allowedEngines, draftEngine]);

  const keysForRole = useMemo(
    () =>
      keys
        .filter((k) => k.role === activeRole)
        .sort((a, b) => a.priority - b.priority || b.id - a.id),
    [keys, activeRole]
  );

  async function save() {
    const v = draftKey.trim();
    if (!v) return toast.error("Hãy paste API key");
    setBusy(true);
    try {
      const nextPriority = keysForRole.length + 1;
      await api.post<AIKey>("/v1/ai-keys", {
        engine: draftEngine,
        role: activeRole,
        api_key: v,
        label: draftLabel || `${ENGINE_META[draftEngine]?.label} (#${nextPriority})`,
        priority: nextPriority,
      });
      setDraftKey("");
      setDraftLabel("");
      toast.success("Đã lưu key");
      loadAll();
    } catch (e: unknown) {
      toast.error((e as Error)?.message || "Lỗi lưu key");
    } finally {
      setBusy(false);
    }
  }

  async function test(key: AIKey) {
    setTestingId(key.id);
    try {
      const r = await api.post<AIKeyTestResponse>("/v1/ai-keys/test", {
        engine: key.engine,
        role: key.role,
      });
      if (r.ok) toast.success(`${key.engine}: ${r.message}`);
      else toast.error(`${key.engine}: ${r.message}`);
    } catch (e: unknown) {
      toast.error((e as Error)?.message || "Lỗi");
    } finally {
      setTestingId(null);
    }
  }

  async function remove(id: number) {
    if (!confirm("Xoá key này? Pipeline sẽ tự rotate sang key kế tiếp.")) return;
    try {
      await api.del(`/v1/ai-keys/${id}`);
      toast.success("Đã xoá");
      loadAll();
    } catch (e: unknown) {
      toast.error((e as Error)?.message || "Lỗi");
    }
  }

  async function toggleActive(k: AIKey) {
    try {
      await api.patch<AIKey>(`/v1/ai-keys/${k.id}`, { is_active: !k.is_active });
      loadAll();
    } catch (e: unknown) {
      toast.error((e as Error)?.message || "Lỗi");
    }
  }

  async function move(k: AIKey, dir: -1 | 1) {
    const newPriority = Math.max(1, k.priority + dir);
    try {
      await api.patch<AIKey>(`/v1/ai-keys/${k.id}`, { priority: newPriority });
      loadAll();
    } catch (e: unknown) {
      toast.error((e as Error)?.message || "Lỗi");
    }
  }

  async function rename(k: AIKey) {
    const next = prompt("Tên gợi nhớ cho key:", k.label);
    if (next == null) return;
    try {
      await api.patch<AIKey>(`/v1/ai-keys/${k.id}`, { label: next });
      loadAll();
    } catch (e: unknown) {
      toast.error((e as Error)?.message || "Lỗi");
    }
  }

  return (
    <div className="max-w-4xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold">AI Keys & Roles</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Mỗi role có thể có nhiều key (cùng engine hoặc khác). Pipeline tự rotate khi gặp lỗi
          quota / 429. Key được mã hoá Fernet trước khi lưu DB.
        </p>
      </div>

      <div className="card p-1">
        <nav className="flex flex-wrap gap-1 p-1">
          {roles.map((r) => (
            <button
              key={r.id}
              onClick={() => setActiveRole(r.id)}
              className={`flex-1 rounded-lg px-4 py-2 text-sm font-medium transition ${
                r.id === activeRole
                  ? "bg-brand-500 text-white shadow-sm"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              }`}
            >
              {r.label}
            </button>
          ))}
        </nav>
      </div>

      {currentRoleMeta && (
        <div className="card p-5">
          <div className="mb-4 flex items-start gap-3">
            <ShieldCheck size={20} className="mt-0.5 text-brand-500" />
            <div>
              <div className="font-semibold">{currentRoleMeta.label}</div>
              <div className="text-sm text-slate-500 dark:text-slate-400">
                {currentRoleMeta.description} — engine cho phép:{" "}
                <code>{currentRoleMeta.engines.join(", ")}</code>
              </div>
            </div>
          </div>

          <div className="grid gap-2 md:grid-cols-[160px_1fr_180px_auto]">
            <select
              className="input"
              value={draftEngine}
              onChange={(e) => setDraftEngine(e.target.value)}
            >
              {allowedEngines.map((eng) => (
                <option key={eng} value={eng}>
                  {ENGINE_META[eng]?.label || eng}
                </option>
              ))}
            </select>
            <input
              type="password"
              className="input"
              placeholder={`Paste ${ENGINE_META[draftEngine]?.label} API key...`}
              value={draftKey}
              onChange={(e) => setDraftKey(e.target.value)}
            />
            <input
              className="input"
              placeholder="Tên gợi nhớ (optional)"
              value={draftLabel}
              onChange={(e) => setDraftLabel(e.target.value)}
            />
            <button
              className="btn-primary whitespace-nowrap"
              disabled={!draftKey.trim() || busy}
              onClick={save}
            >
              + Thêm
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            {ENGINE_META[draftEngine]?.tagline}{" "}
            <a
              href={ENGINE_META[draftEngine]?.setup}
              target="_blank"
              rel="noreferrer"
              className="text-brand-600 hover:underline dark:text-brand-400"
            >
              Lấy API key ↗
            </a>
          </p>
        </div>
      )}

      <div className="card p-5">
        <div className="mb-3 flex items-center justify-between">
          <div className="text-sm font-semibold">
            Key đã lưu cho role này ({keysForRole.length})
          </div>
          <div className="text-xs text-slate-500 dark:text-slate-400">
            Sắp xếp theo priority — số nhỏ = thử trước
          </div>
        </div>
        {keysForRole.length === 0 ? (
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-400">
            Chưa có key nào. Bot sẽ dùng <code>{`{ENGINE}_API_KEY`}</code> trong .env nếu có.
          </div>
        ) : (
          <ul className="divide-y divide-slate-200 dark:divide-slate-700">
            {keysForRole.map((k) => (
              <li key={k.id} className="flex items-center gap-3 py-3">
                <div className="flex flex-col gap-1">
                  <button
                    onClick={() => move(k, -1)}
                    className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                    title="Tăng priority (lên trên)"
                  >
                    <ChevronUp size={14} />
                  </button>
                  <button
                    onClick={() => move(k, +1)}
                    className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                    title="Giảm priority"
                  >
                    <ChevronDown size={14} />
                  </button>
                </div>
                <div className="pill min-w-[42px] justify-center">#{k.priority}</div>
                <div className="flex-1">
                  <div className="font-medium">
                    {k.label}{" "}
                    <span className="text-xs font-normal text-slate-500 dark:text-slate-400">
                      ({k.engine})
                    </span>
                  </div>
                  <div className="font-mono text-xs text-slate-500 dark:text-slate-400">
                    {k.masked_key}
                  </div>
                  <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                    {k.quota_failures > 0 && (
                      <span className="mr-2 text-amber-600 dark:text-amber-400">
                        ⚠ {k.quota_failures} lần dính quota
                      </span>
                    )}
                    {k.last_used_at && (
                      <span>Dùng lần cuối: {new Date(k.last_used_at).toLocaleString("vi-VN")}</span>
                    )}
                  </div>
                </div>
                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={k.is_active}
                    onChange={() => toggleActive(k)}
                  />
                  Active
                </label>
                <button
                  className="btn-outline px-3 py-1.5 text-xs"
                  onClick={() => test(k)}
                  disabled={testingId === k.id}
                >
                  {testingId === k.id ? <Loader2 size={12} className="animate-spin" /> : "Test"}
                </button>
                <button
                  className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                  onClick={() => rename(k)}
                  title="Đổi tên"
                >
                  <Pencil size={14} />
                </button>
                <button
                  className="text-slate-400 hover:text-red-600"
                  onClick={() => remove(k.id)}
                  title="Xoá"
                >
                  <Trash2 size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900 dark:border-amber-700/40 dark:bg-amber-900/10 dark:text-amber-200">
        <b>Quy tắc fail-over</b>: pipeline chạy theo thứ tự priority asc, key cùng engine trước,
        sau đó mới đến engine khác trong cùng role. Khi tất cả key cho role này hết quota,
        pipeline sẽ ghi RunLog &quot;skipped&quot; và tiếp tục với design khác (không crash).
      </div>
    </div>
  );
}
