import type { StudioCitation, StudioClaim } from '../api/types';

/** DESIGN.md §4 的四态。none = 没有绑定 claim(不是“未考”,不能混淆)。 */
export type Basis = 'fact' | 'interp' | 'drama' | 'unknown';

export const BASIS_LABEL: Record<Basis, string> = {
  fact: '史实',
  interp: '解释',
  drama: '演绎',
  unknown: '不可考/待核',
};

/** claim 是否有“已核验来源 + 非空 locator”的引用。 */
export function claimVerified(claimId: string, citations: StudioCitation[]): boolean {
  return citations.some(
    c => c.claim_id === claimId && c.verification_status === 'VERIFIED' && (c.locator ?? '').trim() !== '',
  );
}

/**
 * claim → 视觉四态。
 * - 演绎(DRAMATIZATION) → drama;
 * - certainty=UNKNOWN → unknown(灰虚线,绝不画成不存在);
 * - FACT → fact,INTERPRETATION → interp。
 * 返回 null 表示该内容没有绑定 claim(调用方显示“未绑定 claim”,而非“未考”)。
 */
export function basisOfClaim(claim: StudioClaim | undefined): Basis | null {
  if (!claim) return null;
  if (claim.claim_kind === 'DRAMATIZATION') return 'drama';
  if (claim.certainty === 'UNKNOWN') return 'unknown';
  if (claim.claim_kind === 'FACT') return 'fact';
  if (claim.claim_kind === 'INTERPRETATION') return 'interp';
  return 'unknown';
}

export function indexBy<T>(items: T[], key: (item: T) => string): Map<string, T> {
  const map = new Map<string, T>();
  for (const item of items) map.set(key(item), item);
  return map;
}
