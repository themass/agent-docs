#!/usr/bin/env python3
"""阶段 C 第三条证据：用维基文库《唐詩三百首》诗页复核选本正文，并**按页面自述底本分档**。

为什么必须分档（这是本脚本的全部意义）：
逐字一致 ≠ 双证成立。这些页面不是同一种东西，每页 header 自己写明它从哪抄来——
  from = 唐詩三百首        → 自称抄自《唐詩三百首》。我们的选本就是《三百首》，
                            拿选本正文去对一本自称抄自《三百首》的页面是**循环论证**：
                            即使逐字一致也证明不了正文对。→ WP_CIRCULAR，不算第二证。
  from = 全唐詩/卷NNN      → 与选本同书异转录，逐字一致算第二证（WP_RAW_EXACT/FOLD_EXACT）。
  from = 文苑英華/唐音/文集 → **异源他书**（《春曉 (孟浩然)》就是文苑英華）。也是第二证，
                            但它是跨书比对，差异属跨书异文，不能和同书异读混作一类
                            → WP_XBOOK_RAW_EXACT / WP_XBOOK_FOLD_EXACT。
  只在 notes 里「又見 [[全唐詩/卷160]]」 → 只是**提及**，不是底本声明。
                            这一条是踩过坑后补的：把「又見」读成「转录自」会把
                            来源说错（实测《春曉 (孟浩然)》from=文苑英華、notes 又見全唐詩卷160）。
  两种声明都没有            → WP_UNSOURCED_EXACT：文本相同但谁抄谁不明，不算第二证。

配对不靠本脚本重新猜标题：用 tang300_ws_index_cross.py 的结果（已按「目录消歧括号＝本地正文首句」
定过归属），拿它给出的页面链接去取快照——归属证据与正文证据互相独立。

正文抽取：先抽**诗体区块**（`<poem>…</poem>` 或 `{{VtextStart}}…{{VtextEnd}}`）再清洗。
必须先抽区块：`{{center block| <poem>…</poem> }}` 这类壳，整块删模板的规则会连正文一起吃掉
（实测《春曉 (孟浩然)》正文被吃成空串，误判「找不到这首诗」）。区块内再：
`{{另|A|B}}` 按两种读法分别试；`<ref>…</ref>` 连注文内容删（校勘注插在正文中间，
实测韩愈《八月十五夜贈張功曹》注文拼进正文后窗口对齐整体滑走，报出「选本=蛟 页面=洞」的假异文）；
其余 `{{…}}`、`[[…]]`、`-{…}-`、HTML 标签删。

判定用「选本每一段都能在页面正文里逐字找到」，不是整页相等：页面常带着序、其二、注记，
整页相等会把它们全判成异文（第一版就是这么错的，《韓碑》366≠499 全是注记撑的）。

异文定位：某段找不到时用滑动窗口找最像的对齐位置，逐字报分歧字符对。
不能拿该段起句当锚点——起句自己就可能含异文（《出塞》选本「黃砂」／页面「黃沙」、
《隋宮》选本「于今」／页面「於今」），起句逐字找会把真异文误报成「页面上没有这段」。
一段都对不上但能对齐的仍是异文，不是「找不到」：《江雪》只差 逕/徑、《長信怨》只差 裴回/徘徊，
先前都被误判成 WP_MISS。**异文只登记，不裁决**——裁决要版本依据，我们没有。

用法: python3 -I tang300_ws_poems.py
输入: /tmp/src-dl/ws-poems/*.txt（fetch_ws_poems.py 抓的）、tang300-ws-index-cross.json、选本
输出: tang300-ws-poems-proof.json / .md
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from tang300_dual_proof import fold, strip_punct  # noqa: E402  同一份规则，不抄第二份

HERE = pathlib.Path(__file__).parent
PAGES = pathlib.Path('/tmp/src-dl/ws-poems')
SEL_PATH = pathlib.Path('/Users/gqli/work/xuexi/chinese-poetry/全唐诗/唐诗三百首.json')

LING = re.compile(r'\{\{(?:另|别|別|异|異)\|([^|}]+)\|([^}]+)\}\}')
CONV = re.compile(r'-\{[^}]*\}-')
HEADER = re.compile(r'\{\{[Hh]eader(.*?)\n\}\}', re.S)
POEM_BLOCK = re.compile(r'<poem>(.*?)</poem>', re.S)
VTEXT_BLOCK = re.compile(r'\{\{VtextStart\}\}(.*?)\{\{VtextEnd\}\}', re.S)
# 底本名判定不能要求「/卷NNN」：实测 from 有 `全唐诗`、`全唐詩`（无卷号）、
# `御定全唐詩 (四庫全書本)/卷177`（书名与卷号之间隔着版本注）等写法。
# 御定全唐詩就是《全唐詩》的御定本，与本地御定 json 同书异转录，归 QTS。
# 注意别误伤《全唐文》：只认 詩/诗 字形。三百首要先判（唐詩三百首 也含「唐詩」二字）。
QTS_LINK = re.compile(r'全唐[詩诗]')
T300_RE = re.compile(r'唐[诗詩]三百首')
# 正文里的 [[目标|显示]] 必须换成**显示文字**，不能整块删：
# 实测《聞官軍收河南河北》写的是「[[w:河南道|河南]][[w:河北道|河北]]」、「[[w:劍門關|劍]]」，
# 整块删会把诗本身删掉 10 个字（46≠56），把有底本声明的诗误判成 WP_MISS。
WIKILINK_LABELED = re.compile(r'\[\[[^\]|]*\|([^\]]+)\]\]')
# 页面正文/注里声明另据它本（不是「一作…」式的同书异读，而是整篇或大段来自另一部书）
OTHER_BASE = re.compile(r'(從敦煌[^\n<]{0,18}|敦煌[^\n<]{0,4}殘卷[^\n<]{0,12}|殘卷無[^\n<]{0,12}'
                        r'|鸣沙[^\n<]{0,14}|此句作[^\n<]{0,12}|別本[^\n<]{0,10})')


def header_field(body, key):
    m = HEADER.search(body)
    if not m:
        return None
    mm = re.search(rf'\|\s*{key}\s*=\s*(.*?)(?=\n\||\Z)', m.group(1), re.S | re.I)
    return mm.group(1).strip() if mm else None


def header_blob(text):
    m = HEADER.search(text)
    return m.group(1) if m else ''


def from_fields(text):
    """header 的 from / from2 / from3 —— 页面自述的底本。这是最硬的来源证据。"""
    hb = header_blob(text)
    out = []
    for m in re.finditer(r'\|\s*from\d?\s*=\s*(.*?)(?=\n\||\Z)', hb, re.S | re.I):
        v = re.sub(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', r'\1', m.group(1)).strip()
        if v:
            out.append(v)
    return out


def provenance(text):
    """(档位, 依据说明)。档位: T300 / QTS / OTHER / NONE。

    区分「底本声明」与「 merely 提及」：from* 字段是底本；notes 里「又見 [[全唐詩/…]]」只是提及。
    把「又見」当底本会把来源说错——实测《春曉 (孟浩然)》from=文苑英華(四庫全書本)/卷0157，
    notes 只是「又見[[全唐詩/卷160]]」，它不是《全唐詩》的转录。"""
    fr = from_fields(text)
    blob = ' '.join(fr)
    if T300_RE.search(blob):
        return 'T300', fr[0]
    m = QTS_LINK.search(blob)
    if m:
        return 'QTS', blob[max(0, m.start()):m.end() + 12].strip()
    if fr:
        return 'OTHER', fr[0]
    notes = (header_field(text, 'notes') or '')
    for mm in QTS_LINK.finditer(notes):
        pre = notes[max(0, mm.start() - 8):mm.start()]
        if re.search(r'(又見|另見|另见|参见)\s*$', pre):
            continue                        # 只是提及，不是底本
        return 'QTS', mm.group(0)
    return 'NONE', None


def poem_regions(text):
    """先抽诗体区块。返回 (区块列表, 是否退回整页)。"""
    regs = POEM_BLOCK.findall(text) + VTEXT_BLOCK.findall(text)
    return (regs, False) if regs else ([text], True)


def clean_region(t, reading):
    for _ in range(4):                      # {{另|A|B}} 之类可能嵌套，迭代到不动点
        new = LING.sub(lambda m: m.group(1) if reading == '甲' else m.group(2), t)
        if new == t:
            break
        t = new
    t = re.sub(r'<ref[^>]*/>', '', t)                 # 校勘注连注文一起删
    t = re.sub(r'<ref[^>]*>.*?</ref>', '', t, flags=re.S)
    t = re.sub(r'<references[^>]*/>', '', t)
    for _ in range(4):                      # 其余模板整块删
        new = re.sub(r'\{\{[^{}]*\}\}', '', t)
        if new == t:
            break
        t = new
    t = CONV.sub('', t)
    t = WIKILINK_LABELED.sub(r'\1', t)      # 先保留显示文字
    t = re.sub(r'\[\[[^\]]*\]\]', '', t)    # 没有显示文字的（纯链接）才整块删
    t = re.sub(r'<[^>]+>', '', t)
    return strip_punct(t)


def page_body(text, reading):
    """整页 → 正文（区块拼接）。reading: '甲'={{另|A|B}} 取 A，'乙' 取 B。"""
    regs, _ = poem_regions(text)
    return ''.join(clean_region(r, reading) for r in regs)


def para_diffs(want, page):
    """某段在页面里找不到时，用滑动窗口找「最像」的对齐位置，逐字报分歧。
    不能拿这段的起句当锚点：起句自己就可能含异文（《出塞》选本作「黃砂」、页面作「黃沙」；
    《隋宮》选本「于今」、页面「於今」——于/於 属有意不折叠的繁简归并字），
    起句逐字找就会把真异文误报成「页面上找不到这段」。"""
    if not want or len(page) < len(want):
        return None
    best = None
    for pos in range(len(page) - len(want) + 1):
        mism = 0
        for k in range(len(want)):
            if want[k] != page[pos + k]:
                mism += 1
                if best is not None and mism >= best[0]:
                    break
        if best is None or mism < best[0]:
            best = (mism, pos)
            if mism == 0:
                break
    mism, pos = best
    if mism > len(want) * 0.5:
        return None                          # 半数以上不同：多半不是同一段
    out = [f'第{k + 1}字 选本={want[k]} 页面={page[pos + k]}'
           for k in range(len(want)) if want[k] != page[pos + k]]
    return (f'对齐页面第{pos + 1}字，{len(want)} 字中 {mism} 字不同：'
            + '；'.join(out[:8]) + ('…' if len(out) > 8 else ''))


def compare(want_paras, page_raw, page_fold):
    """按段 containment：选本每一段都能在页面正文里逐字找到 → 正文成立。
    页面多出的（序、其二、赏析、重复排印）不影响判定；这是《春望》那一轮的办法。

    一段都没逐字命中 ≠「不是这首诗」。《江雪》只差 逕/徑、《長信怨》只差 裴回/徘徊，
    先前都因「零段命中」被判 WP_MISS，那是误判。只有对齐也失败（公共重合不足一半）才算 MISS。
    返回 (档位, 详情)。档位 EXACT / FOLD / VARIANT / MISS。"""
    n_raw = n_fold = 0
    bad = []
    for para in want_paras:
        w_raw = strip_punct(para)
        if not w_raw:
            continue
        if w_raw in page_raw:
            n_raw += 1
            continue
        w_fold = fold(w_raw)
        if w_fold in page_fold:
            n_fold += 1
            continue
        bad.append((w_raw[:6], para_diffs(w_fold, page_fold)))
    if not bad:
        return ('EXACT', None) if n_fold == 0 else ('FOLD', f'{n_fold} 段需折叠异体字')
    aligned = [(h, d) for h, d in bad if d]
    if not aligned:
        return ('MISS', None)
    total = n_raw + n_fold + len(bad)
    matched = n_raw + n_fold
    lead = f'{matched}/{total} 段逐字命中' + ('（无一整段命中，但可对齐）' if matched == 0 else '')
    detail = lead + '；未命中 ' + ' ／ '.join(
        f'《{h}…》：{d}' for h, d in aligned[:2])
    if len(aligned) < len(bad):
        detail += f'；另有 {len(bad) - len(aligned)} 段在页面上对不上'
    return ('VARIANT', detail)


def other_base_note(text):
    """页面声明的底本不是《全唐詩》时的依据文本：from* 字段 + 正文里的另据它本声明。
    注意「一作…」是同书异读（校勘记），**不算**底本不同——先前把两者混为一类，
    导致 21 首标成「底本不同系统」，其中 19 首只是附了校勘记。"""
    prov, why = provenance(text)
    bits = []
    if prov == 'OTHER':
        bits.append(f'from={why}')
    hits = [h for h in OTHER_BASE.findall(text) if '一作' not in h]
    bits += list(dict.fromkeys(h.strip() for h in hits))
    return '；'.join(bits)[:160] or None


def main():
    sel = json.loads(SEL_PATH.read_text(encoding='utf-8'))
    cross = json.loads((HERE / 'tang300-ws-index-cross.json').read_text(encoding='utf-8'))
    # 目录核对给出的 seq → 页面标题（归属由「消歧括号＝首句」等内容级证据定，不靠本脚本猜）
    page_of = {}
    for r in cross['selection']:
        if r['tier'] == 'SEL_ONLY':
            continue
        m = re.search(r'\[\[([^\]|]+)', r['ws_raw'])
        if m:
            page_of[r['seq']] = {'title': m.group(1).strip(), 'tier': r['tier']}

    out = []
    counts = __import__('collections').Counter()
    for i, p in enumerate(sel, 1):
        rec = {'seq': i, 'author': p['author'], 'title': p['title']}
        pg = page_of.get(i)
        if not pg:
            rec['verdict'] = 'NO_WS_PAGE'
            counts[rec['verdict']] += 1
            out.append(rec)
            continue
        rec['ws_page'] = pg['title']
        rec['attribution'] = pg['tier']
        f = PAGES / (re.sub(r'[^0-9A-Za-z一-鿿]', '_', pg['title']) + '.txt')
        if not f.exists():
            rec['verdict'] = 'PAGE_NOT_FETCHED'
            counts[rec['verdict']] += 1
            out.append(rec)
            continue
        text = f.read_text(encoding='utf-8')
        prov, why = provenance(text)
        _, fell_back = poem_regions(text)
        rec.update(prov=prov, prov_ref=why, body_fallback=fell_back,
                   page_author=header_field(text, 'author'),
                   page_title=header_field(text, 'title'),
                   page_section=header_field(text, 'section'),
                   other_base=other_base_note(text))

        paras = [strip_punct(x) for x in (p.get('paragraphs') or []) if strip_punct(x)]
        want_raw = ''.join(paras)
        # 两种读法都试（{{另|A|B}} 取前项／后项）；命中优先，否则取命中段数最多的一种
        best = None
        for tag in ('甲', '乙'):
            body = page_body(text, tag)
            v, d = compare(paras, body, fold(body))
            score = {'EXACT': 0, 'FOLD': 1, 'VARIANT': 2, 'MISS': 3}[v]
            cand = (score, tag, v, d, len(body))
            if best is None or cand[0] < best[0]:
                best = cand
            if score == 0:
                break
        _, tag, v, d, page_len = best
        rec['reading'] = tag
        rec['want_len'] = len(want_raw)
        rec['page_len'] = page_len
        rec['len_diff'] = page_len - len(want_raw)   # 页面多出的通常是序/其二/注记
        # 底本决定这条一致算不算第二证、以及它是什么性质的比对——这是本脚本存在的原因
        if v in ('EXACT', 'FOLD'):
            same = v == 'EXACT'
            base = f'读法{tag}' + ('逐字一致' if same else '折叠异体字后一致')
            if prov == 'T300':
                rec['verdict'] = 'WP_CIRCULAR'
                rec['detail'] = base + f'；但页面自述底本是 {why}——与选本同源，**不算第二证**'
            elif prov == 'QTS':
                rec['verdict'] = 'WP_RAW_EXACT' if same else 'WP_FOLD_EXACT'
                rec['detail'] = base + f'；页面自述底本 {why}（同书异转录，第二证成立）'
            elif prov == 'OTHER':
                rec['verdict'] = 'WP_XBOOK_RAW_EXACT' if same else 'WP_XBOOK_FOLD_EXACT'
                rec['detail'] = base + f'；页面自述底本 {why}（异源他书，第二证成立；其差异属跨书异文）'
            else:
                rec['verdict'] = 'WP_UNSOURCED_EXACT'
                rec['detail'] = base + '；页面未声明底本，谁抄谁不明——不算第二证'
        else:
            rec['verdict'] = 'WP_VARIANT' if v == 'VARIANT' else 'WP_MISS'
            rec['detail'] = f'读法{tag}：' + (d or '')
        counts[rec['verdict']] += 1
        out.append(rec)

    (HERE / 'tang300-ws-poems-proof.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    _report(out, counts)
    print(f'wrote {HERE / "tang300-ws-poems-proof.json"} / .md')
    for k, v in counts.most_common():
        print(f'{k}: {v}')


def _report(out, counts):
    order = ['WP_RAW_EXACT', 'WP_FOLD_EXACT', 'WP_XBOOK_RAW_EXACT', 'WP_XBOOK_FOLD_EXACT',
             'WP_UNSOURCED_EXACT', 'WP_CIRCULAR', 'WP_VARIANT', 'WP_MISS',
             'PAGE_NOT_FETCHED', 'NO_WS_PAGE']
    desc = {
        'WP_RAW_EXACT': '逐字一致，页面自述底本是《全唐詩》——同书异转录，**第二证成立**',
        'WP_FOLD_EXACT': '折叠异体字后一致，底本《全唐詩》——第二证成立，异体已登记',
        'WP_XBOOK_RAW_EXACT': '逐字一致，页面自述底本是**他书**（文苑英華等）——异源第二证成立，但属跨书比对',
        'WP_XBOOK_FOLD_EXACT': '折叠异体字后一致，底本他书——异源第二证成立',
        'WP_UNSOURCED_EXACT': '逐字一致但页面未声明底本，谁抄谁不明——不算第二证',
        'WP_CIRCULAR': '逐字一致但页面自述抄自《唐詩三百首》——循环论证，不算第二证',
        'WP_VARIANT': '同一首诗但正文有出入；只登记不裁决',
        'WP_MISS': '页面对不上这首诗（对齐也失败，多半不是同一首或页面残缺）',
        'PAGE_NOT_FETCHED': '对应页面在维基文库缺失或还没抓到',
        'NO_WS_PAGE': '书目核对没给出对应页面',
    }
    md = ['# 三百首 × 维基文库《唐詩三百首》诗页复核（按页面自述底本分档）', '',
          f'- 快照 {PAGES}；配对取自 tang300-ws-index-cross.json（归属由内容级证据定）。',
          '- 正文：先抽 `<poem>`/`{{VtextStart}}` 区块再去 markup；判定是「选本每一段都能在页面正文里逐字找到」。',
          '',
          '**读法**：逐字一致 ≠ 双证成立。页面自述底本决定这条一致算不算数、以及是什么性质的比对——',
          '自称抄自《唐詩三百首》的页面与我们的选本同源，对它比对是循环论证；'
          '只在注里「又見全唐詩」的页面不是《全唐詩》转录（实测《春曉 (孟浩然)》底本实为文苑英華）。',
          '',
          '| 档 | 含义 | 数量 |', '|---|---|---|']
    for k in order:
        if counts.get(k):
            md.append(f'| {k} | {desc[k]} | {counts[k]} |')
    n_same = counts.get('WP_RAW_EXACT', 0) + counts.get('WP_FOLD_EXACT', 0)
    n_book = counts.get('WP_XBOOK_RAW_EXACT', 0) + counts.get('WP_XBOOK_FOLD_EXACT', 0)
    md += ['',
           f'**第二证成立 {n_same + n_book} 首**：同书异转录 {n_same} 首 + 异源他书 {n_book} 首。',
           f'另有 {counts.get("WP_UNSOURCED_EXACT", 0)} 首一致但未声明底本、'
           f'{counts.get("WP_CIRCULAR", 0)} 首属循环论证——两类**不计入双证**。',
           '',
           f'## 异文（{counts.get("WP_VARIANT", 0)} 首）——按底本分两类，不能混着过目', '',
           '### 甲类：页面底本不是《全唐詩》（跨书差异，不属同书异文）', '']
    base = [r for r in out if r['verdict'] == 'WP_VARIANT' and r.get('other_base')]
    same = [r for r in out if r['verdict'] == 'WP_VARIANT' and not r.get('other_base')]
    md += [f'共 {len(base)} 首。底本不同不是校勘分歧，是两个文本系统，'
           '**不该按「同书异文」逐条裁决**：', '']
    for r in base:
        md.append(f"- {r['seq']} {r['author']}《{r['title']}》 ← {r['ws_page']}｜底本：{r['other_base']}\n"
                  f"    - {r['detail'][:200]}")
    md += ['',
           f'### 乙类：同底本内的真实异文（{len(same)} 首，这才是逐条过目的对象）', '',
           '分歧以字符对列出（选本=X 页面=Y）。**只登记，不裁决哪个对**——裁决要版本依据，我们没有。', '']
    for r in same:
        md.append(f"- {r['seq']} {r['author']}《{r['title']}》 ← {r['ws_page']}\n"
                  f"    - {r['detail'][:200]}")
    for label, tier in (('来源未声明但逐字一致（不计入双证）', 'WP_UNSOURCED_EXACT'),
                        ('循环论证', 'WP_CIRCULAR'),
                        ('WP_MISS', 'WP_MISS')):
        rows = [r for r in out if r['verdict'] == tier]
        md += ['', f'## {label}（{len(rows)} 首）', '']
        for r in rows:
            extra = f'（选本 {r["want_len"]} 字／页面 {r["page_len"]} 字）' if tier == 'WP_MISS' else ''
            md.append(f"- {r['seq']} {r['author']}《{r['title']}》 ← {r['ws_page']} {extra}")
    (HERE / 'tang300-ws-poems-proof.md').write_text('\n'.join(md) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
