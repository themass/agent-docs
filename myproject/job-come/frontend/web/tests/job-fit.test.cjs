const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const ts=require('typescript');
// The job list fills in a score for a job that was saved without one (E-16). These tests load the
// real helper; the page only calls it.
const source=fs.readFileSync(path.join(__dirname,'../lib/job-fit.ts'),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
const mod={exports:{}};
new Function('require','module','exports',code)(require,mod,mod.exports);
const withFit=mod.exports.withFit;

const job={id:'job_1',profile_id:'p1',company:'示例科技',title:'用户增长运营专员',source_url:null,requirements:{},fit_score:null,fit_recommendation:null,fit_gaps:[],fit_blockers:[]};
const fit={score:30,recommendation:'practice',gaps:['无增长经验'],blockers:[],evidence_profile_version:3,requirement_evidence:[],summary:'匹配偏低',elevate_hints:[],dimensions:{},legitimacy:null};

test('a saved job without a score gets the score, its reason and its gaps',()=>{
 const out=withFit(job,fit);
 assert.equal(out.fit_score,30);
 assert.equal(out.fit_recommendation,'practice');
 assert.deepEqual(out.fit_gaps,['无增长经验']);
 assert.equal(out.fit_summary,'匹配偏低');
});
test('the job itself is unchanged apart from the score',()=>{
 const out=withFit(job,fit);
 assert.equal(out.id,'job_1');
 assert.equal(out.company,'示例科技');
 assert.equal(out.title,'用户增长运营专员');
});
test('filling the score does not mutate the job it was given',()=>{
 withFit(job,fit);
 assert.equal(job.fit_score,null);
});
