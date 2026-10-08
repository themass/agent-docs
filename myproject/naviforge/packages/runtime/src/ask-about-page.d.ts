import { type LlmConfig, type LlmUsage } from './llm.js';
export declare const PAGE_ASK_SYSTEM = "\u4F60\u662F\u770B\u56FE\u52A9\u624B\u3002\u7528\u6237\u63D0\u4F9B\u4E86\u4E00\u5F20\u56FE\u7247\uFF08\u9875\u9762\u622A\u56FE\u3001\u5DE5\u4F5C\u533A\u622A\u56FE\u6216\u672C\u5730\u4E0A\u4F20\uFF09\uFF0C\u4EE5\u53CA\u53EF\u9009\u7684\u9875\u9762\u6587\u672C\u6458\u5F55\u3002\n\u6839\u636E\u8FD9\u4E9B\u8BC1\u636E\u56DE\u7B54\u7528\u6237\u95EE\u9898\u3002\n- \u4E0D\u8981\u7F16\u9020\u56FE\u4E0A\u770B\u4E0D\u5230\u7684\u5185\u5BB9\uFF1B\u770B\u4E0D\u6E05\u6216\u6458\u5F55\u4E0D\u8DB3\u65F6\u5982\u5B9E\u8BF4\u660E\u3002\n- \u4F18\u5148\u4F9D\u636E\u56FE\u7247\u4E2D\u7684\u53EF\u89C1\u4FE1\u606F\uFF1B\u6587\u672C\u6458\u5F55\u4EC5\u4F5C\u8865\u5145\u3002\n- \u56DE\u7B54\u7B80\u6D01\u3001\u53EF\u7528\u6761\u76EE\u6216\u77ED\u6BB5\u843D\uFF0C\u4E0D\u8981\u5C55\u5F00\u6210\u64CD\u4F5C\u8BA1\u5212\u3002\n- \u5FC5\u987B\u6070\u597D\u8C03\u7528\u4E00\u6B21 system_done\uFF0C\u5E76\u5C06\u7B54\u6848\u653E\u5728 result\u3002";
export declare const PAGE_TEXT_SYSTEM = "\u4F60\u662F\u9875\u9762\u7406\u89E3\u52A9\u624B\u3002\u7528\u6237\u63D0\u4F9B\u4E86\u5F53\u524D\u6D4F\u89C8\u5668\u9875\u9762\u7684\u6B63\u6587\u6458\u5F55\uFF0C\u6CA1\u6709\u622A\u56FE\u3002\n\u6839\u636E\u6B63\u6587\u56DE\u7B54\u7528\u6237\u95EE\u9898\u3002\n- \u4E0D\u8981\u7F16\u9020\u6B63\u6587\u91CC\u6CA1\u6709\u7684\u5185\u5BB9\uFF1B\u6458\u5F55\u4E0D\u8DB3\u65F6\u5982\u5B9E\u8BF4\u660E\u3002\n- \u56DE\u7B54\u7B80\u6D01\u3001\u53EF\u7528\u6761\u76EE\u6216\u77ED\u6BB5\u843D\uFF0C\u4E0D\u8981\u5C55\u5F00\u6210\u64CD\u4F5C\u8BA1\u5212\u3002\n- \u5FC5\u987B\u6070\u597D\u8C03\u7528\u4E00\u6B21 system_done\uFF0C\u5E76\u5C06\u7B54\u6848\u653E\u5728 result\u3002";
export declare const PAGE_SUMMARIZE_QUESTION = "\u603B\u7ED3\u672C\u9875\uFF1A\u8FD9\u662F\u4EC0\u4E48\u3001\u9002\u5408\u8C01\u3001\u5173\u952E\u8981\u70B9\u3002\u6B63\u6587\u4E0D\u8DB3\u65F6\u5982\u5B9E\u8BF4\u660E\uFF0C\u4E0D\u8981\u7F16\u9020\u3002";
export declare function explainPickedQuestion(label: string): string;
export declare function resolveOneShotQuestion(kind: 'page' | 'summarize' | 'explain', typed: string, pickedLabel?: string): string;
export declare function pickedElementExcerpt(element: {
    tag?: string;
    title?: string;
    text?: string;
    selector?: string;
}): string;
export type AskAboutPageInput = {
    llm: LlmConfig;
    question: string;
    /** Viewport screenshot. Omit for text-only one-shots (summarize). */
    imageDataUrl?: string;
    url?: string;
    title?: string;
    /** Compact DOM / text excerpt — required when `imageDataUrl` is omitted. */
    textExcerpt?: string;
    signal?: AbortSignal;
};
export type AskAboutPageResult = {
    answer: string;
    usage?: LlmUsage;
};
/** One-shot page Q&A — not an agent tool loop. Screenshot optional when excerpt is present. */
export declare function askAboutPage(input: AskAboutPageInput): Promise<AskAboutPageResult>;
export declare const OCR_SYSTEM = "\u4F60\u662F\u6587\u5B57\u8BC6\u522B\u52A9\u624B\u3002\u7528\u6237\u63D0\u4F9B\u4E86\u4E00\u5F20\u7F51\u9875\u9009\u533A\u622A\u56FE\u3002\n\u53EA\u8F6C\u5F55\u56FE\u4E2D\u53EF\u89C1\u6587\u5B57\uFF0C\u4FDD\u6301\u539F\u6709\u6362\u884C\u3002\n\u770B\u4E0D\u6E05\u7684\u5B57\u5199 [\u770B\u4E0D\u6E05]\u3002\n\u4E0D\u8981\u603B\u7ED3\u3001\u7FFB\u8BD1\u3001\u89E3\u91CA\uFF0C\u4E5F\u4E0D\u8981\u8865\u5168\u56FE\u4E0A\u6CA1\u6709\u7684\u5B57\u3002\n\u5FC5\u987B\u6070\u597D\u8C03\u7528\u4E00\u6B21 system_done\uFF0C\u5E76\u5C06\u8F6C\u5F55\u653E\u5728 result\u3002";
export type OcrImageInput = {
    llm: LlmConfig;
    imageDataUrl: string;
    signal?: AbortSignal;
};
export type OcrImageResult = {
    text: string;
    usage?: LlmUsage;
};
/** One-shot screenshot transcription — not an agent tool loop. */
export declare function ocrImage(input: OcrImageInput): Promise<OcrImageResult>;
