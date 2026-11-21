#!/usr/bin/env python3
"""阶段 C 旁证：维基文库《唐詩三百首》目录页 × 本地选本 366 首的交叉核对。

为什么值得做：这份目录是**独立于 chinese-poetry 仓库**的第三份书目证据
（维基文库自行编排的《唐詩三百首》索引）。它不含正文，但含两类可用的事实：
  1) 标题（选本与目录的题名可能不同——这类差异本身就是要记录的东西，
     例如选本作《琵琶引》而目录作《琵琶行並序》、选本作《在嶽詠蟬》而目录作《在獄詠蟬》）；
  2) 消歧括号——目录用「[[感遇 (孤鴻海上來)|感遇]]<sub>之一</sub>」这种形式区分同题诗，
     括号里的就是**该诗首句**。本地有正文，所以可以拿本地正文首句去对括号：
     对上了，就是内容级旁证（不靠标题、不靠正文全文，只靠「首句 = 括号」这一独立编排）。

快照：https://zh.wikisource.org/zh-hans/唐詩三百首 （存 /tmp/src-dl/tang300-ws-index.txt，
     解析结果 /tmp/src-dl/tang300-index-entries.json，由本目录的同名一次性解析步骤产出）。
本脚本不联网。

判定档位：
  T1_TITLE_ORDINAL —— 题名一致且组内序号一致（选本「感遇十二首 一」↔ 目录「感遇」<sub>之一</sub>）
  T1_TITLE         —— 题名一致
  T2_FIRSTLINE     —— 题名不同，但目录消歧括号与本地正文首句一致（内容级旁证）
  T3_AUTHOR_ONLY   —— 题名、首句都没对上，只有作者名下有未匹配条目（需人工看）
  WS_ONLY          —— 目录有、选本没有（选本未收，或题名差异过大）
  SEL_ONLY         —— 选本有、目录没有（目录未收，或题名差异过大）

诚实声明：目录条目数与选本条目数本就不同（维基文库这份是 320 条，选本 366 首），
所以「选本未被覆盖」不等于缺陷；本核对只找**能互相印证**的部分，并如实记录差异。
标题差异一律照录，不裁决哪个对。

用法: python3 -I tang300_ws_index_cross.py
输出: tang300-ws-index-cross.json / .md
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from tang300_dual_proof import fold, strip_punct  # noqa: E402  同一份折叠规则，不抄第二份

HERE = pathlib.Path(__file__).parent
SNAP = '/tmp/src-dl/tang300-index-entries.json'
SNAP_RAW = '/tmp/src-dl/tang300-ws-index.txt'
SRC_URL = 'https://zh.wikisource.org/zh-hans/唐詩三百首'

CN_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}

# 乐府类选本标题带曲辞前缀（「橫吹曲辭 出塞 一」「鼓吹曲辭 將進酒」），目录不带
QUCI = ('橫吹曲辭', '鼓吹曲辭', '樂府', '相和歌辭', '清商曲辭', '雜曲歌辭', '近代曲辭', '新樂府')
# 题名尾注：並序之类不算题名差异
TAIL_NOTE = re.compile(r'(並序|并序)$')
# 组诗计数与序号：选本作「遣悲懷三首 一」「感遇十二首 四」，
# 目录有两种写法：「感遇」<sub>之四</sub>，或直接把序号嵌进链接名「遣悲懷之一」「無題之一」。
# 归一时两类都要剥掉，序号单独提出来比对。
CN1 = '[一二三四五六七八九十]'
# 有意保守：只在「空格+序号」或「之+序号」时剥离。否则《雜詩 十三》的「十三」会被吃掉一半。
ORD_TAIL = re.compile(rf'(?:\s|之){CN1}$')
COUNTS = re.compile(rf'{CN1}+首$')                      # 剥掉后剩下的组数词（含「十二首」）


def tnorm(s):
    """题名归一：去标点、折叠异体、去曲辞前缀、去尾注、去序号与组数词、去空白。"""
    s = strip_punct(fold(s or ''))
    for q in QUCI:
        fq = strip_punct(fold(q))
        if s.startswith(fq):
            s = s[len(fq):]
    s = TAIL_NOTE.sub('', s)
    for _ in range(2):                                # 「…三首二」→ 去序号 → 去组数词
        s = ORD_TAIL.sub('', s)
        s = COUNTS.sub('', s)
    return s.strip()


def split_ordinal(title):
    """'感遇十二首 四' → ('感遇十二首', 4)；'遣悲懷之三' → ('遣悲懷', 3)；无序号则 (题名, None)。"""
    t = (title or '').strip()
    m = re.search(rf'(?:之|)({CN1})$', t)
    if m:
        return t[:m.start()].strip(), CN_NUM[m.group(1)]
    return t, None


def parse_ws_entry(e):
    """目录条目 → (作者, 显示题名, 链接目标, 消歧括号内容, 组内序号)。"""
    text = e['text']
    author = (e['plain'] or '').strip()
    sub = re.search(r'<sub>\s*之?([一二三四五六七八九十])\s*</sub>', text)
    ordinal = CN_NUM[sub.group(1)] if sub else None
    m = re.search(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', text)
    target = m.group(1).strip() if m else None
    display = (m.group(2).strip() if m and m.group(2) else target)
    disp = re.sub(r'<[^>]+>', '', display or '').strip()
    disp, o2 = split_ordinal(disp)
    ordinal = ordinal or o2
    disamb = None
    if target and target.endswith(')'):
        disamb = target[target.index('(') + 1: -1].strip()
        target = target[:target.index('(')].strip()
    return author, disp, target, disamb, ordinal


def first_line(paras):
    """本地正文首句（去标点折叠异体）。"""
    for p in (paras or []):
        s = fold(strip_punct(p)).strip()
        if s:
            return s
    return ''


def line_match(a, b):
    """括号内容与首句互为前缀且够长，判为同一句（括号常只取半句）。"""
    if not a or not b:
        return False
    n = min(len(a), len(b))
    if n < 4:
        return False
    return a[:n] == b[:n]


def main():
    entries = json.loads(pathlib.Path(SNAP).read_text(encoding='utf-8'))
    sel = json.loads(
        (pathlib.Path('/Users/gqli/work/xuexi/chinese-poetry/全唐诗/唐诗三百首.json')
         ).read_text(encoding='utf-8'))

    ws = []
    for i, e in enumerate(entries):
        author, disp, target, disamb, ordinal = parse_ws_entry(e)
        ws.append({'i': i, 'genre': e['genre'], 'author': author, 'title': disp,
                   'link': target, 'disamb': disamb, 'ordinal': ordinal,
                   'raw': e['text'], 'used_by': None})

    by_author = {}
    for w in ws:
        by_author.setdefault(fold(strip_punct(w['author'])), []).append(w)

    # 每首选本诗的候选目录条目（同作者、归一题名相同）预先算好，
    # 因为「同题多首」（李商隱《無題》六首、《隋宮》两首）必须整体看才能配对。
    poems = []
    for seq, p in enumerate(sel, 1):
        core, ordinal = split_ordinal(p['title'])
        fl = first_line(p.get('paragraphs'))
        want_t = tnorm(core)
        same_title = [w for w in by_author.get(fold(strip_punct(p['author'])), [])
                      if want_t and tnorm(w['title']) == want_t]
        # 该题名下的全部同作者条目（含选本只有一首而目录分序号的情形）
        poems.append({'seq': seq, 'author': p['author'], 'title': p['title'],
                      'want_t': want_t, 'ordinal': ordinal, 'first_line': fl,
                      'same_title': same_title})

    assigned = {}

    def take(w, seq, tier, **kw):
        w['used_by'] = seq
        assigned[seq] = {'tier': tier, 'ws': w, **kw}

    # 第一轮：内容级配对——目录消歧括号＝本地正文首句。
    # 这一轮不看序号，同题多首靠这个才不会配错首（《無題》六首就是这种）。
    for pm in poems:
        for w in pm['same_title']:
            if w['used_by'] is None and line_match(fold(strip_punct(w['disamb'] or '')), pm['first_line']):
                take(w, pm['seq'], 'T1_TITLE_FIRSTLINE')
                break
    # 第二轮：题名（+序号）配对。序号只是旁注，配到多个时才拿它定夺，并标明「序号推定」。
    for pm in poems:
        if pm['seq'] in assigned:
            continue
        free = [w for w in pm['same_title'] if w['used_by'] is None]
        if not free:
            continue
        if len(free) == 1:
            take(free[0], pm['seq'], 'T1_TITLE')
        else:
            byord = [w for w in free if w['ordinal'] is not None and w['ordinal'] == pm['ordinal']]
            if len(byord) == 1:
                take(byord[0], pm['seq'], 'T1_TITLE_ORDINAL')   # 同题多首，靠序号推定
            else:
                # 目录把同题分成几条（之/一二三）而选本只有一条，或两边序号都对不上：
                # 不做推定，留给首句之外的复核（正文逐字比对）处理。
                pass
    # 第三轮：题名不同，但目录消歧括号＝本地首句（内容级，不靠题名）。
    for pm in poems:
        if pm['seq'] in assigned:
            continue
        for w in by_author.get(fold(strip_punct(pm['author'])), []):
            if w['used_by'] is None and line_match(fold(strip_punct(w['disamb'] or '')), pm['first_line']):
                take(w, pm['seq'], 'T2_FIRSTLINE')
                break

    results = []
    for pm in poems:
        a = assigned.get(pm['seq'])
        if a:
            w = a['ws']
            results.append({'seq': pm['seq'], 'author': pm['author'], 'title': pm['title'],
                            'tier': a['tier'], 'ws_title': w['title'], 'ws_raw': w['raw'],
                            'ws_disamb': w['disamb'], 'ws_genre': w['genre'],
                            'title_diff': tnorm(w['title']) != pm['want_t'],
                            'first_line': pm['first_line'][:12]})
        else:
            # 同作者名下有没有「很像」的条目？只当线索列出，不算旁证。
            near = []
            for w in by_author.get(fold(strip_punct(pm['author'])), []):
                if w['used_by'] is not None or not pm['want_t']:
                    continue
                wt = tnorm(w['title'])
                if wt and (wt in pm['want_t'] or pm['want_t'] in wt
                           or len(_lcs(pm['want_t'], wt)) >= 5):
                    near.append(w['raw'])
            results.append({'seq': pm['seq'], 'author': pm['author'], 'title': pm['title'],
                            'tier': 'SEL_ONLY', 'first_line': pm['first_line'][:12],
                            'near_candidates': near[:3]})
    ws_only = [w for w in ws if w['used_by'] is None]

    import collections
    counts = collections.Counter(r['tier'] for r in results)
    out = {'source_url': SRC_URL, 'snapshot': SNAP_RAW,
           'ws_entries': len(ws), 'selection_poems': len(sel),
           'counts': dict(counts),
           'selection': results,
           'ws_only': [{'genre': w['genre'], 'author': w['author'], 'raw': w['raw']} for w in ws_only]}
    (HERE / 'tang300-ws-index-cross.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    md = ['# 三百首书目旁证：维基文库《唐詩三百首》目录 × 本地选本', '',
          f'- 目录快照：{SRC_URL}（{SNAP_RAW}）；条目 {len(ws)} 条。',
          f'- 本地选本 {len(sel)} 首（chinese-poetry 转录）。',
          '',
          '两边条目数本就不同（维基文库这份目录 320 条，选本 366 首）——'
          '「未被覆盖」不判为缺陷，只如实记录。',
          '',
          '配对次序也说明证据强弱：**先按内容**（目录消歧括号＝本地正文首句），'
          '再按题名，最后才用序号。李商隱《無題》六首、《隋宮》两首这类同题多首，'
          '只有靠首句才不会配错首，所以 T1_TITLE_FIRSTLINE 是最强档，'
          'T1_TITLE_ORDINAL 表示同题多首时靠序号推定（较弱，入库前需逐字复核）。',
          '',
          '| 档 | 含义 | 数量 |', '|---|---|---|']
    desc = {
        'T1_TITLE_FIRSTLINE': '题名一致，且目录消歧括号＝本地正文首句（内容级，最强）',
        'T1_TITLE': '题名一致（同作者同题名只此一条，无歧义）',
        'T1_TITLE_ORDINAL': '同题多首，按组内序号推定（弱旁证）',
        'T2_FIRSTLINE': '题名不同，仅目录消歧括号＝本地首句（内容级）',
        'SEL_ONLY': '选本有、目录未匹配（目录未收或题名差异过大）',
    }
    for k in ('T1_TITLE_FIRSTLINE', 'T1_TITLE', 'T1_TITLE_ORDINAL', 'T2_FIRSTLINE', 'SEL_ONLY'):
        md.append(f'| {k} | {desc[k]} | {counts.get(k, 0)} |')
    md.append(f'| WS_ONLY | 目录有、选本未匹配 | {len(ws_only)} |')

    diffs = [r for r in results if r['tier'] != 'SEL_ONLY' and r['title_diff']]
    md += ['',
           f'## 已匹配条目里的题名差异（{len(diffs)} 首，照录不裁决）', '',
           '> 这类差异是有用的事实：选本与维基文库编排的题名不同，'
           '入库时以复核过的正文为准，题名分歧登记备查。', '']
    for r in diffs:
        md.append(f"- {r['seq']} {r['author']}《{r['title']}》 ↔ 目录 {r['ws_raw'].replace('<sub>', '').replace('</sub>', '')}")
    weak = [r for r in results if r['tier'] == 'T1_TITLE_ORDINAL']
    md += ['', f'## 序号推定的条目（{len(weak)} 首，逐字复核前不采信）', '']
    for r in weak:
        md.append(f"- {r['seq']} {r['author']}《{r['title']}》 ↔ 目录 {r['ws_raw'].replace('<sub>', '').replace('</sub>', '')}")
    md += ['',
           f'## SEL_ONLY（{counts.get("SEL_ONLY", 0)} 首，目录未匹配）', '',
           'near= 同作者名下标题相近的目录条目，只当线索，不是旁证。', '']
    for r in results:
        if r['tier'] == 'SEL_ONLY':
            line = f"- {r['seq']} {r['author']}《{r['title']}》 首句：{r['first_line']}"
            if r.get('near_candidates'):
                line += '  near: ' + '；'.join(c.replace('<sub>', '').replace('</sub>', '')
                                               for c in r['near_candidates'])
            md.append(line)
    md += ['', f'## WS_ONLY（{len(ws_only)} 条，目录有、选本未匹配）', '']
    for w in ws_only:
        md.append(f"- {w['genre']}｜{w['author']} {w['raw']}")
    (HERE / 'tang300-ws-index-cross.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'wrote {HERE / "tang300-ws-index-cross.json"}')
    for k, v in counts.most_common():
        print(f'{k}: {v}')
    print(f'WS_ONLY: {len(ws_only)}')


def _lcs(a, b):
    """最长公共子串（只用于「相近标题」的线索展示，不参与判定）。"""
    best = ''
    for i in range(len(a)):
        for j in range(len(b)):
            k = 0
            while i + k < len(a) and j + k < len(b) and a[i + k] == b[j + k]:
                k += 1
            if k > len(best):
                best = a[i:i + k]
    return best


if __name__ == '__main__':
    main()
