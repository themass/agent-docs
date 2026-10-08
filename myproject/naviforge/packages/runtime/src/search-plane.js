export function formatWebSearchTrace(data) {
    const rec = (data ?? {});
    const results = Array.isArray(rec.results) ? rec.results : [];
    const lines = results
        .filter((item) => !!item && typeof item === 'object')
        .slice(0, 8)
        .map((item, index) => {
        const title = typeof item.title === 'string' ? item.title : '';
        const url = typeof item.url === 'string' ? item.url : '';
        const snippet = typeof item.snippet === 'string' ? item.snippet : '';
        return `${index + 1}. ${title}\n   ${url}${snippet ? `\n   ${snippet}` : ''}`.trim();
    });
    return `web_search ok n=${results.length}\n${lines.join('\n')}`.slice(0, 4_000);
}
