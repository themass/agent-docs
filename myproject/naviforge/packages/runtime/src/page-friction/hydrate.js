import { markObservationSeen } from '../loop-gate-state.js';
import { WORKING_SET } from '../working-set.js';
import { classifyTextFriction, PAGE_FRICTION_JS, parsePageFrictionPayload } from './detect.js';
import { formatPageFrictionForPrompt, frictionGuidanceNotes, frictionHitlKey, frictionHitlQuestion, shouldAutoHitl, } from './policy.js';
import { markPageRateLimited } from './throttle.js';
const FRICTION_REFRESH_TOOLS = new Set([
    'dom_navigate',
    'dom_click',
    'dom_read',
    'dom_snapshot',
    'dom_extract_content',
    'dom_extract_dom',
    'tabs_open',
    'tabs_switch',
]);
export function shouldRefreshPageFriction(tool) {
    return Boolean(tool && FRICTION_REFRESH_TOOLS.has(tool));
}
async function probePageFriction(dom, url) {
    if (!dom.executeJs)
        return null;
    const ran = await dom.executeJs({ code: PAGE_FRICTION_JS });
    if (!ran.ok)
        return null;
    const report = parsePageFrictionPayload(ran.data.result);
    if (!report)
        return null;
    if (!report.url)
        report.url = url;
    return report;
}
function reportFromDomRead(text, url) {
    const kinds = classifyTextFriction(text);
    const blob = text.slice(0, 6000).toLowerCase();
    const hardPaywall = kinds.includes('paywall') &&
        (/登录后观看|请登录后|请先登录|login to download/.test(blob) ||
            (/登录|login/.test(blob) && /密码|password/.test(blob)));
    const hasDownloadCta = /单篇下载|批量下载|立即下载|download/.test(blob);
    const blocking = kinds.some((k) => {
        if (k === 'cookie_banner')
            return false;
        if (k === 'paywall')
            return hardPaywall || !hasDownloadCta;
        return true;
    });
    return {
        url,
        title: '',
        kinds,
        blocking,
        cookieBanner: kinds.includes('cookie_banner'),
    };
}
export async function applyPageFrictionToCtx(ctx, opts) {
    const url = ctx.snap.url;
    const dom = ctx.agent.planes.dom;
    const bodyText = opts?.bodyText ?? ctx.snap.content;
    let report = !opts?.skipJs && dom.executeJs
        ? await probePageFriction(dom, url)
        : null;
    if (!report && bodyText)
        report = reportFromDomRead(bodyText, url);
    if (!report || (!report.kinds.length && !report.cookieBanner)) {
        return { report: null, notes: [] };
    }
    const hitlKey = frictionHitlKey(report);
    if (ctx.gates.frictionHitlKeys.has(hitlKey) &&
        (report.kinds.includes('paywall') || report.kinds.includes('login'))) {
        report = { ...report, blocking: false };
    }
    if (report.kinds.includes('rate_limit'))
        markPageRateLimited();
    const text = formatPageFrictionForPrompt(report);
    ctx.pageFrictionText = text;
    const key = `page_friction|${url}|${report.kinds.join(',')}`;
    markObservationSeen(ctx.gates, key, text.slice(0, WORKING_SET.evidenceChars));
    ctx.gates.stepsWithoutNewObs = 0;
    ctx.recordNote(`EVIDENCE: ${text.slice(0, WORKING_SET.evidenceChars)}`);
    const notes = frictionGuidanceNotes(report);
    for (const note of notes)
        ctx.recordNote(note);
    ctx.emit(ctx.createRecord('run.note', {
        topic: 'page_friction',
        text: text.slice(0, 1_600),
    }));
    let forceAsk;
    if (report.blocking && shouldAutoHitl(report)) {
        if (!ctx.gates.frictionHitlKeys.has(hitlKey)) {
            ctx.gates.frictionHitlKeys.add(hitlKey);
            forceAsk = frictionHitlQuestion(report);
            if (!ctx.gates.loadedSkillIds.has('friction') && !ctx.gates.loadedSkillIds.has('page-friction')) {
                ctx.recordNote('GUIDANCE: skill_load friction — 通用会话/验证/限频 HITL playbook');
            }
        }
    }
    ctx.gates.lastPageFriction = { url, report, at: Date.now() };
    return { report, forceAsk, notes };
}
