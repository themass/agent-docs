/**
 * Media degradation is a policy with a floor, not an error path: text is always available and the
 * learner is told when something did not load. Budgets come from docs/specs/2026-11-06-frontend-
 * and-mobile-strategy.md §4.7 — they are hard limits, exceeded means we ship the lower level.
 */
import { TERMINAL_ASSET, type AssetSpec, type MediaLevel } from './bundle.ts';

export const ORDER: MediaLevel[] = ['L0', 'L1', 'L2', 'L3', 'L4'];
export const rank = (l: MediaLevel) => ORDER.indexOf(l);

export interface Budget {
  forceLevel?: MediaLevel;          // user setting: 图片/动画关掉
  weakNetwork?: boolean;            // RTT/loss probe, not a model-name guess
  lowMemory?: boolean;              // iOS WebView > 1.2GB, or device_memory <= 2
  reducedMotion?: boolean;          // prefers-reduced-motion / low fps
  maxBytesForScene?: number;        // default 8MB for the first scene (L0-L2)
}

export const DEFAULT_BUDGET: Budget = { maxBytesForScene: 8 * 1024 * 1024 };

export function ceiling(budget: Budget): MediaLevel {
  if (budget.forceLevel) return budget.forceLevel;
  if (budget.weakNetwork) return 'L1';
  if (budget.lowMemory) return 'L1';
  if (budget.reducedMotion) return 'L2';
  return 'L4';
}

export interface ResolvedAsset { assetId: string; level: MediaLevel; spec: AssetSpec; chain: string[]; degraded: boolean; reason?: string }

/** Walk the declared fallback chain until something fits the ceiling; text is the floor. */
export function resolve(assetId: string, assets: Record<string, AssetSpec>, budget: Budget = DEFAULT_BUDGET): ResolvedAsset {
  const cap = ceiling(budget);
  const chain: string[] = [];
  const first = assets[assetId];
  let id = assetId;
  let cursor: AssetSpec | undefined = first;
  while (cursor) {
    chain.push(id);
    if (rank(cursor.level) <= rank(cap)) {
      const spec = cursor;
      return {
        assetId: id, level: spec.level, spec, chain,
        degraded: spec !== first,
        reason: spec !== first ? `设备预算不足，从 ${first?.level} 降到 ${spec.level}` : undefined,
      };
    }
    const nextId = cursor.fallback?.[0];
    if (!nextId) break;
    id = nextId;
    cursor = assets[id];
  }
  // Nothing fitted. The chain must still land on text — if it cannot, the bundle is broken and
  // the compiler (not the client) is where this should have been caught.
  const floor = Object.entries(assets).find(([, a]) => a.level === 'L0');
  if (!floor) throw new Error(`${assetId}: no L0 fallback exists — this bundle must not have compiled`);
  return { assetId: floor[0], level: 'L0', spec: floor[1], chain: [...chain, floor[0]],
           degraded: true, reason: '媒体未加载，文字不受影响' };
}
