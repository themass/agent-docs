#!/usr/bin/env python3
"""阶段 D 第 8 首：生成 V026——王維《和賈舍人早朝大明宮之作》(work-t300-140, V018 已立) 四层背景。

与 V025（岑参同组奉和）是同一场诗会的另一半。这首和岑参那首的关键不同：
**王維有真本传**——《舊唐書》卷190下、《新唐书》卷202 文艺都有他，PERSON 层第一次
能写「这个人」而不只写边界。而传里最要紧的一段恰好压在诗会上：陷贼→服药取痢伪瘖→
凝碧池诗→贼平三等定罪→弟縉请削官赎兄罪→特宥→**乾元中**迁太子中庶子、中書舍人。

注本证据同 V025：本诗以「附王維詩」整段收在仇注卷五杜甫条内（{{SK anchor|和前}}标目），
注里还带一条异文重证——仇注正文取「絳幘雞人{{SK notes|一作送}}報曉籌」，
**与维基文库诗页首读「送」正相反**（页面 {{另|送|報}} 取送，注本取報）。两处都登，不裁决。

用法: python3 -I emit_v026.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源
from emit_v025 import (  # noqa: E402  同一卷五快照、同一诗会切片——单一来源，零复制
    QSS, TJ758Y, TJ_AMEND, QSS_DATING, QSS_JIA, QSS_FENG, QSS_GROUP,
)

WS = pathlib.Path('/tmp/src-dl/ws-poems/和賈舍人早朝大明宮之作.txt').read_text(encoding='utf-8')
TJ220 = pathlib.Path('/tmp/src-dl/tongjian/tj-220.txt').read_text(encoding='utf-8')
V128 = pathlib.Path('/tmp/src-dl/quantangshi/vol128.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；锚不唯一即中止） ----------
WS_L1V = slice_between(WS, '絳幘雞人{{另|送|報}}曉籌，', '絳幘雞人{{另|送|報}}曉籌，', 'ws起行(页内异文送/報)')
WS_VAR3 = slice_between(WS, '九{{另|天|重}}閶闔開宮殿，', '九{{另|天|重}}閶闔開宮殿，', 'ws第三行(页内异文天/重)')
WS_VAR8 = slice_between(WS, '佩聲歸{{另|向|到}}鳳池頭。', '佩聲歸{{另|向|到}}鳳池頭。', 'ws末行(页内异文向/到)')
WS_HDR = slice_between(WS, '| title    = 和賈舍人早朝大明宮之作', '| author   = 王維', 'ws header title+author')
V128_NOTE = slice_between(V128, "'''王維'''", "'''王維'''", 'vol128 卷首作者注')
V128_ANCHOR = slice_between(V128, '==[[和賈舍人早朝大明宮之作]]==',
                            '{{:和賈舍人早朝大明宮之作}}', 'vol128 锚点+转引用桩')
QSS_WWT = slice_between(QSS, '{{SK anchor|絳幘雞人報}}{{SK notes|一作送}}曉籌',
                        '佩聲歸向鳯池頭', '仇注附王维诗正文(報一作送—与诗页首读相反)')
QSS_HGY = slice_between(QSS, '漢官儀宮中輿臺竝不得畜雞', '著絳幘雞唱', '仇注注内引汉官仪(絳幘鸡唱)')
TJ_NINE = slice_between(TJ220, '庚寅，命朔方郭子儀', '將所部兵助之。', '通鉴九节度使讨庆绪758')
JTS_XZ = slice_between(JTS, '禄山䧟兩都，玄宗出幸，維扈從不及，為賊所得。',
                       '轉尚書右丞。', '旧唐书王维传陷贼至乾元历职整段')
XTS_XZ = slice_between(XTS, '安祿山反，玄宗西狩，維為賊得', '下遷太子中允。', '新唐书王维传陷贼至太子中允整段')

BG = {
    'bg-wd-scene': (
        '还是那场天没亮的朝会，换一个角度再写一遍：宫里的报晓人戴着红头巾唱筹，'
        '尚衣局刚把翠云裘呈上去——诗从宫墙内最先醒的那个人写起。'
        '第一句维基文库诗页里就并列两读：「絳幘雞人{{另|送|報}}曉籌」（{{另|}} 是页面异文标记，原样引）。\n'
        '这一首的题目「和賈舍人早朝大明宮之作」把自己的位置说清了：它是和作，'
        '唱的那首出自中書舍人賈至。谁先写的、和得如何，仇注有总评——那是读法，照登在第 7、8 句那层。'),
    'bg-wd-city': (
        '「絳幘雞人」不是比喻。仇注注这一句时引《漢官儀》：'
        '「宮中輿臺竝不得畜雞，夜漏未明三刻雞鳴，衛士候於朱雀門外，著絳幘雞唱」——'
        '红头巾报晓是宫中执事的制度名物，写在注家引的汉官仪里（录入标记照登）。\n'
        '「九天閶闔開宮殿」的閶闔是天门，也是宫门的借称；诗页此句同样并列两读'
        '「九{{另|天|重}}閶闔開宮殿」。名物的账，注本替我们记着。'),
    'bg-wd-world': (
        '这场早朝的年份在通鑑里有名有姓：乾元元年（戊戌，公元七五八年）「丁未，上御明鳳門，'
        '赦天下，改元」——朝廷刚改元乾元。同一个春天里，仗还没打完：'
        '通鑑同年记「庚寅，命朔方郭子儀……七節度使及平盧兵馬使董秦將步騎二十萬討慶緒；'
        '又命河東李光弼、關內、澤潞王思禮二節度使將所部兵助之」——九个节度使围安庆绪，'
        '朝廷却不设元帅，只派宦官鱼朝恩做观军容使。\n'
        '朝堂上鸡唱裘进、五色诏裁；朝堂外二十万人讨庆绪。诗里看不到仗——'
        '这正是乱中早朝诗的张力，两页并置是读法，通鑑的记事摆在那里。'),
    'bg-wd-person': (
        '写这首和作的人，两唐书都有传，而且传里最重的一段就压在乱事里：'
        '《舊唐書》「禄山陷两都……维扈从不及，为贼所得。维服药取痢，伪称瘖病……迫以伪署……'
        '凝碧宫……维闻之悲恻，潜为诗曰：万户伤心生野烟……」；贼平论罪，'
        '「维以凝碧诗闻于行在，肃宗嘉之，会缙请削己刑部侍郎以赎兄罪，特宥之」——'
        '弟弟王缙拿自己的官赎他的罪。《新唐书》同记此事，字有详略，事不相背。\n'
        '「佩聲歸向鳳池頭」的凤池即中书省：仇注引《晋书》荀勖传「夺我凤凰池，诸君贺我耶」。'
        '巧的是两传同记他「乾元中，迁太子中庶子、中書舍人」——他后来也成了「舍人」；'
        '但「乾元中」无月，和本诗的先后核不到，不排。\n'
        '这组诗四首：賈至原唱「早朝大明宮呈兩省僚友」，王維、岑参、杜甫三和——'
        '王維这首在《唐詩三百首》里（第 140 首），岑、杜两首也在，原唱在仇注附段里逐字保存。'
        '仇注总评「合觀四作……三和俱有奪席之意……王岑秀色可攬……故當推為擅塲」——注家之判，照登不裁决。'),
}
CLAIMS = {
    'claim-bg-wd-scene': (
        'INTERPRETATION', 'LIKELY',
        '早朝场景为诗本文内证（题「和賈舍人…」+通篇候朝名物）；首行页内异文（送/報）有 ws 快照逐字，'
        '仇注正文取「報」别出「一作送」——两处首读相反，均逐字登记不裁决。'),
    'claim-bg-wd-city': (
        'FACT', 'LIKELY',
        '絳幘鸡唱名物为仇注注内引《漢官儀》（四库本录入快照逐字，录入标记照登）；'
        '属注本转引类书/汉官仪——单链但逐字可指，故 LIKELY 不升 KNOWN。'),
    'claim-bg-wd-world': (
        'FACT', 'LIKELY',
        '乾元元年年标题、改元句、九节度使讨庆绪+不置元帅均以通鉴卷220 逐字'
        '（与 V025 共用年标题/改元切片）；朝堂与战场并置已标明是读法。'),
    'claim-bg-wd-person': (
        'FACT', 'KNOWN',
        '陷贼-伪瘖-凝碧诗-特宥-乾元迁转整段，旧唐书卷190下/新唐书卷202 各记一段互不矛盾逐字可指，'
        '升 KNOWN（同 V017/V021/V022 两史标准）；certainty 只覆盖本传事实与唱和集团，'
        '不覆盖本诗系月与「乾元中」迁转的先后（核不到，正文不排）。'),
}
CITATIONS = [
    ('claim-bg-wd-scene', 'source-ws-t300-140',
     '页面 和賈舍人早朝大明宮之作（起行含页内异文标记 {{另|送|報}} 原样引，'
     '登记 corpus/tang300-variants.md 不裁决；八句全文见 V018 claim-t300-140-text 引文）',
     WS_L1V),
    ('claim-bg-wd-scene', 'source-dushi-xiangzhu-05',
     '杜詩詳註卷五·「附王維詩」正文段（仇注正文作「報」别出「一作送」——与诗页首读相反；'
     '另有第三行异读「一作九天宮殿開閶闔」，均在段内照登）',
     join(QSS_WWT, WS_VAR3, WS_VAR8)),
    ('claim-bg-wd-city', 'source-dushi-xiangzhu-05',
     '杜詩詳註卷五·附王維詩注条（注内引《漢官儀》絳幘鸡唱；录自注本，非汉官仪原本）',
     QSS_HGY),
    ('claim-bg-wd-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十·乾元元年（戊戌，公元七五八年）年標題＋二月改元句＋九節度使討慶緒条'
     '（与 V025 共用年标题/改元切片；三段以「……」相連）',
     join(TJ758Y, TJ_AMEND, TJ_NINE)),
    ('claim-bg-wd-person', 'source-ws-t300-140',
     '页面 和賈舍人早朝大明宮之作（header title+author 字段逐字）',
     WS_HDR),
    ('claim-bg-wd-person', 'source-quantangshi-128',
     '页面 全唐詩/卷128（卷首 notes 作者注＋本诗锚点与转引用桩 {{:…}}；'
     '卷页无正文，正文证据在诗页——同 V022/V025 桩教训，定位已分记）',
     join(V128_NOTE, V128_ANCHOR)),
    ('claim-bg-wd-person', 'source-dushi-xiangzhu-05',
     '杜詩詳註卷五·賈至原唱条标＋晋书凤池典＋組詩总评「合觀四作」段'
     '（三段与 V025 共用切片，逐字相同，以「……」相連）',
     join(QSS_JIA, QSS_FENG, QSS_GROUP)),
    ('claim-bg-wd-person', 'source-jiutangshu-wenyuan',
     '卷一百四十下·文苑下·王維传（陷贼-伪瘖-凝碧诗-特宥-乾元迁转整段连续原文；{{YL|}} 标记照登）',
     JTS_XZ),
    ('claim-bg-wd-person', 'source-xintangshu-wenyi',
     '卷二百二·文藝中·王維传（陷贼-凝碧-下獄-特宥整段连续原文，与旧传字有详略事不相背）',
     XTS_XZ),
    ('claim-wd-time-758', 'source-dushi-xiangzhu-05',
     '杜詩詳註卷五·杜甫奉和条注系年句（「此乾元元年春在諫省作」附在杜甫奉和条上——'
     '王维和作同场为内证，唱和同一集会；注本单源）',
     QSS_DATING),
    ('claim-wd-in-anshi', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十·乾元元年（戊戌，公元七五八年）年標題（758 在 755–763 乱期内的纪年锚）',
     TJ758Y),
]
BG_LINES = {'bg-wd-scene': (1, 2), 'bg-wd-city': (3, 4),
            'bg-wd-world': (5, 6), 'bg-wd-person': (7, 8)}
BG_AUDIENCE = {'bg-wd-scene': 'PRIMARY', 'bg-wd-city': 'JUNIOR',
               'bg-wd-world': 'SENIOR', 'bg-wd-person': 'PRIMARY'}
BG_TITLES = {'bg-wd-scene': '眼前：红头巾唱筹的那个拂晓',
             'bg-wd-city': '这名物：宫里没有鸡，有唱晓的卫士',
             'bg-wd-world': '这个春天：刚改元，九路兵马正围庆绪',
             'bg-wd-person': '这个人：陷贼、凝碧诗，和赎他罪的弟弟'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 8 首·早朝大明宮组诗另一半）；史实句均有逐字引证；'
                 '王维本传两唐书逐字升 KNOWN；系年仍注本单源 LIKELY。' for k in BG}
TIME_VALUE = ('758..758 (EXACT) 乾元元年春说：仇注系年句「此乾元元年春在諫省作」'
              '附于杜甫同组和作（唱和同一集会为内证——原唱与三和同一场早朝）'
              '+通鉴卷220 年标题为纪年锚；注本单源合推，非年谱原文——同 V019/V025 先例给 LIKELY')
ANSHI_VALUE = ('安史之亂（755–763）。係年758在亂期內（通鑑卷220 乾元元年標題）；'
               '诗人本人即乱事亲历者（陷贼-伪瘖-凝碧诗-特宥，两唐书逐字），'
               '此诗是乱中朝廷的早朝声景，诗本文不写战事')


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
    A("""-- V026：王維《和賈舍人早朝大明宮之作》(work-t300-140) 四层背景（阶段 D 第 8 首）。MySQL 5.6.40 兼容。
-- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V015、V016、V017、V018、V025 已执行（work-t300-140 与其 text-work-t300-140-ws 是 V018 行；
--       source-ws-t300-140 亦是 V018 行；source-dushi-xiangzhu-05 是 V025 行；
--       source-jiutangshu-wenyuan / source-xintangshu-wenyi 是 V016 行；
--       source-zizhi-tongjian-events 是 V015 行；event-anshi-rebellion 是 V004/V015 行）。
--
-- 数据源（可复现）：emit_v026.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/和賈舍人早朝大明宮之作.txt（页内 {{另|}} 异文标记照登）、
--   杜詩詳註(四庫全書本)卷05（「附王維詩」段——注本正文取「報」，与诗页首读「送」相反）、
--   資治通鑑卷220（年标题/改元与 V025 共用切片）、全唐詩卷128、舊唐書卷190下、新唐書卷202。
--
-- 做：1 个新 source 登记（全唐詩卷128，PENDING——登记不等于核验）+
--   4 BACKGROUND content/claim/background + 11 组逐字引用 + 系年 claim（time.span LIKELY）+
--   written_during 安史挂接 + 8 行 background_line（scene→1,2｜city→3,4｜world→5,6｜person→7,8，
--   绑 text-work-t300-140-ws）。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log。
--
-- 诚实边界：
--   * 系年为注本单源：仇注系年句附在**杜甫**奉和条（唱和同一集会为内证），LIKELY（V019/V025 先例）；
--   * 首行异文「送/報」两处来源首读相反（诗页取送，仇注正文取報且别出「一作送」）——只登记不裁决；
--   * 「乾元中迁中書舍人」与「此诗（乾元元年春）」的先后核不到，正文不排；
--   * 汉官仪句是仇注注内转引（非汉官仪原本单证）——LIKELY 不升 KNOWN；
--   * 仇注「合觀四作」高下之判是注家读法，照登不裁决；
--   * KNOWN 覆盖本传事实（两唐书各记一段互不矛盾逐字可指）与唱和集团，不覆盖系月。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 25，不含 26
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-wd-%';              -- 空
--   SELECT id FROM poetry_text_version WHERE id='text-work-t300-140-ws';  -- 恰 1 行（V018 已执行）
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-128';     -- 空
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-wd-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-140';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-wd-person';   -- KNOWN
--   SELECT certainty FROM poetry_claim WHERE id='claim-wd-time-758';    -- LIKELY
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-140'
--     AND predicate='written_during';                                   -- 1
-- 回滚: recovery/V026_rollback.sql（按 id 全枚举删除；不动 V018/V025 的任何行，不动共用通鉴来源行）
START TRANSACTION;""")

    A('\n-- ---------- 0. 来源登记（一律 PENDING：登记不等于核验） ----------')
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            [{'id': 'source-quantangshi-128',
              'title': '《全唐詩》全唐詩/卷128（维基文库录入本）',
              'author': None,
              'edition': '全唐詩/卷128（维基文库《全唐詩》录入本）',
              'url': 'https://zh.wikisource.org/wiki/全唐詩/卷128',
              'rights_note': '维基文库录入本，公有领域古籍。本卷为王維诗卷，卷首 notes 标作者；'
                             '本诗条目只有锚点+转引用桩，正文在诗页。本行由 emit_v026.py 对快照逐字定位。'
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
    brows = [{'id': k, 'work_id': 'work-t300-140',
              'layer': {'bg-wd-scene': 'SCENE', 'bg-wd-city': 'CITY',
                        'bg-wd-world': 'WORLD', 'bg-wd-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-140-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 系年 claim（work 主语，V022/V025 同款：合推 → LIKELY）+ 选定 ----------
INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)
SELECT * FROM (
SELECT 'claim-wd-time-758' AS id, 'work-t300-140' AS subject_id, 'time.span' AS property_key,
       """ + sql_s(TIME_VALUE) + """ AS value_text, 'FACT' AS claim_kind, 'LIKELY' AS certainty FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_claim x WHERE x.id = t.id);
INSERT INTO poetry_claim_selection (subject_id, property_key, claim_id)
SELECT * FROM (
SELECT 'work-t300-140' AS subject_id, 'time.span' AS property_key, 'claim-wd-time-758' AS claim_id FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_claim_selection x
                  WHERE x.subject_id = t.subject_id AND x.property_key = t.property_key);

-- ---------- 7. 乱期挂接（event.name 断言 + written_during 关系，V022/V025 同款形状） ----------
INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)
SELECT * FROM (
SELECT 'claim-wd-in-anshi' AS id, 'work-t300-140' AS subject_id, 'event.name' AS property_key,
       """ + sql_s(ANSHI_VALUE) + """ AS value_text, 'FACT' AS claim_kind, 'LIKELY' AS certainty FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_claim x WHERE x.id = t.id);
INSERT INTO poetry_claim_selection (subject_id, property_key, claim_id)
SELECT * FROM (
SELECT 'work-t300-140' AS subject_id, 'event.name' AS property_key, 'claim-wd-in-anshi' AS claim_id FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_claim_selection x
                  WHERE x.subject_id = t.subject_id AND x.property_key = t.property_key);
INSERT INTO poetry_relation (id, subject_id, predicate, object_id, claim_id)
SELECT * FROM (
SELECT 'rel-work-t300-140-written-during-anshi' AS id, 'work-t300-140' AS subject_id,
       'written_during' AS predicate, 'event-anshi-rebellion' AS object_id,
       'claim-wd-in-anshi' AS claim_id FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_relation x
                  WHERE x.id = t.id OR (x.subject_id = t.subject_id AND x.predicate = t.predicate
                                        AND x.object_id = t.object_id));

-- ---------- 8. 版本账本 ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 26, 'wang wei he jiasheren zaochao-daminggong background layers (inserts-only): the other half of the morning-audience poem set completed in V025; Wang Wei is the first stage-D poet with real biographies in both Tang histories (captured by rebels, feigned muteness with purgative medicine, the Ningbi pool poem, brother Juan begging to trade his own office to redeem him) -- biography facts KNOWN per two-histories standard; attribution triple (ws page header, quan tangshi vol128 volume note with transclusion-stub entry, dushi xiangzhu appendix); first line carries a mirror-image variant: ws page prints song as first reading while the commentary text prints bao with "yi zuo song" -- both registered, none adjudicated; time.span LIKELY via the same single-source commentary dating (precedents V019/V025); tongjian ju220 amnesty and the nine-governors campaign against An Qingxu as the spring of 758'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 26);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V026 精确回滚：只删 V026 插入的行（id 全枚举）。work-t300-140 本体是 V018 的行，绝不删；',
         '-- 共用 source 行（dushi-xiangzhu-05=V025、两唐书文苑/V016、通鉴/V015）都不删。',
         'START TRANSACTION;']
    cids = list(CLAIMS) + ['claim-wd-time-758', 'claim-wd-in-anshi']

    def dels(table, col, vals, chunk=40):
        for i in range(0, len(vals), chunk):
            L.append(f'DELETE FROM {table} WHERE {col} IN ('
                     + ', '.join(sql_s(v) for v in vals[i:i + chunk]) + ');')
    dels('poetry_claim_selection', 'claim_id', cids)
    dels('poetry_citation', 'claim_id', cids)
    dels('poetry_background_line', 'background_id', list(BG))
    dels('poetry_background', 'id', list(BG))
    dels('poetry_relation', 'id', ['rel-work-t300-140-written-during-anshi'])
    dels('poetry_claim', 'id', cids)
    dels('poetry_content', 'id', list(BG))
    dels('poetry_source', 'id', ['source-quantangshi-128'])
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 26;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (WS_L1V, WS_VAR3, WS_VAR8, WS_HDR, V128_NOTE, V128_ANCHOR, QSS_WWT, QSS_HGY,
              TJ758Y, TJ_AMEND, TJ_NINE, JTS_XZ, XTS_XZ, QSS_JIA, QSS_FENG, QSS_GROUP, QSS_DATING):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    # 本迁移有意造系年与乱期线（V025 同款）——只查「值 AS 列名」形状，确保真在
    for shape in ("'time.span' AS property_key", "'written_during' AS predicate"):
        if shape not in sql:
            bad.append(f'V026 应有 {shape}，但 SQL 里没有')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 17 切片逐字过审；'
              f'time.span/written_during 在场已断言；11 组 citation 宽度过审')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
