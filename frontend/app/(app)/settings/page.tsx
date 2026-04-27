"use client";
import { useEffect, useState } from "react";
import { api, type User } from "@/lib/api";

export default function SettingsPage() {
  const [me, setMe] = useState<User | null>(null);
  useEffect(() => { api.get<User>("/v1/auth/me").then(setMe).catch(() => {}); }, []);
  return (
    <div className="max-w-2xl space-y-5">
      <h1 className="text-2xl font-bold">Cài đặt</h1>
      <div className="card p-5">
        <h2 className="mb-3 text-lg font-semibold">Tài khoản</h2>
        {me ? (
          <div className="space-y-1 text-sm">
            <div><b>Email:</b> {me.email}</div>
            <div><b>Họ tên:</b> {me.full_name || "-"}</div>
            <div><b>Admin:</b> {me.is_superuser ? "✓" : "—"}</div>
          </div>
        ) : (
          <div className="text-slate-500">Đang tải...</div>
        )}
      </div>
      <div className="card p-5">
        <h2 className="mb-3 text-lg font-semibold">Cấu hình hệ thống</h2>
        <ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">
          <li>
            🔑 <a href="/settings/ai" className="text-brand-600 hover:underline dark:text-brand-400">Quản lý AI keys</a> —
            paste Gemini / OpenAI / Replicate key qua UI (không cần sửa <code>.env</code>).
          </li>
          <li>
            🔌 <a href="/platforms" className="text-brand-600 hover:underline dark:text-brand-400">Kết nối platform POD</a> —
            Printify / Printful / Etsy.
          </li>
          <li>
            ⚙️ Các biến hệ thống còn lại (DB URL, secret key, v.v.) vẫn nằm trong <code>.env</code>.
          </li>
        </ul>
      </div>
    </div>
  );
}
