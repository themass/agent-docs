import type { TraceRecord } from '@naviforge/session'

import {
  evaluateAskUser,
  hasRecentSensitiveApproval,
  sensitiveConfirmQuestion,
  SENSITIVE_TOOLS,
} from '@naviforge/policy'
import type { ToolResult } from '@naviforge/shared'
import { isMcpQualifiedToolName, mcpQualifiedName } from '@naviforge/shared'

import type { AgentCtx } from './agent-ctx.js'
import { formatExtractContentTrace, formatReadPageTrace, isToolAllowed } from './exec-turn.js'
import { CSP_EXECUTE_JS_HINT, ToolOutcomePolicy } from './failure.js'
import {
  CONTINUE,
  HookPipeline,
  ModelErrorHook,
  ProtocolHook,
  ToolOutcomeHook,
  WorkingSetHook,
  type AgentHook,
  type HookDecision,
} from './hooks.js'
import {
  actionLoopKey,
  bareSkillId,
  decideActionLoop,
  isPageReadTask,
  isResearchTask,
  observationDedupeKey,
  recordActionLoopSuccess,
  requestedList,
} from './loop-gates.js'
import {
  bumpDuplicateSkip,
  hasSynthesisEvidence,
  markObservationSeen,
  observationAlreadySeen,
  priorObservation,
  recordListHints,
  recordLoadedSkill,
  recordRunTab,
} from './loop-gate-state.js'
import { formatListResult } from './prompt.js'
import { applyPageSignalsToCtx, formatListPageMediaHint, formatPlaybackCandidatesForHitl, isMediaEvidenceTask, tryMediaPlaybackDeterministicResult } from './page-signals-hydrate.js'
import { applyPageFrictionToCtx } from './page-friction/index.js'
import { listHintsFromToolData, sameActionLoopResult } from './run-limits.js'
import { isRedundantTabsOpen, recordPageVisit } from './page-cache.js'
import { runSiteRecipe } from './recipe-runner.js'
import { hostFromUrl } from './site-recipe.js'
import { intentGuidanceNotes, intentPreflightSkill, resolveTaskIntent } from './task-intent.js'
import { isBulkMdCatalogTask, isCatalogCrawlTask, isSiteCatalogSopTask, resolveTaskMode, taskGuidanceNotes } from './task-classifier.js'
import {
  classifyPageBrief,
  discoverCatalogPage,
  formatCatalogPlanEvidence,
  parseCatalogCrawlSpec,
  runCatalogCrawl,
  runCurrentPageListCrawl,
  selectCatalogStrategy,
  spawnMediaGuidance,
} from './catalog-crawl/index.js'
import { synthesizePreflightResult } from './preflight-synthesize.js'
import { WORKING_SET } from './working-set.js'

function preflightLoadSkill(
  ctx: AgentCtx,
  skillId: string,
  note: string
): void {
  const skill = ctx.skills.find((s) => s.id === skillId)
  if (!skill || ctx.gates.loadedSkillIds.has(skillId)) return
  const header = [
    `# skill:${skill.id}@${skill.version}`,
    skill.description,
    skill.tools?.length ? `Suggested tools (advisory unless hard allowlist): ${skill.tools.join(', ')}` : '',
  ]
    .filter(Boolean)
    .join('\n')
  ctx.gates.loadedSkillBodies.length = 0
  ctx.gates.loadedSkillBodies.push(`${header}\n\n${skill.instructions.trim()}`)
  ctx.gates.loadedSkillIds.add(skillId)
  ctx.recordNote(note)
  ctx.emit(
    ctx.createRecord('tool.result', {
      tool: 'skill_load',
      arguments: { id: skillId, via: 'preflight' },
      ok: true,
      data: { id: skillId, version: skill.version },
    })
  )
}

/** Deterministic DOM reads before the model loop (list extract, top-N mark, page read). */
export class PreflightHook implements AgentHook {
  readonly name = 'preflight'

  async runTaskPreflight(ctx: AgentCtx): Promise<string | undefined> {
    const planes = ctx.agent.planes
    let deterministicResult: string | undefined

    const intent = resolveTaskIntent(ctx.task)
    ctx.gates.taskIntent = intent
    for (const note of intentGuidanceNotes(intent)) ctx.recordNote(note)
    if (intent === 'denied') {
      return 'CONSTRAINT: 任务涉及破解/绕过加密或付费墙，无法执行。请用 system_done 说明合法替代方案。'
    }

    const host = hostFromUrl(ctx.snap.url)
    if (host && planes.recipes && (intent === 'page_download' || intent === 'media_extract')) {
      const recipe = await planes.recipes.find(host, intent)
      if (recipe) {
        ctx.recordNote(`PREFLIGHT: site recipe ${recipe.id} — ${recipe.title}`)
        const ran = await runSiteRecipe({
          recipe,
          dom: planes.dom,
          network: planes.network,
          task: ctx.task,
          url: ctx.snap.url,
          snap: ctx.snap,
        })
        ctx.emit(
          ctx.createRecord('tool.result', {
            tool: 'recipe_run',
            arguments: { id: recipe.id, intent },
            ok: ran.ok,
            ...(ran.ok ? { data: { text: ran.text } } : { error: { code: 'recipe_failed', message: ran.error, recoverable: true } }),
          })
        )
        if (ran.ok) {
          ctx.gates.recipeUsed = true
          ctx.gates.recipeId = recipe.id
          void planes.recipes.bumpSuccess?.(recipe.id)
          ctx.recordNote(`PREFLIGHT: recipe ${recipe.id} ok`)
          return ran.text
        }
        ctx.recordNote(`PREFLIGHT: recipe ${recipe.id} failed (${ran.error}) — fallback skill/LLM`)
      }
    }

    const intentSkill = intentPreflightSkill(intent)
    if (intentSkill) {
      preflightLoadSkill(ctx, intentSkill, `PREFLIGHT: intent=${intent} skill ${intentSkill}`)
    }

    const listRequest = requestedList(ctx.task)
    if (
      listRequest &&
      !listRequest.mark &&
      !isCatalogCrawlTask(ctx.task) &&
      planes.dom.extractContent &&
      !isPageReadTask(ctx.task)
    ) {
      const extracted = await planes.dom.extractContent(listRequest.n)
      ctx.emit(
        ctx.createRecord('tool.result', {
          tool: 'dom_read',
          arguments: { mode: 'list', n: listRequest.n, enforced: true },
          ok: extracted.ok,
          ...(extracted.ok ? { data: extracted.data } : { error: extracted.error }),
        })
      )
      ctx.recordNote(
        extracted.ok
          ? `PREFLIGHT: dom_read list items=${JSON.stringify(extracted.data.items)}${
              extracted.data.shortfall ? ` shortfall=${extracted.data.shortfall}` : ''
            }`
          : `PREFLIGHT: dom_read list failed=${extracted.error.message}`
      )
      if (extracted.ok) {
        ctx.gates.lastListHints = listHintsFromToolData(extracted.data)
        const extractKey = observationDedupeKey('dom_read', ctx.snap.url, { mode: 'list' })
        if (extractKey) {
          markObservationSeen(ctx.gates, extractKey, formatExtractContentTrace(extracted.data))
        }
      }
      ctx.emit(
        ctx.createRecord('run.log', {
          message: extracted.ok
            ? `extract top${listRequest.n}: ${extracted.data.items.length} records (page unchanged)`
            : `extract top${listRequest.n} failed: ${extracted.error.message}`,
        })
      )
      if (extracted.ok && extracted.data.items.length) {
        deterministicResult = formatListResult(extracted.data.items, false, extracted.data.shortfall)
      }
    }

    const topN = listRequest?.mark ? listRequest.n : null
    if (topN !== null && planes.dom.markTopn) {
      const marked = await planes.dom.markTopn(topN)
      ctx.emit(
        ctx.createRecord('tool.result', {
          tool: 'dom_mark_topn',
          arguments: { n: topN, enforced: true },
          ok: marked.ok,
          ...(marked.ok ? { data: marked.data } : { error: marked.error }),
        })
      )
      ctx.recordNote(
        marked.ok
          ? `PREFLIGHT: dom_mark_topn marked=${marked.data.marked} items=${JSON.stringify(marked.data.items)}`
          : `PREFLIGHT: dom_mark_topn failed=${marked.error.message}`
      )
      if (marked.ok) ctx.gates.lastListHints = listHintsFromToolData(marked.data)
      ctx.emit(
        ctx.createRecord('run.log', {
          message: marked.ok
            ? `top${topN} visual mark: ${marked.data.marked}/${topN}`
            : `top${topN} visual mark failed: ${marked.error.message}`,
        })
      )
      if (marked.ok && marked.data.marked) {
        deterministicResult = formatListResult(marked.data.items, true, marked.data.shortfall)
      }
    }

    if (isPageReadTask(ctx.task) && planes.dom.readPage) {
      const readKey = observationDedupeKey('dom_read', ctx.snap.url, { mode: 'body' })
      if (readKey && observationAlreadySeen(ctx.gates, readKey)) {
        const prior = priorObservation(ctx.gates, readKey)
        ctx.recordNote('PREFLIGHT: reuse prior dom_read body for this URL')
        if (prior) ctx.recordNote(`EVIDENCE: ${prior.slice(0, WORKING_SET.evidenceChars)}`)
      } else {
        const read = await planes.dom.readPage()
        ctx.emit(
          ctx.createRecord('tool.result', {
            tool: 'dom_read',
            arguments: { mode: 'body', enforced: true },
            ok: read.ok,
            ...(read.ok ? { data: read.data } : { error: read.error }),
          })
        )
        if (read.ok) {
          ctx.recordNote(`PREFLIGHT: ${formatReadPageTrace(read.data)}`)
          if (readKey) {
            markObservationSeen(ctx.gates, readKey, formatReadPageTrace(read.data))
          }
          ctx.emit(
            ctx.createRecord('run.log', {
              message: `dom_read body: ${read.data.text.length} chars from ${read.data.source}`,
            })
          )
        } else {
          ctx.recordNote(`PREFLIGHT: dom_read body failed=${read.error.message}`)
          ctx.emit(ctx.createRecord('run.log', { message: `dom_read body failed: ${read.error.message}` }))
        }
      }
      const pageRead = ctx.skills.find((s) => s.id === 'page-read')
      if (pageRead && !ctx.gates.loadedSkillIds.has('page-read')) {
        preflightLoadSkill(ctx, 'page-read', 'PREFLIGHT: skill page-read (READ done template)')
      }
    }

    if (isResearchTask(ctx.task) && !isPageReadTask(ctx.task) && !isBulkMdCatalogTask(ctx.task)) {
      preflightLoadSkill(ctx, 'research-compare', 'PREFLIGHT: skill research-compare (off-page compare)')
    }

    if (isSiteCatalogSopTask(ctx.task)) {
      preflightLoadSkill(ctx, 'catalog-crawl-sop', 'PREFLIGHT: skill catalog-crawl-sop (site catalog SOP)')
    }

    if (resolveTaskMode(ctx.task) === 'in_page') {
      const friction = await applyPageFrictionToCtx(ctx, {
        bodyText: ctx.snap.content,
        skipJs: !ctx.agent.policy.allowDomInject,
      })
      if (friction.report?.blocking) {
        preflightLoadSkill(ctx, 'page-friction', 'PREFLIGHT: skill page-friction (universal session gate)')
      }
    }

    const catalogTask = isCatalogCrawlTask(ctx.task) || isSiteCatalogSopTask(ctx.task)
    const spec = catalogTask ? parseCatalogCrawlSpec(ctx.task) : null
    const discover = catalogTask && planes.dom.executeJs ? await discoverCatalogPage(planes.dom) : null

    if (resolveTaskMode(ctx.task) === 'in_page' && planes.dom.collectPageSignalRaw) {
      const bundle = await applyPageSignalsToCtx(ctx)
      const brief = discover ? classifyPageBrief(discover, bundle) : null

      if (brief) {
        ctx.recordNote(
          `PREFLIGHT: page role=${brief.role} confidence=${brief.confidence.toFixed(2)} detailShape=${brief.detailShape ?? '(none)'} items=${brief.listItemCount}`
        )
        if (bundle) {
          const listHint = formatListPageMediaHint(bundle, ctx.task, brief)
          if (listHint) ctx.recordNote(`GUIDANCE: ${listHint}`)
        }
      }

      const strategy =
        discover && spec && brief
          ? selectCatalogStrategy({
              task: ctx.task,
              brief,
              fullSiteCrawl: isCatalogCrawlTask(ctx.task),
              wantsMedia: spec.wantsMediaUrl,
            })
          : undefined

      let mediaPlayback: string | undefined
      if (bundle) {
        if (catalogTask && strategy) {
          mediaPlayback = tryMediaPlaybackDeterministicResult(bundle, ctx.task, { strategy })
        } else if (!catalogTask) {
          mediaPlayback = tryMediaPlaybackDeterministicResult(bundle, ctx.task)
        }
      }

      let catalogCrawl = null as Awaited<ReturnType<typeof runCatalogCrawl>> | null
      let spawnGuidance: string | undefined

      if (catalogTask && spec && discover && strategy) {
        ctx.recordNote(
          `PREFLIGHT: catalog strategy=${strategy} pages/section=${spec.pagesPerSection} media=${spec.wantsMediaUrl}`
        )

        if (strategy === 'full-catalog') {
          catalogCrawl = await runCatalogCrawl(ctx, spec)
        } else if (strategy === 'current-page-list' || strategy === 'spawn-media') {
          catalogCrawl = await runCurrentPageListCrawl(ctx, spec, discover, {
            resolveMedia: strategy === 'current-page-list',
          })
          if (strategy === 'spawn-media' && catalogCrawl) {
            const count = catalogCrawl.sections.reduce(
              (n, s) => n + s.pages.reduce((m, p) => m + p.entries.length, 0),
              0
            )
            if (count > 0) spawnGuidance = spawnMediaGuidance(count)
          }
        }

        if (catalogCrawl) {
          if (catalogCrawl.authBlocked) {
            preflightLoadSkill(ctx, 'page-friction', 'PREFLIGHT: skill page-friction (blocked by session gate)')
            ctx.recordNote(
              'EVIDENCE: PAGE_FRICTION blocked catalog-crawl — user login or system_captcha_wait required'
            )
          }
          ctx.recordNote(
            `EVIDENCE: ${formatCatalogPlanEvidence(catalogCrawl.plan).slice(0, WORKING_SET.evidenceChars)}`
          )
          ctx.emit(
            ctx.createRecord('run.log', {
              message: `catalog-crawl ${catalogCrawl.complete ? 'complete' : 'partial'} strategy=${strategy} sections=${catalogCrawl.sections.length}`,
            })
          )
        }
      }

      const synthesized = synthesizePreflightResult({
        strategy: strategy ?? 'delegate-model',
        mediaPlayback,
        catalogCrawl,
        spawnGuidance,
      })
      if (synthesized) deterministicResult = synthesized
      else if (bundle && isMediaEvidenceTask(ctx.task)) {
        const hitl = formatPlaybackCandidatesForHitl(bundle)
        if (hitl) ctx.recordNote(`EVIDENCE: ${hitl}`)
      }
    } else if (catalogTask && spec && discover) {
      const brief = classifyPageBrief(discover, null)
      const strategy = selectCatalogStrategy({
        task: ctx.task,
        brief,
        fullSiteCrawl: isCatalogCrawlTask(ctx.task),
        wantsMedia: spec.wantsMediaUrl,
      })
      ctx.recordNote(
        `PREFLIGHT: catalog strategy=${strategy} (no PAGE SIGNALS collection)`
      )
    }

    return deterministicResult
  }
}

export class SkillAllowlistHook implements AgentHook {
  readonly name = 'skill-allowlist'

  beforeTool(ctx: AgentCtx): HookDecision {
    const tool = ctx.toolCall?.tool
    if (!tool || isToolAllowed(tool, ctx.allowedTools)) return CONTINUE
    return {
      kind: 'skip_tool',
      note: `${tool} fail denied by skill permissions`,
      privacy: {
        tool,
        code: 'skill_allowlist',
        hint: `当前 Skill 未授权 ${tool}，本次调用已拦截。可在设置中关闭「Skill 硬白名单」。`,
      },
    }
  }
}

/** Hard capability boundary for leaf runs; unlike skill allowlists, no system-tool bypass exists. */
export class RunProfileHook implements AgentHook {
  readonly name = 'run-profile'

  beforeTool(ctx: AgentCtx): HookDecision {
    const tool = ctx.toolCall?.tool
    const profile = ctx.agent.profile
    if (!tool || !profile) return CONTINUE
    const readonlyMcp =
      profile.allowReadonlyMcp &&
      isMcpQualifiedToolName(tool) &&
      ctx.agent.mcpTools.some(
        (candidate) =>
          candidate.readonly &&
          tool === mcpQualifiedName(candidate.serverId, candidate.name)
      )
    if (profile.allowedTools.includes(tool) || readonlyMcp) return CONTINUE
    return {
      kind: 'skip_tool',
      note: `${tool} denied by ${profile.name} capability profile`,
      result: {
        ok: false,
        error: { code: 'capability_denied', message: `${tool} is not allowed for ${profile.name}`, recoverable: false },
      },
    }
  }
}

export class SensitiveToolHook implements AgentHook {
  readonly name = 'sensitive-tool'

  beforeTool(ctx: AgentCtx): HookDecision {
    const call = ctx.toolCall
    if (!call) return CONTINUE
    if (ctx.agent.policy.hitlPolicy === 'permissive') return CONTINUE
    if (!SENSITIVE_TOOLS.has(call.tool)) return CONTINUE
    const noteLines = ctx.ledger
      .all()
      .filter((record): record is Extract<TraceRecord, { type: 'run.note' }> => record.type === 'run.note')
      .map((record) => record.payload.text)
    if (hasRecentSensitiveApproval(noteLines)) return CONTINUE
    const question = sensitiveConfirmQuestion(call.tool, call.arguments)
    if (!question) return CONTINUE
    const blocked = evaluateAskUser(question, ctx.taskScope, ctx.agent.policy.hitlPolicy)
    if (!blocked.allow) {
      return {
        kind: 'skip_tool',
        note: `ask_user blocked: ${blocked.reason} — "${question}"`,
        blockedAsk: { question, reason: blocked.reason },
      }
    }
    return { kind: 'ask_user', question }
  }
}

export class DuplicateSkillHook implements AgentHook {
  readonly name = 'duplicate-skill'

  beforeTool(ctx: AgentCtx): HookDecision {
    const call = ctx.toolCall
    if (call?.tool !== 'skill_load') return CONTINUE
    const requested = typeof call.arguments.id === 'string' ? call.arguments.id : ''
    const id = requested ? bareSkillId(requested) : ''
    if (!id || !ctx.gates.loadedSkillIds.has(id)) return CONTINUE
    return {
      kind: 'skip_tool',
      note: `GUIDANCE: skill ${id} already loaded this session; do not reload. Follow-ups: answer from PAGE EVIDENCE / sticky body — intro template only if the user asked to introduce/summarize.`,
      log: `skip duplicate skill_load ${id}`,
      result: { ok: true, data: { skipped: true, id, reason: 'already_loaded' } },
    }
  }
}

export class CspSkipHook implements AgentHook {
  readonly name = 'csp-skip'

  beforeTool(ctx: AgentCtx): HookDecision {
    const call = ctx.toolCall
    if (call?.tool !== 'dom_execute_js') return CONTINUE
    if (!ctx.gates.jsCspBlocked.has(ctx.snap.url)) return CONTINUE
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
    }
  }
}

export class PageCacheHook implements AgentHook {
  readonly name = 'page-cache'

  beforeTool(ctx: AgentCtx): HookDecision {
    const call = ctx.toolCall
    if (!call || !ctx.snap.url) return CONTINUE
    if (call.tool !== 'tabs_open') return CONTINUE
    const intent = ctx.gates.taskIntent
    if (intent === 'multi_hop_crawl' || intent === 'research') return CONTINUE
    const url = typeof call.arguments?.url === 'string' ? call.arguments.url.trim() : ''
    if (!url) return CONTINUE
    if (!isRedundantTabsOpen(ctx.gates.pageVisits, url, ctx.snap.url)) return CONTINUE
    return {
      kind: 'skip_tool',
      note: 'GUIDANCE: 该 URL 已在当前页或本 run 访问过 — 用 tabs_switch 或 PAGE EVIDENCE 合成，勿重复 tabs_open。',
      log: `skip redundant tabs_open ${url}`,
      result: {
        ok: true,
        data: { skipped: true, reason: 'redundant_tabs_open', url },
      },
    }
  }

  afterTool(ctx: AgentCtx): void {
    const result = ctx.toolResult
    const tool = ctx.toolCall?.tool
    if (!result?.ok || !tool) return
    if (tool === 'dom_read' && ctx.snap.url) {
      recordPageVisit(ctx.gates.pageVisits, ctx.snap.url, ctx.snap.revision)
    }
    if (tool === 'tabs_open') {
      const url =
        typeof ctx.toolResult?.data === 'object' &&
        ctx.toolResult.data &&
        typeof (ctx.toolResult.data as { url?: unknown }).url === 'string'
          ? (ctx.toolResult.data as { url: string }).url
          : typeof ctx.toolCall?.arguments?.url === 'string'
            ? ctx.toolCall.arguments.url
            : ''
      if (url) recordPageVisit(ctx.gates.pageVisits, url)
    }
    if (tool === 'tabs_switch' && ctx.snap.url) {
      recordPageVisit(ctx.gates.pageVisits, ctx.snap.url, ctx.snap.revision)
    }
  }
}

export class DedupeObservationHook implements AgentHook {
  readonly name = 'dedupe-observation'

  beforeTool(ctx: AgentCtx): HookDecision {
    const call = ctx.toolCall
    if (!call || !ctx.snap.url) return CONTINUE
    const obsKey = observationDedupeKey(call.tool, ctx.snap.url, call.arguments)
    if (!obsKey || !observationAlreadySeen(ctx.gates, obsKey)) return CONTINUE
    const n = bumpDuplicateSkip(ctx.gates, obsKey)
    const prior = priorObservation(ctx.gates, obsKey)
    const notes = [
      `GUIDANCE: already have ${call.tool} for this URL; synthesize or open a sibling page — do not call it again`,
    ]
    if (prior) notes.push(`EVIDENCE: ${prior.replace(/\s+/g, ' ').slice(0, WORKING_SET.evidenceChars)}`)
    if (n >= 2) {
      notes.push('CONSTRAINT: 同一观察已跳过两次。下一步必须 system_done，禁止再调用该工具。')
    }
    const result: ToolResult = {
      ok: true,
      data: {
        skipped: true,
        reason: 'duplicate_observation',
        hint: 'synthesize or open sibling page',
      },
    }
    if (n >= 3) {
      return {
        kind: 'skip_tool',
        note: notes.join('\n'),
        log: `skip duplicate ${call.tool}`,
        result,
        stop: true,
        stopResult: `同一页重复观察已停止空转。\n${(prior ?? '').slice(0, 2_000)}`,
      }
    }
    return {
      kind: 'skip_tool',
      note: notes.join('\n'),
      log: `skip duplicate ${call.tool}`,
      result,
    }
  }
}

export class ActionLoopHook implements AgentHook {
  readonly name = 'action-loop'

  beforeTool(ctx: AgentCtx): HookDecision {
    const call = ctx.toolCall
    if (!call || !ctx.snap.url) return CONTINUE
    const loopKey = actionLoopKey(call.tool, ctx.snap.url, call.arguments)
    const loopDecision = decideActionLoop(ctx.gates.actionLoop, loopKey)
    if (loopDecision === 'allow') return CONTINUE
    const execCount = loopKey ? (ctx.gates.actionLoop.exec.get(loopKey) ?? 0) : 0
    const notes = [
      `GUIDANCE: ${call.tool} 已在同一页执行 ${execCount} 次；禁止再重复。用已有产物 system_done。`,
    ]
    if (execCount === ctx.agent.limits.sameActionLimit) {
      notes.push('CONSTRAINT: 禁止对同一 URL 重复 screenshot/scroll/snapshot。下一步必须 system_done 或换策略。')
    }
    const result: ToolResult = {
      ok: true,
      data: {
        skipped: true,
        reason: 'action_loop',
        hint: 'use existing artifact or system_done',
      },
    }
    if (loopDecision === 'stop') {
      return {
        kind: 'skip_tool',
        note: notes.join('\n'),
        log: `skip action loop ${call.tool}`,
        result,
        stop: true,
        stopResult: sameActionLoopResult(call.tool, execCount, ctx.agent.opts.locale),
      }
    }
    return {
      kind: 'skip_tool',
      note: notes.join('\n'),
      log: `skip action loop ${call.tool}`,
      result,
    }
  }
}

export class TaskHintHook implements AgentHook {
  readonly name = 'task-hint'

  beforeStep(ctx: AgentCtx): HookDecision {
    if (ctx.gates.taskHintIssued) return CONTINUE
    ctx.gates.taskHintIssued = true
    if (!ctx.gates.taskIntent) {
      ctx.gates.taskIntent = resolveTaskIntent(ctx.task)
    }
    for (const note of taskGuidanceNotes(ctx.task, ctx.reuse)) {
      ctx.recordNote(note)
    }
    return CONTINUE
  }
}

/** Success-path memory: sticky skill, list hints, observation/action-loop counters. */
export class ToolStateHook implements AgentHook {
  readonly name = 'tool-state'

  afterTool(ctx: AgentCtx): void {
    const result = ctx.toolResult
    const tool = ctx.toolCall?.tool
    if (!result?.ok || !tool) return
    if (tool === 'dom_read' || tool === 'dom_mark_topn') {
      const hints = listHintsFromToolData(result.data)
      recordListHints(ctx.gates, hints)
    }
    if (tool === 'skill_load') {
      const data = result.data as { body?: unknown; id?: unknown }
      if (typeof data.id === 'string') {
        recordLoadedSkill(
          ctx.gates,
          data.id,
          typeof data.body === 'string' ? data.body : undefined
        )
      }
    }
    if (tool === 'tabs_open' || tool === 'tabs_switch') {
      const tabId = (result.data as { tabId?: number } | undefined)?.tabId
      if (typeof tabId === 'number') recordRunTab(ctx.gates, tabId)
    }
    if (tool === 'system_spawn_readonly_tasks') {
      const children =
        (result.data as { children?: Array<{ status?: string; result?: string }> } | undefined)
          ?.children ?? []
      const okCount = children.filter(
        (child) => child.status === 'done' && String(child.result ?? '').trim().length > 0
      ).length
      if (okCount > 0) {
        ctx.gates.subtaskEvidenceReady = true
        ctx.recordNote(
          `GUIDANCE: ${okCount} 个子任务已返回结构化证据；可用 tabs_switch+dom_read 补读未打开的 URL，或直接 system_done 合成对比/答案。`
        )
      }
    }
    const key = observationDedupeKey(tool, ctx.snap.url, ctx.toolCall?.arguments)
    const skipped =
      result.data &&
      typeof result.data === 'object' &&
      !Array.isArray(result.data) &&
      (result.data as { skipped?: boolean }).skipped
    let progressed = false
    if (!skipped) {
      if (key) {
        progressed = !ctx.gates.seenObs.has(key)
        markObservationSeen(ctx.gates, key, ctx.toolTrace ?? '')
      } else if (tool === 'tabs_open' || tool === 'tabs_switch' || tool === 'dom_click') {
        progressed = true
      } else if (tool === 'tabs_list') {
        if (!ctx.gates.tabsListProgressUsed) {
          ctx.gates.tabsListProgressUsed = true
          progressed = true
        }
      } else if (tool === 'dom_execute_js') {
        const payload = result.data as { result?: unknown } | undefined
        progressed = payload?.result != null && payload.result !== ''
      }
    }
    ctx.gates.stepsWithoutNewObs = progressed ? 0 : ctx.gates.stepsWithoutNewObs + 1
    recordActionLoopSuccess(ctx.gates.actionLoop, actionLoopKey(tool, ctx.snap.url, ctx.toolCall?.arguments))
  }
}

export class NoProgressHook implements AgentHook {
  readonly name = 'no-progress'

  beforeTool(ctx: AgentCtx): HookDecision {
    if (ctx.gates.stepsWithoutNewObs < 4) return CONTINUE
    const result = hasSynthesisEvidence(ctx.gates)
      ? '已连续多步无新证据，但 CONTEXT 中已有子任务/dom_read/fetch 材料。请直接 system_done 输出对比或答案，勿再 tabs_list 或重复相同工具。'
      : '连续多步未产生新证据。请根据 CONTEXT 中的 OBSERVATION/EVIDENCE 直接 system_done，勿再重复相同工具。'
    return {
      kind: 'stop',
      status: 'error',
      result,
    }
  }
}

export function createRunHooks(
  sameFailureLimit: number,
  extra: readonly AgentHook[] = [],
  protocolMaxRetries = 1
): {
  pipeline: HookPipeline
  protocol: ProtocolHook
  tools: ToolOutcomeHook
} {
  const protocol = new ProtocolHook(protocolMaxRetries)
  const tools = new ToolOutcomeHook(new ToolOutcomePolicy(sameFailureLimit))
  return {
    pipeline: new HookPipeline([
      new PreflightHook(),
      new TaskHintHook(),
      new WorkingSetHook(),
      protocol,
      new ModelErrorHook(),
      tools,
      new ToolStateHook(),
      new RunProfileHook(),
      new SkillAllowlistHook(),
      new SensitiveToolHook(),
      new DuplicateSkillHook(),
      new CspSkipHook(),
      new PageCacheHook(),
      new DedupeObservationHook(),
      new ActionLoopHook(),
      new NoProgressHook(),
      ...extra,
    ]),
    protocol,
    tools,
  }
}
