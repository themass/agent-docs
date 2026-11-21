#!/usr/bin/env python3
"""阶段 D 第 23 首：生成 V042——李白《春思》(work-t300-312, V018 已立) 四层背景。

「为什么写」第十五次成立，这首逼出**全部二十首里从未出现过的一个事实**：
诗的第一人称不是李白——「是妾斷腸時」的「妾」、被「君」怀归的对象，
是一个思妇的口吻。两传里李白无妻儿记载（新传唯一的「妻」字出现在
**曾孙辈**：「訪後裔，惟二孫女嫁為民妻」），也零燕地行迹——
诗里的两个人（君/妾）与两个地方（燕/秦）全不在传记线上。

系年第十七次判决（题证系列第五状）：**「诗语有地，地不在传；诗有人，人不系传」**——
V038 题有地传无路、V039 题无地传无年、V040 页有年史无年、V041 题有角色无人——
这首是**代辞**：地点在诗内却都是别人的地点，人在诗内却都是别人。
代言体诗的第一次入藏逼出 persona 分离纪律：**抒情「我」不并入传记「我」**，
不写「李白思念妻子」——传里连妻子都没有。零铸造零 relation。

KNOWN 零处（如实）：新传「母夢長庚星，因以命之」得名佳话单得不升；
妻儿零载是负证不是 KNOWN 材料。本首 certainty 全 LIKELY——
这是阶段 D 第一次整首零 KNOWN，审计与账本如实记录，不为凑数升格。

WORLD 层真证：通鉴 734（開元二十二年）条「六月，壬辰，幽州節度使
張守珪大破契丹，遣使獻捷」——燕地正是开天边军驻防区，「燕草如碧絲」
北上之「君」有制度性理由；条在 734 与 735 帝标题之间（生成器位置断言，
V034 立规）；与李白零关联声明照常。负证更硬：**两传李白传区间「燕」字
出现次数为零**（生成时断言，若快照变动即中止）。

六句 2/2/1/1 第二用（V037 送別同款形制）；异文零新行（ws 页 100% 无标记）；
1 新 source：全唐詩卷165 桩页（回滚同步删除）。

用法: python3 -I emit_v042.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/春思__李白_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
QT165 = pathlib.Path('/tmp/src-dl/quantangshi/vol165.txt').read_text(encoding='utf-8')
TJ214 = pathlib.Path('/tmp/src-dl/tongjian/tj-214.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_FURTHER = slice_between(WS, '{{Further|春思}}', '{{Further|春思}}',
                           'ws 页顶消歧模板(同名《春思》另首存在——选本同名诗并存直证)')
WS_TITLE = slice_between(WS, '| title    = 春思', '| title    = 春思', 'ws header title(题只两字:季节+情绪)')
WS_AUTHOR = slice_between(WS, '| author   = 李白', 'author   = 李白', 'ws header author(署名直证)')
WS_L12 = slice_between(WS, '燕草如碧絲，秦桑低綠枝。', '秦桑低綠枝。', 'ws第1-2句联(燕草秦桑——两地名分属两人)')
WS_L12A = slice_between(WS, '燕草如碧絲，秦桑低綠枝。', '燕草如碧絲，', 'ws第1句(燕草如碧丝)')
WS_L34 = slice_between(WS, '當君懷歸日，是妾斷腸時。', '是妾斷腸時。', 'ws第3-4句联(君怀归/妾断肠——代辞核心联)')
WS_L34A = slice_between(WS, '當君懷歸日，是妾斷腸時。', '當君懷歸日，', 'ws第3句(当君怀归日)')
WS_L56 = slice_between(WS, '春風不相識，何事入羅幃。', '何事入羅幃。', 'ws第5-6句联(春风不相识/何事入罗帏)')
WS_L56A = slice_between(WS, '春風不相識，何事入羅幃。', '春風不相識，', 'ws第5句(春风不相识)')
XTS_CG = slice_between(XTS, '白之生，母夢長庚星，因以命之。十歲通詩書，既長，隱岷山。州舉有道，不應。',
                       '州舉有道，不應。',
                       '新传出生段(母梦长庚以命之/十岁通诗书/隐岷山/举有道不应——新传单得不升;岷山在成都府,非燕)')
XTS_HOU = slice_between(XTS, '訪後裔，惟二孫女嫁為民妻，進止仍有風範', '進止仍有風範',
                        '新传范传正访后裔段(二孙女嫁为民妻——两传李白线唯一「妻」字在曾孙辈,本人生无妻儿记载之负证在此段;V041 已立祭塚句,此处访裔句异侧再证)')
TJ214_TITLE = slice_between(TJ214, '開元二十二年{{*|甲戌，西元七三四年}}', '開元二十二年{{*|甲戌，西元七三四年}}',
                            '通鉴214卷734帝标题(生成器位置断言：张守珪条在734与735标题之间)')
TJ214_SK = slice_between(TJ214, '六月，壬辰，幽州節度使張守珪大破契丹，遣使獻捷。', '遣使獻捷。',
                         '通鉴734幽州条(幽州节度使大破契丹献捷——燕地=开天边军驻防区,「燕草」北上的制度背景;与李白零关联)')
QT_STUB = slice_between(QT165, '==[[春思 (李白)|春思]]==\n{{:春思 (李白)}}', '{{:春思 (李白)}}',
                        '全唐诗卷165本诗条目(锚点+转引用桩——卷页无正文)')

# ---------- 生成时硬断言 ----------
# 1) 通鉴年标题位置归属（V034 立规）
_i = TJ214.find('六月，壬辰，幽州節度使張守珪')
_a = TJ214.find('==玄宗至道大聖大明孝皇帝中之中開元二十二年{{*|甲戌')
_b = TJ214.find('==玄宗至道大聖大明孝皇帝中之中開元二十三年{{*|乙亥')
if not (0 <= _a < _i < _b):
    raise SystemExit('张守珪条不在734帝标题区间内——修订后重生成')
# 2) 传区间归属（V036 立规）
_ja, _jb = JTS.find('=李白='), JTS.find('=杜甫=')
_xa, _xb = XTS.find('==李白=='), XTS.find('===附 張旭===')
for _s, _tag in [(XTS_CG, 'XTS_CG'), (XTS_HOU, 'XTS_HOU')]:
    if not (_xa <= XTS.find(_s) <= _xb):
        raise SystemExit(f'切片越出李白传区块：{_tag}——修订后重生成')
# 3) 燕地负证（本首特有，负证自身也要被机器复查）
_seg_j, _seg_x = JTS[_ja:_jb], XTS[_xa:_xb]
if '燕' in _seg_j or '燕' in _seg_x:
    raise SystemExit('李白传区间出现「燕」字——零燕地负证失效，修订后重生成')
if '幽州' in _seg_j or '幽州' in _seg_x:
    raise SystemExit('李白传区间出现「幽州」——零燕地负证失效，修订后重生成')
# 4) ws 页零标记反向断言（V041 立规）
for _tok in ('{{另', '{{别', '{{*'):
    if _tok in WS:
        raise SystemExit('ws 页出现计划外异文标记——先登记后重生成')

BG = {
    'bg-cs-scene': (
        '六句是一场独角戏，台词全是「对不存在于场内的另一个人说」：'
        '燕地的草该像碧丝一样了吧，秦地的桑已经压弯了绿枝（「燕草如碧絲，'
        '秦桑低綠枝」——两个地方，两个人各看各的春）；你怀想归乡的那天，'
        '正是我断肠的时候（「當君懷歸日，是妾斷腸時」——两个「时候」不同步，'
        '诗把不同步本身写成全部感情）；风你不认得我我不认得你，'
        '你凭什么掀我的帐子（「春風不相識，何事入羅幃」——把春心问罪给风，'
        '是全唐诗里最聪明的一次岔开）。'
        '页首 {{Further}} 消歧模板照登：选本系统里另有一首同名《春思》——'
        '连标题都不独有。'),
    'bg-cs-city': (
        '这首诗横跨两个地方，**却一个都不在作者的地图上**：燕（幽州边镇方向）'
        '是「君」所在，秦（关中）是「妾」所在。李白的两传行迹：徂徠山、會稽、'
        '長安、金陵、庐山、宣城——机器复查：**两传区间内「燕」字与「幽州」出现次数'
        '均为零**（生成时断言，快照变动即中止）。他本人从没被史料放进燕地。\n'
        '于是这座「城」是双城的，且两城都是戏台：诗语有地，地不在传——'
        '不是史料缺一条燕地行迹，而是这首诗本来就不需要作者到过那里。'
        '不补传，不系年，不猜为谁代辞。'),
    'bg-cs-world': (
        '「燕草」为何而绿？通鉴给得干脆：734 年（開元二十二年）条'
        '「六月，壬辰，幽州節度使張守珪大破契丹，遣使獻捷」——'
        '条在 734 与 735 帝标题之间（生成器位置断言，V034 立规）。'
        '幽州节度使是开天年间最重的边镇之一，破契丹献捷是当年国闻：'
        '燕地是**驻防区**，「君」北上从军/幕游在那个年代有充分的制度理由，'
        '思妇诗的流行与边镇征兵同呼吸——这是读法，史料部分止于：'
        '734 年幽州确有大捷且入正史。\n'
        '与王维那条「节令入正史不推及诗」同理：**边镇入正史不推及这首诗**——'
        '张守珪的捷报与《春思》零关联，账本如实断开。'),
    'bg-cs-person': (
        '代辞需要被说破：**诗里的「妾」不是李白的经验档案，因为档案里没有家庭**。'
        '两传写李白，妻儿零记载——新传全文唯一的「妻」字在身后：范传正訪後裔，'
        '「惟二孫女嫁為民妻」——连「妻子」这种身份，史料都是在他曾孙辈身上'
        '第一次用到（V041 已立祭塚句，此处访裔句异侧再证）。不写'
        '「李白思念妻子」：传里连妻子都没有。\n'
        '传给的开头是神话的：新传「白之生，母夢長庚星，因以命之」——'
        '名字是梦里那颗星给的；「十歲通詩書，既長，隱岷山。州舉有道，不應」——'
        '不出仕是他选的第一条路（新传单源，不升 KNOWN）。\n'
        '一个被史实抹去家庭的人，写出唐诗里最好的思妇独白——'
        '「为什么写」在这首的答案只能是：为所有传不进史书的人称情而立文。'
        '此为读法，标明。'),
}
CLAIMS = {
    'claim-bg-cs-scene': (
        'FACT', 'LIKELY',
        '六句全诗本文（ws 页零页内标记——另/别/自注三类皆无，audit 反向断言；'
        '页首 {{Further}} 消歧模板照登=选本同名诗并存直证）；'
        '独角戏/两个不同步的时候为本层读法声明。'),
    'claim-bg-cs-city': (
        'FACT', 'LIKELY',
        '双城皆戏台：燕/秦两名全不在两传行迹（负证机器复查：李白传区间'
        '「燕」「幽州」计数为零，生成时断言）；诗语有地，地不在传→'
        '不补传不系年不猜代辞对象；零铸造零 relation。'),
    'claim-bg-cs-world': (
        'FACT', 'LIKELY',
        '734 幽州条（年标题+六月壬辰幽州節度使張守珪大破契丹遣使獻捷，'
        '条在 734/735 帝标题区间内，生成时位置断言 V034 立规）——'
        '燕地=开天边军驻防区的制度形状；边镇入正史不推及此诗，零关联声明；'
        '思妇诗与边镇同呼吸为读法；诗 time.span/event.name/written_during 零铸造。'),
    'claim-bg-cs-person': (
        'FACT', 'LIKELY',
        'persona 分离：代辞抒情我≠传记我（两传李白本人妻儿零记载——'
        '新传唯一「妻」字在曾孙辈「二孫女嫁為民妻」，访裔段逐字立证）；'
        '母夢長庚/隐岷山/举有道不应新传单得不升；整首零 KNOWN 为如实记录非疏漏；'
        '「为传不进史书者立文」标明读法；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-cs-scene', 'source-ws-t300-312',
     '页面 春思 (李白)（页顶消歧模板+header title+author+六句全文，九段以「……」相連——'
     '页面零异文标记（Textquality 100%），无标记即不造标记；'
     '同一 (claim,source) 主键下一行容全文，V037/V039/V040/V041 判例；'
     '全文另见 V018 claim-t300-312-text 引文）',
     join(WS_FURTHER, WS_TITLE, WS_AUTHOR, WS_L12A, WS_L12, WS_L34A, WS_L34, WS_L56A, WS_L56)),
    ('claim-bg-cs-city', 'source-quantangshi-165',
     '卷一百六十五·李白诗目下本诗条目（锚点+转引用桩——卷页无正文，桩文照登；'
     '本迁移开立此来源行）', QT_STUB),
    ('claim-bg-cs-world', 'source-zizhi-tongjian-events',
     '通鉴卷二百一十四·玄宗開元二十二年（734）条（帝标题含{{*|甲戌，西元七三四年}}+'
     '六月壬辰幽州節度使張守珪大破契丹遣使獻捷——生成时位置断言：'
     '条在 734 与 735 帝标题之间；与李白零关联）', join(TJ214_TITLE, TJ214_SK)),
    ('claim-bg-cs-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传（出生段+访后裔段以「……」相連，同卷同传——'
     '母梦长庚/隐岷山单得不升；唯一「妻」字在曾孙辈，本人生无妻儿记载之'
     '负证正面文本；访裔段与 V041 祭塚句异侧不重叠）', join(XTS_CG, XTS_HOU)),
]
BG_LINES = {'bg-cs-scene': (1, 2), 'bg-cs-city': (3, 4), 'bg-cs-world': (5,), 'bg-cs-person': (6,)}
BG_AUDIENCE = {'bg-cs-scene': 'PRIMARY', 'bg-cs-city': 'JUNIOR',
               'bg-cs-world': 'SENIOR', 'bg-cs-person': 'SENIOR'}
BG_TITLES = {'bg-cs-scene': '眼前：独角戏对不在场的人说',
             'bg-cs-city': '这座城：双城都是戏台',
             'bg-cs-world': '这个天下：燕草为何而绿',
             'bg-cs-person': '这个人：档案里没有家庭'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 23 首·六句 2/2/1/1 第二用）；史实句均有逐字引证；'
                 'background_line 六句形制：scene→1-2 city→3-4 world→5 person→6；'
                 '系年第十七次判决「诗语有地，地不在传；诗有人，人不系传」'
                 '（题证系列第五状·首见代辞 persona 分离）→time.span/event.name/'
                 'written_during 全缺席、零 relation；整首零 KNOWN（如实记录非疏漏：'
                 '长庚梦新传单得，妻儿零载是负证）；两传李白区间零燕字负证'
                 '生成时机器复查；通鉴 734 幽州条年标题位置断言（V034 立规）。' for k in BG}
NEW_SOURCES = [
    {'id': 'source-quantangshi-165',
     'title': '《全唐詩》全唐詩/卷165（维基文库录入本）',
     'author': None,
     'edition': '全唐詩/卷165（维基文库《全唐詩》录入本）',
     'url': 'https://zh.wikisource.org/wiki/全唐詩/卷165',
     'rights_note': '维基文库录入本，公有领域古籍。卷页只有诗题锚点+转引用桩，正文在诗页。'
                    '本行由 emit_v042.py 对快照逐字定位。核验状态保持 PENDING。',
     'verification_status': 'PENDING', 'source_kind': 'POETRY_COLLECTION', 'reliability': 'HIGH'},
]


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
    A("""-- V042：李白《春思》(work-t300-312) 四层背景（阶段 D 第 23 首·六句 2/2/1/1 第二用）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-312 与其 text-work-t300-312-ws、
--       source-ws-t300-312 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行；source-zizhi-tongjian-events 早期迁移已立——均不另开）。
-- 本迁移**恰 1 个新 source**：source-quantangshi-165（卷页桩，断言恰 1 个，回滚同步删除）。
--
-- 数据源（可复现）：emit_v042.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/春思__李白_.txt（页顶 {{Further}} 消歧模板照登；页面零异文标记——反向断言）、
--   新唐書卷202（李白传出生段+访后裔段——切片传区间归属生成时断言）、
--   通鉴 tj-214（734 幽州条——帝标题位置断言 V034 立规）、
--   quantangshi/vol165（本诗条目桩）。
--   负证机器复查（生成时）：两传李白传区间「燕」「幽州」计数均为零，否则中止。
--
-- 做：1 个新 source + 4 BACKGROUND content/claim/background +
--   4 组逐字引用（(claim,source) 主键每对恰一行）+
--   6 行 background_line（**六句形制 2/2/1/1 第二用**：scene→1-2 city→3-4 world→5 person→6，
--   绑 text-work-t300-312-ws 的 6 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是代辞——persona 分离首次成为判决主题）：
--   * 抒情「我」=思妇，不并入传记「我」：两传李白妻儿零记载，
--     唯一「妻」字在曾孙辈「二孫女嫁為民妻」（访裔段逐字立证）——不写「李白思念妻子」；
--   * 双城（燕/秦）皆不在两传行迹：负证由生成时计数复查，非人工目测；
--   * 通鉴 734 幽州条只立「燕地=边镇」制度形状，与诗零关联；
--   * 整首零 KNOWN：母夢長庚单得不升、妻儿零载是负证——不为凑数升格，账本如实；
--   * 「为传不进史书者立文」等感情句全部标明读法。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 41，不含 42
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-cs-%';              -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-165';     -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-312-ws';  -- 恰 6（六句）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-cs-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-312';                                  -- 6（2/2/1/1）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-cs-%';   -- 四行全 LIKELY（有意零 KNOWN）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-312'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-312';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-cs-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V042_rollback.sql（按 id 全枚举删除；删 V042 自开的 source-quantangshi-165；
--   不动 V018 的行与共用来源行）
START TRANSACTION;""")

    A('\n-- ---------- 0. 新 source（恰 1 个：全唐詩卷165 桩页，PENDING） ----------')
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            NEW_SOURCES, 'x.id = t.id'))

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
    brows = [{'id': k, 'work_id': 'work-t300-312',
              'layer': {'bg-cs-scene': 'SCENE', 'bg-cs-city': 'CITY',
                        'bg-cs-world': 'WORLD', 'bg-cs-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（六句 2/2/1/1） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-312-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 42, 'Li Bai Spring Thought background layers (stage-D poem 23, six-line 2/2/1/1 second use): dating verdict seventeen, fifth shape of the title-evidence series and the first ventriloquism case -- the lyric I is a waiting wife, not the biographical Li Bai: both biographies record zero wife-and-children (the only wife-character in the whole XTS life spans his great-granddaughters -- er sun-nv jia wei min-qi, quoted verbatim), so the library refuses to write Li Bai missing his wife -- persona separation made explicit; the poem carries two places (Yan, Qin) and neither stands on either biography-s itinerary, a negative proof re-checked by the generator itself (zero occurrences of the characters Yan / You-zhou inside the Li-Bai biography spans, generation aborts otherwise); the Tongjian entry for 734 (You-zhou commissioner Zhang Shou-gui smashes the Khitan, captives presented) pins Yan as a frontier garrison zone with heading-position assertion per the V034 rule, yet touches the poem zero times -- a frontier victory in the annals never drags the poem in; the whole poem carries zero KNOWN ratings, recorded as-is rather than padded: the long-geng dream birth-legend is XTS-single and stays LIKELY; zero new sources besides exactly one opened here (quan-tang-shi juan 165 stub page, rollback deletes it)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 42);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V042 精确回滚：只删 V042 插入的行（id 全枚举）。',
         '-- work-t300-312 本体、其 text_line 6 行与 source-ws-t300-312 都是 V018 的行，绝不删；',
         '-- 共用 source 行（xintangshu-wenyi/tongjian）不删；V042 自开的 source-quantangshi-165 删除。',
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
    dels('poetry_source', 'id', ['source-quantangshi-165'])
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 42;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_FURTHER, WS_TITLE, WS_AUTHOR, WS_L12, WS_L12A, WS_L34, WS_L34A,
              WS_L56, WS_L56A, XTS_CG, XTS_HOU, TJ214_TITLE, TJ214_SK, QT_STUB]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # ws 零标记反向断言（消歧模板是计划内，允许 Further；通鉴帝标题的 {{*|干支}} 属另一来源不在此列）
    ws_ex = ''.join(ex for _, s, _, ex in CITATIONS if s == 'source-ws-t300-312')
    for tok in ('{{另', '{{别|', '{{*|'):
        if tok in ws_ex:
            bad.append(f'ws 零标记迁移的 ws 引文不得含 {tok}')
    if '{{Further|春思}}' not in flat:
        bad.append('{{Further|春思}} 消歧模板须照登在场')
    # 恰 1 新 source + 回滚同步删除
    if sql.count('INSERT INTO poetry_source') != 1:
        bad.append('V042 应恰有 1 个 poetry_source INSERT（source-quantangshi-165）')
    if "'source-quantangshi-165' AS id" not in sql:
        bad.append('新 source 应为 source-quantangshi-165')
    if "DELETE FROM poetry_source WHERE id IN ('source-quantangshi-165')" not in build_rollback():
        bad.append('回滚未删除 V042 自开的 source-quantangshi-165')
    # 通鉴 734 条断言
    w = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-cs-world')
    if '開元二十二年' not in w or '張守珪' not in w or '幽州' not in w:
        bad.append('通鉴 734 幽州条不齐（标题+节度+幽州）')
    # persona 分离断言：person 层引文须含访裔妻字句，claim 禁「李白思念妻子」句式
    p = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-cs-person')
    if '嫁為民妻' not in p or '長庚' not in p:
        bad.append('PERSON 层不齐（访裔妻字句+长庚句）')
    body_all = ''.join(BG.values()) + ''.join(v[2] for v in CLAIMS.values())
    if '李白思念妻子' not in body_all:
        bad.append('BG 须含「不写李白思念妻子」的显式否定句')
    # 整首零 KNOWN 如实断言
    if any(v[1] == 'KNOWN' for v in CLAIMS.values()):
        bad.append('V042 整首应为零 KNOWN（如实记录），出现了 KNOWN')
    # CITY 负证：引文零诗语地名
    for c, s, _, ex in CITATIONS:
        if c == 'claim-bg-cs-city':
            for w_ in ('燕草', '秦桑'):
                if w_ in ex:
                    bad.append(f'CITY 层证据不得含诗语「{w_}」（双城皆戏台=负证，不代拟进引文）')
    # 判例只引不重开
    for tok in ('竹溪六逸', '由是斥去', '醉死', '葬東麓', '凝碧', '謫仙'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 六句形制 2/2/1/1
    if BG_LINES != {'bg-cs-scene': (1, 2), 'bg-cs-city': (3, 4), 'bg-cs-world': (5,), 'bg-cs-person': (6,)}:
        bad.append('六句 background_line 必须 2/2/1/1')
    if len(re.findall(r"text-work-t300-312-ws' AS version_id", sql)) != 6:
        bad.append('bg_line INSERT 的 version 行数应为 6')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V042 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V042 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-312' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V042 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-312' AS subject_id" in sql:
        bad.append('V042 的 claim 主语应全部是 bg-cs-*，work-t300-312 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V042 不碰 poetry_text_line')
    if '诗语有地' not in body_all or '地不在传' not in body_all:
        bad.append('BG/claims 须含「诗语有地，地不在传」判决声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 14 切片逐字过审且全部进引文；'
              f'通鉴 734 帝标题位置断言（V034 立规）；传区间归属断言；'
              f'两传李白区间零燕/零幽州负证机器复查；ws 零标记反向断言+{{{{Further}}}} 照登断言；'
              f'persona 分离断言（访裔妻字句在场+显式否定句在场）；整首零 KNOWN 如实断言；'
              f'CITY 零诗语地名断言；判例只引不重开断言；六句 2/2/1/1 形制断言；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'恰 1 新 source+回滚同步删除断言；诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
