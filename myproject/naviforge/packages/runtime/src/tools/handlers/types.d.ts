import type { ToolCall, ToolResult } from '@naviforge/shared';
import type { RecordedDomAction } from '@naviforge/playbook';
import type { TraceRecord } from '@naviforge/session';
import type { AgentIo } from '../../agent-ctx.js';
import type { ModelDecision } from '../../failure.js';
import type { DomSnapshot } from '@naviforge/dom-plane';
export type ExecOut = {
    nextSnap: DomSnapshot;
    trace: string;
    recorded?: RecordedDomAction;
    terminal?: TraceRecord;
};
export type BuiltinContext = {
    decision: ModelDecision;
    action: ToolCall;
    ctx: AgentIo;
    snap: DomSnapshot;
    blockAsk: (question: string) => ExecOut | null;
};
export type BuiltinResult = ExecOut | {
    result: ToolResult;
    snap: DomSnapshot;
    recorded?: RecordedDomAction;
};
export type BuiltinHandler = (input: BuiltinContext) => Promise<BuiltinResult>;
export declare function str(value: unknown): string | null;
export declare function num(value: unknown): number | null;
