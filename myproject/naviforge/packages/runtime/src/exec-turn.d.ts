import type { DomPlane, DomSnapshot, SnapshotMode } from '@naviforge/dom-plane';
import type { ToolCall, ToolResult } from '@naviforge/shared';
import type { RecordedDomAction } from '@naviforge/playbook';
import type { TraceRecord } from '@naviforge/session';
import type { AgentIo } from './agent-ctx.js';
import type { ModelDecision } from './failure.js';
import { type RecoveryPlan } from './recovery.js';
import { isCspEvalError } from './run-limits.js';
import { formatExtractContentTrace, formatExtractDomTrace, formatReadPageTrace, formatToolTrace, READ_PAGE_TRACE_CHARS } from './tools/format-tool-trace.js';
export { isCspEvalError };
export { formatExtractContentTrace, formatExtractDomTrace, formatReadPageTrace, formatToolTrace, READ_PAGE_TRACE_CHARS, };
export declare function normalizeScrollArgs(args: Record<string, unknown>): {
    to?: 'top' | 'bottom' | 'y';
    y?: number;
    direction?: 'up' | 'down';
    amount?: number;
};
export declare function parseSnapshotMode(value: unknown): SnapshotMode | undefined;
export declare function snapshotWithRetry(dom: DomPlane): Promise<ToolResult<DomSnapshot>>;
type ExecOut = {
    nextSnap: DomSnapshot;
    trace: string;
    recorded?: RecordedDomAction;
    terminal?: TraceRecord;
    recovery?: RecoveryPlan;
    toolResult?: TraceRecord;
};
/** Host meta-tools — always available even under Skill hard allowlist. */
export declare function isToolAllowed(tool: string, allowedTools?: ReadonlySet<string>): boolean;
export declare function executeQualifiedTool(decision: ModelDecision, action: ToolCall, ctx: AgentIo, snap: DomSnapshot, blockAsk: (question: string) => ExecOut | null): Promise<{
    kind: 'builtin';
    out: ExecOut;
} | {
    kind: 'result';
    result: ToolResult;
    snap: DomSnapshot;
    recorded?: RecordedDomAction;
}>;
export declare function execTurn(decision: ModelDecision, ctx: AgentIo): Promise<ExecOut>;
