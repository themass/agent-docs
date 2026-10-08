export function traceLinesToMessages(lines) {
    return lines.map((line) => {
        if (line.startsWith('USER CORRECTION:'))
            return { role: 'user', content: line };
        if (line.startsWith('USER ANSWER:'))
            return { role: 'user', content: line };
        if (line.startsWith('FOLLOW-UP:'))
            return { role: 'user', content: line };
        if (line.includes(' fail '))
            return { role: 'tool', content: line };
        if (line.startsWith('ask:') || line.startsWith('done:')) {
            return { role: 'assistant', content: line };
        }
        return { role: 'tool', content: line };
    });
}
export function formatMessagesForPrompt(messages, limit = 8) {
    const recent = messages.slice(-limit);
    if (!recent.length)
        return '(none)';
    return recent.map((message) => `[${message.role}] ${message.content}`).join('\n');
}
