import type {
  Actor,
  AgentRun,
  AuthMe,
  EventsTicket,
  LoginResult,
  AgentTask,
  BudgetSummary,
  Coverage,
  CreateTaskInput,
  GapReport,
  LocatorInput,
  Page,
  Precheck,
  Proposal,
  ProposalDiff,
  ProposalFilters,
  Readiness,
  ReviewInput,
  RunBudgetResponse,
  Source,
  SourceFilters,
  StudioView,
  TaskFilters,
  ValidationDetail,
  VerificationInput,
  WorkSummary,
} from './types';
import { isRecord, num } from '../lib/guards';
import { getToken, notifyUnauthorized } from './session';

const DEFAULT_BASE = 'http://localhost:8100';

/** BFF 地址只来自构建期环境变量;前端不携带任何令牌或凭据。 */
export function apiBase(): string {
  const raw = import.meta.env.VITE_AGENT_BFF_URL;
  return (raw && raw.trim() !== '' ? raw.trim() : DEFAULT_BASE).replace(/\/+$/, '');
}

const PREFIX = '/api/poetry/v1/agent';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  /** 429 LOGIN_LOCKED 的 Retry-After(秒);其他错误为 null。 */
  readonly retryAfter: number | null;

  constructor(status: number, code: string, message: string, details?: unknown, retryAfter: number | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryAfter = retryAfter;
  }
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === 'AbortError'
    : isRecord(error) && error.name === 'AbortError';
}

type Query = Record<string, string | number | boolean | undefined | null>;

function buildUrl(path: string, query?: Query): string {
  const url = `${apiBase()}${PREFIX}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue;
    params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

/** 构造 SSE 地址(EventSource 无法自带请求头:续传用 after_event_id,鉴权用一次性 ticket)。 */
export function runEventsUrl(runId: string, afterEventId?: string, ticket?: string): string {
  return buildUrl(`/runs/${encodeURIComponent(runId)}/events`, { after_event_id: afterEventId, ticket });
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT';
  query?: Query;
  body?: unknown;
  signal?: AbortSignal;
}

function retryAfterSeconds(response: Response): number | null {
  const raw = response.headers.get('Retry-After');
  const value = raw ? Number(raw) : NaN;
  return Number.isFinite(value) && value >= 0 ? value : null;
}

async function parseErrorBody(response: Response): Promise<ApiError> {
  const retryAfter = retryAfterSeconds(response);
  let parsed: unknown = null;
  try {
    parsed = await response.json();
  } catch {
    parsed = null;
  }
  if (isRecord(parsed) && isRecord(parsed.error)) {
    const { code, message, details } = parsed.error;
    return new ApiError(
      response.status,
      typeof code === 'string' ? code : `HTTP_${response.status}`,
      typeof message === 'string' ? message : `请求失败(HTTP ${response.status})`,
      details,
      retryAfter,
    );
  }
  return new ApiError(response.status, `HTTP_${response.status}`, `请求失败(HTTP ${response.status})`, undefined, retryAfter);
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', query, body, signal } = options;
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  // 令牌只在请求头里出现;不写日志、不进界面。off 模式没有令牌,不加头。
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (isAbortError(error)) throw error;
    throw new ApiError(0, 'NETWORK_ERROR', '无法连接 BFF。请确认服务已启动,且地址与 CORS 白名单配置正确。');
  }
  if (!response.ok) {
    const error = await parseErrorBody(response);
    // 任何 401 AUTH_REQUIRED:清令牌并通知外壳回登录页(登录失败的 LOGIN_FAILED 不在此列)。
    if (error.status === 401 && error.code === 'AUTH_REQUIRED') notifyUnauthorized();
    throw error;
  }
  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError(response.status, 'INVALID_RESPONSE', 'BFF 返回了无法解析的响应。');
  }
}

/** 契约要求列表一律分页对象;对数组响应做兜底,避免页面崩溃。 */
export function toPage<T>(raw: unknown): Page<T> {
  if (Array.isArray(raw)) return { items: raw as T[], limit: raw.length, offset: 0, has_more: false };
  if (isRecord(raw) && Array.isArray(raw.items)) {
    return {
      items: raw.items as T[],
      limit: num(raw.limit) ?? raw.items.length,
      offset: num(raw.offset) ?? 0,
      has_more: raw.has_more === true,
    };
  }
  throw new ApiError(200, 'INVALID_RESPONSE', 'BFF 返回的列表格式不符合契约(缺少 items)。');
}

const enc = encodeURIComponent;

// ---------- 登录与会话 ----------

export function getMe(signal?: AbortSignal): Promise<AuthMe> {
  return request<AuthMe>('/auth/me', { signal });
}

/** 注意:密码只进请求体,不记录、不回显。 */
export function login(userId: string, password: string, signal?: AbortSignal): Promise<LoginResult> {
  return request<LoginResult>('/auth/login', { method: 'POST', body: { user_id: userId, password }, signal });
}

/** SSE 连接票据:只对该 run 有效、约 60 秒;每次(重)连接都要重新取。off 模式返回空 ticket。 */
export function getEventsTicket(runId: string, signal?: AbortSignal): Promise<EventsTicket> {
  return request<EventsTicket>(`/auth/events-ticket/${encodeURIComponent(runId)}`, { method: 'POST', signal });
}

// ---------- 健康 ----------

export function getReadiness(signal?: AbortSignal): Promise<Readiness> {
  return request<Readiness>('/health/ready', { signal });
}

// ---------- 任务与运行 ----------

export async function listTasks(filters: TaskFilters, signal?: AbortSignal): Promise<Page<AgentTask>> {
  return toPage<AgentTask>(await request<unknown>('/tasks', { query: { ...filters }, signal }));
}

export function createTask(input: CreateTaskInput, signal?: AbortSignal): Promise<AgentTask> {
  return request<AgentTask>('/tasks', {
    method: 'POST',
    body: { ...input, requested_profile: 'authoring' },
    signal,
  });
}

export function getTask(taskId: string, signal?: AbortSignal): Promise<AgentTask> {
  return request<AgentTask>(`/tasks/${enc(taskId)}`, { signal });
}

export async function listRuns(taskId: string, signal?: AbortSignal): Promise<AgentRun[]> {
  return toPage<AgentRun>(await request<unknown>(`/tasks/${enc(taskId)}/runs`, { signal })).items;
}

/** runtime 省略 = 由 BFF 按配置选 DEERFLOW 或 STUB;'STUB' = 确定性运行时重试。 */
export function startRun(taskId: string, runtime?: 'STUB', signal?: AbortSignal): Promise<AgentRun> {
  return request<AgentRun>(`/tasks/${enc(taskId)}/run`, {
    method: 'POST',
    body: runtime ? { runtime } : undefined,
    signal,
  });
}

export function cancelRun(runId: string, actor?: Actor, signal?: AbortSignal): Promise<AgentRun> {
  return request<AgentRun>(`/runs/${enc(runId)}/cancel`, {
    method: 'POST',
    body: actor ? { actor } : undefined,
    signal,
  });
}

export function getRun(runId: string, signal?: AbortSignal): Promise<AgentRun> {
  return request<AgentRun>(`/runs/${enc(runId)}`, { signal });
}

/** budget 字段在不同响应里同形且可空;所有数值字段独立容错。 */
export function parseBudget(raw: unknown): BudgetSummary | null {
  if (!isRecord(raw)) return null;
  const budget: BudgetSummary = {
    tool_calls: num(raw.tool_calls),
    max_tool_calls: num(raw.max_tool_calls),
    elapsed_s: num(raw.elapsed_s),
    max_wall_s: num(raw.max_wall_s),
    tokens: num(raw.tokens),
    max_tokens: num(raw.max_tokens),
  };
  return Object.values(budget).every(value => value === null) ? null : budget;
}

export async function getRunBudget(runId: string, signal?: AbortSignal): Promise<RunBudgetResponse> {
  const raw = await request<unknown>(`/runs/${enc(runId)}/budget`, { signal });
  const body = isRecord(raw) ? raw : {};
  return {
    run_id: typeof body.run_id === 'string' ? body.run_id : runId,
    budget: parseBudget(body.budget),
    event_id: typeof body.event_id === 'string' ? body.event_id : null,
  };
}

// ---------- 提案与评审 ----------

export async function listProposals(filters: ProposalFilters, signal?: AbortSignal): Promise<Page<Proposal>> {
  return toPage<Proposal>(await request<unknown>('/proposals', { query: { ...filters }, signal }));
}

export function getProposal(proposalId: string, signal?: AbortSignal): Promise<Proposal> {
  return request<Proposal>(`/proposals/${enc(proposalId)}`, { signal });
}

export function getProposalDiff(proposalId: string, signal?: AbortSignal): Promise<ProposalDiff> {
  return request<ProposalDiff>(`/proposals/${enc(proposalId)}/diff`, { signal });
}

export function reviewProposal(proposalId: string, input: ReviewInput, signal?: AbortSignal): Promise<Proposal> {
  return request<Proposal>(`/proposals/${enc(proposalId)}/review`, { method: 'POST', body: input, signal });
}

/** 契约补充:off 模式 apply 必须带 {actor};required 模式不带。 */
export function applyProposal(proposalId: string, actor?: Actor, signal?: AbortSignal): Promise<unknown> {
  // required 模式不带 actor(服务端以令牌为准);off 模式带。
  return request<unknown>(`/proposals/${enc(proposalId)}/apply`, {
    method: 'POST',
    body: actor ? { actor } : {},
    signal,
  });
}

// ---------- 作品、覆盖、预检 ----------

export async function listWorks(signal?: AbortSignal): Promise<Page<WorkSummary>> {
  return toPage<WorkSummary>(await request<unknown>('/works', { query: { limit: 200 }, signal }));
}

export function getOverview(workId: string, signal?: AbortSignal): Promise<StudioView> {
  return request<StudioView>(`/works/${enc(workId)}/overview`, { signal });
}

export function getCoverage(workId: string, signal?: AbortSignal): Promise<Coverage> {
  return request<Coverage>(`/works/${enc(workId)}/coverage`, { signal });
}

export function getGapReport(workId: string, signal?: AbortSignal): Promise<GapReport> {
  return request<GapReport>(`/works/${enc(workId)}/gap-report`, { signal });
}

export function getPrecheck(workId: string, signal?: AbortSignal): Promise<Precheck> {
  return request<Precheck>(`/works/${enc(workId)}/precheck`, { signal });
}

// ---------- 出处核查 ----------

export async function listSources(filters: SourceFilters, signal?: AbortSignal): Promise<Page<Source>> {
  return toPage<Source>(await request<unknown>('/sources', { query: { ...filters }, signal }));
}

export function putLocator(
  claimId: string,
  sourceId: string,
  input: LocatorInput,
  signal?: AbortSignal,
): Promise<unknown> {
  return request<unknown>(`/sources/citations/${enc(claimId)}/${enc(sourceId)}/locator`, {
    method: 'PUT',
    body: input,
    signal,
  });
}

export function postVerification(sourceId: string, input: VerificationInput, signal?: AbortSignal): Promise<unknown> {
  return request<unknown>(`/sources/${enc(sourceId)}/verification`, { method: 'POST', body: input, signal });
}

export function sourceIdOf(source: Source): string {
  return source.id ?? source.source_id ?? '';
}

/** 从 422 VALIDATION_ERROR 里取出 details,按字段名归类。 */
export function validationDetails(error: unknown): ValidationDetail[] {
  if (!(error instanceof ApiError) || !Array.isArray(error.details)) return [];
  const result: ValidationDetail[] = [];
  for (const item of error.details) {
    if (isRecord(item) && typeof item.message === 'string') {
      const loc = Array.isArray(item.loc) ? item.loc.map(String) : [];
      result.push({ loc, message: item.message });
    }
  }
  return result;
}
