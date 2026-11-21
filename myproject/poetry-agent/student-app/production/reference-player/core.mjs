// 角色清单的参考播放器内核(纯函数,不碰 DOM,Node 与浏览器通用)。
// 它是 contracts/character.schema.json 语义的"唯一参考实现":B 可以直接拷贝,也可以照着用 TS 重写;
// 两者行为不一致时以本文件为准(发现本文件有错请在 handoff 里报告,不要悄悄各改各的)。
//
// 约定(与 schema 的 description 一致,这里写死细节):
//  1. 时间单位毫秒。循环状态按 duration_ms 取模;非循环状态播完停在末帧,并在 then 存在时切到 then。
//  2. 每个 track 在关键帧间线性插值(easing 缺省 linear;easing 作用于每一段)。第一帧之前取首值,末帧之后取末值。
//  3. 属性默认值:translateX/Y=0, rotate=0, scale/scaleX/scaleY=1, opacity=1。
//     同一图层同一属性有多条轨道时:平移/旋转相加,缩放相乘,opacity 相乘。
//  4. 变换顺序(对每个图层,以 pivot 为原点):translate → rotate → scale。父节点变换先作用,子节点继承。
//  5. 状态切换:对上一状态在切换瞬间的姿态做快照,在 transition_ms 内线性过渡到新状态的姿态;
//     可见性(show/hide、眨眼、嘴形)不过渡,切换即生效。
//  6. 降级:状态被禁用(disabled)或不存在 → 沿 fallback_state 链走到可用状态,最终 idle。reducedMotion 时只用
//     degrade.reduced_motion_state 的第 0 帧姿态,不眨眼,不嘴动。
//  7. 嘴:mouth_mode=amplitude 且调用方给出 amplitude(0..1)→ 直接把 mouth.prop 设为 closed+(open-closed)*amp,并忽略
//     role=mouth_cycle 的轨道;amplitude 缺省(undefined)→ 保持轨道的循环嘴动;amplitude=null 或 mouth_mode=none → 嘴不动。
//  8. 眨眼:ambient.blink 按 interval_ms 区间内的确定性伪随机间隔触发,闭眼 closed_ms;suppress_in 的状态里不眨。

const DEFAULTS = { translateX: 0, translateY: 0, rotate: 0, scale: 1, scaleX: 1, scaleY: 1, opacity: 1 };
const ADDITIVE = new Set(['translateX', 'translateY', 'rotate']);
const EASE = {
  linear: (x) => x,
  'ease-in': (x) => x * x,
  'ease-out': (x) => 1 - (1 - x) * (1 - x),
  'ease-in-out': (x) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2),
};

export function sampleTrack(track, t) {
  const k = track.keyframes, ease = EASE[track.easing || 'linear'];
  if (t <= k[0][0]) return k[0][1];
  if (t >= k[k.length - 1][0]) return k[k.length - 1][1];
  for (let i = 1; i < k.length; i++) {
    if (t <= k[i][0]) {
      const [t0, v0] = k[i - 1], [t1, v1] = k[i];
      return t1 === t0 ? v1 : v0 + (v1 - v0) * ease((t - t0) / (t1 - t0));
    }
  }
  return k[k.length - 1][1];
}

export function stateDuration(state) {
  if (state.duration_ms) return state.duration_ms;
  let m = 0;
  for (const tr of state.tracks || []) m = Math.max(m, tr.keyframes[tr.keyframes.length - 1][0]);
  return m || 1000;
}

/** 解析要播放的状态名:沿 fallback_state 链,跳过 disabled 的状态。 */
export function resolveState(manifest, name, disabled = new Set()) {
  let cur = name, n = 0;
  while (cur && n++ < 10) {
    if (manifest.states[cur] && !disabled.has(cur)) return cur;
    cur = manifest.states[cur]?.fallback_state;
  }
  return 'idle';
}

/** 取一个状态在 localMs 时刻的"姿态":每个图层的各属性值(只含被轨道触及的图层)。 */
export function samplePose(manifest, stateName, localMs, { amplitude } = {}) {
  const st = manifest.states[stateName];
  const out = {}; // layerId -> {translateX,...}
  const useAmp = manifest.mouth_mode === 'amplitude' && amplitude !== undefined && amplitude !== null;
  for (const tr of st.tracks || []) {
    if (tr.role === 'mouth_cycle' && (useAmp || manifest.mouth_mode === 'none' || amplitude === null)) continue;
    const v = sampleTrack(tr, localMs);
    const L = (out[tr.layer] ||= {});
    const cur = L[tr.prop] ?? DEFAULTS[tr.prop];
    L[tr.prop] = ADDITIVE.has(tr.prop) ? cur + v : tr.prop === 'opacity' || tr.prop.startsWith('scale') ? cur * v : v;
  }
  if (useAmp && manifest.mouth) {
    const m = manifest.mouth, a = Math.max(0, Math.min(1, amplitude));
    (out[m.layer] ||= {})[m.prop] = m.closed + (m.open - m.closed) * a;
  }
  return out;
}

/** 两个姿态按 w(0..1)线性混合;缺失的属性用默认值。 */
export function blendPose(a, b, w) {
  if (w >= 1) return b;
  const out = {};
  for (const id of new Set([...Object.keys(a), ...Object.keys(b)])) {
    const L = (out[id] = {});
    for (const p of new Set([...Object.keys(a[id] || {}), ...Object.keys(b[id] || {})])) {
      const x = a[id]?.[p] ?? DEFAULTS[p], y = b[id]?.[p] ?? DEFAULTS[p];
      L[p] = x + (y - x) * w;
    }
  }
  return out;
}

/** 确定性伪随机,播放与预览用同一序列。 */
export function seededRandom(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

/** 有状态播放器。tick(dtMs, {amplitude}) 返回当前帧 {pose, visible:Set, state}。 */
export class CharacterPlayer {
  constructor(manifest, { reducedMotion = false, disabled = [], seed = 1 } = {}) {
    this.m = manifest; this.reducedMotion = reducedMotion; this.disabled = new Set(disabled);
    this.rand = seededRandom(seed);
    this.clock = 0; this.stateStart = 0; this.state = null; this.snapshot = null; this.transitionFrom = 0;
    this.nextBlink = this.#blinkGap(); this.blinkUntil = -1;
    this.requested = null;
    this.setState(manifest.default_state);
  }
  #blinkGap() { const b = this.m.ambient?.blink; if (!b) return Infinity; const [lo, hi] = b.interval_ms; return this.clock + lo + this.rand() * (hi - lo); }

  setState(name) {
    const resolved = this.reducedMotion ? this.m.degrade.reduced_motion_state : resolveState(this.m, name, this.disabled);
    if (resolved === this.state) { this.requested = name; return resolved; }
    if (this.state) this.snapshot = this.#pose(0);
    this.requested = name; this.state = resolved; this.stateStart = this.clock;
    this.transitionMs = this.snapshot && !this.reducedMotion ? (this.m.states[resolved].transition_ms ?? 0) : 0;
    return resolved;
  }

  #local() {
    const st = this.m.states[this.state], dur = stateDuration(st), el = this.clock - this.stateStart;
    if (this.reducedMotion) return 0;
    return st.loop ? el % dur : Math.min(el, dur);
  }
  #pose(amplitude) {
    const cur = samplePose(this.m, this.state, this.#local(), { amplitude: this.reducedMotion ? null : amplitude });
    const el = this.clock - this.stateStart;
    if (this.snapshot && this.transitionMs > 0 && el < this.transitionMs) return blendPose(this.snapshot, cur, el / this.transitionMs);
    return cur;
  }

  tick(dtMs, { amplitude } = {}) {
    this.clock += dtMs;
    const st = this.m.states[this.state];
    if (!st.loop && st.then && this.clock - this.stateStart >= stateDuration(st) && !this.reducedMotion) this.setState(st.then);
    const bl = this.m.ambient?.blink;
    let blinking = false;
    if (bl && !this.reducedMotion && !(bl.suppress_in || []).includes(this.state)) {
      if (this.clock >= this.nextBlink) { this.blinkUntil = this.clock + bl.closed_ms; this.nextBlink = this.#blinkGap() + bl.closed_ms; }
      blinking = this.clock < this.blinkUntil;
    }
    return { state: this.state, pose: this.#pose(amplitude), visible: this.visibleSet(blinking, amplitude), blinking };
  }

  visibleSet(blinking, amplitude) {
    const m = this.m, st = m.states[this.state], vis = new Set();
    for (const l of m.layers || []) if (l.type !== 'group' && l.default_visible !== false) vis.add(l.id);
    for (const id of st.show || []) vis.add(id);
    for (const id of st.hide || []) vis.delete(id);
    const bl = m.ambient?.blink;
    if (blinking && bl) { vis.delete(bl.open_layer); vis.add(bl.closed_layer); }
    // mouth_mode=none:不显示张开的嘴(如果状态 show 了它),保持闭合嘴
    if (m.mouth_mode === 'none' && m.mouth) { vis.delete(m.mouth.layer); }
    return vis;
  }
}

/** 一个图层最终的 SVG transform 字符串(以 pivot 为原点;缺省 pivot 取画布中心)。 */
export function layerTransform(manifest, layer, pose) {
  const p = pose[layer.id]; if (!p) return '';
  const pv = layer.pivot || { x: manifest.canvas.width / 2, y: manifest.canvas.height / 2 };
  const tx = p.translateX ?? 0, ty = p.translateY ?? 0, rot = p.rotate ?? 0;
  const sx = (p.scale ?? 1) * (p.scaleX ?? 1), sy = (p.scale ?? 1) * (p.scaleY ?? 1);
  const f = (n) => +n.toFixed(3);
  return `translate(${f(tx)} ${f(ty)}) translate(${pv.x} ${pv.y}) rotate(${f(rot)}) scale(${f(sx)} ${f(sy)}) translate(${-pv.x} ${-pv.y})`;
}
