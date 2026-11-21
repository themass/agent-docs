// 机检单元测试(node:test)。按约定:已写,开发期间不运行;最后统一 `node --test tools/tests/`。
// 全部在临时目录里造文件,不碰 inbox/ published/,不联网。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { checkFile, checkDelivery, parseVtt, wavInfo, pngInfo, webpInfo, matchesGlob } from '../lib/checks.mjs';
import { validate } from '../lib/jsonschema.mjs';

const tmp = () => mkdtempSync(join(tmpdir(), 'qj-test-'));

function png(w, h, colorType = 6) {
  const b = Buffer.alloc(33); b.writeUInt32BE(0x89504e47, 0); b.writeUInt32BE(0x0d0a1a0a, 4);
  b.writeUInt32BE(13, 8); b.write('IHDR', 12, 'latin1'); b.writeUInt32BE(w, 16); b.writeUInt32BE(h, 20); b[24] = 8; b[25] = colorType; return b;
}
function wav(ms, rate = 22050) {
  const n = Math.round((rate * ms) / 1000) * 2, b = Buffer.alloc(44 + n);
  b.write('RIFF', 0); b.writeUInt32LE(36 + n, 4); b.write('WAVEfmt ', 8); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22);
  b.writeUInt32LE(rate, 24); b.writeUInt32LE(rate * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(n, 40); return b;
}

test('png: 尺寸与透明通道', () => {
  assert.deepEqual(pngInfo(png(1280, 720)), { width: 1280, height: 720, alpha: true });
  assert.equal(pngInfo(png(10, 10, 2)).alpha, false);
  assert.equal(pngInfo(Buffer.from('not a png')), null);
});

test('webp: 非 webp 文件被拒', () => assert.equal(webpInfo(Buffer.alloc(40)), null));

test('wav: 时长按数据块计算', () => {
  const i = wavInfo(wav(2000)); assert.equal(i.sampleRate, 22050); assert.ok(Math.abs(i.durationMs - 2000) <= 2);
});

test('checkFile: 尺寸/宽高比/透明/大小约束', () => {
  const d = tmp(); const p = join(d, 'a.png'); writeFileSync(p, png(640, 360, 2));
  const ok = checkFile(p, { width: 640, height: 360, aspect: '16:9' }); assert.deepEqual(ok.errors, []);
  const bad = checkFile(p, { min_width: 1280, alpha: true, max_bytes: 10 });
  assert.equal(bad.errors.length, 3);
});

test('checkFile: 把文本改名成 .png 会被文件头识破', () => {
  const d = tmp(); const p = join(d, 'fake.png'); writeFileSync(p, 'hello');
  assert.match(checkFile(p, {}).errors[0], /文件头不符/);
});

test('checkFile: SVG 不允许脚本、事件属性、外部引用、foreignObject', () => {
  const d = tmp();
  for (const body of ['<script>1</script>', '<rect onclick="x()"/>', '<image href="https://x/y.png"/>', '<foreignObject/>']) {
    const p = join(d, 'x.svg'); writeFileSync(p, `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">${body}</svg>`);
    assert.ok(checkFile(p, {}).errors.length >= 1, body);
  }
});

test('checkFile: SVG viewBox 必须等于画布', () => {
  const d = tmp(); const p = join(d, 'l.svg');
  writeFileSync(p, '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50"></svg>');
  assert.deepEqual(checkFile(p, { svg_viewbox_equals_canvas: true }, { canvas: { width: 100, height: 50 } }).errors, []);
  assert.equal(checkFile(p, { svg_viewbox_equals_canvas: true }, { canvas: { width: 200, height: 50 } }).errors.length, 1);
});

test('checkFile: wav 时长与采样率约束', () => {
  const d = tmp(); const p = join(d, 'a.wav'); writeFileSync(p, wav(500, 8000));
  const r = checkFile(p, { min_duration_ms: 1000, min_sample_rate: 22050 }); assert.equal(r.errors.length, 2);
});

test('vtt: 格式、递增、重叠、超长', () => {
  const good = 'WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.000\n国破山河在\n\n2\n00:00:01.000 --> 00:00:02.000\n城春草木深\n';
  assert.equal(parseVtt(good).cues.length, 2);
  const d = tmp(); const p = join(d, 'c.vtt');
  writeFileSync(p, good); assert.deepEqual(checkFile(p, { vtt_monotonic: true }).errors, []);
  writeFileSync(p, good.replace('00:00:01.000 --> 00:00:02', '00:00:00.500 --> 00:00:02')); assert.ok(checkFile(p, { vtt_monotonic: true }).errors.some((e) => /重叠/.test(e)));
  writeFileSync(p, 'no header\n'); assert.ok(checkFile(p, {}).errors.length >= 1);
  writeFileSync(p, `WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.000\n${'字'.repeat(35)}\n`); assert.ok(checkFile(p, { vtt_monotonic: true }).errors.some((e) => /34/.test(e)));
});

test('glob: * 不跨目录', () => {
  assert.ok(matchesGlob('layers/*', 'layers/a.svg')); assert.ok(!matchesGlob('layers/*', 'layers/x/a.svg')); assert.ok(matchesGlob('still.*', 'still.svg'));
});

test('jsonschema: required/enum/pattern/additionalProperties', () => {
  const s = { type: 'object', required: ['a'], additionalProperties: false, properties: { a: { type: 'string', pattern: '^x' }, b: { enum: [1, 2] } } };
  assert.deepEqual(validate(s, { a: 'xy', b: 1 }), []);
  assert.equal(validate(s, { b: 3, c: 1 }).length, 3);
});

const task = (over = {}) => ({
  task_id: 't1', rights_requirements: { must_provide: ['origin', 'license'], forbidden: ['网图'] },
  deliverables: [{ role: 'entry', filename: 'card.txt', formats: ['txt'], required: true, constraints: { max_bytes: 100 } }], ...over });
const delivery = (rights = {}, extra = {}) => ({ schema_version: '1.0', task_id: 't1', delivered_at: 'x', author: '外包A', rights: { origin: '自绘插画', license: 'own', ...rights }, ...extra });

test('checkDelivery: 缺 delivery.json、缺必需文件', () => {
  const d = tmp();
  const r = checkDelivery(task(), d);
  assert.ok(r.errors.some((e) => /delivery\.json/.test(e))); assert.ok(r.errors.some((e) => /需要至少 1 个/.test(e)));
});

test('checkDelivery: 完整交付通过;禁止来源、授权缺项被拦', () => {
  const d = tmp(); writeFileSync(join(d, 'card.txt'), '春天的长安。\n');
  writeFileSync(join(d, 'delivery.json'), JSON.stringify(delivery()));
  assert.deepEqual(checkDelivery(task(), d).errors, []);
  writeFileSync(join(d, 'delivery.json'), JSON.stringify(delivery({ origin: '网图 下载' })));
  assert.ok(checkDelivery(task(), d).errors.some((e) => /禁止项/.test(e)));
  writeFileSync(join(d, 'delivery.json'), JSON.stringify(delivery({ license: '' })));
  assert.ok(checkDelivery(task(), d).errors.length >= 1);
});

test('checkDelivery: 多余文件只警告;空 evidence 数组视为缺失', () => {
  const d = tmp(); writeFileSync(join(d, 'card.txt'), 'x'); writeFileSync(join(d, 'extra.bin'), 'x');
  writeFileSync(join(d, 'delivery.json'), JSON.stringify(delivery({ evidence: [] })));
  const r = checkDelivery(task({ rights_requirements: { must_provide: ['origin', 'license', 'evidence'], forbidden: [] } }), d);
  assert.ok(r.warnings.some((w) => /extra\.bin/.test(w))); assert.ok(r.errors.some((e) => /evidence/.test(e)));
});

test('checkDelivery: 视差清单引用的层文件必须已交付', () => {
  const d = tmp(); mkdirSync(join(d, 'layers'));
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"></svg>';
  for (const n of ['a', 'b', 'c']) writeFileSync(join(d, 'layers', `${n}.svg`), svg);
  writeFileSync(join(d, 'parallax.json'), JSON.stringify({ schema_version: '1.0', canvas: { width: 1280, height: 720 }, max_shift_pct: 2, poster: 'poster.webp',
    layers: ['a', 'b', 'c'].map((n, i) => ({ id: n, file: `layers/${n}.svg`, depth: i / 2, role: ['sky', 'far', 'near'][i] })) }));
  writeFileSync(join(d, 'delivery.json'), JSON.stringify(delivery()));
  const t = task({ deliverables: [
    { role: 'entry', filename: 'parallax.json', formats: ['json'], required: true, constraints: { json_schema: 'parallax-manifest' } },
    { role: 'layer', filename: 'layers/*', formats: ['svg'], required: true, min_count: 3, constraints: { svg_viewbox_equals_canvas: true } }] });
  const r = checkDelivery(t, d); assert.ok(r.errors.some((e) => /poster\.webp/.test(e)), '缺 poster 应报错');
});
