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

// ADR-011 §6-D: uploadProfileWithProgress is direct-first with a multipart
// fallback. All three paths are asserted here: the gate (a type the sign
// endpoint would refuse never reaches the network), the direct channel (no
// XHR at all), and the fallback (direct fails -> the real-progress XHR runs).
// Real `directUpload` semantics live in tests/media-upload.test.ts; this file
// pins the WIRING, so the module is mocked deliberately.
function loadUploadClient({ directImpl, apiJsonImpl }) {
  const calls = { json: [], xhrOpened: 0, progressFns: [] };
  const events = {};
  class FakeXHR {
    upload = { set onprogress(fn) { events.progress = fn; calls.progressFns.push(fn); } };
    status = 201;
    responseText = JSON.stringify({ id: 'p', sources: [] });
    open(method, url) { this.method = method; this.url = url; calls.xhrOpened += 1; }
    send(body) {
      this.body = body;
      events.progress({ lengthComputable: true, loaded: 50, total: 100 });
      events.load();
    }
    set onload(fn) { events.load = fn; }
    set onerror(fn) { events.error = fn; }
    set onabort(fn) { events.abort = fn; }
  }
  const mod = load('../lib/api/profile.ts', {
    './client': { apiJson: apiJsonImpl ?? (async () => ({})) },
    './errors': {
      ApiError: class ApiError extends Error {},
      USER_NETWORK_ERROR: 'network',
      USER_SERVICE_UNAVAILABLE: 'unavailable',
    },
    '@/lib/profile-parse': parse,
    '@/lib/media-upload': {
      directUpload: directImpl ?? (async () => { throw new Error('unreachable in this test'); }),
      PROFILE_SOURCE_TYPES: new Set([
        'image/jpeg', 'image/png', 'image/webp', 'application/pdf', 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain',
      ]),
    },
  });
  return { uploadProfileWithProgress: mod.uploadProfileWithProgress, calls, FakeXHR };
}

test('upload client reports real XHR progress and parses the created profile', async () => {
  // An untyped Blob (old browsers report '' for .doc) is outside the scene
  // whitelist: it must skip the direct channel entirely and keep the real
  // transport progress the bar has always shown.
  const directCalls = [];
  const { uploadProfileWithProgress, calls, FakeXHR } = loadUploadClient({
    directImpl: async (...args) => { directCalls.push(args); return 'key-never-happens'; },
  });
  const prior = global.XMLHttpRequest;
  global.XMLHttpRequest = FakeXHR;
  try {
    const percentages = [];
    const profile = await uploadProfileWithProgress(new Blob(['resume']), value => percentages.push(value));
    assert.equal(profile.id, 'p');
    assert.deepEqual(percentages, [50]);
    assert.deepEqual(directCalls, []); // the gate: no sign call for a non-whitelisted type
  } finally {
    global.XMLHttpRequest = prior;
  }
});

test('profile upload goes direct when the type is whitelisted, with no XHR at all', async () => {
  const signed = [];
  const { uploadProfileWithProgress, calls, FakeXHR } = loadUploadClient({
    directImpl: async (scene, blob, contentType) => {
      signed.push({ scene, contentType, size: blob.size });
      return 'jc/prod/uploads/usr_a/profile-source/2026/11/18/k22charsxxxxxxxx.pdf';
    },
    apiJsonImpl: async (path, init) => {
      calls.json.push({ path, body: JSON.parse(String(init.body)) });
      return { id: 'p', sources: [{ id: 's1' }] };
    },
  });
  const prior = global.XMLHttpRequest;
  global.XMLHttpRequest = FakeXHR;
  try {
    const file = new Blob(['%PDF-1.4 bytes'], { type: 'application/pdf' });
    file.name = 'resume.pdf';
    const percentages = [];
    const profile = await uploadProfileWithProgress(file, value => percentages.push(value));
    assert.equal(profile.id, 'p');
    assert.deepEqual(signed, [{ scene: 'profile-source', contentType: 'application/pdf', size: 14 }]);
    assert.deepEqual(calls.json, [{
      path: '/profiles/upload-direct',
      body: {
        objectKey: 'jc/prod/uploads/usr_a/profile-source/2026/11/18/k22charsxxxxxxxx.pdf',
        fileName: 'resume.pdf',
      },
    }]);
    assert.equal(calls.xhrOpened, 0); // the bytes never went through this server
    assert.deepEqual(percentages, [90, 100]);
  } finally {
    global.XMLHttpRequest = prior;
  }
});

test('a failed direct upload falls back to multipart and still resolves the profile', async () => {
  const { uploadProfileWithProgress, calls, FakeXHR } = loadUploadClient({
    directImpl: async () => { throw new Error('CORS refused the PUT'); },
  });
  const prior = global.XMLHttpRequest;
  global.XMLHttpRequest = FakeXHR;
  try {
    const file = new Blob(['%PDF-1.4 bytes'], { type: 'application/pdf' });
    const percentages = [];
    const profile = await uploadProfileWithProgress(file, value => percentages.push(value));
    assert.equal(profile.id, 'p');
    assert.equal(calls.xhrOpened, 1); // degradation ran
    assert.deepEqual(percentages, [50]);
  } finally {
    global.XMLHttpRequest = prior;
  }
});
