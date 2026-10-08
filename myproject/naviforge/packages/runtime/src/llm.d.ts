import type { OpenAiFunctionTool } from '@naviforge/shared';
/** OpenAI-compatible `reasoning_effort`. Omit on the wire when thinking is off. */
export type ReasoningEffort = 'low' | 'medium' | 'high' | 'xhigh';
export type LlmConfig = {
    baseURL: string;
    apiKey: string;
    model: string;
    reasoningEffort?: ReasoningEffort;
};
/** OpenAI-compatible usage; absent when the gateway omits it. */
export type LlmUsage = {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
};
export type LlmToolCall = {
    name: string;
    arguments: Record<string, unknown>;
};
export type ChatCompletionResult = {
    /** `message.content` — empty when the model only emitted tool_calls or reasoning. */
    content: string;
    /** `message.reasoning_content` when the gateway sends it (kept separate from content). */
    reasoning?: string;
    usage?: LlmUsage;
    toolCalls?: LlmToolCall[];
};
export type ChatCompletionOptions = {
    signal?: AbortSignal;
    imageDataUrl?: string;
    tools?: OpenAiFunctionTool[];
};
/** OpenAI-compatible chat.completions — prefers native tools[] / tool_calls when provided. */
export declare function chatCompletion(config: LlmConfig, system: string, user: string, opts?: ChatCompletionOptions): Promise<ChatCompletionResult>;
