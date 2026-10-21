const {test} = require('node:test');
const assert = require('node:assert/strict');
const ts = require('typescript');
const fs = require('node:fs');
const code = ts.transpileModule(fs.readFileSync(require('node:path').join(__dirname, '../lib/image-crop.ts'), 'utf8'), {
  compilerOptions: {target: ts.ScriptTarget.ES2017, module: ts.ModuleKind.CommonJS}
}).outputText;
const mod = {exports: {}};
new Function('exports', code)(mod.exports);
const c = mod.exports;
const bounds = {width:256,height:320};
const initial = {x:24,y:30,width:208,height:260};
const close = (a,b) => assert.ok(Math.abs(a-b)<1e-7, `${a} != ${b}`);
test('selection moves and clamps at every stage edge', () => {
  assert.deepEqual(c.moveCrop(initial,10,15,bounds), {...initial,x:34,y:45});
  assert.deepEqual(c.moveCrop(initial,-999,999,bounds), {...initial,x:0,y:60});
});
for (const corner of ['nw','ne','sw','se']) test(`${corner} resize locks aspect and opposite anchor within bounds`, () => {
  for (const dx of [-999,-10,10,999]) for (const dy of [-999,-10,10,999]) {
    const r = c.resizeCrop(initial,corner,dx,dy,bounds);
    close(r.width/r.height,.8);
    assert.ok(r.x >= -1e-8 && r.y >= -1e-8 && r.x+r.width<=256+1e-8 && r.y+r.height<=320+1e-8);
    close(corner.endsWith('e') ? r.x : r.x+r.width, corner.endsWith('e') ? initial.x : initial.x+initial.width);
    close(corner.startsWith('s') ? r.y : r.y+r.height, corner.startsWith('s') ? initial.y : initial.y+initial.height);
  }
});
for (const natural of [{width:800,height:1000},{width:1600,height:600},{width:600,height:1600},{width:300,height:9000}]) {
  test(`preview to source coordinate roundtrip ${natural.width}x${natural.height}`, () => {
    for (const zoom of [1,2,4]) {
      const t = c.clampTransform({x:999,y:-999,zoom},natural,bounds);
      const r = c.selectionSourceRect(t,natural,bounds,initial);
      const scale = c.coverScale(natural,bounds)*zoom;
      close(r.width/r.height,.8);
      assert.ok(r.x>=0 && r.y>=0 && r.x+r.width<=natural.width+1e-7 && r.y+r.height<=natural.height+1e-7);
      close((r.x-natural.width/2)*scale + bounds.width/2+t.x,initial.x);
      close((r.y-natural.height/2)*scale + bounds.height/2+t.y,initial.y);
    }
  });
}
