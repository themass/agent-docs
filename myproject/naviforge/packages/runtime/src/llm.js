function parseUsage(raw) {
    if (!raw || typeof raw !== 'object')
        return undefined;
    const u = raw;
    const prompt = Number(u.prompt_tokens ?? u.input_tokens ?? 0);
    const completion = Number(u.completion_tokens ?? u.output_tokens ?? 0);
    const total = Number(u.total_tokens ?? prompt + completion);
    if (![prompt, completion, total].every((n) => Number.isFinite(n)))
        return undefined;
    if (prompt === 0 && completion === 0 && total === 0)
        return undefined;
    return { promptTokens: prompt, completionTokens: completion, totalTokens: total || prompt + completion };
}
function parseToolCalls(message) {
    const calls = message.tool_calls;
    if (!Array.isArray(calls) || !calls.length)
        return undefined;
    const out = [];
    for (const call of calls) {
        const name = call.function?.name?.trim() ?? '';
        let args = {};
        const raw = call.function?.arguments;
        if (typeof raw === 'string' && raw.trim()) {
            try {
                const parsed = JSON.parse(raw);
                if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
                    args = parsed;
                }
            }
            catch {
                args = { _raw: raw };
            }
        }
        out.push({ name, arguments: args });
    }
    return out;
}
function toolChoiceForRequest(config) {
    if (config.reasoningEffort)
        return 'auto';
    const model = config.model.toLowerCase();
    // DeepSeek reasoner / V4: thinking on by default; rejects tool_choice=required (vendor quirk).
    if (/deepseek[-_]?(reasoner|v4|r1)/.test(model) || model.startsWith('deepseek-v4'))
        return 'auto';
    return 'required';
}
/** Some gateways (e.g. Kimi/Moonshot) reject temperature≠1. */
function temperatureForRequest(config) {
    const model = config.model.toLowerCase();
    if (/kimi|moonshot/.test(model))
        return 1;
    return 0;
}
function temperatureRetryAllowed(errBody) {
    return /invalid temperature/i.test(errBody) && /only\s*1/i.test(errBody);
}
function buildChatBody(config, system, userMessage, opts, temperature) {
    const body = {
        model: config.model,
        temperature,
        messages: [{ role: 'system', content: system }, userMessage],
    };
    if (opts?.tools?.length) {
        body.tools = opts.tools;
        body.tool_choice = toolChoiceForRequest(config);
    }
    if (config.reasoningEffort)
        body.reasoning_effort = config.reasoningEffort;
    return body;
}
/** OpenAI-compatible chat.completions — prefers native tools[] / tool_calls when provided. */
export async function chatCompletion(config, system, user, opts) {
    const base = config.baseURL.replace(/\/$/, '');
    const userMessage = opts?.imageDataUrl
        ? {
            role: 'user',
            content: [
                { type: 'text', text: user },
                { type: 'image_url', image_url: { url: opts.imageDataUrl } },
            ],
        }
        : { role: 'user', content: user };
    const timeoutMs = 120_000; // ponytail: single ceiling; raise if your gateway is slower
    const timeoutSignal = AbortSignal.timeout(timeoutMs);
    const signal = opts?.signal;
    const requestSignal = signal != null && typeof AbortSignal.any === 'function'
        ? AbortSignal.any([signal, timeoutSignal])
        : signal ?? timeoutSignal;
    const url = `${base}/chat/completions`;
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${config.apiKey}`,
    };
    let temperature = temperatureForRequest(config);
    let body = buildChatBody(config, system, userMessage, opts, temperature);
    let res = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: requestSignal,
    });
    if (!res.ok) {
        const errBody = await res.text().catch(() => '');
        if (temperature !== 1 && res.status === 400 && temperatureRetryAllowed(errBody)) {
            temperature = 1;
            body = buildChatBody(config, system, userMessage, opts, temperature);
            res = await fetch(url, {
                method: 'POST',
                headers,
                body: JSON.stringify(body),
                signal: requestSignal,
            });
            if (!res.ok) {
                const retryErr = await res.text().catch(() => '');
                throw new Error(`LLM HTTP ${res.status}: ${retryErr.slice(0, 400)}`);
            }
        }
        else {
            throw new Error(`LLM HTTP ${res.status}: ${errBody.slice(0, 400)}`);
        }
    }
    const json = (await res.json());
    const message = json.choices?.[0]?.message;
    const toolCalls = message ? parseToolCalls(message) : undefined;
    const content = (message?.content ?? '').trim();
    const reasoning = (message?.reasoning_content ?? '').trim() || undefined;
    return {
        content,
        reasoning,
        usage: parseUsage(json.usage),
        toolCalls,
    };
}
