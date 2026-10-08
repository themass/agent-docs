/** Structured turn messages for prompt compilation (pi-style, lightweight). */
export type TurnMessage = {
    role: 'user' | 'assistant' | 'tool' | 'system';
    content: string;
};
export declare function traceLinesToMessages(lines: string[]): TurnMessage[];
export declare function formatMessagesForPrompt(messages: TurnMessage[], limit?: number): string;
