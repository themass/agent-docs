import assert from 'node:assert/strict';
import { deliverableGuidanceNotes, deliverablePlanMilestone, deliverablePreflightSkill, resolveDeliverable, resolveDeliverableWithContinuity, shouldRunCatalogPreflight, shouldRunMediaRecipe, } from './deliverable.js';
import { resolveTaskIntent } from './task-intent.js';
const SAMPLE = '分析这个网站的 视频列表，给我生成一个python 脚本，抓取每个分类下的第一页。\n页码可以定义多少页，默认值为1';
assert.equal(resolveDeliverable(SAMPLE), 'script');
assert.equal(resolveTaskIntent(SAMPLE), 'script_authoring');
assert.equal(deliverablePreflightSkill('script'), 'persist');
assert.equal(shouldRunCatalogPreflight(SAMPLE, 'script'), false);
assert.equal(shouldRunMediaRecipe('script', 'script_authoring'), false);
assert.ok(deliverableGuidanceNotes('script').every((l) => !l.includes('intent=media') && !l.includes('MEDIA_ENTRY_OUTPUT')), 'script guidance must not use media-extract intent or MEDIA_ENTRY schema');
assert.match(deliverablePlanMilestone('media'), /click_index/);
assert.match(deliverablePlanMilestone('script'), /script_save/);
assert.equal(resolveDeliverable('分析这个视频的 m3u8 播放地址'), 'media');
assert.equal(resolveDeliverable('分析这个页面的视频名称和源地址'), 'media');
assert.equal(resolveDeliverable('分析视频名称和源地址，并写 python 脚本保存'), 'script', 'script phrases win when combined with media harvest');
assert.equal(resolveTaskIntent('分析这个视频的 m3u8 播放地址'), 'media_extract');
// --- Regression: tests/message.txt drift. "上面的内容不全，请重新抓取一下"
// contains the generic "抓取" verb and would resolve to deliverable=data in
// isolation — but once deliverable=media is established for the thread, a
// generic follow-up must not reclassify the task narrative.
assert.equal(resolveDeliverable('上面的内容不全，请重新抓取一下'), 'data', 'sanity: this phrase alone is weak/generic and resolves to data without thread context');
assert.equal(resolveDeliverableWithContinuity('上面的内容不全，请重新抓取一下', 'media'), 'media', 'a generic follow-up must stick to the previously established deliverable');
assert.equal(resolveDeliverableWithContinuity('？？', 'media'), 'media', 'a bare confused follow-up must stick to the previously established deliverable');
assert.equal(resolveDeliverableWithContinuity('继续', 'media'), 'media', 'continuation phrasing must stick to the previously established deliverable');
// A strong, specific signal for a *different* deliverable must still win —
// stickiness is not an infinite lock, only a guard against generic/ambiguous
// follow-ups.
assert.equal(resolveDeliverableWithContinuity('帮我写一个 python 脚本抓取这些视频链接', 'media'), 'script', 'an explicit, specific request for a different deliverable overrides stickiness');
// No prior deliverable (fresh thread) falls back to plain resolution.
assert.equal(resolveDeliverableWithContinuity('上面的内容不全，请重新抓取一下', undefined), 'data', 'fresh thread with no prior deliverable uses plain resolveDeliverable');
console.log('deliverable.self-check ok');
