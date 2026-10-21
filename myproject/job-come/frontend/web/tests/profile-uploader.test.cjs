const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
function load(file, mocks = {}) {
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, file), 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const mod = { exports: {} };
  new Function('exports', 'require', code)(mod.exports, name => mocks[name] ?? require(name));
  return mod.exports;
}
const parse = load('../lib/profile-parse.ts');
const { ProfileUploader } = load('../components/profile/ProfileUploader.tsx', {
  '@/lib/api/user-error': { userFacingApiError: String },
  '@/lib/api/profile': {},
  '@/lib/brand': { ZHOUKA_NAME: '舟卡' },
  '@/lib/profile-parse': parse,
  '@/components/profile/ProfileParseProgress': {
    ProfileParseProgress: ({ source }) => React.createElement('p', null, `正在解析:${source.id}`),
  },
});
function view(status, payload = {}) {
  return renderToStaticMarkup(React.createElement(ProfileUploader, {
    hasProfile: false, // The actual first-upload branch in resume-agent/page.tsx.
    profile: { id: 'p', payload, sources: [{ id: 'latest', parse_status: status, parse_error: '解析超时' }] },
    onUploaded() {},
  }));
}
test('first upload immediately shows background processing instead of the upload landing', () => {
  assert.match(view('processing'), /正在解析:latest/);
  assert.doesNotMatch(view('processing'), /选择文件/);
});
test('failed first upload displays failure, not a silent return to the upload landing', () => {
  assert.match(view('failed'), /简历解析未完成/);
  assert.match(view('failed'), /解析超时/);
});
test('source selection uses upload time, not relationship ordering or phase update time', () => {
  const older = { id: 'old', created_at: '2026-10-19T23:00:00', updated_at: '2026-10-20T00:10:00' };
  const newer = { id: 'new', created_at: '2026-10-20T00:00:00' };
  assert.equal(parse.latestProfileSource({ sources: [older, newer] }).id, 'new');
  assert.equal(parse.latestProfileSource({ sources: [newer, older] }).id, 'new');
});

test('new-resume actions are above upload and paste, rather than below the viewport', () => {
  const html = renderToStaticMarkup(React.createElement(ProfileUploader, {
    onUploaded() {}, onStartInterview() {},
  }));
  assert.ok(html.indexOf('和舟卡聊着写') < html.indexOf('选择文件'));
  assert.ok(html.indexOf('按问题填写') < html.indexOf('选择文件'));
  assert.match(html, /半成品或旧简历/);
  const page = fs.readFileSync(path.join(__dirname, '../app/resume-agent/page.tsx'), 'utf8');
  assert.match(page, /studioContent = !uploadComplete \? \([\s\S]*?scroll-area h-full min-h-0 overflow-y-auto/);
});
for (const [label, mode] of [['和舟卡聊着写', 'chat'], ['按问题填写', 'interview']]) {
  test(`${label} creates a profile and hands off to the correct editor`, async () => {
    const created = { id: 'new-profile', payload: {}, sources: [] };
    const handed = [];
    let calls = 0;
    const { ProfileUploader: Interactive } = load('../components/profile/ProfileUploader.tsx', {
      react: { ...React, useState: value => [value, () => {}], useCallback: callback => callback },
      '@/lib/api/user-error': { userFacingApiError: String },
      '@/lib/api/profile': { createProfile: async () => { calls++; return created; } },
      '@/lib/brand': { ZHOUKA_NAME: '舟卡' },
      '@/lib/profile-parse': parse,
      '@/components/profile/ProfileParseProgress': {},
    });
    const tree = Interactive({ onUploaded() {}, onStartInterview: (...args) => handed.push(args) });
    function find(node) {
      if (!node || typeof node !== 'object') return null;
      if (node.type === 'button' && node.props.children === label) return node;
      for (const child of React.Children.toArray(node.props?.children)) {
        const found = find(child);
        if (found) return found;
      }
      return null;
    }
    const button = find(tree);
    assert.ok(button, `missing ${label}`);
    button.props.onClick();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(calls, 1);
    assert.deepEqual(handed, [[created, mode]]);
  });
}

test('failed parsing does not hide the independent no-model manual creation route', () => {
  const html = renderToStaticMarkup(React.createElement(ProfileUploader, {
    profile: { id: 'failed', sources: [{ parse_status: 'failed' }], payload: {} },
    onUploaded() {}, onStartInterview() {},
  }));
  assert.match(html, /从零填写简历/);
  assert.match(html, /不必等待解析服务恢复/);
});

test('upload client reports real XHR progress and parses the created profile', async () => {
  const events = {};
  class FakeXHR {
    upload = { set onprogress(fn) { events.progress = fn; } };
    status = 201;
    responseText = JSON.stringify({ id: 'p', sources: [] });
    open(method, url) { this.method = method; this.url = url; }
    send(body) {
      this.body = body;
      events.progress({ lengthComputable: true, loaded: 50, total: 100 });
      events.load();
    }
    set onload(fn) { events.load = fn; }
    set onerror(fn) { events.error = fn; }
    set onabort(fn) { events.abort = fn; }
  }
  const { uploadProfileWithProgress } = load('../lib/api/profile.ts', {
    './client': { apiJson: async () => ({}) },
    './errors': {
      ApiError: class ApiError extends Error {},
      USER_NETWORK_ERROR: 'network',
      USER_SERVICE_UNAVAILABLE: 'unavailable',
    },
    '@/lib/profile-parse': parse,
  });
  const prior = global.XMLHttpRequest;
  global.XMLHttpRequest = FakeXHR;
  try {
    const percentages = [];
    const profile = await uploadProfileWithProgress(new Blob(['resume']), value => percentages.push(value));
    assert.equal(profile.id, 'p');
    assert.deepEqual(percentages, [50]);
  } finally {
    global.XMLHttpRequest = prior;
  }
});
