#!/usr/bin/env python3
"""抓取维基文库《全唐詩》所需各卷的 wikitext 快照（阶段 C 独立复核的地基）。
用法: python3 -I fetch_quantangshi.py [volumes.txt]
  volumes.txt 每行一个卷号（数字）；默认 tang300-volumes.txt。
快照: /tmp/src-dl/quantangshi/volNNN.txt；日志: /tmp/src-dl/quantangshi/fetch.log
命名规则不统一（卷48 的裸名是个 30 字节壳，真页在卷048；卷115 真页就是裸名），
所以先试补零名（卷048/卷115），拿不到像样的正文再试裸名（卷48）。
限速：每次 API 调用之间 sleep 40s。UA 自报家门。"""
import json
import pathlib
import subprocess
import sys
import time

OUT = pathlib.Path('/tmp/src-dl/quantangshi')
OUT.mkdir(parents=True, exist_ok=True)
UA = 'poetry-chronology/1.0 (evidence sourcing; one-off research fetch)'
API = 'https://zh.wikisource.org/w/api.php'
SLEEP = 40


def fetch_page(title):
    """返回 (ok, content_or_none, note)。redirect 跟一次。"""
    r = subprocess.run(
        ['curl', '-s', '--max-time', '40', '-H', f'User-Agent: {UA}', '--get', API,
         '--data-urlencode', 'action=query', '--data-urlencode', f'titles={title}',
         '--data-urlencode', 'prop=revisions', '--data-urlencode', 'rvslots=main',
         '--data-urlencode', 'rvprop=content', '--data-urlencode', 'format=json',
         '--data-urlencode', 'redirects=1'],
        capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        return False, None, 'non-json (rate limited?)'
    pages = list(d.get('query', {}).get('pages', {}).values())
    if not pages:
        return False, None, 'no pages'
    p = pages[0]
    if 'missing' in p:
        return False, None, 'missing'
    revs = p.get('revisions')
    if not revs:
        return False, None, 'no revisions'
    slot = revs[0]['slots']['main']
    content = slot.get('content') or slot.get('*')
    if content is None:
        return False, None, 'no content'
    if content.strip().startswith('#REDIRECT'):
        return fetch_page_redirect_target(content)
    return True, content, p['title']


def fetch_page_redirect_target(content):
    import re
    m = re.search(r'#REDIRECT\s*\[\[([^|\]]+)', content, re.I)
    if not m:
        return False, None, 'unparsable redirect'
    time.sleep(SLEEP)
    return fetch_page(m.group(1))


def main():
    args = sys.argv[1:]
    volfile = pathlib.Path(args[0]) if args else pathlib.Path(__file__).parent / 'tang300-volumes.txt'
    vols = [v.strip() for v in volfile.read_text(encoding='utf-8').split() if v.strip()]
    log = (OUT / 'fetch.log').open('a', encoding='utf-8')
    done = skip = fail = 0
    for n in vols:
        out = OUT / f'vol{int(n):03d}.txt'
        if out.exists() and out.stat().st_size > 2000:
            skip += 1
            continue
        got = None
        for title in (f'全唐詩/卷{int(n):03d}', f'全唐詩/卷{int(n)}'):
            ok, content, note = fetch_page(title)
            if ok and content and len(content) > 1500:
                got = content
                log.write(f'{title} -> {out.name} {len(content)} chars\n')
                break
            log.write(f'{title}: {note}\n')
            log.flush()
            time.sleep(SLEEP)
        if got:
            out.write_text(got, encoding='utf-8')
            done += 1
        else:
            fail += 1
            log.write(f'卷{n}: FAILED both name forms\n')
        log.flush()
        time.sleep(SLEEP)
    log.write(f'session done: wrote {done}, skipped {skip}, failed {fail}\n')
    log.close()
    print(f'done: wrote {done}, skipped {skip}, failed {fail}')


if __name__ == '__main__':
    main()
