#!/usr/bin/env python3
"""Sync TencentDB static headers and Hermes' official per-session affinity header."""
from __future__ import annotations
import argparse, sys
from pathlib import Path

STATIC_KEYS=(('TDAI_TEAM_ID','x-team-id'),('TDAI_AGENT_ID','x-agent-id'),('TDAI_TASK_ID','x-task-id'))

def load_env(path):
    out={}
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1); out[k.strip()]=v.strip().strip("'\"")
    return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--config',required=True); p.add_argument('--ids-file',default=''); p.add_argument('--require',action='store_true')
    a=p.parse_args(); config=Path(a.config); ids_path=Path(a.ids_file) if a.ids_file else config.parent/'tdai-hermes-ids.env'
    if not config.is_file():
        print(f'config not found: {config}',file=sys.stderr); return 1 if a.require else 0
    ids=load_env(ids_path)
    static={hdr:ids[key].strip() for key,hdr in STATIC_KEYS if ids.get(key,'').strip()}
    if len(static)<3:
        msg=f'incomplete TencentDB headers in {ids_path}; need TDAI_TEAM_ID, TDAI_AGENT_ID, TDAI_TASK_ID'
        if a.require: print(msg,file=sys.stderr); return 1
        print(msg)
        return 0
    try:
        from ruamel.yaml import YAML
    except ImportError:
        print('ruamel.yaml not installed; skip tdai header sync',file=sys.stderr); return 1 if a.require else 0
    y=YAML(); y.preserve_quotes=True; data=y.load(config.read_text(encoding='utf-8')) or {}
    model=data.setdefault('model',{})
    if not isinstance(model,dict): model={}; data['model']=model
    # Keep static headers for auxiliary/rebuild clients, but never persist a fake conversation id.
    dh=model.get('default_headers')
    if not isinstance(dh,dict): dh={}
    dh.update(static); dh.pop('x-conversation-id',None); model['default_headers']=dh
    model.pop('extra_headers',None)
    custom=data.get('custom_providers')
    if isinstance(custom,list):
        for entry in custom:
            if not isinstance(entry,dict): continue
            base=str(entry.get('base_url') or '')
            if '/hermes/' in base or ':8096' in base:
                eh=entry.get('extra_headers')
                if not isinstance(eh,dict): eh={}
                eh.update(static); eh.pop('x-conversation-id',None)
                entry['extra_headers']=eh
                entry['session_affinity_header']='x-conversation-id'
    with config.open('w',encoding='utf-8') as f: y.dump(data,f)
    print(f'updated {config} → static TencentDB headers + session_affinity_header=x-conversation-id')
    return 0
if __name__=='__main__': raise SystemExit(main())
