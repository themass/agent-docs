import Link from "next/link";

import { PRODUCT_NAME } from "@/lib/brand";
import { CONTACT_EMAIL, OPERATOR_NAME } from "@/lib/legal";

export function SiteFooter() {
  return (
    <footer className="mt-6 shrink-0 border-t border-surface-border bg-surface px-4 py-4 text-xs text-ink-500">
      <div className="mx-auto flex max-w-shell flex-wrap items-center justify-between gap-x-6 gap-y-2">
        <p>
          © {new Date().getFullYear()} {PRODUCT_NAME} · {OPERATOR_NAME}
        </p>
        <nav className="flex flex-wrap gap-x-4 gap-y-1" aria-label="资源">
          <Link href="/guides" className="hover:text-ink-900">简历指南</Link>
          <Link href="/resume-format" className="hover:text-ink-900">格式转换</Link>
          <Link href="/resume-template" className="hover:text-ink-900">简历模板</Link>
        </nav>
        <nav className="flex flex-wrap gap-x-4 gap-y-1" aria-label="法律信息">
          <Link href="/privacy" className="hover:text-ink-900">隐私政策</Link>
          <Link href="/terms" className="hover:text-ink-900">用户协议</Link>
          <Link href="/membership-terms" className="hover:text-ink-900">会员与退款</Link>
          <a href={`mailto:${CONTACT_EMAIL}`} className="hover:text-ink-900">联系我们</a>
        </nav>
      </div>
    </footer>
  );
}
