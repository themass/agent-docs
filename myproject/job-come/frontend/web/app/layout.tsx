import type { Metadata } from "next";

import { AppHeader } from "@/components/layout/AppHeader";
import { FeedbackLauncher } from "@/components/feedback/FeedbackLauncher";
import { AuthProvider } from "@/lib/auth/AuthProvider";
import { NotificationProvider } from "@/lib/notifications/NotificationProvider";

import {
  DOCUMENT_DESCRIPTION,
  DOCUMENT_TITLE,
  DOCUMENT_TITLE_TEMPLATE,
  PRODUCT_NAME,
  PRODUCT_NAME_EN,
} from "@/lib/brand";
import { rootJsonLd, SITE_KEYWORDS_EN, SITE_KEYWORDS_ZH, SITE_URL } from "@/lib/seo/site";

import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: DOCUMENT_TITLE,
    template: DOCUMENT_TITLE_TEMPLATE,
  },
  description: DOCUMENT_DESCRIPTION,
  keywords: [...SITE_KEYWORDS_ZH, ...SITE_KEYWORDS_EN],
  applicationName: PRODUCT_NAME,
  openGraph: {
    title: DOCUMENT_TITLE,
    description: DOCUMENT_DESCRIPTION,
    siteName: PRODUCT_NAME_EN,
    locale: "zh_CN",
    type: "website",
    url: SITE_URL,
  },
  twitter: {
    card: "summary_large_image",
    title: DOCUMENT_TITLE,
    description: DOCUMENT_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true },
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="h-full">
      <body className="flex h-full min-h-screen flex-col bg-surface-sunken font-sans antialiased">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(rootJsonLd()) }}
        />
        <AuthProvider>
          <NotificationProvider>
            <AppHeader />
            <main className="mx-auto flex min-h-0 w-full max-w-shell flex-1 flex-col px-3 py-3 sm:px-4 sm:py-4">
              {children}
            </main>
            <FeedbackLauncher />
          </NotificationProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
