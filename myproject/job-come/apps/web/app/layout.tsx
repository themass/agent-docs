import type { Metadata } from "next";
import { Inter, Noto_Sans_SC } from "next/font/google";

import { AppHeader } from "@/components/layout/AppHeader";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { NotificationProvider } from "@/lib/notifications/NotificationProvider";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const notoSansSc = Noto_Sans_SC({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-noto",
  display: "swap",
});

export const metadata: Metadata = {
  title: "JobCome",
  description: "简历优化与面试辅导",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={`${inter.variable} ${notoSansSc.variable} h-full`}>
      <body
        className="flex h-full min-h-screen flex-col font-sans antialiased"
        style={{ fontFamily: "var(--font-noto), var(--font-inter), system-ui, sans-serif" }}
      >
        <AuthProvider>
          <NotificationProvider>
            <AppHeader />
            <main className="mx-auto flex w-full max-w-[1600px] flex-1 min-h-0 flex-col px-4 py-4 sm:py-5">
              {children}
            </main>
          </NotificationProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
