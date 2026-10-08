/** Model-facing reply locale for system_done / ask_user / Progress. Task text wins over UI locale. */
export declare function resolveReplyLanguage(task: string, uiLocale?: string): string;
export declare function formatReplyLanguageBlock(replyLanguage: string): string;
