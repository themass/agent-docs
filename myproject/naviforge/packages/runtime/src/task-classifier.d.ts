import type { ThreadReuse } from '@naviforge/session';
import { isCatalogCrawlTask, isSiteCatalogSopTask, parseCatalogCrawlSpec } from './catalog-crawl/spec.js';
export type TaskMode = 'in_page' | 'research' | 'general' | 'list_detail';
/** Off-page research: web_search → open sources → compare. */
export declare function isResearchTask(task: string): boolean;
/** Knowledge-style ask without DOM ops on the current shell page. */
export declare function isGeneralTask(task: string): boolean;
/** Many static document URLs (e.g. repo tree listing) — prefer fetch_text batches in spawn briefs. */
export declare function isBulkMdCatalogTask(task: string): boolean;
export { isCatalogCrawlTask, isSiteCatalogSopTask, parseCatalogCrawlSpec };
export declare function resolveTaskMode(task: string): TaskMode;
/** 「读当前页」：总结 / 介绍 / 是什么 / 干什么 — not list→detail or web search. */
export declare function isPageReadTask(task: string): boolean;
/** Open a list item only when the user named a row / story / detail page. */
export declare function shouldHintListThenDetail(task: string): boolean;
/** A "top N" ask, plus whether the user wanted the page marked or just the data. */
export declare function requestedList(task: string): {
    n: number;
    mark: boolean;
} | null;
export declare function requestedTopN(task: string): number | null;
export declare function urlsMatchForReuse(a: string, b: string): boolean;
export declare function bareSkillId(id: string): string;
/** @deprecated Use isSiteCatalogSopTask — parallel fan-out is phase 3 of catalog SOP. */
export declare function shouldHintParallelSubtasks(task: string): boolean;
export declare function parallelSubtaskGuidanceNotes(task: string): string[];
/** Deterministic GUIDANCE notes before the model loop (shared by TaskHintHook). */
export declare function taskGuidanceNotes(task: string, reuse: ThreadReuse): string[];
