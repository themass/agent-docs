import { API_BASE, apiJson } from "./client";

export type RedeemCodeStatus = "unused" | "redeemed" | "void";

export type RedeemCodeItem = {
  id: string;
  code: string;
  batch_id: string;
  plan: string;
  duration_days: number;
  status: RedeemCodeStatus;
  expires_at: string | null;
  note: string | null;
  created_at: string;
  redeemed_at: string | null;
  redeemed_by_user_id: string | null;
  redeemed_by_email: string | null;
  voided_at: string | null;
};

export type RedeemCodeStats = {
  total: number;
  unused: number;
  redeemed: number;
  void: number;
};

export type RedeemCodeList = {
  items: RedeemCodeItem[];
  total: number;
  limit: number;
  offset: number;
  stats: RedeemCodeStats;
};

export type RedeemCodeFilters = {
  status?: RedeemCodeStatus | "";
  batchId?: string;
  search?: string;
};

export type RedeemCodeBatch = {
  batch_id: string;
  count: number;
  codes: string[];
};

function filterQuery(filters: RedeemCodeFilters): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.batchId) params.set("batch_id", filters.batchId.trim());
  if (filters.search) params.set("search", filters.search.trim());
  return params;
}

export function listRedeemCodes(
  filters: RedeemCodeFilters,
  paging: { limit: number; offset: number },
): Promise<RedeemCodeList> {
  const params = filterQuery(filters);
  params.set("limit", String(paging.limit));
  params.set("offset", String(paging.offset));
  return apiJson(`/admin/redeem-codes?${params.toString()}`);
}

export function createRedeemBatch(body: {
  count: number;
  note?: string;
  expires_at?: string;
}): Promise<RedeemCodeBatch> {
  return apiJson("/admin/redeem-codes/batches", {
    method: "POST",
    body: JSON.stringify({ plan: "monthly", ...body }),
  });
}

export function updateRedeemNote(id: string, note: string | null): Promise<RedeemCodeItem> {
  return apiJson(`/admin/redeem-codes/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ note }),
  });
}

export function voidRedeemCode(id: string): Promise<RedeemCodeItem> {
  return apiJson(`/admin/redeem-codes/${id}/void`, { method: "POST" });
}

export function deleteRedeemCode(id: string): Promise<void> {
  return apiJson(`/admin/redeem-codes/${id}`, { method: "DELETE" });
}

export function getPurchaseUrlSetting(): Promise<{ url: string | null }> {
  return apiJson("/admin/membership/purchase-url");
}

export function setPurchaseUrlSetting(url: string | null): Promise<{ url: string | null }> {
  return apiJson("/admin/membership/purchase-url", {
    method: "PUT",
    body: JSON.stringify({ url }),
  });
}

/** Fetches the CSV with the session cookie and saves it; a plain link would lose the cookie. */
export async function downloadRedeemCodesCsv(filters: RedeemCodeFilters): Promise<void> {
  const params = filterQuery(filters);
  const response = await fetch(`${API_BASE}/admin/redeem-codes/export.csv?${params.toString()}`, {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(`导出失败（${response.status}）`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const named = /filename="([^"]+)"/.exec(disposition);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = named?.[1] ?? "redeem-codes.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
