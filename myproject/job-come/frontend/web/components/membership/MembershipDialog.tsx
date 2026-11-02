"use client";

import { useEffect, useState } from "react";

import { getMembership, type Membership } from "@/lib/api/membership";
import { userFacingApiError } from "@/lib/api/user-error";

import { RedeemCodeForm } from "./RedeemCodeForm";

export type MembershipDialogReason = "quota_exhausted" | "upgrade";

export function MembershipDialog({
  open,
  reason,
  onClose,
  onMembershipChanged,
}: {
  open: boolean;
  reason: MembershipDialogReason;
  onClose: () => void;
  onMembershipChanged?: (membership: Membership) => void;
}) {
  const [membership, setMembership] = useState<Membership | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoadError(null);
    getMembership()
      .then((next) => {
        if (!cancelled) setMembership(next);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(userFacingApiError(err, "暂时没能读取会员信息。"));
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const purchaseUrl = membership?.purchase_url ?? null;
  const title = reason === "quota_exhausted" ? "免费下载次数已用完" : "开通会员";

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-ink-900/55 p-4"
      role="presentation"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className="card card-pad w-full max-w-md max-h-[calc(100dvh-2rem)] overflow-y-auto outline-none"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="text-base font-semibold text-ink-900">{title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-ink-600">
          {reason === "quota_exhausted"
            ? "每个账号可以免费下载一次简历，这次的机会已经用掉了。"
            : "会员期间下载简历不限次数。"}
        </p>

        <div className="mt-4 rounded-xl bg-brand-50/50 p-4 ring-1 ring-inset ring-brand-200">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-sm font-semibold text-ink-900">月会员</span>
            <span className="text-lg font-semibold text-ink-900">
              ¥{membership?.monthly_price_cny ?? 25}
              <span className="ml-1 text-xs font-normal text-ink-500">
                / {membership?.monthly_days ?? 30} 天
              </span>
            </span>
          </div>
          <ol className="mt-3 space-y-2 text-xs leading-relaxed text-ink-600">
            <li>1. 在咸鱼购买兑换码。</li>
            <li>2. 回到这里输入兑换码，即时开通。</li>
          </ol>
          {loadError ? (
            <p className="notice notice-warn mt-3 text-xs" role="alert">{loadError}</p>
          ) : purchaseUrl ? (
            <a
              href={purchaseUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-sm btn-primary mt-3 w-full justify-center"
            >
              去咸鱼购买兑换码
              <span aria-hidden>↗</span>
            </a>
          ) : (
            <p className="mt-3 text-xs text-ink-500">购买入口暂未开放，请稍后再来。</p>
          )}
        </div>

        <div className="mt-4 border-t border-surface-border pt-4">
          <RedeemCodeForm
            compact
            onRedeemed={(next) => {
              setMembership(next);
              onMembershipChanged?.(next);
            }}
          />
        </div>

        <div className="mt-4 flex justify-end">
          <button type="button" onClick={onClose} className="btn btn-sm btn-ghost">
            稍后再说
          </button>
        </div>
      </div>
    </div>
  );
}
