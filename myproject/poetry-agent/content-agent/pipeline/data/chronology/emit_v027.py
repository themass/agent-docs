#!/usr/bin/env python3
"""阶段 D 第 9 首：生成 V027——杜甫《登岳陽樓》(work-t300-231, V018 已立) 四层背景。

系年形状与 V023《宿府》/V024《登樓》同类且更硬：**注本与两史各给一个对不上的窗口**——
  * 仇注《杜詩詳註》卷三–五快照实测无此诗（卷三/四/五连「岳陽」二字都无——本迁移头注可复核）；
  * 《舊唐書》本传的叙事顺序把整个江湘之-end 放在「永泰二年」（766）啗牛肉白酒而卒；
  * 《新唐書》本传却把「出瞿唐，下江陵，溯沅、湘以登衡山」系于「大曆中」（766–779）。
两史同记江湘行舟、客耒陽、卒耒陽年五十九（事同），年份却互相打架——所以 time.span 与
written_during 一个都不造（两个窗口都在安史乱事 763 收场**之后**，挂 written_during 是错的），
年份两窗口并列进 PERSON 层正文。

这首的另一特点：ws 诗页快照**实测无页内异文**（无 {{另|}} 标记，八句与 V018 入库正文全同）——
没有异文也如实写明，防止「没登记＝没核过」的误读。

WORLD 层把「戎馬關山北」逐字对年：通鑑卷224 大曆三年（768）「吐蕃眾數萬圍靈州……京師戒嚴」、
大曆五年（770）「湖南兵馬使臧玠殺觀察使崔灌」——前者正是「關山北」之戎馬，後者是他在
湖南漂泊的终点之乱。

用法: python3 -I emit_v027.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/登岳陽樓__杜甫_.txt').read_text(encoding='utf-8')
V233 = pathlib.Path('/tmp/src-dl/quantangshi/vol233.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷201.txt').read_text(encoding='utf-8')
TJ224 = pathlib.Path('/tmp/src-dl/tongjian/tj-224.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；锚不唯一即中止） ----------
WS_L12 = slice_between(WS, '昔聞洞庭水，今上岳陽樓。', '昔聞洞庭水，今上岳陽樓。', 'ws起二句')
WS_L34 = slice_between(WS, '吳楚東南坼，乾坤日夜浮。', '吳楚東南坼，乾坤日夜浮。', 'ws三四句')
WS_L78 = slice_between(WS, '戎馬關山北，憑軒涕泗流。', '戎馬關山北，憑軒涕泗流。', 'ws末二句')
WS_HDR = slice_between(WS, '| title    = 登岳陽樓\n| section  =\n| author   = 杜甫',
                       '| author   = 杜甫', 'ws header title+author')
V233_NOTE = slice_between(V233, "'''杜甫'''", "'''杜甫'''", 'vol233 卷首作者注')
V233_ANCHOR = slice_between(V233, '==[[登岳陽樓 (杜甫)|登岳陽樓]]==', '{{:登岳陽樓 (杜甫)}}',
                            'vol233 锚点+转引用桩')
JTS_RIVER = slice_between(JTS, '甫以其家避亂荊、楚，扁舟下峽', '寓居耒陽。', '旧唐书江湘行舟段')
JTS_DEATH = slice_between(JTS, '永泰二年，啗牛肉白酒', '時年五十九。', '旧唐书耒阳卒(窗口一 766)')
XTS_RIVER = slice_between(XTS, '大曆中，出瞿唐，下江陵，溯沅、湘以登衡山，因客耒陽。',
                          '因客耒陽。', '新唐书大历中江湘段(窗口二 大历)')
XTS_DEATH = slice_between(XTS, '令嘗饋牛炙白酒，大醉，一昔卒，年五十九。',
                          '年五十九。', '新唐书耒阳卒')
TJ768Y = slice_between(TJ224, '代宗睿文孝武皇帝中之上大曆三年（戊申，公元七六八年）',
                       '公元七六八年）', '通鉴224卷768年标题')
TJ_LZ = slice_between(TJ224, '九月，吐蕃眾數萬圍靈州', '京師戒嚴。', '通鉴吐蕃围灵州京师戒严768')
TJ770Y = slice_between(TJ224, '代宗睿文孝武皇帝中之上大曆五年（庚戌，公元七七零年）',
                       '公元七七零年）', '通鉴224卷770年标题')
TJ_ZJ = slice_between(TJ224, '夏，四月，庚子，湖南兵馬使臧玠殺觀察使崔灌',
                      '取賂而還。', '通鉴臧玠杀崔灌770')

BG = {
    'bg-yy-scene': (
        '这一次是登临，而且登临本身就是诗眼：「昔聞洞庭水，今上岳陽樓。」——'
        '听说洞庭很多年了，今天才站上来；一「昔」一「今」之间隔着一生。\n'
        '哪年上的楼，要靠年谱——本地注本实测不覆盖此诗，两唐书给出的年份还互相打架（见第 7、8 句那层），'
        '所以这里只说诗本文写得出的东西：一个久闻而迟登的人，把湖看进了诗里。'),
    'bg-yy-city': (
        '水比楼大：「吳楚東南坼，乾坤日夜浮。」——吴楚之地在东南裂开，天地日月在水上浮动；'
        '这是站在岳阳城头看洞庭的字面。楼的来历、湖的建制，注本核不到（本地快照实测无此诗），不补。\n'
        '可核到的是他到这条水路上的路：《舊唐書》本传「扁舟下峽……泝沿湘流」，《新唐書》'
        '「出瞿唐，下江陵，溯沅、湘以登衡山」——两传同记这一程江湘舟行；'
        '岳阳正在下峡与溯沅湘之间的水路上。洞庭是他晚年的路过的地界，这由两传各自的原文说得定。'),
    'bg-yy-world': (
        '「戎馬關山北」在通鑑里有对应的年月：大曆三年（戊申，公元七六八年）「九月，吐蕃眾數萬圍靈州，'
        '游騎至潘原、宜祿……京師戒嚴」——关山以北，京师的戒严令一年里贴了又揭。\n'
        '而在他自己停舟的湖南，通鑑大曆五年（庚戌，公元七七零年）记「夏，四月，庚子，'
        '湖南兵馬使臧玠殺觀察使崔灌；澧州刺史楊子琳起兵討之，取賂而還」——'
        '乱事按史书算收了场，兵变却在湖广的衙门里接着发生。北望是戎马，舟下是兵变：'
        '凭轩所涕，通鑑同卷里两页都有得对。'),
    'bg-yy-person': (
        '这首诗系于何年，本地核不实——两个窗口各出自一史，逐字可指，却互不相容：\n'
        '窗口一：《舊唐書》本传的叙事里，江湘行舟之后接「永泰二年，啗牛肉白酒，一夕而卒於耒陽，'
        '時年五十九」——照旧传的笔序，这一程与卒都在 766。\n'
        '窗口二：《新唐書》本传「大曆中，出瞿唐，下江陵，溯沅、湘以登衡山，因客耒陽」——'
        '江湘之程整个放进大曆（766–779），卒亦在其后。\n'
        '通行年谱系此诗于大曆三年（768），落在窗口二之内，但年谱本地核不到，不采信。\n'
        '两传可核而不打架的部分：扁舟下峡、溯沅湘、客耒陽、卒于耒陽、年五十九。'
        '年号各说，正文并列——一首诗收在「憑軒涕泗流」上，它的年份本身就是晚唐漂泊的一部分。'),
}
CLAIMS = {
    'claim-bg-yy-scene': (
        'INTERPRETATION', 'LIKELY',
        '迟登之叹为诗本文内证（起联昔闻/今上对举）；年份注本实测不覆盖且两史窗口互斥，正文并列，已声明边界。'),
    'claim-bg-yy-city': (
        'FACT', 'LIKELY',
        '江湘舟行两传各记一段（扁舟下峽/溯沅湘），岳阳在其间水路上为字面所及；'
        '楼名建制注本核不到，正文零注家引用。'),
    'claim-bg-yy-world': (
        'FACT', 'LIKELY',
        '768 吐蕃围灵州京师戒严、770 臧玠杀崔灌均有通鉴卷224 逐字（年标题分记）；'
        '戎马/兵变与凭轩之涕的对应是读法，正文标明。'),
    'claim-bg-yy-person': (
        'FACT', 'KNOWN',
        '晚年江湘行舟、客耒陽、卒耒陽年五十九——两唐书各记一段，事同而年号互异，'
        '不矛盾部分（行舟/耒阳/五十九）升 KNOWN（V016 两史标准）；'
        'certainty 不覆盖系年——旧传笔序指向 766、新传系大曆中，两窗口并列不裁决。'),
}
CITATIONS = [
    ('claim-bg-yy-scene', 'source-ws-t300-231',
     '页面 登岳陽樓 (杜甫)（起二句逐字；页内实测无 {{另|}} 异文标记，八句与 V018 入库正文全同；'
     '全文见 V018 claim-t300-231-text 引文）',
     WS_L12),
    ('claim-bg-yy-city', 'source-ws-t300-231',
     '页面 登岳陽樓 (杜甫)（三四句逐字——洞庭水势为诗本文）',
     WS_L34),
    ('claim-bg-yy-city', 'source-jiutangshu-dufu',
     '卷一百九十下·杜甫传（江湘行舟段：避乱荆楚—扁舟下峡—江陵乱—溯沿湘流—游衡山—寓居耒阳，'
     '连续原文；窗口一系年语境）',
     JTS_RIVER),
    ('claim-bg-yy-city', 'source-xintangshu-wenyi',
     '卷二百一·文藝上·杜甫传（窗口二「大曆中」江湘段）',
     XTS_RIVER),
    ('claim-bg-yy-world', 'source-ws-t300-231',
     '页面 登岳陽樓 (杜甫)（末二句逐字——「戎馬關山北」即本层对年的诗眼，通鑑两段所对）',
     WS_L78),
    ('claim-bg-yy-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十四·大曆三年標題+吐蕃圍靈州京師戒嚴段＋大曆五年標題+臧玠殺崔灌条；'
     '四段以「……」相連，年標題歸屬已分記',
     join(TJ768Y, TJ_LZ, TJ770Y, TJ_ZJ)),
    ('claim-bg-yy-person', 'source-ws-t300-231',
     '页面 登岳陽樓 (杜甫)（header title+author 字段逐字——署名与组诗归属同 V025/V026 路数）',
     WS_HDR),
    ('claim-bg-yy-person', 'source-quantangshi-233',
     '页面 全唐詩/卷233（卷首 notes 作者注＋本诗锚点与转引用桩 {{:登岳陽樓 (杜甫)}}；'
     '卷页无正文，正文证据在诗页——同 V022/V025/V026 桩教训，定位已分记）',
     join(V233_NOTE, V233_ANCHOR)),
    ('claim-bg-yy-person', 'source-jiutangshu-dufu',
     '卷一百九十下·杜甫传（行舟段＋永泰二年耒阳卒句——窗口一 766 的出处；两段以「……」相連）',
     join(JTS_RIVER, JTS_DEATH)),
    ('claim-bg-yy-person', 'source-xintangshu-wenyi',
     '卷二百一·文藝上·杜甫传（大曆中江湘段＋耒阳卒句——窗口二的出处；两段以「……」相連）',
     join(XTS_RIVER, XTS_DEATH)),
]
BG_LINES = {'bg-yy-scene': (1, 2), 'bg-yy-city': (3, 4),
            'bg-yy-world': (5, 6), 'bg-yy-person': (7, 8)}
BG_AUDIENCE = {'bg-yy-scene': 'PRIMARY', 'bg-yy-city': 'JUNIOR',
               'bg-yy-world': 'SENIOR', 'bg-yy-person': 'JUNIOR'}
BG_TITLES = {'bg-yy-scene': '眼前：听说了很多年才站上的楼',
             'bg-yy-city': '这段水：扁舟下峡与溯沅湘之间',
             'bg-yy-world': '这个天下：京师戒严那年、兵变那年',
             'bg-yy-person': '这个人：两史各给一个年份，都不采信'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 9 首）；史实句均有逐字引证；'
                 '系年两窗口并列（旧传 766／新传大曆中），不铸 time.span 不挂乱事线。' for k in BG}


def guard(table, cols, rows, match_expr):
    def lit(v):
        return 'NULL' if v is None else sql_s(v)
    sel = '\nUNION ALL\n'.join(
        'SELECT ' + ', '.join(f'{lit(r[c])} AS {c}' for c in cols) + ' FROM DUAL'
        for r in rows)
    return (f'INSERT INTO {table} ({", ".join(cols)})\n'
            f'SELECT * FROM (\n{sel}\n) AS t\n'
            f'WHERE NOT EXISTS (SELECT 1 FROM {table} x WHERE {match_expr});')


def build():
    L = []
    A = L.append
    A("""-- V027：杜甫《登岳陽樓》(work-t300-231) 四层背景（阶段 D 第 9 首）。MySQL 5.6.40 兼容。
-- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V018 已执行（work-t300-231 与其 text-work-t300-231-ws、source-ws-t300-231
--       都是 V018 的行；source-jiutangshu-dufu 是 V010/V011 的行；source-xintangshu-wenyi 是 V016 的行；
--       source-zizhi-tongjian-events 是 V015 的行——本迁移在同一通鉴来源上增引卷224，不另开行）。
--
-- 数据源（可复现）：emit_v027.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/登岳陽樓__杜甫_.txt（页内实测无 {{另|}} 异文——如实写明）、資治通鑑卷224、
--   全唐詩卷233（锚点+转引用桩+卷首作者注）、舊唐書卷190下、新唐書卷201。
--
-- 做：1 个新 source 登记（全唐詩卷233，PENDING——登记不等于核验）+
--   4 BACKGROUND content/claim/background + 10 组逐字引用 +
--   8 行 background_line（scene→1,2｜city→3,4｜world→5,6｜person→7,8，绑 text-work-t300-231-ws）。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不铸 time.span、不挂 written_during**——见下。
--
-- 诚实边界（这首的边界就是形状本身，同 V023/V024）：
--   * 系年两窗口互斥：旧唐书笔序指向永泰二年（766），新唐书系「大曆中」（766–779），
--     通行年谱（768）本地核不到不采信——time.span 与 written_during 一个都不造；
--     且两窗口都在安史乱事收场（763）之后，挂 written_during 是**肯定错的**，不是弃权；
--   * 注本不覆盖：《杜詩詳註》卷三–五快照实测连「岳陽」二字都没有（qss-卷03/04/05 grep 复核）；
--   * 楼名建制、洞庭建制零注家引用，正文不补；
--   * 页内异文实测无（ws 快照八句与 V018 入库正文全同）——没有异文也登记为「核过」；
--   * person 层 KNOWN 只覆盖两传事同年异的不矛盾部分（行舟/客耒阳/卒耒阳/年五十九，
--     V016 已按同一标准立过 person-du-fu 的并列卒年断言），不覆盖此诗属哪一窗口。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 26，不含 27
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-yy-%';              -- 空
--   SELECT id FROM poetry_text_version WHERE id='text-work-t300-231-ws';  -- 恰 1 行（V018 已执行）
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-233';     -- 空
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-yy-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-231';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-yy-person';   -- KNOWN
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-231'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
-- 回滚: recovery/V027_rollback.sql（按 id 全枚举删除；不动 V018 的任何行，不动共用通鉴来源行）
START TRANSACTION;""")

    A('\n-- ---------- 0. 来源登记（一律 PENDING：登记不等于核验） ----------')
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            [{'id': 'source-quantangshi-233',
              'title': '《全唐詩》全唐詩/卷233（维基文库录入本）',
              'author': None,
              'edition': '全唐詩/卷233（维基文库《全唐詩》录入本）',
              'url': 'https://zh.wikisource.org/wiki/全唐詩/卷233',
              'rights_note': '维基文库录入本，公有领域古籍。本卷为杜甫大曆间诗卷，卷首 notes 标作者；'
                             '本诗条目只有锚点+转引用桩，正文在诗页。本行由 emit_v027.py 对快照逐字定位。'
                             '核验状态保持 PENDING。',
              'verification_status': 'PENDING', 'source_kind': 'POETRY_COLLECTION',
              'reliability': 'HIGH'}],
            'x.id = t.id'))

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
    brows = [{'id': k, 'work_id': 'work-t300-231',
              'layer': {'bg-yy-scene': 'SCENE', 'bg-yy-city': 'CITY',
                        'bg-yy-world': 'WORLD', 'bg-yy-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-231-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不铸 time.span / 不挂 written_during，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 27, 'du fu deng-yueyang-lou background layers (inserts-only): tongjian ju224 768 Tufan siege of Lingzhou with capital on alert plus 770 rebel assassination of the Hunan observer; both Tang histories carry the late river journey (down the gorges, upstream the Yuan and Xiang, lodging at Leiyang, dead aged 59) but their dating windows are mutually exclusive -- the JTS narrative order implies Yongtai-2 (766) while the XTS dates the journey to Da-li; the received chronology-year 768 is locally unverifiable and NOT adopted: deliberately NO time.span and NO written_during (both windows fall after the 763 end of the rebellion, so hanging written_during would be affirmatively wrong); ws page verified to carry no inline variants for this poem -- recorded as checked-and-clean'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 27);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V027 精确回滚：只删 V027 插入的行（id 全枚举）。work-t300-231 本体是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-dufu/xintangshu-wenyi/tongjian-events）都不删。',
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
    dels('poetry_source', 'id', ['source-quantangshi-233'])
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 27;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (WS_L12, WS_L34, WS_L78, WS_HDR, V233_NOTE, V233_ANCHOR, JTS_RIVER, JTS_DEATH,
              XTS_RIVER, XTS_DEATH, TJ768Y, TJ_LZ, TJ770Y, TJ_ZJ):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    # 有意的形状断言（V023/V024 同款）：只查「值 AS 列名」形状，不查裸词
    for shape in ("'time.span' AS property_key", "'event.name' AS property_key",
                  "'written_during' AS predicate"):
        if shape in sql:
            bad.append(f'V027 有意不造 {shape}，但 SQL 里出现了')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 14 切片逐字过审；'
              f'time.span/event.name/written_during 缺席已断言；10 组 citation 宽度过审')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
