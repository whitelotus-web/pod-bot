import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "POD Bot — Tự động thiết kế & đăng áo thun",
  description: "Bot tự động tìm keyword hot → AI design → mockup → đăng bán áo thun",
};

// Run before React hydrates so the dark class is set before first paint.
const themeBootstrap = `
(function(){
  try {
    var s = localStorage.getItem('podbot_theme');
    var prefers = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (s === 'dark' || (s === null && prefers)) {
      document.documentElement.classList.add('dark');
    }
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
      <body>
        {children}
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
