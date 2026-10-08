import { isCatalogCrawlTask, isPageReadTask, isResearchTask, isSiteCatalogSopTask, resolveTaskMode, } from './task-classifier.js';
const MEDIA_TASK = /播放|视频|m3u8|mp4|stream|playback|media url|播放地址|流地址|源地址|hls|webm/i;
function taskLooksLikeMedia(task) {
    return MEDIA_TASK.test(task.trim());
}
const SCRIPT_TASK = /(?:生成|写|输出|给我).{0,16}(python|py|脚本|scraper|爬虫)|(?:python|py|脚本).{0,24}(抓取|爬取|crawl|scrape|采集)|(?:抓取|爬取).{0,16}(python|脚本)/i;
export function isScriptDeliverableTask(task) {
    return SCRIPT_TASK.test(task.trim());
}
/**
 * Strong, deliverable-specific signal: the text itself names what kind of
 * outcome is wanted (a script, a media URL, a research comparison, a known
 * catalog/SOP shape, a page summary). These are precise enough to justify
 * switching the task narrative mid-thread.
 */
function resolveStrongDeliverableSignal(t) {
    if (isScriptDeliverableTask(t))
        return 'script';
    if (isResearchTask(t) || resolveTaskMode(t) === 'research')
        return 'research';
    if (taskLooksLikeMedia(t) && !isScriptDeliverableTask(t))
        return 'media';
    if (isSiteCatalogSopTask(t) || isCatalogCrawlTask(t))
        return 'data';
    if (isPageReadTask(t))
        return 'summary';
    return undefined;
}
/**
 * Weak/generic signal: catches verbs like "提取/抓取/列出" that describe an
 * *action* rather than a specific outcome. On a fresh thread this is still
 * useful as a last-resort classification, but it must never be allowed to
 * override an already-established deliverable — "上面的内容不全，请重新抓取
 * 一下" contains "抓取" and would otherwise flip deliverable=media into
 * deliverable=data mid-task (the exact drift seen in tests/message.txt).
 */
function resolveWeakDeliverableSignal(t) {
    if (resolveTaskMode(t) === 'general')
        return 'general';
    if (/提取|抓取|列出|top\s*\d+|前\s*\d+/.test(t) && !isPageReadTask(t))
        return 'data';
    return 'general';
}
export function resolveDeliverable(task) {
    const t = task.trim();
    return resolveStrongDeliverableSignal(t) ?? resolveWeakDeliverableSignal(t);
}
/**
 * Thread-aware resolution: once a deliverable is established for a thread,
 * keep it across follow-up turns unless the new message carries a strong,
 * specific signal for a *different* deliverable. A generic follow-up like
 * "继续" / "上面的内容不全，请重新抓取一下" / "？？" must not reclassify the
 * task narrative — it should continue serving the deliverable already in
 * flight. New threads (no `previous`) fall back to plain resolveDeliverable.
 */
export function resolveDeliverableWithContinuity(task, previous) {
    const t = task.trim();
    const strong = resolveStrongDeliverableSignal(t);
    if (strong)
        return strong;
    if (previous)
        return previous;
    return resolveWeakDeliverableSignal(t);
}
export const SCRAPER_SKILL_ID = 'persist';
export const SCRAPER_SKILL_INLINE = `# persist (script inline)
Phase 0: Read PAGE STATE + PAGE FRICTION. role=login → system_ask_user（公开入口或手动登录），勿空转读取。
Phase 1: browser_observe action=read mode=list 或 discover 摘要 → 记录分类 URL 模式、分页参数。
Phase 2: workspace action=script_save 写出 Python（requests/httpx + 可配置 pages 默认 1）。
Phase 3: system_done 附脚本 path + 采样到的 URL 模式；缺 Network/登录写 shortfall。`;
export function deliverablePreflightSkill(deliverable) {
    switch (deliverable) {
        case 'script':
            return SCRAPER_SKILL_ID;
        case 'media':
            return 'harvest';
        case 'data':
            return 'traverse';
        case 'summary':
            return 'observe';
        case 'research':
            return 'research';
        default:
            return undefined;
    }
}
export function deliverablePlanMilestone(deliverable) {
    switch (deliverable) {
        case 'script':
            return ('PLAN: deliverable=script — ' +
                '(1) PAGE STATE：role=login→system_ask_user；list 记录分类/分页 URL 模式。' +
                '(2) browser_observe read/list 或 discover 采样，勿 media recipe。' +
                '(3) workspace script_save：Python requests/httpx，channels+pages 可配置，pages 默认 1。' +
                '(4) system_done：脚本 path + 采样模式；缺登录/Network 写 shortfall。' +
                ' 禁止 media_extract recipe、MEDIA_ENTRY、spawn 媒体子任务。');
        case 'media':
            return ('PLAN: deliverable=media — ' +
                '(1) PAGE STATE：先识别 media candidate（feed_clicks/click_index），排除分类/导航节点；login→shortfall/ask，勿空转 observe。' +
                '(2) 记录可见视频名；structured extract 为空也不能判定无媒体，优先 click candidate，再按需进入详情。' +
                '(3) Network prepare/start/clear → click candidate → wait/list 捕获 m3u8/mp4/webm 或其它可验证媒体 URL；attach 暂时失败要重试。' +
                '(4) 用 network provenance 验证源地址后 system_done；严格任务缺源地址不得伪装 complete，输出明确 shortfall；navigation:forbidden 时用 spawn(mode:tab)。');
        case 'data':
            return 'PLAN: deliverable=data — traverse 列表/分页；结构化条目（非 script_save）。';
        case 'summary':
            return 'PLAN: deliverable=summary — dom_read body → system_done（结论先行）。';
        case 'research':
            return 'PLAN: deliverable=research — web_search → tabs → 对比 system_done。';
        default:
            return 'PLAN: deliverable=general — THREAD/CONTEXT 优先；必要时 web_search。';
    }
}
/** One narrative block per run (replaces stacked GUIDANCE for locked deliverables). */
export function deliverableGuidanceNotes(deliverable) {
    return [deliverablePlanMilestone(deliverable)];
}
/** Phase A/B: skip heavy catalog preflight for script deliverable. */
export function shouldRunCatalogPreflight(task, deliverable) {
    if (deliverable === 'script')
        return false;
    return isCatalogCrawlTask(task) || isSiteCatalogSopTask(task);
}
export function shouldRunMediaRecipe(deliverable, intent) {
    if (deliverable === 'script')
        return false;
    return intent === 'media_extract' || deliverable === 'media';
}
/** Summary text must not downgrade script/data deliverables from the user's anchor ask. */
export function lockDeliverable(anchorTask, executionTask) {
    const anchor = resolveDeliverable(anchorTask);
    const exec = resolveDeliverable(executionTask);
    if (anchor === 'script')
        return 'script';
    if (anchor === 'data' && exec === 'media' && !isScriptDeliverableTask(executionTask)) {
        return 'data';
    }
    if (anchor !== 'general' && exec === 'general')
        return anchor;
    return exec;
}
export function shouldEmitSiteCatalogGuidance(task, deliverable) {
    if (deliverable === 'script')
        return false;
    return isSiteCatalogSopTask(task);
}
