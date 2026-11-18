const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
// R2 P1-1/P1-3 on the client, one file both ways through useAgentSession.ts.
// The projection is EXECUTED (same transpile+append-export trick as
// agent-confirm-history.test.cjs); the send gate is pinned by order, because
// its whole meaning is "before streamAgentMessage, not after".
const source=fs.readFileSync(path.join(__dirname,'../hooks/useAgentSession.ts'),'utf8')+'\nexport const projectHistoryForTest = recordsToDisplayItems;';
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
const mod={exports:{}};
new Function('require','module','exports',code)((name)=>name==='react'?require(name):{},mod,mod.exports);
const project=mod.exports.projectHistoryForTest;
const userRow=(extra)=>({id:'agtr_1',session_id:'as1',role:'user',event_type:'message',content:'你好',payload:null,created_at:'2026-11-18T00:00:00Z',...extra});

// ---- P1-1 (G1): history carries the id back onto the bubble. ----
test('a user row with client_message_id re-glues the optimistic bubble by id',()=>{
  const [item]=project([userRow({client_message_id:'cm_1'})]);
  assert.equal(item.clientMessageId,'cm_1');
});
test('a row without one stays undefined — no invented id, no merge collision',()=>{
  const [withId]=project([userRow({client_message_id:'cm_1'})]);
  const [without]=project([userRow({client_message_id:null})]);
  assert.equal(without.clientMessageId,undefined);
  // Two identical texts, only one of which has an id: distinct bubbles.
  const both=project([userRow({id:'a',client_message_id:'cm_1'}),userRow({id:'b',client_message_id:null})]);
  assert.equal(both.length,2);
  assert.equal(both[0].clientMessageId,'cm_1');
  assert.equal(both[1].clientMessageId,undefined);
});

// ---- P1-3 (E5): the send must gate on the upload marker BEFORE streaming. ----
const fn=source.slice(source.indexOf('const sendMessage'),source.indexOf('const stopStream'));
test('sendMessage gates on hasFailedUpload before streamAgentMessage, and bails',()=>{
  const gate=fn.indexOf('hasFailedUpload(refreshed)');
  const stream=fn.indexOf('await streamAgentMessage');
  assert.ok(gate>=0,'the gate must exist');
  assert.ok(stream>=0,'the stream call must exist');
  assert.ok(gate<stream,'the gate must run BEFORE the message can stream out');
  // R2 measured the old path relaying anyway: the gate's early return is the fix.
  const bail=fn.slice(gate,stream);
  assert.ok(bail.includes('return'),'a failed upload must end the send, not mark and continue');
  assert.ok(bail.includes('markLastUserMessageFailed'),'the bubble must enter the retry affordance');
});
test('the gate reads the REFRESHED list, not the stale one',()=>{
  const gate=fn.indexOf('hasFailedUpload(refreshed)');
  assert.ok(gate>=0,'the gate must test refreshLiveUploads output; the pre-upload list can never carry the marker');
});
