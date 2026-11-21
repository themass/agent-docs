/**
 * 五步学习外壳. Any step can be entered from the rail at any time; previous / skip / exit are always present;
 * no progress bar, no "2/5", no score. If anything needed fails the learner is told in words and the poem
 * stays readable. Step bodies live in lesson-steps.js.
 */
import { el } from '../core/dom.js';
import { STEPS } from '../core/vocab.js';
import { openLesson, createDegradeReporter } from '../usecases/open-lesson.js';
import { renderLines } from '../ui/lines.js';
import { renderMedia } from '../ui/media.js';
import { S } from '../strings.js';
import { renderStep } from './lesson-steps.js';
import { agentBubble } from '../ui/speaker.js';

export async function lesson(app, { workId, step }, { isCurrent }) {
  const { store, tracker } = app;
  const opened = await openLesson(app, workId, step);
  if (!opened.ok) {
    return opened.reason === 'failed'
      ? notReady('这一课没有取到。检查一下网络，或者稍后再试。文字版不受影响。', workId, opened.retry)
      : notReady('这首诗的场景还在整理，先去读原文吧。', workId);
  }
  if (!isCurrent()) return document.createComment('stale');
  const { entry, pack, bundle, index, assets, narration, session } = opened.ctx;
  const reportDegrade = createDegradeReporter({ app, workId, session });

  const poetName = poetNameOf(bundle, pack);
  const banner = el('div', { class: 'banner degrade', hidden: true, role: 'status', text: S.mediaFailed });
  const onDegrade = why => { banner.hidden = false; reportDegrade(why); };

  let tapHandler = () => {};
  const lines = renderLines({ lines: pack.lines, annotations: pack.annotations, pinyin: store.pinyinOn(), showNotes: true,
    onTap: seq => { session.tapLine(seq); tapHandler(seq); } });

  const body = el('div', { class: 'step-body', 'aria-live': 'polite' });
  const rail = el('nav', { class: 'rail', 'aria-label': '五个步骤' });
  const foot = el('div', { class: 'lesson-foot' });
  let cleanup = () => {};

  const env = {
    app, workId, pack, bundle, index, session, lines, assets, poetName, entry, onDegrade, narration,
    setTap: fn => { tapHandler = fn; },
    media: id => renderMedia(assets.resolve(id), { reducedMotion: app.platform.env.reducedMotion(), onDegrade }),
    /** Ask the agent (or the local fallback) and show the answer as a labelled bubble. */
    async ask(action, args, out) {
      // A typed question is the learner's own words: it goes to the agent's /turn and nowhere else, and it is
      // not an event either (events carry a fixed action name, never anything the learner wrote).
      if (action !== 'free_text') session.ask(action);
      out.replaceChildren(el('p', { class: 'soft', text: '…' }));
      const reply = await app.agent.ask({ bundleHash: entry.bundleHash, workId, step: session.step, action, args, index, pack });
      if (reply.degraded_reason && reply.degraded_reason !== 'disabled')
        tracker.track({ workId, step: session.step, kind: 'agent_fallback', ref: reply.degraded_reason });
      out.replaceChildren(agentBubble(reply, { poetName }));
      return reply;
    },
  };

  async function show() {
    cleanup();
    app.platform.audio.stop();                       // narration of the step we just left must not talk over the next one
    lines.setHot([]);
    body.replaceChildren();
    const cur = session.step;
    rail.replaceChildren(...STEPS.map(s => el('button', { class: 'step', type: 'button', 'aria-current': String(s === cur), text: S.steps[s], onclick: () => session.go(s) })));
    body.append(el('p', { class: 'step-hint', text: S.stepHints[cur] }));
    const out = await renderStep(cur, env);
    body.append(out.el);
    cleanup = out.cleanup || (() => {});
    foot.replaceChildren(
      el('button', { class: 'btn', type: 'button', text: S.nav.prev, disabled: cur === STEPS[0], onclick: () => session.prev() }),
      el('button', { class: 'btn', type: 'button', text: S.nav.skip, disabled: cur === STEPS[4], onclick: () => session.skip() }),
      el('button', { class: 'btn primary', type: 'button', id: 'next', text: S.nav.next, disabled: cur === STEPS[4], onclick: onNext }),
      el('a', { class: 'btn', href: `#/poem/${workId}`, text: S.nav.exit, onclick: () => session.exit() }));
  }
  function onNext(e) {
    if (session.shouldNudge(4)) {
      body.prepend(el('p', { class: 'notice', role: 'note', text: S.nudge }));
      e.target.textContent = '还是继续';
      return;
    }
    session.next();
  }
  session.subscribe(show);
  show();

  return el('section', { class: 'page lesson' },
    el('div', { class: 'lesson-top' }, el('a', { class: 'back', href: `#/poem/${workId}`, text: '‹ 诗词页' }), el('strong', { text: pack.title }), rail),
    banner,
    el('div', { class: 'lesson-grid' }, el('aside', { class: 'poem-side' }, lines.el), el('div', { class: 'lesson-main' }, body, foot)),
    el('p', { class: 'coverage', text: session.coverageNotice() || pack.coverageNotice }));
}

function notReady(message, workId, retry) {
  return el('section', { class: 'page' }, el('h1', { text: '这一课还没准备好' }), el('p', { text: message }),
    el('a', { class: 'btn primary', href: `#/poem/${workId}`, text: '去读原文' }),
    retry ? el('button', { class: 'btn', type: 'button', text: '重试', onclick: () => location.reload() }) : null);
}

/** The cast entry names a content id; the poem pack's author list gives the display name. */
export function poetNameOf(bundle, pack) {
  const cid = bundle.cast?.[0]?.content_id;
  return pack.authors?.find(a => a.personId === cid)?.name || pack.authors?.[0]?.name || '诗人';
}
