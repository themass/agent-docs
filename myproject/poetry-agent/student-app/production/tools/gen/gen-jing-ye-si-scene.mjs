#!/usr/bin/env node
// 占位:《静夜思》的场景插画(scene-illustration)。概括轮廓,不画床、窗、屋、人、季节标志。
// 输出 main.webp(1280×720,16:9)与 mini.webp(640×360),由本机 Chrome 栅格化 SVG,再 cwebp 转换。
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { fresh, put, delivery, run } from './_common.mjs';

const ID = 'a-jys-moonlight';
const W = 1280, H = 720;
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" aria-hidden="true">
<!-- 占位素材:代码生成的概括轮廓,不可上线。只画诗句字面的月与地上的白;不画床、窗、屋、人,不指明季节。 -->
<defs>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1d2a36"/><stop offset="1" stop-color="#3b4a55"/></linearGradient>
  <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#f7f3e6" stop-opacity="0.9"/><stop offset="1" stop-color="#f7f3e6" stop-opacity="0"/></radialGradient>
  <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9e6dc" stop-opacity="0.85"/><stop offset="1" stop-color="#c9c7bd" stop-opacity="0.6"/></linearGradient>
</defs>
<rect width="${W}" height="${H}" fill="url(#sky)"/>
<circle cx="860" cy="250" r="190" fill="url(#glow)"/>
<circle cx="860" cy="250" r="62" fill="#f4efdc"/>
<path d="M0 500 Q640 470 1280 500 L1280 720 L0 720 Z" fill="url(#ground)"/>
</svg>
`;
const miniSvg = svg.replace(`width="${W}" height="${H}"`, 'width="640" height="360"');

fresh(ID);
const tmp = mkdtempSync(join(tmpdir(), 'qj-scene-'));
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
if (!existsSync(chrome)) throw new Error('找不到 Chrome,无法栅格化');
const shot = (src, out, w, h) => {
  writeFileSync(join(tmp, src + '.svg'), src === 'main' ? svg : miniSvg);
  run(chrome, ['--headless=new', '--disable-gpu', '--hide-scrollbars', `--window-size=${w},${h}`, `--screenshot=${join(tmp, src + '.png')}`, `file://${join(tmp, src + '.svg')}`]);
  run('cwebp', ['-q', '72', '-m', '6', join(tmp, src + '.png'), '-o', join(tmp, out)]);
  return readFileSync(join(tmp, out));
};
put(ID, 'main.webp', shot('main', 'main.webp', W, H));
put(ID, 'mini.webp', shot('mini', 'mini.webp', 640, 360));
delivery(ID, { generator: 'tools/gen/gen-jing-ye-si-scene.mjs', origin: '自生成占位(代码绘制的概括轮廓 SVG,无 AI 图像)', extraNotes: '不画床、窗、屋、人;不表示季节、时间、地点。' });
console.log(`wrote inbox/${ID} (main.webp 1280x720, mini.webp 640x360)`);
