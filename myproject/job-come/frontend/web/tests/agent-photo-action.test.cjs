const {test}=require('node:test');
const assert=require('node:assert/strict');
const ts=require('typescript');
const fs=require('node:fs');
const path=require('node:path');
const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../lib/agent/photo-action.ts'),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
const mod={exports:{}};
new Function('exports',code)(mod.exports);
const parse=mod.exports.latestPhotoRequest;
const request={status:'photo_crop_required',session_id:'session',profile_id:'profile',message_id:'message',attachment_index:0,name:'photo.jpg'};
const tool=(value,name='jc_profile_photo_set')=>({id:'i',kind:'tool_result',name,result:JSON.stringify(value)});
test('recognizes real photo tool request and preserves reference',()=>{
 assert.deepEqual(parse([tool(request)],'session'),request);
});
test('ignores assistant text, unknown tools, malformed JSON and other sessions',()=>{
 assert.equal(parse([{kind:'assistant',content:JSON.stringify(request)}],'session'),null);
 assert.equal(parse([tool(request,'other_tool')],'session'),null);
 assert.equal(parse([tool(request)],'someone_else'),null);
 assert.equal(parse([{...tool(request),result:'not json'}],'session'),null);
});
test('rejects invalid index and incomplete action contracts',()=>{
 for(const attachment_index of [-1,.5,'0',null]) assert.equal(parse([tool({...request,attachment_index})],'session'),null);
 assert.equal(parse([tool({...request,message_id:undefined})],'session'),null);
});
test('multi-photo selection is not mistaken for a ready crop',()=>{
 assert.equal(parse([tool({...request,status:'photo_selection_required'})],'session'),null);
});
