"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { CheckCircle2, Circle, Sparkles, X } from "lucide-react";
import { api, type AIKey, type PlatformAccount } from "@/lib/api";

const DISMISSED_KEY = "podbot_onboarding_dismissed";

type Step = { id: string; label: string; href: string; done: boolean };

export function Onboarding() {
  const [aiKeys, setAiKeys] = useState<AIKey[]>([]);
  const [platforms, setPlatforms] = useState<PlatformAccount[]>([]);
  const [dismissed, setDismissed] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem(DISMISSED_KEY) === "1") {
      setDismissed(true);
    }
    Promise.all([
      api.get<AIKey[]>("/v1/ai-keys").catch(() => []),
      api.get<PlatformAccount[]>("/v1/platforms").catch(() => []),
    ]).then(([k, p]) => {
      setAiKeys(k);
      setPlatforms(p);
      setLoaded(true);
    });
  }, []);

  if (!loaded || dismissed) return null;

  const steps: Step[] = [
    { id: "ai", label: "Kết nối AI engine (Gemini/OpenAI/Replicate)", href: "/settings/ai", done: aiKeys.length > 0 },
    { id: "platform", label: "Kết nối Printify (hoặc Printful/Etsy)", href: "/platforms", done: platforms.length > 0 },
    { id: "campaign", label: "Tạo chiến dịch đầu tiên", href: "/campaigns/new", done: false },
  ];
  const allDone = steps.every((s) => s.done);
  if (allDone) return null;

  function dismiss() {
    localStorage.setItem(DISMISSED_KEY, "1");
    setDismissed(true);
  }

  const completed = steps.filter((s) => s.done).length;

  return (
    <div className="card relative border-brand-200 bg-brand-50/60 p-5 dark:border-brand-700 dark:bg-brand-700/10">
      <button
        onClick={dismiss}
        aria-label="Ẩn"
        className="absolute right-3 top-3 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
      >
        <X size={16} />
      </button>
      <div className="mb-3 flex items-center gap-2">
        <Sparkles className="text-brand-600 dark:text-brand-400" size={18} />
        <h2 className="text-lg font-semibold">
          Bắt đầu trong 3 bước ({completed}/3)
        </h2>
      </div>
      <ol className="space-y-2 text-sm">
        {steps.map((s, idx) => (
          <li key={s.id} className="flex items-center gap-3">
            {s.done ? (
              <CheckCircle2 className="text-emerald-500" size={18} />
            ) : (
              <Circle className="text-slate-400" size={18} />
            )}
            <Link
              href={s.href}
              className={
                s.done
                  ? "text-slate-500 line-through dark:text-slate-400"
                  : "font-medium text-brand-700 hover:underline dark:text-brand-300"
              }
            >
              {idx + 1}. {s.label}
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
