import { parseIndexedSnapshotLines as parseIndexedLinesFromBlob } from '@naviforge/extract';
const NAV_NOISE = /^(登录|注册|sign|register|home|首页|热门|直播|安装|更多|未命名|\*{3}|axx\.|http|www\.)/i;
function snapshotBlob(snap) {
    return [snap.header, snap.content, snap.footer].filter(Boolean).join('\n');
}
/** Parse `*[n] title` / `[n] title` rows from any snapshot (host-agnostic). */
export function parseIndexedSnapshotLines(snap, limit = 24) {
    return parseIndexedLinesFromBlob(snapshotBlob(snap), limit);
}
export function isNavLikeFeedTitle(title) {
    return title.length < 2 || NAV_NOISE.test(title) || /register|login|signin/i.test(title);
}
