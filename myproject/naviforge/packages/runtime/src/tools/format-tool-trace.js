import { sanitizeUntrustedText } from '@naviforge/shared';
import { formatWebSearchTrace } from '../search-plane.js';
import { formatFetchTextTrace } from '../fetch-plane.js';
import { WORKING_SET } from '../working-set.js';
export const READ_PAGE_TRACE_CHARS = WORKING_SET.evidenceChars;
/** GitHub REST contents listing or JSON-formatter page — extract file names + raw URLs. */
export function extractGithubContentsListing(text) {
    const names = [...text.matchAll(/"name"\s*:\s*"(20\d{6}\.md)"/g)].map((match) => match[1]);
    if (!names.length)
        return null;
    const rawUrls = [
        ...text.matchAll(/"download_url"\s*:\s*"(https:\/\/raw\.githubusercontent\.com\/[^"]+\.md)"/g),
    ].map((match) => match[1]);
    return { names, rawUrls };
}
export function formatGithubContentsEvidence(text) {
    const listing = extractGithubContentsListing(text);
    if (!listing)
        return null;
    const base = listing.rawUrls[0]?.replace(/\/\d{8}\.md$/, '') ??
        'https://raw.githubusercontent.com/OpenGithubs/github-daily-rank/main/2026/08';
    return `GitHub directory listing (${listing.names.length} files): ${listing.names.join(', ')}; raw base ${base}`;
}
export function formatReadPageTrace(data) {
    const rec = (data ?? {});
    const text = typeof rec.text === 'string'
        ? sanitizeUntrustedText(rec.text, { maxChars: READ_PAGE_TRACE_CHARS })
        : '';
    const catalog = formatGithubContentsEvidence(text);
    if (catalog)
        return `dom_read body ok ${catalog}`;
    const excerpt = text.length > READ_PAGE_TRACE_CHARS ? `${text.slice(0, READ_PAGE_TRACE_CHARS)}\n… (truncated)` : text;
    return `dom_read body ok source=${typeof rec.source === 'string' ? rec.source : ''} truncated=${rec.truncated === true} title=${typeof rec.title === 'string' ? rec.title : ''} url=${typeof rec.url === 'string' ? rec.url : ''}\n${excerpt}`;
}
export function formatExtractDomTrace(data) {
    const rec = (data ?? {});
    const items = Array.isArray(rec.items) ? rec.items : [];
    const lines = items
        .filter((item) => !!item && typeof item === 'object')
        .filter((item) => typeof item.href === 'string' || item.kind === 'link')
        .slice(0, 30)
        .map((item) => {
        const href = typeof item.href === 'string' ? item.href : '(no href)';
        return `[${item.index ?? '?'}] ${String(item.title ?? '')} ${href}`.trim();
    });
    return `dom_extract_dom ok n=${items.length} title=${typeof rec.title === 'string' ? rec.title : ''} url=${typeof rec.url === 'string' ? rec.url : ''}\n${lines.join('\n')}`.slice(0, 4_000);
}
export function formatExtractContentTrace(data) {
    const rec = (data ?? {});
    const items = Array.isArray(rec.items) ? rec.items : [];
    const lines = items
        .filter((item) => !!item && typeof item === 'object')
        .slice(0, 12)
        .map((item, index) => {
        const title = typeof item.title === 'string' ? item.title : '';
        const url = typeof item.url === 'string' ? item.url : '';
        return `${index + 1}. ${title}${url ? ` ${url}` : ''}`.trim();
    });
    const shortfall = typeof rec.shortfall === 'string' ? `\nshortfall=${rec.shortfall}` : '';
    return `dom_read list ok n=${items.length}${shortfall}\n${lines.join('\n')}`.slice(0, 4_000);
}
const TOOL_TRACE_FORMATTERS = {
    skill_load: (data) => `skill_load ok ${JSON.stringify(data).slice(0, 400)}`,
    dom_read: (data, args) => {
        const mode = typeof args?.mode === 'string' ? args.mode : 'body';
        if (mode === 'list')
            return formatExtractContentTrace(data);
        if (mode === 'dom')
            return formatExtractDomTrace(data);
        if (mode === 'markdown')
            return `dom_read markdown ok ${JSON.stringify(data).slice(0, 200)}`;
        return formatReadPageTrace(data);
    },
    dom_read_page: (data) => formatReadPageTrace(data),
    dom_extract_dom: (data) => formatExtractDomTrace(data),
    dom_extract_content: (data) => formatExtractContentTrace(data),
    web_search: (data) => formatWebSearchTrace(data),
    fetch_text: (data) => formatFetchTextTrace(data),
    dom_execute_js: (data) => {
        const rec = (data ?? {});
        return `dom_execute_js ok ${JSON.stringify(rec.result ?? null).slice(0, 800)}`;
    },
    workspace_glob: (data) => {
        const rec = (data ?? {});
        return `workspace_glob ok n=${rec.n ?? 0} ${rec.pattern ?? ''}`;
    },
    workspace_grep: (data) => {
        const rec = (data ?? {});
        return `workspace_grep ok n=${rec.n ?? 0}`;
    },
    workspace: (data) => {
        const rec = (data ?? {});
        if (typeof rec.path === 'string')
            return `workspace ok path=${rec.path}`;
        if (typeof rec.pattern === 'string')
            return `workspace ok pattern=${rec.pattern} n=${rec.n ?? 0}`;
        return 'workspace ok';
    },
    system_spawn_readonly_tasks: (data) => {
        const rec = (data ?? {});
        const children = Array.isArray(rec.children) ? rec.children : [];
        if (!children.length)
            return `system_spawn_readonly_tasks ok=${rec.ok === true}`;
        return children
            .map((child, index) => {
            const body = String(child.result ?? '').replace(/\s+/g, ' ').slice(0, 600);
            return `child${index + 1} ${child.status ?? 'unknown'}: ${body}`;
        })
            .join('\n');
    },
};
function workspaceInternalTrace(tool, data) {
    const rec = (data ?? {});
    return rec.path ? `${tool} ok path=${rec.path}` : `${tool} ok`;
}
/** Single entry for successful tool trace lines in execTurn and hooks. */
export function formatToolTrace(tool, data, args) {
    const formatter = TOOL_TRACE_FORMATTERS[tool];
    if (formatter)
        return formatter(data, args);
    if (tool.startsWith('workspace_'))
        return workspaceInternalTrace(tool, data);
    return `${tool} ok ${JSON.stringify(data).slice(0, 200)}`;
}
