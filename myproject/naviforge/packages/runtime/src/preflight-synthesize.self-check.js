import assert from 'node:assert/strict';
import { minePageSignals } from '@naviforge/observe';
import { synthesizePreflightResult } from './preflight-synthesize.js';
import { tryMediaPlaybackDeterministicResult } from './page-signals-hydrate.js';
const playBundle = minePageSignals({
    url: 'https://example.com/play/1',
    title: 'p',
    inlineScripts: [`var player_aaaa = {"url":"https://cdn.example/a.m3u8","flag":"play"}`],
    externalScriptSrcs: [],
    meta: [],
    resources: [],
});
const singlePlayback = tryMediaPlaybackDeterministicResult(playBundle, '分析播放地址', {
    strategy: 'media-extract',
});
assert.ok(singlePlayback?.includes('a.m3u8'), 'media-extract strategy allows playback shortcut');
assert.equal(tryMediaPlaybackDeterministicResult(playBundle, '抓取当前页面下所有的视频源地址和名称', {
    strategy: 'spawn-media',
}), undefined, 'spawn-media must not short-circuit to single playback');
const merged = synthesizePreflightResult({
    strategy: 'spawn-media',
    mediaPlayback: singlePlayback,
    catalogCrawl: {
        plan: {
            startUrl: 'https://example.com/list',
            sections: [{ name: '(current)', url: 'https://example.com/list' }],
            pagesPerSection: 1,
            wantsMediaUrl: true,
        },
        complete: false,
        sections: [
            {
                section: { name: '(current)', url: 'https://example.com/list' },
                pages: [
                    {
                        url: 'https://example.com/list',
                        entries: [
                            { title: 'V1', url: 'https://example.com/play/1' },
                            { title: 'V2', url: 'https://example.com/play/2' },
                        ],
                    },
                ],
            },
        ],
    },
    spawnGuidance: 'spawn me',
});
assert.ok(merged?.includes('V1'), 'partial catalog beats single playback');
assert.ok(merged?.includes('V2'), 'partial catalog includes all entries');
assert.ok(merged?.includes('spawn me'), 'spawn guidance appended');
assert.ok(!merged?.includes('目录爬取完成') || merged.includes('部分完成'), 'partial label ok');
console.log('preflight-synthesize self-check ok');
