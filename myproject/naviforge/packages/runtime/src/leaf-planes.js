/** Read-only DOM facade (no navigate/inject); navigation uses scoped tabs plane when provided. */
export function readonlyDom(dom) {
    return {
        snapshot: () => dom.snapshot(),
        ...(dom.readPage ? { readPage: () => dom.readPage() } : {}),
    };
}
