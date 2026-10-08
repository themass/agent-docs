import type { DomPlane } from '@naviforge/dom-plane';
import type { CatalogCrawlPlan, CatalogDiscoverResult } from './types.js';
/**
 * Site-agnostic catalog discovery (runs in page MAIN world via dom_execute_js).
 * Finds nav sections, pagination, and dominant list-item URL shape by voting —
 * no host names, no vertical-specific selectors.
 */
export declare const CATALOG_DISCOVER_JS = "(() => {\n  const origin = location.origin\n  const clean = (s) => (s || '').trim().replace(/\\s+/g, ' ')\n  const links = [...document.querySelectorAll('a[href]')].map((a) => ({\n    t: clean(a.textContent),\n    h: a.href,\n    inNav: Boolean(\n      a.closest(\n        'header,nav,[role=navigation],[role=tablist],.tabs,.tab,.categories,.menu,[class*=\"category\"],[class*=\"nav\"]'\n      )\n    ),\n    inMain: Boolean(\n      a.closest('main,[role=main],article,.content,#content,.list,.grid,.feed,.products,.posts')\n    ),\n  }))\n\n  const skipLabel = /^(home|index|\u9996\u9875|login|\u767B\u5F55|register|\u6CE8\u518C|sign\\s*in|sign\\s*up|search|\u641C\u7D22|cart|\u8D2D\u7269\u8F66|more|\u66F4\u591A|menu|help|\u5173\u4E8E|about)$/i\n\n  function shape(href) {\n    try {\n      const u = new URL(href, location.href)\n      if (u.origin !== origin) return ''\n      const parts = u.pathname.split('/').filter(Boolean)\n      if (parts.length < 2) return ''\n      return parts\n        .map((seg, i, arr) =>\n          i === arr.length - 1 && seg.length >= 3 && /[0-9A-Za-z]{3,}/.test(seg) ? '*' : seg\n        )\n        .join('/')\n    } catch {\n      return ''\n    }\n  }\n\n  const shapeCounts = new Map()\n  for (const x of links) {\n    if (!x.h.startsWith(origin)) continue\n    if (!x.inMain) continue\n    const s = shape(x.h)\n    if (!s || s.split('/').length < 2) continue\n    shapeCounts.set(s, (shapeCounts.get(s) || 0) + 1)\n  }\n  const detailShape =\n    [...shapeCounts.entries()].sort((a, b) => b[1] - a[1]).find(([, n]) => n >= 3)?.[0] ?? undefined\n\n  const sections = []\n  const seen = new Set()\n  for (const x of links) {\n    if (!x.h.startsWith(origin)) continue\n    if (!x.inNav) continue\n    if (!x.t || x.t.length > 28 || x.t.length < 2) continue\n    if (skipLabel.test(x.t)) continue\n    if (seen.has(x.h)) continue\n    seen.add(x.h)\n    sections.push({ name: x.t, url: x.h })\n  }\n\n  const pagination = links\n    .filter(\n      (x) =>\n        x.h.startsWith(origin) &&\n        /^(\\d+|next|prev|\u4E0A\u4E00\u9875|\u4E0B\u4E00\u9875|\u203A|\u00BB|\u2039|\u2039)$/i.test(x.t)\n    )\n    .slice(0, 20)\n    .map((x) => ({ label: x.t, url: x.h }))\n  const relNext = document.querySelector('a[rel=\"next\"],link[rel=\"next\"]')\n  if (relNext && relNext.href && relNext.href.startsWith(origin)) {\n    pagination.push({ label: 'rel=next', url: relNext.href })\n  }\n\n  const infiniteScroll = Boolean(\n    document.querySelector(\n      '.infinite-scroll,[data-infinite],[class*=\"infinite\"],.load-more,button[class*=\"load-more\"]'\n    )\n  )\n\n  const listSample = links\n    .filter((x) => {\n      if (!x.h.startsWith(origin)) return false\n      if (detailShape) return shape(x.h) === detailShape\n      return x.inMain && x.t.length >= 2\n    })\n    .slice(0, 16)\n    .map((x) => ({ title: x.t.slice(0, 160), url: x.h }))\n\n  return {\n    url: location.href,\n    origin,\n    sections: sections.slice(0, 32),\n    pagination,\n    detailShape,\n    listSample,\n    infiniteScroll,\n  }\n})()";
export declare const CATALOG_PAGE_URL_JS: (pageNum: number) => string;
export declare function parseDiscoverPayload(raw: unknown): CatalogDiscoverResult | null;
export declare function discoverCatalogPage(dom: DomPlane): Promise<CatalogDiscoverResult | null>;
/** Single-section plan anchored on the current URL (no nav-section expansion). */
export declare function buildCurrentPagePlan(discover: CatalogDiscoverResult, spec: {
    pagesPerSection: number;
    wantsMediaUrl: boolean;
}): CatalogCrawlPlan;
export declare function buildCatalogPlan(discover: CatalogDiscoverResult, spec: {
    pagesPerSection: number;
    maxSections: number;
    wantsMediaUrl: boolean;
}): {
    plan: CatalogCrawlPlan;
    usedFallbackSection: boolean;
};
