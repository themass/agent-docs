#!/usr/bin/env node
// 生成占位角色「杜甫」:分层 SVG + manifest.json + still.svg。纯代码,无网络,无随机(输出可复现)。
// 这是占位,不可上线:形象是抽象的几何水墨风,不依据任何画像,也不暗示史实外貌(见 manifest.depiction)。
// 用法: node gen-character-dufu.mjs [输出目录]   默认 ../../published/characters/du-fu
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(process.argv[2] || join(here, '../../published/characters/du-fu'));
mkdirSync(join(outDir, 'layers'), { recursive: true });

const W = 512, H = 768;
const C = { ink: '#1f1e1b', inkSoft: '#4a4740', paper: '#e9dcc3', robe: '#46606f', robeDark: '#34495a', collar: '#cbbf9f', cap: '#2a2824', line: '#1f1e1b' };
const NOTE = '<!-- 占位素材:代码生成的抽象几何形象,不可上线;不依据任何画像,不代表诗人真实外貌。 -->';
const wrap = (inner, id) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" data-layer="${id}" aria-hidden="true">\n${NOTE}\n${inner}\n</svg>\n`;

// ---- 图层(返回 SVG 内部标记)----
const L = {};
L.body = `<path d="M150 440 Q256 405 362 440 L400 750 L112 750 Z" fill="${C.robe}" stroke="${C.line}" stroke-width="3" stroke-linejoin="round"/>
<path d="M214 420 L256 520 L298 420 Z" fill="${C.collar}" stroke="${C.line}" stroke-width="2.5" stroke-linejoin="round"/>
<path d="M150 440 Q120 560 132 660 L170 650 Q168 560 190 470 Z" fill="${C.robeDark}" stroke="${C.line}" stroke-width="2.5" stroke-linejoin="round"/>
<path d="M362 440 Q392 560 380 660 L342 650 Q344 560 322 470 Z" fill="${C.robeDark}" stroke="${C.line}" stroke-width="2.5" stroke-linejoin="round"/>
<path d="M200 560 Q256 580 312 560" fill="none" stroke="${C.ink}" stroke-width="5" stroke-linecap="round"/>`;
L.head = `<rect x="238" y="360" width="36" height="70" fill="${C.paper}" stroke="${C.line}" stroke-width="3"/>
<ellipse cx="256" cy="298" rx="68" ry="84" fill="${C.paper}" stroke="${C.line}" stroke-width="3"/>
<ellipse cx="188" cy="305" rx="9" ry="16" fill="${C.paper}" stroke="${C.line}" stroke-width="3"/>
<ellipse cx="324" cy="305" rx="9" ry="16" fill="${C.paper}" stroke="${C.line}" stroke-width="3"/>
<path d="M256 292 L250 322 L262 322" fill="none" stroke="${C.inkSoft}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`;
L.hair = `<path d="M186 262 Q184 198 256 190 Q328 198 326 262 Q300 226 256 226 Q212 226 186 262 Z" fill="${C.cap}" stroke="${C.line}" stroke-width="3" stroke-linejoin="round"/>
<path d="M326 250 Q372 262 380 312" fill="none" stroke="${C.cap}" stroke-width="8" stroke-linecap="round"/>
<path d="M186 250 Q140 262 132 312" fill="none" stroke="${C.cap}" stroke-width="8" stroke-linecap="round"/>`;
L.brow_l = `<path d="M208 268 Q228 258 248 266" fill="none" stroke="${C.ink}" stroke-width="5" stroke-linecap="round"/>`;
L.brow_r = `<path d="M264 266 Q284 258 304 268" fill="none" stroke="${C.ink}" stroke-width="5" stroke-linecap="round"/>`;
L.eyes_open = `<ellipse cx="228" cy="292" rx="11" ry="6.5" fill="#fff" stroke="${C.line}" stroke-width="2.5"/><circle cx="228" cy="292" r="3.6" fill="${C.ink}"/>
<ellipse cx="284" cy="292" rx="11" ry="6.5" fill="#fff" stroke="${C.line}" stroke-width="2.5"/><circle cx="284" cy="292" r="3.6" fill="${C.ink}"/>`;
L.eyes_closed = `<path d="M217 292 Q228 299 239 292" fill="none" stroke="${C.line}" stroke-width="3" stroke-linecap="round"/>
<path d="M273 292 Q284 299 295 292" fill="none" stroke="${C.line}" stroke-width="3" stroke-linecap="round"/>`;
L.mouth = `<path d="M244 346 Q256 350 268 346" fill="none" stroke="${C.ink}" stroke-width="3.5" stroke-linecap="round"/>`;
L.mouth_open = `<ellipse cx="256" cy="354" rx="12" ry="8" fill="#6b2f2a" stroke="${C.line}" stroke-width="2.5"/>`;
L.mouth_sorrow = `<path d="M244 352 Q256 342 268 352" fill="none" stroke="${C.ink}" stroke-width="3.5" stroke-linecap="round"/>`;

const fileOf = (id) => `layers/${id}.svg`;
for (const id of Object.keys(L)) writeFileSync(join(outDir, fileOf(id)), wrap(L[id], id));

// ---- 静帧(降级用):把默认可见的图层按 z 顺序叠成一张 ----
const stillOrder = ['body', 'head', 'hair', 'brow_l', 'brow_r', 'eyes_open', 'mouth'];
writeFileSync(join(outDir, 'still.svg'),
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="杜甫(占位示意图)">\n${NOTE}\n` +
  stillOrder.map((id) => `<g data-layer="${id}">\n${L[id]}\n</g>`).join('\n') + '\n</svg>\n');

// ---- 动作 ----
const breathe = (period, amp) => ({ layer: 'body', prop: 'scaleY', easing: 'ease-in-out', keyframes: [[0, 1], [period / 2, 1 + amp], [period, 1]] });
const rise = (period, px) => ({ layer: 'head_rig', prop: 'translateY', easing: 'ease-in-out', keyframes: [[0, 0], [period / 2, -px], [period, 0]] });

const states = {
  idle: { description: '待机:呼吸,头部极轻微起伏。', loop: true, fps: 24, duration_ms: 4000,
    tracks: [breathe(4000, 0.012), rise(4000, 4), { layer: 'rig', prop: 'rotate', easing: 'ease-in-out', keyframes: [[0, 0], [2000, 0.6], [4000, 0]] }] },
  talk: { description: '讲话:头部小幅起伏与点头,嘴开合;不要求与声音对齐。有音频振幅时由 mouth 配置接管嘴部。', loop: true, fps: 24, duration_ms: 1600,
    show: ['mouth_open'], hide: ['mouth'], transition_ms: 160, fallback_state: 'idle',
    tracks: [
      breathe(1600, 0.01),
      { layer: 'head_rig', prop: 'translateY', easing: 'ease-in-out', keyframes: [[0, 0], [400, -3], [800, 0], [1200, -2], [1600, 0]] },
      { layer: 'head_rig', prop: 'rotate', easing: 'ease-in-out', keyframes: [[0, 0], [400, 1.2], [800, -1], [1200, 1], [1600, 0]] },
      { layer: 'mouth_open', prop: 'scaleY', role: 'mouth_cycle', easing: 'ease-in-out',
        keyframes: [[0, 0.15], [110, 0.9], [230, 0.3], [360, 1], [480, 0.2], [640, 0.75], [760, 0.15], [900, 0.95], [1040, 0.25], [1200, 0.8], [1340, 0.2], [1480, 0.6], [1600, 0.15]] }] },
  listen: { description: '倾听:头微侧,眉微抬,呼吸。', loop: true, fps: 24, duration_ms: 5000, transition_ms: 300, fallback_state: 'idle',
    tracks: [
      breathe(5000, 0.012),
      { layer: 'head_rig', prop: 'rotate', easing: 'ease-in-out', keyframes: [[0, -3], [2500, -5], [5000, -3]] },
      { layer: 'brow_l', prop: 'translateY', keyframes: [[0, -3], [5000, -3]] },
      { layer: 'brow_r', prop: 'translateY', keyframes: [[0, -3], [5000, -3]] }] },
  sorrow: { description: '忧伤:低头(下沉并轻微压扁,不靠侧倾),眉心上扬,嘴角下垂,呼吸放慢。', loop: true, fps: 24, duration_ms: 5000,
    show: ['mouth_sorrow'], hide: ['mouth'], transition_ms: 500, fallback_state: 'idle',
    tracks: [
      breathe(5000, 0.01),
      { layer: 'head_rig', prop: 'translateY', easing: 'ease-in-out', keyframes: [[0, 12], [2500, 16], [5000, 12]] },
      { layer: 'head_rig', prop: 'scaleY', easing: 'ease-in-out', keyframes: [[0, 0.97], [2500, 0.95], [5000, 0.97]] },
      { layer: 'head_rig', prop: 'rotate', easing: 'ease-in-out', keyframes: [[0, 1.5], [2500, 2.5], [5000, 1.5]] },
      { layer: 'brow_l', prop: 'rotate', keyframes: [[0, -14], [5000, -14]] },
      { layer: 'brow_r', prop: 'rotate', keyframes: [[0, 14], [5000, 14]] }] },
  bow: { description: '行礼(正面视角):躯干压缩并略加宽,头下沉并压扁,闭眼;保持片刻后起身,结束回到待机。', loop: false, fps: 24, duration_ms: 2600,
    show: ['eyes_closed'], hide: ['eyes_open'], then: 'idle', transition_ms: 200, fallback_state: 'idle',
    tracks: [
      { layer: 'body', prop: 'scaleY', easing: 'ease-in-out', keyframes: [[0, 1], [900, 0.92], [1500, 0.92], [2600, 1]] },
      { layer: 'body', prop: 'scaleX', easing: 'ease-in-out', keyframes: [[0, 1], [900, 1.03], [1500, 1.03], [2600, 1]] },
      { layer: 'head_rig', prop: 'translateY', easing: 'ease-in-out', keyframes: [[0, 0], [900, 34], [1500, 34], [2600, 0]] },
      { layer: 'head_rig', prop: 'scaleY', easing: 'ease-in-out', keyframes: [[0, 1], [900, 0.9], [1500, 0.9], [2600, 1]] },
      { layer: 'head_rig', prop: 'rotate', easing: 'ease-in-out', keyframes: [[0, 0], [900, 2], [1500, 2], [2600, 0]] }] },
};

const layers = [
  { id: 'rig', type: 'group', pivot: { x: 256, y: 560 }, role: 'rig', note: '整体以腰为轴的轻微晃动(idle)。行礼不用旋转,见 states.bow。' },
  { id: 'body', type: 'svg', file: fileOf('body'), parent: 'rig', z: 1, pivot: { x: 256, y: 750 }, role: 'body', note: '以脚底为轴做呼吸缩放。' },
  { id: 'head_rig', type: 'group', parent: 'rig', z: 2, pivot: { x: 256, y: 410 }, role: 'rig', note: '头部以颈为轴点头/侧倾,不随呼吸缩放。' },
  { id: 'head', type: 'svg', file: fileOf('head'), parent: 'head_rig', z: 1, pivot: { x: 256, y: 410 }, role: 'head' },
  { id: 'hair', type: 'svg', file: fileOf('hair'), parent: 'head_rig', z: 2, pivot: { x: 256, y: 410 }, role: 'hair' },
  { id: 'brow_l', type: 'svg', file: fileOf('brow_l'), parent: 'head_rig', z: 3, pivot: { x: 208, y: 268 }, role: 'brow', note: '以外侧端点为轴;rotate 为负=内侧上扬。' },
  { id: 'brow_r', type: 'svg', file: fileOf('brow_r'), parent: 'head_rig', z: 3, pivot: { x: 304, y: 268 }, role: 'brow', note: '以外侧端点为轴;rotate 为正=内侧上扬。' },
  { id: 'eyes_open', type: 'svg', file: fileOf('eyes_open'), parent: 'head_rig', z: 4, role: 'eyes' },
  { id: 'eyes_closed', type: 'svg', file: fileOf('eyes_closed'), parent: 'head_rig', z: 4, default_visible: false, role: 'eyes' },
  { id: 'mouth', type: 'svg', file: fileOf('mouth'), parent: 'head_rig', z: 5, role: 'mouth' },
  { id: 'mouth_open', type: 'svg', file: fileOf('mouth_open'), parent: 'head_rig', z: 5, pivot: { x: 256, y: 346 }, default_visible: false, role: 'mouth', note: '以上缘为轴,scaleY 控制张开程度。' },
  { id: 'mouth_sorrow', type: 'svg', file: fileOf('mouth_sorrow'), parent: 'head_rig', z: 5, default_visible: false, role: 'mouth' },
];

const manifest = {
  schema_version: '1.0',
  character_id: 'du-fu',
  display_name: '杜甫(占位)',
  content_id: 'person-du-fu',
  version: '0.1.0-placeholder',
  renderer: 'svg-layers',
  canvas: { width: W, height: H },
  anchors: { feet: { x: 256, y: 750 }, head: { x: 256, y: 300 }, mouth: { x: 256, y: 350 }, speech_bubble: { x: 360, y: 190 } },
  layers,
  mouth_mode: 'amplitude',
  mouth: { layer: 'mouth_open', prop: 'scaleY', closed: 0.1, open: 1, smoothing_ms: 60 },
  default_state: 'idle',
  states,
  ambient: { blink: { open_layer: 'eyes_open', closed_layer: 'eyes_closed', interval_ms: [2600, 5200], closed_ms: 140, suppress_in: ['bow'] } },
  degrade: {
    still: { file: 'still.svg', width: W, height: H },
    reduced_motion_state: 'idle',
    text_alt: '杜甫的占位示意图:一个抽象的半身人物。形象为演绎,不是诗人的画像,外貌与服饰都没有史料依据。',
  },
  depiction: { declared_as: 'DRAMATIZATION', notice: '这是画师想象的示意形象,不是诗人的画像。' },
  rights: {
    origin: '代码生成的占位素材(tools/gen/gen-character-dufu.mjs)', license: 'own', author: 'production pipeline (自动生成)',
    workflow: 'student-app/production/tools/gen/gen-character-dufu.mjs', human_fix: false, attribution_required: false, third_party: [],
    notes: '纯几何图形,无第三方素材,无 AI 生成图像。不依据任何画像或文献描述外貌。',
  },
  placeholder: { is_placeholder: true, not_for_release: true,
    reason: '为了让学生端渲染、状态切换与降级先跑通;不是最终美术。', replace_with_task: 'a-dufu-bust' },
  budget: { max_bytes: 204800, target_fps: 24 },
};
writeFileSync(join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
console.log(`wrote ${Object.keys(L).length} layers, still.svg, manifest.json -> ${outDir}`);
