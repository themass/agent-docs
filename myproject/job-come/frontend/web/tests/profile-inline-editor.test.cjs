const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const cache = new Map();
function load(file, react = React) {
  if (react === React && cache.has(file)) return cache.get(file);
  const mod = {exports:{}};
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname,'..',file),'utf8'), {
    compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX},
  }).outputText;
  new Function('exports','require',code)(mod.exports,name=>{
    if(name==='react') return react;
    if(name==='react/jsx-runtime')return require(name);
    if(name==='@/lib/ui-context')return {experienceLabel:(a,b)=>`${a} · ${b}`};
    if(name==='@/components/resume/ProfilePhotoField')return {ProfilePhotoField:()=>null};
    if(name.startsWith('./'))return load(`components/profile/${name.slice(2)}.tsx`,react);
    throw new Error(name);
  });
  if(react===React)cache.set(file,mod.exports);
  return mod.exports;
}
const {ProfileDocumentEditor} = load('components/profile/ProfileDocumentEditor.tsx');
const {EducationAndSkills,DraftStringList} = load('components/profile/ProfileDocumentSections.tsx');
function setup() {
  const payload={contact:{name:'测试',email:'a@example.test',photo:{enabled:false},links:[{type:'作品',url:'https://example.test'}]},summary:'原始简介',
    experiences:[{id:'e1',company:'原公司',title:'工程师',start_date:'2020',scope:'原范围',highlights:['原要点'],skills:['Java'],confidence:'high'}],
    education:[{id:'edu1',school:'学校',degree:'本科',major:'计算机',start_date:'2016',end_date:'2020'}],
    projects:[{id:'proj1',name:'项目',scope:'项目范围',description:'背景',highlights:['项目要点']}],
    skills:[{name:'Java',level:'熟练',evidence:['e1']}],constraints:{retracted_claims:[{claim:'不能写',scope:'profile'}]},meta:{source_locale:'zh-CN'}};
  const profile={id:'p1',version:5,payload,sources:[]};
  const editor={draft:{base:profile,payload,conflict:null},dirty:false,busy:false,setPayload(fn){this.draft={...this.draft,payload:fn(this.draft.payload)}},downloadDraft(){},discard(){}};
  // Production setters are stable functions, not object methods.
  editor.setPayload=editor.setPayload.bind(editor);
  const props={profile,editor,sourceLocale:'zh-CN'};
  return {props,editor,payload,render:()=>ProfileDocumentEditor(props)};
}
function nodes(tree) {
  if(!tree || typeof tree!=='object')return [];
  if(Array.isArray(tree))return tree.flatMap(nodes);
  const children=[...React.Children.toArray(tree.props?.children),...React.Children.toArray(tree.props?.action)];
  return [tree,...children.flatMap(nodes)];
}
function field(tree,label) {
  const found=nodes(tree).find(n=>n.props?.label===label && typeof n.props?.onChange==='function');
  assert.ok(found,`missing editable field ${label}`);return found;
}
test('review document displays editable values at their original locations, without a second form',()=>{
  const s=setup();const html=renderToStaticMarkup(React.createElement(ProfileDocumentEditor,s.props));
  assert.match(html,/可直接编辑的简历/);assert.match(html,/编辑第1段经历公司/);assert.match(html,/编辑第1段工作要点第1条/);
  assert.match(html,/编辑第1个项目要点第1条/);assert.match(html,/编辑第1段教育学校/);
  assert.doesNotMatch(html,/快速编辑|展开表单编辑|保存档案/);
  assert.match(html,/data-path="experiences\[0\].highlights\[0\]"/);
});
test('editing a work field changes the shared draft and preserves hidden facts',()=>{
  const s=setup();field(s.render(),'第1段经历公司').props.onChange('新公司');
  assert.equal(s.editor.draft.payload.experiences[0].company,'新公司');
  assert.equal(s.payload.experiences[0].company,'原公司');
  assert.deepEqual(s.editor.draft.payload.constraints,s.payload.constraints);
  assert.equal(s.editor.draft.payload.experiences[0].confidence,'high');
  assert.deepEqual(s.editor.draft.payload.contact.photo,{enabled:false});
});
test('stable experience IDs keep edits on the correct record after reorder',()=>{
  const s=setup();const input=field(s.render(),'第1段经历职位');
  s.editor.setPayload(p=>({...p,experiences:[{id:'other',company:'other',title:'untouched',start_date:''},...p.experiences]}));
  input.props.onChange('新职位');
  assert.equal(s.editor.draft.payload.experiences[0].title,'untouched');assert.equal(s.editor.draft.payload.experiences[1].title,'新职位');
});
test('project description, scope and bullets write their own schema fields',()=>{
  const s=setup();field(s.render(),'第1个项目说明').props.onChange('新背景');field(s.render(),'第1个项目范围').props.onChange('新范围');
  field(s.render(),'第1个项目要点').props.onChange(['新要点']);
  assert.deepEqual(s.editor.draft.payload.projects[0],{...s.payload.projects[0],description:'新背景',scope:'新范围',highlights:['新要点']});
});
test('degree and major stay separate; skill evidence is not flattened away',()=>{
  const s=setup();const tree=EducationAndSkills({payload:s.payload,editor:s.editor});
  field(tree,'第1段教育学历').props.onChange('硕士');field(tree,'第1项技能').props.onChange('Java 研发');
  assert.equal(s.editor.draft.payload.education[0].major,'计算机');assert.equal(s.editor.draft.payload.education[0].degree,'硕士');
  assert.deepEqual(s.editor.draft.payload.skills[0],{name:'Java 研发',level:'熟练',evidence:['e1']});
});
test('contact editing preserves photo and links',()=>{
  const s=setup();field(s.render(),'邮箱').props.onChange('new@example.test');
  assert.equal(s.editor.draft.payload.contact.email,'new@example.test');
  assert.deepEqual(s.editor.draft.payload.contact.links,s.payload.contact.links);
  assert.deepEqual(s.editor.draft.payload.contact.photo,s.payload.contact.photo);
});
test('new record and bullet controls are located inside the document',()=>{
  const s=setup();const button=nodes(s.render()).find(n=>n.type==='button'&&n.props.children==='+ 添加经历');button.props.onClick();
  assert.equal(s.editor.draft.payload.experiences.length,2);assert.notEqual(s.editor.draft.payload.experiences[0].id,'e1');
  assert.equal(s.editor.draft.payload.experiences[1].company,'原公司');
  let items=['已有'];const tree=DraftStringList({items,label:'工作要点',onChange:next=>items=next});
  nodes(tree).find(n=>n.type==='button').props.onClick();assert.deepEqual(items,['已有','']);
});
test('conflicts remain visible in the same document and language switch is disabled when dirty',()=>{
  const s=setup();s.editor.draft.conflict={...s.props.profile,version:6};s.editor.dirty=true;s.props.onRelocalize=()=>{};
  const html=renderToStaticMarkup(React.createElement(ProfileDocumentEditor,s.props));assert.match(html,/你的编辑仍保留/);assert.match(html,/下载未保存内容/);
  const buttons=nodes(s.render()).filter(n=>n.type==='button'&&['中文','英文'].includes(n.props.children));assert.equal(buttons.length,2);buttons.forEach(b=>assert.equal(b.props.disabled,true));
});
function inlineHarness(multiline=false) {
  const slots=[];let cursor=0;let value='原文';
  const react={useState(initial){const i=cursor++;if(!(i in slots))slots[i]=initial;return[slots[i],v=>slots[i]=v]},useRef(initial){const i=cursor++;return slots[i]??(slots[i]={current:initial})},useLayoutEffect(){}};
  const {InlineProfileField}=load('components/profile/InlineProfileField.tsx',react);
  const render=()=>{cursor=0;return InlineProfileField({label:'测试字段',value,multiline,onChange:v=>value=v})};
  return {render,value:()=>value};
}
test('inline typing updates the parent draft immediately; blur is not the commit boundary',()=>{
  const h=inlineHarness();h.render().props.onClick();let input=h.render();assert.equal(input.type,'input');
  input.props.onChange({target:{value:'新内容'}});assert.equal(h.value(),'新内容');input.props.onBlur();assert.equal(h.render().type,'button');
});
test('Escape only cancels the current field edit',()=>{
  const h=inlineHarness();h.render().props.onClick();const input=h.render();input.props.onChange({target:{value:'临时'}});
  input.props.onKeyDown({key:'Escape',nativeEvent:{isComposing:false},preventDefault(){}});assert.equal(h.value(),'原文');assert.equal(h.render().type,'button');
});
test('multiline Enter and IME confirmation do not prematurely close the editor',()=>{
  const h=inlineHarness(true);h.render().props.onClick();let input=h.render();assert.equal(input.type,'textarea');
  input.props.onKeyDown({key:'Enter',nativeEvent:{isComposing:false},preventDefault(){}});assert.equal(h.render().type,'textarea');
  input.props.onKeyDown({key:'Enter',nativeEvent:{isComposing:true},ctrlKey:true,preventDefault(){}});assert.equal(h.render().type,'textarea');
  input.props.onKeyDown({key:'Enter',nativeEvent:{isComposing:false},ctrlKey:true,preventDefault(){}});assert.equal(h.render().type,'button');
});
test('raw markup remains escaped text rather than executable HTML',()=>{
  const s=setup();s.editor.setPayload(p=>({...p,summary:'<img src=x onerror=alert(1)>'}));
  const html=renderToStaticMarkup(React.createElement(ProfileDocumentEditor,s.props));assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img src="?x/);
});
