#!/usr/bin/env node
// 占位:春望「春日长安」视差场景(5 层 SVG + parallax.json + poster.webp)和长安示意地图。
// 几何水墨风,纯代码,确定性输出。没有任何依据场景要素表的细节:城郭只有概括轮廓,没有人物、旗帜、兵器、文字。
// poster 用本机 Chrome(headless,不联网)把合成 SVG 栅格化,再用 cwebp 转 webp;缺工具则报错退出(不静默跳过)。
import { writeFileSync, mkdtempSync, readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { fresh, put, delivery, run, rng } from './_common.mjs';

const W = 1280, H = 720;
const C = { paper: '#f6f1e7', paper2: '#efe6d3', ink: '#1f1e1b', inkSoft: '#4a4740', faint: '#8a857a', rule: '#ded6c6', green: '#4f6d4b', greenDark: '#3d563a', indigo: '#2d4a5e' };
const NOTE = '<!-- 占位素材:代码生成的几何水墨风,不可上线。不依据场景要素表;城郭只是概括轮廓。 -->';
const svg = (inner, defs = '') => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true">\n${NOTE}\n${defs}${inner}\n</svg>\n`;
const r = rng(757);

// ---- 层 ----
const sky = svg(`<rect width="${W}" height="${H}" fill="url(#sky)"/>\n<circle cx="930" cy="190" r="58" fill="#f3e9cf" opacity="0.8"/>`,
  `<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e5ddca"/><stop offset="0.65" stop-color="${C.paper}"/><stop offset="1" stop-color="${C.paper2}"/></linearGradient></defs>\n`);

const ridge = (base, amp, seed, step = 80) => { const g = rng(seed); let d = `M0 ${H} L0 ${base}`; for (let x = 0; x <= W + step; x += step) d += ` L${x} ${(base - amp * (0.35 + 0.65 * g())).toFixed(1)}`; return d + ` L${W} ${H} Z`; };
const far = svg(`<path d="${ridge(430, 150, 11, 110)}" fill="${C.faint}" opacity="0.28"/>\n<path d="${ridge(470, 120, 23, 90)}" fill="${C.inkSoft}" opacity="0.30"/>`);

// 城郭:只有概括的低矮长墙 + 一座门楼的块状剪影 + 墙后几个屋顶块;不画旗、不画人、不画形制细节
const merlons = Array.from({ length: 34 }, (_, i) => `<rect x="${150 + i * 28}" y="478" width="16" height="10" fill="${C.inkSoft}" opacity="0.55"/>`).join('');
const mid = svg(`<g opacity="0.92">
<rect x="150" y="488" width="980" height="74" fill="${C.inkSoft}" opacity="0.62"/>
${merlons}
<rect x="600" y="430" width="110" height="132" fill="${C.ink}" opacity="0.58"/>
<polygon points="590,432 655,392 720,432" fill="${C.ink}" opacity="0.66"/>
<rect x="628" y="500" width="54" height="62" fill="${C.paper2}" opacity="0.9"/>
<rect x="240" y="450" width="86" height="40" fill="${C.ink}" opacity="0.45"/><polygon points="232,452 283,426 334,452" fill="${C.ink}" opacity="0.5"/>
<rect x="920" y="446" width="100" height="44" fill="${C.ink}" opacity="0.45"/><polygon points="912,448 970,420 1028,448" fill="${C.ink}" opacity="0.5"/>
</g>
<path d="M0 ${H} L0 560 L${W} 560 L${W} ${H} Z" fill="${C.paper2}" opacity="0.0"/>`);

// 近景:很深的草木(对应『城春草木深』),密集的草叶线条 + 几丛矮灌
const blades = (n, yMin, yMax, hMin, hMax, color, op) => Array.from({ length: n }, () => {
  const x = r() * W, y = yMin + r() * (yMax - yMin), h = hMin + r() * (hMax - hMin), lean = (r() - 0.5) * 40;
  return `<path d="M${x.toFixed(1)} ${y.toFixed(1)} Q${(x + lean * 0.4).toFixed(1)} ${(y - h * 0.55).toFixed(1)} ${(x + lean).toFixed(1)} ${(y - h).toFixed(1)}" stroke="${color}" stroke-width="${(1.6 + r() * 2.2).toFixed(1)}" stroke-linecap="round" fill="none" opacity="${op}"/>`; }).join('\n');
const near = svg(`<path d="M0 ${H} L0 600 Q320 575 640 598 T1280 592 L${W} ${H} Z" fill="${C.greenDark}" opacity="0.5"/>
${blades(260, 600, 720, 60, 170, C.green, 0.8)}
${blades(180, 640, 720, 90, 230, C.greenDark, 0.85)}
${Array.from({ length: 7 }, (_, i) => `<ellipse cx="${(90 + i * 190 + r() * 40).toFixed(0)}" cy="${(640 + r() * 40).toFixed(0)}" rx="${(70 + r() * 40).toFixed(0)}" ry="${(26 + r() * 14).toFixed(0)}" fill="${C.green}" opacity="0.55"/>`).join('\n')}`);

const overlay = svg(`<rect x="0" y="470" width="${W}" height="60" fill="url(#mist)"/>`,
  `<defs><linearGradient id="mist" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.paper}" stop-opacity="0"/><stop offset="0.5" stop-color="${C.paper}" stop-opacity="0.55"/><stop offset="1" stop-color="${C.paper}" stop-opacity="0"/></linearGradient></defs>\n`);

const LAYERS = [
  { id: 'sky', file: 'layers/sky.svg', depth: 0, role: 'sky', svg: sky },
  { id: 'far', file: 'layers/far.svg', depth: 0.15, role: 'far', svg: far },
  { id: 'mid', file: 'layers/mid.svg', depth: 0.4, role: 'mid', svg: mid, note: '概括的城郭轮廓,无细节' },
  { id: 'mist', file: 'layers/mist.svg', depth: 0.55, role: 'overlay', svg: overlay, drift: { x_pct_per_min: 2, loop_s: 60 } },
  { id: 'grass', file: 'layers/grass.svg', depth: 0.9, role: 'near', svg: near },
];

// ---- a-changan-dusk ----
const ID = 'a-changan-dusk'; fresh(ID);
for (const l of LAYERS) put(ID, l.file, l.svg);
const manifest = { schema_version: '1.0', canvas: { width: W, height: H }, max_shift_pct: 2,
  layers: LAYERS.map(({ svg: _s, ...rest }) => rest), poster: 'poster.webp', depiction: 'DRAMATIZATION',
  alt_text: '春天的长安城示意图(占位):远处有山,中间是低矮的城郭轮廓,近处草木很深。' };
put(ID, 'parallax.json', JSON.stringify(manifest, null, 2) + '\n');

// poster:合成 SVG → Chrome 截图 → cwebp
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
if (!existsSync(chrome)) throw new Error('找不到 Chrome,无法栅格化 poster');
const tmp = mkdtempSync(join(tmpdir(), 'qj-poster-'));
const inner = (s) => s.replace(/^<svg[^>]*>\n/, '').replace(/\n<\/svg>\n$/, '');
writeFileSync(join(tmp, 'poster.svg'), `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${LAYERS.map((l) => inner(l.svg)).join('\n')}</svg>`);
run(chrome, ['--headless=new', '--disable-gpu', '--hide-scrollbars', `--window-size=${W},${H}`, `--screenshot=${join(tmp, 'poster.png')}`, `file://${join(tmp, 'poster.svg')}`]);
run('cwebp', ['-q', '72', '-m', '6', join(tmp, 'poster.png'), '-o', join(tmp, 'poster.webp')]);
put(ID, 'poster.webp', readFileSync(join(tmp, 'poster.webp')));
delivery(ID, { generator: 'tools/gen/gen-chun-wang-scene.mjs', origin: '自生成占位(代码绘制的几何水墨风 SVG)', extraNotes: '无 AI 生成图像,无第三方素材。' });

// ---- a-chang-an-map ----
const MID = 'a-chang-an-map'; fresh(MID);
const map = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640" width="960" height="640" role="img" aria-label="长安示意图(占位)">
${NOTE}
<rect width="960" height="640" fill="${C.paper}"/>
<rect x="190" y="110" width="580" height="420" fill="${C.paper2}" stroke="${C.ink}" stroke-width="3"/>
<rect x="215" y="135" width="530" height="370" fill="none" stroke="${C.rule}" stroke-width="2" stroke-dasharray="10 8"/>
<text x="480" y="335" text-anchor="middle" font-family="'Songti SC','Noto Serif SC',serif" font-size="56" fill="${C.ink}">长安</text>
<text x="480" y="600" text-anchor="middle" font-family="'PingFang SC','Noto Sans SC',sans-serif" font-size="22" fill="${C.faint}">示意图,不按比例,不代表真实城郭形制(占位)</text>
</svg>
`;
put(MID, 'map.svg', map);
delivery(MID, { generator: 'tools/gen/gen-chun-wang-scene.mjs', origin: '自生成占位(代码绘制的示意方框,只写『长安』二字)', extraNotes: '未使用任何底座地点条目以外的地名。' });
console.log('wrote inbox/a-changan-dusk (5 layers + poster.webp) and inbox/a-chang-an-map');
