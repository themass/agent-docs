// 参考播放器的 DOM 挂载(浏览器)。把 manifest + 各图层 SVG 文本装配成一个 <svg>,apply() 按帧更新。
// 依赖 core.mjs 的 layerTransform。layerSvgText: { [layerId]: svgText }。
import { layerTransform } from './core.js';

const NS = 'http://www.w3.org/2000/svg';

export function mountCharacter(host, manifest, layerSvgText) {
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${manifest.canvas.width} ${manifest.canvas.height}`);
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', manifest.degrade.text_alt);
  svg.style.cssText = 'width:100%;height:100%;display:block;overflow:visible';
  const nodes = new Map(), children = new Map();
  for (const l of manifest.layers) (children.get(l.parent || null) || children.set(l.parent || null, []).get(l.parent || null)).push(l);
  const build = (parentEl, parentId) => {
    for (const l of (children.get(parentId) || []).sort((a, b) => (a.z || 0) - (b.z || 0))) {
      const g = document.createElementNS(NS, 'g');
      g.dataset.layer = l.id;
      if (layerSvgText[l.id]) {
        const doc = new DOMParser().parseFromString(layerSvgText[l.id], 'image/svg+xml').documentElement;
        for (const c of [...doc.childNodes]) if (c.nodeType === 1) g.appendChild(document.importNode(c, true));
      }
      parentEl.appendChild(g); nodes.set(l.id, { g, layer: l }); build(g, l.id);
    }
  };
  build(svg, null);
  host.appendChild(svg);
  return {
    svg,
    /** frame: CharacterPlayer.tick() 的返回值 */
    apply(frame) {
      for (const { g, layer } of nodes.values()) {
        const t = layerTransform(manifest, layer, frame.pose);
        if (t) g.setAttribute('transform', t); else g.removeAttribute('transform');
        if (layer.type !== 'group') g.style.display = frame.visible.has(layer.id) ? '' : 'none';
      }
    },
  };
}
