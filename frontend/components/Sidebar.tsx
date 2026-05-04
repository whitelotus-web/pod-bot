"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  Bell,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Megaphone,
  Package,
  Palette,
  Plug,
  Search,
  Settings,
  Shield,
  Sparkles,
} from "lucide-react";
import { clearToken } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/ThemeToggle";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/campaigns", label: "Chiến dịch", icon: Megaphone },
  { href: "/keywords", label: "Keyword", icon: Search },
  { href: "/designs", label: "Designs", icon: Palette },
  { href: "/products", label: "Sản phẩm", icon: Package },
  { href: "/platforms", label: "Platform", icon: Plug },
  { href: "/templates", label: "Prompt Templates", icon: Sparkles },
  { href: "/trademark", label: "Trademark Shield", icon: Shield },
  { href: "/health", label: "Account Health", icon: Activity },
  { href: "/notifications", label: "Thông báo", icon: Bell },
  { href: "/settings/ai", label: "AI Keys", icon: KeyRound },
  { href: "/runs", label: "Run logs", icon: ListChecks },
  { href: "/settings", label: "Cài đặt", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  return (
    <aside className="sticky top-0 flex h-screen w-60 flex-col border-r border-slate-200 bg-white px-3 py-4 dark:border-slate-700 dark:bg-slate-900">
      <div className="mb-6 px-2 text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
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
                  ? "bg-brand-50 font-semibold text-brand-700 dark:bg-brand-700/20 dark:text-brand-300"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800",
              )}
            >
              <Icon size={16} /> {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-2 space-y-1 border-t border-slate-200 pt-2 dark:border-slate-700">
        <ThemeToggle />
        <button
          onClick={() => {
            clearToken();
            router.push("/login");
          }}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          <LogOut size={16} /> Đăng xuất
        </button>
      </div>
    </aside>
  );
}
