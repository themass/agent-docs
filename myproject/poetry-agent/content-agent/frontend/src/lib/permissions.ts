import type { Role } from '../api/types';
import { ROLE_LABEL } from './labels';

// 角色白名单取自协调者补充的 BFF 行为;服务端为准,这里只用于提前禁用并说明原因。
export const REVIEW_ROLES: readonly Role[] = ['CONTENT_EDITOR', 'HISTORICAL_REVIEWER'];
export const APPLY_ROLES: readonly Role[] = ['CONTENT_EDITOR', 'HISTORICAL_REVIEWER', 'RELEASE_MANAGER'];
export const SOURCE_ROLES: readonly Role[] = ['HISTORICAL_REVIEWER', 'PLATFORM_ADMIN'];

export const canReview = (role: Role) => REVIEW_ROLES.includes(role);
export const canApply = (role: Role) => APPLY_ROLES.includes(role);
export const canReviewSources = (role: Role) => SOURCE_ROLES.includes(role);

const names = (roles: readonly Role[]) => roles.map(r => `${ROLE_LABEL[r]}(${r})`).join('、');

export function reviewDenyReason(role: Role): string | null {
  return canReview(role) ? null : `当前角色 ${role} 不能评审提案。需要:${names(REVIEW_ROLES)}。服务端会再次校验。`;
}

export function applyDenyReason(role: Role): string | null {
  return canApply(role) ? null : `当前角色 ${role} 不能写入草稿。需要:${names(APPLY_ROLES)}。服务端会再次校验。`;
}

export function sourceDenyReason(role: Role): string | null {
  return canReviewSources(role)
    ? null
    : `当前角色 ${role} 不能填写 locator 或核验来源。需要:${names(SOURCE_ROLES)}。服务端会再次校验。`;
}

export const PERMISSION_MATRIX: { action: string; roles: readonly Role[] }[] = [
  { action: '评审提案(批准/驳回)', roles: REVIEW_ROLES },
  { action: '把已批准提案写入草稿', roles: APPLY_ROLES },
  { action: '填写 locator、核验/驳回来源', roles: SOURCE_ROLES },
];
