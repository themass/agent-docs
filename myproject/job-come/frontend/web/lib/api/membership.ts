import { apiJson } from "./client";

export type MembershipTier = "free" | "vip" | "admin";

export type Membership = {
  tier: MembershipTier;
  vip_expires_at: string | null;
  unlimited_download: boolean;
  free_download_available: boolean;
  free_download_used_at: string | null;
  monthly_price_cny: number;
  monthly_days: number;
  purchase_url: string | null;
};

export function getMembership(): Promise<Membership> {
  return apiJson("/membership/me");
}

export function redeemMembershipCode(code: string): Promise<Membership> {
  return apiJson("/membership/redeem", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}
