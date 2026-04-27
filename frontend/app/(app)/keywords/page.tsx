"use client";
import { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";

const SOURCES = ["google_trends", "etsy", "amazon", "pinterest", "tiktok"];

type Preview = { term: string; source: string; score: number };

export default function KeywordsPage() {
  const [seed, setSeed] = useState("cat lovers");
  const [selected, setSelected] = useState<string[]>(SOURCES);
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState<Preview[]>([]);

  async function run() {
    setLoading(true);
    try {
      const r = await api.post<Preview[]>(`/v1/keywords/preview?seed=${encodeURIComponent(seed)}&top=30`, selected);
      setRows(r);
    } catch (e: any) {
      toast.error(e?.message || "Lỗi tìm keyword");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Keyword Scout</h1>
      <div className="card p-5 space-y-3">
        <div className="flex gap-2">
          <input className="input flex-1" value={seed} onChange={(e) => setSeed(e.target.value)}
            placeholder="Niche / từ khoá gốc (vd: cat lovers)" />
          <button className="btn-primary" onClick={run} disabled={loading}>
            {loading ? "Đang tìm..." : "🔎 Tìm"}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {SOURCES.map((s) => {
            const on = selected.includes(s);
            return (
              <button key={s} onClick={() =>
                setSelected((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]))
              } className={`rounded-full px-3 py-1 text-sm ${on ? "bg-brand-500 text-white" : "bg-slate-100"}`}>
                {s}
              </button>
            );
          })}
        </div>
      </div>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">#</th>
              <th className="px-4 py-2">Term</th>
              <th className="px-4 py-2">Source</th>
              <th className="px-4 py-2 text-right">Score</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.term}-${i}`} className="border-t border-slate-100">
                <td className="px-4 py-2 text-slate-500">{i + 1}</td>
                <td className="px-4 py-2 font-medium">{r.term}</td>
                <td className="px-4 py-2"><span className="pill">{r.source}</span></td>
                <td className="px-4 py-2 text-right tabular-nums">{r.score.toFixed(1)}</td>
              </tr>
            ))}
            {!rows.length && (
              <tr><td colSpan={4} className="px-4 py-10 text-center text-slate-500">
                Nhập niche và bấm Tìm.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
