/**
 * Browser entry. Everything on screen is assembled from the scene bundle + the base's own records:
 * no poem text, no explanation, no coverage sentence is written in this file.
 *
 * Student mode (no ?preview) refuses to render while the base says DRAFT. That refusal is the
 * product's safety property, so it is exercised on the same screen as the preview.
 */
import { buildScene, publishGate } from './scene.js';

const PREVIEW = new URLSearchParams(location.search).has('preview');
const $ = id => document.getElementById(id);
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };

const bundle = await (await fetch('/legacy/public/bundle.json', { credentials: 'omit' })).json();
const preview = await (await fetch('/legacy/public/preview.json', { credentials: 'omit' })).json();

let mediaOff = false;
let scene = build(bundle, preview);
$('work').textContent = titleOfPreview();
$('coverage').textContent = '覆盖声明：' + scene.coverageNotice;
$('unknown').textContent = scene.unknownDatesNotice ? '年代说明：' + scene.unknownDatesNotice : '';
$('src').textContent = `${preview.text_version_id} · ${preview.scriptId} · 导出于 ${new Date(preview.fetched_at).toLocaleString('zh-CN')}`;

function titleOfPreview() {
  const line = preview.lines[0];
  return line ? `春望（${preview.lines.length} 句）` : '春望';
}

function build(b, p) {
  const budget = mediaOff ? { forceLevel: 'L0' } : {};
  const s = buildScene(b, p, budget);
  s.gate = publishGate(b, p);
  return s;
}

function render() {
  const gate = scene.gate;
  if (!gate.open && !PREVIEW) {
    $('stage').replaceChildren(el('div', 'banner gate', '这个场景还没有发布，学生端不会显示任何内容。'));
    document.querySelectorAll('.rail button').forEach(b => { b.disabled = true; });
    return;
  }
  const g = $('gate');
  g.hidden = gate.open;   // show the draft banner whenever the base is not published
  $('gate-detail').textContent = gate.open ? '' : `未发布：${gate.blocked.slice(0, 4).join('、')}${gate.blocked.length > 4 ? ` 等 ${gate.blocked.length} 项` : ''}`;

  const step = scene.steps.find(s => s.id === scene.machine.snapshot.current) || scene.steps[0];
  const hot = new Set(step.layers.flatMap(l => l.linkedLines.map(x => x.seq)));
  renderLines(hot);

  const body = $('step-body');
  body.replaceChildren();
  if (step.id === 'read') body.appendChild(el('p', 'notice', '先读。不懂哪一句，点那一句的字词注释。'));
  for (const layer of step.layers) {
    const card = el('section', 'layer');
    card.appendChild(el('div', 'kind', LAYER_LABEL[layer.layer] + ' · ' + layer.bgId));
    card.appendChild(el('h2', null, layer.title));
    if (layer.body) card.appendChild(el('p', null, layer.body));
    for (const line of layer.spoken) {
      if (line.badge) card.appendChild(el('span', 'badge', line.badge));
      card.appendChild(el('p', 'spoken', line.text));
    }
    if (layer.linkedLines.length)
      card.appendChild(el('p', 'linked', '↔ 这几句：' + layer.linkedLines.map(x => `${x.seq} ${x.text}`).join('　')));
    body.appendChild(card);
  }
  if (step.demoAudio) body.appendChild(el('p', 'notice', '诵：示范音频 ' + step.demoAudio + '（尚未产出，文本与断句先行）'));
  if (step.agentHelp) body.appendChild(el('p', 'notice', '可以问：换一句话说 / 给一点提示 / 追问为什么'));

  const assets = step.layers.flatMap(l => l.assets);
  const degraded = assets.filter(a => a.degraded);
  $('degraded').hidden = degraded.length === 0;
  $('level-tag').textContent = '当前 ' + (assets.length ? maxLevel(assets.map(a => a.level)) : 'L0（纯文本）');
  document.querySelectorAll('.rail .step').forEach(b => b.setAttribute('aria-current', String(b.dataset.step === step.id)));
}

const LAYER_LABEL = { SCENE: '眼前', CITY: '这座城', WORLD: '这个天下', PERSON: '这个人' };
const maxLevel = levels => levels.reduce((a, b) => (ORDER(a) >= ORDER(b) ? a : b));
const ORDER = l => ({ L0: 0, L1: 1, L2: 2, L3: 3, L4: 4 })[l] ?? 0;

function renderLines(hot) {
  const ol = $('lines');
  ol.replaceChildren();
  for (const line of scene.lines) {
    const li = el('li', hot.has(line.seq) ? 'hot' : null, `${line.seq}. ${line.text}`);
    li.tabIndex = 0;
    for (const a of line.annotations) li.appendChild(el('div', 'ann', `${a.kind === 'WORD' ? '字词' : a.kind}：${a.text}`));
    if (!line.annotations.length && hot.has(line.seq)) li.appendChild(el('div', 'ann', '这一句的依据来自底座背景（注释还没录进来）'));
    ol.appendChild(li);
  }
}

for (const button of document.querySelectorAll('.rail .step'))
  button.addEventListener('click', () => { scene.machine.step(button.dataset.step); render(); });
$('back').addEventListener('click', () => { scene.machine.back(); render(); });
$('media-off').addEventListener('change', e => { mediaOff = e.target.checked; scene = build(bundle, preview); render(); });
render();
