const { test } = require('node:test');
const assert = require('node:assert/strict');
const ts = require('typescript');
const fs = require('node:fs');
const path = require('node:path');
const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../lib/preview-progress.ts'), 'utf8'),
 { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const streamCode = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../lib/operation-stream.ts'), 'utf8'),
 { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const streamMod = { exports: {} }; new Function('exports', streamCode)(streamMod.exports);
const mod = { exports: {} }; new Function('exports', 'require', code)(mod.exports, () => streamMod.exports);
const { advancePreviewProgress, readPreviewResult } = mod.exports;
const response = (chunks) => new Response(new ReadableStream({ start(controller) {
 for (const c of chunks) controller.enqueue(c); controller.close();
}}));
const enc = new TextEncoder();
test('elapsed time never advances progress and duplicate events do not regress', () => {
 let s = advancePreviewProgress({}, { stage: 'read', status: 'done' });
 assert.deepEqual(s, { read: 'done' });
 s = advancePreviewProgress(s, { stage: 'read', status: 'running' });
 assert.deepEqual(s, { read: 'done' });
});
test('arbitrarily split UTF8 SSE returns the exact final document', async () => {
 const raw = enc.encode(': heartbeat\n\ndata: '+JSON.stringify({type:'progress',stage:'generate',status:'running'})+
 '\n\ndata: '+JSON.stringify({type:'result',data:{html:'真实中文预览'}})+'\n\n');
 const seen=[];
 const out = await readPreviewResult(response(Array.from(raw, b=>Uint8Array.of(b))), e=>seen.push(e));
 assert.deepEqual(out,{html:'真实中文预览'}); assert.equal(seen.length,1);
});
test('errors and incomplete streams cannot be treated as successful previews', async () => {
 await assert.rejects(readPreviewResult(response([enc.encode('data: {"type":"error","message":"生成失败"}\n\n')])), /生成失败/);
 await assert.rejects(readPreviewResult(response([enc.encode(': heartbeat\n\n')])), /连接已中断/);
});
