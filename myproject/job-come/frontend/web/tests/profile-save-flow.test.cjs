const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const draftExports = load('../lib/profile-draft.ts', () => {throw new Error('unexpected import')});
function load(file, dependency) {
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, file), 'utf8'), {
    compilerOptions: {target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX},
  }).outputText;
  const mod = {exports:{}};
  new Function('exports','require',code)(mod.exports, dependency);
  return mod.exports;
}
const profile = () => ({id:'p1',version:1,status:'draft',payload:{contact:{name:'test'},summary:'',experiences:[],education:[]}});
function setupHook(api) {
  const slots=[]; let cursor=0; let pending=[]; let result;
  const events = new Map();
  const equal = (a,b) => a && b && a.length===b.length && a.every((v,i)=>Object.is(v,b[i]));
  const react = {
    useState(initial) { const i=cursor++; if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;
      return [slots[i],v=>{slots[i]=typeof v==='function'?v(slots[i]):v}]; },
    useRef(initial){const i=cursor++; return slots[i]??(slots[i]={current:initial});},
    useCallback(fn,deps){const i=cursor++; if(!slots[i]||!equal(slots[i].deps,deps))slots[i]={deps,fn};return slots[i].fn;},
    useEffect(fn,deps){const i=cursor++; if(!slots[i]||!equal(slots[i].deps,deps)){const old=slots[i];slots[i]={deps};pending.push(()=>{old?.cleanup?.();slots[i].cleanup=fn()})}},
  };
  const listeners={addEventListener:(n,fn)=>events.set(n,fn),removeEventListener:(n,fn)=>{if(events.get(n)===fn)events.delete(n)}};
  global.window={...listeners,confirm:()=>false}; global.document={...listeners};
  const {useProfileDraft} = load('../lib/hooks/useProfileDraft.ts', name => {
    if(name==='react')return react;
    if(name==='@/lib/api/profile')return {updateProfile:api};
    if(name==='@/lib/profile-draft')return draftExports;
    if(name==='@/lib/api/user-error')return {userFacingApiError:e=>e.message};
    throw new Error(name);
  });
  const saved=[]; const onSaved=p=>saved.push(p);
  return {saved, events, render(p){cursor=0;result=useProfileDraft(p,onSaved);const effects=pending;pending=[];effects.forEach(fn=>fn());cursor=0;result=useProfileDraft(p,onSaved);return result;}};
}
test('failed save retains typed content and remains dirty for retry', async () => {
  const p=profile();let fail=true;const h=setupHook(async(id,payload)=>{if(fail)throw new Error('offline');return {...p,version:2,payload}});
  let editor=h.render(p);editor.setPayload(v=>({...v,summary:'typed'}));editor=h.render(p);
  assert.equal(await editor.save(),false);
  editor=h.render(p);assert.equal(editor.draft.payload.summary,'typed');assert.equal(editor.dirty,true);assert.equal(editor.message,'offline');assert.equal(h.saved.length,0);
  fail=false;assert.equal(await editor.save(),true);editor=h.render(h.saved[0]);assert.equal(editor.dirty,false);
});
test('concurrent save clicks share one request and preserve later typing', async () => {
  let resolve;let count=0;const p=profile();const h=setupHook((id,payload)=>{count++;return new Promise(r=>resolve=()=>r({...p,version:2,payload}))});
  let editor=h.render(p);editor.setPayload(v=>({...v,summary:'first'}));editor=h.render(p);
  const a=editor.save(),b=editor.save();assert.equal(a,b);assert.equal(count,1);
  editor.setPayload(v=>({...v,summary:'later'}));resolve();assert.equal(await a,false);
  editor=h.render(h.saved[0]);assert.equal(editor.draft.payload.summary,'later');assert.equal(editor.dirty,true);
});
test('refresh and close are guarded while dirty, and clean saves release guard', async () => {
  const p=profile();const h=setupHook(async(id,payload)=>({...p,version:2,payload}));let editor=h.render(p);
  editor.setPayload(v=>({...v,summary:'typed'}));editor=h.render(p);
  let prevented=false;const e={preventDefault(){prevented=true}};h.events.get('beforeunload')(e);assert.equal(prevented,true);assert.equal(e.returnValue,'');
  await editor.save();editor=h.render(h.saved[0]);prevented=false;h.events.get('beforeunload')({preventDefault(){prevented=true}});assert.equal(prevented,false);
});
test('server conflict keeps edits and never sends a blind overwrite', async () => {
  let calls=0;const p=profile();const h=setupHook(async()=>{calls++});let editor=h.render(p);
  editor.setPayload(v=>({...v,summary:'typed'}));editor=h.render({...p,version:2,payload:{...p.payload,summary:'agent'}});
  assert.equal(await editor.save(),false);editor=h.render({...p,version:2,payload:{...p.payload,summary:'agent'}});
  assert.equal(calls,0);assert.equal(editor.draft.payload.summary,'typed');assert.equal(editor.draft.conflict.version,2);
});
function workflow(beforeContinue) {
  const calls=[];
  const {ResumeWorkflowActions}=load('../components/resume/ResumeWorkflowActions.tsx',name=>{
    if(name==='react')return {useState:v=>[v,()=>{}]};
    if(name==='react/jsx-runtime')return require(name);
    if(name==='@/lib/api/profile')return {confirmProfile:async()=>calls.push('confirm'),getProfile:async()=>profile()};
    if(name==='@/lib/api/user-error')return {userFacingApiError:e=>e.message};
    if(name==='@/lib/profile-parse')return {isProfileParseBlocking:()=>false};
    if(name==='@/lib/elevation-techniques')return {LEVEL_GUIDE:{}};
    throw new Error(name);
  });
  const tree=ResumeWorkflowActions({profile:profile(),step:'review',isConfirmed:false,beforeContinue,
    onProfileChange:()=>calls.push('refresh'),onStepChange:()=>calls.push('step')});
  const button=tree.props.children.find(v=>v?.type==='button');
  return {calls,click:button.props.onClick};
}
test('confirmation is not called if pending edits fail to save', async()=>{
  const flow=workflow(async()=>false);await flow.click();await new Promise(r=>setImmediate(r));assert.deepEqual(flow.calls,[]);
});
test('confirmation runs strictly after the draft save succeeds', async()=>{
  let finish;const flow=workflow(()=>new Promise(r=>finish=r));flow.click();assert.deepEqual(flow.calls,[]);
  finish(true);await new Promise(r=>setImmediate(r));assert.deepEqual(flow.calls,['confirm','refresh','step']);
});
