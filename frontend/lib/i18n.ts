// Minimal i18n stub. The app currently ships in Vietnamese; this scaffolds
// English mirroring + future locale switching without pulling next-intl yet.
//
// Usage:
//   import { t } from "@/lib/i18n";
//   t("nav.dashboard");
//
// Set the active locale at runtime via `setLocale("en")` (defaults to "vi"
// from the user record once the locale column is wired into /auth/me).

const DICT = {
  vi: {
    "nav.dashboard": "Dashboard",
    "nav.campaigns": "Chiến dịch",
    "nav.keywords": "Keyword",
    "nav.designs": "Designs",
    "nav.products": "Sản phẩm",
    "nav.pnl": "P&L",
    "nav.platforms": "Platform",
    "nav.templates": "Prompt Templates",
    "nav.trademark": "Trademark Shield",
    "nav.health": "Account Health",
    "nav.notifications": "Thông báo",
    "nav.ai_keys": "AI Keys",
    "nav.security": "Bảo mật",
    "nav.runs": "Run logs",
    "nav.settings": "Cài đặt",
    "nav.logout": "Đăng xuất",
    "common.save": "Lưu",
    "common.cancel": "Huỷ",
    "common.delete": "Xoá",
    "common.confirm": "Xác nhận",
    "common.loading": "Đang tải...",
    "common.error": "Lỗi",
    "security.2fa.title": "Two-factor authentication",
    "security.2fa.enable": "Bật 2FA bằng Google Authenticator",
    "security.gdpr.export": "Tải dữ liệu (JSON)",
    "security.gdpr.delete": "Xoá account vĩnh viễn",
  },
  en: {
    "nav.dashboard": "Dashboard",
    "nav.campaigns": "Campaigns",
    "nav.keywords": "Keywords",
    "nav.designs": "Designs",
    "nav.products": "Products",
    "nav.pnl": "P&L",
    "nav.platforms": "Platforms",
    "nav.templates": "Prompt Templates",
    "nav.trademark": "Trademark Shield",
    "nav.health": "Account Health",
    "nav.notifications": "Notifications",
    "nav.ai_keys": "AI Keys",
    "nav.security": "Security",
    "nav.runs": "Run logs",
    "nav.settings": "Settings",
    "nav.logout": "Log out",
    "common.save": "Save",
    "common.cancel": "Cancel",
    "common.delete": "Delete",
    "common.confirm": "Confirm",
    "common.loading": "Loading...",
    "common.error": "Error",
    "security.2fa.title": "Two-factor authentication",
    "security.2fa.enable": "Enable 2FA with Google Authenticator",
    "security.gdpr.export": "Download data (JSON)",
    "security.gdpr.delete": "Permanently delete account",
  },
} as const;

export type Locale = keyof typeof DICT;
export type TranslationKey = keyof (typeof DICT)["vi"];

let active: Locale = "vi";

export function setLocale(locale: Locale) {
  if (locale in DICT) {
    active = locale;
    if (typeof window !== "undefined") {
      window.localStorage.setItem("podbot_locale", locale);
    }
  }
}

export function getLocale(): Locale {
  if (typeof window !== "undefined") {
    const saved = window.localStorage.getItem("podbot_locale");
    if (saved === "vi" || saved === "en") return saved;
  }
  return active;
}

export function t(key: TranslationKey): string {
  const locale = getLocale();
  return DICT[locale][key] ?? DICT.vi[key] ?? key;
}
