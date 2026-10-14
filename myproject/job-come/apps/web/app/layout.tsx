import type { Metadata } from "next";

import { AppHeader } from "@/components/layout/AppHeader";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { NotificationProvider } from "@/lib/notifications/NotificationProvider";

import "./globals.css";

export const metadata: Metadata = {
  title: "JobCome",
  description: "简历优化与面试辅导",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="h-full">
      <body
        className="flex h-full min-h-screen flex-col font-sans antialiased"
        style={{ fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif' }}
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
