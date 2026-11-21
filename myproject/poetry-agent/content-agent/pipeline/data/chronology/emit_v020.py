#!/usr/bin/env python3
"""阶段 D 第 2 首：生成 V020——《月夜》(work-t300-207, V018 已立) 四层背景。MySQL 5.6.40。

与 V019 的区别：月夜在库里没有任何 V004 遗留（V004 只做了春望），所以 V020 是**纯新增**：
  4 个 BACKGROUND content + 4 个 claim + 4 行 background（body_text 带证）+ 引用的逐字原文
  + background_line 绑到 text-work-t300-207-ws（V018 建的版本——**前置：V018 已执行**）
  + 1 条 time.span 系年断言 + 1 条 written_during 安史之乱挂接（同 V017 春望的形状）。

证据与 V019 同源复用（import，不抄第二份）；月夜自己的注材料全在 qss-卷04.txt 快照内：
鹤注系年月夜（天寳十五載八月）、杜臆（思家想家人思己）、刘后村（笃于伉俪）。
切片规矩同 V019：唯一锚点、逐字节一致、录入标记照登。

一个必须如实处理的史料矛盾：**《旧唐书》说杜甫自长安宵遁成功（拜右拾遗），《新唐书》说他被叛军抓住
（為賊所得），两《唐书》互相矛盾**；《月夜》的处境读法（身在长安、家在鄜州）站在《新唐书》+鹤注一边。
正文与 claim 都要写出这个分歧，不取独断。

用法: python3 -I emit_v020.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
# 证据单一来源：通鉴/两唐书切片与 sql_s 全部来自 emit_v019（其顶层代码只做快照读取与切片校验）
from emit_v019 import (  # noqa: E402
    slice_between, sql_s,
    TJ755Y, TJ755, TJ763Y, TJ763, TJC1, TJC2, V011_XTS, V011_JTS,
)

QSS04 = (pathlib.Path('/tmp/src-dl/qss-卷04.txt')).read_text(encoding='utf-8')

# ---------- 月夜自己的注引文（唯一锚点切片，快照内逐字节） ----------
HE_YY = slice_between(QSS04, '{{SK anchor|月夜}}', '故作此詩}}', '鹤注月夜系年')
DUYI = slice_between(QSS04, '杜臆公本思家', '見此老鍾情之至', '杜臆月夜语')
LHC = slice_between(QSS04, '劉後村詩話故人陳伯霆', '其篤於伉儷如此', '刘后村语')


def join(*parts):
    return '……'.join(parts)


# ---------- 四层正文（读者语言；史实后面站的只有下面的引文） ----------
BG = {
    'bg-yueye-scene': (
        '这首诗的「眼前」不在诗人自己面前：他被困在长安，看见的月亮是想象里家人的月亮——'
        '今夜鄜州上空那轮月，只有妻子一个人在看。\n'
        '「本是自己思家，偏从对面写家人想你」不是现代人的讲法：注本《杜臆》就说'
        '「公本思家偏想家人思已，已进一层；至念及儿女不能思，又进一层」。'
        '先把自己翻过去，再替家人把月看完——这一层的入口是注家早就指出的。'),
    'bg-yueye-city': (
        '「未解忆长安」——孩子们还不懂得「长安」两个字值多少牵挂。懂的人才知道：'
        '这座京城已经陷在叛军手里，诗人自己也陷在里面。\n'
        '沦陷后的长安，《资治通鉴》卷二一八记了两笔：禄山「命搜捕百官、宦者、宫女等，每获数百人，'
        '辄以兵卫送洛阳」，留在长安的王侯将相「诛及婴孩」；同罗、突厥叛军逃归时'
        '「长安大扰，官吏窜匿，狱囚自出」。'),
    'bg-yueye-world': (
        '这场战事起于天宝十四年（乙未，公元七五五年）「禄山发所部兵……反于范阳」，'
        '终于广德元年（癸卯，公元七六三年）史朝义「穷蹙，缢于林中」——都在《资治通鉴》的年标题里。\n'
        '这首诗写于乱中的哪一年？注家给了一个点：仇注引鹤注系于天宝十五载八月，也就是公元 756 年。'
        '这是单源注本的系年，我们记下它，不把它当定论。'),
    'bg-yueye-person': (
        '写这首诗时，杜甫的家眷寄在鄜州，他本人在沦陷的长安——「身在长安，家在鄜州」。\n'
        '他是怎么陷在长安的，两部正史自己就先打架：《新唐书》本传说他「自鄜州羸服欲奔行在，为贼所得」'
        '（衣衫破旧想去投奔朝廷，半路被叛军抓住）；《旧唐书》本传却说「十五载，禄山陷京师……'
        '甫自京师宵遁赴河西，谒肃宗于彭原郡，拜右拾遗」（夜里逃出去了）。两说并存，我们不下判断；'
        '《月夜》的处境读法依据的是《新唐书》与鹤注「为贼所得，时在长安」这一边。\n'
        '注家说这首诗「笃于伉俪」：刘后村引陈伯霆的玩笑反证——人们都说杜甫善谑、连妻女都不放过，'
        '可「香雾云鬟湿，清辉玉臂寒」写妻子的发肤如此细致，「其笃于伉俪如此」。'),
}
CLAIMS = {
    'claim-bg-yueye-scene': (
        'INTERPRETATION', 'LIKELY',
        '对面写法（本思家而写家人思己）为注家《杜臆》指出的读法；想象之月是诗的结构，不是诗人目击。'),
    'claim-bg-yueye-city': (
        'FACT', 'LIKELY',
        '长安沦陷后的搜捕与秩序崩坏有《资治通鉴》卷218逐字记载；本诗背景中的陷城处境另系于鹤注系年（756）。'),
    'claim-bg-yueye-world': (
        'FACT', 'LIKELY',
        '战事起讫以通鉴年标题为锚（755反于范阳/763史朝义死）；本诗系年于天宝十五载八月（=756）出自鹤注单源，LIKELY。'),
    'claim-bg-yueye-person': (
        'FACT', 'DISPUTED',
        '家眷在鄜州、身在贼占长安为鹤注与新唐书一致；「如何陷在长安」两《唐书》矛盾（新唐书：为贼所得／旧唐书：宵遁赴行在拜右拾遗），不裁决。'),
}
CITATIONS = [
    # (claim, source, locator, excerpt)
    ('claim-bg-yueye-scene', 'source-dushi-xiangzhu',
     '卷四·月夜·杜臆语（{{SK anchor|}}、{{SK notes|}} 为四库本录入标记，照登）',
     DUYI),
    ('claim-bg-yueye-city', 'source-zizhi-tongjian-events',
     '通鑑卷二百十八·唐紀三十四（至德元載=756，由年表換算）；搜捕句與大擾句以「……」相連',
     join(TJC1, TJC2)),
    ('claim-bg-yueye-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百十七起點＋卷二百二十二終點（年標題與紀事句以「……」相連；卷217內年標題作「天寶十四年」不作「載」，照登）',
     join(TJ755Y, TJ755, TJ763Y, TJ763)),
    ('claim-bg-yueye-world', 'source-dushi-xiangzhu',
     '卷四·月夜·鶴注（天寳十五載八月=756，由年表換算；單源注本係年）',
     HE_YY),
    ('claim-bg-yueye-person', 'source-dufu-zhuan-candidate',
     '卷二百一·文藝上·杜甫传（新唐书说：被执一边）',
     V011_XTS),
    ('claim-bg-yueye-person', 'source-jiutangshu-dufu',
     '卷一百九十下·杜甫传（旧唐书说：宵遁一边——与新唐书矛盾，两说并存的另一半证据）',
     V011_JTS),
    ('claim-bg-yueye-person', 'source-dushi-xiangzhu',
     '卷四·月夜·鶴注＋劉後村語（「身在長安家在鄜州」注本依据；伉俪之篤的注家读法；两段以「……」相連）',
     join(HE_YY, LHC)),
]
BG_LINES = {  # 每层绑两行（R11：每个 bg 至少一行；行号存在于 text-work-t300-207-ws 1–8）
    'bg-yueye-scene': (1, 2),
    'bg-yueye-city': (3, 4),
    'bg-yueye-person': (5, 6),
    'bg-yueye-world': (7, 8),
}
BG_AUDIENCE = {'bg-yueye-scene': 'PRIMARY', 'bg-yueye-city': 'JUNIOR',
               'bg-yueye-world': 'SENIOR', 'bg-yueye-person': 'JUNIOR'}
BG_TITLES = {'bg-yueye-scene': '眼前：想象里家人的月亮',
             'bg-yueye-city': '这座城：陷落的长安',
             'bg-yueye-world': '这个天下：打了八年才收京的战事',
             'bg-yueye-person': '这个人：身陷长安、家寄鄜州'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 2 首）；史实句均有逐字引证，分歧与单源均已在正文言明。' for k in BG}


def guard(table, cols, rows, match_expr):
    """UNION SELECT + WHERE NOT EXISTS 守卫（MySQL 5.6 无行构造 INSERT IGNORE 语义可用形态）。
    match_expr 是字面条件（'x.id = t.id' 这种），不做 format——列名每张表不同，
    模板占位符迟早和真实列名打架，第一版就在这里错配过。"""
    sel = '\nUNION ALL\n'.join(
        'SELECT ' + ', '.join(f'{sql_s(r[c])} AS {c}' for c in cols) + ' FROM DUAL'
        for r in rows)
    return (f'INSERT INTO {table} ({", ".join(cols)})\n'
            f'SELECT * FROM (\n{sel}\n) AS t\n'
            f'WHERE NOT EXISTS (SELECT 1 FROM {table} x WHERE {match_expr});')


def build():
    L = []
    A = L.append
    A("""-- V020：《月夜》(work-t300-207) 四层背景 + 系年 + 安史线挂接（阶段 D 第 2 首）。MySQL 5.6.40 兼容。
-- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V003（background 有 body_text）、V004（Audience 词表先例）、V011、V015、V017、V018 已执行
--       —— background_line 绑到 text-work-t300-207-ws，那一行是 V018 插的；缺 V018 本迁移的行会成孤儿。
--
-- 数据源（可复现）：引文由 emit_v020.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，
--   与快照逐字节一致（杜詩詳註四庫本卷四·月夜注条；通鉴217/218/222 与两唐书·杜甫传切片与 V019 共用同一代码路径）。
--   {{SK anchor|}}、{{SK notes|}} 等录入标记照登。
--
-- 做：4 个 BACKGROUND content/claim/background（正文全部带证）+ 14 行逐字引用 + 8 行 background_line
--   （scene→1,2｜city→3,4｜person→5,6｜world→7,8，绑 text-work-t300-207-ws）
--   + 系年断言 claim-yueye-time-756（鹤注单源 → LIKELY）+ written_during 安史之乱挂接（形状同 V017 春望）。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布；不写 review_log；
--   不裁决两《唐书》「为贼所得 vs 宵遁」矛盾——PERSON 层 claim 保持 DISPUTED，两边证据都挂上。
--
-- 诚实边界：
--   * 两《唐书》对杜甫如何陷长安的记载矛盾（新唐书：為賊所得／旧唐书：宵遁赴行在），正文言明、不取独断；
--   * 系年只有鹤注单源（天寳十五載八月），LIKELY 而非 KNOWN，更不是「定论」；
--   * 「家人对月」是诗的想象结构（杜臆语），不是杜甫目击的事实，正文照此写。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;       -- 含 19，不含 20
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-yueye-%';               -- 空
--   SELECT id FROM poetry_text_version WHERE id='text-work-t300-207-ws';    -- 恰 1 行（V018 已执行）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-yueye-%';         -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-207';                                      -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-yueye-person';    -- DISPUTED（两唐书矛盾未裁）
-- 回滚: recovery/V020_rollback.sql（按 id 全枚举反序删除；不动 V018 的任何行）
START TRANSACTION;""")

    A('\n-- ---------- 1. BACKGROUND content identities ----------')
    rows = [{'id': k, 'entity_type': 'BACKGROUND', 'slug': k[3:], 'title': BG_TITLES[k],
             'summary': BG_SUMMARY[k], 'time_precision': 'UNKNOWN'} for k in BG]
    A(guard('poetry_content', ['id', 'entity_type', 'slug', 'title', 'summary', 'time_precision'],
            rows, 'x.id = t.id'))

    A('\n-- ---------- 2. claims（主语是 BACKGROUND content 行，同 V004 的形状：'
      'claim id 与 subject id 是两个东西） ----------')
    crows = [{'id': k, 'subject_id': k.replace('claim-', '', 1), 'property_key': 'context',
              'value_text': v[2], 'claim_kind': v[0], 'certainty': v[1]} for k, v in CLAIMS.items()]
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            crows, 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': k.replace('claim-', '', 1), 'property_key': 'context', 'claim_id': k}
             for k in CLAIMS],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))

    A('\n-- ---------- 3. background rows（一层一段正文；audience 是遗留编写元数据，读者端不用） ----------')
    brows = [{'id': k, 'work_id': 'work-t300-207', 'layer': {'bg-yueye-scene': 'SCENE',
               'bg-yueye-city': 'CITY', 'bg-yueye-world': 'WORLD', 'bg-yueye-person': 'PERSON'}[k],
              'body_text': BG[k], 'audience': BG_AUDIENCE[k], 'claim_id': ''} for k in BG]
    # claim id 与 content id 不同：bg-yueye-scene ← claim-bg-yueye-scene（V004 同款前缀）
    brows = [dict(b, claim_id='claim-' + b['id']) for b in brows]
    A(guard('poetry_background', ['id', 'work_id', 'layer', 'body_text', 'audience', 'claim_id'],
            brows, 'x.id = t.id'))

    A('\n-- ---------- 4. 逐字引文 ----------')
    ci_rows = [{'claim_id': c, 'source_id': s, 'locator': loc, 'excerpt': ex}
               for c, s, loc, ex in CITATIONS]
    L.append('INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(r['claim_id'])} AS claim_id, {sql_s(r['source_id'])} AS source_id, "
        f"{sql_s(r['locator'])} AS locator, {sql_s(r['excerpt'])} AS evidence_excerpt FROM DUAL"
        for r in ci_rows))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_citation x '
             'WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);')

    A('\n-- ---------- 5. background_line（绑 V018 的版本；行号 1–8 都在） ----------')
    bl_rows = [{'background_id': k, 'version_id': 'text-work-t300-207-ws', 'line_seq': n}
               for k, seqs in BG_LINES.items() for n in seqs]
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(r['background_id'])} AS background_id, {sql_s(r['version_id'])} AS version_id, "
        f"{r['line_seq']} AS line_seq FROM DUAL" for r in bl_rows))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A('\n-- ---------- 6. 系年断言（鹤注单源 → LIKELY；758 式第二说：月夜没有，但单源不给 KNOWN） ----------')
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            [{'id': 'claim-yueye-time-756', 'subject_id': 'work-t300-207', 'property_key': 'time.span',
              'value_text': '756..756 (EXACT) 鹤注：天宝十五载八月，自鄜州赴行在为贼所得时在长安（单源注本，换算：天宝十五载=756）',
              'claim_kind': 'FACT', 'certainty': 'LIKELY'}], 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': 'work-t300-207', 'property_key': 'time.span', 'claim_id': 'claim-yueye-time-756'}],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))
    A(f"""INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)
SELECT 'claim-yueye-time-756', 'source-dushi-xiangzhu',
       '卷四·月夜·鶴注（天寳十五載八月=756，由年表換算；單源注本係年，故 LIKELY 不升 KNOWN）',
       {sql_s(HE_YY)}
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_citation
  WHERE claim_id = 'claim-yueye-time-756' AND source_id = 'source-dushi-xiangzhu');""")

    A('\n-- ---------- 7. written_during 安史之乱（形状同 V017 春望；claim 主语=work） ----------')
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            [{'id': 'claim-yueye-in-anshi', 'subject_id': 'work-t300-207', 'property_key': 'event.name',
              'value_text': '安史之亂（755–763）。鶴注係年天寶十五載（756）落在亂期內；「憶長安」與陷城語境為詩內證',
              'claim_kind': 'FACT', 'certainty': 'LIKELY'}], 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': 'work-t300-207', 'property_key': 'event.name', 'claim_id': 'claim-yueye-in-anshi'}],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))
    A("""INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)
SELECT * FROM (
SELECT 'claim-yueye-in-anshi' AS claim_id, 'source-dushi-xiangzhu' AS source_id, '卷四·月夜·鶴注（係年756在亂期內）' AS locator, {HE_YY_Q} AS evidence_excerpt FROM DUAL
UNION ALL
SELECT 'claim-yueye-in-anshi' AS claim_id, 'source-zizhi-tongjian-events' AS source_id, '通鑑卷二百十七·天寶十四年（乙未，公元七五五年）年標題（亂世起点；「……」連反于范陽句）' AS locator, {TJ_Q} AS evidence_excerpt FROM DUAL
) AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_citation x WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);"""
      .replace('{HE_YY_Q}', sql_s(HE_YY)).replace('{TJ_Q}', sql_s(join(TJ755Y, TJ755))))
    A(guard('poetry_relation', ['id', 'subject_id', 'predicate', 'object_id', 'claim_id'],
            [{'id': 'rel-work-t300-207-written-during-anshi', 'subject_id': 'work-t300-207',
              'predicate': 'written_during', 'object_id': 'event-anshi-rebellion',
              'claim_id': 'claim-yueye-in-anshi'}],
            'x.id = t.id OR (x.subject_id = t.subject_id AND x.predicate = t.predicate AND x.object_id = t.object_id)'))

    A("""
-- ---------- 8. 版本账本 ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 20, 'yue-ye background layers (sourced, inserts-only): 4 bg + lines on text-work-t300-207-ws, 756 dating (single-source LIKELY), written_during anshi; Jiu/Xin Tangshu capture contradiction kept DISPUTED'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 20);
COMMIT;""")
    return '\n'.join(L) + '\n'


NEW_IDS = {
    # 只枚举 V020 新插的行。诗本体 work-t300-207 是 V018 的行，回滚绝不删。
    'poetry_content': list(BG),
    'poetry_claim': list(CLAIMS) + ['claim-yueye-time-756', 'claim-yueye-in-anshi'],
    'poetry_background': list(BG),
}


def build_rollback():
    L = ['-- V020 精确回滚：只删 V020 插入的行（id 全枚举）。',
         '-- 注意：poetry_content 只删 4 个 bg-yueye-* 行；work-t300-207 本体是 V018 的行，绝不碰。',
         'START TRANSACTION;']

    def dels(table, col, vals, chunk=40):
        for i in range(0, len(vals), chunk):
            L.append(f'DELETE FROM {table} WHERE {col} IN ('
                     + ', '.join(sql_s(v) for v in vals[i:i + chunk]) + ');')
    cids = NEW_IDS['poetry_claim']
    dels('poetry_claim_selection', 'claim_id', cids)
    dels('poetry_citation', 'claim_id', cids)
    dels('poetry_relation', 'id', ['rel-work-t300-207-written-during-anshi'])
    dels('poetry_background_line', 'background_id', list(BG))
    dels('poetry_background', 'id', list(BG))
    dels('poetry_claim', 'id', cids)
    dels('poetry_content', 'id', list(BG))
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 20;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (HE_YY, DUYI, LHC, TJC1, TJC2, V011_XTS, V011_JTS, TJ755Y, TJ755, TJ763Y, TJ763):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    # 新 id 文档内唯一——必须按表分组：bg-* 同时是 poetry_content 和 poetry_background 的主键
    # （V004 同款设计），跨表同键是规矩不是重复。
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
    # 宽度（work 级 cap 沿用 V018 的真实 DDL：id64/slug120/title200/claim64/locator300/line500）
    for k, v in BG_TITLES.items():
        if len(k) > 64 or len(k[3:]) > 120 or len(v) > 200:
            bad.append(f'content 宽度超限: {k}')
    for c, s, loc, ex in CITATIONS:
        if len(c) > 64 or len(loc) > 300 or len(ex) > 500:
            bad.append(f'citation 宽度超限: {c} ({len(loc)}B/{len(ex)}B)')
    # 幂等守卫覆盖：每条 INSERT INTO poetry_* 的语句体必须带 WHERE NOT EXISTS
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 11 条逐字过审')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
