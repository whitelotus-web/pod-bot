"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Term = { id: number; term: string; source: string; note: string | null; created_at: string };
type CheckResult = {
  safe: boolean;
  reason: string | null;
  matched_phrase: string | null;
  source: string | null;
};

export default function TrademarkPage() {
  const [terms, setTerms] = useState<Term[]>([]);
  const [newTerm, setNewTerm] = useState("");
  const [newNote, setNewNote] = useState("");
  const [phrase, setPhrase] = useState("");
  const [enableUspto, setEnableUspto] = useState(false);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [loading, setLoading] = useState(false);

  const load = () =>
    api.get<Term[]>("/v1/trademark/terms").then(setTerms).catch(console.error);

  useEffect(() => {
    void load();
  }, []);

  const add = async () => {
    if (!newTerm.trim()) return;
    await api.post("/v1/trademark/terms", { term: newTerm.trim(), note: newNote.trim() || null });
    setNewTerm("");
    setNewNote("");
    void load();
  };

  const remove = async (id: number) => {
    await api.del(`/v1/trademark/terms/${id}`);
    void load();
  };

  const runCheck = async () => {
    if (!phrase.trim()) return;
    setLoading(true);
    try {
      const res = await api.post<CheckResult>("/v1/trademark/check", {
        phrase: phrase.trim(),
        enable_uspto: enableUspto,
      });
      setCheck(res);
    } catch (e) {
      setCheck({ safe: false, reason: String(e), matched_phrase: null, source: null });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Trademark Shield</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          3 lớp bảo vệ shop khỏi DMCA/trademark strike: substring marker (©, ®, ™…) →
          builtin blacklist 120+ brand → user blacklist của anh → USPTO TESS API (optional).
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
        <h3 className="font-semibold">Kiểm tra cụm từ</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto]">
          <input
            value={phrase}
            onChange={(e) => setPhrase(e.target.value)}
            placeholder="vd: Star Wars cat shirt"
            className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
          />
          <button
            onClick={runCheck}
            disabled={loading}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? "Đang quét…" : "Kiểm tra"}
          </button>
        </div>
        <label className="mt-2 flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
          <input
            type="checkbox"
            checked={enableUspto}
            onChange={(e) => setEnableUspto(e.target.checked)}
          />
          Bật check USPTO TESS (chậm hơn, cần API key cấu hình ở .env)
        </label>
        {check && (
          <div
            className={`mt-3 rounded-md p-3 text-sm ${
              check.safe
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-700/10 dark:text-emerald-300"
                : "bg-rose-50 text-rose-700 dark:bg-rose-700/10 dark:text-rose-300"
            }`}
          >
            {check.safe ? "✅ An toàn — không trùng trademark đã biết." : "⚠️ Phát hiện rủi ro!"}
            {check.reason && <div className="mt-1 text-xs opacity-90">Lý do: {check.reason}</div>}
            {check.source && <div className="text-xs opacity-70">Nguồn: {check.source}</div>}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
        <h3 className="font-semibold">Blacklist nội bộ</h3>
        <p className="text-xs text-slate-500">
          Thêm các cụm từ anh muốn chặn riêng (vd brand mới chưa có trong builtin list).
        </p>
        <div className="mt-3 grid gap-2 md:grid-cols-[1fr_1fr_auto]">
          <input
            value={newTerm}
            onChange={(e) => setNewTerm(e.target.value)}
            placeholder="Term"
            className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
          />
          <input
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            placeholder="Note (optional)"
            className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
          />
          <button
            onClick={add}
            className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            Thêm
          </button>
        </div>
        <ul className="mt-4 divide-y divide-slate-200 dark:divide-slate-700">
          {terms.length === 0 && (
            <li className="py-4 text-sm text-slate-400">Chưa có term nào.</li>
          )}
          {terms.map((t) => (
            <li key={t.id} className="flex items-center justify-between py-2">
              <div>
                <span className="font-medium">{t.term}</span>
                <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  {t.source}
                </span>
                {t.note && (
                  <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">{t.note}</span>
                )}
              </div>
              <button
                onClick={() => remove(t.id)}
                className="text-xs text-rose-600 hover:underline"
              >
                Xoá
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
