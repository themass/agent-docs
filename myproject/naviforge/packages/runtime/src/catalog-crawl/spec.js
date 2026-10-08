/** Multi-section × multi-page site crawl (video, blog, shop, news…). */
export function isCatalogCrawlTask(task) {
    const t = task.trim();
    if (/(所有|全部|每个|every).{0,16}(分类|类别|栏目|频道|标签|tag|category|section|aisle|department)/i.test(t)) {
        return true;
    }
    if (/(分类|类别|栏目|频道|tag|category).{0,24}(前\s*\d+\s*页|每页|\d+\s*pages?)/i.test(t)) {
        return true;
    }
    if (/(抓取|采集|爬取|scrape|crawl).{0,16}(所有|全部|每个|all)/i.test(t) &&
        /分类|categories?|category|栏目|列表|list|catalog/i.test(t)) {
        return true;
    }
    return false;
}
export function parseCatalogCrawlSpec(task) {
    const pagesMatch = /(?:前|each\s*|每\s*)?(\d{1,2})\s*页/i.exec(task);
    const pagesPerSection = pagesMatch ? Math.min(5, Math.max(1, Number(pagesMatch[1]))) : 1;
    const wantsMediaUrl = /播放|stream|源流|源地址|视频地址|播放地址|webm|mpd|dash|m3u8|mp4|media|视频|audio|下载地址|在线播放|嵌入/i.test(task);
    const wantsTableRows = /表格|table|sheet|行数据|列表数据/i.test(task);
    const maxSectionsMatch = /(?:最多|limit\s*)?(\d{1,2})\s*(?:个\s*)?(?:分类|栏目|section)/i.exec(task);
    const maxSections = maxSectionsMatch ? Math.min(16, Number(maxSectionsMatch[1])) : 10;
    const hopsMatch = /(\d)\s*跳|(\d)\s*hop/i.exec(task);
    const maxDetailHops = hopsMatch ? Math.min(3, Math.max(1, Number(hopsMatch[1] ?? hopsMatch[2]))) : 2;
    return {
        pagesPerSection,
        maxSections,
        maxItemsPerPage: 48,
        maxMediaFetches: wantsMediaUrl ? 24 : 0,
        wantsMediaUrl,
        wantsTableRows,
        maxDetailHops,
    };
}
/**
 * Full browser catalog SOP: categories → paginated lists → detail (incl. multi-hop) → validate.
 * Broader than isCatalogCrawlTask (includes single-list-page + per-item detail fields).
 */
export function isSiteCatalogSopTask(task) {
    if (isCatalogCrawlTask(task))
        return true;
    const t = task.trim();
    const multiItem = /所有|全部|每个|各行|各条|批量|每一/i.test(t) ||
        /(?:each|every|all)\s+(?:the\s+)?(?:items?|entries|videos?|products?|articles?)/i.test(t);
    const detailFields = /源地址|播放|流地址|m3u8|mp4|webm|mpd|dash|media|stream|价格|库存|详情|字段|sku|正文|表格|下载|视频地址/i.test(t);
    const listContext = /当前页|当前页面|本页|this page|列表|list page|分类页|目录/i.test(t) || multiItem;
    if (listContext && multiItem && detailFields)
        return true;
    if (multiItem && detailFields && /视频|商品|文章|条目|records?/i.test(t))
        return true;
    return false;
}
