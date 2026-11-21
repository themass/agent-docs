#!/usr/bin/env python3
"""阶段 D 第 7 首：生成 V025——岑参《奉和中書舍人賈至早朝大明宮》(work-t300-299, V018 已立) 四层背景。

阶段 D 第一首非杜甫诗——「只打磨唐朝」不是「只打磨杜甫」。候选是机器选出来的：
126 首 V018 诗逐首拿首行对本地《杜詩詳註》卷三–五快照做折叠检索，唯一一首被注本
正文收着的非深挖诗就是这一首（仇注把它作为杜甫奉和的「附岑參詩」整段抄在注里）。

这首的证据形状也是第一次：
  * 注本快照对它的正文收在**杜甫诗条的附段**里（{{SK anchor|和前}}{{SK notes|附岑參詩}}），
    注本对这一组的态度是「合觀四作」——背景层的主体从人换成了**诗会**。
  * 岑参本传本地核不到：旧唐书文苑（卷190 上/中/下）与新唐书文艺（卷201–203）实测
    均无岑参传——PERSON 层只写可核的署名三证与唱和集团，生平不写。
  * 全唐詩卷201 对本诗只有**转引用桩** {{:奉和中書舍人賈至早朝大明宮}}（无正文，同 V022 的
    vol227 教训），但卷首 notes 的作者注 '''岑參''' + 锚点仍在——署名第二证走这里。
  * 系年走注本路线：仇注系年句「此{{YL|乾元元年}}春在諫省作」附在**杜甫**奉和条上
    （唱和同一集会为内证），注本单源，按 V019 鹤注先例给 LIKELY；758 落在 755–763
    乱期内（通鑑卷220 年标题为纪年锚），written_during 挂安史之乱，V022 同款形状。

用法: python3 -I emit_v025.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import (  # noqa: E402  切片器/SQL字面量/共用引文——单一来源
    slice_between, sql_s, join,
)

WS = pathlib.Path('/tmp/src-dl/ws-poems/奉和中書舍人賈至早朝大明宮.txt').read_text(encoding='utf-8')
QSS = pathlib.Path('/tmp/src-dl/qss-卷05.txt').read_text(encoding='utf-8')
TJ220 = pathlib.Path('/tmp/src-dl/tongjian/tj-220.txt').read_text(encoding='utf-8')
V201 = pathlib.Path('/tmp/src-dl/quantangshi/vol201.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；锚不唯一即中止） ----------
WS_L12 = slice_between(WS, '雞鳴紫陌曙光寒，', '鶯囀皇州春{{另|色|欲}}闌。', 'ws起二句(含页内异文色/欲)')
WS_VAR3 = slice_between(WS, '金{{另|闕|鎖}}曉鐘開萬戶，', '金{{另|闕|鎖}}曉鐘開萬戶，', 'ws第三行(页内异文闕/鎖)')
WS_VAR5 = slice_between(WS, '花{{另|迎|明}}劒珮星初落，', '花{{另|迎|明}}劒珮星初落，', 'ws第五行(页内异文迎/明)')
WS_HDR = slice_between(WS, '| title    = 奉和中書舍人賈至早朝大明宮', '| author   = 岑參', 'ws header title+author')
V201_NOTE = slice_between(V201, "'''岑參'''", "'''岑參'''", 'vol201 卷首作者注')
V201_ANCHOR = slice_between(V201, '==[[奉和中書舍人賈至早朝大明宮]]==',
                            '{{:奉和中書舍人賈至早朝大明宮}}', 'vol201 锚点+转引用桩')
QSS_DATING = slice_between(QSS, '{{SK notes|此{{YL|乾元元年}}春在諫省作',
                             '{{SK notes|此{{YL|乾元元年}}春在諫省作', '仇注系年句(附杜甫奉和条)')
QSS_PALACE = slice_between(QSS, '舊唐書東内大明宮在禁苑之東南', '天后改大明殿', '仇注引旧唐书大明宫建置')
QSS_CEN = slice_between(QSS, '雞鳴紫陌曙光寒鶯囀皇州春色{{SK notes|草堂作夜}}闌',
                        '陽春一曲和{{SK notes|去聲}}皆難', '仇注附岑参诗正文(含草堂异读注)')
QSS_FENG = slice_between(QSS, '晉書荀朂傳朂乆在中書', '奪我鳯凰池諸君賀我耶', '仇注引晋书凤池典')
QSS_GROUP = slice_between(QSS, '合觀四作賈首倡殊平平三和俱有奪席之意', '故當推為擅塲', '仇注合观四作评')
QSS_JIA = slice_between(QSS, '{{SK anchor|早朝}}{{SK notes|音潮}}大明宮呈兩省僚友',
                        '{{SK notes|附賈至詩}}', '仇注賈至原唱条标(附賈至詩)')
TJ758Y = slice_between(TJ220, '肅宗文明武德大聖大宣孝皇帝中之下乾元元年（戊戌，公元七五八年）',
                       '肅宗文明武德大聖大宣孝皇帝中之下乾元元年（戊戌，公元七五八年）', '通鉴220卷758年标题')
TJ_AMEND = slice_between(TJ220, '丁未，上御明鳳門，赦天下，改元。', '復以載為年。', '通鉴乾元改元句')

BG = {
    'bg-hz-scene': (
        '这首诗本身就是一场天没亮的朝会。鸡叫了，京路上曙光还寒，莺声把春色啼到将尽，'
        '金阙的晓钟开万户，玉阶前的仙仗拥着千官——全诗八句几乎全是候朝的景物；'
        '题目把来由写得明白：「奉和中書舍人賈至早朝大明宮」，是和人家的「早朝大明宮」。\n'
        '哪座殿、哪一年朝会，要靠注本与史书——这一层只说诗本文写得出的东西：'
        '天未亮而百官已列，诗写的是等待。'),
    'bg-hz-city': (
        '诗里的大明宮、金闕、玉階、仙仗都是朝堂名物，其中那座宫有自己的来历。'
        '仇注在组诗注里引《舊唐書》：「東内大明宮在禁苑之東南，本永安宫，貞觀八年置，'
        '九年改大明宮，龍朔二年號蓬萊宮，咸亨元年改含元宮，尋復大明宮，正殿曰含元殿，'
        '天后改大明殿」（{{YL|}} 录入标记照登于引文）。改名几轮，朝会照旧——'
        '「金闕曉鐘」敲的是这座几经改名的宫。'),
    'bg-hz-world': (
        '这首早朝诗的年份在通鑑里有名有姓：乾元元年（戊戌，公元七五八年）年标题之下，'
        '「丁未，上御明鳳門，赦天下，改元。盡免百姓今載租、庸」——写这首诗的这一开春，'
        '朝廷刚改元乾元。\n'
        '朝会之前，战争刚收复了两京，但收而复来，乱事没完（通鑑卷220 同年连着记两京之外的仗）。'
        '诗里一个字的仗都没有：鸡鸣钟声是太平朝仪——这正是安史乱中早朝诗的张力。'
        '两页并置是读法，通鑑的记事摆在那里。'),
    'bg-hz-person': (
        '岑参的本传本地核不到——旧唐书文苑（卷190上/中/下）、新唐书文艺（卷201–203）'
        '实测都没有他的传。所以这一层说这组诗本身：賈至任中書舍人，作「早朝大明宮呈兩省僚友」'
        '为原唱（附賈至詩），王維、岑参、杜甫各有奉和——王維和作也在《唐詩三百首》里（第 140 首），'
        '賈至原唱与杜甫和作都在《杜詩詳註》的附段里逐字保存。仇注总评四首：'
        '「合觀四作，賈首倡殊平平，三和俱有奪席之意……王岑秀色可攬……故當推為擅塲」——'
        '注家的高下之判是读法，照登不裁决。\n'
        '「獨有鳳皇池上客」说的是賈至：仇注引《晉書》荀朂傳「奪我鳯凰池，諸君賀我耶」，'
        '鳳池是中書省的省称。这首诗的署名有三处互不相犯的记载：维基文库诗页 header 的 '
        'author 字段、《全唐詩》卷201 的卷首作者注、《杜詩詳註》的「附岑參詩」段——'
        '三处同指岑参。署名与唱和集团可核到；岑参这一生，本地核不到，不写。'),
}
CLAIMS = {
    'claim-bg-hz-scene': (
        'INTERPRETATION', 'LIKELY',
        '早朝场景为诗本文内证（题「奉和…早朝大明宮」+通篇候朝景物）；殿名/年份另层给，正文已声明边界。'),
    'claim-bg-hz-city': (
        'FACT', 'LIKELY',
        '大明宫建置沿革为仇注引旧唐书原文（四库本录入快照逐字，{{YL|}} 标记照登）；'
        '属注本转引正史——单链但逐字可指，故 LIKELY 不升 KNOWN。'),
    'claim-bg-hz-world': (
        'FACT', 'LIKELY',
        '乾元元年年标题与改元句有通鉴卷220 逐字（本迁移在同一通鉴来源上增引卷220，'
        '沿用 V017「增引不另开行」规矩）；诗不写乱事与史书战事的并置已标明是读法。'),
    'claim-bg-hz-person': (
        'FACT', 'KNOWN',
        '署名三证（ws header author 字段／全唐詩卷201 作者注／杜詩詳註附岑參詩段）互不矛盾逐字可指，'
        '升 KNOWN；certainty 只覆盖署名与唱和集团（一倡三和四首俱在），不覆盖岑参生平——'
        '两唐书本传实测无岑参，正文已声明。'),
}
CITATIONS = [
    ('claim-bg-hz-scene', 'source-ws-t300-299',
     '页面 奉和中書舍人賈至早朝大明宮（起二句逐字；页内异文标记 {{另|色|欲}} 原样引，'
     '登记 corpus/tang300-variants.md 不裁决；八句全文见 V018 claim-t300-299-text 引文）',
     WS_L12),
    ('claim-bg-hz-scene', 'source-dushi-xiangzhu-05',
     '杜詩詳註卷五（页内另两对页内异文的注本对应：第三行「闕/鎖」仇注无注、'
     '第五行「迎/明」仇注无注——此条只登草堂异读所系处）',
     join(WS_VAR3, WS_VAR5)),
    ('claim-bg-hz-city', 'source-dushi-xiangzhu-05',
     '杜詩詳註卷五·組詩注条（引「舊唐書」大明宫建置；{{YL|}} 标记照登）',
     QSS_PALACE),
    ('claim-bg-hz-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十·乾元元年（戊戌，公元七五八年）年標題＋二月改元句'
     '（本迁移在同一通鉴来源上增引卷220，沿用 V017 增引卷218 的「不另开来源行」规矩）',
     join(TJ758Y, TJ_AMEND)),
    ('claim-bg-hz-person', 'source-ws-t300-299',
     '页面 奉和中書舍人賈至早朝大明宮（header title+author 字段逐字）',
     WS_HDR),
    ('claim-bg-hz-person', 'source-quantangshi-201',
     '页面 全唐詩/卷201（卷首 notes 作者注＋本诗锚点与转引用桩 {{:…}}；'
     '卷页无正文，正文证据在诗页——同 V022 卷227 桩教训，定位已分记）',
     join(V201_NOTE, V201_ANCHOR)),
    ('claim-bg-hz-person', 'source-dushi-xiangzhu-05',
     '杜詩詳註卷五·杜甫奉和条「附岑參詩」正文段＋賈至原唱条标（早朝…呈兩省僚友＋附賈至詩）＋'
     '杜甫和詩注条引晉書凤池典＋組詩总评「合觀四作」段；四段以「……」相連，各段归属已在定位分記',
     join(QSS_CEN, QSS_JIA, QSS_FENG, QSS_GROUP)),
    ('claim-hz-time-758', 'source-dushi-xiangzhu-05',
     '杜詩詳註卷五·杜甫奉和条注系年句（「此乾元元年春在諫省作」附在杜甫奉和条上，'
     '非岑参诗条原文——唱和同一集会为内证，注本单源）',
     QSS_DATING),
    ('claim-hz-in-anshi', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十·乾元元年（戊戌，公元七五八年）年標題（758 在 755–763 乱期内的纪年锚）',
     TJ758Y),
]
BG_LINES = {'bg-hz-scene': (1, 2), 'bg-hz-city': (3, 4),
            'bg-hz-world': (5, 6), 'bg-hz-person': (7, 8)}
BG_AUDIENCE = {'bg-hz-scene': 'PRIMARY', 'bg-hz-city': 'JUNIOR',
               'bg-hz-world': 'SENIOR', 'bg-hz-person': 'JUNIOR'}
BG_TITLES = {'bg-hz-scene': '眼前：天没亮的那场朝会',
             'bg-hz-city': '这座宫：改了几轮名的明宫',
             'bg-hz-world': '这个年号：刚改元乾元的那年春天',
             'bg-hz-person': '这组诗：一倡三和与推不出的高下'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 7 首·第一首非杜甫）；史实句均有逐字引证；'
                 '系年依仇注（附杜甫条）给 LIKELY；岑参本传两唐书实测无传，写成边界。' for k in BG}
TIME_VALUE = ('758..758 (EXACT) 乾元元年春说：仇注系年句「此乾元元年春在諫省作」'
              '附于杜甫同组和作（唱和同一集会为内证）+通鉴卷220 年标题为纪年锚；'
              '注本单源合推，非年谱原文——同 V019 鹤注先例给 LIKELY')
ANSHI_VALUE = ('安史之亂（755–763）。係年758在亂期內（通鑑卷220 乾元元年標題）；'
               '此诗是乱中朝廷的早朝声景，诗本文不写战事')


def guard(table, cols, rows, match_expr):
    # None → 裸 NULL（V018 source 行同款）；其余走 sql_s 双写转义
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
    A("""-- V025：岑参《奉和中書舍人賈至早朝大明宮》(work-t300-299) 四层背景（阶段 D 第 7 首）。MySQL 5.6.40 兼容。
-- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V015、V017、V018 已执行（work-t300-299 与其 text-work-t300-299-ws 都是 V018 的行；
--       source-zizhi-tongjian-events 是 V015 的行（V017 已增引卷218，本迁移增引卷220）；
--       event-anshi-rebellion 是 V004/V015 的行）。
--
-- 数据源（可复现）：emit_v025.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/奉和中書舍人賈至早朝大明宮.txt（页内 {{另|}} 异文标记照登）、
--   杜詩詳註(四庫全書本)卷05（注本正文——本诗以「附岑參詩」收在杜甫条内）、
--   資治通鑑卷220、全唐詩卷201（锚点+转引用桩+卷首作者注）。
--
-- 做：2 个新 source 登记（杜詩詳註卷五／全唐詩卷201，一律 PENDING——登记不等于核验）+
--   4 BACKGROUND content/claim/background + 9 组逐字引用 + 系年 claim（time.span LIKELY）+
--   written_during 安史挂接 + 8 行 background_line（scene→1,2｜city→3,4｜world→5,6｜person→7,8，
--   绑 text-work-t300-299-ws）。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log。
--
-- 诚实边界：
--   * 系年为注本单源：仇注系年句附在**杜甫**奉和条（「此{{YL|乾元元年}}春在諫省作」），
--     岑参诗条本身无系年——唱和同一集会为内证，合推 LIKELY（V019 鹤注先例）；
--   * 岑参本传本地核不到：两唐书文苑/文艺实测无传；PERSON 层只写署名三证与唱和集团，
--     KNOWN 不覆盖生平；
--   * 全唐詩卷201 对本诗只有锚点+转引用桩（无正文）——署名第二证走卷首作者注；
--   * 页内异文 色/欲、闕/鎖、迎/明 只登记（tang300-variants.md）；草堂本「春色夜闌」
--     为注本别出异读，照登不裁决；
--   * 仇注「合觀四作」高下之判是注家读法，照登不裁决。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 24，不含 25
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-hz-%';              -- 空
--   SELECT id FROM poetry_text_version WHERE id='text-work-t300-299-ws';  -- 恰 1 行（V018 已执行）
--   SELECT id FROM poetry_source WHERE id IN ('source-dushi-xiangzhu-05','source-quantangshi-201');  -- 空
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-hz-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-299';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-hz-person';   -- KNOWN
--   SELECT certainty FROM poetry_claim WHERE id='claim-hz-time-758';    -- LIKELY
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-299'
--     AND predicate='written_during';                                   -- 1
-- 回滚: recovery/V025_rollback.sql（按 id 全枚举删除；不动 V018 的任何行，不动共用通鉴来源行）
START TRANSACTION;""")

    A('\n-- ---------- 0. 来源登记（一律 PENDING：登记不等于核验） ----------')
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            [{'id': 'source-dushi-xiangzhu-05',
              'title': '《杜詩詳註》卷五（清仇兆鰲注）',
              'author': '仇兆鰲',
              'edition': '欽定四庫全書本（维基文库录入本，页面标注需据扫描版校对；'
                         '{{YL|}}、{{SK notes|}}、{{SKchar|}} 等录入标记在引文中原样保留）',
              'url': 'https://zh.wikisource.org/wiki/杜詩詳註_(四庫全書本)/卷05',
              'rights_note': '公有领域古籍。卷五恰是「早朝大明宮」组诗所在——岑参诗无本传，'
                             '却以「附岑參詩」收在杜甫条内，是这首诗最重要的本地注本证据。'
                             'reliability 不代表已核验。',
              'verification_status': 'PENDING', 'source_kind': 'YEAR_BOOK', 'reliability': 'MEDIUM'},
             {'id': 'source-quantangshi-201',
              'title': '《全唐詩》全唐詩/卷201（维基文库录入本）',
              'author': None,
              'edition': '全唐詩/卷201（维基文库《全唐詩》录入本）',
              'url': 'https://zh.wikisource.org/wiki/全唐詩/卷201',
              'rights_note': '维基文库录入本，公有领域古籍。本卷为岑参诗卷，卷首 notes 标作者；'
                             '本诗条目只有锚点+转引用桩，正文在诗页。本行由 emit_v025.py 对快照逐字定位。'
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
    brows = [{'id': k, 'work_id': 'work-t300-299',
              'layer': {'bg-hz-scene': 'SCENE', 'bg-hz-city': 'CITY',
                        'bg-hz-world': 'WORLD', 'bg-hz-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-299-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 系年 claim（work 主语，V022 同款：合推 → LIKELY）+ 选定 ----------
INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)
SELECT * FROM (
SELECT 'claim-hz-time-758' AS id, 'work-t300-299' AS subject_id, 'time.span' AS property_key,
       """ + sql_s(TIME_VALUE) + """ AS value_text, 'FACT' AS claim_kind, 'LIKELY' AS certainty FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_claim x WHERE x.id = t.id);
INSERT INTO poetry_claim_selection (subject_id, property_key, claim_id)
SELECT * FROM (
SELECT 'work-t300-299' AS subject_id, 'time.span' AS property_key, 'claim-hz-time-758' AS claim_id FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_claim_selection x
                  WHERE x.subject_id = t.subject_id AND x.property_key = t.property_key);

-- ---------- 7. 乱期挂接（event.name 断言 + written_during 关系，V022 同款形状） ----------
INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)
SELECT * FROM (
SELECT 'claim-hz-in-anshi' AS id, 'work-t300-299' AS subject_id, 'event.name' AS property_key,
       """ + sql_s(ANSHI_VALUE) + """ AS value_text, 'FACT' AS claim_kind, 'LIKELY' AS certainty FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_claim x WHERE x.id = t.id);
INSERT INTO poetry_claim_selection (subject_id, property_key, claim_id)
SELECT * FROM (
SELECT 'work-t300-299' AS subject_id, 'event.name' AS property_key, 'claim-hz-in-anshi' AS claim_id FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_claim_selection x
                  WHERE x.subject_id = t.subject_id AND x.property_key = t.property_key);
INSERT INTO poetry_relation (id, subject_id, predicate, object_id, claim_id)
SELECT * FROM (
SELECT 'rel-work-t300-299-written-during-anshi' AS id, 'work-t300-299' AS subject_id,
       'written_during' AS predicate, 'event-anshi-rebellion' AS object_id,
       'claim-hz-in-anshi' AS claim_id FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_relation x
                  WHERE x.id = t.id OR (x.subject_id = t.subject_id AND x.predicate = t.predicate
                                        AND x.object_id = t.object_id));

-- ---------- 8. 版本账本 ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 25, 'cen-shen fenghe zaochao-daminggong background layers (inserts-only): first non-Du poem in stage D; four-poem court-verse group (Jia Zhi original plus Wang Wei, Cen Shen, Du Fu responses) evidenced across ws page header, quan tangshi vol201 volume note with transclusion-stub entry, and dushi xiangzhu ju5 which copies the poem as an appendix under the Du Fu entry; tongjian ju220 Qianyuan-1 year title and amnesty; time.span LIKELY from commentary dating attached to the Du Fu poem of the same gathering (single-source, precedent V019); KNOWN limited to attribution and the group, Cen Shen biography verified absent in both Tang history anthologies'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 25);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V025 精确回滚：只删 V025 插入的行（id 全枚举）。work-t300-299 本体是 V018 的行，绝不删；',
         '-- 共用通鉴来源行 source-zizhi-tongjian-events 是 V015 的行，本迁移只是增引卷220，不删。',
         'START TRANSACTION;']
    cids = list(CLAIMS) + ['claim-hz-time-758', 'claim-hz-in-anshi']

    def dels(table, col, vals, chunk=40):
        for i in range(0, len(vals), chunk):
            L.append(f'DELETE FROM {table} WHERE {col} IN ('
                     + ', '.join(sql_s(v) for v in vals[i:i + chunk]) + ');')
    dels('poetry_claim_selection', 'claim_id', cids)
    dels('poetry_citation', 'claim_id', cids)
    dels('poetry_background_line', 'background_id', list(BG))
    dels('poetry_background', 'id', list(BG))
    dels('poetry_relation', 'id', ['rel-work-t300-299-written-during-anshi'])
    dels('poetry_claim', 'id', cids)
    dels('poetry_content', 'id', list(BG))
    dels('poetry_source', 'id', ['source-dushi-xiangzhu-05', 'source-quantangshi-201'])
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 25;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (WS_L12, WS_VAR3, WS_VAR5, WS_HDR, V201_NOTE, V201_ANCHOR, QSS_DATING,
              QSS_PALACE, QSS_CEN, QSS_JIA, QSS_FENG, QSS_GROUP, TJ758Y, TJ_AMEND):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    # 本迁移有意**造**系年与乱期线（与 V023/V024 相反）——只查「值 AS 列名」形状，确保真在
    for shape in ("'time.span' AS property_key", "'written_during' AS predicate"):
        if shape not in sql:
            bad.append(f'V025 应有 {shape}，但 SQL 里没有')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 13 切片逐字过审；'
              f'time.span/written_during 在场已断言；9 组 citation 宽度过审')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
