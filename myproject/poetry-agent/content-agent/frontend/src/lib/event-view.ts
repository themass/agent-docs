import type { RunEvent } from '../api/types';

export interface EventGroup {
  id: string;
  label: string;
  types: readonly string[];
}

export const EVENT_GROUPS: readonly EventGroup[] = [
  { id: 'lifecycle', label: '生命周期', types: ['RUN_CREATED', 'RUNTIME_ADMISSION', 'RUN_STATE_CHANGED', 'RUN_STARTED', 'RUN_CANCELLED'] },
  { id: 'context', label: '上下文与步骤', types: ['CONTEXT_LOADED', 'STEP'] },
  { id: 'model', label: '工具与模型', types: ['TOOL_CALL', 'MODEL_USAGE'] },
  { id: 'budget', label: '预算', types: ['BUDGET_UPDATE'] },
  { id: 'output', label: '输出校验与提案', types: ['OUTPUT_ACCEPTED', 'OUTPUT_REJECTED', 'PROPOSAL_RECORDED'] },
  { id: 'fault', label: '重试与故障', types: ['RETRY', 'CIRCUIT_OPEN', 'RUNTIME_FAILED'] },
  { id: 'review', label: '评审与应用', types: ['PROPOSAL_APPROVED', 'PROPOSAL_REJECTED', 'DRAFT_APPLICATION_COMPLETED'] },
];
const OTHER_GROUP: EventGroup = { id: 'other', label: '其他', types: [] };

/** 需要在视觉上加警示的事件。文字标记“故障/拒绝”,不只靠颜色。 */
const FAULT_TYPES = new Set(['RUNTIME_FAILED', 'CIRCUIT_OPEN', 'OUTPUT_REJECTED']);
export const isFaultEvent = (type: string) => FAULT_TYPES.has(type);

export function groupOf(type: string): EventGroup {
  return EVENT_GROUPS.find(g => g.types.includes(type)) ?? OTHER_GROUP;
}

export function groupEvents(events: RunEvent[]): { group: EventGroup; events: RunEvent[] }[] {
  const buckets = new Map<string, { group: EventGroup; events: RunEvent[] }>();
  for (const event of events) {
    const group = groupOf(event.event_type);
    const bucket = buckets.get(group.id) ?? { group, events: [] };
    bucket.events.push(event);
    buckets.set(group.id, bucket);
  }
  return [...EVENT_GROUPS, OTHER_GROUP].flatMap(g => {
    const bucket = buckets.get(g.id);
    return bucket ? [bucket] : [];
  });
}

const numericId = (id: string): number | null => (/^\d+$/.test(id) ? Number(id) : null);

/** 以 event_id 去重;全部为数字 id 时按数值排序,否则保持到达顺序。 */
export function mergeEvents(existing: RunEvent[], incoming: RunEvent[]): RunEvent[] {
  const seen = new Set(existing.map(e => e.event_id));
  const merged = [...existing];
  let changed = false;
  for (const event of incoming) {
    if (seen.has(event.event_id)) continue;
    seen.add(event.event_id);
    merged.push(event);
    changed = true;
  }
  if (!changed) return existing;
  if (merged.every(e => numericId(e.event_id) !== null)) {
    merged.sort((a, b) => (numericId(a.event_id) ?? 0) - (numericId(b.event_id) ?? 0));
  }
  return merged;
}

/** 载荷里即使混入这些键也不展示(契约要求事件只含元数据)。 */
const HIDDEN_KEYS = /prompt|content|message|text|output|completion|body|input_text|response/i;

export interface PayloadSummary {
  text: string;
  hiddenCount: number;
}

/** 只展示标量元数据;对象/数组折叠为计数,疑似正文的键直接隐藏。 */
export function summarizePayload(payload: Record<string, unknown>): PayloadSummary {
  const parts: string[] = [];
  let hiddenCount = 0;
  for (const [key, value] of Object.entries(payload)) {
    if (value === null || value === undefined) continue;
    if (HIDDEN_KEYS.test(key) && typeof value === 'string' && key !== 'detail') {
      hiddenCount += 1;
      continue;
    }
    if (typeof value === 'string') {
      parts.push(`${key}=${value.length > 80 ? `${value.slice(0, 80)}…` : value}`);
    } else if (typeof value === 'number' || typeof value === 'boolean') {
      parts.push(`${key}=${String(value)}`);
    } else if (Array.isArray(value)) {
      parts.push(`${key}=[${value.length} 项]`);
    } else {
      parts.push(`${key}={…}`);
    }
    if (parts.length >= 8) break;
  }
  return { text: parts.join(' · '), hiddenCount };
}
