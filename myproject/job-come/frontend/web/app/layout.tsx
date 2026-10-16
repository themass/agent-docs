import type { Metadata } from "next";

import { AppHeader } from "@/components/layout/AppHeader";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { NotificationProvider } from "@/lib/notifications/NotificationProvider";

import "./globals.css";

export const metadata: Metadata = {
  title: "JC · 主动跳槽的准备工具",
  description: "面向互联网行业知识工作者：优化简历、解析岗位、练习面试，为下一份更好的工作做准备。",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="h-full">
      <body className="flex h-full min-h-screen flex-col bg-surface-sunken font-sans antialiased">
        <AuthProvider>
          <NotificationProvider>
            <AppHeader />
            <main className="mx-auto flex min-h-0 w-full max-w-shell flex-1 flex-col px-3 py-3 sm:px-4 sm:py-4">
              {children}
            </main>
          </NotificationProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
