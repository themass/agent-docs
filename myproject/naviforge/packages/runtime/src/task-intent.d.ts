export type TaskIntent = 'page_read' | 'page_download' | 'media_extract' | 'script_authoring' | 'list_extract' | 'multi_hop_crawl' | 'research' | 'general' | 'list_detail' | 'denied';
export declare function isMediaTask(task: string): boolean;
export declare function resolveTaskIntent(task: string): TaskIntent;
export declare function intentPreflightSkill(intent: TaskIntent): string | undefined;
export declare function intentGuidanceNotes(intent: TaskIntent): string[];
