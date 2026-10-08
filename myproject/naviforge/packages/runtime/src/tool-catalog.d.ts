import type { TraceRecordPayload } from '@naviforge/session';
import type { OpenAiFunctionTool } from '@naviforge/shared';
export type ToolCatalogEntry = TraceRecordPayload['run.tools']['catalog'][number];
/** Snapshot of the tools[] block sent to the model — audit/UI only. */
export declare function buildToolCatalog(tools: readonly OpenAiFunctionTool[]): ToolCatalogEntry[];
