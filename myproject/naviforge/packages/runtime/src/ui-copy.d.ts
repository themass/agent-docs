/** User-visible runtime copy. UI chrome lives in the extension catalogs.
 *  Adding a language: append UI_LOCALES + a Copy block here (runtime cannot import the extension).
 */
export declare const UI_LOCALES: readonly ["en", "zh-CN", "es"];
export type UiLocale = (typeof UI_LOCALES)[number];
export declare function resolveUiLocale(raw?: string): UiLocale;
type Copy = {
    acting: string;
    actingSkill: string;
    actingMcp: string;
    actingAsk: string;
    actingDone: string;
    actingSearch: string;
    actingSearchEmpty: string;
    actingSub: string;
    actingTool: string;
    timeout: string;
    tokenBudget: string;
    privacy: Record<string, string>;
    hardDeny: string;
    hardDenySearch: string;
    sameFailureNav: string;
    sameFailure: string;
    transportAsk: string;
    actionLoop: string;
};
export declare function uiCopy(locale?: string): Copy;
export declare function fillCopy(template: string, vars: Record<string, string | number>): string;
export {};
