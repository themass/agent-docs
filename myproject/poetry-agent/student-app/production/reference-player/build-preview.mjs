#!/usr/bin/env node
// 生成独立的预览页(单个 HTML,内联 core/dom/manifest/各图层 SVG,不依赖网络,可 file:// 打开)。
//   node reference-player/build-preview.mjs [manifest.json] [输出.html]
// 页面有两种模式:
//   默认:交互预览(选状态、拖振幅、减少动效、实时播放)。
//   ?sheet=1:联合表——每个状态在 0/25/50/75% 四个时刻各一帧,外加眨眼与不同嘴型;给 Chrome 无头截图用。
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const manifestPath = resolve(process.argv[2] || join(here, '../published/characters/du-fu/manifest.json'));
const outPath = resolve(process.argv[3] || '/tmp/c-preview/character-preview.html');
const dir = dirname(manifestPath);
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
const layerSvg = Object.fromEntries((manifest.layers || []).filter((l) => l.file).map((l) => [l.id, readFileSync(join(dir, l.file), 'utf8')]));

const strip = (s) => s.replace(/^import .*$/gm, '').replace(/^export /gm, '');
const core = strip(readFileSync(join(here, 'core.mjs'), 'utf8'));
const dom = strip(readFileSync(join(here, 'dom.mjs'), 'utf8'));
const esc = (o) => JSON.stringify(o).replace(/</g, '\\u003c');

const html = `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>角色预览(占位,不可上线)</title>
<style>
body{margin:0;background:#f6f1e7;color:#1f1e1b;font:14px/1.5 -apple-system,"PingFang SC",sans-serif}
header{padding:10px 16px;background:#b5342a;color:#fff}
.sheet{display:grid;gap:6px;padding:12px}
.row{display:grid;grid-template-columns:90px repeat(var(--cols),1fr);gap:6px;align-items:center}
.cell{background:#fbf7ef;border:1px solid #ded6c6;border-radius:4px;aspect-ratio:2/3;position:relative}
.cell small{position:absolute;left:4px;top:2px;font-size:11px;color:#8a857a}
.lbl{font-weight:600}
#live{display:flex;gap:16px;padding:16px}#stage{width:340px;height:510px;background:#fbf7ef;border:1px solid #ded6c6}
#ctl{display:flex;flex-direction:column;gap:8px}button{padding:6px 12px}
</style>
<header>占位角色预览:代码生成,不可上线 · 形象为演绎</header>
<div id="app"></div>
<script>
const MANIFEST=${esc(manifest)};const LAYERS=${esc(layerSvg)};
${core}
${dom}
const q=new URLSearchParams(location.search);
function frame(state,t,opts={}){ // 确定性的一帧:新播放器 → 进入 state → 推进 t
  const p=new CharacterPlayer(MANIFEST,{reducedMotion:!!opts.reduced,seed:7});
  p.setState(state);
  let f=p.tick(0,{amplitude:opts.amp});
  const step=20;for(let e=0;e<t;e+=step){f=p.tick(Math.min(step,t-e),{amplitude:opts.amp});}
  if(opts.blink){f.visible=p.visibleSet(true,opts.amp);}
  return f;
}
function cell(host,label,f){const c=document.createElement('div');c.className='cell';const s=document.createElement('small');s.textContent=label;c.appendChild(s);
  const box=document.createElement('div');box.style.cssText='position:absolute;inset:14px 4px 4px';c.appendChild(box);host.appendChild(c);
  mountCharacter(box,MANIFEST,LAYERS).apply(f);}
function sheet(){
  const app=document.getElementById('app'),wrap=document.createElement('div');wrap.className='sheet';app.appendChild(wrap);
  for(const [name,st] of Object.entries(MANIFEST.states)){
    const dur=stateDuration(st),fr=[0,.25,.5,.75];
    const row=document.createElement('div');row.className='row';row.style.setProperty('--cols',fr.length+(name==='talk'?3:1));
    const l=document.createElement('div');l.className='lbl';l.textContent=name+(st.loop?'(循环)':'(单次)')+' '+dur+'ms';row.appendChild(l);
    for(const k of fr)cell(row,Math.round(k*dur)+'ms',frame(name,Math.round(k*dur)));
    if(name==='talk'){for(const a of[0,.5,1])cell(row,'振幅 '+a,frame('talk',400,{amp:a}));}
    else cell(row,'眨眼',frame(name,Math.round(dur*.25),{blink:true}));
    wrap.appendChild(row);}
  const r=document.createElement('div');r.className='row';r.style.setProperty('--cols',5);
  const l=document.createElement('div');l.className='lbl';l.textContent='降级';r.appendChild(l);
  cell(r,'reduced-motion',frame('talk',800,{reduced:true}));
  const fb=document.createElement('div');fb.className='cell';fb.style.gridColumn='span 1';fb.innerHTML='<small>still.svg</small>';const img=document.createElement('div');img.style.cssText='position:absolute;inset:14px 4px 4px';img.innerHTML=${esc(readFileSync(join(dir, manifest.degrade.still.file), 'utf8'))};img.firstElementChild.style.cssText='width:100%;height:100%';fb.appendChild(img);r.appendChild(fb);
  wrap.appendChild(r);document.title='ready';}
function live(){
  const app=document.getElementById('app');app.innerHTML='<div id="live"><div id="stage"></div><div id="ctl"></div></div>';
  const m=mountCharacter(document.getElementById('stage'),MANIFEST,LAYERS);let p=new CharacterPlayer(MANIFEST),amp;
  const ctl=document.getElementById('ctl');
  for(const n of Object.keys(MANIFEST.states)){const b=document.createElement('button');b.textContent=n;b.onclick=()=>p.setState(n);ctl.appendChild(b);}
  const r=document.createElement('input');r.type='range';r.min=0;r.max=100;r.value=0;r.oninput=()=>amp=r.value/100;ctl.append('嘴部振幅 ',r);
  const rm=document.createElement('label');rm.innerHTML='<input type=checkbox> 减少动效';rm.firstChild.onchange=e=>{p=new CharacterPlayer(MANIFEST,{reducedMotion:e.target.checked});};ctl.appendChild(rm);
  let last=performance.now();(function loop(now){m.apply(p.tick(now-last,{amplitude:amp}));last=now;requestAnimationFrame(loop);})(last);}
q.get('sheet')?sheet():live();
</script></html>`;
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, html);
console.log('wrote', outPath, `(${html.length} bytes)`);
