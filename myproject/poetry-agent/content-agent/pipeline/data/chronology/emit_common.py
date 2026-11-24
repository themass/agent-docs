#!/usr/bin/env python3
"""emit_common——阶段 D 生成器公共框架（2026-11-24 抽取）。

抽的判据只有一条：**这件事与「这首 poems 的解读」无关，且 64 个生成器里已经复制过**。
每首诗剩下的只有四样东西：切片、四层正文、该首特有的负证/入引硬卡、系年判决语。
其余（切片器、快照语料、闭域档扫、年标题窗口、幂等 INSERT、回滚枚举、既往引文域查重、
审计不变量）都在此文件——**一处实现，一处文档**（不变量清单见 docs/emit-framework.md）。

框架不放宽任何断言：所有 check_* 只把 v019–v077 里已经在跑的断言搬过来，
每个生成器仍必须显式列出自己要跑的项（漏项 = 该首诗 audit 少一栏，
docs/emit-framework.md 的第 0 节就是「每首必跑项」清单）。

核心类/函数一览
    Snap            快照语料（/tmp/src-dl）只读装载 + 语料规模断言（页/卷数变动即中止）
    slice_between   唯一锚点闭区间切片（emit_v019 原版逐字节同义）
    window          摘句前最近年标题窗口断言
    guard           幂等 INSERT（WHERE NOT EXISTS）
    citation_union / bgline_union / version_row   SQL 段拼装（格式与 v076/v077 逐字节一致）
    rollback_sql    按 id 全枚举回滚
    Premises        既往引文域查重（域=V0*.sql 里 evidence_excerpt 行含针；排除本迁移自己）
    check_*         可组合审计项（切片入引/零重开/形制/恰 N 枚源/KNOWN 零/宽度/幂等/主键/id 重复）

用法（生成器骨架）：
    from emit_common import (Snap, slice_between, window, guard, citation_union,
                             bgline_union, version_row, rollback_sql, Premises,
                             join, sql_s, check_*)
"""
from __future__ import annotations
import pathlib
import re

# ---------------------------------------------------------------- 快照语料

DL = pathlib.Path('/tmp/src-dl')
POETRY_SQL_DIR = pathlib.Path(
    '/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')


class Snap:
    """只读快照语料。规模断言：语料被回收/增删即中止——所有闭域判决的地基在这里。

    ws      ws-poems/*.txt        （《唐詩三百首》选本诗页）
    qts     quantangshi/vol*.txt  （御定全唐詩卷页）
    tj      tongjian/tj-*.txt     （资治通鉴）
    hist    jts-*/xts-*/qss-*     （旧唐书/新唐书/全唐诗注本等史部与注本快照，顶层）
    fetch   quantangshi/fetch.log （抓取日志：底本在册/在册外的机器凭证）
    """

    def __init__(self, expect_ws=295, expect_qts=118, expect_tj=75):
        self.expect = {}
        self.ws = self._dir(DL / 'ws-poems', '*.txt')
        self.qts = self._dir(DL / 'quantangshi', 'vol*.txt')
        self.tj = self._dir(DL / 'tongjian', 'tj-*.txt')
        self.hist = {}
        for pat in ('jts-*.txt', 'xts-*.txt', 'qss-*.txt'):
            for p in DL.rglob(pat):
                self.hist[p.name] = p.read_text(encoding='utf-8')
        fl = DL / 'quantangshi' / 'fetch.log'
        self.fetch = fl.read_text(encoding='utf-8') if fl.exists() else ''
        for label, got, want in (('ws 诗页', len(self.ws), expect_ws),
                                 ('全唐詩卷', len(self.qts), expect_qts),
                                 ('通鉴卷', len(self.tj), expect_tj)):
            if want is not None and got != want:
                raise SystemExit(f'快照 {label} 数 {got} ≠ {want}——所有闭域档扫须重估，中止')

    @staticmethod
    def _dir(d, pat):
        out = {p.name: p.read_text(encoding='utf-8') for p in sorted(d.glob(pat))}
        if not out:
            raise SystemExit(f'快照目录 {d} 无 {pat}——先按 fetch_*.sh 补齐语料')
        return out

    # 拼接语料（闭域计数用）
    @property
    def all_tj(self):
        return ''.join(self.tj.values())

    @property
    def all_qts(self):
        return ''.join(self.qts.values())

    @property
    def all_hist(self):
        """史部快照+通鉴（「七史快照全零」类判决的地基）。"""
        return ''.join(self.hist.values()) + self.all_tj

    @property
    def all_ws(self):
        return ''.join(self.ws.values())


# ---------------------------------------------------------------- 切片与断言

def slice_between(src, start_anchor, end_anchor, what):
    """唯一锚点切片：start/end 各自在快照中恰好出现一次，且 end 在 start 之后。
    返回 [start, end] 闭区间原文，逐字节来自快照。任何一步不满足就中止——
    宁可生成失败，不能引错字。（emit_v019 原版）"""
    if src.count(start_anchor) != 1:
        raise SystemExit(f'锚点不唯一（{src.count(start_anchor)} 次）：{what} / {start_anchor[:20]}')
    if src.count(end_anchor) != 1:
        raise SystemExit(f'锚点不唯一（{src.count(end_anchor)} 次）：{what} / {end_anchor[:20]}')
    a = src.index(start_anchor)
    b = src.index(end_anchor)
    if b < a:
        raise SystemExit(f'锚点顺序反了：{what}')
    q = src[a:b + len(end_anchor)]
    if src.count(q) != 1:
        raise SystemExit(f'切片不唯一：{what}')
    return q


def join(*parts):
    """同一 (claim,source) 只允许一行引文，跨段用「……」连接（V017 起惯例）。"""
    return '……'.join(parts)


def need(cond, msg):
    """断言失败即中止（生成器里所有「快照变了」的中止走这里）。"""
    if not cond:
        raise SystemExit(msg)


_YEAR_HEAD = re.compile(
    r'[^\n]*(?:（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][，、]公元[〇零一二三四五六七八九十百千]+年）'
    r'|\{\{\*\|[甲乙丙丁戊己庚辛壬癸]，西元[〇零一二三四五六七八九十百千]+年\}\})')


def window(txt, needle, want):
    """摘句前最近的年标题必须含 want（通鉴年标题窗口断言）。"""
    i = txt.find(needle)
    need(i >= 0, f'快照里没有「{needle[:20]}」——窗口断言无从谈起')
    hs = [m.start() for m in _YEAR_HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    need(bool(prev) and want in txt[prev[-1]:prev[-1] + 90],
         f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')


# ---------------------------------------------------------------- 闭域档扫
# 约定：*where 返回「含该针的页/卷名集合」，调用方拿它做恰 N / 全零 / 恰在某页断言。

def ws_where(snap, pred):
    return {n for n, t in snap.ws.items() if pred(t)}


def qts_where(snap, needle):
    return sorted(n for n, t in snap.qts.items() if needle in t)


def tj_where(snap, needle):
    return sorted(n for n, t in snap.tj.items() if needle in t)


def line_pages(snap, needle):
    """evidence_excerpt 无关；按「行含针」统计页（notes/title/类目这类行级判据）。"""
    return {n for n, t in snap.ws.items() if any(needle in l for l in t.splitlines())}


def notes_line(t):
    for l in t.splitlines():
        if l.startswith('| notes'):
            return l
    return ''


def title_line(t):
    for l in t.splitlines():
        if l.startswith('| title'):
            return l
    return ''


# ---------------------------------------------------------------- SQL 拼装
# 格式与已入库的 V0xx 逐字节一致：动格式=动已提交的 SQL 事实，须双跑比对。

def sql_s(v):
    assert '\\' not in v, f'字面量里不许有反斜杠: {v[:40]}'
    return "'" + v.replace("'", "''") + "'"


def guard(table, cols, rows, match_expr):
    """幂等 INSERT：VALUES 走 SELECT ... UNION ALL + WHERE NOT EXISTS。"""
    def lit(v):
        if v is None:
            return 'NULL'
        if isinstance(v, int):
            return str(v)
        return sql_s(v)
    sel = '\nUNION ALL\n'.join(
        'SELECT ' + ', '.join(f'{lit(r[c])} AS {c}' for c in cols) + ' FROM DUAL'
        for r in rows)
    return (f'INSERT INTO {table} ({", ".join(cols)})\n'
            f'SELECT * FROM (\n{sel}\n) AS t\n'
            f'WHERE NOT EXISTS (SELECT 1 FROM {table} x WHERE {match_expr});')


def content_rows(BG, BG_TITLES, BG_SUMMARY):
    return [{'id': k, 'entity_type': 'BACKGROUND', 'slug': k[3:], 'title': BG_TITLES[k],
             'summary': BG_SUMMARY[k], 'time_precision': 'UNKNOWN'} for k in BG]


def claim_rows(CLAIMS):
    return [{'id': k, 'subject_id': k.replace('claim-', '', 1), 'property_key': 'context',
             'value_text': v[2], 'claim_kind': v[0], 'certainty': v[1]} for k, v in CLAIMS.items()]


def claim_selection_rows(CLAIMS):
    return [{'subject_id': k.replace('claim-', '', 1), 'property_key': 'context', 'claim_id': k}
            for k in CLAIMS]


def background_rows(BG, work_id, layers, audience=None):
    return [{'id': k, 'work_id': work_id, 'layer': layers[k],
             'body_text': BG[k], 'audience': (audience or {}).get(k),
             'claim_id': 'claim-' + k} for k in BG]


def citation_union(CITATIONS):
    out = ['INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)\nSELECT * FROM (',
           '\nUNION ALL\n'.join(
               f"SELECT {sql_s(c)} AS claim_id, {sql_s(s)} AS source_id, {sql_s(loc)} AS locator, "
               f"{sql_s(ex)} AS evidence_excerpt FROM DUAL"
               for c, s, loc, ex in CITATIONS),
           ') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_citation x '
           'WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);']
    return '\n'.join(out)


def bgline_union(BG_LINES, version_id):
    out = ['INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (',
           '\nUNION ALL\n'.join(
               f"SELECT {sql_s(k)} AS background_id, {sql_s(version_id)} AS version_id, {n} AS line_seq FROM DUAL"
               for k, seqs in BG_LINES.items() for n in seqs),
           ') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
           'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
           'AND x.line_seq = t.line_seq);']
    return '\n'.join(out)


def version_row(no, description):
    return ("INSERT INTO poetry_schema_version (version_no, description)\n"
            f"SELECT {no}, {sql_s(description)}\n"
            'FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version '
            f'WHERE version_no = {no});')


def rollback_sql(version_no, BG, CLAIMS, new_source_ids, header_lines):
    """按 id 全枚举回滚。new_source_ids = 本迁移新建的源（其余既有源绝不删）。"""
    L = list(header_lines) + ['START TRANSACTION;']
    cids = list(CLAIMS)

    def dels(table, col, vals, chunk=40):
        for i in range(0, len(vals), chunk):
            L.append(f'DELETE FROM {table} WHERE {col} IN ('
                     + ', '.join(sql_s(v) for v in vals[i:i + chunk]) + ');')
    dels('poetry_claim_selection', 'claim_id', cids)
    dels('poetry_citation', 'claim_id', cids)
    dels('poetry_background_line', 'background_id', list(BG))
    dels('poetry_background', 'id', list(BG))
    dels('poetry_claim', 'id', cids)
    dels('poetry_content', 'id', list(BG))
    for sid in new_source_ids:
        L.append('DELETE FROM poetry_source WHERE id = ' + sql_s(sid) + ';')
    L.append(f'DELETE FROM poetry_schema_version WHERE version_no = {version_no};')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


# ---------------------------------------------------------------- 既往引文域查重

class Premises:
    """既有 V0*.sql 里「这句话谁引过」的机器查重——在册句零重开、让渡/耗尽断言的地基。

    域(excerpt)：evidence_excerpt 所在行含针的迁移集（只看单行——逐字引文都在一行上）；
    域(whole)：整文件含针（source id、locator 这类跨段事实用这个）。
    本迁移自己的文件必须排除（exclude=<本迁移版本前缀>），否则自引用。
    """

    def __init__(self, exclude_prefixes=()):
        self.exclude = tuple(exclude_prefixes)
        self.files = [f for f in sorted(POETRY_SQL_DIR.glob('V0*.sql'))
                      if not f.name.startswith(self.exclude)]

    def excerpt(self, needle):
        out = set()
        for f in self.files:
            for ln in f.read_text(encoding='utf-8').splitlines():
                if 'evidence_excerpt' in ln and needle in ln:
                    out.add(f.name.split('__')[0])
                    break
        return sorted(out)

    def whole(self, needle):
        return sorted({f.name.split('__')[0] for f in self.files
                       if needle in f.read_text(encoding='utf-8')})

    def must_be(self, label, needle, want, mode='excerpt'):
        got = self.whole(needle) if mode == 'whole' else self.excerpt(needle)
        need(got == want, f'前提「{label}」既往引文域 {got} ≠ {want}——须重设计')

    def must_be_first(self, label, needle):
        got = self.excerpt(needle)
        need(not got, f'首引句「{label}」既往域非零（{got}）——须换句或降级')


# ---------------------------------------------------------------- 审计不变量
# 每个生成器的 audit() 显式调用需要的 check_*；漏调 = 该首少一栏（见框架文档第 0 节）。

def cited_blob(CITATIONS):
    return '……'.join(sorted(ex for _, _, _, ex in CITATIONS))


def check_slices(sql, CITATIONS, slices, bad):
    """每条切片：①逐字节进 SQL ②逐字节进某条引文。"""
    flat = sql.replace("''", "'")
    cited = cited_blob(CITATIONS)
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')


def check_not_reopen(cited, tokens, bad, label='判例只引不重开'):
    for tok in tokens:
        if tok in cited:
            bad.append(f'{label}：{tok} 不得入本迁移引文')


def check_tokens_in(needle, toks, bad, label):
    for tok in toks:
        if tok not in needle:
            bad.append(f'{label}缺要素「{tok}」')


def check_shape(BG_LINES, want, bad):
    if BG_LINES != want:
        bad.append(f'background_line 须为 {want}（四句绝句常规顺次）')


def check_bgline_count(sql, version_id, n, bad):
    if len(re.findall(re.escape(version_id) + r"' AS version_id", sql)) != n:
        bad.append(f'bg_line INSERT 的 version 行数应为 {n}')


def check_sources(sql, rb, new_ids, keep_ids, bad):
    """恰新建 len(new_ids) 枚 source；回滚恰删这些枚；既有 keep_ids 零删除。"""
    if sql.count('INSERT INTO poetry_' + 'source') != len(new_ids):
        bad.append(f'本迁移应恰新建 {len(new_ids)} 枚 source，SQL 里 source INSERT 数不是 {len(new_ids)}')
    for sid in new_ids:
        if sql_s(sid) not in sql:
            bad.append(f'{sid} 未入 SQL')
    if rb.count('DELETE FROM poetry_' + 'source') != len(new_ids):
        bad.append(f'回滚须恰含 {len(new_ids)} 行 source 删除')
    for sid in new_ids:
        if 'DELETE FROM poetry_source WHERE id = ' + sql_s(sid) not in rb:
            bad.append(f'回滚缺 source 删除行 {sid}')
    for keep in keep_ids:
        if 'DELETE FROM poetry_source WHERE id = ' + sql_s(keep) in rb:
            bad.append(f'回滚误删既有源 {keep}')


def check_zero_known(sql, CLAIMS, bad):
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（KNOWN 零如实记录）')


def check_pairs(CITATIONS, bad, want_n=None):
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if want_n is not None and len(CITATIONS) != want_n:
        bad.append(f'本迁移引文应为 {want_n} 组')


def check_no_cast(sql, work_ids, bad):
    """零铸造：不给诗铸 time.span/event.name/written_during、零 relation、work 不做 claim 主语。"""
    if "'written_during' AS predicate" in sql:
        bad.append("本迁移有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('本迁移有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for w in work_ids:
        for pk in ('time.span', 'event.name'):
            if f"'{w}' AS subject_id, '{pk}' AS property_key" in sql:
                bad.append(f'本迁移有意不给 {w} 铸 {pk}，但该主语组合出现了')
        if f"SELECT '{w}' AS subject_id" in sql:
            bad.append(f'claim 主语应全部是 bg-*，{w} 不该做主语')


def check_no_textline_touch(sql, rb, bad):
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('本迁移不碰 poetry_text_line')


def check_phrases(text, required, bad):
    for p in required:
        if p not in text:
            bad.append(f'BG 须含「{p}」声明')


def check_id_unique(sql, bad):
    seen = {}
    cur = None
    for m in re.finditer(r'INSERT INTO (poetry_\w+)|SELECT \'([a-z0-9][a-z0-9_.-]{3,})\' AS id\b', sql):
        if m.group(1):
            cur = m.group(1)
        else:
            key = (cur, m.group(2))
            if key in seen:
                bad.append(f'id 文档内重复：{cur} {m.group(2)}')
            seen[key] = True


def check_widths(BG_TITLES, CITATIONS, bad):
    for k, v in BG_TITLES.items():
        if len(k) > 64 or len(k[3:]) > 120 or len(v) > 200:
            bad.append(f'content 宽度超限: {k}')
    for c, s, loc, ex in CITATIONS:
        if len(c) > 64 or len(loc) > 300 or len(ex) > 500:
            bad.append(f'citation 宽度超限: {c} ({len(loc)}B/{len(ex)}B)')


def check_idempotent(sql, version_no, bad):
    """每条 INSERT（版本账本除外）必须带 WHERE NOT EXISTS；账本要有显式守卫。"""
    for m in re.finditer(r'INSERT INTO (poetry_\w+)', sql):
        if m.group(1) == 'poetry_schema_version':
            continue
        i, in_str, end = m.end(), False, len(sql)
        while i < end:
            ch = sql[i]
            if in_str:
                if ch == "'":
                    if i + 1 < end and sql[i + 1] == "'":
                        i += 1
                    else:
                        in_str = False
            elif ch == "'":
                in_str = True
            elif ch == ';':
                end = i
                break
            i += 1
        if 'WHERE NOT EXISTS' not in sql[m.start():end]:
            bad.append(f'{m.group(1)} 的 INSERT 没有幂等守卫')
    vblk = sql[sql.index('INSERT INTO poetry_schema_version'):]
    if (f'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = {version_no})'
            not in vblk):
        bad.append('poetry_schema_version INSERT 缺显式幂等守卫')
