"""Focused DEX field/name metadata; no instruction decompilation or execution."""
import json,zipfile,struct
from pathlib import Path
OUT=Path(__file__).parent
scope={
'Lcom/baicizhan/app/biz/ui/feature/study/enums/QuestionType;',
'Lcom/baicizhan/app/study/engine/contract/model/QuestionType;',
'Lcom/baicizhan/app/biz/game/model/ReviewMode;',
'Lcom/baicizhan/app/biz/ui/component/phrase/PhraseType;',
'Lcom/baicizhan/client/business/dataset/models/TopicLearnRecord;',
'Lcom/baicizhan/client/business/dataset/models/ScheduleRecord;',
'Lcom/baicizhan/app/biz/ui/feature/study/model/StudySessionWikiFlowPolicy;',
'Lcom/baicizhan/main/phrasetraining/data/bean/Phrase;',
}
u32=lambda b,p:struct.unpack_from('<I',b,p)[0]
def leb(b,p):
 v=0;s=0
 while True:
  x=b[p];p+=1;v|=(x&127)<<s
  if not x&128:return v,p
  s+=7
result={}
with zipfile.ZipFile('/Users/gqli/work/android/app/baicizhan.apk') as z:
 for n in z.namelist():
  if not n.endswith('.dex'):continue
  b=z.read(n);sc,so=struct.unpack_from('<II',b,56);strings=[]
  for i in range(sc):
   p=u32(b,so+i*4);_,p=leb(b,p);strings.append(b[p:b.index(0,p)].decode('utf-8',errors='replace'))
  tc,to=struct.unpack_from('<II',b,64);types=[strings[u32(b,to+4*i)] for i in range(tc)]
  fc,fo=struct.unpack_from('<II',b,80);fields=[]
  for i in range(fc):
   cl,t,si=struct.unpack_from('<HHI',b,fo+8*i);fields.append({'owner':types[cl],'name':strings[si],'type':types[t]})
  cc,co=struct.unpack_from('<II',b,96)
  for i in range(cc):
   p=co+i*32;c=types[u32(b,p)];data=u32(b,p+24)
   if c not in scope or not data:continue
   counts=[]
   for _ in range(4):v,data=leb(b,data);counts.append(v)
   out=[]
   for kind,num in zip(['static','instance'],counts[:2]):
    index=0
    for _ in range(num):
     delta,data=leb(b,data);flags,data=leb(b,data);index+=delta
     out.append({**fields[index],'kind':kind,'access_flags':flags})
   result[c]={'dex':n,'declared_fields':out}
(OUT/'focused-fields.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
for c,x in result.items():print(c,[(f['name'],f['type']) for f in x['declared_fields']])
