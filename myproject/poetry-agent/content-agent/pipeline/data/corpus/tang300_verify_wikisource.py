#!/usr/bin/env python3
"""阶段 C 第二步：对维基文库《全唐詩》录入本逐字复核三百首正文（独立第二证）。

前置：fetch_quantangshi.py 已把各卷 wikitext 快照抓到 /tmp/src-dl/quantangshi/volNNN.txt。
本脚本读 tang300-dual-proof.json（366 首 + 御定给的《全唐詩》卷号）与选本正文，
在对应卷页快照里找这首诗。

两种页面结构都支持（维基文库《全唐詩》各卷不统一）：
  - 内联：<poem>…</poem> 直接在卷页里（如卷224 杜甫）；
  - 转引用：每首诗是 `{{:詩題 (作者)}}` 指到子页（如卷125）——默认只登记「待抓子页」，
    加 --fetch-children 才批量抓子页（action=query 一次 50 个标题，同样限速）。
匹配不靠标题：把整页（或子页）wikitext 去掉 {{…}} 模板、HTML 标签、标点后，
找「选本正文（去标点、折叠异体字）」是否为其中连续子串——各卷排版不同不影响判定。
折叠表与双证脚本同一份（import 复用，不抄第二份）。

作者双证旁注：作者名以 `== 作者 ==` 出现在卷页、或子页标题括号里，记 author_on_page。

用法: python3 -I tang300_verify_wikisource.py [--fetch-children]
输出: tang300-wikisource-proof.json / .md。可反复重跑（增量，快照缓存）。
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from tang300_dual_proof import fold, strip_punct, char_diff, cn_volume_to_int  # noqa: E402  同一份规则，不抄第二份

HERE = pathlib.Path(__file__).parent
SNAP = pathlib.Path('/tmp/src-dl/quantangshi')
UA = 'poetry-chronology/1.0 (evidence sourcing; one-off research fetch)'
API = 'https://zh.wikisource.org/w/api.php'
SLEEP = 40
BATCH = 45  # action=query titles 上限 50，留余量


def canon_body(paras):
    return fold(strip_punct(''.join(paras)))


def strip_markup(text):
    """去 <poem>/HTML/模板，只留正文顺序。{{…}} 与 <…> 都整块删（含嵌套一层）。"""
    for _ in range(3):
        text = re.sub(r'\{\{[^{}]*\}\}', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    # header2/Collection header 的元数据行（| key = value）
    text = re.sub(r'(?m)^\s*\|[^=]*=.*$', '', text)
    return text


def norm_page(text):
    return fold(strip_punct(strip_markup(text)))


def locate_in_page(canonical, page_norm):
    """返回 ('EXACT', pos) 或 ('PARTIAL', 最长公共前缀长度)。"""
    pos = page_norm.find(canonical)
    if pos >= 0:
        return 'EXACT', pos
    # 找最长公共片段起点：用首 12 字定位，再逐字对齐看差在哪
    head = canonical[:12]
    p = page_norm.find(head)
    if p < 0:
        return 'MISS', None
    k = 12
    while k < len(canonical) and p + k < len(page_norm) and page_norm[p + k] == canonical[k]:
        k += 1
    return 'PARTIAL', (p, k)


def anchor_before(page_norm, pos):
    """回找匹配位置之前**最近的条目锚**。子串命中本身不回答「命中的真是这首吗」——
    20 字的五绝完全可能嵌进更长的诗里；锚才是归属证据。卷页两种排版都认（实测）：
      内联条目体：`卷301_23 《故行宮》王建` → 去标点后成 `卷301_23故行宮王建`（卷号_序号留在文本里）；
      分节标题体：`===宮詞二首===`（`=` 不在标点表里，原样留下）。
    取 end() 最大的那个 = 紧贴匹配之前。找不到锚不改变判定，但如实记 None——
    合入迁移时只收带锚的命中（无锚的进人工清单，不自动入库）。"""
    found = []
    for m in re.finditer(r'卷\d+_\d+.{2,16}', page_norm[:pos]):
        found.append((m.end(), m.group(0)[:34]))
    for m in re.finditer(r'={2,4}[^=]{2,30}={2,4}', page_norm[:pos]):
        found.append((m.end(), m.group(0)[:34]))
    if not found:
        return None
    return max(found)[1]


def fetch_children(titles):
    """批量抓子页 wikitext，缓存到 SNAP/child/。返回 {title: content}。"""
    cache = SNAP / 'child'
    cache.mkdir(parents=True, exist_ok=True)
    out = {}
    todo = []
    for t in titles:
        f = cache / (re.sub(r'[^0-9A-Za-z一-鿿]', '_', t) + '.txt')
        if f.exists():
            out[t] = f.read_text(encoding='utf-8')
        else:
            todo.append((t, f))
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        r = subprocess.run(
            ['curl', '-s', '--max-time', '60', '-H', f'User-Agent: {UA}', '--get', API,
             '--data-urlencode', 'action=query',
             '--data-urlencode', 'titles=' + '|'.join(t for t, _ in chunk),
             '--data-urlencode', 'prop=revisions', '--data-urlencode', 'rvslots=main',
             '--data-urlencode', 'rvprop=content', '--data-urlencode', 'format=json',
             '--data-urlencode', 'redirects=1'],
            capture_output=True, text=True)
        try:
            pages = json.loads(r.stdout)['query']['pages']
        except Exception:
            print(f'batch failed at {i}（限流？稍后重跑本脚本即可续传）')
            break
        by_title = {p['title']: p for p in pages.values()}
        for t, f in chunk:
            p = by_title.get(t) or {}
            revs = p.get('revisions')
            if revs:
                c = revs[0]['slots']['main'].get('content') or revs[0]['slots']['main'].get('*') or ''
                f.write_text(c, encoding='utf-8')
                out[t] = c
        time.sleep(SLEEP)
    return out


def ws_search(search_text, ns=0):
    """维基文库全文检索（CirrusSearch）：拿诗的首 12 字找页面。返回候选标题列表。"""
    r = subprocess.run(
        ['curl', '-s', '--max-time', '40', '-H', f'User-Agent: {UA}', '--get', API,
         '--data-urlencode', 'action=query', '--data-urlencode', 'list=search',
         '--data-urlencode', f'srsearch={search_text}', '--data-urlencode', f'srsnamespace={ns}',
         '--data-urlencode', 'srlimit=10', '--data-urlencode', 'format=json'],
        capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except Exception:
        return []
    return [hit['title'] for hit in d.get('query', {}).get('search', [])]


def fetch_single(title):
    """抓一个页面的 wikitext（带缓存）。"""
    cache = SNAP / 'child'
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / (re.sub(r'[^0-9A-Za-z一-鿿]', '_', title) + '.txt')
    if f.exists():
        return f.read_text(encoding='utf-8')
    r = subprocess.run(
        ['curl', '-s', '--max-time', '40', '-H', f'User-Agent: {UA}', '--get', API,
         '--data-urlencode', 'action=query', '--data-urlencode', f'titles={title}',
         '--data-urlencode', 'prop=revisions', '--data-urlencode', 'rvslots=main',
         '--data-urlencode', 'rvprop=content', '--data-urlencode', 'format=json',
         '--data-urlencode', 'redirects=1'],
        capture_output=True, text=True)
    try:
        p = list(json.loads(r.stdout)['query']['pages'].values())[0]
        c = p['revisions'][0]['slots']['main'].get('content') or p['revisions'][0]['slots']['main'].get('*')
    except Exception:
        return None
    if c:
        f.write_text(c, encoding='utf-8')
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fetch-children', action='store_true',
                    help='对转引用型卷页批量抓诗子页（限速，慢；不抓则记 TRANSCLUDE）')
    ap.add_argument('--search', action='store_true',
                    help='本地映射卷没命中时，按正文首句检索维基文库定位真页（限速，慢）')
    args = ap.parse_args()
    root = pathlib.Path('/Users/gqli/work/xuexi/chinese-poetry')

    results0 = json.loads((HERE / 'tang300-dual-proof.json').read_text(encoding='utf-8'))
    sel = json.loads((root / '全唐诗/唐诗三百首.json').read_text(encoding='utf-8'))
    by_seq = {i + 1: p for i, p in enumerate(sel)}

    out, counts = [], __import__('collections').Counter()
    for r in results0:
        seq, author, title = r['seq'], r['author'], r['title']
        vol = r.get('quantangshi_volume')
        paras = by_seq[seq]['paragraphs']
        body = canon_body(paras)
        raw_body = strip_punct(''.join(paras))  # 去标点、未折叠：判 RAW/FOLD 用
        rec = {'seq': seq, 'title': title, 'author': author, 'quantangshi_volume': vol}

        def judge(raw_page, page_label):
            """在一页 wikitext 上判这首诗；返回是否命中（并写进 rec）。"""
            page = norm_page(raw_page)
            verdict, pos = locate_in_page(body, page)
            rec['author_on_page'] = f'== {author} ==' in raw_page or f'({author})' in raw_page
            if verdict == 'EXACT':
                rec['ws_page'] = page_label
                # 归属旁注：紧贴命中之前的条目锚（见 anchor_before）。合入迁移只收带锚的。
                rec['ws_anchor'] = anchor_before(page, pos)
                unpunct = strip_punct(strip_markup(raw_page))
                if raw_body in unpunct:
                    rec['ws'] = 'WS_RAW_EXACT'
                else:
                    rec['ws'] = 'WS_FOLD_EXACT'
                    # 折叠后才一致的，记下**实际差在哪几对字**——断言要写得出具体字符，不能只说「折叠过」。
                    # 可行是因为 fold 不增删字符：page_norm 与 unpunct 逐位对齐，
                    # 在折叠页上定位（pos），到未折叠页同位置取页面原字与选本原字比。
                    pairs = {f'{a}/{b}' for a, b in zip(raw_body, unpunct[pos:pos + len(raw_body)])
                             if a != b}
                    rec['ws_fold_chars'] = '、'.join(sorted(pairs)) or '折叠位点未在原文层重现（页面 markup 差异）'
                return True
            if verdict == 'PARTIAL':
                p, k = pos
                rec.setdefault('ws_variants', []).append(
                    {'page': page_label,
                     'detail': f'前 {k} 字一致后分叉（{page[p + k]}≠正文 {body[k]}）'})
                return False
            # 内联没有 → 转引用子页：只在显式开启时抓
            children = re.findall(r'\{\{:([^|}\n]+)', raw_page)
            cands = [c.strip() for c in children if author in c or title in c or title.split(' ')[-1] in c]
            if cands and args.fetch_children:
                got = fetch_children(cands)
                for t, c in got.items():
                    if body in norm_page(c):
                        rec['ws'] = 'WS_RAW_EXACT'
                        rec['ws_page'] = t
                        return True
                rec.setdefault('ws_variants', []).append(
                    {'page': page_label, 'detail': '子页已查但未逐字命中: ' + '、'.join(sorted(got)[:3])})
                return False
            if cands:
                rec['transclude_children'] = len(cands)
            return False

        hit = False
        # 第一步：用本地映射的御定卷号（快，不联网；但御定卷号已证实不可靠，只当首选猜测）
        if vol:
            n = cn_volume_to_int(vol)
            snap = SNAP / f'vol{n:03d}.txt'
            if snap.exists():
                hit = judge(snap.read_text(encoding='utf-8'), f'全唐詩/卷{n:03d}')
            else:
                rec['local_snapshot'] = 'not_fetched'
        # 第二步：本地映射卷没命中或没有映射 → 按正文首句检索维基文库，找真正含这首诗的页面。
        # （御定 json 的 volume 字段实测有误：李白的《玉階怨》被记到根本不含它的卷二十。）
        if not hit and args.search:
            hits = ws_search(f'"{raw_body[:12]}"')
            rec['search_hits'] = hits[:5]
            time.sleep(SLEEP)
            for t in hits[:4]:
                c = fetch_single(t)
                if not c:
                    continue
                if judge(c, t):
                    hit = True
                    break
                time.sleep(SLEEP // 2)
        if not hit:
            if 'ws_variants' in rec:
                rec['ws'] = 'WS_VARIANT'
            elif vol and rec.get('local_snapshot') == 'not_fetched':
                rec['ws'] = 'NOT_FETCHED'
            elif 'transclude_children' in rec:
                rec['ws'] = 'TRANSCLUDE'
            else:
                rec['ws'] = 'WS_MISS'
        counts[rec['ws']] += 1
        out.append(rec)

    (HERE / 'tang300-wikisource-proof.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    md = ['# 三百首 × 维基文库《全唐詩》逐字复核', '',
          f'- 快照目录 {SNAP}；转引用子页' + ('已批量抓取' if args.fetch_children else '未抓取（加 --fetch-children 再跑）'), '',
          '| 档 | 数量 |', '|---|---|']
    for k, v in counts.most_common():
        md.append(f'| {k} | {v} |')
    md += ['',
           'WS_RAW_EXACT = 与维基文库正文码位逐字一致（独立转录，真·第二证过）；',
           'WS_FOLD_EXACT = 折叠异体字后一致（异体差异保留登记，入库正文以本页为准）；',
           'WS_VARIANT = 找到同一诗但真异文，逐条看；TRANSCLUDE = 卷页是转引用壳，还没抓子页；',
           'NOT_FETCHED = 映射卷的快照还没抓到；',
           'WS_MISS = 映射卷里没这首诗（含御定卷号错记、本地无卷号两类）——加 --search 按正文检索真页重判。']
    (HERE / 'tang300-wikisource-proof.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'wrote {HERE / "tang300-wikisource-proof.json"}')
    for k, v in counts.most_common():
        print(f'{k}: {v}')


if __name__ == '__main__':
    main()
