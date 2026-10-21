import Link from "next/link";
import type { ReactNode } from "react";

import { PRODUCT_TAGLINE } from "@/lib/brand";

type Props = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  /** Rendered under the card, usually the cross-link to the other auth page. */
  footer?: ReactNode;
};

/**
 * Shared frame for every /auth page.
 *
 * Two columns on large screens: the form on the left, a short value recap on the
 * right. The recap exists because these pages are the first thing a new user
 * sees, and a bare form gives no reason to finish signing up.
 */
export function AuthShell({ title, subtitle, children, footer }: Props) {
  return (
    <div className="flex flex-1 items-center justify-center py-6 sm:py-10">
      <div className="grid w-full max-w-4xl gap-8 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:items-center">
        <div className="card bg-sheen p-6 sm:p-8">
          <Link
            href="/resume-agent"
            className="inline-flex items-center gap-2 text-sm font-semibold tracking-tight text-ink-900"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-xs font-bold text-white shadow-brand">
              JC
            </span>
            舟卡
          </Link>

          <h1 className="mt-6 text-2xl font-semibold tracking-tight text-ink-900">{title}</h1>
          {subtitle ? (
            <p className="mt-1.5 max-w-prose text-sm leading-relaxed text-ink-500">{subtitle}</p>
          ) : null}

          <div className="mt-6">{children}</div>

          {footer ? (
            <div className="mt-6 border-t border-surface-border pt-4 text-center text-sm text-ink-500">
              {footer}
            </div>
          ) : null}
        </div>

        <aside className="hidden lg:block">
          <p className="label-meta">{PRODUCT_TAGLINE}</p>
          <h2 className="mt-2 text-2xl font-semibold leading-snug tracking-tight text-ink-900">
            把你的真实经历，
            <br />
            写成招聘方看得懂的简历。
          </h2>
          <ul className="mt-6 space-y-4">
            {[
              {
                title: "档案先对齐事实",
                desc: "解析简历成结构化档案，由你逐段确认，模型不会替你改事实。",
              },
              {
                title: "按岗位出优化稿",
                desc: "三档优化强度，每处改动都标出用了哪种强化手段，可逐条回看。",
              },
              {
                title: "导出前先过质检",
                desc: "站不住的表述会被拦下，通过后再导出 PDF / Word / 网页版。",
              },
            ].map((item) => (
              <li key={item.title} className="flex gap-3">
                <span
                  aria-hidden
                  className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-50 text-brand-600 ring-1 ring-inset ring-brand-100"
                >
                  <svg viewBox="0 0 16 16" className="h-3 w-3" fill="currentColor">
                    <path d="M6.2 11.3 3.4 8.5l1.13-1.13 1.67 1.67 4.27-4.27L11.6 5.9 6.2 11.3Z" />
                  </svg>
                </span>
                <div>
                  <p className="text-sm font-medium text-ink-900">{item.title}</p>
                  <p className="mt-0.5 max-w-prose text-xs leading-relaxed text-ink-500">
                    {item.desc}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}
