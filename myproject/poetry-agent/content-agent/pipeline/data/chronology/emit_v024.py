#!/usr/bin/env python3
"""阶段 D 第 6 首：生成 V024——《登樓》(work-t300-220, V018 已立) 四层背景。MySQL 5.6.40。

与前两首（V023 宿府）同为「不铸 time.span、不挂 written_during」的形状，理由更硬：
  * 注本路线实测不覆盖——qss-卷03/04/05 里全部三处「登樓」都是注文引王粲《登樓赋》，
    没有一处是这首诗的诗题锚；764 说出自核不到的年谱。
  * 本地能钉住的只有**下限**：「西山寇盜」可对应通鑑卷223（廣德元年標題下）
    「吐蕃陷松、維、保三州及雲山新築二城……劍南西山諸州亦入於吐蕃矣」（763）——
    但窗口关不上（西山之扰此后经年），而且诗很可能作于安史乱事**之后**（这正是它的意思），
    所以 time.span 与 written_during 一个都不造，边界写进正文与 ledger。

这首特有的证据：维基文库诗页自带**页内并列异文** `錦江春{{另|色|水}}{{另|來|流}}天地`——
页面把 色/水、來/流 两对读法都印在诗行里。V018 取首读「春色來」入正文（ws-fold），
本迁移把这一行原样引用并登记异文（tang300-variants.md），只登记不裁决。

用法: python3 -I emit_v024.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import (  # noqa: E402  切片器/SQL字面量/共用引文——单一来源
    slice_between, sql_s, join, TJ763Y, TJ763,
)
from emit_v022 import JTS_GW, XTS_JN  # noqa: E402  两唐书切片
from emit_v023 import TJ_TF, TJ_YWSANG  # noqa: E402  吐蕃入长安 / 严武薨段

TJ223 = pathlib.Path('/tmp/src-dl/tongjian/tj-223.txt').read_text(encoding='utf-8')
V228 = pathlib.Path('/tmp/src-dl/quantangshi/vol228.txt').read_text(encoding='utf-8')
WS220 = pathlib.Path('/tmp/src-dl/ws-poems/登樓__杜甫_.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；锚不唯一即中止） ----------
WS_HEAD = slice_between(WS220, '花近高樓傷客心，萬方多難此登臨。', '花近高樓傷客心，萬方多難此登臨。', 'ws220起二句')
WS_VAR = slice_between(WS220, '錦江春{{另|色|水}}{{另|來|流}}天地，', '錦江春{{另|色|水}}{{另|來|流}}天地，', 'ws220第三行(含页内异文)')
V228_HEAD = slice_between(V228, '==[[登樓 (杜甫)|登樓]]==', '萬方多難此登臨。', '卷228登樓起二句(含poem标记)')
V228_L34 = slice_between(V228, '錦江春色來天地', '玉壘浮雲變古今。', '卷228三四句')
XISHAN = slice_between(TJ223, '吐蕃陷松、維、保三州及雲山新築二城', '亦入於吐蕃矣。', '通鉴西山诸州入吐蕃')
TJ_FENG = slice_between(TJ223, '僕固懷恩與回紇、吐蕃進逼奉天', '京師戒嚴。', '通鉴奉天戒严764')
TJ_YWWIN = slice_between(TJ223, '己未，劍南節度使嚴武破吐蕃七萬眾', '拔當狗城。', '通鉴严武破吐蕃764')

BG = {
    'bg-dl-scene': (
        '这一次是登临。花逼近高楼，看的却是伤心——诗题只有一个动作：登樓；'
        '第一联把动作和心情同时给出：「花近高樓傷客心，萬方多難此登臨。」\n'
        '哪座楼、哪一年登的，要靠注本和年谱——实测本地《杜詩詳註》三卷快照里出现的'
        '「登樓」全是注家引王粲的《登樓赋》，没有一处注这首诗，所以我们连楼名都不给。'),
    'bg-dl-city': (
        '他望见的两处地名都在诗里：锦江、玉垒。维基文库诗页在第三行里**并列印着两读**——'
        '「錦江春{{另|色|水}}{{另|來|流}}天地」（{{另|}} 是页面的异文标记，原样引）；'
        '《全唐詩》卷228 的转录取首读作「錦江春色來天地」。两读只登记，不裁决。\n'
        '这一年蜀中的边境有自己的分量：通鑑记严武「三鎮劍南」时写「吐蕃畏之，不敢犯其境」，'
        '又在廣德二年记他「破吐蕃七萬眾，拔當狗城」。锦江玉垒之南是一个打得动吐蕃的剑南；'
        '但往西北看，就是下一条。'),
    'bg-dl-world': (
        '「萬方多難」在这首诗的时间点上，有一串通鑑逐字可对的事。安史收场（廣德元年'
        '「朝義窮蹙，縢于林中」）之后紧接着：同年十月「吐蕃入長安……長安中蕭然一空」；'
        '同年，「吐蕃陷松、維、保三州及雲山新築二城，西川節度使高適不能救，於是劍南西山'
        '諸州亦入於吐蕃矣」；廣德二年，「僕固懷恩與回紇、吐蕃進逼奉天，京師戒嚴」。\n'
        '所以「北極朝廷終不改，西山寇盜莫相侵」不是泛泛的忧世：北边京师刚被占过又夺回，'
        '西边的剑南州郡正在成片丢。朝廷与寇盗，通鑑同一年代里两页都有。'),
    'bg-dl-person': (
        '写诗的人此时在剑南，具体年份与《宿府》同案：只有两个窗口——《旧唐书》本传'
        '「上元二年冬……严武镇成都，奏为节度参谋检校尚书工部员外郎」（761），'
        '《通鉴》广德二年「合剑南东、西川为一道，以黄门侍郎严武为节度使」+《新唐书》'
        '「武再帅剑南，表为参谋」（764）；注本年谱核不到，两说并列。\n'
        '末联的两个典故都不注不行，但我们核不到注：「後主還祠廟」历来多解——'
        '不选边，只把史实摆出：763 年长安确实被占（「吐蕃入長安」），代宗确实还了京；'
        '「梁甫吟」旧属诸葛亮，注本没核到，也不替他续。一首诗收在「日暮」二字上，'
        '这是诗本文写得出的全部。'),
}
CLAIMS = {
    'claim-bg-dl-scene': (
        'INTERPRETATION', 'LIKELY',
        '登临场景为诗本文内证（题「登樓」+首联）；楼名/年份注本实测不覆盖（qss 三卷「登樓」皆引王粲赋），正文已声明。'),
    'claim-bg-dl-city': (
        'FACT', 'LIKELY',
        '页内并列异文（色/水、來/流）有 ws 快照逐字（{{另|}} 标记照登）；首读「春色來」有卷228 第二转录逐字；'
        '严武破吐蕃/吐蕃不敢犯境有通鉴卷223 逐字。'),
    'claim-bg-dl-world': (
        'FACT', 'LIKELY',
        '763 收场+吐蕃入长安+西山诸州入吐蕃+764 奉天戒严均有通鉴卷222/223 逐字（763 两端与 V019/V021–V023 共用切片）。'),
    'claim-bg-dl-person': (
        'FACT', 'KNOWN',
        '两度入严武幕（761/764 两窗口，两唐书+通鉴各记一段互不矛盾逐字可指）升 KNOWN，'
        '与 V023 同规矩：certainty 只覆盖幕府事，不覆盖此诗属哪一窗口；典故诸解核不到，不裁决。'),
}
CITATIONS = [
    ('claim-bg-dl-scene', 'source-ws-t300-220',
     '页面 登樓 (杜甫)（起二句逐字，八句全文见 V018 claim-t300-220-text 引文）',
     WS_HEAD),
    ('claim-bg-dl-city', 'source-ws-t300-220',
     '页面 登樓 (杜甫)（第三行含页内异文标记 {{另|色|水}}{{另|來|流}}，原样引；'
     '登记 corpus/tang300-variants.md 不裁决）',
     WS_VAR),
    ('claim-bg-dl-city', 'source-quantangshi-228',
     '页面 全唐詩/卷228（锚点 ==[[登樓 (杜甫)|登樓]]==，<poem> 标记照登；第二转录取首读）',
     join(V228_HEAD, V228_L34)),
    ('claim-bg-dl-city', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十三·永泰元年（嚴武薨段含「三鎮劍南」「吐蕃畏之不敢犯其境」）',
     TJ_YWSANG),
    ('claim-bg-dl-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十二（廣德元年標題+史朝義死）與卷二百二十三（吐蕃入長安段〔廣德元年〕、'
     '陷松維保三州〔廣德元年〕、廣德二年奉天戒嚴、嚴武破吐蕃拔當狗城）；'
     '六段以「……」相連，卷次與年標題歸屬已在定位分記',
     join(TJ763Y, TJ763, TJ_TF, XISHAN, TJ_FENG, TJ_YWWIN)),
    ('claim-bg-dl-person', 'source-jiutangshu-dufu',
     '卷一百九十下·杜甫传（窗口一 761 奏授句；{{YL|}} 标记照登）',
     JTS_GW),
    ('claim-bg-dl-person', 'source-dufu-zhuan-candidate',
     '卷二百一·文藝上·杜甫传（窗口二「武再帥劍南」在流落剑南连续段内）',
     XTS_JN),
]
BG_LINES = {'bg-dl-scene': (1, 2), 'bg-dl-city': (3, 4),
            'bg-dl-world': (5, 6), 'bg-dl-person': (7, 8)}
BG_AUDIENCE = {'bg-dl-scene': 'PRIMARY', 'bg-dl-city': 'JUNIOR',
               'bg-dl-world': 'SENIOR', 'bg-dl-person': 'JUNIOR'}
BG_TITLES = {'bg-dl-scene': '眼前：花逼近楼的那次登临',
             'bg-dl-city': '这一带：锦江玉垒与打得动吐蕃的剑南',
             'bg-dl-world': '这个天下：乱事收了场、州郡在成片丢的一年',
             'bg-dl-person': '这个人：两个窗口都真、典故都核不到'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 6 首）；史实句均有逐字引证；'
                 '页内异文只登记；年份窗口关不上，不铸系年不挂乱事线。' for k in BG}


def guard(table, cols, rows, match_expr):
    sel = '\nUNION ALL\n'.join(
        'SELECT ' + ', '.join(f'{sql_s(r[c])} AS {c}' for c in cols) + ' FROM DUAL'
        for r in rows)
    return (f'INSERT INTO {table} ({", ".join(cols)})\n'
            f'SELECT * FROM (\n{sel}\n) AS t\n'
            f'WHERE NOT EXISTS (SELECT 1 FROM {table} x WHERE {match_expr});')


def build():
    L = []
    A = L.append
    A("""-- V024：《登樓》(work-t300-220) 四层背景（阶段 D 第 6 首）。MySQL 5.6.40 兼容。
-- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V004、V010、V015、V018 已执行（background_line 绑 text-work-t300-220-ws，V018 插的行；
--       220 走诗页路线，text_version 的 source 是 source-ws-t300-220；source-quantangshi-228 亦 V018 立）。
--
-- 数据源（可复现）：emit_v024.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/登樓__杜甫_.txt（页内异文 {{另|}} 标记照登）、全唐詩卷228、
--   資治通鑑卷222/223（763 两端共用 emit_v019 代码路径）、新唐書卷201、舊唐書卷190下（复用 emit_v022/023 常量）。
--
-- 做：4 BACKGROUND content/claim/background + 7 组逐字引用 +
--   8 行 background_line（scene→1,2｜city→3,4｜world→5,6｜person→7,8，绑 text-work-t300-220-ws）。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不铸 time.span、不挂 written_during**——见下。
--
-- 诚实边界：
--   * 系年只有下限：「西山寇盜」对应通鑑卷223（廣德元年）西山诸州入吐蕃（763），窗口关不上，
--     764 说出核不到的年谱；诗可能作于安史乱事之后，written_during 亦不造；
--   * 楼名不取（注本实测三卷快照的「登樓」全是引王粲《登樓赋》，不注此诗）；
--   * 页内异文 色/水、來/流 只登记（tang300-variants.md）；「後主還祠廟」诸解不选边，只列史实；
--   * 「梁甫吟」属诸葛亮的注法未核到，不引申。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 23，不含 24
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-dl-%';              -- 空
--   SELECT id FROM poetry_text_version WHERE id='text-work-t300-220-ws';  -- 恰 1 行（V018 已执行）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-dl-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-220';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-dl-person';   -- KNOWN
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-220'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
-- 回滚: recovery/V024_rollback.sql（按 id 全枚举删除；不动 V018 的任何行）
START TRANSACTION;""")

    A('\n-- ---------- 1. BACKGROUND content identities ----------')
    rows = [{'id': k, 'entity_type': 'BACKGROUND', 'slug': k[3:], 'title': BG_TITLES[k],
             'summary': BG_SUMMARY[k], 'time_precision': 'UNKNOWN'} for k in BG]
    A(guard('poetry_content', ['id', 'entity_type', 'slug', 'title', 'summary', 'time_precision'],
            rows, 'x.id = t.id'))

    A('\n-- ---------- 2. claims（主语=BACKGROUND content 行；claim id 带 claim- 前缀，V004 同款） ----------')
    crows = [{'id': k, 'subject_id': k.replace('claim-', '', 1), 'property_key': 'context',
              'value_text': v[2], 'claim_kind': v[0], 'certainty': v[1]} for k, v in CLAIMS.items()]
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            crows, 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': k.replace('claim-', '', 1), 'property_key': 'context', 'claim_id': k}
             for k in CLAIMS],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))

    A('\n-- ---------- 3. background rows ----------')
    brows = [{'id': k, 'work_id': 'work-t300-220',
              'layer': {'bg-dl-scene': 'SCENE', 'bg-dl-city': 'CITY',
                        'bg-dl-world': 'WORLD', 'bg-dl-person': 'PERSON'}[k],
              'body_text': BG[k], 'audience': BG_AUDIENCE[k], 'claim_id': 'claim-' + k} for k in BG]
    A(guard('poetry_background', ['id', 'work_id', 'layer', 'body_text', 'audience', 'claim_id'],
            brows, 'x.id = t.id'))

    A('\n-- ---------- 4. 逐字引文 ----------')
    L.append('INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(c)} AS claim_id, {sql_s(s)} AS source_id, {sql_s(loc)} AS locator, "
        f"{sql_s(ex)} AS evidence_excerpt FROM DUAL"
        for c, s, loc, ex in CITATIONS))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_citation x '
             'WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);')

    A('\n-- ---------- 5. background_line ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-220-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（字面量里不用裸撇号——V023 教训；此处无撇号） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 24, 'deng-lou background layers (inserts-only): tongjian vol223 Xishan lost + Fengtian alarm + Yan Wu victory; ws page carries inline variant pairs (se/shui, lai/liu) quoted verbatim and registered not adjudicated; deliberately NO time.span (only a 763 lower bound closes locally) and NO written_during (the poem may postdate the An-Shi ending)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 24);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V024 精确回滚：只删 V024 插入的行（id 全枚举）。work-t300-220 本体是 V018 的行，绝不删。',
         'START TRANSACTION;']
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 24;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (WS_HEAD, WS_VAR, V228_HEAD, V228_L34, XISHAN, TJ_FENG, TJ_YWWIN,
              TJ_TF, TJ_YWSANG, JTS_GW, XTS_JN, TJ763Y, TJ763):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    # 有意的形状断言：只查「值 AS 列名」形状，不查裸词（header 的说明该提到这些词）
    for shape in ("'time.span' AS property_key", "'event.name' AS property_key",
                  "'written_during' AS predicate"):
        if shape in sql:
            bad.append(f'V024 有意不造 {shape}，但 SQL 里出现了')
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
    for k, v in BG_TITLES.items():
        if len(k) > 64 or len(k[3:]) > 120 or len(v) > 200:
            bad.append(f'content 宽度超限: {k}')
    for c, s, loc, ex in CITATIONS:
        if len(c) > 64 or len(loc) > 300 or len(ex) > 500:
            bad.append(f'citation 宽度超限: {c} ({len(loc)}B/{len(ex)}B)')
    for m in re.finditer(r'INSERT INTO (poetry_\w+)', sql):
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
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-sql', required=True)
    ap.add_argument('--out-rollback', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    sql = build()
    rb = build_rollback()
    bad = audit(sql)
    if bad:
        print('AUDIT FAIL:')
        for b in bad:
            print(' -', b)
        raise SystemExit(1)
    if args.dry_run:
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 13 条逐字过审；'
              f'time.span/event.name/written_during 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
