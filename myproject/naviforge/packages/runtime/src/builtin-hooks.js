import { evaluateAskUser, hasRecentSensitiveApproval, sensitiveConfirmQuestion, SENSITIVE_TOOLS, } from '@naviforge/policy';
import { isCoveredByToolAllowlist, isMcpQualifiedToolName, mcpQualifiedName } from '@naviforge/shared';
import { formatExtractContentTrace, formatReadPageTrace, isToolAllowed } from './exec-turn.js';
import { CSP_EXECUTE_JS_HINT, ToolOutcomePolicy } from './failure.js';
import { CONTINUE, HookPipeline, ModelErrorHook, ProtocolHook, ToolOutcomeHook, WorkingSetHook, } from './hooks.js';
import { actionLoopKey, bareSkillId, decideActionLoop, isPageReadTask, isResearchTask, observationDedupeKey, recordActionLoopSuccess, requestedList, } from './loop-gates.js';
import { bumpDuplicateSkip, hasSynthesisEvidence, markObservationSeen, observationAlreadySeen, priorObservation, recordListHints, recordLoadedSkill, recordRunTab, } from './loop-gate-state.js';
import { formatListResult } from './prompt.js';
import { WORKING_SET } from './working-set.js';
import { shouldSkipLoginLinkRead } from './page-state.js';
import { applyPageSignalsToCtx, formatListPageMediaHint, formatPlaybackCandidatesForHitl, isMediaEvidenceTask, tryMediaPlaybackDeterministicResult } from './page-signals-hydrate.js';
import { applyPageFrictionToCtx } from './page-friction/index.js';
import { listHintsFromToolData, sameActionLoopResult } from './run-limits.js';
import { isRedundantTabsOpen, recordPageVisit } from './page-cache.js';
import { runSiteRecipe } from './recipe-runner.js';
import { hostFromUrl } from './site-recipe.js';
import { intentGuidanceNotes, intentPreflightSkill, resolveTaskIntent } from './task-intent.js';
import { isBulkMdCatalogTask, isCatalogCrawlTask, resolveTaskMode, taskGuidanceNotes } from './task-classifier.js';
import { classifyPageBrief, discoverCatalogPage, formatCatalogPlanEvidence, parseCatalogCrawlSpec, runCatalogCrawl, runCurrentPageListCrawl, selectCatalogStrategy, spawnMediaGuidance, } from './catalog-crawl/index.js';
import { synthesizePreflightResult } from './preflight-synthesize.js';
import { deliverableGuidanceNotes, deliverablePreflightSkill, resolveDeliverable, resolveDeliverableWithContinuity, SCRAPER_SKILL_INLINE, SCRAPER_SKILL_ID, shouldEmitSiteCatalogGuidance, shouldRunCatalogPreflight, shouldRunMediaRecipe, } from './deliverable.js';
import { attachPageState } from './pi-run-loop.js';
import { MediaHarvestMilestoneHook, NetworkDegradedToolGateHook, NetworkPlaneHealthHook } from './media-harvest-hooks.js';
import { tryMediaFeedDeterministicHarvest } from './media-feed-deterministic.js';
import { tryMediaHomePreflightDone } from './media-home-harvest.js';
import { evaluateEvidence } from './evaluator.js';
function preflightLoadSkill(ctx, skillId, note) {
    let skill = ctx.skills.find((s) => s.id === skillId);
    if (!skill && skillId === SCRAPER_SKILL_ID) {
        skill = {
            id: SCRAPER_SKILL_ID,
            version: '0.1.0',
            description: '站点结构采样 → script_save Python 爬虫脚本',
            instructions: SCRAPER_SKILL_INLINE,
        };
    }
    if (!skill || ctx.gates.loadedSkillIds.has(skillId))
        return;
    const header = [
        `# skill:${skill.id}@${skill.version}`,
        skill.description,
        skill.tools?.length ? `Suggested tools (advisory unless hard allowlist): ${skill.tools.join(', ')}` : '',
    ]
        .filter(Boolean)
        .join('\n');
    ctx.gates.loadedSkillBodies.length = 0;
    ctx.gates.loadedSkillBodies.push(`${header}\n\n${skill.instructions.trim()}`);
    ctx.gates.loadedSkillIds.add(skillId);
    ctx.recordNote(note);
    ctx.emit(ctx.createRecord('tool.result', {
        tool: 'skill_load',
        arguments: { id: skillId, via: 'preflight' },
        ok: true,
        data: { id: skillId, version: skill.version },
    }));
}
/** Deterministic DOM reads before the model loop (list extract, top-N mark, page read). */
export class PreflightHook {
    name = 'preflight';
    writes = ['deliverable', 'taskIntent', 'recipeUsed', 'recipeId', 'loadedSkillIds', 'loadedSkillBodies'];
    async runTaskPreflight(ctx) {
        const planes = ctx.agent.planes;
        let deterministicResult;
        const previousDeliverable = ctx.reuse.lastDeliverable;
        const deliverable = ctx.gates.deliverable ?? resolveDeliverableWithContinuity(ctx.task, previousDeliverable);
        ctx.gates.deliverable = deliverable;
        // Structured marker (topic='deliverable') so the *next* run in this
        // thread can read it back via ThreadReuse.lastDeliverable — see
        // formatSessionReuse in @naviforge/session. Generic follow-ups like
        // "继续" / "上面的内容不全，请重新抓取一下" / "？？" must not reclassify
        // the task narrative away from what was already established.
        ctx.emit(ctx.createRecord('run.note', { text: `DELIVERABLE: ${deliverable}`, topic: 'deliverable' }));
        for (const note of deliverableGuidanceNotes(deliverable))
            ctx.recordNote(note);
        const intent = resolveTaskIntent(ctx.task);
        ctx.gates.taskIntent = intent;
        if (intent === 'denied') {
            return 'CONSTRAINT: 任务涉及破解/绕过加密或付费墙，无法执行。请用 system_done 说明合法替代方案。';
        }
        if (deliverable === 'general') {
            for (const note of intentGuidanceNotes(intent))
                ctx.recordNote(note);
        }
        const host = hostFromUrl(ctx.snap.url);
        if (host && planes.recipes && shouldRunMediaRecipe(deliverable, intent) && !ctx.networkUnavailable) {
            const recipe = await planes.recipes.find(host, intent);
            if (recipe) {
                const network = planes.network;
                let skipRecipe = false;
                if (network) {
                    const digestProbe = await network.digest(1).catch(() => undefined);
                    if (digestProbe?.ok) {
                        ctx.recordNote(`PREFLIGHT: skip recipe ${recipe.id} — network digest ok (avoid duplicate attach)`);
                        skipRecipe = true;
                    }
                }
                if (!skipRecipe) {
                    ctx.recordNote(`PREFLIGHT: site recipe ${recipe.id} — ${recipe.title}`);
                    const ran = await runSiteRecipe({
                        recipe,
                        dom: planes.dom,
                        network: planes.network,
                        task: ctx.task,
                        url: ctx.snap.url,
                        snap: ctx.snap,
                    });
                    ctx.emit(ctx.createRecord('tool.result', {
                        tool: 'recipe_run',
                        arguments: { id: recipe.id, intent },
                        ok: ran.ok,
                        ...(ran.ok ? { data: { text: ran.text } } : { error: { code: 'recipe_failed', message: ran.error, recoverable: true } }),
                    }));
                    if (ran.ok) {
                        ctx.gates.recipeUsed = true;
                        ctx.gates.recipeId = recipe.id;
                        void planes.recipes.bumpSuccess?.(recipe.id);
                        ctx.recordNote(`PREFLIGHT: recipe ${recipe.id} ok`);
                        return ran.text;
                    }
                    ctx.recordNote(`PREFLIGHT: recipe ${recipe.id} failed (${ran.error}) — fallback skill/LLM`);
                    if (deliverable === 'media' && planes.network) {
                        const feedResult = await tryMediaFeedDeterministicHarvest(ctx);
                        if (feedResult)
                            return feedResult;
                    }
                }
            }
        }
        const intentSkill = deliverablePreflightSkill(deliverable) ?? intentPreflightSkill(intent);
        if (intentSkill) {
            preflightLoadSkill(ctx, intentSkill, `PREFLIGHT: deliverable=${deliverable} skill ${intentSkill}`);
        }
        if (deliverable === 'media') {
            const mediaEarly = await tryMediaHomePreflightDone(ctx);
            if (mediaEarly)
                return mediaEarly;
        }
        const listRequest = requestedList(ctx.task);
        if (listRequest &&
            deliverable !== 'script' &&
            deliverable !== 'media' &&
            !listRequest.mark &&
            !isCatalogCrawlTask(ctx.task) &&
            planes.dom.extractContent &&
            !isPageReadTask(ctx.task)) {
            const extracted = await planes.dom.extractContent(listRequest.n);
            ctx.emit(ctx.createRecord('tool.result', {
                tool: 'dom_read',
                arguments: { mode: 'list', n: listRequest.n, enforced: true },
                ok: extracted.ok,
                ...(extracted.ok ? { data: extracted.data } : { error: extracted.error }),
            }));
            ctx.recordNote(extracted.ok
                ? `PREFLIGHT: dom_read list items=${JSON.stringify(extracted.data.items)}${extracted.data.shortfall ? ` shortfall=${extracted.data.shortfall}` : ''}`
                : `PREFLIGHT: dom_read list failed=${extracted.error.message}`);
            if (extracted.ok) {
                ctx.gates.lastListHints = listHintsFromToolData(extracted.data);
                const extractKey = observationDedupeKey('dom_read', ctx.snap.url, { mode: 'list' });
                if (extractKey) {
                    markObservationSeen(ctx.gates, extractKey, formatExtractContentTrace(extracted.data));
                }
            }
            ctx.emit(ctx.createRecord('run.log', {
                message: extracted.ok
                    ? `extract top${listRequest.n}: ${extracted.data.items.length} records (page unchanged)`
                    : `extract top${listRequest.n} failed: ${extracted.error.message}`,
            }));
            if (extracted.ok && extracted.data.items.length) {
                deterministicResult = formatListResult(extracted.data.items, false, extracted.data.shortfall);
            }
        }
        const topN = listRequest?.mark ? listRequest.n : null;
        if (topN !== null && deliverable !== 'script' && deliverable !== 'media' && planes.dom.markTopn) {
            const marked = await planes.dom.markTopn(topN);
            ctx.emit(ctx.createRecord('tool.result', {
                tool: 'dom_mark_topn',
                arguments: { n: topN, enforced: true },
                ok: marked.ok,
                ...(marked.ok ? { data: marked.data } : { error: marked.error }),
            }));
            ctx.recordNote(marked.ok
                ? `PREFLIGHT: dom_mark_topn marked=${marked.data.marked} items=${JSON.stringify(marked.data.items)}`
                : `PREFLIGHT: dom_mark_topn failed=${marked.error.message}`);
            if (marked.ok)
                ctx.gates.lastListHints = listHintsFromToolData(marked.data);
            ctx.emit(ctx.createRecord('run.log', {
                message: marked.ok
                    ? `top${topN} visual mark: ${marked.data.marked}/${topN}`
                    : `top${topN} visual mark failed: ${marked.error.message}`,
            }));
            if (marked.ok && marked.data.marked) {
                deterministicResult = formatListResult(marked.data.items, true, marked.data.shortfall);
            }
        }
        if (isPageReadTask(ctx.task) && planes.dom.readPage) {
            const readKey = observationDedupeKey('dom_read', ctx.snap.url, { mode: 'body' });
            if (readKey && observationAlreadySeen(ctx.gates, readKey)) {
                const prior = priorObservation(ctx.gates, readKey);
                ctx.recordNote('PREFLIGHT: reuse prior dom_read body for this URL');
                if (prior)
                    ctx.recordNote(`EVIDENCE: ${prior.slice(0, WORKING_SET.evidenceChars)}`);
            }
            else {
                const read = await planes.dom.readPage();
                ctx.emit(ctx.createRecord('tool.result', {
                    tool: 'dom_read',
                    arguments: { mode: 'body', enforced: true },
                    ok: read.ok,
                    ...(read.ok ? { data: read.data } : { error: read.error }),
                }));
                if (read.ok) {
                    ctx.recordNote(`PREFLIGHT: ${formatReadPageTrace(read.data)}`);
                    if (readKey) {
                        markObservationSeen(ctx.gates, readKey, formatReadPageTrace(read.data));
                    }
                    ctx.emit(ctx.createRecord('run.log', {
                        message: `dom_read body: ${read.data.text.length} chars from ${read.data.source}`,
                    }));
                }
                else {
                    ctx.recordNote(`PREFLIGHT: dom_read body failed=${read.error.message}`);
                    ctx.emit(ctx.createRecord('run.log', { message: `dom_read body failed: ${read.error.message}` }));
                }
            }
            const pageRead = ctx.skills.find((s) => s.id === 'observe' || s.id === 'page-read');
            if (pageRead && !ctx.gates.loadedSkillIds.has('observe') && !ctx.gates.loadedSkillIds.has('page-read')) {
                preflightLoadSkill(ctx, 'observe', 'PREFLIGHT: skill observe (READ done template)');
            }
        }
        if (isResearchTask(ctx.task) && !isPageReadTask(ctx.task) && !isBulkMdCatalogTask(ctx.task)) {
            preflightLoadSkill(ctx, 'research', 'PREFLIGHT: skill research (off-page compare)');
        }
        if (shouldEmitSiteCatalogGuidance(ctx.task, deliverable)) {
            preflightLoadSkill(ctx, 'traverse', 'PREFLIGHT: skill traverse (site catalog SOP)');
        }
        if (resolveTaskMode(ctx.task) === 'in_page') {
            const friction = await applyPageFrictionToCtx(ctx, {
                bodyText: ctx.snap.content,
                skipJs: !ctx.agent.policy.allowDomInject,
            });
            if (friction.report?.blocking) {
                preflightLoadSkill(ctx, 'friction', 'PREFLIGHT: skill friction (universal session gate)');
            }
        }
        const catalogTask = shouldRunCatalogPreflight(ctx.task, deliverable);
        const spec = catalogTask ? parseCatalogCrawlSpec(ctx.task) : null;
        const discover = catalogTask && planes.dom.executeJs ? await discoverCatalogPage(planes.dom) : null;
        if (resolveTaskMode(ctx.task) === 'in_page' && planes.dom.collectPageSignalRaw) {
            const bundle = await applyPageSignalsToCtx(ctx);
            const brief = discover ? classifyPageBrief(discover, bundle) : null;
            if (brief) {
                ctx.recordNote(`PREFLIGHT: page role=${brief.role} confidence=${brief.confidence.toFixed(2)} detailShape=${brief.detailShape ?? '(none)'} items=${brief.listItemCount}`);
                if (bundle) {
                    const listHint = formatListPageMediaHint(bundle, ctx.task, brief);
                    if (listHint &&
                        (deliverable === 'general' || deliverable === 'data' || deliverable === 'media')) {
                        ctx.recordNote(`GUIDANCE: ${listHint}`);
                    }
                }
            }
            const strategy = discover && spec && brief
                ? selectCatalogStrategy({
                    task: ctx.task,
                    brief,
                    fullSiteCrawl: isCatalogCrawlTask(ctx.task),
                    wantsMedia: spec.wantsMediaUrl,
                })
                : undefined;
            let mediaPlayback;
            if (bundle) {
                if (catalogTask && strategy) {
                    mediaPlayback = tryMediaPlaybackDeterministicResult(bundle, ctx.task, { strategy });
                }
                else if (!catalogTask) {
                    mediaPlayback = tryMediaPlaybackDeterministicResult(bundle, ctx.task);
                }
            }
            let catalogCrawl = null;
            let spawnGuidance;
            if (catalogTask && spec && discover && strategy) {
                ctx.recordNote(`PREFLIGHT: catalog strategy=${strategy} pages/section=${spec.pagesPerSection} media=${spec.wantsMediaUrl}`);
                if (strategy === 'full-catalog') {
                    catalogCrawl = await runCatalogCrawl(ctx, spec);
                }
                else if (strategy === 'current-page-list' || strategy === 'spawn-media') {
                    catalogCrawl = await runCurrentPageListCrawl(ctx, spec, discover, {
                        resolveMedia: strategy === 'current-page-list',
                    });
                    if (strategy === 'spawn-media' && catalogCrawl) {
                        const count = catalogCrawl.sections.reduce((n, s) => n + s.pages.reduce((m, p) => m + p.entries.length, 0), 0);
                        if (count > 0)
                            spawnGuidance = spawnMediaGuidance(count);
                    }
                }
                if (catalogCrawl) {
                    if (catalogCrawl.authBlocked) {
                        preflightLoadSkill(ctx, 'friction', 'PREFLIGHT: skill friction (blocked by session gate)');
                        ctx.recordNote('EVIDENCE: PAGE_FRICTION blocked catalog-crawl — user login or system_captcha_wait required');
                    }
                    ctx.recordNote(`EVIDENCE: ${formatCatalogPlanEvidence(catalogCrawl.plan).slice(0, WORKING_SET.evidenceChars)}`);
                    ctx.emit(ctx.createRecord('run.log', {
                        message: `catalog-crawl ${catalogCrawl.complete ? 'complete' : 'partial'} strategy=${strategy} sections=${catalogCrawl.sections.length}`,
                    }));
                }
            }
            const synthesized = synthesizePreflightResult({
                strategy: strategy ?? 'delegate-model',
                mediaPlayback,
                catalogCrawl,
                spawnGuidance,
            });
            if (synthesized)
                deterministicResult = synthesized;
            else if (bundle && isMediaEvidenceTask(ctx.task)) {
                const hitl = formatPlaybackCandidatesForHitl(bundle);
                if (hitl)
                    ctx.recordNote(`EVIDENCE: ${hitl}`);
            }
        }
        else if (catalogTask && spec && discover) {
            const brief = classifyPageBrief(discover, null);
            const strategy = selectCatalogStrategy({
                task: ctx.task,
                brief,
                fullSiteCrawl: isCatalogCrawlTask(ctx.task),
                wantsMedia: spec.wantsMediaUrl,
            });
            ctx.recordNote(`PREFLIGHT: catalog strategy=${strategy} (no PAGE SIGNALS collection)`);
        }
        await attachPageState(ctx);
        if (!deterministicResult && deliverable === 'media') {
            deterministicResult = await tryMediaHomePreflightDone(ctx);
        }
        return deterministicResult;
    }
}
export class SkillAllowlistHook {
    name = 'skill-allowlist';
    // No ctx.gates reads/writes — checks ctx.allowedTools only.
    beforeTool(ctx) {
        const tool = ctx.toolCall?.tool;
        if (!tool || isToolAllowed(tool, ctx.allowedTools))
            return CONTINUE;
        return {
            kind: 'skip_tool',
            note: `${tool} fail denied by skill permissions`,
            privacy: {
                tool,
                code: 'skill_allowlist',
                hint: `当前 Skill 未授权 ${tool}，本次调用已拦截。可在设置中关闭「Skill 硬白名单」。`,
            },
        };
    }
}
/** Hard capability boundary for leaf runs; unlike skill allowlists, no system-tool bypass exists. */
export class RunProfileHook {
    name = 'run-profile';
    // No ctx.gates reads/writes — checks ctx.agent.profile only.
    beforeTool(ctx) {
        const tool = ctx.toolCall?.tool;
        const profile = ctx.agent.profile;
        if (!tool || !profile)
            return CONTINUE;
        const readonlyMcp = profile.allowReadonlyMcp &&
            isMcpQualifiedToolName(tool) &&
            ctx.agent.mcpTools.some((candidate) => candidate.readonly &&
                tool === mcpQualifiedName(candidate.serverId, candidate.name));
        if (isCoveredByToolAllowlist(tool, profile.allowedTools) || readonlyMcp)
            return CONTINUE;
        return {
            kind: 'skip_tool',
            note: `${tool} denied by ${profile.name} capability profile`,
            result: {
                ok: false,
                error: { code: 'capability_denied', message: `${tool} is not allowed for ${profile.name}`, recoverable: false },
            },
        };
    }
}
export class SensitiveToolHook {
    name = 'sensitive-tool';
    // No ctx.gates reads/writes — checks ctx.ledger notes only.
    beforeTool(ctx) {
        const call = ctx.toolCall;
        if (!call)
            return CONTINUE;
        if (ctx.agent.policy.hitlPolicy === 'permissive')
            return CONTINUE;
        if (!SENSITIVE_TOOLS.has(call.tool))
            return CONTINUE;
        const noteLines = ctx.ledger
            .all()
            .filter((record) => record.type === 'run.note')
            .map((record) => record.payload.text);
        if (hasRecentSensitiveApproval(noteLines))
            return CONTINUE;
        const question = sensitiveConfirmQuestion(call.tool, call.arguments);
        if (!question)
            return CONTINUE;
        const blocked = evaluateAskUser(question, ctx.taskScope, ctx.agent.policy.hitlPolicy);
        if (!blocked.allow) {
            return {
                kind: 'skip_tool',
                note: `ask_user blocked: ${blocked.reason} — "${question}"`,
                blockedAsk: { question, reason: blocked.reason },
            };
        }
        return { kind: 'ask_user', question };
    }
}
export class DuplicateSkillHook {
    name = 'duplicate-skill';
    reads = ['loadedSkillIds'];
    beforeTool(ctx) {
        const call = ctx.toolCall;
        if (call?.tool !== 'skill_load')
            return CONTINUE;
        const requested = typeof call.arguments.id === 'string' ? call.arguments.id : '';
        const id = requested ? bareSkillId(requested) : '';
        if (!id || !ctx.gates.loadedSkillIds.has(id))
            return CONTINUE;
        return {
            kind: 'skip_tool',
            note: `GUIDANCE: skill ${id} already loaded this session; do not reload. Follow-ups: answer from PAGE EVIDENCE / sticky body — intro template only if the user asked to introduce/summarize.`,
            log: `skip duplicate skill_load ${id}`,
            result: { ok: true, data: { skipped: true, id, reason: 'already_loaded' } },
        };
    }
}
export class CspSkipHook {
    name = 'csp-skip';
    reads = ['jsCspBlocked'];
    beforeTool(ctx) {
        const call = ctx.toolCall;
        if (call?.tool !== 'dom_execute_js')
            return CONTINUE;
        if (!ctx.gates.jsCspBlocked.has(ctx.snap.url))
            return CONTINUE;
        return {
            kind: 'skip_tool',
            note: CSP_EXECUTE_JS_HINT,
            log: 'skip execute_js after CSP block',
            result: {
                ok: false,
                error: {
                    code: 'csp_eval_blocked',
                    message: 'page CSP blocked eval on this URL',
                    recoverable: false,
                },
            },
        };
    }
}
export class PageCacheHook {
    name = 'page-cache';
    reads = [{ key: 'taskIntent', optional: true }, 'pageVisits'];
    beforeTool(ctx) {
        const call = ctx.toolCall;
        if (!call || !ctx.snap.url)
            return CONTINUE;
        if (call.tool !== 'tabs_open')
            return CONTINUE;
        const intent = ctx.gates.taskIntent;
        if (intent === 'multi_hop_crawl' || intent === 'research')
            return CONTINUE;
        const url = typeof call.arguments?.url === 'string' ? call.arguments.url.trim() : '';
        if (!url)
            return CONTINUE;
        if (!isRedundantTabsOpen(ctx.gates.pageVisits, url, ctx.snap.url))
            return CONTINUE;
        return {
            kind: 'skip_tool',
            note: 'GUIDANCE: 该 URL 已在当前页或本 run 访问过 — 用 tabs_switch 或 PAGE EVIDENCE 合成，勿重复 tabs_open。',
            log: `skip redundant tabs_open ${url}`,
            result: {
                ok: true,
                data: { skipped: true, reason: 'redundant_tabs_open', url },
            },
        };
    }
    afterTool(ctx) {
        const result = ctx.toolResult;
        const tool = ctx.toolCall?.tool;
        if (!result?.ok || !tool)
            return;
        if (tool === 'dom_read' && ctx.snap.url) {
            recordPageVisit(ctx.gates.pageVisits, ctx.snap.url, ctx.snap.revision);
        }
        if (tool === 'tabs_open') {
            const tr = ctx.toolResult;
            const url = tr?.ok &&
                typeof tr.data === 'object' &&
                tr.data &&
                typeof tr.data.url === 'string'
                ? tr.data.url
                : typeof ctx.toolCall?.arguments?.url === 'string'
                    ? ctx.toolCall.arguments.url
                    : '';
            if (url)
                recordPageVisit(ctx.gates.pageVisits, url);
        }
        if (tool === 'tabs_switch' && ctx.snap.url) {
            recordPageVisit(ctx.gates.pageVisits, ctx.snap.url, ctx.snap.revision);
        }
    }
}
export class ScriptDeliverableStepHook {
    name = 'script-deliverable-step';
    // scriptLoginAskIssued starts undefined (falsy) and this hook both reads
    // and writes it within the same beforeStep call — safe without an earlier writer.
    reads = [{ key: 'deliverable', optional: true }, { key: 'scriptLoginAskIssued', optional: true }];
    writes = ['scriptLoginAskIssued'];
    beforeStep(ctx) {
        if (ctx.gates.deliverable !== 'script')
            return CONTINUE;
        if (ctx.pageState?.role !== 'login')
            return CONTINUE;
        if (ctx.gates.scriptLoginAskIssued)
            return CONTINUE;
        ctx.gates.scriptLoginAskIssued = true;
        return {
            kind: 'ask_user',
            question: 'PAGE STATE 显示登录页。请在浏览器打开可匿名浏览的分类/列表入口，或完成登录后回复「已就绪」。勿反复 dom_navigate。',
        };
    }
}
export class ScriptLoginNavigateHook {
    name = 'script-login-navigate';
    reads = [{ key: 'deliverable', optional: true }];
    beforeTool(ctx) {
        const call = ctx.toolCall;
        if (!call || call.tool !== 'dom_navigate')
            return CONTINUE;
        if (ctx.gates.deliverable !== 'script')
            return CONTINUE;
        if (ctx.pageState?.role !== 'login')
            return CONTINUE;
        const url = typeof call.arguments.url === 'string' ? call.arguments.url : '';
        return {
            kind: 'skip_tool',
            note: 'GUIDANCE: deliverable=script 且 PAGE STATE=login — 禁止 dom_navigate 碰运气。system_ask_user 或换用户给的公开列表 URL。',
            log: `skip dom_navigate on login wall ${url}`,
            result: {
                ok: true,
                data: { skipped: true, reason: 'script_login_navigate', url },
            },
        };
    }
}
export class LoginLinkReadHook {
    name = 'login-link-read';
    // No ctx.gates reads/writes — decides from ctx.pageState / ctx.snap.url only.
    beforeTool(ctx) {
        const call = ctx.toolCall;
        if (!call)
            return CONTINUE;
        if (!shouldSkipLoginLinkRead({
            tool: call.tool,
            args: call.arguments,
            page: ctx.pageState,
            snapUrl: ctx.snap.url,
        })) {
            return CONTINUE;
        }
        return {
            kind: 'skip_tool',
            note: 'GUIDANCE: PAGE STATE role=login。不要再对同一登录页 dom_read links。换公开入口，或 system_ask_user。',
            log: 'skip login link read',
            result: {
                ok: true,
                data: { skipped: true, reason: 'login_page_state', url: ctx.snap.url },
            },
        };
    }
}
export class DeliverableVerifyHook {
    name = 'deliverable-verify';
    reads = [{ key: 'deliverable', optional: true }, 'scriptSaved', 'subtaskEvidenceReady'];
    beforeTool(ctx) {
        const call = ctx.toolCall;
        if (!call || call.tool !== 'system_done')
            return CONTINUE;
        const deliverable = ctx.gates.deliverable ?? resolveDeliverable(ctx.task);
        if (deliverable === 'script' && !ctx.gates.scriptSaved) {
            const result = typeof call.arguments.result === 'string' ? call.arguments.result : '';
            const hasPath = /scripts?\//i.test(result) || /\.py\b/i.test(result);
            if (!hasPath) {
                return {
                    kind: 'skip_tool',
                    note: 'CONSTRAINT: deliverable=script 须先 script_save 成功，再 system_done 附 path。若缺 URL/登录/Network，用 shortfall 模板说明，禁止空完成。',
                    log: 'block system_done without script_save',
                    result: {
                        ok: false,
                        error: {
                            code: 'deliverable_verify',
                            message: 'script deliverable requires script_save before system_done',
                            recoverable: true,
                        },
                    },
                };
            }
        }
        if (deliverable === 'media') {
            const result = typeof call.arguments.result === 'string' ? call.arguments.result : '';
            const hasUrl = /https?:\/\//i.test(result) && /m3u8|mp4|webm|media/i.test(result);
            const hasShortfall = /shortfall|无法|unavailable|缺少|未能|未找到|无.*源/i.test(result);
            const sourceRequired = ctx.taskContract.capabilities.network === 'required';
            const evaluation = evaluateEvidence(ctx.taskContract, ctx.runtimeState.evidence.records);
            const verifiedSource = evaluation.status === 'complete' ||
                ctx.runtimeState.evidence.records.some((item) => item.kind === 'network' && item.source === 'network_media');
            // A URL-shaped string in the model's prose is not provenance.  For the
            // strict smoke task, only Network evidence (or an explicitly structured
            // shortfall) may cross the completion boundary.
            if (sourceRequired && !verifiedSource && !hasShortfall) {
                return {
                    kind: 'skip_tool',
                    note: 'CONSTRAINT: media source evidence is missing — model text alone cannot verify an original playback URL. Retry candidate click + Network, or return an explicit shortfall.',
                    log: 'block unverified media source completion',
                    result: {
                        ok: false,
                        error: {
                            code: 'deliverable_verify',
                            message: 'strict media task requires network_media evidence or explicit shortfall',
                            recoverable: true,
                        },
                    },
                };
            }
            if (!sourceRequired && !hasUrl && !hasShortfall && !ctx.gates.subtaskEvidenceReady) {
                return {
                    kind: 'skip_tool',
                    note: 'CONSTRAINT: deliverable=media — system_done 须含 mediaUrl（m3u8/mp4 等）或明确 shortfall；若仅拿到标题可先 click+network，或 script_save 骨架。',
                    log: 'block vague media system_done',
                    result: {
                        ok: false,
                        error: {
                            code: 'deliverable_verify',
                            message: 'media deliverable needs mediaUrl, spawn evidence, or explicit shortfall',
                            recoverable: true,
                        },
                    },
                };
            }
        }
        return CONTINUE;
    }
}
export class DedupeObservationHook {
    name = 'dedupe-observation';
    reads = ['seenObs', 'dupSkipByKey', 'lastObsByKey', { key: 'deliverable', optional: true }];
    writes = ['dupSkipByKey'];
    beforeTool(ctx) {
        const call = ctx.toolCall;
        if (!call || !ctx.snap.url)
            return CONTINUE;
        const obsKey = observationDedupeKey(call.tool, ctx.snap.url, call.arguments);
        if (!obsKey || !observationAlreadySeen(ctx.gates, obsKey))
            return CONTINUE;
        const n = bumpDuplicateSkip(ctx.gates, obsKey);
        const prior = priorObservation(ctx.gates, obsKey);
        const notes = [
            `GUIDANCE: already have ${call.tool} for this URL; synthesize or open a sibling page — do not call it again`,
        ];
        if (prior)
            notes.push(`EVIDENCE: ${prior.replace(/\s+/g, ' ').slice(0, WORKING_SET.evidenceChars)}`);
        if (n >= 2) {
            const del = ctx.gates.deliverable;
            if (del === 'script') {
                notes.push('CONSTRAINT: 重复观察 — 基于 PAGE STATE/EVIDENCE 调用 script_save，或 system_ask_user / shortfall；禁止空 system_done。');
            }
            else if (del === 'media' || del === 'data') {
                notes.push('CONSTRAINT: 重复观察 — 改用 browser_act click 列表/播放，或 network read mode=media|hls；system_done 须含 mediaUrl/条目或 shortfall。');
            }
            else {
                notes.push('CONSTRAINT: 同一观察已跳过两次。下一步必须 system_done，禁止再调用该工具。');
            }
        }
        const result = {
            ok: true,
            data: {
                skipped: true,
                reason: 'duplicate_observation',
                hint: 'synthesize or open sibling page',
            },
        };
        if (n >= 3) {
            const del = ctx.gates.deliverable;
            const stopResult = del === 'script'
                ? '重复观察已停止。请 script_save（基于已有 PAGE STATE/URL 模式）或 system_done 说明缺登录/Network/公开入口。'
                : del === 'media' || del === 'data'
                    ? '重复观察已停止。请 browser_act click + network media/hls，或 system_done 附 shortfall（可选 workspace script_save 骨架）。'
                    : `同一页重复观察已停止空转。\n${(prior ?? '').slice(0, 2_000)}`;
            const allowContinue = del === 'script' || del === 'media' || del === 'data';
            return {
                kind: 'skip_tool',
                note: notes.join('\n'),
                log: `skip duplicate ${call.tool}`,
                result,
                stop: !allowContinue,
                stopResult,
            };
        }
        return {
            kind: 'skip_tool',
            note: notes.join('\n'),
            log: `skip duplicate ${call.tool}`,
            result,
        };
    }
}
export class ActionLoopHook {
    name = 'action-loop';
    reads = ['actionLoop'];
    beforeTool(ctx) {
        const call = ctx.toolCall;
        if (!call || !ctx.snap.url)
            return CONTINUE;
        const loopKey = actionLoopKey(call.tool, ctx.snap.url, call.arguments);
        const loopDecision = decideActionLoop(ctx.gates.actionLoop, loopKey);
        if (loopDecision === 'allow')
            return CONTINUE;
        const execCount = loopKey ? (ctx.gates.actionLoop.exec.get(loopKey) ?? 0) : 0;
        const notes = [
            `GUIDANCE: ${call.tool} 已在同一页执行 ${execCount} 次；禁止再重复。用已有产物 system_done。`,
        ];
        if (execCount === ctx.agent.limits.sameActionLimit) {
            notes.push('CONSTRAINT: 禁止对同一 URL 重复 screenshot/scroll/snapshot。下一步必须 system_done 或换策略。');
        }
        const result = {
            ok: true,
            data: {
                skipped: true,
                reason: 'action_loop',
                hint: 'use existing artifact or system_done',
            },
        };
        if (loopDecision === 'stop') {
            return {
                kind: 'skip_tool',
                note: notes.join('\n'),
                log: `skip action loop ${call.tool}`,
                result,
                stop: true,
                stopResult: sameActionLoopResult(call.tool, execCount, ctx.agent.opts.locale),
            };
        }
        return {
            kind: 'skip_tool',
            note: notes.join('\n'),
            log: `skip action loop ${call.tool}`,
            result,
        };
    }
}
export class TaskHintHook {
    name = 'task-hint';
    reads = ['taskHintIssued', { key: 'deliverable', optional: true }];
    writes = ['taskHintIssued', 'taskIntent'];
    beforeStep(ctx) {
        if (ctx.gates.taskHintIssued)
            return CONTINUE;
        ctx.gates.taskHintIssued = true;
        const deliverable = ctx.gates.deliverable ?? resolveDeliverable(ctx.task);
        if (deliverable !== 'general')
            return CONTINUE;
        if (!ctx.gates.taskIntent) {
            ctx.gates.taskIntent = resolveTaskIntent(ctx.task);
        }
        for (const note of taskGuidanceNotes(ctx.task, ctx.reuse)) {
            ctx.recordNote(note);
        }
        return CONTINUE;
    }
}
/** Success-path memory: sticky skill, list hints, observation/action-loop counters. */
export class ToolStateHook {
    name = 'tool-state';
    reads = ['actionLoop', 'tabsListProgressUsed', 'seenObs'];
    writes = [
        'lastListHints', 'loadedSkillIds', 'loadedSkillBodies', 'scriptSaved', 'scriptSavePath',
        'runTabIds', 'subtaskEvidenceReady', 'seenObs', 'lastObsByKey', 'tabsListProgressUsed',
        'stepsWithoutNewObs', 'actionLoop',
    ];
    afterTool(ctx) {
        const result = ctx.toolResult;
        const tool = ctx.toolCall?.tool;
        if (!result?.ok || !tool)
            return;
        if (tool === 'dom_read' || tool === 'dom_extract_content' || tool === 'dom_mark_topn') {
            const hints = listHintsFromToolData(result.data);
            recordListHints(ctx.gates, hints);
        }
        if (tool === 'skill_load') {
            const data = result.data;
            if (typeof data.id === 'string') {
                recordLoadedSkill(ctx.gates, data.id, typeof data.body === 'string' ? data.body : undefined);
            }
        }
        if (tool === 'script_save') {
            const path = result.data?.path;
            if (path) {
                ctx.gates.scriptSaved = true;
                ctx.gates.scriptSavePath = path;
                ctx.recordNote(`GUIDANCE: script saved at ${path} — system_done 须引用此 path。`);
            }
        }
        if (tool === 'tabs_open' || tool === 'tabs_switch') {
            const tabId = result.data?.tabId;
            if (typeof tabId === 'number')
                recordRunTab(ctx.gates, tabId);
        }
        if (tool === 'system_spawn_readonly_tasks') {
            const children = result.data
                ?.children ?? [];
            const okCount = children.filter((child) => child.status === 'done' && String(child.result ?? '').trim().length > 0).length;
            if (okCount > 0) {
                ctx.gates.subtaskEvidenceReady = true;
                ctx.recordNote(`GUIDANCE: ${okCount} 个子任务已返回结构化证据；可用 tabs_switch+dom_read 补读未打开的 URL，或直接 system_done 合成对比/答案。`);
            }
        }
        const key = observationDedupeKey(tool, ctx.snap.url, ctx.toolCall?.arguments);
        const skipped = result.data &&
            typeof result.data === 'object' &&
            !Array.isArray(result.data) &&
            result.data.skipped;
        let progressed = false;
        if (!skipped) {
            if (key) {
                progressed = !ctx.gates.seenObs.has(key);
                markObservationSeen(ctx.gates, key, ctx.toolTrace ?? '');
            }
            else if (tool === 'tabs_open' || tool === 'tabs_switch' || tool === 'dom_click') {
                progressed = true;
            }
            else if (tool === 'tabs_list') {
                if (!ctx.gates.tabsListProgressUsed) {
                    ctx.gates.tabsListProgressUsed = true;
                    progressed = true;
                }
            }
            else if (tool === 'dom_execute_js') {
                const payload = result.data;
                progressed = payload?.result != null && payload.result !== '';
            }
        }
        ctx.gates.stepsWithoutNewObs = progressed ? 0 : ctx.gates.stepsWithoutNewObs + 1;
        recordActionLoopSuccess(ctx.gates.actionLoop, actionLoopKey(tool, ctx.snap.url, ctx.toolCall?.arguments));
    }
}
export class NoProgressHook {
    name = 'no-progress';
    reads = ['stepsWithoutNewObs'];
    beforeTool(ctx) {
        if (ctx.gates.stepsWithoutNewObs < 4)
            return CONTINUE;
        const result = hasSynthesisEvidence(ctx.gates)
            ? '已连续多步无新证据，但 CONTEXT 中已有子任务/dom_read/fetch 材料。请直接 system_done 输出对比或答案，勿再 tabs_list 或重复相同工具。'
            : '连续多步未产生新证据。请根据 CONTEXT 中的 OBSERVATION/EVIDENCE 直接 system_done，勿再重复相同工具。';
        return {
            kind: 'stop',
            status: 'error',
            result,
        };
    }
}
export function createRunHooks(sameFailureLimit, extra = [], protocolMaxRetries = 1) {
    const protocol = new ProtocolHook(protocolMaxRetries);
    const tools = new ToolOutcomeHook(new ToolOutcomePolicy(sameFailureLimit));
    // Grouped by function, not by lifecycle phase (several groups mix
    // runTaskPreflight/beforeTool/afterTool hooks). Array order inside and
    // across groups is still the real contract — HookPipeline is first-wins
    // per phase, and runTaskPreflight runs every hook in this order until one
    // returns a result — so a hook that *reads* a gate must appear after
    // whichever hook *writes* it. `validateHookOrdering` (called from
    // `HookPipeline`'s constructor) asserts this from each hook's declared
    // `reads`/`writes`; see docs/BEST_PRACTICES_REVIEW.md section 4 P0 for why
    // this exists (it is a direct response to the deliverable cross-turn
    // drift bug fixed in GENERAL_BROWSER_AGENT_REFACTOR_PHASE_1.md section 9).
    //
    // 1. Availability — is the network plane even usable this run.
    const availabilityHooks = [new NetworkPlaneHealthHook()];
    // 2. Task state establishment — resolve deliverable/intent once,
    //    assemble the working-set prompt. PreflightHook here is the sole
    //    writer of gates.deliverable; everything downstream that reads it
    //    (directly or via the `optional: true` fallback) must stay after it.
    const taskStateHooks = [
        new PreflightHook(),
        new NetworkDegradedToolGateHook(),
        new TaskHintHook(),
        new WorkingSetHook(),
    ];
    // 3. Protocol / error discipline — one-tool-call-per-turn enforcement,
    //    transport error recovery, and the policy ledger for repeated tool
    //    failures.
    const protocolHooks = [protocol, new ModelErrorHook(), tools, new ToolStateHook()];
    // 4. Permissions & safety — capability profile, skill allowlist, HITL
    //    confirmation, duplicate-load/CSP guards. Pure gate checks, no task
    //    narrative state.
    const securityHooks = [
        new RunProfileHook(),
        new SkillAllowlistHook(),
        new SensitiveToolHook(),
        new DuplicateSkillHook(),
        new CspSkipHook(),
    ];
    // 5. Task-specific execution steps — deliverable-aware guidance and
    //    completion gating (script/media SOPs, login-wall handling).
    const executionHooks = [
        new PageCacheHook(),
        new ScriptLoginNavigateHook(),
        new LoginLinkReadHook(),
        new ScriptDeliverableStepHook(),
        new DeliverableVerifyHook(),
        new MediaHarvestMilestoneHook(),
    ];
    // 6. Loop guards — last line of defense against the model repeating
    //    itself with no new evidence.
    const loopGuardHooks = [
        new DedupeObservationHook(),
        new ActionLoopHook(),
        new NoProgressHook(),
    ];
    return {
        pipeline: new HookPipeline([
            ...availabilityHooks,
            ...taskStateHooks,
            ...protocolHooks,
            ...securityHooks,
            ...executionHooks,
            ...loopGuardHooks,
            ...extra,
        ]),
        protocol,
        tools,
    };
}
