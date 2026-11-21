#!/usr/bin/env python3
"""阶段 D 第 5 首：生成 V023——《宿府》(work-t300-221, V018 已立) 四层背景。MySQL 5.6.40。

与前四首的两处有意结构差异（都是证据形状逼出来的，不是偷懒）：
  1) **不铸 time.span、不挂 written_during**——本地核得到的史料只给出两个入幕窗口
     （761 严武初镇剑南／764 再镇），注本系年（鹤年谱之类）本地快照不覆盖此诗
     （实测 qss-卷03/04/05 无「宿府」）。年份未定时连「作于乱期内」都不能断言，
     所以这两个对象一个都不造——年份并列进 PERSON 层正文，向读者明说。
  2) 221 在 V018 走的是**卷页路线**（text-work-t300-221-ws 的 source 是
     source-quantangshi-228，锚点 ==宿府==）；诗页 source-ws-t300-221 不存在，不能用。

形状沿用 V020/V021/V022：纯新增（4 content + 4 claim + 4 background + 逐字引用 +
background_line 绑 text-work-t300-221-ws）。

用法: python3 -I emit_v023.py --out-sql <path> --out-rollback <path> [--dry-run]
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
from emit_v022 import (  # noqa: E402  两唐书切片也走单一来源
    JTS_GW, XTS_JN,
)

TJ223 = pathlib.Path('/tmp/src-dl/tongjian/tj-223.txt').read_text(encoding='utf-8')
V228 = pathlib.Path('/tmp/src-dl/quantangshi/vol228.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；锚不唯一即中止） ----------
# vol228 快照实际锚形状是维基链 ==[[宿府]]==，与 V018 locator 里的「==宿府==」指同一处
V228_HEAD = slice_between(V228, '==[[宿府]]==', '獨宿江城蠟炬殘。', '卷228宿府起二句')
TJ223_763Y = slice_between(TJ223, '代宗睿文孝武皇帝上之下廣德元年（癸卯', '公元七六三年）', '通鉴223卷763年标题')
TJ_TF = slice_between(TJ223, '戊寅，吐蕃入長安', '長安中蕭然一空。', '通鉴吐蕃入长安')
TJ223_764Y = slice_between(TJ223, '代宗睿文孝武皇帝上之下廣德二年（甲辰', '公元七六四年）', '通鉴223卷764年标题')
TJ_YW764 = slice_between(TJ223, '癸卯，合劍南東、西川為一道', '以黃門侍郎嚴武為節度使。', '通鉴严武再镇764')
TJ223_765Y = slice_between(TJ223, '代宗睿文孝武皇帝上之下永泰元年（乙巳', '公元七六五年）', '通鉴223卷765年标题')
TJ_YWSANG = slice_between(TJ223, '辛卯，劍南節度使嚴武薨', '吐蕃畏之，不敢犯其境。', '通鉴严武薨765')

BG = {
    'bg-sufu-scene': (
        '这一夜在幕府。井边的梧桐在清秋里发着寒，城中独宿，蜡烛一点点烧残；'
        '长夜里号角一声声，像在自言自语，中天月色那样好，却没有人同看。\n'
        '幕府是什么建制、这一夜驻在哪个衙署，要靠注本解释——本地快照里没有这部注本（实测），'
        '所以这里只说诗本文写得出的东西：一个人值夜未睡，听见了角声，看见了月亮。'),
    'bg-sufu-city': (
        '他寄身的是严武的剑南幕府。《旧唐书》本传记严武「镇成都」，《新唐书》本传记他自己'
        '「流落剑南，结庐成都西郭」——幕府在成都，成都有锦江，这些是两传的原文或字面。'
        '但诗里只说「幕府」「江城」，哪座城是注家的事；把「江城」解成成都这一步，'
        '我们本地核不到注家原文，就不替他走完。\n'
        '「已忍伶俜十年事，强移栖息一枝安」——寄人幕府，注本之外也看得见：这是安身，不是回家。'),
    'bg-sufu-world': (
        '天下在诗的字面上是远的：「风尘荏苒音书绝，关塞萧条行路难」。这两句能对上通鉴的两页：'
        '广德元年（癸卯，公元七六三年）「朝义穷蹙，缢于林中，怀仙取其首以献」，安史收场；'
        '同年十月，「戊寅，吐蕃入长安……长安中萧然一空」，代宗出奔陕州——'
        '乱子按史书算已结束，按这座被劫空的首都算没有。\n'
        '「荏苒」「萧条」把音书与行路都断在关山之外，这是诗语；'
        '通鉴同页上恰好是「士民避乱，皆入山谷」。两件事的并置是读法，通鉴的记事先后摆在那里。'),
    'bg-sufu-person': (
        '这首诗确定写在某个幕府之夜，但哪一年，我们核不到——本地只有两个窗口，都逐字可指：\n'
        '窗口一：《旧唐书》本传「上元二年冬，黄门侍郎、郑国公严武镇成都，奏为节度参谋检校尚书工部员外郎，'
        '赐绯鱼袋」（上元二年＝761，{{YL|}} 标记照登）。\n'
        '窗口二：《资治通鉴》广德二年（甲辰，公元七六四年）「癸卯，合剑南东、西川为一道，'
        '以黄门侍郎严武为节度使」，《新唐书》本传「武再帅剑南，表为参谋，检校工部员外郎」。'
        '764 年再入幕与注本旧说相合，但旧说出自我们核不到的注本，所以只能并列，不能采信。\n'
        '两传同记的结尾：「永泰元年夏，武卒，甫无所依」（旧唐书）——通鉴永泰元年（乙巳，公元七六五年）'
        '记「辛卯，剑南节度使严武薨」「吐蕃畏之，不敢犯其境」。在幕府的那几年，靠山是会先他而死的人。'),
}
CLAIMS = {
    'claim-bg-sufu-scene': (
        'INTERPRETATION', 'LIKELY',
        '独宿场景为诗本文内证（题「宿府」+起四句）；幕府建制/驻所需注本，本地快照实测无此诗，正文已声明边界。'),
    'claim-bg-sufu-city': (
        'FACT', 'LIKELY',
        '严武镇成都（旧唐书）与甫结庐成都西郭（新唐书）逐字可指；「江城」=成都的注解未核到，正文不裁决。'),
    'claim-bg-sufu-world': (
        'FACT', 'LIKELY',
        '763 收场（通鉴年标题+史朝义死，与 V019/V021/V022 同一批切片）与同年吐蕃入长安'
        '（通鉴卷223）均有逐字记载；风尘/音书与士民避乱的并置读法已标明。'),
    'claim-bg-sufu-person': (
        'FACT', 'KNOWN',
        '严武两度镇蜀与甫两度受幕职、765 武卒——旧唐书/新唐书/通鉴各记一段，互不矛盾、逐字可指，升 KNOWN；'
        'certainty 只覆盖幕府事本身，不覆盖《宿府》属于哪一窗口（注本未核到，正文并列两窗口）。'),
}
CITATIONS = [
    ('claim-bg-sufu-scene', 'source-quantangshi-228',
     '页面 全唐詩/卷228（锚点实际形状 ==[[宿府]]==，即 V018 locator 所记「==宿府==」；'
     '起二句逐字，八句全文见 V018 claim-t300-221-text 引文）',
     V228_HEAD),
    ('claim-bg-sufu-city', 'source-jiutangshu-dufu',
     '卷一百九十下·杜甫传（上元二年严武镇成都奏授一段；「镇成都」在此；{{YL|}} 标记照登）',
     JTS_GW),
    ('claim-bg-sufu-city', 'source-dufu-zhuan-candidate',
     '卷二百一·文藝上·杜甫传（流落剑南—结庐成都西郭—依严武—检校工部员外郎，连续原文）',
     XTS_JN),
    ('claim-bg-sufu-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十二（廣德元年標題+史朝義死）與卷二百二十三（同年標題+吐蕃入長安段）；'
     '四段以「……」相連，卷次不同已在定位中分記',
     join(TJ763Y, TJ763, TJ223_763Y, TJ_TF)),
    ('claim-bg-sufu-person', 'source-jiutangshu-dufu',
     '卷一百九十下·杜甫传（窗口一 761 奏授句 + 永泰元年武卒甫无所依句，两段以「……」相连）',
     join(JTS_GW, slice_between(
         pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8'),
         '{{YL|永泰元年}}夏，武卒', '甫無所依。', '旧唐书严武卒句'))),
    ('claim-bg-sufu-person', 'source-dufu-zhuan-candidate',
     '卷二百一·文藝上·杜甫传（窗口二「武再帥劍南」在流落剑南连续段内）',
     XTS_JN),
    ('claim-bg-sufu-person', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十三·廣德二年標題+合劍南東西川一道（窗口二 764）＋永泰元年標題+嚴武薨段；'
     '四段以「……」相連',
     join(TJ223_764Y, TJ_YW764, TJ223_765Y, TJ_YWSANG)),
]
BG_LINES = {'bg-sufu-scene': (1, 2), 'bg-sufu-person': (3, 4),
            'bg-sufu-world': (5, 6), 'bg-sufu-city': (7, 8)}
BG_AUDIENCE = {'bg-sufu-scene': 'PRIMARY', 'bg-sufu-person': 'JUNIOR',
               'bg-sufu-world': 'SENIOR', 'bg-sufu-city': 'JUNIOR'}
BG_TITLES = {'bg-sufu-scene': '眼前：幕府井梧边的不眠夜',
             'bg-sufu-city': '这座城：寄身人眼里的幕府与江城',
             'bg-sufu-world': '这个天下：史书说已结束、长安说没有的一年',
             'bg-sufu-person': '这个人：核不到哪一年、但两个窗口都真实'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 5 首）；史实句均有逐字引证；'
                 '注本核不到的年份写成两窗口并列，不铸系年不挂乱事线。' for k in BG}


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
    A("""-- V023：《宿府》(work-t300-221) 四层背景（阶段 D 第 5 首）。MySQL 5.6.40 兼容。
-- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V015、V018 已执行（background_line 绑 text-work-t300-221-ws，V018 插的行；
--       其 source 是 source-quantangshi-228——221 走卷页路线，无 source-ws-t300-221）。
--
-- 数据源（可复现）：emit_v023.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   資治通鑑卷222/223（763 两端与 V019/V021/V022 共用 emit_v019 的切片代码路径）、
--   新唐書卷201、舊唐書卷190下（切片复用 emit_v022 常量）、全唐詩卷228。
--
-- 做：4 BACKGROUND content/claim/background + 7 组逐字引用 +
--   8 行 background_line（scene→1,2｜person→3,4｜world→5,6｜city→7,8，绑 text-work-t300-221-ws）。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不铸 time.span、不挂 written_during**——见下。
--
-- 诚实边界（这首的边界就是形状本身）：
--   * 系年核不到：注本本地快照实测无此诗（qss-卷03/04/05 无「宿府」）；本地可核史料只给出
--     两个入幕窗口（761 初镇／764 再镇），PERSON 层并列两窗口，注本旧说「与 764 相合」也
--     标明出自核不到的来源——年份未定，所以 time.span 与 written_during 一个都不造；
--   * 「江城」=成都的注解未核到，正文不裁决；幕府建制词零注家引用；
--   * person 层 KNOWN 只覆盖幕府事（两唐书+通鉴各自逐字、互不矛盾，同 V017/V021/V022 标准），
--     不覆盖《宿府》属哪一窗口。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 22，不含 23
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-sufu-%';            -- 空
--   SELECT id FROM poetry_text_version WHERE id='text-work-t300-221-ws';  -- 恰 1 行（V018 已执行）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-sufu-%';      -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-221';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-sufu-person'; -- KNOWN
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-221'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
-- 回滚: recovery/V023_rollback.sql（按 id 全枚举删除；不动 V018 的任何行）
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
    brows = [{'id': k, 'work_id': 'work-t300-221',
              'layer': {'bg-sufu-scene': 'SCENE', 'bg-sufu-city': 'CITY',
                        'bg-sufu-world': 'WORLD', 'bg-sufu-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-221-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本 ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 23, 'su-fu background layers (inserts-only): tongjian 763 ending + Tufan capture of Chang''an + both Tang histories on the two Yan Wu shu-mufu windows; deliberately NO time.span and NO written_during -- the dating window is unresolved locally and the poem-year cannot even be placed inside or after the rebellion'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 23);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V023 精确回滚：只删 V023 插入的行（id 全枚举）。work-t300-221 本体是 V018 的行，绝不删。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 23;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (V228_HEAD, TJ223_763Y, TJ_TF, TJ223_764Y, TJ_YW764, TJ223_765Y, TJ_YWSANG,
              JTS_GW, XTS_JN, TJ763Y, TJ763):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    # 有意的形状断言：不得出现系年/乱事线对象。只查「形状」（值 AS 列名），不查裸词——
    # header 的诚实边界说明与执行后核对查询里理应提到这些词（那是文档，不是数据）。
    for shape in ("'time.span' AS property_key", "'event.name' AS property_key",
                  "'written_during' AS predicate"):
        if shape in sql:
            bad.append(f'V023 有意不造 {shape}，但 SQL 里出现了')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 11 条逐字过审；'
              f'time.span/event.name/written_during 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
