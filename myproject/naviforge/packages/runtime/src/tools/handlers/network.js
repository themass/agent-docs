import { formatMediaHints, mediaHintsFromUrls, resolveHlsPlaylist } from '@naviforge/media-plane';
import { resolveBuiltinToolCall } from '../builtin-tool-resolver.js';
import { handlerPrelude } from './prelude.js';
import { num, str } from './types.js';
const networkDigest = async (input) => {
    const { network, action } = handlerPrelude(input);
    let snap = input.snap;
    if (!network) {
        return {
            result: {
                ok: false,
                error: { code: 'no_network', message: 'network plane disabled', recoverable: false },
            },
            snap,
        };
    }
    return { result: await network.digest(num(action.arguments.limit) ?? 12), snap };
};
const networkList = async (input) => {
    const { network, action } = handlerPrelude(input);
    let snap = input.snap;
    if (!network) {
        return {
            result: {
                ok: false,
                error: { code: 'no_network', message: 'network plane disabled', recoverable: false },
            },
            snap,
        };
    }
    return {
        result: await network.list({
            urlIncludes: str(action.arguments.urlIncludes) ?? undefined,
            method: str(action.arguments.method) ?? undefined,
            limit: num(action.arguments.limit) ?? 20,
        }),
        snap,
    };
};
async function resolveNetworkBodyId(network, args) {
    const id = str(args.id);
    if (id)
        return id;
    const urlIncludes = str(args.urlIncludes);
    const urlRegex = str(args.urlRegex);
    const method = str(args.method);
    if (!urlIncludes && !urlRegex)
        return undefined;
    const listed = await network.list({
        urlIncludes: urlIncludes ?? undefined,
        method: method ?? undefined,
        limit: num(args.limit) ?? 40,
    });
    if (!listed.ok || !Array.isArray(listed.data) || !listed.data.length)
        return undefined;
    let events = listed.data;
    if (urlRegex) {
        try {
            const re = new RegExp(urlRegex);
            events = events.filter((event) => re.test(event.url));
        }
        catch {
            return undefined;
        }
    }
    const status = num(args.status);
    const matches = events.filter((event) => {
        if (status != null && event.status !== status)
            return false;
        if (urlIncludes && !event.url.includes(urlIncludes))
            return false;
        if (urlRegex) {
            try {
                if (!new RegExp(urlRegex).test(event.url))
                    return false;
            }
            catch {
                return false;
            }
        }
        if (method && event.method.toUpperCase() !== method.toUpperCase())
            return false;
        return true;
    });
    return (matches.length ? matches[matches.length - 1] : events[events.length - 1])?.id;
}
const networkGetBody = async (input) => {
    const { network, action } = handlerPrelude(input);
    let snap = input.snap;
    if (!network?.getBody) {
        return {
            result: {
                ok: false,
                error: {
                    code: 'no_body',
                    message: 'response body capture disabled — enable in Settings → Privacy',
                    recoverable: false,
                },
            },
            snap,
        };
    }
    const id = network ? await resolveNetworkBodyId(network, action.arguments) : undefined;
    if (!id) {
        return {
            result: {
                ok: false,
                error: {
                    code: 'bad_args',
                    message: 'id required (or urlIncludes matching a captured request)',
                    recoverable: true,
                },
            },
            snap,
        };
    }
    return { result: await network.getBody(id), snap };
};
const networkMediaHints = async (input) => {
    const { network, action } = handlerPrelude(input);
    let snap = input.snap;
    if (!network) {
        return {
            result: {
                ok: false,
                error: { code: 'no_network', message: 'network plane disabled', recoverable: false },
            },
            snap,
        };
    }
    const listed = await network.list({ limit: num(action.arguments.limit) ?? 80 });
    if (!listed.ok)
        return { result: listed, snap };
    const hints = mediaHintsFromUrls(listed.data);
    return { result: { ok: true, data: { hints, text: formatMediaHints(hints) } }, snap };
};
const networkResolveHls = async (input) => {
    const { network, action } = handlerPrelude(input);
    let snap = input.snap;
    let result;
    if (!network) {
        result = {
            ok: false,
            error: { code: 'no_network', message: 'network plane disabled', recoverable: false },
        };
        return { result, snap };
    }
    const id = str(action.arguments.id);
    const inlineText = str(action.arguments.text);
    let baseUrl = str(action.arguments.baseUrl) ?? str(action.arguments.url) ?? undefined;
    let text = inlineText;
    if (!text && id) {
        if (!network.getBody) {
            result = {
                ok: false,
                error: {
                    code: 'no_body',
                    message: 'enable captureNetworkBodies and capture m3u8 response first',
                    recoverable: true,
                },
            };
            return { result, snap };
        }
        const body = await network.getBody(id);
        if (!body.ok)
            return { result: body, snap };
        text = body.data.body;
        if (!baseUrl) {
            const listed = await network.list({ limit: 100 });
            if (listed.ok)
                baseUrl = listed.data.find((event) => event.id === id)?.url;
        }
    }
    if (!text) {
        result = {
            ok: false,
            error: { code: 'bad_args', message: 'id or text required', recoverable: true },
        };
        return { result, snap };
    }
    return { result: { ok: true, data: resolveHlsPlaylist(text, baseUrl) }, snap };
};
const networkWait = async (input) => {
    const { network, action } = handlerPrelude(input);
    let snap = input.snap;
    if (!network) {
        return {
            result: {
                ok: false,
                error: { code: 'no_network', message: 'network plane disabled', recoverable: false },
            },
            snap,
        };
    }
    const opts = {
        urlIncludes: str(action.arguments.urlIncludes) ?? undefined,
        urlRegex: str(action.arguments.urlRegex) ?? undefined,
        method: str(action.arguments.method) ?? undefined,
        status: num(action.arguments.status) ?? undefined,
        timeoutMs: num(action.arguments.timeout_ms) ?? 10000,
    };
    const result = await network.wait(opts);
    if (!result.ok && result.error.code === 'cancelled') {
        throw new DOMException('Network wait cancelled', 'AbortError');
    }
    return { result, snap };
};
const networkIntercept = async (input) => {
    const { network, action, allowNetworkIntercept } = handlerPrelude(input);
    let snap = input.snap;
    let result;
    let recorded;
    if (!network?.setIntercepts) {
        result = {
            ok: false,
            error: { code: 'no_network', message: 'network intercept unsupported', recoverable: false },
        };
        return { result, snap, recorded };
    }
    if (!allowNetworkIntercept) {
        result = {
            ok: false,
            error: {
                code: 'intercept_denied',
                message: 'network intercept blocked — enable allowNetworkIntercept in Settings',
                recoverable: false,
            },
        };
        return { result, snap, recorded };
    }
    const rawRules = action.arguments.rules;
    if (!Array.isArray(rawRules)) {
        result = {
            ok: false,
            error: { code: 'bad_args', message: 'rules array required', recoverable: true },
        };
        return { result, snap, recorded };
    }
    const rules = rawRules
        .filter((item) => typeof item === 'object' && item !== null)
        .map((item, index) => ({
        id: typeof item.id === 'string' ? item.id : `rule-${index + 1}`,
        urlIncludes: typeof item.urlIncludes === 'string' ? item.urlIncludes : undefined,
        urlRegex: typeof item.urlRegex === 'string' ? item.urlRegex : undefined,
        method: typeof item.method === 'string' ? item.method : undefined,
        action: String(item.action ?? 'block'),
        status: typeof item.status === 'number' ? item.status : undefined,
        body: typeof item.body === 'string' ? item.body : undefined,
        responseHeaders: typeof item.responseHeaders === 'object' && item.responseHeaders
            ? item.responseHeaders
            : undefined,
        forwardUrl: typeof item.forwardUrl === 'string' ? item.forwardUrl : undefined,
        setHeaders: typeof item.setHeaders === 'object' && item.setHeaders
            ? item.setHeaders
            : undefined,
        removeHeaders: Array.isArray(item.removeHeaders)
            ? item.removeHeaders.filter((value) => typeof value === 'string')
            : undefined,
    }))
        .filter((rule) => ['block', 'mock', 'forward', 'rewrite'].includes(rule.action));
    result = await network.setIntercepts(rules);
    return { result, snap, recorded };
};
const networkClearIntercepts = async (input) => {
    const { network, allowNetworkIntercept } = handlerPrelude(input);
    let snap = input.snap;
    let result;
    if (!network?.clearIntercepts) {
        result = {
            ok: false,
            error: { code: 'no_network', message: 'clearIntercepts unsupported', recoverable: false },
        };
        return { result, snap };
    }
    if (!allowNetworkIntercept) {
        result = {
            ok: false,
            error: {
                code: 'intercept_denied',
                message: 'network intercept blocked — enable allowNetworkIntercept in Settings',
                recoverable: false,
            },
        };
        return { result, snap };
    }
    result = await network.clearIntercepts();
    return { result, snap };
};
export const networkHandlers = {
    network_digest: networkDigest,
    network_list: networkList,
    network_get_body: networkGetBody,
    network_media_hints: networkMediaHints,
    network_resolve_hls: networkResolveHls,
    network_wait: networkWait,
    network_intercept: networkIntercept,
    network_clear_intercepts: networkClearIntercepts,
};
export const networkCatalogHandler = async (input) => {
    const mode = input.action.arguments.mode;
    if (typeof mode !== 'string') {
        return {
            result: {
                ok: false,
                error: {
                    code: 'bad_args',
                    message: 'network mode required (digest|list|body|media|hls|wait)',
                    recoverable: true,
                },
            },
            snap: input.snap,
        };
    }
    const resolved = resolveBuiltinToolCall('network_read', input.action.arguments);
    const handler = networkHandlers[resolved.tool];
    if (!handler) {
        return {
            result: {
                ok: false,
                error: { code: 'bad_args', message: `unknown network mode: ${mode}`, recoverable: true },
            },
            snap: input.snap,
        };
    }
    return handler({
        ...input,
        action: { ...input.action, tool: resolved.tool, arguments: resolved.arguments },
    });
};
