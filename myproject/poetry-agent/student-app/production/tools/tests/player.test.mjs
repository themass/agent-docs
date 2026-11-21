// 参考播放器内核的单元测试(node:test)。已写,开发期间不运行。只依赖 reference-player/core.mjs 与已发布的杜甫 manifest。
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { sampleTrack, samplePose, blendPose, resolveState, CharacterPlayer, layerTransform, stateDuration } from '../../reference-player/core.mjs';

const M = JSON.parse(readFileSync(new URL('../../published/characters/du-fu/manifest.json', import.meta.url), 'utf8'));

test('sampleTrack: 首帧前取首值、末帧后取末值、中间线性插值', () => {
  const tr = { keyframes: [[0, 0], [100, 10]] };
  assert.equal(sampleTrack(tr, -5), 0); assert.equal(sampleTrack(tr, 50), 5); assert.equal(sampleTrack(tr, 999), 10);
});
test('sampleTrack: ease-in-out 在中点等于线性中点', () => {
  assert.ok(Math.abs(sampleTrack({ easing: 'ease-in-out', keyframes: [[0, 0], [100, 10]] }, 50) - 5) < 1e-9);
});
test('循环状态首尾值相同(无跳变):idle 与 talk 的所有轨道', () => {
  for (const name of ['idle', 'talk', 'listen', 'sorrow']) {
    const st = M.states[name];
    for (const tr of st.tracks) assert.equal(tr.keyframes[0][1], tr.keyframes.at(-1)[1], `${name}/${tr.layer}.${tr.prop}`);
  }
});
test('resolveState: 沿 fallback 链降级,最终到 idle;disabled 的状态被跳过', () => {
  assert.equal(resolveState(M, 'sorrow'), 'sorrow');
  assert.equal(resolveState(M, 'sorrow', new Set(['sorrow'])), 'idle');
  assert.equal(resolveState(M, 'nonexistent'), 'idle');
});
test('samplePose: 给定振幅时嘴按 closed→open 线性映射,并忽略 mouth_cycle 轨', () => {
  const p = samplePose(M, 'talk', 400, { amplitude: 0.5 });
  assert.ok(Math.abs(p.mouth_open.scaleY - (M.mouth.closed + (M.mouth.open - M.mouth.closed) * 0.5)) < 1e-9);
  const p0 = samplePose(M, 'talk', 400, {});
  assert.notEqual(p0.mouth_open.scaleY, p.mouth_open.scaleY); // 无振幅时用循环嘴动
});
test('samplePose: amplitude=null 时嘴不动(没有 mouth_open 条目)', () => {
  assert.equal(samplePose(M, 'talk', 400, { amplitude: null }).mouth_open, undefined);
});
test('blendPose: w=0 取旧、w=1 取新、缺失属性用默认值', () => {
  const a = { x: { translateY: 10 } }, b = { x: { translateY: 20 }, y: { scaleY: 0.5 } };
  assert.equal(blendPose(a, b, 0).x.translateY, 10); assert.equal(blendPose(a, b, 1).x.translateY, 20);
  assert.equal(blendPose(a, b, 0.5).y.scaleY, 0.75);
});
test('layerTransform: 以 pivot 为原点的变换字符串;无姿态返回空', () => {
  const t = layerTransform(M, { id: 'q', pivot: { x: 10, y: 20 } }, { q: { rotate: 5 } });
  assert.match(t, /translate\(10 20\) rotate\(5\)/); assert.equal(layerTransform(M, { id: 'z' }, {}), '');
});
test('播放器:bow 非循环,播完自动回到 then 指定的 idle', () => {
  const p = new CharacterPlayer(M, { seed: 1 }); p.setState('bow');
  let f; for (let t = 0; t < stateDuration(M.states.bow) + 100; t += 20) f = p.tick(20, {});
  assert.equal(f.state, 'idle');
});
test('播放器:reduced-motion 固定在 reduced_motion_state 第 0 帧,不眨眼', () => {
  const p = new CharacterPlayer(M, { reducedMotion: true }); p.setState('talk');
  let blinked = false; for (let t = 0; t < 20000; t += 50) { const f = p.tick(50, { amplitude: 0.9 }); if (f.blinking) blinked = true; assert.equal(f.state, M.degrade.reduced_motion_state); }
  assert.equal(blinked, false);
});
test('播放器:眨眼按区间触发,bow 期间被抑制', () => {
  const p = new CharacterPlayer(M, { seed: 3 }); let n = 0;
  for (let t = 0; t < 60000; t += 20) if (p.tick(20, {}).blinking) n++;
  assert.ok(n > 0, 'idle 里 60 秒内应眨眼');
  const q = new CharacterPlayer(M, { seed: 3 }); q.setState('bow');
  for (let t = 0; t < 2000; t += 20) assert.equal(q.tick(20, {}).blinking, false);
});
test('状态过渡:切换后 transition_ms 内姿态在旧值与新值之间', () => {
  const p = new CharacterPlayer(M, { seed: 1 });
  for (let t = 0; t < 2000; t += 20) p.tick(20, {});
  p.setState('sorrow'); const f = p.tick(20, {});
  const target = samplePose(M, 'sorrow', 20, {}).head_rig.translateY; // 12 左右
  assert.ok(f.pose.head_rig.translateY < target, '刚切换时还没到目标值');
});
