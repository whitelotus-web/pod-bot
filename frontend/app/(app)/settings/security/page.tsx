"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";

type EnrollResponse = {
  secret: string;
  otpauth_uri: string;
  qr_label: string;
};

type StatusResponse = {
  two_factor_enabled: boolean;
  enrolled: boolean;
};

type ConfirmResponse = {
  enabled: boolean;
  recovery_codes: string[];
};

export default function SecurityPage() {
  const [enrollment, setEnrollment] = useState<EnrollResponse | null>(null);
  const [code, setCode] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get<StatusResponse>("/v1/two-factor/status")
      .then((s) => setEnabled(s.two_factor_enabled))
      .catch(() => setEnabled(false));
  }, []);

  async function startEnroll() {
    setBusy(true);
    try {
      const r = await api.post<EnrollResponse>("/v1/two-factor/enroll");
      setEnrollment(r);
    } catch (e: unknown) {
      toast.error(`Enroll failed: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function confirmEnroll() {
    if (!enrollment || code.length !== 6) {
      toast.error("Nhập đủ 6 chữ số từ Authenticator");
      return;
    }
    setBusy(true);
    try {
      const r = await api.post<ConfirmResponse>("/v1/two-factor/confirm", { code });
      toast.success("Đã bật 2FA");
      setRecoveryCodes(r.recovery_codes || []);
      setEnrollment(null);
      setCode("");
      setEnabled(true);
    } catch (e: unknown) {
      toast.error(`Mã không khớp: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    if (disableCode.length !== 6) {
      toast.error("Nhập 6 chữ số hiện tại để tắt");
      return;
    }
    if (!window.confirm("Tắt 2FA? Anh nên giữ 2FA bật cho production.")) return;
    setBusy(true);
    try {
      await api.post("/v1/two-factor/disable", { code: disableCode });
      toast.success("Đã tắt 2FA");
      setDisableCode("");
      setEnabled(false);
      setRecoveryCodes([]);
    } catch (e: unknown) {
      toast.error(`Tắt thất bại: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  async function exportData() {
    try {
      const data = await api.get("/v1/gdpr/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `podbot-export-${Date.now()}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Đã tải file export");
    } catch (e: unknown) {
      toast.error(`Export thất bại: ${(e as Error).message}`);
    }
  }

  async function deleteAccount() {
    const phrase = window.prompt(
      'GỠ vĩnh viễn account và TẤT CẢ dữ liệu? Gõ "DELETE" để xác nhận:',
    );
    if (phrase !== "DELETE") return;
    try {
      await api.post("/v1/gdpr/delete");
      toast.success("Đã xoá. Đăng xuất...");
      window.localStorage.clear();
      window.location.href = "/login";
    } catch (e: unknown) {
      toast.error(`Xoá thất bại: ${(e as Error).message}`);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-1">
      <header>
        <h1 className="text-2xl font-bold tracking-tight">Bảo mật</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          2FA TOTP + GDPR (export &amp; delete dữ liệu).
        </p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
        <h2 className="text-lg font-semibold">Two-factor authentication</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Trạng thái:{" "}
          {enabled === null ? (
            <span className="text-slate-400">đang kiểm tra...</span>
          ) : enabled ? (
            <span className="text-green-600 dark:text-green-400">đã bật</span>
          ) : (
            <span className="text-slate-500">chưa bật</span>
          )}
        </p>

        {recoveryCodes.length > 0 && (
          <div className="mt-4 rounded-lg border border-yellow-300 bg-yellow-50 p-4 text-sm dark:border-yellow-700 dark:bg-yellow-900/20">
            <strong>Recovery codes — chỉ hiện lần này, lưu lại an toàn:</strong>
            <ul className="mt-2 grid grid-cols-2 gap-1 font-mono text-xs">
              {recoveryCodes.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {!enrollment && !enabled && (
          <button
            onClick={startEnroll}
            disabled={busy}
            className="mt-4 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            Bật 2FA bằng Google Authenticator
          </button>
        )}

        {enrollment && (
          <div className="mt-4 space-y-3 text-sm">
            <p>1. Mở Google Authenticator / 1Password / Authy → paste link bên dưới hoặc copy secret.</p>
            <code className="block break-all rounded bg-slate-100 p-3 text-xs dark:bg-slate-800">
              {enrollment.otpauth_uri}
            </code>
            <p className="font-mono text-xs">
              Secret: <span className="select-all">{enrollment.secret}</span>
            </p>
            <p>2. Nhập 6 chữ số hiện tại để xác nhận:</p>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              placeholder="123456"
              className="w-32 rounded border px-3 py-2 font-mono text-lg"
            />
            <div className="flex gap-2">
              <button
                onClick={confirmEnroll}
                disabled={busy || code.length !== 6}
                className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                Xác nhận
              </button>
              <button
                onClick={() => {
                  setEnrollment(null);
                  setCode("");
                }}
                className="rounded-lg border px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                Huỷ
              </button>
            </div>
          </div>
        )}

        {enabled && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <input
              value={disableCode}
              onChange={(e) =>
                setDisableCode(e.target.value.replace(/\D/g, "").slice(0, 6))
              }
              inputMode="numeric"
              placeholder="6-digit code"
              className="w-40 rounded border px-3 py-2 font-mono"
            />
            <button
              onClick={disable}
              disabled={busy}
              className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 dark:border-red-700 dark:hover:bg-red-900/20"
            >
              Tắt 2FA
            </button>
          </div>
        )}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
        <h2 className="text-lg font-semibold">Dữ liệu của bạn (GDPR)</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Tải về toàn bộ dữ liệu account (AI keys được mask). Hoặc xoá vĩnh viễn không thể khôi phục.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={exportData}
            className="rounded-lg border px-4 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            Tải dữ liệu (JSON)
          </button>
          <button
            onClick={deleteAccount}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700"
          >
            Xoá account vĩnh viễn
          </button>
        </div>
      </section>
    </div>
  );
}
