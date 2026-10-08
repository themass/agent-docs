import assert from 'node:assert/strict';
import { formatReplyLanguageBlock, resolveReplyLanguage } from './reply-language.js';
import { compileUserPrompt } from './prompt.js';
assert.equal(resolveReplyLanguage('分析这个页面的视频名称和源地址', 'en'), 'zh-CN');
assert.equal(resolveReplyLanguage('Summarize this page', 'zh-CN'), 'en');
assert.ok(formatReplyLanguageBlock('zh-CN').includes('必须用中文'));
assert.ok(compileUserPrompt('分析视频源地址', { revision: 1, url: 'https://x.test', title: 't', header: '', content: '', footer: '' }, [], 'NETWORK: (empty)', undefined, undefined, 'en').includes('必须用中文'));
console.log('reply-language.self-check ok');
