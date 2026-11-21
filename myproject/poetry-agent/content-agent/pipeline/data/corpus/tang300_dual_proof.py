#!/usr/bin/env python3
"""阶段 C：唐诗三百首 366 首的原文与作者双证比对（只读语料，不写库、不写迁移）。

三份语料（都在本机 chinese-poetry/ 下，繁体原样，不做繁简转换）：
  A  chinese-poetry/全唐诗/唐诗三百首.json      —— 选本：366 首，带作者、分段、tag
  B  chinese-poetry/御定全唐詩/json/*.json       —— 御定全唐詩 900 卷转录（按卷）
  C  chinese-poetry/全唐诗/poet.tang.*.json     —— 四库全唐诗按人拆分（57,607 首）

匹配策略：正文为主，标题作者为旁证。
  三百首的乐府类标题带曲辞前缀（「橫吹曲辭 出塞 一」），与 B/C 的题名体系对不上，
  所以按「全诗去标点正文的前 10 字」建索引找候选，再用全诗正文判定。
  分段（一行一段 vs 四联一段）是各库的排版选择，不算异文；比对在去标点正文上进行。

判定档位（逐首 + 总体）：
  RAW_EXACT   —— 正文逐字一致（码位相同）
  FOLD_EXACT  —— 归一异体字后才一致（差异字符逐条列出，不裁决哪个对，只登记差异）
  VARIANT     —— 归一后仍有异文（真异文或字数不同，需版本判断）
  MISSING     —— 该语料里找不到

诚实声明：A 与 C 同出 chinese-poetry 仓库（转录来源可能同源），B 是同一仓库下的另一部转录。
  本脚本给出的是「仓库内多转录一致」；真正独立于该仓库的第二证，按《春望》的做法
  对维基文库《全唐詩》页面逐字复核，只对要入库的部分做，成本可控。

用法: python3 tang300_dual_proof.py [--corpus <chinese-poetry 根目录>]
输出: tang300-dual-proof.json（逐首结果）+ tang300-dual-proof.md（计数与未过清单）
退出码恒为 0：这是一份报告，不是门禁。
"""
import argparse
import collections
import json
import pathlib
import re

PUNCT = set('，。！？；：、（）「」『』《》“”‘’…—－· \n\r　[]【】()')

# 异体字折叠表——只收「同一字的不同写法」。有意排除的：
#   風/光、隔/來、是/似、倚/依：这些是真版本异文，折叠就会掩盖它，必须留在 VARIANT 里。
#   復/複、云/雲、里/裏、斗/鬥、沈/沉、採/采、遊/游、御/禦、薰/熏、乾/幹：
#   这类「后世繁简归并字」在唐诗里各有其字，合并会掩盖真实异文，宁可多报不误合。
# 第二批的取舍按同一标准，逐条有实测出处（见各条注释）；下面这几条实测出现过但**不收**：
#   飢/饑（《對酒》等）：飢=饿、饑=荒年，唐诗里是两个词，繁简才合并成「饥」——
#     收了就会把真异文抹掉，与上面 里/裏 同一类错误。
#   唯/惟：经籍里的通用字，不是同字异写（二字各有本义），异文照登。
#   衮/滚、砂/沙、綵/彩：三字对各自有别义（《出塞》「黃砂/黃沙」是历代注家争的异文），不折。
#   確/确：确另有用例，样本只有 1 处，不值得为它扩表——留在异文清单里由人过目。
VARIANT_FOLD = {
    '爲': '為', '荆': '荊', '疎': '疏', '衆': '眾', '臺': '台', '迴': '回',
    '羣': '群', '霑': '沾', '淩': '凌', '掛': '挂', '猨': '猿', '櫂': '棹',
    '汎': '泛', '絃': '弦', '遰': '遞', '谿': '溪', '閑': '閒', '鏁': '鎖',
    '倖': '幸', '鴈': '雁', '溼': '濕', '秪': '只', '竈': '灶',
    # 踪/蹤： simplify 只有一个对应字，不并入别的字（不同于 復/複），属同字异写。
    # 实测：选本《無題》「來是空言去絕踪」／维基文库目录「來是空言去絕蹤」。
    '踪': '蹤',
    # 第二批：三百首 × 维基文库诗页复核实测出的同字异写（实测次数取自上一轮
    # tang300-ws-poems-proof.json 的 detail 字段）。判据与上面各条相同：
    # 该字只有一个对应字、不并入别的字，所以不是「繁简归并字」那一类；
    # 不收的结果不是保住真异文，而是把真·第二证淹在异文清单里。
    # 却/卻 从原先的「不折叠」名单移出，理由同上條：卻 的后世对应字只有「却」，
    # 与 復/複（複另对应「复」）不同类。实测 4 处。
    '却': '卻',
    '桮': '杯',      # 4 处
    '牀': '床',      # 3 处
    '荅': '答',      # 3 处
    '劒': '劍',      # 3 处
    '裏': '裡',      # 2 处。与上面有意不折的 里/裏 严格区分：裏/裡 同字异写，
                     # 而「闾里」之「里」与「裏外」之「裏」在唐诗里各有其字，仍不并。
    '遶': '繞',      # 2 处
    '逕': '徑',      # 2 处
    '樽': '尊',      # 2 处；樽 只有「酒器＝尊」一个义，不并入别的字
    '栖': '棲',      # 2 处（《異體字整理表》以 棲 为正、栖 为异）
    '隣': '鄰',      # 1 处（反向 鄰/隣 另 1 处）
    '壻': '婿',      # 1 处
    '翫': '玩',      # 1 处
    '廻': '回',      # 迴→回 已在表内，廻 是同一字的另一写法
    '蓑': '簑',      # 1 处（《江雪》「孤舟蓑笠翁」）
    '鵶': '鴉',      # 1 处（《長信怨》「玉顏不及寒鵶色」）
    '燄': '焰',      # 1 处（《贈內人》「斜拔玉釵燈影涼」下句）
    # 鄕/鄉：《異體字整理表》以 鄉 为正、鄕 为异——同字异写，只有一个对应字，
    # 不是繁简归并字那一类。实测：卷页快照 4 个文件共 15 次（vol225×7、vol224×4、
    # vol227×3、vol218×1）；《月夜憶舍弟》卷225 命中只差这一对字
    # （折叠后自 4741 字起全串逐字命中；未折叠时「月是故鄉明」处分叉）。
    '鄕': '鄉',
    # 有意不收：裴/徘、回/徊。《長信怨》「裴回」／页面「徘徊」是**联绵词**的整体异写，
    # 二字各有本义，按单字折叠等于把 裴→徘 当成同字异写，那是错的；整词异写属异文，照登。
}

KEY_LEN = 10


def strip_punct(s):
    return ''.join(ch for ch in s if ch not in PUNCT)


def fold(s):
    return ''.join(VARIANT_FOLD.get(ch, ch) for ch in s)


def norm(paras):
    return fold(strip_punct(''.join(paras or [])))


def raw(paras):
    return strip_punct(''.join(paras or []))


def load_corpus(poems):
    """按「全诗归一正文的前 KEY_LEN 字」建索引；撞键的（同首句组诗、拟作）全保留。"""
    idx = collections.defaultdict(list)
    for p in poems:
        k = norm(p.get('paragraphs'))[:KEY_LEN]
        if len(k) == KEY_LEN:
            idx[k].append(p)
    return idx


def lookup(a, idx):
    k = norm(a.get('paragraphs'))[:KEY_LEN]
    return idx.get(k, [])


def char_diff(ca, cb):
    """两条归一正文的差异：等长逐字列出，否则报长度差与首异位置。"""
    if len(ca) == len(cb):
        out = []
        for i, (x, y) in enumerate(zip(ca, cb)):
            if x != y:
                out.append(f'第{i + 1}字 {x}≠{y}')
                if len(out) >= 8:
                    out.append('…')
                    break
        return '；'.join(out) if out else None
    j = 0
    while j < min(len(ca), len(cb)) and ca[j] == cb[j]:
        j += 1
    return f'长度 {len(ca)}≠{len(cb)}，首异在第 {j + 1} 字（{ca[j:j + 4]}… / {cb[j:j + 4]}…）'


def raw_variant_chars(ca, cb):
    """归一后相等、逐字不等时，列出被折叠掉的字符对（供人工过目）。"""
    out = []
    for x, y in zip(ca, cb):
        if x != y:
            out.append(f'{x}/{y}')
    return '、'.join(dict.fromkeys(out))


def compare_poem(a, cand):
    """返回 (verdict, detail)。verdict: RAW_EXACT / FOLD_EXACT / VARIANT。"""
    ra, rb = raw(a['paragraphs']), raw(cand.get('paragraphs'))
    if ra == rb:
        return 'RAW_EXACT', None if a['paragraphs'] == cand['paragraphs'] else '分段不同（正文逐字一致）'
    na, nb = fold(ra), fold(rb)
    if na == nb:
        return 'FOLD_EXACT', '异体字：' + raw_variant_chars(ra, rb)
    return 'VARIANT', char_diff(na, nb)


def best_match(a, idx):
    """在同键候选里找最接近的一首；RAW_EXACT 优先，其次 FOLD_EXACT，其次差异行数最少。
    返回 (verdict, detail, matched)——matched 是选中的那条语料记录（可能题名与选本不同，
    比如选本作「橫吹曲辭 出塞 一」而语料题作「出塞」；它的 volume 字段就是复核要抓的卷）。"""
    cands = lookup(a, idx)
    if not cands:
        return None, None, None
    scored = []
    for c in cands:
        verdict, detail = compare_poem(a, c)
        n = {'RAW_EXACT': 0, 'FOLD_EXACT': 1, 'VARIANT': 2}[verdict]
        scored.append((n, verdict, detail, c))
    scored.sort(key=lambda t: t[0])
    _, verdict, detail, c = scored[0]
    return verdict, detail, c


def classify(a, idx_b, idx_c):
    vb, db, mb = best_match(a, idx_b)
    vc, dc, mc = best_match(a, idx_c)
    cands = lookup(a, idx_b) + lookup(a, idx_c)
    auth_b = sorted({c['author'] for c in lookup(a, idx_b)})
    auth_c = sorted({c['author'] for c in lookup(a, idx_c)})
    author_ok = bool(cands) and all(a['author'] in x for x in (auth_b, auth_c) if x)
    hit = lambda v: v in ('RAW_EXACT', 'FOLD_EXACT')
    both_raw = vb == 'RAW_EXACT' and vc == 'RAW_EXACT'
    both_hit = hit(vb) and hit(vc)
    if both_raw and author_ok:
        overall = 'DUAL_RAW'
    elif both_hit and author_ok:
        overall = 'DUAL_FOLDED'
    elif both_hit:
        overall = 'TEXT_OK_AUTHOR_SPLIT'
    elif hit(vb) or hit(vc):
        overall = 'SINGLE'
    elif vb == 'VARIANT' or vc == 'VARIANT':
        overall = 'VARIANT_ONLY'
    else:
        overall = 'MISSING'
    return {
        'title': a['title'], 'author': a['author'],
        'verdict_yuding': vb, 'detail_yuding': db,
        'verdict_poettang': vc, 'detail_poettang': dc,
        'author_yuding': auth_b, 'author_poettang': auth_c,
        'author_ok': author_ok, 'overall': overall,
        'matched_yuding_title': mb['title'] if mb else None,
        'quantangshi_volume': mb.get('volume') if mb else None,
    }


def yuding_volume_map(kd):
    """(作者, 标题) → 御定卷号。御定 json 自带 volume 字段，用它给每首定位《全唐詩》卷次，
    下一步据此去维基文库抓对应卷做独立复核（御定本与维基文库录入本是同一部书的不同转录）。"""
    m = {}
    for po in kd:
        v = po.get('volume')
        if v:
            m.setdefault((po['author'], po['title']), v)
    return m


def truncation_count(results):
    """御定 json 的已知缺陷：部分长诗被截断（正文比四库本短 15% 以上）。
    这类不是版本异文，是这份转录不完整——所以御定不能当第二证，只能当旁证。"""
    n = 0
    for e in results:
        m = re.match(r'长度 (\d+)≠(\d+)', e['detail_yuding'] or '')
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b and (a - b) / a > 0.15:
                n += 1
    return n


def cn_volume_to_int(s):
    """'卷二百二十五' → 225。只处理 1–999 的卷号。"""
    digits = {'〇': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
              '六': 6, '七': 7, '八': 8, '九': 9}
    units = {'十': 10, '百': 100}
    s = s.replace('卷', '').strip()
    total = num = 0
    for ch in s:
        if ch in digits:
            num = digits[ch]
        elif ch in units:
            total += (num or 1) * units[ch]
            num = 0
    return total + num


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', default='/Users/gqli/work/xuexi/chinese-poetry')
    args = ap.parse_args()
    root = pathlib.Path(args.corpus)
    here = pathlib.Path(__file__).parent

    sel = json.loads((root / '全唐诗/唐诗三百首.json').read_text(encoding='utf-8'))
    kd = []
    for f in sorted((root / '御定全唐詩/json').glob('*.json')):
        kd.extend(json.loads(f.read_text(encoding='utf-8')))
    pt = []
    for f in sorted((root / '全唐诗').glob('poet.tang.*.json')):
        pt.extend(json.loads(f.read_text(encoding='utf-8')))
    idx_b, idx_c = load_corpus(kd), load_corpus(pt)

    results, counts = [], collections.Counter()
    for i, a in enumerate(sel):
        r = classify(a, idx_b, idx_c)
        r['seq'] = i + 1
        counts[r['overall']] += 1
        results.append(r)

    # 《全唐詩》卷次：classify 已从按正文匹配到的御定记录取 volume（题名不同也没关系），
    # 据此定位维基文库页面（下一步独立复核要抓的卷）
    truncated = truncation_count(results)
    vol_nums = sorted({cn_volume_to_int(v) for r in results if (v := r['quantangshi_volume'])})
    vols_needed = [f'{n:03d}' for n in vol_nums]

    out_json = here / 'tang300-dual-proof.json'
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (here / 'tang300-volumes.txt').write_text('\n'.join(vols_needed) + '\n', encoding='utf-8')

    order = ['DUAL_RAW', 'DUAL_FOLDED', 'TEXT_OK_AUTHOR_SPLIT', 'SINGLE', 'VARIANT_ONLY', 'MISSING']
    desc = {
        'DUAL_RAW': '两路正文逐字一致 + 作者一致（入库候选；仍需维基文库独立复核）',
        'DUAL_FOLDED': '两路都命中，但有一路需归一异体字（差异字符已逐条登记）',
        'TEXT_OK_AUTHOR_SPLIT': '正文两路一致，但某一路署了别的作者（作者双证未过）',
        'SINGLE': '只有一路命中（另一路异文或未收录）',
        'VARIANT_ONLY': '两路都是真异文（需版本判断，不入库）',
        'MISSING': '两路都找不到（选本独采或正文差异过大）',
    }
    md = ['# 唐诗三百首双证报告（阶段 C）', '',
          f'- 三百首 {len(sel)} 首；御定全唐詩 {len(kd)} 首；poet.tang {len(pt)} 首。',
          '- 比对在去标点正文上进行；分段差异不算异文；异体字折叠表见脚本注释（只折叠同字异写，繁简归并字不折叠）。',
          '',
          '| 档 | 含义 | 数量 |', '|---|---|---|']
    for k in order:
        md.append(f'| {k} | {desc[k]} | {counts.get(k, 0)} |')
    md.append('')
    md.append(f'**够格进入下一步（维基文库独立复核）的：{counts.get("DUAL_RAW", 0) + counts.get("DUAL_FOLDED", 0)} 首**'
              f'（其中 {counts.get("DUAL_FOLDED", 0)} 首需先人工看过异体字差异）。')
    md += ['', '## 未过清单', '']
    for k in order[2:]:
        rows = [r for r in results if r['overall'] == k]
        md += [f'### {k}（{len(rows)}）', '']
        for r in rows:
            md.append(
                f"- {r['seq']} {r['author']}《{r['title']}》 御定={r['verdict_yuding'] or '未收'}"
                f"／poet.tang={r['verdict_poettang'] or '未收'}"
            )
            for tag in ('detail_yuding', 'detail_poettang'):
                if r[tag]:
                    md.append(f'    - {r[tag][:160]}')
            if not r['author_ok']:
                md.append(f"    - 作者: 选本={r['author']} 御定={r['author_yuding']} poet.tang={r['author_poettang']}")
        md.append('')
    folded = [r for r in results if r['overall'] == 'DUAL_FOLDED']
    md += [f'## DUAL_FOLDED 的异体字差异（{len(folded)} 首，供人工过目）', '']
    for r in folded:
        ds = [d for d in (r['detail_yuding'], r['detail_poettang']) if d and d.startswith('异体字')]
        md.append(f"- {r['seq']} {r['author']}《{r['title']}》 " + '；'.join(ds))
    md += [
        '', '## 关键发现：本地三份 JSON 不构成独立双证',
        '',
        f'- 御定 json 有已知缺陷：{truncated} 首正文比四库本短 15% 以上（长诗被截断，如《錦瑟》只存首尾联）。',
        '  这不是版本异文，是转录不完整——所以御定 json 只能当旁证，不能当第二证。',
        '- A（选本）与 C（poet.tang）同出 chinese-poetry 仓库，且抽查显示同源痕迹明显；',
        '  B 虽标「御定」，其 json 同样出自该仓库的转录。三份都在同一棵树上。',
        f'- 真正的第二证 = 维基文库《全唐詩》录入本（V011 核《春望》用的就是它，卷号体系一致）。',
        f'  经御定 volume 字段映射，366 首要复核的卷共 {len(vols_needed)} 卷，清单在 tang300-volumes.txt。',
        '',
        '## 已知局限',
        '',
        '- 本报告是「仓库内多转录一致」；够格的档位在维基文库逐字复核之前不算完成双证。',
        '- 三百首含 4 个同题同作者条目（李商隐《隋宮》等），按选本原样逐条计。',
        '- 撞键候选取最接近的一首；同首句的组诗/拟作可能取错首，逐条看清单即可发现。',
        '- DUAL_FOLDED 的异体字只登记差异、不裁决；入库时正文以维基文库复核结果为准，异体照原样保留。',
    ]
    out_md = here / 'tang300-dual-proof.md'
    out_md.write_text('\n'.join(md) + '\n', encoding='utf-8')
    print(f'wrote {out_json}')
    print(f'wrote {out_md}')
    for k in order:
        print(f'{k}: {counts.get(k, 0)}')


if __name__ == '__main__':
    main()
