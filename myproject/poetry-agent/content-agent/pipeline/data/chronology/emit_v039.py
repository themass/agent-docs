#!/usr/bin/env python3
"""阶段 D 第 20 首：生成 V039——王维《終南別業》(work-t300-135, V018 已立) 四层背景。

「为什么写」第十二次成立，这次的钥匙藏在**第 1 句的自我报告**里：
「中歲頗好道」——诗人自陈中年转向，而两唐书各有一句独立直书接住它：
旧传「維弟兄俱奉佛，居常蔬食，不茹葷血，晚年長齋，不衣文綵」，
新传「兄弟皆篤志奉佛，食不葷，衣不文彩」——两源独立一致：
**王维兄弟终身奉佛（蔬食/不文彩两要素齐）升 KNOWN**，
诗的第一行不是修辞姿态，是两唐书联署的档案。

系年第十四次判决（与第十三次对偶成对）：**「题不系地，传不系年」**——
V038 是「题自带地名，传不纪其游」（题有地、传无路）；
这首正好反过来：**题只给别名（別業=别宅），不给可核之地；
两传明记一处别业却在蓝田輞川，无一字系「終南別業」之事**。
诗里「晚家南山陲」的南山与辋川（蓝田，终南支麓）之间隔着一步读法——
**不跨**。传里那处宅子与诗题这处宅子不互相认领。
time.span/event.name/written_during 零铸造，零 relation。

KNOWN 两处：①奉佛两源合龙（上）；②死状直书——旧「{{YL|乾元二年}}七月卒」
新「上元初卒，年六十一」，两源独立一致（乾元二年四月改元上元，
「七月卒」与「上元初」相容——相容不裁决，不硬判改元细节，
但「王维卒年两传俱在」这一存在性升 KNOWN，V037 先例）。
群像侧「诗名盛于开元、天宝间」两源独立出现——V035 已判 KNOWN，
本迁移**不重复裁决**，引先例并声明。

异文三连照登：题目自注 {{*|一作初至山中，一作入山寄城中故人}} +
三处 {{另}}（空/祗、值/見+林/鄰、無/滯）——variants.md 已先登记；
V018 正文首读（空/值/林/無）不动，引文含标记原样。

八句第二用：background_line 每层 2 行（1-2/3-4/5-6/7-8），audit 形制断言。

用法: python3 -I emit_v039.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/終南別業.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
QT126 = pathlib.Path('/tmp/src-dl/quantangshi/vol126.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 終南別業{{*|一作初至山中，一作入山寄城中故人}}',
                         '| title    = 終南別業{{*|一作初至山中，一作入山寄城中故人}}',
                         'ws header title(含题目自注{{*}}——别名线,标记照录)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', 'author   = 王維', 'ws header author(署名直证)')
WS_L12 = slice_between(WS, '中歲頗好道，晚家南山陲。', '晚家南山陲。', 'ws第1-2句联(中岁好道/晚家南山陲)')
WS_L34 = slice_between(WS, '興來每獨往，勝事{{另|空|祗}}自知。', '勝事{{另|空|祗}}自知。',
                       'ws第3-4句联(独往/自知——{{另|空|祗}}标记原样)')
WS_L56 = slice_between(WS, '行到水窮處，坐看雲起時。', '坐看雲起時。', 'ws第5-6句联(水穷云起)')
WS_L78 = slice_between(WS, '偶然{{另|值|見}}{{另|林|鄰}}叟，談笑{{另|無|滯}}還期。', '談笑{{另|無|滯}}還期。',
                       'ws第7-8句联(林叟/无还期——{{另}}×3标记原样)')
JTS_FF = slice_between(JTS, '維弟兄俱奉佛，居常蔬食，不茹葷血，晚年長齋，不衣文綵。', '不衣文綵。',
                       '旧传奉佛段(俱奉佛/蔬食/长斋/不衣文彩——奉佛两源合龙旧传侧)')
JTS_ZU = slice_between(JTS, '{{YL|乾元二年}}七月卒。臨終之際，以縉在鳳翔，忽索筆作别縉書，又與平生親故作别書數幅，多敦厲朋友奉佛脩心之旨，捨筆而絶。',
                       '捨筆而絶。', '旧传卒段(乾元二年七月卒/临终作书——死状直书旧传侧)')
JTS_WC = slice_between(JTS, '得宋之問藍田别墅，在輞口，輞水周於舍下，别漲竹洲花塢，與道友裴廸浮舟往來，彈琴賦詩，嘯詠終日。甞聚其田園所為詩，號輞川集。',
                       '號輞川集。', '旧传辋川段(传中唯一明记别业=蓝田辋川——V035 已立此句,此处别名侧再证;不系终南事为负证)')
XTS_FF = slice_between(XTS, '兄弟皆篤志奉佛，食不葷，衣不文彩。', '衣不文彩。',
                       '新传奉佛段(笃志奉佛/食不荤/衣不文彩——奉佛两源合龙新传侧)')
XTS_ZU = slice_between(XTS, '上元初卒，年六十一。疾甚，縉在鳳翔，作書與別，又遺親故書數幅，停筆而化。',
                       '停筆而化。', '新传卒段(上元初卒/年六十一/停筆而化——死状直书新传侧,与旧传乾元二年相容不裁决;「贈秘書監」四字卷202两处,终点锚收到停筆而化)')
XTS_WC = slice_between(XTS, '別墅在輞川，地奇勝，有華子岡、欹湖、竹裏館、柳浪、茱萸沜、辛夷塢，與裴迪遊其中，賦詩相酬為樂。',
                       '賦詩相酬為樂。', '新传辋川段(新传明记别墅亦唯一=辋川——V035 已立此句,此处别名侧再证)')
QT_STUB = slice_between(QT126, '==[[終南別業]]==\n{{:終南別業}}', '{{:終南別業}}',
                        '全唐诗卷126本诗条目(锚点+转引用桩——卷页无正文)')

# 传区间归属复验（V036 立规）
_ja, _jb = JTS.find('=王維='), JTS.find('=李白=')
_xa, _xb = XTS.find('==王維=='), XTS.find('==鄭虔==')
for _s, _tag in [(JTS_FF, 'JTS_FF'), (JTS_ZU, 'JTS_ZU'), (JTS_WC, 'JTS_WC')]:
    if not (_ja <= JTS.find(_s) <= _jb):
        raise SystemExit(f'切片越出王维传区间：{_tag}——修订后重生成')
for _s, _tag in [(XTS_FF, 'XTS_FF'), (XTS_ZU, 'XTS_ZU'), (XTS_WC, 'XTS_WC')]:
    if not (_xa <= XTS.find(_s) <= _xb):
        raise SystemExit(f'切片越出王维传区块：{_tag}——修订后重生成')

BG = {
    'bg-zn-scene': (
        '这首诗的前四句是一条完整的私人日志：「中歲頗好道，晚家南山陲」——'
        '中年起开始偏好那条路，晚年把家安到南山的边上；「興來每獨往，'
        '勝事{{另|空|祗}}自知」——兴头来了就一个人去，好处只有自己能知道'
        '（页内空/祗异读照登不裁决，V018 正文取首读「空」）。\n'
        '后四句把这条日志写绝了：「行到水窮處，坐看雲起時」——走到水的尽头就坐下，'
        '看云起来；「偶然{{另|值|見}}{{另|林|鄰}}叟，談笑{{另|無|滯}}還期」——'
        '碰巧遇到个老人，谈笑之间就把回家的日子忘了（值/見、林/鄰、無/滯三对页内'
        '异读照登）。全诗没有一个事件——「偶然」两个字自己就是反纪年：'
        '这首诗拒绝被写进任何年谱。'),
    'bg-zn-city': (
        '「終南別業」是个**别名**不是地址：別業=别宅，题里只有「在終南那边有处宅子」'
        '的口气，没有可核之地；页上题目自注「一作初至山中，一作入山寄城中故人」'
        '——连诗题本身在两读之间（照登不裁决）。\n'
        '而两传明记的那处别业在别处：旧传「得宋之問藍田别墅，在輞口，輞水周於舍下」，'
        '新传「別墅在輞川，地奇勝」——两传各有且只有一处宅子，都在蓝田辋川，'
        '传中无一字系「終南別業」之事。**不跨读**：辋川在蓝田、终南有支麓，'
        '两步读法能把「南山陲」挪去辋川——但那不是史料。「晚家南山陲」不指认'
        '蓝田别墅；两处宅子互不认领。题不系地，传不系年。'),
    'bg-zn-world': (
        '「中歲頗好道」的自我报告，两唐书各有一句独立直书接住：\n'
        '旧传「維弟兄俱奉佛，居常蔬食，不茹葷血，晚年長齋，不衣文綵」；'
        '新传「兄弟皆篤志奉佛，食不葷，衣不文彩」——措辞各自成句、要素两两相当'
        '（俱/皆奉佛、蔬食/食不葷、不衣文綵/衣不文彩）：**王维兄弟终身奉佛升 KNOWN**'
        '（两源独立一致）。\n'
        '于是「好道」不再是可以打折的诗人套话——开天年间奉佛是上层士人的空气，'
        '两传把王维一家钉在这团空气里；但**具体哪一年开始蔬食长斋，两传不给**——'
        '中岁就是中岁。群像侧「诗名盛于開元、天寶間」两源亦俱在——'
        'V035 已判 KNOWN，此处不重复裁决只引先例。'),
    'bg-zn-person': (
        '王维的死状两传直书俱在：旧传「{{YL|乾元二年}}七月卒。臨終之際，以縉在鳳翔，'
        '忽索筆作别縉書……捨筆而絶」；新传「上元初卒，年六十一。疾甚，縉在鳳翔，'
        '作書與別……停筆而化」——两源独立一致（乾元二年四月改元上元，'
        '七月与上元初相容；相容即并列，改元细节不裁决，V037 先例），'
        '「卒年两传俱在」升 KNOWN。两传同记的临终一幕更冷：弟弟王縉在凤翔行在，'
        '他索笔写别书——连告别都是公文的方向；遗书里「多敦厲朋友奉佛脩心之旨」，'
        '到最后一笔还是把朋友往那条路上推。\n'
        '鳏居条（旧「妻亡不再娶」/新「喪妻不娶，孤居三十年」）V037 已两源合龙判过，'
        '本处不重开只声明。传中辋川宅与诗题別業互不认领——王维有几处宅子，'
        '史料说得清的只有一处，诗里这处说得清名字，说不清在哪。'),
}
CLAIMS = {
    'claim-bg-zn-scene': (
        'FACT', 'LIKELY',
        '前四句私人日志/后四句反纪年全诗本文（题目自注一作两题+四处 {{另}} 页内异文'
        '首读照登、variants.md 先登记）；「偶然」自拒系年为本层读法声明，非史料断言。'),
    'claim-bg-zn-city': (
        'FACT', 'LIKELY',
        '题=别名非地址（{{*}}自注两题照登）；两传明记别业各唯一=蓝田辋川'
        '（旧「得宋之問藍田别墅在輞口」/新「別墅在輞川」——V035 已立两源，'
        '此处别名侧再证）；传零系「終南別業」事（负证）；'
        '南山陲↔辋川两步读法不跨；题不系地、传不系年→零铸造零 relation。'),
    'claim-bg-zn-world': (
        'FACT', 'KNOWN',
        '王维兄弟终身奉佛两源独立一致：旧传「俱奉佛/蔬食/長齋/不衣文綵」+新传'
        '「篤志奉佛/食不葷/衣不文彩」要素两两相当各成句→升 KNOWN；'
        '奉佛起年两传零载不外推；「诗名盛于开元天宝间」V035 已判 KNOWN 不重复裁决；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-zn-person': (
        'FACT', 'KNOWN',
        '卒年两传直书俱在（旧「{{YL|乾元二年}}七月卒」/新「上元初卒，年六十一」，'
        '相容并列不裁决改元细节）→存在性 KNOWN（V037 先例）；临终别书两传同幕'
        '（弟在凤翔/索笔作书）；鳏居条 V037 已判不重开；辋川宅与诗题別業互不认领'
        '为本层边界声明；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-zn-scene', 'source-ws-t300-135',
     '页面 終南別業（header title 含题目自注 {{*}}+author 字段+八句全文，五段以「……」相連——'
     '四处 {{另}} 标记原样入证；V018 正文取首读，variants.md 已先登记；'
     '一句一对会把同一 (claim,source) 拆成八行违反主键——全文一行，V037 判例）',
     join(WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56, WS_L78)),
    ('claim-bg-zn-city', 'source-quantangshi-126',
     '卷一百二十六·王维诗目下本诗条目（锚点+转引用桩——卷页无正文，桩文照登；'
     '来源行 V035 已立，此处零新开）', QT_STUB),
    ('claim-bg-zn-city', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传辋川段（旧传明记别业唯一=蓝田輞口，零「終南別業」'
     '系事之负证在此段；V035 已立此句（辋川线），此处别名侧再证——跨迁移同句'
     '再证，claim 不同故主键不冲突）', JTS_WC),
    ('claim-bg-zn-city', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王维传辋川段（新传明记别墅唯一=輞川；V035 已立此句，'
     '此处别名侧再证）', XTS_WC),
    ('claim-bg-zn-world', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传奉佛段（俱奉佛/蔬食/长斋/不衣文綵——两源合龙旧传侧逐字）',
     JTS_FF),
    ('claim-bg-zn-world', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王维传奉佛段（笃志奉佛/食不葷/衣不文彩——两源合龙新传侧逐字）',
     XTS_FF),
    ('claim-bg-zn-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传卒段（乾元二年七月卒/临终别缙书/敦厉奉佛——直书旧传侧；'
     '{{YL|乾元二年}} 系快照年份链接模板标记，随文原样保留，非异文不入登记）',
     JTS_ZU),
    ('claim-bg-zn-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王维传卒段（上元初卒/年六十一/停筆而化——直书新传侧，相容并列）',
     XTS_ZU),
]
BG_LINES = {'bg-zn-scene': (1, 2), 'bg-zn-city': (3, 4), 'bg-zn-world': (5, 6), 'bg-zn-person': (7, 8)}
BG_AUDIENCE = {'bg-zn-scene': 'PRIMARY', 'bg-zn-city': 'JUNIOR',
               'bg-zn-world': 'SENIOR', 'bg-zn-person': 'SENIOR'}
BG_TITLES = {'bg-zn-scene': '眼前：走到水尽处坐下',
             'bg-zn-city': '这座城：别名里的宅子',
             'bg-zn-world': '这个天下：两唐书联署的素食',
             'bg-zn-person': '这个人：最后一笔还是那条路'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 20 首·八句 2/2/2/2 第二用）；史实句均有逐字引证；'
                 'background_line 八句形制：每层两行（1-2/3-4/5-6/7-8）；'
                 '系年第十四次判决「题不系地，传不系年」（与第十三次对偶）→time.span/'
                 'event.name/written_during 全缺席、零 relation；KNOWN 两处（奉佛两源合龙+'
                 '卒年两传直书俱在）；鳏居 V037/诗名 V035 判例只引不重开；'
                 '题目自注+四处 {{另}} 先登记后照登。' for k in BG}


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
    A("""-- V039：王维《終南別業》(work-t300-135) 四层背景（阶段 D 第 20 首·八句 2/2/2/2 第二用）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-135 与其 text-work-t300-135-ws、
--       source-ws-t300-135 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行；source-quantangshi-126 是 V035 的行——均不另开）。
--       本迁移零新 source（断言）。
--
-- 数据源（可复现）：emit_v039.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/終南別業.txt（题目自注 {{*|一作…}} 与三处 {{另}} 标记原样——variants.md 先登记后照登）、
--   舊唐書卷190下（王维传奉佛段+卒段+辋川段——辋川段 V035 已立，别名侧再证声明入 locator）、
--   新唐書卷202（王维传奉佛段+卒段+辋川段——切片传区间归属生成时断言）。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   9 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句形制：scene→1-2 city→3-4 world→5-6 person→7-8，
--   绑 text-work-t300-135-ws 的 8 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界与 V038 对偶成对）：
--   * 题=别名（別業=别宅）非地址，题目自注两题照登不裁决；
--   * 两传明记别业各唯一=蓝田辋川，零「終南別業」系事（负证逐字立出）；
--     「晚家南山陲」不指认蓝田别墅——两处宅子互不认领，两步读法不跨；
--   * 系年第十四次判决「题不系地，传不系年」→零铸造零 relation；
--   * KNOWN 两处：奉佛（旧「俱奉佛…不衣文綵」+新「篤志奉佛…衣不文彩」两源合龙）、
--     卒年存在性（旧「{{YL|乾元二年}}七月卒」+新「上元初卒，年六十一」相容并列，
--     改元细节不裁决）；均不外溢到诗；
--   * 鳏居条 V037 已判、诗名段 V035 已判——只引先例不重开（BG 与文件头双声明）；
--   * 跨迁移同句再证合规声明：JTS_WC/XTS_WC（V035 辋川线）此处别名侧再证。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 38，不含 39
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-zn-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-135-ws';  -- 恰 8（五律）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-zn-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-135';                                  -- 8（每层两行）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-zn-world','claim-bg-zn-person');
--     -- KNOWN / KNOWN（world=奉佛两源；person=卒年两传直书）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-zn-scene','claim-bg-zn-city');
--     -- LIKELY / LIKELY
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-135'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-135';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-zn-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V039_rollback.sql（按 id 全枚举删除；不动 V018/V035 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-135',
              'layer': {'bg-zn-scene': 'SCENE', 'bg-zn-city': 'CITY',
                        'bg-zn-world': 'WORLD', 'bg-zn-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（八句：每层两行） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-135-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 39, 'Wang Wei Zhong-nan Bie-ye background layers (stage-D poem 20, 2/2/2/2 second use): dating verdict fourteen, the mirror pair of thirteen -- thirteen said the title carries the place while biographies record no such journey; here the reverse -- the title gives only an alias (bie-ye = a second house, no checkable site; the page carries two alternative titles under {{*}}, registered before quoting) and both biographies name exactly one estate each, both at Lan-tian Wang-chuan (JTS de Song zhi-wen Lan-tian bieshu zai Wang-kou + XTS bieshu zai Wang-chuan, both re-cited from V035 on the alias side -- cross-migration lawful, different claims), with zero lines tying the poem-title to any annalistic event -- the two houses never claim each other and the two-step reading that would move nan-shan chui onto the Wang river is refused: title pins no site, biographies pin no year, so time.span/event.name/written_during stay absent with zero relations; first KNOWN: the family devotion to Buddhism, JTS ju feng-fo / shu-shi / bu yi wen-cai plus XTS du-zhi feng-fo / shi bu hun / yi bu wen-cai -- two independent wordings, matching element by element; no year is inferred for the turn, zhong-sui stays zhong-sui; second KNOWN (existence-only): both biographies state his death outright (JTS Qian-yuan 2 7th month vs XTS Shang-yuan early, age 61) -- compatible, listed side by side, no ruling on the reign-name switch (V037 precedent); the widower line already KNOWN via V037 and the fame line already KNOWN via V035 are cited as precedents, not re-ruled; zero new sources (quan-tang-shi juan 126 opened by V035)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 39);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V039 精确回滚：只删 V039 插入的行（id 全枚举）。',
         '-- work-t300-135 本体、其 text_line 8 行与 source-ws-t300-135 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi/quantangshi-126）与 V035 的行不删；',
         '-- V039 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 39;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56, WS_L78,
              JTS_FF, JTS_ZU, JTS_WC, XTS_FF, XTS_ZU, XTS_WC, QT_STUB]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 异文标记照录断言：题目自注 + 三处 {{另}} 原样在场
    for tok in ('{{*|一作初至山中', '{{另|空|祗}}', '{{另|值|見}}', '{{另|林|鄰}}', '{{另|無|滯}}'):
        if tok not in flat:
            bad.append(f'异文/自注标记须原样在场: {tok}')
    # 奉佛两源断言：两侧关键词各在其引文且要素齐
    f_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-zn-world' and s == 'source-jiutangshu-wenyuan')
    f_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-zn-world' and s == 'source-xintangshu-wenyi')
    if not ('奉佛' in f_jts and '蔬食' in f_jts and '不衣文綵' in f_jts):
        bad.append('旧传奉佛段要素不齐（俱奉佛/蔬食/不衣文綵）')
    if not ('奉佛' in f_xts and '食不葷' in f_xts and '衣不文彩' in f_xts):
        bad.append('新传奉佛段要素不齐（篤志奉佛/食不葷/衣不文彩）')
    # 卒年两源断言
    d_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-zn-person' and s == 'source-jiutangshu-wenyuan')
    d_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-zn-person' and s == 'source-xintangshu-wenyi')
    if '乾元二年' not in d_jts or '上元初卒' not in d_xts or '年六十一' not in d_xts:
        bad.append('卒年两传直书不齐')
    # 别名侧：两传辋川切片在 CITY 层且南山二字不得入 CITY 证据（负证据不代拟）
    for c, s, _, ex in CITATIONS:
        if c == 'claim-bg-zn-city' and '南山陲' in ex:
            bad.append('CITY 层证据不得含诗语「南山陲」（两传零系事=负证，不代拟进引文）')
    # 只引不重开：鳏居句/诗名段关键语不得入本迁移任何引文
    for tok in ('妻亡不再娶', '喪妻不娶', '孤居三十年', '名盛於開元'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句形制：每层恰 2 行，合计 8
    if sum(len(v) for v in BG_LINES.values()) != 8 or any(len(v) != 2 for v in BG_LINES.values()):
        bad.append('八句 background_line 必须是每层恰 2 行（4 层共 8 行）')
    if len(re.findall(r"text-work-t300-135-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V039 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V039 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-135' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V039 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-135' AS subject_id" in sql:
        bad.append('V039 的 claim 主语应全部是 bg-zn-*，work-t300-135 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V039 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V039 零新 source（卷126 已 V035 开立），不该出现 INSERT INTO poetry_source')
    # 「题不系地，传不系年」声明必须在 BG 与文件头双处
    body_all = ''.join(BG.values()) + sql
    if '题不系地' not in body_all or '传不系年' not in body_all:
        bad.append('BG/文件头须含「题不系地，传不系年」判决声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 13 切片逐字过审且全部进引文；'
              f'切片传区间归属断言；奉佛两源/卒年两源断言；CITY 负证不含诗语断言；'
              f'判例只引不重开断言（鳏居/诗名关键语零入引文）；'
              f'题目自注+四处 {{{{另}}}} 标记照录断言；八句每层两行形制断言；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'零新 source 已断言；诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
