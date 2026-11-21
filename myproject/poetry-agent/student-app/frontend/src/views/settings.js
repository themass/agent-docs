/** 设置. Everything here is a preference that lives on this device. */
import { el } from '../core/dom.js';

export async function settings(app) {
  const { store } = app;
  const check = (label, key, invert) => el('label', { class: 'switch' }, el('input', { type: 'checkbox', checked: invert ? !store.get(key) : store.get(key),
    onchange: e => { store.set(key, invert ? !e.target.checked : e.target.checked); app.refresh(); } }), el('span', { text: label }));
  return el('section', { class: 'page settings' }, el('h1', { text: '设置' }),
    check('关闭图片与动画（文字照常）', 'mediaOff'),
    el('label', { class: 'switch' }, el('input', { type: 'checkbox', checked: store.pinyinOn(), onchange: e => { store.set('pinyin', e.target.checked); app.refresh(); } }), el('span', { text: '显示拼音' })),
    el('label', {}, '字号 ', el('input', { type: 'range', min: '0.9', max: '1.6', step: '0.1', value: String(store.get('fontScale')), 'aria-label': '字号',
      oninput: e => { store.set('fontScale', Number(e.target.value)); document.documentElement.style.setProperty('--font-scale', String(store.get('fontScale'))); } })),
    el('p', { class: 'soft', text: '学习记录怎么处理，在“家长”里看，也能在那里删除。' }));
}
