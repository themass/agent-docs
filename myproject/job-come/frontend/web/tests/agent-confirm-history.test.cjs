const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
// Exercise the actual history projection, without rendering or invoking hooks.
const source=fs.readFileSync(path.join(__dirname,'../hooks/useAgentSession.ts'),'utf8')+'\nexport const projectHistoryForTest = recordsToDisplayItems;\nexport const mergeConfirmDecisionsForTest = mergeConfirmDecisions;';
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
const mod={exports:{}};
new Function('require','module','exports',code)((name)=>name==='react'?require(name):{},mod,mod.exports);
const project=mod.exports.projectHistoryForTest;
const mergeDecisions=mod.exports.mergeConfirmDecisionsForTest;
const proposal=(id)=>({id:'msg_'+id,event_type:'confirm',payload:{confirm_id:id,profile_id:'p',patch:{summary:'修改'}}});
const decision=(id,type)=>({id:'decision_'+id,event_type:type,payload:{confirm_id:id}});
test('successful decision updates the original proposal, does not add a second card',()=>{
 const rows=project([proposal('a'),decision('a','confirm_applied')]);
 assert.equal(rows.length,1); assert.equal(rows[0].status,'applied');
 assert.equal(rows[0].confirmId,'a'); assert.deepEqual(rows[0].patch,{summary:'修改'});
});
test('rejected decision stays rejected after refresh',()=>{
 const rows=project([proposal('a'),decision('a','confirm_rejected')]);
 assert.equal(rows.length,1);assert.equal(rows[0].status,'rejected');
});
test('decisions do not change other pending confirmations',()=>{
 const rows=project([proposal('a'),proposal('b'),decision('a','confirm_applied')]);
 assert.deepEqual(rows.map(r=>r.status),['applied','pending']);
});
test('a newer proposal supersedes older pending cards',()=>{
 const rows=project([proposal('a'),proposal('b')]);
 assert.deepEqual(rows.map(r=>r.status),['superseded','pending']);
});
test('projection uses confirm id, not timestamps or response position',()=>{
 const rows=project([decision('a','confirm_applied'),proposal('a')]);
 assert.equal(rows[0].status,'applied');
});
test('optimistic applied status survives a stale history sync',()=>{
 const local=[{id:'c1',kind:'confirm',confirmId:'a',status:'applied'}];
 const server=[{id:'c1',kind:'confirm',confirmId:'a',status:'pending'}];
 const rows=mergeDecisions(local,server);
 assert.equal(rows[0].status,'applied');
});
