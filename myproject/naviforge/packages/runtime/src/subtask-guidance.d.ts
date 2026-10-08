/** Max parallel readonly leaves per spawn call (DeerFlow SubagentLimitMiddleware default). */
export declare const MAX_PARALLEL_SUBTASKS = 3;
export type ReadonlySubtaskSpec = {
    /** Short label for trace/UI (DeerFlow `description`). */
    title: string;
    /** Full isolated instructions (DeerFlow `prompt`). Child sees only this + user task line. */
    prompt: string;
    /** Optional explicit URLs to open or fetch. */
    urls?: string[];
    /** `fetch` = static text via fetch_text; `tab` = JS/rendered page via tabs_open+dom_read. */
    mode?: 'fetch' | 'tab';
};
export declare function briefFromSubtask(spec: ReadonlySubtaskSpec): string;
/** Accept legacy briefs[] or structured subtasks[] (DeerFlow-style title+prompt). */
export declare function normalizeSpawnBriefs(args: Record<string, unknown>): {
    briefs: string[];
} | {
    error: string;
};
/** Leaf readonly sub-agent system append. */
export declare const READONLY_CHILD_KERNEL_SECTION = "## \u53EA\u8BFB\u5B50 Agent\n\u4F60\u7531 Lead \u901A\u8FC7 system_spawn_readonly_tasks \u6D3E\u51FA\uFF1B\u6D88\u606F\u91CC\u53EA\u6709\u672C\u5B50\u4EFB\u52A1 brief\u3002\n\n\u226416 \u6B65\u5185\u5B8C\u6210\u5E76 system_done\u3002\u9759\u6001 URL \u2192 fetch_text\uFF1B\u9700 JS/\u64AD\u653E\u5668 \u2192 tabs open \u2192 browser_observe / network / PAGE SIGNALS\u3002\n\u7981\u6B62\uFF1ADOM \u5199\u3001browser_nav\u3001js\u3001\u5D4C\u5957 spawn\u3001system_ask_user\u3002\u8FD4\u56DE\u7ED3\u6784\u5316 JSON \u6216 bullet\uFF1B\u7F3A\u5B57\u6BB5\u8BF4\u660E shortfall\uFF0C\u52FF\u7F16\u9020\u3002";
export declare const SUBTASK_KERNEL_SECTION = "## \u59D4\u6D3E\uFF1A\u53EA\u8BFB\u5B50\u4EFB\u52A1\uFF08system_spawn_readonly_tasks\uFF09\n\n\u4F60\u662F **Lead**\uFF1A\u89C4\u5212\u3001\u59D4\u6D3E\u3001\u6C47\u603B\u3002\u5B50 Agent \u53EA\u505A\u72EC\u7ACB\u53EA\u8BFB\u7247\uFF1B\u6700\u7EC8 system_done \u7531\u4F60\u5199\u7528\u6237\u53EF\u89C1\u7ED3\u8BBA\uFF08\u5408\u5E76 children[]\uFF0C\u7981\u6B62\u88F8\u8D34\u65E5\u5FD7\uFF09\u3002\n\n**\u4F55\u65F6\u59D4\u6D3E** \u2014 2+ \u4E92\u4E0D\u4F9D\u8D56 URL\uFF1B\u6216 navigation:forbidden \u4F46\u8BE6\u60C5\u5728\u522B\u7684\u9875\uFF1B\u6216\u6279\u91CF\u53EA\u8BFB\u53EF\u5E76\u884C\u3002\n**\u81EA\u5DF1\u5B8C\u6210** \u2014 \u5355\u9875\u4E00\u6B21 fetch_text \u6216 browser_observe \u591F\uFF1B\u6709\u987A\u5E8F\u4F9D\u8D56\u5219\u5206\u6279 spawn\uFF1B\u5199 DOM/\u767B\u5F55/HITL \u7531\u7236 Agent \u505A\u3002\n\n**\u5E76\u884C**\uFF1A\u4E00\u6B21 spawn \u6700\u591A **3** \u6761 subtasks[]\u3002\u66F4\u591A\u5219\u591A\u8F6E spawn\uFF0C\u6BCF\u8F6E\u6C47\u603B\u518D\u7EE7\u7EED\u3002\n**\u7981\u6B62**\uFF1Anavigation:forbidden \u65F6\u7236 tab \u4E32\u884C\u6253\u5F00\u5217\u8868\u9879\uFF1B\u7528 spawn \u4EE3\u66FF\u3002\n\n**subtasks[]**\uFF1A\u6BCF\u9879 title + prompt + \u53EF\u9009 urls\u3001mode\uFF08fetch=\u9759\u6001 fetch_text\uFF0Ctab=tabs+observe/network\uFF09\u3002\n\u5B50 Agent \u53EA\u8BFB\uFF1A\u7981\u6B62\u5199 DOM\u3001\u5D4C\u5957 spawn\u3001system_ask_user\u3002";
export declare const PARALLEL_SUBTASK_GUIDANCE: readonly string[];
export declare const PARALLEL_SUBTASK_STATIC_URL_HINT = "GUIDANCE: \u5DF2\u77E5\u9759\u6001 document/API URL \u8BBE mode:fetch\uFF1B\u4EC5 JS \u6E32\u67D3\u9875\u7528 mode:tab\u3002";
