import type { Role, TaskType } from '../api/types';

export const TASK_TYPE_INFO: Record<TaskType, { label: string; description: string }> = {
  GAP_ANALYSIS: {
    label: '缺口分析',
    description: '读取作品快照,列出缺注释、缺背景、缺出处的位置。只提出缺口与来源请求,不写史实。',
  },
  ANNOTATION_DRAFT: {
    label: '注释草稿',
    description: '为缺注释的诗句起草字词/典故注释。注释以“解释”提出,史实性内容只能转为来源请求。',
  },
  SCRIPT_DRAFT: {
    label: '剧本草稿',
    description: '起草情境剧本片段。所有对白与场景一律标为“演绎”,不作为史实使用。',
  },
  COMPILE_TRIAGE: {
    label: '编译分诊',
    description: '对发布前检查的阻塞项分类并给出处理顺序建议,不修改任何内容。',
  },
  CONTENT_REVIEW: {
    label: '内容审核',
    description: '发布前逐条审核已发布内容:依据是否支持陈述、两说是否被当定论、演绎是否标明、学段是否合适。只报问题,不改内容。',
  },
};

export function taskTypeLabel(value: string): string {
  return value in TASK_TYPE_INFO ? TASK_TYPE_INFO[value as TaskType].label : value;
}

export const ROLE_LABEL: Record<Role, string> = {
  CONTENT_EDITOR: '内容编辑',
  HISTORICAL_REVIEWER: '史料审核人',
  PLATFORM_ADMIN: '平台管理员',
  RELEASE_MANAGER: '发布管理',
};

export const LAYER_LABEL: Record<string, string> = {
  SCENE: '眼前(场景)',
  CITY: '这座城',
  WORLD: '这个天下',
  PERSON: '这个人',
};
export const LAYER_ORDER = ['SCENE', 'CITY', 'WORLD', 'PERSON'] as const;

export const CLAIM_KIND_LABEL: Record<string, string> = {
  FACT: '史实',
  INTERPRETATION: '解释',
  DRAMATIZATION: '演绎',
};

export const CERTAINTY_LABEL: Record<string, string> = {
  KNOWN: '确凿',
  LIKELY: '可能',
  DISPUTED: '两说并存',
  UNKNOWN: '不可考',
};

export const ANNOTATION_KIND_LABEL: Record<string, string> = {
  WORD: '字词',
  PHRASE: '词句',
  ALLUSION: '典故',
  IMAGE: '意象',
  RHYME: '音韵',
  OTHER: '其他',
};

/** 三个门禁级别共用的中文名;未知值原样显示,不猜。 */
export function labelOr(map: Record<string, string>, value: string | null | undefined): string {
  if (!value) return '—';
  return map[value] ?? value;
}

/** 发布前规则的中文释义,仅供阅读辅助;规则名以契约为准(与 rules.mjs 一致)。 */
export const RULE_GLOSS: Record<string, string> = {
  R1: '引用的实体都存在',
  R2: '只引用已发布内容',
  R3: '每句台词有依据,或明确标为演绎',
  R4: '每个素材的降级链终止于文字',
  R5: '已声明覆盖范围',
  R6: '未考年代必须声明,不可隐藏',
  R7: '注释来自内容底座,不写入页面',
  R8: '背景到诗句的链接落在真实诗句上',
  R9: '素材带内容哈希',
  R10: '素材权利与含义已填写',
  R11: '背景不堆砌(每条背景至少绑一句)',
  R12: '每步允许跳过与返回',
};
