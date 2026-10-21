const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
function setup(api) {
  const slots=[]; let cursor=0, pending=[];
  const same=(a,b)=>a&&b&&a.length===b.length&&a.every((v,i)=>Object.is(v,b[i]));
  const react={
    useState(v){const i=cursor++; if(!(i in slots))slots[i]=typeof v==='function'?v():v;return [slots[i],v=>slots[i]=typeof v==='function'?v(slots[i]):v];},
    useRef(v){const i=cursor++;return slots[i]??(slots[i]={current:v});},
    useCallback(fn,deps){const i=cursor++;if(!slots[i]||!same(slots[i].deps,deps))slots[i]={deps,fn};return slots[i].fn;},
    useEffect(fn,deps){const i=cursor++;if(!slots[i]||!same(slots[i].deps,deps)){const old=slots[i];slots[i]={deps};pending.push(()=>{old?.cleanup?.();slots[i].cleanup=fn();});}},
  };
  const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../lib/hooks/useResumeQualityReview.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const mod={exports:{}};
  new Function('exports','require',code)(mod.exports,name=>{
    if(name==='react')return react;
    if(name==='@/lib/api/resume')return {reviewBeforeExport:api};
    if(name==='@/lib/api/user-error')return {userFacingExportError:e=>e.message};
    if(name==='@/lib/review-progress')return {REVIEW_TIMEOUT_MS:180000,advanceReviewProgress:(s,e)=>({...s,[e.stage]:e.status})};
    throw Error(name);
  });
  global.window={setTimeout,clearTimeout};
  return {render(props){cursor=0;let result=mod.exports.useResumeQualityReview(props);const effects=pending;pending=[];effects.forEach(fn=>fn());cursor=0;return mod.exports.useResumeQualityReview(props);},dispose(){slots.forEach(s=>s?.cleanup?.());}};
}
const target={profileId:'p1',profileVersion:1,canReview:true,draftId:'d1',locale:'zh-CN',elevationLevel:'standard'};
const tick=()=>new Promise(r=>setTimeout(r,8));
test('a generated draft is reviewed automatically and switching steps reuses its result',async()=>{
  let calls=0;const h=setup(async()=>{calls++;return {draft_id:'d1',status:'passed',issues:[]};});
  try {h.render(target);await tick();let q=h.render(target);assert.equal(calls,1);assert.equal(q.review.status,'passed');q=h.render({...target});await tick();assert.equal(calls,1);}finally{h.dispose();}
});
test('changed draft cancels stale requests and does not inherit verdict or acknowledgement',async()=>{
  const requests=[];const h=setup((...args)=>new Promise(resolve=>requests.push({args,resolve})));
  try {h.render(target);await tick();let q=h.render(target);q.setAcknowledged(true);q=h.render({...target,draftId:'d2'});assert.equal(q.review,null);assert.equal(q.acknowledged,false);assert.equal(requests[0].args[4].signal.aborted,true);await tick();requests[0].resolve({draft_id:'d1',status:'passed',issues:[]});requests[1].resolve({draft_id:'d2',status:'failed',issues:[{message:'核对数字'}]});await tick();q=h.render({...target,draftId:'d2'});assert.equal(q.review.draft_id,'d2');}finally{h.dispose();}
});
test('unavailable reviewer is not a pass; skip cancels and permits continuing',async()=>{
  const h=setup(()=>new Promise(()=>{}));
  try{h.render(target);await tick();let q=h.render(target);assert.equal(q.reviewBusy,true);q.skipReview();q=h.render(target);assert.equal(q.review,null);assert.equal(q.skipped,true);assert.equal(q.reviewBusy,false);}finally{h.dispose();}
});
test('no review starts before a draft exists or without permission',async()=>{
  let calls=0;const h=setup(async()=>{calls++;});try{h.render({...target,draftId:null});await tick();h.render({...target,canReview:false});await tick();assert.equal(calls,0);}finally{h.dispose();}
});
test('review failure remains visible and retry performs a fresh check',async()=>{
  let calls=0;const h=setup(async()=>{if(++calls===1)throw Error('service unavailable');return {draft_id:'d1',status:'passed',issues:[]};});
  try{h.render(target);await tick();let q=h.render(target);assert.equal(q.review,null);assert.equal(q.reviewError,'service unavailable');await q.runReview();q=h.render(target);assert.equal(q.review.status,'passed');assert.equal(q.reviewError,null);assert.equal(calls,2);}finally{h.dispose();}
});
test('profile version changes invalidate the result even for the same draft ID',async()=>{
  let calls=0;const h=setup(async()=>{calls++;return {draft_id:'d1',status:'passed',issues:[]};});
  try{h.render(target);await tick();assert.equal(h.render(target).review.status,'passed');let q=h.render({...target,profileVersion:2});assert.equal(q.review,null);await tick();assert.equal(h.render({...target,profileVersion:2}).review.status,'passed');assert.equal(calls,2);}finally{h.dispose();}
});
function component(file, overrides={}) {
  const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../components/resume/',file+'.tsx'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const mod={exports:{}};
  new Function('exports','require',code)(mod.exports,name=>{
    if(name in overrides)return overrides[name];
    if(name==='react'||name==='react/jsx-runtime')return require(name);
    if(name==='@/lib/api/resume')return {exportProfile:()=>{throw Error('SSR must not export');}};
    if(name==='@/lib/api/user-error')return {userFacingExportError:e=>e.message};
    if(name==='./ExportReviewProgress')return {ExportReviewProgress:component('ExportReviewProgress')};
    if(name==='@/lib/review-progress'){
      const mod={exports:{}};
      const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../lib/review-progress.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
      new Function('exports',code)(mod.exports);return mod.exports;
    }
    throw Error(name);
  });return mod.exports[file];
}
const quality = (patch={}) => ({review:null,reviewBusy:false,reviewError:null,acknowledged:false,skipped:false,reviewProgress:{},reviewStartedAt:null,runReview(){},skipReview(){},setAcknowledged(){},...patch});
const html=(C,props)=>require('react-dom/server').renderToStaticMarkup(require('react').createElement(C,props));
test('optimization panel exposes actionable findings before export',()=>{
  const C=component('ResumeQualityPanel');
  const text=html(C,{quality:quality({review:{status:'failed',reviewed:true,issues:[{message:'数字需要核对',severity:'error'}]}}),onRegenerate(){},onEditProfile(){}});
  assert.match(text,/优化稿内容检查/);assert.match(text,/数字需要核对/);assert.match(text,/修改档案事实/);assert.match(text,/重新生成优化稿/);assert.doesNotMatch(text,/回到优化预览修改/);
});
test('export renders the existing verdict and formats without starting a review',()=>{
  const C=component('ResumeExportStep');
  const text=html(C,{quality:quality({review:{status:'passed',reviewed:true,issues:[]}}),profileId:'p1',canExport:true,locale:'zh-CN',elevationLevel:'standard',draftId:'d1'});
  assert.match(text,/直接选择格式下载/);assert.match(text,/生成 PDF/);assert.doesNotMatch(text,/重新检查|导出前质检/);
});
test('export review outage permits download but unacknowledged findings require acknowledgement',()=>{
  const C=component('ResumeExportStep');const props={profileId:'p1',canExport:true,locale:'zh-CN',elevationLevel:'standard',draftId:'d1'};
  const unavailable=html(C,{...props,quality:quality({reviewError:'offline'})});
  assert.match(unavailable,/不代表检查通过/);assert.doesNotMatch(unavailable,/disabled=""/);
  const failed=html(C,{...props,quality:quality({review:{status:'failed',reviewed:true,issues:[{message:'核对数字',severity:'error'}]}})});
  assert.match(failed,/我已了解，继续下载/);assert.match(failed,/disabled=""/);
});
test('studio owns the reviewer and renders it on the optimization step, not only on export',()=>{
  let observed;
  const C=component('ResumeStudio',{
    '@/lib/profile-parse':{isProfileParseBlocking:()=>false},
    '@/lib/hooks/useResumeQualityReview':{useResumeQualityReview:target=>{observed=target;return quality({review:{status:'passed',reviewed:true,issues:[]}});}},
    '@/components/resume/ElevatePreviewPanel':{ElevatePreviewPanel:props=>require('react').createElement('div',null,props.rail)},
    '@/components/resume/ResumeQualityPanel':{ResumeQualityPanel:component('ResumeQualityPanel')},
    '@/components/resume/ResumeExportStep':{ResumeExportStep:()=>{throw Error('download must not mount during optimization');}},
    '@/components/profile/ProfileIntakePanel':{ProfileIntakePanel:()=>null},
    '@/components/profile/ProfileOverview':{ProfileOverview:()=>null},
    '@/components/profile/ProfileUploader':{ProfileUploader:()=>null},
    '@/components/resume/EvidencePanel':{EvidencePanel:()=>null},
    '@/components/resume/WritingOptionsPanel':{WritingOptionsPanel:()=>null},
    '@/lib/api/profile':{},
  });
  const props={profile:{id:'p1',version:1},isConfirmed:true,canExport:true,activeStep:'elevate',generateTick:0,exportCtx:{draftId:'d1',profileVersion:1,locale:'zh-CN',level:'standard'}};
  assert.match(html(C,props),/优化稿内容检查/);assert.equal(observed.canReview,true);
  assert.doesNotMatch(html(C,{...props,profile:{id:'p1',version:2}}),/优化稿内容检查/);assert.equal(observed.canReview,false);
});

test('export retains real review stages and animation while the shared task is running',()=>{
  const C=component('ResumeExportStep');
  const props={profileId:'p1',canExport:true,locale:'zh-CN',elevationLevel:'standard',draftId:'d1'};
  const state=quality({reviewBusy:true,reviewStartedAt:Date.now()-10000,reviewProgress:{read:'done',rules:'done',model:'running'}});
  const text=html(C,{...props,quality:state});
  assert.match(text,/role="progressbar"/);assert.match(text,/aria-valuenow="2"/);
  assert.match(text,/已完成 2\/4 项/);assert.match(text,/width:50%/);
  assert.match(text,/模型核对事实与表达/);assert.match(text,/进行中…/);assert.match(text,/animate-pulse/);
  assert.equal((text.match(/停止等待，直接下载/g)||[]).length,1);
  for(const patch of [{review:{status:'passed',reviewed:true,issues:[]}}, {skipped:true}, {reviewError:'offline'}]){
    const settled=html(C,{...props,quality:quality(patch)});
    assert.doesNotMatch(settled,/role="progressbar"|animate-pulse/);
  }
});
