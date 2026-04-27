"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Megaphone,
  Search,
  Palette,
  Package,
  Plug,
  ListChecks,
  Settings,
  LogOut,
} from "lucide-react";
import { clearToken } from "@/lib/api";
import { useRouter } from "next/navigation";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/campaigns", label: "Chiến dịch", icon: Megaphone },
  { href: "/keywords", label: "Keyword", icon: Search },
  { href: "/designs", label: "Designs", icon: Palette },
  { href: "/products", label: "Sản phẩm", icon: Package },
  { href: "/platforms", label: "Platform", icon: Plug },
  { href: "/runs", label: "Run logs", icon: ListChecks },
  { href: "/settings", label: "Cài đặt", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  return (
    <aside className="sticky top-0 flex h-screen w-60 flex-col border-r border-slate-200 bg-white px-3 py-4">
      <div className="mb-6 px-2 text-xl font-bold tracking-tight">
        <span className="text-brand-500">POD</span> Bot
      </div>
      <nav className="flex-1 space-y-1">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm",
                active
                  ? "bg-brand-50 font-semibold text-brand-700"
                  : "text-slate-600 hover:bg-slate-100",
              )}
            >
              <Icon size={16} /> {label}
            </Link>
          );
        })}
      </nav>
      <button
        onClick={() => {
          clearToken();
          router.push("/login");
        }}
        className="mt-2 flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
      >
        <LogOut size={16} /> Đăng xuất
      </button>
    </aside>
  );
}
