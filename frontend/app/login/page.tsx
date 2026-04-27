"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@podbot.local");
  const [password, setPassword] = useState("admin123");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const r = await api.post<{ access_token: string }>("/v1/auth/login", { email, password });
      setToken(r.access_token);
      toast.success("Đăng nhập thành công");
      router.push("/dashboard");
    } catch (err: any) {
      toast.error(err?.message || "Đăng nhập thất bại");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center p-6">
      <h1 className="mb-6 text-3xl font-bold">Đăng nhập POD Bot</h1>
      <form onSubmit={onSubmit} className="card p-6 space-y-4">
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div>
          <label className="label">Mật khẩu</label>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button disabled={loading} className="btn-primary w-full" type="submit">
          {loading ? "Đang đăng nhập..." : "Đăng nhập"}
        </button>
        <p className="text-xs text-slate-500">
          Tài khoản admin mặc định: <code>admin@podbot.local</code> / <code>admin123</code>.
          Đổi trong <code>.env</code>.
        </p>
      </form>
    </main>
  );
}
