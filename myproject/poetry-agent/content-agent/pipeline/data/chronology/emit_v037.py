#!/usr/bin/env python3
"""阶段 D 第 18 首：生成 V037——王维《送別》(work-t300-054, V018 已立) 四层背景。

「为什么写」第十次成立：这首诗的「为什么」整个装在诗里——「君言不得意，歸臥南山陲」，
落第/失意者归山，是唐诗三百首里最少字的一则失意档案。本地史料能接住的：
**王維与孟浩然，一第一不第的两条路**——新传王维「開元初，擢進士」，
旧传孟浩然「年四十來遊京師，應進士不第，還……不逹而卒」（孟传旧传侧全文只有 63 字，
全部逐字入证）。「不得意」三字于是有了同时代的重量。

PERSON 层两源合龙：王维鳏居——旧传「妻亡不再娶，三十年孤居一室，屏絶塵累」/
新传「喪妻不娶，孤居三十年」，两源独立一致升 KNOWN；KNOWN 共两处（鳏居+世界层
一第一不第两传各自直书，见 CLAIMS）。

系年第十二次判决：**全缺席，原因「送别诗无系事，两传不系年」**。
被送者连姓名都没有（诗题只作「送別」，ws 页与全唐诗卷125 的消歧也只到首句
「(下馬飲君酒)」）——无名可查，无年可锚。time.span/event.name/written_during
零铸造 + 零 relation。

六句第三形制：8 行=每层 2、4 行=每层 1，六句诗两者都不是——本首用 **2/2/1/1**
（scene→1-2 city→3-4 world→5 person→6），audit 按此精确形状断言。

简繁页形差异登记（非异文）：ws 页 header title 行作简体「送别」而诗身繁体、
全唐诗卷125 桩作繁体「送別」——是维基文库页面录入形制，不属Witness 间异文，
不开 variants 行；两处引文各按本页原样逐字，locator 声明。
1 个新 source：全唐詩卷125 桩页（noauthor 空——V035/V036 判例，PENDING）。

用法: python3 -I emit_v037.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/送別__下馬飲君酒_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
QT125 = pathlib.Path('/tmp/src-dl/quantangshi/vol125.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_L1 = slice_between(WS, '下馬飲君酒，問君何所之。', '下馬飲君酒，', 'ws第1句(下马饮酒)')
WS_L2 = slice_between(WS, '下馬飲君酒，問君何所之。', '問君何所之。', 'ws第2句(问君何之)')
WS_L3 = slice_between(WS, '君言不得意，歸臥南山陲。', '君言不得意，', 'ws第3句(君言不得意)')
WS_L4 = slice_between(WS, '君言不得意，歸臥南山陲。', '歸臥南山陲。', 'ws第4句(归卧南山陲)')
WS_L5 = slice_between(WS, '但去莫復問，白雲無盡時。', '但去莫復問，', 'ws第5句(但去莫问)')
WS_L6 = slice_between(WS, '但去莫復問，白雲無盡時。', '白雲無盡時。', 'ws第6句(白云无尽)')
# title 行是简体「送别」（页形制，非异文——locator 声明，逐字照录）
WS_TITLE = slice_between(WS, '| title    = 送别', '| title    = 送别', 'ws header title(简体页形+同名消歧)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', 'author   = 王維', 'ws header author(署名直证)')
JTS_YC = slice_between(JTS, '太子中允，乾元中，遷太子中庶子、中書舍人，復拜給事中，轉尚書右丞。',
                       '轉尚書右丞。', '旧传官历段(长安为官——城的锚)')
JTS_MH = slice_between(JTS, '年四十來遊京師，應進士不第，還。', '應進士不第，還。',
                       '旧传孟浩然段一(四十入京/不第而还——世界层不第线)')
JTS_MH2 = slice_between(JTS, '襄陽張九齡鎮荆州，署為從事，與之唱和，不逹而卒。', '不逹而卒。',
                        '旧传孟浩然段二(九龄辟从事/唱和/不达而卒——不第线的收口)')
XTS_ZL = slice_between(XTS, '開元初，擢進士，調太樂丞，坐累為濟州司倉參軍。', '坐累為濟州司倉參軍。',
                       '新传王维段(开元初擢进士——世界层及第线)')
JTS_QI = slice_between(JTS, '妻亡不再娶，三十年孤居一室，屏絶塵累。', '屏絶塵累。',
                       '旧传鳏居段(不再娶/孤居一室——两源合龙第一源)')
XTS_QI = slice_between(XTS, '喪妻不娶，孤居三十年。', '孤居三十年。', '新传鳏居段(两源合龙第二源)')
QT_STUB = slice_between(QT125, '==[[送別 (下馬飲君酒)|送別]]==\n{{:送別 (下馬飲君酒)}}',
                        '{{:送別 (下馬飲君酒)}}', '全唐诗卷125本诗条目(锚点+消歧转引用桩——卷页无正文)')

# 传区间归属复验（V036 立规：切片必须落在本人传区间内）
_jw = JTS.find('=王維='); _jw_e = JTS.find('=李白=')
_jm = JTS.find('=孟浩然='); _jm_e = JTS.find('=元德秀=')
_xw = XTS.find('　　王維，字摩詰'); _xw_e = XTS.find('==鄭虔==')
for _s, _r, _src, _tag in [
        (JTS_YC, (_jw, _jw_e), JTS, 'JTS_YC'), (JTS_QI, (_jw, _jw_e), JTS, 'JTS_QI'),
        (JTS_MH, (_jm, _jm_e), JTS, 'JTS_MH'), (JTS_MH2, (_jm, _jm_e), JTS, 'JTS_MH2'),
        (XTS_ZL, (_xw, _xw_e), XTS, 'XTS_ZL'), (XTS_QI, (_xw, _xw_e), XTS, 'XTS_QI')]:
    if not (_r[0] <= _src.find(_s) <= _r[1]):
        raise SystemExit(f'切片越出传区间：{_tag}——修订后重生成')

BG = {
    'bg-sb-scene': (
        '这场送别从一杯酒开始：「下馬飲君酒，問君何所之」——下马，请你喝一杯，'
        '问你去哪儿。全唐诗三百首里的送别，这是最短的一道档案：没有地名，'
        '没有天气，没有流泪。\n'
        '本传给不了这场酒——两传写王维，一条也没提到他给人饯行。'
        '被送的人史料里也不存在（见 CITY 层）。所以这场酒的证据只有诗本身二十个字：'
        '下马、举杯、问一句。别的都是我们想加的。'),
    'bg-sb-city': (
        '这座城在诗里只露一个方向：「歸臥南山陲」——你要回终南山脚下睡去了。'
        '饯别的城按王维的官历应在长安（旧传「轉尚書右丞」——右丞是长安的官），'
        '但诗连长安二字都没给；南山是实指还是泛指，本地史料无法裁决——'
        '王维自己的别业在蓝田辋口（V035 已立），与终南山同一条山带，'
        '这最多说明「南山」在他嘴里不会是无的放矢。\n'
        '被送者是谁：诗题只作「送別」（ws 页与全唐诗卷125 的消歧都只到首句'
        '「(下馬飲君酒)」）——姓名不入史料，我们就不发明。无名，无城，'
        '只有「歸臥」的方向感。'),
    'bg-sb-world': (
        '「但去莫復問」——去吧，不必再问了。这五个字的重量，来自那个时代'
        '人人都懂的半句话：「君言不得意」。不得意是什么？本地史料给了同时代的两条路：\n'
        '旧唐书孟浩然传全文只有六十三字，字字都在说这条路的难：'
        '「年四十來遊京師，應進士不第，還」——四十岁进京，落第，回去；'
        '「襄陽張九齡鎮荆州，署為從事，與之唱和，不逹而卒」——宰相旧友给他一份幕职，'
        '最后还是「不达而卒」。旧史连安慰都懒得写。\n'
        '另一条路在新唐书王维传里：「開元初，擢進士」——同一时代，'
        '有人一第入仕，有人四十落第。送别的酒桌上站着的是第二条路的人：'
        '「不得意」不需要解释，因为满朝都是听懂的人。'),
    'bg-sb-person': (
        '「白雲無盡時」——山里的白云没有尽头。写这五个字的人，'
        '两唐书在同一个事实上合了龙：旧传「妻亡不再娶，三十年孤居一室，屏絶塵累」，'
        '新传「喪妻不娶，孤居三十年」——妻子死后不再娶，一个人住了三十年，'
        '断绝尘世牵累。两源独立一致，这一处升 KNOWN：'
        '写「白云无尽」的王维，自己就是无家可归去的人。\n'
        '所以这首送别的读法整个反了过来：送的人比被送的更「归卧」——'
        '朋友回南山，是「不得意」的退路；王维的孤居一室，早就是他的常态。'
        '「但去莫復問」因此不是洒脱，是同类认出了同类：你的路我懂，别解释了。\n'
        '旧传官历（太子中允→中庶子→中书舍人→给事中→右丞）与新传官历清单不同——'
        '两传做官履历各说各话，照登不裁决，与 V035 辋川段同款处理。'),
}
CLAIMS = {
    'claim-bg-sb-scene': (
        'FACT', 'LIKELY',
        '下马/饮酒/问所之全诗本文；送别场景之外零外推（两传无一字涉饯行）；'
        '被送者无名——诗题与卷125 消歧均只到首句，不发明受赠人。'),
    'claim-bg-sb-city': (
        'FACT', 'LIKELY',
        '饯地在长安=由旧传右丞官历推定（推定非直载，LIKELY）；'
        '南山实指泛指南本地无法裁决（辋川别业同山带仅作旁注）；'
        '无名无城——两源桩页逐字支持「消歧只到首句」。'),
    'claim-bg-sb-world': (
        'FACT', 'KNOWN',
        '一第一不第两条路两传各自直书：孟浩然「應進士不第」段与王维「開元初擢進士」段'
        '各自单源逐字（事件直书，V028 判例升 KNOWN）；此 KNOWN 只覆盖两条履历本身，'
        '**不外溢到诗**：被送者非孟浩然（无任何史料连线，明说）→'
        '诗 time.span/event.name/written_during 零铸造、零 relation。'),
    'claim-bg-sb-person': (
        'FACT', 'KNOWN',
        'KNOWN 一处：王维鳏居孤处三十年——旧传「不再娶/孤居一室/屏絶塵累」与'
        '新传「喪妻不娶/孤居三十年」两源独立一致；两传官历清单不同——并列不裁决；'
        'certainty 不覆盖任何系年与受赠人身份。'),
}
CITATIONS = [
    ('claim-bg-sb-scene', 'source-ws-t300-054',
     '页面 送別（header title+author 两字段+第1、2句，四段以「……」相連——'
     '**title 行简体「送别」而诗身繁体，为维基文库页形制非 Witness 异文，逐字照录**；'
     '页内实测无 {{另|}} 异文，「查过、干净」；同名组诗消歧靠首句；'
     '全文另见 V018 claim-t300-054-text 引文）',
     join(WS_TITLE, WS_AUTHOR, WS_L1, WS_L2)),
    ('claim-bg-sb-city', 'source-ws-t300-054',
     '页面 送別（第3、4句逐字——「南山陲」是城层唯一的诗内方位）',
     join(WS_L3, WS_L4)),
    ('claim-bg-sb-city', 'source-quantangshi-125',
     '页面 全唐詩/卷125（本诗锚点+消歧转引用桩 {{:送別 (下馬飲君酒)}}——'
     '卷页繁体「送別」与 ws 页 title 行简体「送别」各按本页原样；'
     '卷首 Collection header 的 noauthor 字段为空——卷页无作者标注、无正文，'
     '正文证据在诗页；同 V022/V025–V036 桩教训）',
     QT_STUB),
    ('claim-bg-sb-city', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传官历段（太子中允至尚書右丞——右丞为长安官，'
     '饯地在长安由此推定；两传官历清单不同，另侧见新传引文）', JTS_YC),
    ('claim-bg-sb-world', 'source-ws-t300-054',
     '页面 送別（第5句逐字——「但去莫復問」与下方两条履历并读）', WS_L5),
    ('claim-bg-sb-world', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·孟浩然传（年四十來遊京師，應進士不第，還——'
     '旧传孟传侧全部家底六十三字中的两段，逐字全收；不第线直书）',
     join(JTS_MH, JTS_MH2)),
    ('claim-bg-sb-world', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王维传首段（開元初擢進士——及第线直书，'
     '与旧传孟浩然段并读成一第一不第之两路）', XTS_ZL),
    ('claim-bg-sb-person', 'source-ws-t300-054',
     '页面 送別（第6句逐字——「白雲無盡時」与下方鳏居两源合龙对读）', WS_L6),
    ('claim-bg-sb-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传鳏居段（妻亡不再娶/三十年孤居一室/屏絶塵累——'
     '两源合龙第一源）', JTS_QI),
    ('claim-bg-sb-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王维传鳏居段（喪妻不娶/孤居三十年——两源合龙第二源；'
     '措辞各自逐字，孤居年数两源一致）', XTS_QI),
]
BG_LINES = {'bg-sb-scene': (1, 2), 'bg-sb-city': (3, 4), 'bg-sb-world': (5,), 'bg-sb-person': (6,)}
BG_AUDIENCE = {'bg-sb-scene': 'PRIMARY', 'bg-sb-city': 'JUNIOR',
               'bg-sb-world': 'SENIOR', 'bg-sb-person': 'PRIMARY'}
BG_TITLES = {'bg-sb-scene': '眼前：一杯酒的档案',
             'bg-sb-city': '这座城：只有归卧的方向',
             'bg-sb-world': '这个天下：一第与不第',
             'bg-sb-person': '这个人：无家可归的人送还乡的人'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 18 首·六句第三形制 2/2/1/1）；史实句均有逐字引证；'
                 'background_line 六句形制：scene→1-2 city→3-4 world→5 person→6；'
                 '送别诗无系事+两传不系年→time.span/event.name/written_during 全缺席、'
                 '零 relation；KNOWN 两处：一第一不第两履历直书（不外溢）+鳏居（两源合龙）；'
                 '受赠人无名不发明；ws title 简体页形制声明不裁异文。' for k in BG}


def guard(table, cols, rows, match_expr):
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


def build():
    L = []
    A = L.append
    A("""-- V037：王维《送別》(work-t300-054) 四层背景（阶段 D 第 18 首·六句第三形制）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-054 与其 text-work-t300-054-ws、
--       source-ws-t300-054 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行——不另开行）。本迁移另开 1 个 source（全唐詩卷125，见下）。
--
-- 数据源（可复现）：emit_v037.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/送別__下馬飲君酒_.txt（页内实测无 {{另}}——「查过、干净」；header title 行
--   简体「送别」诗身繁体——页形制逐字照录并在 locator 声明，不属 Witness 异文不开 variants 行）、
--   舊唐書卷190下（王维传官历段+鳏居段；孟浩然传六十三字全收）、
--   新唐書卷202（王维传擢进士段+鳏居段；切片传区间归属生成时断言）、
--   全唐詩卷125（锚点+消歧转引用桩，noauthor 空——V035/V036 判例）。
--
-- 做：1 个新 source（source-quantangshi-125，PENDING——桩页教训同款）+
--   4 BACKGROUND content/claim/background + 10 组逐字引用（(claim,source) 主键每对恰一行）+
--   6 行 background_line（**六句第三形制 2/2/1/1**：scene→1-2 city→3-4 world→5 person→6，
--   绑 text-work-t300-054-ws 的 6 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「送别诗无系事 + 受赠人无名 + 饯地系推定」）：
--   * 被送者姓名不入任何史料（诗题与两处消歧只到首句）——不发明受赠人；
--   * 饯地=长安系右丞官历推定（LIKELY 非直载）；南山实指泛指不裁决；
--   * 孟浩然「应进士不第」与王维「开元初擢进士」两履历直书升 KNOWN，
--     但**被送者非孟浩然**——无任何史料连线，明说，不外溢；
--   * 鳏居孤处三十年=两传独立一致升 KNOWN；两传官历清单不同并列不裁决；
--   * 系年第十二次判决：送别无系事、两传不系年→零铸造零 relation；
--   * KNOWN 共两处，其余照 LIKELY。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 36，不含 37
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-sb-%';              -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-125';     -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-054-ws';  -- 恰 6（六句）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-sb-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-054';                                  -- 6（2/2/1/1）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-sb-world','claim-bg-sb-person');
--     -- KNOWN / KNOWN（world=两履历直书不外溢；person=鳏居两源合龙）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-sb-scene','claim-bg-sb-city');
--     -- LIKELY / LIKELY
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-054'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-054';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-sb-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V037_rollback.sql（按 id 全枚举删除；不动 V018 的行，不动共用来源行；
--   本迁移自开的 source-quantangshi-125 随回滚删除）
START TRANSACTION;""")

    A('\n-- ---------- 0. 新 source（1 个；桩页如实标注，PENDING 照 V031/V035/V036 判例） ----------')
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            [{'id': 'source-quantangshi-125',
              'title': '《全唐詩》全唐詩/卷125（维基文库录入本）',
              'author': None,
              'edition': '全唐詩/卷125（维基文库《全唐詩》录入本）',
              'url': 'https://zh.wikisource.org/wiki/全唐詩/卷125',
              'rights_note': '维基文库录入本，公有领域古籍。卷首 Collection header 的 noauthor '
                             '字段为空——卷页无作者标注（同卷126/卷164 无标注情形）。本诗条目只有'
                             '锚点+消歧转引用桩（送別 (下馬飲君酒)），正文在诗页。'
                             '本行由 emit_v037.py 对快照逐字定位。核验状态保持 PENDING。',
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
    brows = [{'id': k, 'work_id': 'work-t300-054',
              'layer': {'bg-sb-scene': 'SCENE', 'bg-sb-city': 'CITY',
                        'bg-sb-world': 'WORLD', 'bg-sb-person': 'PERSON'}[k],
              'body_text': BG[k], 'audience': BG_AUDIENCE[k], 'claim_id': 'claim-' + k} for k in BG]
    A(guard('poetry_background', ['id', 'work_id', 'layer', 'body_text', 'audience', 'claim_id'],
            brows, 'x.id = t.id'))

    A('\n-- ---------- 4. 逐字引文（(claim,source) 主键每对恰一行） ----------')
    L.append('INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(c)} AS claim_id, {sql_s(s)} AS source_id, {sql_s(loc)} AS locator, "
        f"{sql_s(ex)} AS evidence_excerpt FROM DUAL"
        for c, s, loc, ex in CITATIONS))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_citation x '
             'WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);')

    A('\n-- ---------- 5. background_line（六句第三形制：2/2/1/1） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-054-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 37, 'Wang Wei Song-bie (seeing a friend off) background layers (stage-D poem 18, third line-shape: six-line poem 2/2/1/1): the why sits inside the twenty syllables -- jun yan bu-de-yi, gui wo Nan-shan chui (you say you came to nothing; you go home to sleep at the edge of South Mountain); local history supplies the era-weight of those three words via two parallel resumes quoted from two sources: JTS Meng Haoran, forty to the capital, failed the jinshi, went home, and died without advancement (his entire JTS biography is 63 characters, all quoted), XTS Wang Wei, passed the jinshi in early kai-yuan -- two recorded resumes raised KNOWN as annalistic statements but never overflowing to the poem: the farewell guest is NOT Meng Haoran (no source connects them; said plainly); a second KNOWN: Wang Wei widowed and unwed for thirty years, JTS (qi wang bu zai qu...) plus XTS (sang qi bu qu...) two independent sources in agreement -- the man who wrote endless white clouds had no home to go to, which reads the farewell backwards; dating verdict twelve: a farewell poem with no dated event, unnamed guest (title and both disambiguating stubs reach only the first line), no chronology in either history -- time.span/event.name/written_during absent, zero relations; the sending city Chang-an is an inference from the Right Vice Minister post (LIKELY, not stated); South Mountain literal-or-general left unruled; the ws page title line carries the simplified form of the title while the poem body is traditional -- a Wikisource page-shape quirk, not a witness variant: quoted verbatim as-is on each side, declared in the locator, no variants.md row; one new source: quan-tang-shi juan 125 page (anchor plus disambiguated transclusion stub; noauthor empty per V035/V036 precedent, PENDING)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 37);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V037 精确回滚：只删 V037 插入的行（id 全枚举）。',
         '-- work-t300-054 本体、其 text_line 6 行与 source-ws-t300-054 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi）不删；',
         '-- V037 自开的 source-quantangshi-125 随回滚删除；零 relation。',
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
    dels('poetry_source', 'id', ['source-quantangshi-125'])
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 37;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_L1, WS_L2, WS_L3, WS_L4, WS_L5, WS_L6, WS_TITLE, WS_AUTHOR,
              JTS_YC, JTS_MH, JTS_MH2, XTS_ZL, JTS_QI, XTS_QI, QT_STUB]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 鳏居两源合龙断言：两侧关键语各自在场
    p_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-sb-person' and s == 'source-jiutangshu-wenyuan')
    p_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-sb-person' and s == 'source-xintangshu-wenyi')
    if '妻亡不再娶' not in p_jts or '喪妻不娶' not in p_xts:
        bad.append('鳏居两源侧关键语不齐')
    # 一第一不第断言：两侧履历各在其引文
    w_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-sb-world' and s == 'source-jiutangshu-wenyuan')
    w_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-sb-world' and s == 'source-xintangshu-wenyi')
    if '應進士不第' not in w_jts or '開元初，擢進士' not in w_xts:
        bad.append('一第一不第两履历不齐')
    # 六句第三形制：2/2/1/1
    if BG_LINES['bg-sb-scene'] != (1, 2) or BG_LINES['bg-sb-city'] != (3, 4) \
            or BG_LINES['bg-sb-world'] != (5,) or BG_LINES['bg-sb-person'] != (6,):
        bad.append('六句形制必须是 2/2/1/1')
    if len(re.findall(r"text-work-t300-054-ws' AS version_id", sql)) != 6:
        bad.append('bg_line INSERT 的 version 行数应为 6')
    # 简体 title 逐字在场（页形制照录，不许被「修正」成繁体）
    if '| title    = 送别' not in flat:
        bad.append('ws 简体 title 须逐字在场（页形制非异文，不校勘）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V037 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V037 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-054' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V037 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-054' AS subject_id" in sql:
        bad.append('V037 的 claim 主语应全部是 bg-sb-*，work-t300-054 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V037 不碰 poetry_text_line')
    if sql.count('INSERT INTO poetry_source') != 1:
        bad.append('V037 应恰有 1 个 poetry_source INSERT（source-quantangshi-125）')
    if "'source-quantangshi-125' AS id" not in sql:
        bad.append('新 source 应为 source-quantangshi-125')
    if "DELETE FROM poetry_source WHERE id IN ('source-quantangshi-125')" not in build_rollback():
        bad.append('回滚未删除 V037 自开的 source-quantangshi-125')
    # 受赠人不发明的正断言：BG 正文必须含「不发明」声明
    body_all = ''.join(BG.values())
    if '不发明' not in body_all:
        bad.append('BG 正文须含「不发明受赠人」声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 15 切片逐字过审且全部进引文；'
              f'切片传区间归属已生成时复验；鳏居两源合龙断言；一第一不第两履历断言；'
              f'六句 2/2/1/1 形制断言；简体 title 照录断言；(claim,source) 主键 '
              f'{len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；1 新 source+回滚同步断言；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
