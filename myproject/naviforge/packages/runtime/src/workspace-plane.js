/** Local disk workspace — implemented by the Host HTTP helper. Runtime stays Chrome-free. */
export function workspaceSlug(title) {
    const slug = title
        .toLowerCase()
        .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .slice(0, 40);
    return slug || 'thread';
}
