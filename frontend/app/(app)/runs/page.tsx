"use client";
import { useEffect, useState } from "react";
import { api, type RunLog } from "@/lib/api";

export default function RunsPage() {
  const [items, setItems] = useState<RunLog[]>([]);
  useEffect(() => { api.get<RunLog[]>("/v1/runs?limit=200").then(setItems).catch(() => {}); }, []);
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Run logs</h1>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">#</th>
              <th className="px-4 py-2">Campaign</th>
              <th className="px-4 py-2">Stage</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2">Message</th>
              <th className="px-4 py-2">Time</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 align-top">
                <td className="px-4 py-2">{r.id}</td>
                <td className="px-4 py-2">#{r.campaign_id ?? "-"}</td>
                <td className="px-4 py-2"><span className="pill">{r.stage}</span></td>
                <td className={
                  `px-4 py-2 font-medium ${r.status === "success" ? "text-green-600" :
                  r.status === "failed" ? "text-red-600" : "text-slate-500"}`
                }>{r.status}</td>
                <td className="px-4 py-2 max-w-sm truncate">{r.message || JSON.stringify(r.data || {})}</td>
                <td className="px-4 py-2 text-slate-500">{new Date(r.started_at).toLocaleString("vi-VN")}</td>
              </tr>
            ))}
            {!items.length && <tr><td colSpan={6} className="px-4 py-10 text-center text-slate-500">Chưa có run nào.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
