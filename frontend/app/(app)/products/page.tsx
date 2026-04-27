"use client";
import { useEffect, useState } from "react";
import { api, type Product } from "@/lib/api";

export default function ProductsPage() {
  const [items, setItems] = useState<Product[]>([]);
  useEffect(() => { api.get<Product[]>("/v1/products").then(setItems).catch(() => {}); }, []);
  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Sản phẩm đã đăng</h1>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-2">ID</th>
              <th className="px-4 py-2">Tiêu đề</th>
              <th className="px-4 py-2">Trạng thái</th>
              <th className="px-4 py-2">Giá</th>
              <th className="px-4 py-2">Link</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p) => (
              <tr key={p.id} className="border-t border-slate-100">
                <td className="px-4 py-2">#{p.id}</td>
                <td className="px-4 py-2 font-medium">{p.title}</td>
                <td className="px-4 py-2">
                  <span className={
                    p.status === "published" ? "text-green-600" :
                    p.status === "failed" ? "text-red-600" : "text-slate-500"
                  }>{p.status}</span>
                </td>
                <td className="px-4 py-2">${p.price_usd.toFixed(2)}</td>
                <td className="px-4 py-2">
                  {p.url ? <a className="text-brand-600 underline" href={p.url} target="_blank">Xem</a> : "-"}
                </td>
              </tr>
            ))}
            {!items.length && <tr><td colSpan={5} className="px-4 py-10 text-center text-slate-500">Chưa có sản phẩm nào.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
