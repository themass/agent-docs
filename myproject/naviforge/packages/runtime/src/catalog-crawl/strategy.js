export function wantsMultipleMediaItems(task) {
    return /所有|全部|每个|各条|批量|每一|all|every/i.test(task.trim());
}
export function selectCatalogStrategy(opts) {
    if (opts.fullSiteCrawl)
        return 'full-catalog';
    if (opts.brief.role === 'play' && opts.wantsMedia)
        return 'media-extract';
    if (opts.brief.role === 'list') {
        if (opts.wantsMedia && (wantsMultipleMediaItems(opts.task) || opts.brief.listItemCount > 1)) {
            return 'spawn-media';
        }
        return 'current-page-list';
    }
    if (opts.brief.role === 'detail' && opts.wantsMedia) {
        return opts.brief.hasPlayback ? 'media-extract' : 'delegate-model';
    }
    if (opts.brief.confidence < 0.65)
        return 'delegate-model';
    return 'current-page-list';
}
export function spawnMediaGuidance(entryCount) {
    return [
        `NOTE: 当前页已提取 ${entryCount} 条列表项；直链流不在列表 DOM 中。`,
        '请用 system_spawn_readonly_tasks 并行打开各播放/详情 URL（每批 ≤3，mode: tab），',
        '子任务读 PAGE SIGNALS，返回 JSON {title, listUrl, mediaUrl?, playPageUrl?, format?, confidence?, shortfall?}。',
        '父 Agent 合并 children[] 后 system_done。',
    ].join('\n');
}
