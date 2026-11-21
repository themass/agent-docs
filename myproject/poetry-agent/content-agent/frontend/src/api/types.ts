// 类型依据:A-contract.md §3.3/§3.4/§7 与协调者补充的 BFF 实际行为。
// 契约未写明字段的实体(studio-view 里的 claim/background 等)一律把非主键字段标为可选,
// 渲染层必须容忍缺失,不得假设存在。

export const ROLES = ['CONTENT_EDITOR', 'HISTORICAL_REVIEWER', 'PLATFORM_ADMIN', 'RELEASE_MANAGER'] as const;
export type Role = (typeof ROLES)[number];

/** 未接入登录的占位身份(D8)。服务端校验角色白名单,前端不可信。 */
export interface Actor {
  actor_id: string;
  role: Role;
}

/** 登录后由 /auth/me 或登录响应给出;name 仅用于显示。 */
export interface SessionActor extends Actor {
  name?: string;
}

/** off = 离线演示(占位身份选择器、请求体带 actor);required = 必须登录(身份以令牌为准)。 */
export type AuthMode = 'off' | 'required';

export interface AuthMe {
  auth_mode: AuthMode;
  warning?: string;
  actor?: SessionActor;
}

export interface LoginResult {
  token: string;
  /** 秒级 unix 时间。 */
  expires_at: number;
  actor: SessionActor;
}

export interface EventsTicket {
  /** off 模式下为空字符串:此时连接不加 ticket 参数。 */
  ticket: string;
  expires_at: number;
}

export interface Page<T> {
  items: T[];
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

/** 422 VALIDATION_ERROR 的 details 单项。 */
export interface ValidationDetail {
  loc: string[];
  message: string;
}

// ---------- 任务与运行 ----------

export const TASK_TYPES = ['GAP_ANALYSIS', 'ANNOTATION_DRAFT', 'SCRIPT_DRAFT', 'COMPILE_TRIAGE', 'CONTENT_REVIEW'] as const;
export type TaskType = (typeof TASK_TYPES)[number];

export type RunStatus =
  | 'CREATED'
  | 'RUNNING'
  | 'WAITING_FOR_RUNTIME'
  | 'AWAITING_REVIEW'
  | 'COMPLETED'
  | 'FAILED';

export type RuntimeKind = 'DEERFLOW' | 'STUB';

export interface AgentTask {
  task_id: string;
  work_id: string;
  title: string;
  task_type: TaskType;
  status: RunStatus | string;
  active_run_id?: string | null;
  instructions: string;
  actor?: Actor;
  created_at: string;
  updated_at: string;
}

/** BUDGET_UPDATE 汇总。各字段可空:BFF 可能只给部分。 */
export interface BudgetSummary {
  tool_calls: number | null;
  max_tool_calls: number | null;
  elapsed_s: number | null;
  max_wall_s: number | null;
  tokens: number | null;
  max_tokens: number | null;
}

export interface AgentRun {
  run_id: string;
  task_id: string;
  work_id?: string;
  mandate_id?: string;
  status: RunStatus | string;
  runtime: RuntimeKind | string;
  profile_name?: string;
  profile_fingerprint?: string;
  reason?: string | null;
  budget?: BudgetSummary | null;
  created_at: string;
  updated_at: string;
}

export interface RunBudgetResponse {
  run_id: string;
  budget: BudgetSummary | null;
  event_id: string | null;
}

export interface RunEvent {
  /** SSE id,数字字符串;重连续传依据。 */
  event_id: string;
  run_id: string;
  event_type: string;
  occurred_at: string;
  /** 只含元数据(契约 §7.1),UI 只展示标量。 */
  payload: Record<string, unknown>;
}

export interface TaskFilters {
  work_id?: string;
  status?: string;
  task_type?: string;
  limit?: number;
  offset?: number;
}

export interface CreateTaskInput {
  work_id: string;
  title: string;
  task_type: TaskType;
  instructions: string;
  /** off 模式带;required 模式不带(服务端以令牌为准)。 */
  actor?: Actor;
}

// ---------- 提案与评审 ----------

export type ProposalStatus = 'REVIEW_REQUIRED' | 'APPROVED' | 'REJECTED' | 'APPLIED';
export type ItemDecisionValue = 'APPROVE' | 'REJECT';

export interface ItemDecision {
  item_index: number;
  decision: ItemDecisionValue;
  reviewer?: string | null;
  comment?: string | null;
  created_at?: string;
}

export interface ProposalPayload {
  summary?: string;
  unknowns?: string[];
  human_review_question?: string;
  changes?: unknown[];
}

export interface Proposal {
  proposal_id: string;
  work_id: string;
  run_id: string;
  task_id?: string;
  mandate_id?: string;
  status: ProposalStatus | string;
  review_status?: string | null;
  reviewed_by?: string | null;
  review_comment?: string | null;
  created_at: string;
  applied_at?: string | null;
  payload?: ProposalPayload | null;
  /** 列表项为 null,详情才有。 */
  items?: ItemDecision[] | null;
  executable_count?: number | null;
  /** 仅详情。 */
  approved_executable_count?: number | null;
}

export type DiffLabel = '来源请求' | '解释' | '演绎' | '草稿' | '未考' | '缺口';

export interface DiffChange {
  index: number;
  change_type: string;
  classification: string;
  label: DiffLabel | string;
  executable: boolean;
  target_ref: string | null;
  before: Record<string, unknown> | null;
  after: string;
  annotation: Record<string, unknown> | null;
  risks: string[];
  item_decision: { decision: ItemDecisionValue; comment?: string | null; reviewer?: string | null } | null;
}

export interface ProposalDiff {
  proposal_id: string;
  work_id: string;
  snapshot_taken_at?: string;
  changes: DiffChange[];
}

export interface ProposalFilters {
  work_id?: string;
  status?: string;
  run_id?: string;
  task_id?: string;
  limit?: number;
  offset?: number;
}

export interface ReviewInput {
  actor?: Actor;
  decision: ItemDecisionValue;
  comment?: string;
  item_decisions?: { item_index: number; decision: ItemDecisionValue; comment?: string }[];
}

// ---------- 作品 / 覆盖 / 内容 ----------

export interface WorkSummary {
  work_id: string;
  title: string;
  status: string;
  genre?: string | null;
  dynasty_id?: string | null;
  line_count?: number;
  version_count?: number;
  background_count?: number;
  annotation_count?: number;
  claim_count?: number;
  pending_source_count?: number;
}

export interface LayerCoverage {
  count?: number;
  linked_lines?: number;
}

export interface LineCoverage {
  version_id: string;
  line_seq: number;
  content: string;
  annotation_count: number;
  background_count: number;
  layers: string[];
}

export interface Coverage {
  work_id: string;
  totals: Record<string, number>;
  claims_by_status: Record<string, number>;
  claims_checkable: { checkable: number; total: number };
  sources_by_verification: Record<string, number>;
  layers: Record<string, LayerCoverage>;
  lines: LineCoverage[];
  gap_codes: string[];
  publication?: {
    work_status?: string;
    published_claims?: number;
    audit_checks?: number;
    audit_non_zero?: unknown[];
  };
}

export interface Gap {
  code: string;
  severity?: string;
  message?: string;
  target_ref?: string | null;
}

export interface GapReport {
  work_id?: string;
  gaps: Gap[];
  audit_checks?: number;
  audit_non_zero?: unknown[];
}

export interface StudioWork {
  id?: string;
  title?: string;
  status?: string;
  summary?: string | null;
  [key: string]: unknown;
}

export interface StudioVersion {
  id: string;
  work_id?: string;
  version_code?: string;
  label?: string | null;
  script?: string | null;
  source_id?: string | null;
  source_locator?: string | null;
  status?: string;
}

export interface StudioLine {
  version_id: string;
  line_seq: number;
  content: string;
  pinyin?: string | null;
}

export interface StudioClaim {
  id: string;
  subject_id?: string;
  property_key?: string;
  value_text?: string;
  claim_kind?: string;
  certainty?: string;
  status?: string;
}

export interface StudioCitation {
  claim_id: string;
  source_id: string;
  locator?: string | null;
  evidence_excerpt?: string | null;
  verification_status?: string;
}

export interface StudioBackground {
  id: string;
  work_id?: string;
  layer: string;
  audience?: string;
  body_text?: string;
  claim_id?: string | null;
}

export interface StudioAnnotation {
  id: string;
  version_id: string;
  line_seq: number;
  annotation_kind?: string;
  audience?: string;
  content?: string;
  claim_id?: string | null;
}

export interface StudioSource {
  id: string;
  title?: string;
  author?: string | null;
  edition?: string | null;
  url?: string | null;
  rights_note?: string | null;
  source_kind?: string | null;
  reliability?: string | null;
  verification_status?: string;
}

export interface StudioView {
  work?: StudioWork | null;
  work_info?: Record<string, unknown> | null;
  versions: StudioVersion[];
  lines: StudioLine[];
  claims: StudioClaim[];
  citations: StudioCitation[];
  backgrounds: StudioBackground[];
  annotations: StudioAnnotation[];
  sources: StudioSource[];
  background_lines: { background_id: string; version_id: string; line_seq: number }[];
  claim_status_by_id: Record<string, string>;
  content_status_by_id: Record<string, string>;
  version_status_by_id: Record<string, string>;
  source_verification_by_id: Record<string, string>;
  coverage_rows?: unknown[];
  gap_report?: GapReport | null;
}

// ---------- 出处核查 ----------

export type LocatorState = 'MISSING' | 'PLACEHOLDER' | 'SET';

export interface SourceCitation {
  claim_id: string;
  claim_value?: string;
  claim_kind?: string;
  claim_status?: string;
  locator?: string | null;
  evidence_excerpt?: string | null;
  locator_state: LocatorState | string;
}

export interface Source {
  /** 契约写 id;Java mapper 里也可能叫 source_id,取用时用 sourceIdOf()。 */
  id?: string;
  source_id?: string;
  title?: string;
  author?: string | null;
  edition?: string | null;
  url?: string | null;
  rights_note?: string | null;
  source_kind?: string | null;
  reliability?: string | null;
  verification_status: string;
  citations: SourceCitation[];
}

export interface SourceFilters {
  verification_status?: string;
  limit?: number;
  offset?: number;
}

export interface LocatorInput {
  actor?: Actor;
  locator: string;
  evidence_excerpt?: string;
  note?: string;
}

export interface VerificationInput {
  actor?: Actor;
  decision: 'VERIFY' | 'REJECT';
  note?: string;
}

// ---------- 发布前检查 ----------

export type RuleStatus = 'PASS' | 'FAIL' | 'NOT_EVALUATED';
export type PrecheckVerdict = 'READY_FOR_HUMAN_PUBLISH' | 'BLOCKED' | 'INCOMPLETE';

export interface PrecheckRule {
  id: string;
  name: string;
  evaluation: 'DATA' | 'BUNDLE' | string;
  status: RuleStatus | string;
  details: string[];
}

export interface Precheck {
  work_id: string;
  evaluated_at: string;
  bundle: {
    state: 'EVALUATED' | 'NOT_AVAILABLE' | string;
    script_id?: string;
    script_version?: string;
    shape_failures?: string[];
  };
  rules: PrecheckRule[];
  verdict: PrecheckVerdict | string;
  note?: string;
}

export interface Readiness {
  status?: string;
  worker_configured?: boolean;
  reviewer_token_configured?: boolean;
  [key: string]: unknown;
}
