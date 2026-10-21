const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../lib/profile-draft.ts'), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
}}).outputText;
const mod = { exports: {} };
new Function('exports', code)(mod.exports);
const {createProfileDraft, receiveProfile, acknowledgeSave, draftIsDirty, cleanProfileDraft} = mod.exports;
const profile = (version = 1, patch = {}) => ({ id: 'p1', version, payload: {
  contact: {name: 'test'}, summary: '', education: [],
  experiences: [{id: 'e1', company: 'original', title: 'Engineer', scope: null, highlights: ['original']}],
  ...patch,
}});
const edit = (d, text = 'unsaved') => ({...d, payload: {...d.payload, experiences: [
  {...d.payload.experiences[0], company: text, highlights: [text]},
]}});
test('same-version network reload must not discard edited experience or bullet', () => {
  const d = edit(createProfileDraft(profile()));
  const next = receiveProfile(d, structuredClone(profile()));
  assert.equal(next.payload.experiences[0].company, 'unsaved');
  assert.deepEqual(next.payload.experiences[0].highlights, ['unsaved']);
  assert.equal(next.conflict, null);
  assert.equal(draftIsDirty(next), true);
});
test('agent write preserves user input and blocks silent overwrite with conflict', () => {
  const d = edit(createProfileDraft(profile()));
  const incoming = profile(2, {summary: 'agent update'});
  const next = receiveProfile(d, incoming);
  assert.equal(next.payload.experiences[0].company, 'unsaved');
  assert.equal(next.base.version, 1);
  assert.equal(next.conflict.version, 2);
});
test('photo-only changes adopt new photo and CAS version without dropping input', () => {
  const d = edit(createProfileDraft(profile()));
  const next = receiveProfile(d, profile(2, {contact: {name: 'test', photo: {enabled: true}}}));
  assert.equal(next.payload.experiences[0].company, 'unsaved');
  assert.equal(next.payload.contact.photo.enabled, true);
  assert.equal(next.base.version, 2);
  assert.equal(next.conflict, null);
});
test('late older reload cannot regress the version or content', () => {
  const d = edit(createProfileDraft(profile(3)));
  assert.equal(receiveProfile(d, profile(1)), d);
});
test('save acknowledgment clears only edits actually submitted', () => {
  const d = edit(createProfileDraft(profile()));
  const saved = profile(2, cleanProfileDraft(d.payload));
  const next = acknowledgeSave(d, d.payload, saved);
  assert.equal(draftIsDirty(next), false);
  assert.equal(next.payload.experiences[0].company, 'unsaved');
});
test('typing during a save is retained as the next unsaved edit', () => {
  const d = edit(createProfileDraft(profile()), 'first');
  const later = edit(d, 'second');
  const next = acknowledgeSave(later, d.payload, profile(2, d.payload));
  assert.equal(next.payload.experiences[0].company, 'second');
  assert.equal(next.base.payload.experiences[0].company, 'first');
  assert.equal(draftIsDirty(next), true);
});
test('concurrent newer agent update survives save acknowledgment', () => {
  const d = edit(createProfileDraft(profile()));
  const conflicted = receiveProfile(d, profile(3, {summary: 'newer'}));
  const next = acknowledgeSave(conflicted, d.payload, profile(2, d.payload));
  assert.equal(next.conflict.version, 3);
});
test('new profile gets its own payload; old save response cannot contaminate it', () => {
  const d = edit(createProfileDraft(profile()));
  const next = receiveProfile(d, {...profile(), id: 'p2'});
  assert.equal(draftIsDirty(next), false);
  assert.equal(acknowledgeSave(next, d.payload, profile(2)), next);
});
test('clean forms accept agent changes normally', () => {
  const next = receiveProfile(createProfileDraft(profile()), profile(2, {summary: 'new'}));
  assert.equal(next.payload.summary, 'new');
  assert.equal(draftIsDirty(next), false);
});
test('out-of-order refresh cannot downgrade an already observed conflict', () => {
  const d = edit(createProfileDraft(profile()));
  const newest = receiveProfile(d, profile(4, {summary:'newest'}));
  assert.equal(receiveProfile(newest, profile(2, {summary:'older'})), newest);
});
