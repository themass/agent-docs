/** Primary user-facing outcome for one run (mutually exclusive narrative). */
export type Deliverable = 'script' | 'data' | 'media' | 'summary' | 'research' | 'general';
export declare function isScriptDeliverableTask(task: string): boolean;
export declare function resolveDeliverable(task: string): Deliverable;
/**
 * Thread-aware resolution: once a deliverable is established for a thread,
 * keep it across follow-up turns unless the new message carries a strong,
 * specific signal for a *different* deliverable. A generic follow-up like
 * "继续" / "上面的内容不全，请重新抓取一下" / "？？" must not reclassify the
 * task narrative — it should continue serving the deliverable already in
 * flight. New threads (no `previous`) fall back to plain resolveDeliverable.
 */
export declare function resolveDeliverableWithContinuity(task: string, previous?: Deliverable): Deliverable;
export declare const SCRAPER_SKILL_ID = "persist";
export declare const SCRAPER_SKILL_INLINE = "# persist (script inline)\nPhase 0: Read PAGE STATE + PAGE FRICTION. role=login \u2192 system_ask_user\uFF08\u516C\u5F00\u5165\u53E3\u6216\u624B\u52A8\u767B\u5F55\uFF09\uFF0C\u52FF\u7A7A\u8F6C\u8BFB\u53D6\u3002\nPhase 1: browser_observe action=read mode=list \u6216 discover \u6458\u8981 \u2192 \u8BB0\u5F55\u5206\u7C7B URL \u6A21\u5F0F\u3001\u5206\u9875\u53C2\u6570\u3002\nPhase 2: workspace action=script_save \u5199\u51FA Python\uFF08requests/httpx + \u53EF\u914D\u7F6E pages \u9ED8\u8BA4 1\uFF09\u3002\nPhase 3: system_done \u9644\u811A\u672C path + \u91C7\u6837\u5230\u7684 URL \u6A21\u5F0F\uFF1B\u7F3A Network/\u767B\u5F55\u5199 shortfall\u3002";
export declare function deliverablePreflightSkill(deliverable: Deliverable): string | undefined;
export declare function deliverablePlanMilestone(deliverable: Deliverable): string;
/** One narrative block per run (replaces stacked GUIDANCE for locked deliverables). */
export declare function deliverableGuidanceNotes(deliverable: Deliverable): string[];
/** Phase A/B: skip heavy catalog preflight for script deliverable. */
export declare function shouldRunCatalogPreflight(task: string, deliverable: Deliverable): boolean;
export declare function shouldRunMediaRecipe(deliverable: Deliverable, intent: string): boolean;
/** Summary text must not downgrade script/data deliverables from the user's anchor ask. */
export declare function lockDeliverable(anchorTask: string, executionTask: string): Deliverable;
export declare function shouldEmitSiteCatalogGuidance(task: string, deliverable: Deliverable): boolean;
