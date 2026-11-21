/**
 * 我的时空. One poem is the main thing on the screen ("today"), everything else is a small door under it.
 * Why one and not four equal cards: a child given four equal choices reads a menu, not a place
 * (docs/research/2026-11-11-competitors-and-next-features.md, 二·2.2 and 一·5.6).
 * No score, streak, ranking or "today's task" anywhere; the parent link is not here at all (it sits in the corner).
 */
import { el } from '../core/dom.js';
import { S } from '../strings.js';
import { pickToday, hookOf } from './selectors.js';

export async function home(app) {
  const { store, repo } = app;
  const root = el('section', { class: 'page home' }, el('h1', { class: 'visually-hidden', text: '我的时空' }));
  if (store.get('consent') == null) root.append(consentCard(app, root));

  let works = [];
  try { works = (await repo.works()).filter(w => w.hasLesson); } catch { /* the doors below still work */ }

  const today = pickToday(works, id => store.progressOf(id));
  root.append(today ? todayBlock(today) : el('div', { class: 'today today--empty' },
    el('p', { class: 'soft', text: '这里还在整理，可以先去时间轴看看。' })));

  // Another poem left half-way (only when it is not already the main one): a small line, not a second hero.
  const other = works.map(w => ({ w, p: store.progressOf(w.workId) }))
    .find(x => x.p?.lastStep && x.w.workId !== today?.work.workId);

  root.append(el('nav', { class: 'doors doors--small', 'aria-label': '别的入口' },
    other ? el('a', { class: 'door', href: `#/lesson/${other.w.workId}/${other.p.lastStep}` },
      el('strong', { text: `接着《${other.w.title}》` }), el('span', { text: `上次在“${S.steps[other.p.lastStep]}”` })) : null,
    el('a', { class: 'door', href: '#/timeline' }, el('strong', { text: '找一首诗' }), el('span', { text: '沿着年代，找到那首诗' })),
    el('a', { class: 'door', href: '#/timeline/overview' }, el('strong', { text: '看看全貌' }), el('span', { text: '朝代、诗人、主题，连成一条河' }))));
  return root;
}

function todayBlock({ work, progress }) {
  const hook = hookOf(work);
  const going = progress?.lastStep;
  return el('article', { class: 'today', 'aria-label': `今天：《${work.title}》` },
    el('p', { class: 'today-kicker', text: going ? '接着上次' : '今天读这一首' }),
    el('h2', { class: 'today-title', text: `《${work.title}》` }),
    hook ? el('p', { class: 'today-hook', text: hook }) : null,
    el('div', { class: 'row' },
      going
        ? el('a', { class: 'btn primary', href: `#/lesson/${work.workId}/${going}`, text: `接着走（上次在“${S.steps[going]}”）` })
        : el('a', { class: 'btn primary', href: `#/poem/${work.workId}`, text: '进去看看' }),
      going ? el('a', { class: 'linkline', href: `#/poem/${work.workId}`, text: '先读一遍原文' }) : null));
}

function consentCard(app) {
  const { store } = app;
  const card = el('div', { class: 'card notice', role: 'region', 'aria-label': S.consent.title },
    el('h2', { text: S.consent.title }), el('p', { text: S.consent.body }),
    el('div', { class: 'row' },
      el('button', { class: 'btn primary', type: 'button', text: S.consent.ok, onclick: () => { store.set('consent', 'yes'); card.remove(); app.afterConsent?.(); } }),
      el('button', { class: 'btn', type: 'button', text: S.consent.later, onclick: () => { store.set('consent', 'no'); card.remove(); } })));
  return card;
}
