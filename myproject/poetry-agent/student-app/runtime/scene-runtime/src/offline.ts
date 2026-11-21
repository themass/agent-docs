/**
 * Offline-first prefetch plan. Content-addressed assets + a byte quota: on a phone we download the
 * text and the audio first, animation last, and evict the least recently used scene when the quota
 * (default 300MB) is hit. Pure function so the native shell can reuse the exact same policy.
 */
import { rank, type Budget } from './degrade.ts';
import type { AssetSpec, BundleManifest } from './bundle.ts';

export const QUOTA_BYTES = 300 * 1024 * 1024;

export interface PrefetchPlan { download: { assetId: string; bytes: number }[]; skipped: string[]; totalBytes: number }

export function plan(manifest: BundleManifest, assets: Record<string, AssetSpec>, cap: Budget): PrefetchPlan {
  const capRank = rank(ceilingLevel(cap));
  const entries = Object.entries(assets)
    .filter(([, a]) => rank(a.level) <= capRank)
    // text/subtitle first, then audio, then images, then character animation last
    .sort((a, b) => rank(a[1].level) - rank(b[1].level) || (a[1].bytes ?? 0) - (b[1].bytes ?? 0));
  const sceneCap = cap.maxBytesForScene ?? 8 * 1024 * 1024;
  const out: PrefetchPlan = { download: [], skipped: [], totalBytes: 0 };
  for (const [assetId, a] of entries) {
    const bytes = a.bytes ?? 0;
    if (out.totalBytes + bytes > sceneCap) { out.skipped.push(assetId); continue; }
    out.download.push({ assetId, bytes });
    out.totalBytes += bytes;
  }
  return out;
}

function ceilingLevel(b: Budget) {
  if (b.forceLevel) return b.forceLevel;
  if (b.weakNetwork || b.lowMemory) return 'L1' as const;
  if (b.reducedMotion) return 'L2' as const;
  return 'L4' as const;
}

export async function evictToQuota(storage: { usage(): Promise<number>; keys(): Promise<string[]>; evict(k: string[]): Promise<void> }, quota = QUOTA_BYTES) {
  let used = await storage.usage();
  if (used <= quota) return { evicted: [] as string[], used };
  const keys = await storage.keys();               // shell keeps access order
  const evicted: string[] = [];
  for (const k of keys) {
    if (used <= quota) break;
    evicted.push(k);
    await storage.evict([k]);
    used = await storage.usage();
  }
  return { evicted, used };
}
