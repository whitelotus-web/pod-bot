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
        <p className="text-sm text-slate-600">
          Các API key (Gemini, OpenAI, Printify, v.v.) được đặt qua file <code>.env</code>
          rồi restart Docker Compose. Xem README để biết chi tiết.
        </p>
      </div>
    </div>
  );
}
