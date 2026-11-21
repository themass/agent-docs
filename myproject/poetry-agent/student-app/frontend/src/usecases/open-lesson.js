/**
 * 一节课的应用层用例：把「取数据 → 建状态机 → 建资产解析器 → 装 ViewModel」这一整套编排从视图里
 * 搬出来（架构规则 A2：views/ 不得 import data/）。
 *
 * 视图只调用 `openLesson(app, workId)`，拿到一个 ctx；ctx 里没有任何 fetch、没有 store 读取、
 * 没有降级策略——这些在打开时已经算好。这样视图可以对着一个假 ctx 单独渲染，数据源换了也不用动页面。
 */
import { STEPS } from '../core/vocab.js';
import { indexBundle } from '../data/facts.js';
import { loadNarration } from '../data/narration.js';
import { budgetFrom, createAssets } from '../data/assets.js';
import { createSession } from '../lesson/session.js';

/** 打开一节可渲染的课。返回 { ok: true, ctx } 或 { ok: false, reason: 'not-ready' | 'failed', retry }。 */
export async function openLesson(app, workId, step) {
  const { repo, store, tracker, platform } = app;
  let entry, pack, bundle;
  try {
    [entry, pack] = await Promise.all([repo.lesson(workId), repo.pack(workId)]);
    if (!entry) return { ok: false, reason: 'not-ready' };
    bundle = await repo.bundle(entry.bundleHash);
  } catch {
    return { ok: false, reason: 'failed', retry: true };
  }

  const registry = await repo.assets().catch(() => new Map());
  const index = indexBundle(bundle);
  const budget = () => budgetFrom({
    mediaOff: store.get('mediaOff'),
    weak: store.get('net').weak,
    lowMemory: platform.env.lowMemory(),
    reducedMotion: platform.env.reducedMotion(),
  });
  const assets = createAssets({ assets: bundle.assets, registry, budget, assetBase: platform.config.assetBase });
  // line -> narration asset. Optional: without it every line is simply text (which is also the caption).
  const narration = await loadNarration({
    assetBase: platform.config.assetBase, workId, index, bundleAssets: bundle.assets,
  });

  let session;
  try {
    session = createSession({
      bundle, workId, store, track: e => tracker.track(e),
      entry: STEPS.includes(step) ? step : 'read',
    });
  } catch {
    return { ok: false, reason: 'not-ready' };
  }

  return { ok: true, ctx: baseContext({ app, workId, entry, pack, bundle, index, assets, narration, session }) };
}

/**
 * 降级上报：把「为什么降级」翻译成事件词表里的枚举，同一个原因只报一次。
 * 放在应用层而不是视图，因为它是业务规则（哪些降级值得记录），不是画法。
 */
export function createDegradeReporter({ app, workId, session }) {
  const { store, tracker } = app;
  const seen = new Set();
  return why => {
    const mapped = store.get('mediaOff') ? 'user_off'
      : store.get('net').weak ? 'weak_net'
      : app.platform.env.lowMemory() ? 'low_memory'
      : app.platform.env.reducedMotion() ? 'reduced_motion'
      : (why === 'user_off' ? 'user_off' : 'asset_failed');
    if (!seen.has(mapped)) {
      seen.add(mapped);
      tracker.track({ workId, step: session.step, kind: 'media_degraded', ref: mapped });
    }
    return mapped;
  };
}

function baseContext(fields) {
  return fields;
}
