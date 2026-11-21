/**
 * Tiny DOM helpers. Rule for the whole app: text goes in through textContent / text nodes, never
 * innerHTML. Content comes from a bundle; a stray "<" in it must stay a character, not become markup.
 * Nothing here touches `document` at import time, so the module loads under node.
 */
const PROPS = new Set(['hidden', 'disabled', 'value', 'checked', 'tabIndex', 'selected']);

export function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === 'class') node.className = v;
      else if (k === 'text') node.textContent = v;
      else if (k === 'dataset') Object.assign(node.dataset, v);
      else if (k.startsWith('on') && typeof v === 'function') node.addEventListener(k.slice(2).toLowerCase(), v);
      else if (PROPS.has(k)) node[k] = v;
      else node.setAttribute(k, v === true ? '' : String(v));
    }
  }
  append(node, children);
  return node;
}

export function append(node, children) {
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    node.append(typeof c === 'string' || typeof c === 'number' ? document.createTextNode(String(c)) : c);
  }
  return node;
}

export function clear(node) { node.replaceChildren(); return node; }

/** Wrap a click handler so a keyboard user gets the same thing with Enter / Space on a non-button. */
export function activatable(node, handler) {
  node.tabIndex = 0;
  node.setAttribute('role', 'button');
  node.addEventListener('click', handler);
  node.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handler(e); }
  });
  return node;
}
