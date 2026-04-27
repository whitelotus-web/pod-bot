"use client";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, type PlatformAccount } from "@/lib/api";

type Meta = Record<string, {
  label: string;
  auth: string;
  tier?: string;
  supported: boolean;
  tagline?: string;
  setup_url?: string;
}>;

export default function PlatformsPage() {
  const [meta, setMeta] = useState<Meta>({});
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [form, setForm] = useState({ platform: "printify", label: "", api_key: "", shop_id: "" });

  async function load() {
    setMeta(await api.get<Meta>("/v1/platforms/meta"));
    setAccounts(await api.get<PlatformAccount[]>("/v1/platforms"));
  }
  useEffect(() => { load().catch(() => {}); }, []);

  async function create() {
    try {
      await api.post("/v1/platforms", form);
      toast.success("Đã lưu"); setForm({ platform: "printify", label: "", api_key: "", shop_id: "" }); load();
    } catch (e: any) { toast.error(e?.message || "Lỗi"); }
  }
  async function test(id: number) {
    const r = await api.post<any>(`/v1/platforms/${id}/test`);
    r.ok ? toast.success("Kết nối OK") : toast.error(r.error || "Thất bại");
  }
  async function del(id: number) {
    if (!confirm("Xoá account?")) return;
    await api.del(`/v1/platforms/${id}`); load();
  }

  async function connectEtsy() {
    try {
      const r = await api.get<{ authorize_url: string }>("/v1/platforms/etsy/oauth-start");
      window.location.href = r.authorize_url;
    } catch (e: any) { toast.error(e?.message || "Lỗi"); }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Kết nối Platform</h1>

      <div className="grid gap-3 sm:grid-cols-3">
        {Object.entries(meta).map(([k, v]) => (
          <div key={k} className="card p-4">
            <div className="flex items-center justify-between">
              <div className="font-semibold">{v.label}</div>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] uppercase text-slate-600">
                {v.tier || v.auth}
              </span>
            </div>
            {v.tagline && <p className="mt-1 text-xs text-slate-500">{v.tagline}</p>}
            {v.setup_url && (
              <a href={v.setup_url} target="_blank" rel="noreferrer"
                className="mt-2 inline-block text-xs text-brand-600 hover:underline">
                Lấy API key ↗
              </a>
            )}
          </div>
        ))}
      </div>

      <div className="card p-5">
        <h2 className="mb-3 text-lg font-semibold">Thêm tài khoản mới</h2>
        <div className="grid gap-3 sm:grid-cols-4">
          <select className="input" value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })}>
            {Object.entries(meta).map(([k, v]) => (
              <option key={k} value={k}>{v.label} {v.supported ? "" : " (beta)"}</option>
            ))}
          </select>
          <input className="input" placeholder="Nhãn (label)" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} />
          <input className="input sm:col-span-2" placeholder="API key" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} />
          <input className="input" placeholder="Shop ID (nếu có)" value={form.shop_id} onChange={(e) => setForm({ ...form, shop_id: e.target.value })} />
          <div className="sm:col-span-3 flex items-center gap-2">
            <button className="btn-primary" onClick={create}>Lưu</button>
            {form.platform === "etsy" && (
              <button className="btn-outline" onClick={connectEtsy}>Hoặc kết nối Etsy qua OAuth →</button>
            )}
          </div>
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">Platform</th>
              <th className="px-4 py-2">Label</th>
              <th className="px-4 py-2">Creds</th>
              <th className="px-4 py-2">Active</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((a) => (
              <tr key={a.id} className="border-t border-slate-100">
                <td className="px-4 py-2 font-medium">{a.platform}</td>
                <td className="px-4 py-2">{a.label || "-"}</td>
                <td className="px-4 py-2">{a.has_credentials ? "✓" : "—"}</td>
                <td className="px-4 py-2">{a.is_active ? "✓" : "—"}</td>
                <td className="px-4 py-2 text-right">
                  <button className="btn-ghost" onClick={() => test(a.id)}>Test</button>
                  <button className="btn-ghost text-red-600" onClick={() => del(a.id)}>Xoá</button>
                </td>
              </tr>
            ))}
            {!accounts.length && <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-500">Chưa kết nối platform nào.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
