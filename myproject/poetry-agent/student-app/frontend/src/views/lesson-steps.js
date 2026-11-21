/**
 * The five step bodies. Every one returns { el, cleanup? }. Rules each step keeps:
 *  - the words are on screen as text first; media only adds to them;
 *  - nothing is required: no step waits for a click on another before it can be left;
 *  - anything the app says about the poem or history comes from the bundle / pack / agent, not from here.
 */
import { el } from '../core/dom.js';
import { S } from '../strings.js';
import { spoken, DRAMATIZATION_TAG } from '../ui/trust.js';
import { speakerBar } from '../ui/speaker.js';
import { groupsOf, situationOf } from './selectors.js';
import { mountCharacter } from '../character/mount.js';
import { retellLength } from './selectors.js';
import { showCitations } from './poem.js';
import { askBox } from '../ui/ask-box.js';

/**
 * A spoken line, plus a 「听」 button when this line has narration the device is allowed to play. The text is the
 * caption and is always there. If the sound cannot start (blocked, missing, undecodable) the button says so in words
 * and points at the text; it never leaves a silent player. Audio dropped by the budget (weak network, media off) shows
 * no button at all: that is the expected state, not a failure.
 */
function voiced(env, fact, opts = {}) {
  const row = spoken(fact, { onBasis: onBasis(env), ...opts });
  const assetId = env.narration?.get(fact.id);
  if (!row || !assetId) return row;
  const r = env.assets.resolve(assetId);
  if (r.mode !== 'audio' || !r.url) return row;
  const note = el('span', { class: 'soft voice-note', role: 'status' });
  const btn = el('button', { class: 'btn voice', type: 'button', 'aria-label': '听这一句', text: '听' });
  btn.addEventListener('click', async () => {
    note.textContent = '';
    try { await env.app.platform.audio.play(r.url); }
    catch { note.textContent = '声音没放出来，上面的文字就是字幕。'; env.onDegrade('asset_failed'); }
  });
  row.append(' ', btn);
  if (env.app.store.get('source') === 'demo-fixture') row.append(el('span', { class: 'tag tag--placeholder', text: '占位配音' }));
  row.append(note);
  return row;
}

export async function renderStep(step, env) {
  return ({ read, arrive, meet, return: back, recite })[step](env);
}

const onBasis = env => line => line.claimId && showCitations(env.app, line.claimId);

/* ---------------------------------------------------------------- 读 */
function read(env) {
  const picked = el('p', { class: 'soft', 'aria-live': 'polite' });
  env.setTap(seq => {
    env.app.store.patchProgress(env.workId, { askedLine: seq });
    picked.textContent = `你想弄清楚的是第 ${seq} 句。`;
  });
  return { el: el('div', { class: 'step read' }, el('h2', { text: '你最想弄清楚哪一句？' }),
    el('p', { text: '点一下诗里的那一句，会出现它的字词说明。也可以直接下一步。' }), picked) };
}

/* ---------------------------------------------------------------- 到 */
function arrive(env) {
  const root = el('div', { class: 'step arrive' });
  const groups = ['SCENE', 'CITY', 'WORLD', 'PERSON'].map(layer => groupsOf(env.index, 'arrive', 'narrator').find(g => g.layer === layer)).filter(Boolean);
  const cards = new Map();
  const situation = situationOf(env.bundle, groups.map(g => g.layer));

  for (const g of groups) {
    const out = el('div', { class: 'ask-out' });
    const facts = g.facts;
    const card = el('details', { class: 'layer-card', dataset: { layer: g.layer } }, el('summary', { text: S.layers[g.layer] }));
    let opened = false;
    card.addEventListener('toggle', () => {
      if (!card.open) return;
      env.lines.setHot(g.seqs);
      if (!opened) { opened = true; env.session.openLayer(g.layer); }
    });
    for (const id of g.assets) { const m = env.media(id); if (m) card.append(m); }
    for (const f of facts) card.append(voiced(env, f));
    if (!facts.length) card.append(el('p', { class: 'soft', text: '这一层暂时没有内容。' }));
    card.append(el('div', { class: 'asks' },
      g.seqs.length ? el('button', { class: 'linkline', type: 'button', text: '↳ 回到诗句看一眼', onclick: () => env.lines.setHot(g.seqs, { scroll: true }) }) : null,
      el('button', { class: 'btn', type: 'button', text: '换个说法', onclick: () => env.ask('rephrase', { layer: g.layer, ref: facts[0]?.id }, out) }),
      el('button', { class: 'btn', type: 'button', text: '这有根据吗', onclick: () => env.ask('basis', { layer: g.layer, ref: facts[0]?.id }, out) })), out);
    cards.set(g.layer, card);
    if (situation) card.hidden = true;                  // 有处境时先只露一句，四层等学生自己点开
    root.append(card);
  }
  if (!groups.length) root.append(el('p', { class: 'soft', text: '这一步暂时没有内容，可以直接去下一步。' }));

  if (situation) root.prepend(situationBlock(env, situation, cards));
  if (groups.length) root.append(askBox({ ask: env.ask }));
  return { el: root };
}

/**
 * 处境句：在四层并列之前，先给一个"你在这里"的位置，并把先看哪儿交给学生。
 * 三种情况下页面照常工作：没有 situation（旧 bundle）、有 situation 但所有 choice 指向的层都不存在、
 * 学生不点任何 choice（四层仍然可以自己展开）。所以它不是入口闸门，只是一句话 + 几个指路。
 */
function situationBlock(env, situation, cards) {
  const choices = (situation.choices || []).filter(c => cards.has(c.layer));
  const row = el('div', { class: 'choices' });
  const open = layer => {
    const card = cards.get(layer);
    if (!card) return;
    card.hidden = false;
    card.open = true;
    card.scrollIntoView?.({ block: 'nearest' });
  };
  for (const c of choices) row.append(el('button', { class: 'btn', type: 'button', text: c.label, onclick: () => open(c.layer) }));
  if (choices.length >= 2) row.append(el('button', { class: 'linkline', type: 'button', text: '都打开', onclick: () => choices.forEach(c => open(c.layer)) }));
  const block = el('div', { class: 'situation card' },
    spoken(situation, { onBasis: onBasis(env) }),
    el('p', { class: 'situation-ask', text: '先看哪儿？' }), row);
  return block;
}

/* ---------------------------------------------------------------- 见 */
function meet(env) {
  const root = el('div', { class: 'step meet' }, speakerBar({ role: 'poet', name: env.poetName }));
  const stage = el('div', { class: 'stage' });
  const out = el('div', { class: 'ask-out' });
  const seal = () => { stage.replaceChildren(el('div', { class: 'seal big', 'aria-hidden': 'true', text: env.poetName.slice(0, 1) })); };
  let character = null;

  const groups = groupsOf(env.index, 'meet', 'poet');
  const facts = groups.flatMap(g => g.facts);
  const avatarId = env.bundle.cast?.[0]?.avatar_asset || groups.flatMap(g => g.assets)[0];
  const r = avatarId ? env.assets.resolve(avatarId) : null;

  // Ladder: animated character -> the still picture -> the name seal. Each rung that fails drops to the next,
  // and the lines the poet speaks are on screen as text the whole time.
  function showStill(resolved, why) {
    if (!resolved || resolved.mode !== 'image' || !resolved.url) { seal(); env.onDegrade(why); return; }
    const img = el('img', { src: resolved.url, alt: '诗人的示意图，是后人想象的样子，不是画像', style: 'width:100%;height:100%;object-fit:contain' });
    img.addEventListener('error', () => { seal(); env.onDegrade('asset_failed'); });
    stage.replaceChildren(img);
    if (resolved.degraded || why) env.onDegrade(resolved.reason || why || 'budget');
  }
  if (r?.mode === 'character' && r.url) {
    mountCharacter({ host: stage, manifestUrl: r.url, reducedMotion: env.app.platform.env.reducedMotion(),
      onFail: () => showStill(env.assets.resolve(avatarId, { forceLevel: 'L1' }), 'asset_failed') })
      .then(c => { character = c; });
  } else if (r?.mode === 'image') {
    showStill(r, null);      // the budget already ruled out the animation (reduced motion / weak network / low memory)
  } else {
    seal();
    if (r?.degraded) env.onDegrade(r.reason || 'asset_failed');
  }
  root.append(stage, el('p', { class: 'depiction soft', text: S.depiction }));

  for (const f of facts) root.append(voiced(env, f, { who: env.poetName }));
  if (!facts.length) root.append(el('p', { class: 'soft', text: '这一位诗人的话还在整理，先看看“到”里的四个地方。' }));
  root.append(el('div', { class: 'asks' },
    el('button', { class: 'btn', type: 'button', text: '听他说', onclick: () => character?.talk(Math.min(6000, 400 + facts.reduce((n, f) => n + f.text.length, 0) * 160)) }),
    el('button', { class: 'btn', type: 'button', text: '这有根据吗', onclick: () => env.ask('basis', { ref: facts[0]?.id }, out) }),
    el('button', { class: 'btn', type: 'button', text: '换个说法', onclick: () => env.ask('rephrase', { ref: facts[0]?.id }, out) })), out);
  root.append(askBox({ ask: env.ask, label: '想问他什么' }));
  return { el: root, cleanup: () => character?.destroy() };
}

/* ---------------------------------------------------------------- 回 */
function back(env) {
  const root = el('div', { class: 'step return' }, el('h2', { text: '这一句，和刚才哪件事有关？' }));
  const panel = el('div', { class: 'related' });
  const out = el('div', { class: 'ask-out' });
  const asked = env.app.store.progressOf(env.workId)?.askedLine;

  function show(seq) {
    panel.replaceChildren();
    env.lines.select(seq); env.lines.setHot([seq]);
    const facts = env.index.groups.filter(g => g.owner === 'narrator' && (g.step === 'return' || g.step === 'arrive') && g.seqs.includes(seq)).flatMap(g => g.facts);
    const bgs = env.pack.backgrounds.filter(b => env.pack.relations.some(r => r.backgroundId === b.id && r.lineSeq === seq));
    for (const f of facts) panel.append(voiced(env, f));
    for (const b of bgs) {
      const seqs = env.pack.relations.filter(r => r.backgroundId === b.id).map(r => r.lineSeq);
      panel.append(el('div', { class: 'card' }, el('strong', { text: S.layers[b.layer] }), el('p', { text: b.body }),
        el('button', { class: 'linkline', type: 'button', text: `↳ 也对应第 ${seqs.join('、')} 句`, onclick: () => env.lines.setHot(seqs, { scroll: true }) })));
    }
    if (!facts.length && !bgs.length) panel.append(el('p', { class: 'soft', text: '这条背景暂时没绑定诗句，读读上下句试试。' }));
    panel.append(el('div', { class: 'asks' },
      el('button', { class: 'btn', type: 'button', text: '这个字词什么意思', onclick: () => env.ask('hint', { line_seq: seq }, out) }),
      el('button', { class: 'btn', type: 'button', text: '换个说法', onclick: () => env.ask('rephrase', { line_seq: seq, ref: facts[0]?.id }, out) })));
  }
  env.setTap(show);
  root.append(el('p', { text: '点左边（或上面）的一句诗。' }), panel, out, askBox({ ask: env.ask }));
  if (asked) show(asked);
  return { el: root };
}

/* ---------------------------------------------------------------- 诵 */
function recite(env) {
  const root = el('div', { class: 'step recite' });
  const out = el('div', { class: 'ask-out' });
  const demo = env.bundle.steps.find(s => s.step === 'recite')?.demo_audio;
  const r = demo ? env.assets.resolve(demo) : null;
  const audioBar = el('div', { class: 'audio' });
  if (r?.mode === 'audio' && r.url) {
    const btn = el('button', { class: 'btn', type: 'button', text: '听一遍示范', onclick: () => env.app.platform.audio.play(r.url).catch(() => env.onDegrade('asset_failed')) });
    audioBar.append(btn, el('button', { class: 'btn', type: 'button', text: '停', onclick: () => env.app.platform.audio.stop() }));
  } else {
    audioBar.append(el('p', { class: 'soft', text: '示范音频暂时没有，先照着诗句一句一句读，逗号处停一停。' }));
    if (demo) env.onDegrade(r?.reason || 'asset_failed');
  }
  const follow = el('button', { class: 'btn', type: 'button', text: '跟着读：下一句' });
  let at = 0;
  follow.addEventListener('click', () => { const l = env.pack.lines[at % env.pack.lines.length]; env.lines.setHot([l.seq], { scroll: true }); follow.textContent = `跟着读：下一句（刚读到第 ${l.seq} 句）`; at++; });
  root.append(el('h2', { text: '读一读' }), audioBar, follow,
    el('button', { class: 'btn', type: 'button', text: '节奏提示', onclick: () => env.ask('recite_prompt', { line_seq: env.pack.lines[0]?.seq }, out) }), out, retell(env));
  return { el: root };
}

function retell(env) {
  const { app, workId } = env;
  const box = el('div', { class: 'retell card' }, el('h2', { text: '用自己的话说说，他为什么写这首诗' }));
  const area = el('textarea', { rows: 4, maxlength: 400, 'aria-label': '用自己的话说', placeholder: '说得不全也可以' });
  const result = el('div', { class: 'ask-out', 'aria-live': 'polite' });
  const saved = app.platform.kv.get(`retell:${workId}`);
  if (saved) area.value = saved;
  const del = el('button', { class: 'btn', type: 'button', text: '删掉我写的', onclick: () => { app.platform.kv.remove(`retell:${workId}`); area.value = ''; result.replaceChildren(); } });

  const submit = el('button', { class: 'btn primary', type: 'button', text: '看看还可以补什么', onclick: async () => {
    const text = area.value.trim();
    app.platform.kv.set(`retell:${workId}`, text);                    // stays on this device, learner can delete it
    env.app.tracker.track({ workId, step: 'recite', kind: 'retell_submit', ref: retellLength(text) });
    const reply = await env.ask('evaluate_retell', { text }, result);
    const ev = reply.evaluation;
    if (!ev) { result.append(referenceLines(env)); return; }
    result.append(evalView(ev, env));
    if (ev.covered.length + ev.missing.length) reportGaps(env, ev);
  } });
  box.append(area, el('div', { class: 'asks' }, submit, del), result);
  return box;
}

/** Only point ids leave the device, and only with consent. The sentence itself never does. */
function reportGaps(env, ev) {
  const { app, workId, entry } = env;
  if (app.store.get('consent') !== 'yes' || !app.store.get('device')) return;
  app.api.post('/devices/me/gaps', { workId, scriptHash: entry.bundleHash.slice(0, 32), covered: ev.covered, missing: ev.missing }, { auth: true }).catch(() => {});
}

function evalView(ev, env) {
  const wrap = el('div', { class: 'eval' }, el('p', { text: ev.summary }));
  if (ev.supplement.length) {
    wrap.append(el('h3', { text: '还可以想一想' }), ...ev.supplement.map(s => el('div', { class: 'card' },
      s.ask ? el('p', { class: 'soft', text: s.ask }) : null, spoken({ text: s.say, kind: s.badge === 'NONE' ? 'INTERPRETATION' : s.badge, badge: s.badge === 'DRAMATIZATION' ? DRAMATIZATION_TAG : null,
        id: s.basis?.[0]?.id, claimId: s.basis?.[0]?.claim_id }, { onBasis: onBasis(env) }))));
  }
  return wrap;
}

/** No agent to evaluate: show the lines of the lesson and let the learner compare. */
function referenceLines(env) {
  const facts = [...env.index.facts.values()].filter(f => f.owner === 'narrator' && (f.step === 'arrive' || f.step === 'return'));
  return el('div', { class: 'eval' }, el('p', { text: '可以对照下面这几句，看看自己讲到了哪些。' }),
    ...facts.slice(0, 6).map(f => spoken(f, { onBasis: onBasis(env) })).filter(Boolean));
}
