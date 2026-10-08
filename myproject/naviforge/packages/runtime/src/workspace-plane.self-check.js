import assert from 'node:assert/strict';
import { workspaceSlug } from './workspace-plane.js';
assert.equal(workspaceSlug('截图在哪了？'), '截图在哪了');
assert.equal(workspaceSlug('Hello, World!'), 'hello-world');
assert.equal(workspaceSlug('   '), 'thread');
console.log('workspace-plane self-check ok');
