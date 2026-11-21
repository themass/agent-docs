import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement } from 'react';
import { vi, expect } from 'vitest';
import { waitFor } from '@testing-library/react';
import type { EventSourceLike } from '../api/events';
import { App } from '../app';
import { AnnouncerProvider } from '../components/announcer';
import { ACTOR_STORAGE_KEY, AuthProvider } from '../lib/actor';
import type { Role } from '../api/types';

// ---------- fetch 模拟 ----------

export interface MockRequest {
  method: string;
  path: string;
  query: URLSearchParams;
  body: unknown;
}
export type MockReply = unknown | Promise<unknown> | ((req: MockRequest) => unknown);

export interface MockRoute {
  method?: string;
  /** 以 /api/poetry/v1/agent 之后的路径匹配;字符串=精确,RegExp=正则。 */
  path: string | RegExp;
  reply: MockReply;
  status?: number;
}

export const OFF_ME = { auth_mode: 'off', warning: '离线演示模式:未启用登录。' };
export const requiredMe = (role: Role = 'CONTENT_EDITOR', actorId = 'li-wen', name = '李文') => ({
  auth_mode: 'required',
  actor: { actor_id: actorId, role, name },
});

export const json = (body: unknown, status = 200, headers: Record<string, string> = {}) => ({
  __json: true as const,
  body,
  status,
  headers,
});
export const apiError = (status: number, code: string, message: string, details?: unknown, headers: Record<string, string> = {}) =>
  json({ error: { code, message, ...(details === undefined ? {} : { details }) } }, status, headers);
export const page = <T,>(items: T[], extra: Partial<{ limit: number; offset: number; has_more: boolean }> = {}) => ({
  items,
  limit: extra.limit ?? 20,
  offset: extra.offset ?? 0,
  has_more: extra.has_more ?? false,
});

function isWrapped(value: unknown): value is { __json: true; body: unknown; status: number; headers: Record<string, string> } {
  return typeof value === 'object' && value !== null && (value as { __json?: boolean }).__json === true;
}

/** 安装假的 fetch。未匹配的请求返回 404,便于发现遗漏的路由。返回 spy 供断言。 */
export function mockBff(routes: MockRoute[]) {
  const defaults: MockRoute[] = [
    { path: '/health/ready', reply: { status: 'ready', worker_configured: true, reviewer_token_configured: true } },
    // 默认离线演示模式:无需登录,身份由占位选择器决定。登录相关测试用 REQUIRED_ME 覆盖。
    { path: '/auth/me', reply: OFF_ME },
    { method: 'POST', path: /^\/auth\/events-ticket\//, reply: { ticket: '', expires_at: 0 } },
  ];
  const all = [...routes, ...defaults];
  const spy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input));
    const path = url.pathname.replace('/api/poetry/v1/agent', '');
    const method = (init?.method ?? 'GET').toUpperCase();
    const body = typeof init?.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined;
    const route = all.find(r => (r.method ?? 'GET') === method && (typeof r.path === 'string' ? r.path === path : r.path.test(path)));
    if (!route) {
      return new Response(JSON.stringify({ error: { code: 'NOT_MOCKED', message: `未模拟 ${method} ${path}` } }), { status: 404 });
    }
    const raw = typeof route.reply === 'function' ? (route.reply as (r: MockRequest) => unknown)({ method, path, query: url.searchParams, body }) : route.reply;
    const value = await raw;
    if (isWrapped(value)) return new Response(JSON.stringify(value.body), { status: value.status, headers: value.headers });
    return new Response(JSON.stringify(value), { status: route.status ?? 200 });
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

/**
 * 页面上真正的 alert / notice。不能直接用 findByRole('alert'):页面常驻一个 sr-only 播报区
 * (screen-reader announcer),它也是 role="alert" 但内容为空,find 会命中最先出现的那个。
 * 这里显式排除 sr-only 区域,并接受 notice--info(离线演示的提示用的是这一档)。
 */
export async function findErrorAlert(): Promise<HTMLElement> {
  return waitFor(
    () => {
      const candidates = Array.from(document.querySelectorAll<HTMLElement>('[role="alert"]'))
        .filter((el) => !el.closest('.sr-only'));
      const found = candidates.find((el) => (el.textContent ?? '').trim().length > 0) ?? candidates[0];
      if (!found) throw new Error('no error alert yet');
      return found;
    },
    { timeout: 2000 },
  );
}

/** 取出某个调用的 Authorization 头(用于断言 Bearer)。 */
export function authHeaderOf(call: [RequestInfo | URL, RequestInit | undefined]): string | undefined {
  const headers = call[1]?.headers as Record<string, string> | undefined;
  return headers?.Authorization;
}

/** 取出某个方法+路径的所有调用(用于断言请求体)。 */
export function callsTo(spy: ReturnType<typeof mockBff>, method: string, pathPart: string) {
  return spy.mock.calls
    .filter(([input, init]) => (init?.method ?? 'GET').toUpperCase() === method && String(input).includes(pathPart))
    .map(([input, init]) => ({
      url: new URL(String(input)),
      body: typeof init?.body === 'string' ? (JSON.parse(init.body) as Record<string, unknown>) : undefined,
    }));
}

/** 永不返回的请求,用于 loading 态。 */
export const never = () => new Promise<never>(() => undefined);

// ---------- 假 EventSource ----------

export class FakeEventSource implements EventSourceLike {
  static instances: FakeEventSource[] = [];
  static reset() {
    FakeEventSource.instances = [];
  }
  static last(): FakeEventSource {
    const item = FakeEventSource.instances[FakeEventSource.instances.length - 1];
    if (!item) throw new Error('还没有创建任何 EventSource');
    return item;
  }
  static create = (url: string): EventSourceLike => new FakeEventSource(url);

  readyState = 0;
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  closed = false;
  private listeners = new Map<string, ((event: MessageEvent) => void)[]>();

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }
  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  close() {
    this.closed = true;
    this.readyState = 2;
  }
  open() {
    this.readyState = 1;
    this.onopen?.(new Event('open'));
  }
  /** 浏览器仍在自动重连(readyState=CONNECTING)。 */
  failTransient() {
    this.readyState = 0;
    this.onerror?.(new Event('error'));
  }
  /** 浏览器已放弃连接(readyState=CLOSED)。 */
  failFatal() {
    this.readyState = 2;
    this.onerror?.(new Event('error'));
  }
  emit(type: string, id: string, payload: Record<string, unknown> = {}, runId = 'run-1') {
    const data = JSON.stringify({
      event_id: id,
      run_id: runId,
      event_type: type,
      occurred_at: '2026-11-06T10:00:00Z',
      payload,
    });
    const event = new MessageEvent(type, { data, lastEventId: id });
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }
}

/** 带票据的连接在取票(异步)之后才创建 EventSource;测试里等它出现。 */
export async function waitForSource(count = 1): Promise<FakeEventSource> {
  await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThanOrEqual(count));
  return FakeEventSource.last();
}

// ---------- 渲染 ----------

export function seedActor(role: Role, actorId = 'li-wen') {
  window.localStorage.setItem(ACTOR_STORAGE_KEY, JSON.stringify({ actor_id: actorId, role }));
}

export function renderWithProviders(ui: ReactElement): RenderResult {
  return render(
    <AnnouncerProvider>
      <AuthProvider>{ui}</AuthProvider>
    </AnnouncerProvider>,
  );
}

export function renderApp(hash: string): RenderResult {
  window.location.hash = hash;
  return render(<App />);
}

// ---------- 数据样例 ----------

export const WORKS = [
  { work_id: 'work-chun-wang', title: '春望', status: 'DRAFT', line_count: 8, pending_source_count: 4 },
  { work_id: 'work-demo-empty', title: '空白作品', status: 'DRAFT', line_count: 0, pending_source_count: 0 },
];

export const TASK = {
  task_id: 'task-1',
  work_id: 'work-chun-wang',
  title: '春望 · 缺口分析',
  task_type: 'GAP_ANALYSIS',
  status: 'RUNNING',
  active_run_id: 'run-1',
  instructions: '列出缺口。',
  actor: { actor_id: 'li-wen', role: 'CONTENT_EDITOR' },
  created_at: '2026-11-06T09:00:00Z',
  updated_at: '2026-11-06T09:00:00Z',
};

export const RUN = {
  run_id: 'run-1',
  task_id: 'task-1',
  work_id: 'work-chun-wang',
  mandate_id: 'mandate-1',
  status: 'RUNNING',
  runtime: 'STUB',
  reason: null,
  budget: null,
  created_at: '2026-11-06T09:00:00Z',
  updated_at: '2026-11-06T09:00:00Z',
};

export const DIFF = {
  proposal_id: 'proposal_1',
  work_id: 'work-chun-wang',
  snapshot_taken_at: '2026-11-06T09:30:00Z',
  changes: [
    {
      index: 0, change_type: 'ANNOTATION', classification: 'INTERPRETATION', label: '解释', executable: true,
      target_ref: 'line:text-chun-wang-draft#1', before: null, after: '【解释】山河指国土。',
      annotation: { audience: 'PRIMARY', certainty: 'LIKELY' }, risks: ['certainty=LIKELY'], item_decision: null,
    },
    {
      index: 1, change_type: 'ANNOTATION', classification: 'DRAFT', label: '草稿', executable: true,
      target_ref: 'line:text-chun-wang-draft#2', before: { content: '城春草木深' }, after: '【草稿】春天的长安城。',
      annotation: null, risks: [], item_decision: null,
    },
    {
      index: 2, change_type: 'SCRIPT', classification: 'INTERPRETATION', label: '演绎', executable: false,
      target_ref: null, before: null, after: '【演绎】杜甫望着城墙叹气。', annotation: null, risks: [], item_decision: null,
    },
    {
      index: 3, change_type: 'CLAIM', classification: 'UNKNOWN', label: '来源请求', executable: false,
      target_ref: 'claim-tang-time', before: null, after: '【来源请求】请核对至德二年的出处。', annotation: null, risks: ['无出处'], item_decision: null,
    },
  ],
};

export const PROPOSAL = {
  proposal_id: 'proposal_1',
  work_id: 'work-chun-wang',
  run_id: 'run-1',
  task_id: 'task-1',
  status: 'REVIEW_REQUIRED',
  review_status: 'PENDING',
  created_at: '2026-11-06T09:30:00Z',
  applied_at: null,
  payload: { summary: '为两句诗补注释。', unknowns: ['至德二年的出处'], human_review_question: '是否采用这两条注释?' },
  items: [],
  executable_count: 2,
  approved_executable_count: 0,
};

export const COVERAGE = {
  work_id: 'work-chun-wang',
  totals: { lines: 2, versions: 1, backgrounds: 1, annotations: 1, claims: 3, sources: 2, citations: 2 },
  claims_by_status: { DRAFT: 3, PUBLISHED: 0 },
  claims_checkable: { checkable: 0, total: 3 },
  sources_by_verification: { PENDING: 2, VERIFIED: 0, REJECTED: 0 },
  layers: { SCENE: { count: 1, linked_lines: 1 }, CITY: {}, WORLD: {}, PERSON: {} },
  lines: [
    { version_id: 'text-chun-wang-draft', line_seq: 1, content: '国破山河在', annotation_count: 1, background_count: 1, layers: ['SCENE'] },
    { version_id: 'text-chun-wang-draft', line_seq: 2, content: '城春草木深', annotation_count: 0, background_count: 0, layers: [] },
  ],
  gap_codes: ['CLAIM_VERIFIED_CITATION_MISSING'],
  publication: { work_status: 'DRAFT', published_claims: 0, audit_checks: 106, audit_non_zero: [] },
};

export const GAP_REPORT = {
  work_id: 'work-chun-wang',
  gaps: [{ code: 'CLAIM_VERIFIED_CITATION_MISSING', severity: 'HIGH', message: '3 条 claim 没有已核验引用', target_ref: null }],
};

export const SOURCES = [
  {
    id: 'src-a', title: '旧唐书', verification_status: 'PENDING',
    citations: [
      { claim_id: 'claim-a1', claim_value: '至德二年', locator: '', locator_state: 'MISSING' },
      { claim_id: 'claim-a2', claim_value: '安史之乱', locator: '卷九', locator_state: 'SET' },
    ],
  },
  {
    id: 'src-b', title: '资治通鉴', verification_status: 'PENDING',
    citations: [{ claim_id: 'claim-b1', claim_value: '长安陷落', locator: '卷二百一十八', locator_state: 'SET' }],
  },
];

export const PRECHECK = {
  work_id: 'work-chun-wang',
  evaluated_at: '2026-11-06T10:00:00Z',
  bundle: { state: 'NOT_AVAILABLE' },
  verdict: 'INCOMPLETE',
  note: '没有 bundle,部分规则无法评估。',
  rules: [
    { id: 'R1', name: 'reference exists', evaluation: 'DATA', status: 'PASS', details: [] },
    { id: 'R2', name: 'published only', evaluation: 'DATA', status: 'FAIL', details: ['entity x 是 DRAFT'] },
    { id: 'R3', name: 'basis', evaluation: 'BUNDLE', status: 'NOT_EVALUATED', details: ['需要 bundle'] },
  ],
};

export const OVERVIEW = {
  work: { id: 'work-chun-wang', title: '春望', status: 'DRAFT' },
  versions: [{ id: 'text-chun-wang-draft', label: '草稿版', status: 'DRAFT', source_locator: '卷二' }],
  lines: [
    { version_id: 'text-chun-wang-draft', line_seq: 1, content: '国破山河在', pinyin: 'guó pò shān hé zài' },
    { version_id: 'text-chun-wang-draft', line_seq: 2, content: '城春草木深', pinyin: '' },
  ],
  claims: [
    { id: 'claim-fact', property_key: 'time', value_text: '至德二年春', claim_kind: 'FACT', certainty: 'KNOWN', status: 'DRAFT' },
    { id: 'claim-drama', property_key: 'line', value_text: '杜甫叹气', claim_kind: 'DRAMATIZATION', certainty: 'LIKELY', status: 'DRAFT' },
    { id: 'claim-unk', property_key: 'place', value_text: '具体地点', claim_kind: 'FACT', certainty: 'UNKNOWN', status: 'DRAFT' },
    { id: 'claim-pub', property_key: 'x', value_text: '已发布的说法', claim_kind: 'INTERPRETATION', certainty: 'LIKELY', status: 'PUBLISHED' },
  ],
  citations: [],
  backgrounds: [
    { id: 'bg-scene', layer: 'SCENE', body_text: '长安城春天', claim_id: 'claim-fact' },
    { id: 'bg-city', layer: 'CITY', body_text: '杜甫叹气', claim_id: 'claim-drama' },
  ],
  annotations: [{ id: 'ann-1', version_id: 'text-chun-wang-draft', line_seq: 1, annotation_kind: 'WORD', content: '山河', claim_id: 'claim-pub' }],
  sources: [],
  background_lines: [{ background_id: 'bg-scene', version_id: 'text-chun-wang-draft', line_seq: 1 }],
  claim_status_by_id: { 'claim-fact': 'DRAFT', 'claim-drama': 'DRAFT', 'claim-unk': 'DRAFT', 'claim-pub': 'PUBLISHED' },
  content_status_by_id: { 'bg-scene': 'DRAFT', 'bg-city': 'DRAFT', 'work-chun-wang': 'DRAFT' },
  version_status_by_id: { 'text-chun-wang-draft': 'DRAFT' },
  source_verification_by_id: {},
};
