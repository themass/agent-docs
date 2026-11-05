const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
// The request body streamAgentMessage sends, with fetch stubbed. The server tells a retry from a
// new message by client_message_id, so the id the caller gives must reach the body, and a caller
// that gives none must send null rather than an invented id.
const source=fs.readFileSync(path.join(__dirname,'../lib/api/agent.ts'),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
const stubs={'./client':{apiJson:async()=>({}),API_BASE:'/api'},'./errors':{USER_NETWORK_ERROR:'net',USER_SERVICE_UNAVAILABLE:'down'}};
const mod={exports:{}};
new Function('require','module','exports',code)((name)=>stubs[name]??{},mod,mod.exports);

async function sentBody(body){
  let sent;
  global.fetch=async(url,init)=>{
    sent=JSON.parse(init.body);
    return {ok:true,body:{getReader:()=>({read:async()=>({done:true,value:undefined})})}};
  };
  await mod.exports.streamAgentMessage('as1',body,()=>{});
  return sent;
}

test('the message id the caller gives is sent with the message',async()=>{
  const sent=await sentBody({content:'我把结算接口拆成了两张表。',client_message_id:'cm_1'});
  assert.equal(sent.client_message_id,'cm_1');
  assert.equal(sent.content,'我把结算接口拆成了两张表。');
});
test('a caller that gives no id sends none',async()=>{
  const sent=await sentBody({content:'你好'});
  assert.equal(sent.client_message_id,null);
});
