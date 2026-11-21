#!/usr/bin/env python3
"""抓维基文库《唐詩三百首》目录页链接的 295 个诗页快照（阶段 C 独立复核的第二条路线）。

为什么走这条路而不是只抓 128 卷：卷页实测多是 2–3 KB 的转引用壳（正文都在子页），
按卷复核要先抓 1000+ 子页；而目录页的链接直接指向这些诗页，295 页 × 约 500 字节，
action=query 一次 50 个标题 → 6 次请求即可全部拿到（限速 40s，约 5 分钟）。

**关键诚实前提**：这些页面不是同一种东西。每页 header 的来源声明决定它能不能当第二证——
  from = 唐詩三百首        → 该页声明抄自《唐詩三百首》，而我们的选本就是三百首，
                             拿选本正文去对它＝循环论证，**不算第二证**，只算文本旁注；
  notes 里引 全唐詩/卷NNN   → 该页声明转录自《全唐詩》，与选本异源，**可作第二证**；
  两者都没有                → 来源未声明，待核。
所以抓下来第一件事不是比对正文，而是把 provenance 读出来分档（tang300_ws_poems.py）。

快照: /tmp/src-dl/ws-poems/<safe>.txt；日志: /tmp/src-dl/ws-poems/fetch.log
可反复重跑（增量续传）。限速 UA 同其余脚本。
"""
import json
import pathlib
import re
import subprocess
import sys
import time

UA = 'poetry-chronology/1.0 (evidence sourcing; one-off research fetch)'
API = 'https://zh.wikisource.org/w/api.php'
SLEEP = 40
BATCH = 50
OUT = pathlib.Path('/tmp/src-dl/ws-poems')
OUT.mkdir(parents=True, exist_ok=True)
ENTRIES = pathlib.Path('/tmp/src-dl/tang300-index-entries.json')
PAGEINFO = pathlib.Path('/tmp/src-dl/tang300-index-pageinfo.json')


def safe(title):
    return re.sub(r'[^0-9A-Za-z一-鿿]', '_', title) + '.txt'


def fetch(titles):
    """批量取 wikitext。返回 {title: content}；失败的记日志不缓存（重跑续传）。"""
    got = {}
    r = subprocess.run(
        ['curl', '-s', '--max-time', '90', '-H', f'User-Agent: {UA}', '--get', API,
         '--data-urlencode', 'action=query',
         '--data-urlencode', 'titles=' + '|'.join(titles),
         '--data-urlencode', 'prop=revisions', '--data-urlencode', 'rvslots=main',
         '--data-urlencode', 'rvprop=content|timestamp', '--data-urlencode', 'format=json',
         '--data-urlencode', 'redirects=1'],
        capture_output=True, text=True)
    try:
        pages = json.loads(r.stdout)['query']['pages']
    except Exception:
        return got  # 限流/网络：调用方本轮不缓存，下次重跑再取
    by = {p['title']: p for p in pages.values()}
    for t in titles:
        p = by.get(t) or {}
        revs = p.get('revisions')
        if not revs:
            continue
        slot = revs[0]['slots']['main']
        c = slot.get('content') or slot.get('*')
        if c:
            got[t] = c
    return got


def main():
    ents = json.loads(ENTRIES.read_text(encoding='utf-8'))
    titles, seen = [], set()
    for e in ents:
        for l in e['links']:
            if l not in seen:
                seen.add(l)
                titles.append(l)
    # 只抓已确认存在的页面（pageinfo 是上一轮一次性批量 info 查询的结果）
    present = titles
    if PAGEINFO.exists():
        info = json.loads(PAGEINFO.read_text(encoding='utf-8'))
        present = [t for t in titles if 'missing' not in (info.get(t) or {'missing': 1})]
    log = (OUT / 'fetch.log').open('a', encoding='utf-8')
    todo = [t for t in present if not (OUT / safe(t)).exists()]
    log.write(f'session start: {len(present)} present, {len(todo)} to fetch\n')
    done = fail = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        got = fetch(chunk)
        for t in chunk:
            if t in got:
                (OUT / safe(t)).write_text(got[t], encoding='utf-8')
                log.write(f'{t} -> {safe(t)} {len(got[t])} chars\n')
                done += 1
            else:
                log.write(f'{t}: FAILED\n')
                fail += 1
        log.flush()
        if i + BATCH < len(todo):
            time.sleep(SLEEP)
    log.write(f'session done: wrote {done}, failed {fail}\n')
    log.close()
    print(f'done: wrote {done}, failed {fail}, cached {len(present) - len(todo)}')


if __name__ == '__main__':
    sys.exit(main())
