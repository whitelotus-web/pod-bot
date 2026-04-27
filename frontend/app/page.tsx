import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col items-center justify-center gap-8 p-8 text-center">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <span className="rounded bg-brand-100 px-2 py-0.5 text-brand-700">v0.1</span>
        <span>Open-source POD automation</span>
      </div>
      <h1 className="text-5xl font-bold tracking-tight">
        POD Bot — Tự động <span className="text-brand-500">tìm → thiết kế → đăng</span> áo thun
      </h1>
      <p className="max-w-2xl text-lg text-slate-600">
        Kết nối Printify / Printful / Etsy một lần, chọn nguồn keyword (Google
        Trends, Amazon, Etsy, Pinterest, TikTok), rồi để AI lo phần còn lại.
      </p>
      <div className="flex gap-3">
        <Link href="/login" className="btn-primary">Đăng nhập</Link>
        <Link href="/dashboard" className="btn-outline">Mở dashboard</Link>
      </div>
      <div className="mt-12 grid w-full gap-6 text-left sm:grid-cols-3">
        {[
          ["🔎 Tìm keyword hot", "Tổng hợp Google Trends, Etsy, Amazon BSR, Pinterest & TikTok"],
          ["🎨 AI design", "Gemini / DALL-E / SDXL — prompt tối ưu cho print-on-demand"],
          ["🚀 Đăng tự động", "Adapter cho Printify, Printful, Etsy — mở rộng dễ dàng"],
        ].map(([t, d]) => (
          <div key={t} className="card p-5">
            <div className="mb-2 text-lg font-semibold">{t}</div>
            <div className="text-sm text-slate-600">{d}</div>
          </div>
        ))}
      </div>
    </main>
  );
}
