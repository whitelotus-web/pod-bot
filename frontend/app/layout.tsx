import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "POD Bot — Tự động thiết kế & đăng áo thun",
  description: "Bot tự động tìm keyword hot → AI design → mockup → đăng bán áo thun",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body>
        {children}
        <Toaster richColors position="top-right" />
      </body>
    </html>
  );
}
