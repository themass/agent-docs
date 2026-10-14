"""Read-only ZIP/AXML/DEX metadata inspection; never executes APK code.
No Java decompilation. Export structural summaries, not a copy of lesson assets.
"""
import zipfile,struct,json,hashlib,collections,re
from pathlib import Path
APK=Path('/Users/gqli/work/android/app/baicizhan.apk')
OUT=Path(__file__).parent
u16=lambda b,p: struct.unpack_from('<H',b,p)[0]
u32=lambda b,p: struct.unpack_from('<I',b,p)[0]
def leb(b,p):
 v=0;s=0
 while True:
  x=b[p];p+=1;v|=(x&127)<<s
  if not x&128:return v,p
  s+=7

def axml(b):
 strings=[];events=[];p=u16(b,2)
 while p+8<=len(b):
  typ,head,size=struct.unpack_from('<HHI',b,p)
  if size<8 or p+size>len(b):raise ValueError('bad chunk')
  if typ==1:
   count=u32(b,p+8);flags=u32(b,p+16);start=u32(b,p+20)
   for i in range(count):
    q=p+start+u32(b,p+head+4*i)
    if flags&256:
     def length(q):
      n=b[q];q+=1
      if n&128:n=((n&127)<<8)|b[q];q+=1
      return n,q
     _,q=length(q);n,q=length(q);s=b[q:q+n].decode('utf-8',errors='replace')
    else:
     n=u16(b,q);q+=2
     if n&32768:n=((n&32767)<<16)|u16(b,q);q+=2
     s=b[q:q+2*n].decode('utf-16le',errors='replace')
    strings.append(s)
  elif typ==0x102:
   tag=strings[u32(b,p+20)];a=p+16+u16(b,p+24);step=u16(b,p+26);count=u16(b,p+28);attrs={}
   for i in range(count):
    q=a+i*step;name=strings[u32(b,q+4)];raw=u32(b,q+8);t=b[q+15];data=u32(b,q+16)
    value=strings[raw] if raw!=0xffffffff else strings[data] if t==3 else bool(data) if t==18 else data
    attrs[name]=value
   events.append({'tag':tag,'attrs':attrs})
  p+=size
 return events

def dex(b):
 count,off=struct.unpack_from('<II',b,56);ss=[]
 for i in range(count):
  q=u32(b,off+i*4);_,q=leb(b,q);end=b.index(0,q);ss.append(b[q:end].decode('utf-8',errors='replace'))
 tc,to=struct.unpack_from('<II',b,64);types=[ss[u32(b,to+i*4)] for i in range(tc)]
 mc,mo=struct.unpack_from('<II',b,88);methods=[]
 for i in range(mc):
  cl,pr,si=struct.unpack_from('<HHI',b,mo+8*i);methods.append((types[cl],ss[si]))
 cc,co=struct.unpack_from('<II',b,96);classes=[types[u32(b,co+32*i)] for i in range(cc)]
 return ss,classes,methods

with zipfile.ZipFile(APK) as z:
 names=z.namelist();manifest=axml(z.read('AndroidManifest.xml'))
 groups=collections.Counter('/'.join(n.split('/')[:4]) for n in names if n.startswith('assets/GameHost/'))
 summary={'apk':str(APK),'bytes':APK.stat().st_size,'sha256':hashlib.file_digest(APK.open('rb'),'sha256').hexdigest(),'zip_members':len(names),'manifest':manifest,'game_groups':dict(groups),'dex':[],'phrase_structure':{},'animation_paths':[n for n in names if n.startswith(('assets/spine/','assets/option_answer_animation/')) and n.endswith(('.skel','.json','.atlas.txt'))]}
 for n in ['assets/GameHost/bundled-game-catalog.json','assets/bcz_cocos_startup_screen/startup_screen.json']:
  summary[n]=json.loads(z.read(n))
 for n in names:
  if n.startswith('assets/phrasetraining/') and n.endswith('.json'):
   obj=json.loads(z.read(n))
   def shape(x,depth=0):
    if depth>3:return type(x).__name__
    if isinstance(x,dict):return {k:shape(v,depth+1) for k,v in x.items()}
    if isinstance(x,list):return {'count':len(x),'first_shape':shape(x[0],depth+1) if x else None}
    return type(x).__name__
   summary['phrase_structure'][n]={'bytes':z.getinfo(n).file_size,'sha256':hashlib.sha256(z.read(n)).hexdigest(),'shape':shape(obj)}
 candidates=[];class_all=[]
 patterns=re.compile(r'phrase|review|recite|learn|study|word|topic|option|memory|schedule|forget',re.I)
 for n in names:
  if not n.endswith('.dex'):continue
  ss,classes,methods=dex(z.read(n));class_all+=classes
  own=[c for c in classes if any(x in c.lower() for x in ['baicizhan','jiong','bcz'])]
  chosen=[c for c in own if patterns.search(c)]
  for c in chosen:candidates.append({'dex':n,'class':c,'methods':sorted(set(m for cl,m in methods if cl==c))})
  summary['dex'].append({'path':n,'bytes':z.getinfo(n).file_size,'strings':len(ss),'classes':len(classes),'app_namespace_classes':len(own),'candidate_classes':len(chosen)})
 summary['namespace_counts']=dict(collections.Counter('/'.join(c.split('/')[:3]) for c in class_all).most_common(30))
 (OUT/'structural-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 (OUT/'class-candidates.json').write_text(json.dumps(candidates,ensure_ascii=False,indent=2))
 print('Manifest identity',next((e for e in manifest if e['tag']=='manifest'),None))
 print('SDK',next((e for e in manifest if e['tag']=='uses-sdk'),None))
 print('DEX counts',summary['dex']);print('candidate count',len(candidates))
 print('phrase shapes',json.dumps(summary['phrase_structure'],ensure_ascii=False,indent=2)[:6500])
 print('game catalog',summary['assets/GameHost/bundled-game-catalog.json'])
