const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
// The retry button re-sends the bubble it is on. The bubble keeps the id it was first sent with,
// so the server can tell the resend from a new message. These tests load the real helper.
const source=fs.readFileSync(path.join(__dirname,'../lib/agent-retry.ts'),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
const mod={exports:{}};
new Function('require','module','exports',code)(require,mod,mod.exports);
const retryPlan=mod.exports.retryPlan;

const user=(id,content,extra={})=>({id,kind:'user',content,...extra});
const reply=(id)=>({id,kind:'assistant',content:'好的。'});

test('a retry sends the same id the bubble was first sent with',()=>{
 const items=[user('u1','我把结算接口拆成了两张表。',{clientMessageId:'cm_1'}),reply('a1')];
 const plan=retryPlan(items,'u1');
 assert.equal(plan.clientMessageId,'cm_1');
 assert.equal(plan.content,'我把结算接口拆成了两张表。');
});
test('what comes before the bubble stays and what follows it goes',()=>{
 const items=[reply('a0'),user('u1','第一句',{clientMessageId:'cm_1'}),reply('a1'),user('u2','第二句',{clientMessageId:'cm_2'})];
 const plan=retryPlan(items,'u1');
 assert.deepEqual(plan.kept.map(i=>i.id),['a0']);
});
test('a bubble from before ids existed is retried without one, and the server makes a new id',()=>{
 const plan=retryPlan([user('u1','旧消息')],'u1');
 assert.equal(plan.clientMessageId,undefined);
});
test('attachments are carried over, and absent ones become an empty list',()=>{
 const att=[{name:'a.png'}];
 assert.deepEqual(retryPlan([user('u1','x',{attachments:att})],'u1').attachments,att);
 assert.deepEqual(retryPlan([user('u1','x')],'u1').attachments,[]);
});
test('an id that is not a user message, or is not there, retries nothing',()=>{
 const items=[reply('a1'),user('u1','x',{clientMessageId:'cm_1'})];
 assert.equal(retryPlan(items,'a1'),null);
 assert.equal(retryPlan(items,'nope'),null);
});
