// 登记簿与任务单的单元测试(node:test)。已写,开发期间不运行。只用内存对象与临时目录。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { checkRegistry, fingerprint, filesIndexHash, sha256 } from '../lib/registry.mjs';
import { checkTasks, getPath, transition } from '../lib/tasks.mjs';
import { splitCues, vtt } from '../lib/vtt.mjs';

const file = (path, s) => ({ path, sha256: sha256(Buffer.from(s)), bytes: Buffer.byteLength(s), format: path.split('.').pop() });
function entry(id, level, fallback, content = id) {
  const files = [file(`${id}/x.txt`, content)];
  return { asset_id: id, kind: level === 'L0' ? 'subtitle' : 'illustration', level, uri: files[0].path, ...fingerprint(files), files,
    rights: { origin: '自生成占位', license: 'own' }, meaning: '让学生感到城还在但已残破', fallback_asset_id: fallback, status: 'published',
    placeholder: { is_placeholder: true, not_for_release: true } };
}
const reg = (...assets) => ({ schema_version: '1.0', generated_at: 'x', assets });
const errs = (r) => checkRegistry(r, { verifyFiles: false }).errors;

test('registry: 正确的三级链通过', () => {
  assert.deepEqual(errs(reg(entry('a', 'L2', 'b'), entry('b', 'L1', 'c'), entry('c', 'L0', null))), []);
});
test('registry: L0 不得有 fallback;非 L0 必须有', () => {
  assert.ok(errs(reg(entry('c', 'L0', 'x'))).some((e) => /L0 是地板/.test(e)));
  assert.ok(errs(reg(entry('a', 'L1', null))).some((e) => /必须有 fallback/.test(e)));
});
test('registry: fallback 必须严格降层(同级、升级都不行)', () => {
  assert.ok(errs(reg(entry('a', 'L1', 'b'), entry('b', 'L1', 'c'), entry('c', 'L0', null))).some((e) => /严格更低/.test(e)));
  assert.ok(errs(reg(entry('a', 'L1', 'b'), entry('b', 'L2', 'c'), entry('c', 'L0', null))).some((e) => /严格更低/.test(e)));
});
test('registry: 不能降到自己,fallback 必须已登记', () => {
  assert.ok(errs(reg(entry('a', 'L1', 'a'))).some((e) => /自己/.test(e)));
  assert.ok(errs(reg(entry('a', 'L1', 'ghost'))).some((e) => /未登记/.test(e)));
});
test('registry: hash 全库唯一(镜像 Java hashTaken)', () => {
  const r = errs(reg(entry('a', 'L1', 'b', 'same'), entry('b', 'L0', null, 'same')));
  assert.ok(r.some((e) => /hash 与/.test(e)));
});
test('registry: asset_id 必须小写;meaning 至少 8 字;rights 必填', () => {
  assert.ok(errs(reg({ ...entry('A_b', 'L0', null) })).length >= 1);
  assert.ok(errs(reg({ ...entry('a', 'L0', null), meaning: '太短' })).length >= 1);
  assert.ok(errs(reg({ ...entry('a', 'L0', null), rights: { origin: '', license: '' } })).length >= 1);
});
test('registry: hash 与 files 不一致会被发现', () => {
  const e = entry('a', 'L0', null); e.hash = 'a'.repeat(64);
  assert.ok(errs(reg(e)).some((x) => /hash\/hash_scheme 与 files/.test(x)));
});
test('registry: 多文件 hash 与文件顺序无关,内容变一字节就变', () => {
  const a = file('p/a', '1'), b = file('p/b', '2');
  assert.equal(filesIndexHash([a, b]), filesIndexHash([b, a]));
  assert.notEqual(filesIndexHash([a, b]), filesIndexHash([a, file('p/b', '3')]));
});

const T = (id, level, fb, over = {}) => ({
  // Schema requires 3-64 chars matching ^[a-z0-9][a-z0-9._-]{2,63}$; single-letter ids failed validation
  // before reaching the rule under test, so every case reported two schema errors as well.
  task_id: 'task-' + id, poem: 'p', type: 'x', title: '标题标题', asset_id: id, kind: level === 'L0' ? 'subtitle' : 'illustration', level, render: 'still', registry: true, priority: 'P0',
  usage: { steps: ['arrive'], purpose: '让学生感到城还在但已残破' }, deliverables: [{ role: 'entry', filename: 'a.txt', formats: ['txt'], required: true }],
  rights_requirements: { must_provide: ['origin'], allowed_origins: [], forbidden: [] }, acceptance: { auto: [], human: ['x'] },
  fallback: { fallback_asset_id: fb ? 'task-' + fb : null }, brief: { creative_notes: '创作说明说明文字更长的说明', grounding: '依据', forbidden_elements: [], depiction: 'DRAMATIZATION' },
  placeholder_plan: { strategy: 'none' }, ...over });
test('tasks: 合法链通过;同级降级、缺 fallback、悬空 fallback 都被拦', () => {
  assert.deepEqual(checkTasks([T('a', 'L1', 'b'), T('b', 'L0', null)]).errors, []);
  assert.ok(checkTasks([T('a', 'L1', 'b'), T('b', 'L1', 'c'), T('c', 'L0', null)]).errors.some((e) => /严格降层/.test(e)));
  assert.ok(checkTasks([T('a', 'L1', null)]).errors.some((e) => /必须有 fallback/.test(e)));
  assert.ok(checkTasks([T('a', 'L1', 'ghost')]).errors.some((e) => /没有对应任务单/.test(e)));
});
test('tasks: 样例 bundle 的同级降级会被报告为警告(给 A/B 的信息)', () => {
  const bundle = { assets: { x: { level: 'L1', fallback: ['y'] }, y: { level: 'L1', fallback: ['L0-text'] } } };
  assert.ok(checkTasks([T('x', 'L1', 'z'), T('z', 'L0', null)], bundle).warnings.some((w) => /不是严格降层/.test(w)));
});
test('tasks: getPath 取 bundle 文本', () => assert.equal(getPath({ steps: [{ layers: [{ lines: [{ text: 'hi' }] }] }] }, 'steps[0].layers[0].lines[0].text'), 'hi'));

test('state: 不能跳级;派发需要 assignee;退回需要原因;验收需要验收人', () => {
  const st = { tasks: { t: { state: 'TODO', assignee: null, history: [] } } };
  assert.throws(() => transition(st, 't', 'PUBLISHED'), /不允许/);
  assert.throws(() => transition(st, 't', 'DISPATCHED'), /assignee/);
  transition(st, 't', 'DISPATCHED', { assignee: '外包A' });
  transition(st, 't', 'DELIVERED'); transition(st, 't', 'AUTO_PASSED');
  assert.throws(() => transition(st, 't', 'HUMAN_ACCEPTED'), /验收人/);
  transition(st, 't', 'HUMAN_ACCEPTED', { by: '验收人' });
  assert.throws(() => transition(st, 't', 'REJECTED'), /原因/);
  transition(st, 't', 'PUBLISHED'); assert.equal(st.tasks.t.history.length, 5);
});

test('字幕:切分后拼回与原文逐字一致,每条 ≤ 30 字,时间递增', () => {
  const text = '国破山河在,城春草木深。感时花溅泪,恨别鸟惊心。烽火连三月,家书抵万金。白头搔更短,浑欲不胜簪。';
  const cues = splitCues(text); assert.equal(cues.join(''), text); assert.ok(cues.every((c) => [...c].length <= 30));
  const out = vtt(text, 12000); assert.ok(out.startsWith('WEBVTT')); assert.ok(out.includes('00:00:12.000'));
});
