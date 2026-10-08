import assert from 'node:assert/strict';
import { buildCatalogPlan, parseDiscoverPayload } from './discover.js';
import { isCatalogCrawlTask, isSiteCatalogSopTask, parseCatalogCrawlSpec } from './spec.js';
import { formatCatalogCrawlResult } from './format.js';
import { classifyPlaybackUrl, entryHasPlayableEvidence } from './media-entry.js';
import { validateCatalogCrawlResult } from './validate.js';
import { parseTableExtractPayload } from './table-extract.js';
assert.equal(classifyPlaybackUrl('https://x/a.m3u8'), 'hls');
assert.equal(classifyPlaybackUrl('https://x/v.mp4'), 'mp4');
assert.ok(entryHasPlayableEvidence({ playPageUrl: 'https://x/play/1' }));
assert.ok(isCatalogCrawlTask('分析所有博客分类，抓取每个分类前2页的文章标题和链接'));
assert.ok(isCatalogCrawlTask('scrape all shop categories, 2 pages each, product name and url'));
assert.ok(!isCatalogCrawlTask('提取前5个视频名称'));
assert.ok(isSiteCatalogSopTask('抓取当前页面下所有的视频源地址和名称'), 'single list + per-item media is catalog SOP');
assert.ok(isSiteCatalogSopTask('分析所有博客分类，抓取每个分类前2页的文章标题和链接'));
assert.equal(parseCatalogCrawlSpec('每个分类前2页').pagesPerSection, 2);
assert.equal(parseCatalogCrawlSpec('每个分类前2页').wantsMediaUrl, false);
assert.equal(parseCatalogCrawlSpec('每个分类前2页').maxDetailHops, 2);
assert.ok(parseCatalogCrawlSpec('抓取视频名称和播放地址').wantsMediaUrl);
assert.ok(parseCatalogCrawlSpec('表格列表数据').wantsTableRows);
const tableRows = parseTableExtractPayload([
    { title: 'A', url: 'https://x/a', fields: { name: 'A', price: '1' } },
]);
assert.equal(tableRows.length, 1);
assert.equal(tableRows[0]?.fields?.price, '1');
const discover = parseDiscoverPayload({
    url: 'https://shop.example/catalog',
    origin: 'https://shop.example',
    sections: [
        { name: 'Phones', url: 'https://shop.example/c/phones' },
        { name: 'Laptops', url: 'https://shop.example/c/laptops' },
    ],
    pagination: [{ label: '2', url: 'https://shop.example/c/phones?page=2' }],
    detailShape: 'p/*',
    listSample: [{ title: 'Widget', url: 'https://shop.example/p/abc123' }],
});
assert.ok(discover);
const { plan, usedFallbackSection } = buildCatalogPlan(discover, {
    pagesPerSection: 2,
    maxSections: 8,
    wantsMediaUrl: false,
});
assert.equal(usedFallbackSection, false);
assert.equal(plan.sections.length, 2);
assert.equal(plan.detailShape, 'p/*');
const formatted = formatCatalogCrawlResult({
    plan,
    complete: true,
    sections: [
        {
            section: plan.sections[0],
            pages: [
                {
                    url: plan.sections[0].url,
                    entries: [{ title: 'Item A', url: 'https://shop.example/p/a' }],
                },
            ],
        },
    ],
});
assert.ok(formatted.includes('Item A'));
const deduped = validateCatalogCrawlResult({
    plan,
    complete: true,
    sections: [
        {
            section: plan.sections[0],
            pages: [
                {
                    url: plan.sections[0].url,
                    entries: [
                        { title: 'Item A', url: 'https://shop.example/p/a' },
                        { title: 'Item A dup', url: 'https://shop.example/p/a' },
                    ],
                },
            ],
        },
    ],
}, { wantsMediaUrl: false });
assert.equal(deduped.duplicatesRemoved, 1);
assert.equal(deduped.uniqueEntries, 1);
const embedVal = validateCatalogCrawlResult({
    plan,
    complete: true,
    sections: [
        {
            section: plan.sections[0],
            pages: [
                {
                    url: plan.sections[0].url,
                    entries: [{ title: 'V', url: 'https://shop.example/p/v', playPageUrl: 'https://shop.example/play/v', format: 'embed' }],
                },
            ],
        },
    ],
}, { wantsMediaUrl: true });
assert.equal(embedVal.missingMedia, 0);
assert.equal(embedVal.embedOnly, 1);
console.log('catalog-crawl self-check ok');
