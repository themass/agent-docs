"use client";

import { useEffect, useState } from "react";

import { getMembership, type Membership } from "@/lib/api/membership";
import { userFacingApiError } from "@/lib/api/user-error";
import { formatDateTime } from "@/lib/datetime";

import { RedeemCodeForm } from "./RedeemCodeForm";

function tierBadge(tier: Membership["tier"]) {
  if (tier === "admin") return <span className="badge badge-brand">管理员</span>;
  if (tier === "vip") return <span className="badge badge-success">会员</span>;
  return <span className="badge badge-neutral">免费</span>;
}

export function MembershipPanel() {
  const [membership, setMembership] = useState<Membership | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMembership()
      .then(setMembership)
      .catch((err) => setError(userFacingApiError(err, "暂时没能读取会员信息。")));
  }, []);

  return (
    <section className="card card-pad">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-ink-900">会员与下载</h2>
          <p className="mt-1 text-xs text-ink-500">
            免费账号可以下载一次简历；月会员期间下载不限次数。
          </p>
        </div>
        {membership ? tierBadge(membership.tier) : null}
      </div>

      {error ? (
        <p className="notice notice-warn mt-3 text-xs" role="alert">{error}</p>
      ) : membership ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="space-y-2 text-sm text-ink-700">
            {membership.tier === "admin" ? (
              <p>管理员账号，下载不限次数。</p>
            ) : membership.tier === "vip" ? (
              <p>会员有效期至 <span className="font-medium">{formatDateTime(membership.vip_expires_at)}</span>，下载不限次数。</p>
            ) : membership.free_download_available ? (
              <p>你还有 1 次免费下载机会（终身一次）。</p>
            ) : (
              <p>免费下载次数已用完（{formatDateTime(membership.free_download_used_at)}）。</p>
            )}
            {membership.tier !== "admin" ? (
              <p className="text-xs text-ink-500">
                月会员 ¥{membership.monthly_price_cny} / {membership.monthly_days} 天。到期后不会补发额外的次数。
              </p>
            ) : null}
            {membership.tier !== "admin" && membership.purchase_url ? (
              <a
                href={membership.purchase_url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-sm btn-secondary"
              >
                去咸鱼购买兑换码
                <span aria-hidden>↗</span>
              </a>
            ) : null}
          </div>
          {membership.tier !== "admin" ? (
            <RedeemCodeForm onRedeemed={setMembership} />
          ) : null}
        </div>
      ) : (
        <p className="mt-4 text-sm text-ink-500">正在读取…</p>
      )}
    </section>
  );
}
