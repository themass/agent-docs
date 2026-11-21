#!/usr/bin/env python3
"""阶段 D 第 21 首：生成 V040——王维《九月九日憶山東兄弟》(work-t300-148, V018 已立) 四层背景。

「为什么写」第十三次成立，钥匙是**两个「兄弟」的错位**：
诗题里想的是兄弟，两传里写得最实的兄弟关系却只有弟弟王縉——
旧传「與弟縉俱有俊才，博學多藝亦齊名，閨門友悌，多士推之」+
新传「九歲知屬辭，與弟縉齊名，資孝友」：**王维与弟縉齐名友悌两源合龙 KNOWN**。
「山東兄弟」是谁，两传零字——不发明。

系年第十五次判决（题证系列第三状）：**「页注系年，史无系年」**——
维基文库页底整理者注「時年十七」给了一年（十七岁≈开元五年上下），
通鉴两条重阳条（695 刘知几表、819 李玨疏）年份本地位置核验可钉，
却都不涉此诗。底注是底注，史料是史料：
「時年十七」照登、标明系整理者注无出处、不入库为史实——
time.span/event.name/written_during 零铸造，零 relation。

KNOWN 两处：①兄弟齐名友悌（上）；②「徙家于蒲，遂為河東人」旧传单得——**不升**
（单源 LIKELY；「山東」与河東/蒲的地理纠葛全在推定层，BG 声明不裁决）。
临终别书一幕（新传「疾甚，縉在鳳翔，作書與別」）与「己有五短，縉五長」自表
让兄弟线在 PERSON 层闭合：他一生给弟弟写的信，传里存了两封。

异文照登：「{{别|為|爲}}」页内标记原样入引文（variants.md 先登记）；
V018 正文取首读「爲」；页底注「時年十七」随引文照登并声明非史料。

绝句第二用：background_line 每层 1 行（1/2/3/4）。

用法: python3 -I emit_v040.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/九月九日憶山東兄弟.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
QT128 = pathlib.Path('/tmp/src-dl/quantangshi/vol128.txt').read_text(encoding='utf-8')
TJ205 = pathlib.Path('/tmp/src-dl/tongjian/tj-205.txt').read_text(encoding='utf-8')
TJ241 = pathlib.Path('/tmp/src-dl/tongjian/tj-241.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
# L1 含 {{别|為|爲}} 标记原样（V031 判例；variants.md 已先登记）
WS_TITLE = slice_between(WS, '| title    = 九月九日憶山東兄弟', '| title    = 九月九日憶山東兄弟',
                         'ws header title(节令+山東+兄弟三题眼)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', 'author   = 王維', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '[[全唐詩/卷128#九月九日憶山東兄弟|全唐詩·卷128]]時年十七',
                        '時年十七', 'ws notes行尾整理者注(時年十七——无出处底注,照登并声明非史料)')
WS_L1 = slice_between(WS, '獨在異鄉{{别|為|爲}}異客，每逢佳節倍思親。', '每逢佳節倍思親。',
                      'ws第1-2句联(异乡异客/佳节思亲——{{别|為|爲}}标记在其句,联引含之)')
WS_L1A = slice_between(WS, '獨在異鄉{{别|為|爲}}異客，每逢佳節倍思親。', '獨在異鄉{{别|為|爲}}異客，',
                       'ws第1句(含{{别|為|爲}}标记原样)')
WS_L2 = slice_between(WS, '遙知兄弟登高處，遍插茱萸少一人。', '遍插茱萸少一人。', 'ws第3-4句联(遥知登高/少一人)')
WS_L2A = slice_between(WS, '遙知兄弟登高處，遍插茱萸少一人。', '遙知兄弟登高處，', 'ws第3句(遥知兄弟登高处)')
JTS_XJ = slice_between(JTS, '父處㢘，終汾州司馬，徙家于蒲，遂為河東人。', '徙家于蒲，遂為河東人。',
                       '旧传籍贯段(徙家于蒲/河东人——單源不升,「山东」纠葛声明在BG)')
JTS_DI = slice_between(JTS, '與弟縉俱有俊才，博學多藝亦齊名，閨門友悌，多士推之。', '多士推之。',
                       '旧传兄弟段(俱俊才/齐名/闺门友悌——兄弟两源合龙旧传侧)')
XTS_DI = slice_between(XTS, '九歲知屬辭，與弟縉齊名，資孝友。', '資孝友。',
                       '新传兄弟段(九岁属辞/齐名/孝友——兄弟两源合龙新传侧)')
XTS_BB = slice_between(XTS, '己有五短，縉五長，臣在省戶，縉遠方，願歸所任官，放田里，使縉得還京師。',
                       '使縉得還京師。', '新传自表段(五短五长/愿还官放田里——兄弟线制度形状,新传单得)')
QT_STUB = slice_between(QT128, '==[[九月九日憶山東兄弟]]==\n{{:九月九日憶山東兄弟}}', '{{:九月九日憶山東兄弟}}',
                        '全唐诗卷128本诗条目(锚点+转引用桩——卷页无正文;来源行V026已立)')
TJ205_TITLE = slice_between(TJ205, '上天冊萬歲元年（乙未，公元六九五年）', '上天冊萬歲元年（乙未，公元六九五年）',
                            '通鉴205卷695年标题(生成器位置断言：刘知几条在此标题与696标题之间)')
TJ205_LZJ = slice_between(TJ205, '獲嘉主簿彭城劉知幾表陳四事。', '佇降皇恩',
                          '通鉴695刘知几条(起句至「重陽之節，佇降皇恩」——节日入正史语料本体入证,与诗零关联)')
TJ241_TITLE = slice_between(TJ241, '元和十四年（己亥，公元八一九年）', '元和十四年（己亥，公元八一九年）',
                            '通鉴241卷819年标题(生成器位置断言：重阳大宴条在此标题与821标题之间)')
TJ241_CX = slice_between(TJ241, '九月，欲以重陽大宴。拾遺李玨帥其同僚上疏', '拾遺李玨帥其同僚上疏',
                         '通鉴819重阳大宴条(宫廷重阳宴+谏疏——节日制度侧语料,与诗零关联)')

# ---------- 生成时硬断言：年标题位置归属（V034 立规） ----------
_i = TJ205.find('重陽之節')
_a, _b = TJ205.find('上天冊萬歲元年'), TJ205.find('上萬歲通天元年')
if not (0 <= _a < _i < _b):
    raise SystemExit('刘知几条重阳语不在695年标题区间内——修订后重生成')
_j = TJ241.find('欲以重陽大宴')
_c, _d = TJ241.find('元和十四年（己亥'), TJ241.find('皇帝下長慶元年')
if not (0 <= _c < _j < _d):
    raise SystemExit('重阳大宴条不在819年标题区间内——修订后重生成')
# 传区间归属复验（V036 立规）
_ja, _jb = JTS.find('=王維='), JTS.find('=李白=')
_xa, _xb = XTS.find('==王維=='), XTS.find('==鄭虔==')
for _s, _tag in [(JTS_XJ, 'JTS_XJ'), (JTS_DI, 'JTS_DI')]:
    if not (_ja <= JTS.find(_s) <= _jb):
        raise SystemExit(f'切片越出王维传区间：{_tag}——修订后重生成')
for _s, _tag in [(XTS_DI, 'XTS_DI'), (XTS_BB, 'XTS_BB')]:
    if not (_xa <= XTS.find(_s) <= _xb):
        raise SystemExit(f'切片越出王维传区块：{_tag}——修订后重生成')

BG = {
    'bg-99-scene': (
        '诗只给了四件事：一个人在外地（「獨在異鄉{{别|為|爲}}異客」，'
        '页内為/爲异读照登不裁决，V018 正文取首读「爲」）；'
        '今天是个好节日，而且**每**逢都加倍（「每逢佳節倍思親」——不是今天才想）；'
        '他想象远方：兄弟们登高，每人插着茱萸，数下来少一个'
        '（「遙知兄弟登高處，遍插茱萸少一人」）。全诗没有一处实景——'
        '只有缺席者对在场的想象。茱萸是重阳的佩戴物，「少一人」是缺席者'
        '替在场者补出来的缺口。\n'
        '页底整理者注「時年十七」给了个年纪——**照登，标明系底注无出处**：'
        '注者说十七岁写的，注者没说注者是谁。'),
    'bg-99-city': (
        '题里的「山東」是这首诗最大的悬案：题眼「九月九日」有节令、'
        '「兄弟」有人，「山東」有方向却没有可核之地。旧传给王维家的地址：'
        '「父處㢘，終汾州司馬，徙家于蒲，遂為河東人」——**河东**，蒲州，'
        '在山西，不在太行山之东；新传连地址都不给。旧传单源，不升。\n'
        '于是「山東兄弟」至少有三种读法（故里在他乡人对故乡的称呼/兄弟真在山东/语感词）'
        '——史料一种都不支持裁决，BG 到此为止：节令真实（重阳）、方向存疑（山東）、'
        '兄弟无名（零记载）。题证节令，不证地理。'),
    'bg-99-world': (
        '重阳在正史里的样子，本迁移用通鉴两条**位置核验**的条目立起来：'
        '695 年（上天冊萬歲元年）条内刘知几表陈四事，抱怨朝廷滥赦——'
        '「元日之朝，指期天澤，重陽之節，佇降皇恩」：连最无赖的人都把重阳'
        '当作等恩赦的日子；819 年（元和十四年）条「九月，欲以重陽大宴」，'
        '拾遗李玨率同僚上疏谏止——皇帝想在重阳办大宴，谏官把它当国事拦。'
        '两条各在其年标题区间内（生成器位置断言，V034 立规）。\n'
        '这就是王维那个「佳節」的天下形状：重阳是**国家日程**——'
        '恩赦候它，宴饮候它，谏疏也候它；诗把它当私人记忆的容器用。'
        '两条通鉴与王维**零关联**——节令入正史不意味诗入正史。'),
    'bg-99-person': (
        '两传写得最实的兄弟关系是**弟弟王縉**：旧传「與弟縉俱有俊才，'
        '博學多藝亦齊名，閨門友悌，多士推之」+新传「九歲知屬辭，與弟縉齊名，'
        '資孝友」——齐名与友悌/孝友要素两两相当，**王维兄弟友悌升 KNOWN**（两源合龙）。\n'
        '但诗题「山東兄弟」不是王縉的实名的任何一步：两传只给一个弟弟，'
        '给不出「山東」那一群——兄弟几人不载，不发明。\n'
        '兄弟线在传里有两封存信：新传王维自表「己有五短，縉五長，臣在省戶，'
        '縉遠方，願歸所任官，放田里，使縉得還京師」——拿自己的官换弟弟回京；'
        '临终「疾甚，縉在鳳翔，作書與別」——最后一封信还是给弟弟的'
        '（V039 已直书卒段，此处只引别书一句续线，不重开卒年裁决）。'
        '他一生写给兄弟的信，传里存了两封；诗里这首，传里不收。'),
}
CLAIMS = {
    'claim-bg-99-scene': (
        'FACT', 'LIKELY',
        '四句全诗本文（{{别|為|爲}} 页内标记首读爲照登，variants.md 先登记；'
        '缺席者想象在场为本层读法声明）；页底「時年十七」系整理者注无出处——'
        '照登入引文但明标非史料，不入库为事实。'),
    'claim-bg-99-city': (
        'FACT', 'LIKELY',
        '题证节令（重阳）不证地理：旧传籍贯「徙家于蒲，遂為河東人」单源 LIKELY，'
        '新传零地址；「山東」三读法并列不裁决（负证：两传零山东记载）；'
        '兄弟不载名数，不发明。'),
    'claim-bg-99-world': (
        'FACT', 'LIKELY',
        '重阳=国家日程两条通鉴条目（695 刘知几表「重陽之節，佇降皇恩」/819'
        '「九月，欲以重陽大宴」+李玨疏）各在其年标题区间内（生成时位置断言，'
        'V034 立规）；两条与王维零关联——节令入正史不推及诗入正史；'
        '诗 time.span/event.name/written_during 零铸造、零 relation。'),
    'claim-bg-99-person': (
        'FACT', 'KNOWN',
        '王维与弟縉齐名友悌两源独立一致（旧「俱有俊才…齊名，閨門友悌」/新'
        '「與弟縉齊名，資孝友」）→升 KNOWN；兄弟数人山东一差不载，不外溢；'
        '自表换官+临终别书新传单得 LIKELY 级细节（V039 卒段只引不重开）；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-99-scene', 'source-ws-t300-148',
     '页面 九月九日憶山東兄弟（header title+author+notes 行尾整理者注「時年十七」+四句全文，'
     '六段以「……」相連——第1句含页内异文标记 {{别|為|爲}} 原样入证'
     '（V018 正文取首读爲，variants.md 已先登记）；「時年十七」照登并声明系'
     '整理者注无出处、非史料；同一 (claim,source) 主键下一行容全文，V037/V039 判例）',
     join(WS_TITLE, WS_AUTHOR, WS_NOTE, WS_L1A, WS_L1, WS_L2A, WS_L2)),
    ('claim-bg-99-city', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传籍贯段（徙家于蒲/河东人——单源不升；'
     '「山東」零记载之负证在本段；「河东在山西」是今地理常识注非本证）', JTS_XJ),
    ('claim-bg-99-world', 'source-zizhi-tongjian-events',
     '通鉴卷二百零五·上天冊萬歲元年（695）条+卷二百四十一·元和十四年（819）条'
     '（两条四段以「……」相連，同一 (claim,source) 主键一行，V037/V039 判例——'
     '695：年标题+刘知几表陈四事至「重陽之節，佇降皇恩」，生成时位置断言：'
     '语在695与696标题之间；819：年标题+「九月，欲以重陽大宴」李玨上疏，'
     '生成时位置断言：条在819与821标题之间；两条与王维零关联）',
     join(TJ205_TITLE, TJ205_LZJ, TJ241_TITLE, TJ241_CX)),
    ('claim-bg-99-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传兄弟段（俱俊才/齐名/闺门友悌——两源合龙旧传侧逐字）',
     JTS_DI),
    ('claim-bg-99-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王维传（九岁属辞/齐名孝友段+自表换官段以「……」相連；'
     '同卷同传——齐名两源合龙新传侧/五短五长单得；临终别书 V039 已立不重开）',
     join(XTS_DI, XTS_BB)),
    ('claim-bg-99-city', 'source-quantangshi-128',
     '卷一百二十八·王维诗目下本诗条目（锚点+转引用桩——卷页无正文，桩文照登；'
     '来源行 V026 已立，此处零新开）', QT_STUB),
]
BG_LINES = {'bg-99-scene': (1,), 'bg-99-city': (2,), 'bg-99-world': (3,), 'bg-99-person': (4,)}
BG_AUDIENCE = {'bg-99-scene': 'PRIMARY', 'bg-99-city': 'JUNIOR',
               'bg-99-world': 'SENIOR', 'bg-99-person': 'SENIOR'}
BG_TITLES = {'bg-99-scene': '眼前：数出来的缺口',
             'bg-99-city': '这座城：河东人说山東',
             'bg-99-world': '这个天下：重阳是国家日程',
             'bg-99-person': '这个人：传里存了两封给弟弟的信'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 21 首·绝句第二用）；史实句均有逐字引证；'
                 'background_line 绝句形制：每层一行（1/2/3/4）；'
                 '系年第十五次判决「页注系年，史无系年」（题证系列第三状：页底整理者注'
                 '「時年十七」照登标非史料）→time.span/event.name/written_during 全缺席、'
                 '零 relation；KNOWN 一处（兄弟齐名友悌两源合龙）；通鉴两条重阳条'
                 '年标题位置断言（V034 立规）；{{别|為|爲}} 先登记后照登。' for k in BG}


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
    A("""-- V040：王维《九月九日憶山東兄弟》(work-t300-148) 四层背景（阶段 D 第 21 首·绝句第二用）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-148 与其 text-work-t300-148-ws、
--       source-ws-t300-148 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行；source-quantangshi-128 是 V026 的行；source-zizhi-tongjian-events
--       早期迁移已立——均不另开）。本迁移零新 source（断言）。
--
-- 数据源（可复现）：emit_v040.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/九月九日憶山東兄弟.txt（{{别|為|爲}} 标记原样+页底整理者注「時年十七」照登
--   并声明非史料——variants.md 先登记后照登）、
--   舊唐書卷190下（王维传籍贯段+兄弟段）、新唐書卷202（兄弟段+自表换官段；
--   切片传区间归属生成时断言）、
--   通鉴 tj-205（695 刘知几条）+tj-241（819 重阳大宴条）——两条目均生成时
--   位置断言其落在各自年标题区间内（V034 年标题归属立规）。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   8 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 行 background_line（**绝句形制：每层一行** scene→1 city→2 world→3 person→4，
--   绑 text-work-t300-148-ws 的 4 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「页注系年，史无系年」）：
--   * 页底注「時年十七」系整理者注无出处——照登入引文、标非史料、不入库为事实；
--   * 通鉴两条重阳条年份可钉（位置断言）但与王维零关联——节令入正史不推及诗；
--   * 「山東」零史料（旧传单得河东/新传零地址）——三读法并列不裁决，兄弟不发明；
--   * KNOWN 一处：兄弟齐名友悌两源合龙；不外溢到诗（诗 time.span/event.name/
--     written_during 零铸造、零 relation）；
--   * V039 卒段只引别书一句续线不重开；鳏居/奉佛等判例不入本迁移（audit 断言）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 39，不含 40
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-99-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-148-ws';  -- 恰 4（绝句）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-99-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-148';                                  -- 4（绝句每层一行）
--   SELECT certainty FROM poetry_claim WHERE id = 'claim-bg-99-person'; -- KNOWN（兄弟两源合龙）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-99-scene','claim-bg-99-city','claim-bg-99-world');
--     -- LIKELY / LIKELY / LIKELY（通鉴条年份可钉但 claim 含节令解读整体 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-148'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-148';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-99-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V040_rollback.sql（按 id 全枚举删除；不动 V018/V026 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-148',
              'layer': {'bg-99-scene': 'SCENE', 'bg-99-city': 'CITY',
                        'bg-99-world': 'WORLD', 'bg-99-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（绝句：每层一行） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-148-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 40, 'Wang Wei Sep 9th Missing Shan-dong Brothers background layers (stage-D poem 21, second quatrain): dating verdict fifteen, third shape of the title-evidence series -- the wikisource page carries an editor note shi nian shi-qi (written at seventeen) with no source given: transcribed verbatim in the citation, labelled a curator note, never entered as fact -- page-notes date, history does not; the Tongjian carries two Double-Ninth entries whose years ARE pin-able by heading-position assertions (695 Liu Zhiji memorial yin zhong-yang zhi jie zhu jiang huang-en, and 819 the court plans a great Double-Ninth banquet and Li Jue memorializes against it, V034 positional rule enforced at generation) yet neither touches Wang Wei -- a festival in the annals never drags the poem in; shan-dong itself stays unclaimed: JTS gives only xi jia yu pu (a Hedong home, single-source, not raised), XTS gives no address at all, three readings left un-ruled and no brothers invented; one KNOWN: the brotherhood itself, JTS yu di Jin ... qi-ming, gui-men you-ti plus XTS yu di Jin qi-ming, zi xiao-you -- two independent wordings agreeing; the self-memorial trading his post to recall his brother and the deathbed letter to Jin cited as line-continuation only (V039 owns the death ruling, not reopened); zero new sources (juan 128 opened by V026, tongjian source row already standing)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 40);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V040 精确回滚：只删 V040 插入的行（id 全枚举）。',
         '-- work-t300-148 本体、其 text_line 4 行与 source-ws-t300-148 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi/quantangshi-128/tongjian）与 V026 的行不删；',
         '-- V040 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 40;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_L1, WS_L1A, WS_L2, WS_L2A,
              JTS_XJ, JTS_DI, XTS_DI, XTS_BB, QT_STUB,
              TJ205_TITLE, TJ205_LZJ, TJ241_TITLE, TJ241_CX]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 异文标记与底注照登断言
    for tok in ('{{别|為|爲}}', '時年十七'):
        if tok not in flat:
            bad.append(f'标记/底注须原样在场: {tok}')
    if '非史料' not in ''.join(BG.values()) + sql:
        bad.append('底注「時年十七」须伴「非史料」声明')
    # 通鉴两条年标题断言：标题与其条同段且两条年份关键词在引文
    w695 = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-99-world' and '劉知幾' in ex)
    w819 = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-99-world' and '重陽大宴' in ex)
    if '公元六九五年' not in w695 or '重陽之節' not in w695 or '劉知幾' not in w695:
        bad.append('695 条断言失效（标题+刘知几+重阳语须同段入证）')
    if '公元八一九年' not in w819 or '重陽大宴' not in w819:
        bad.append('819 条断言失效（标题+重阳宴）')
    # 兄弟两源断言
    p_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-99-person' and s == 'source-jiutangshu-wenyuan')
    p_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-99-person' and s == 'source-xintangshu-wenyi')
    if '齊名' not in p_jts or '齊名' not in p_xts:
        bad.append('兄弟齐名两源不齐')
    # 判例只引不重开：V039/V037 关键语不得入本迁移引文
    for tok in ('乾元二年', '妻亡不再娶', '蔬食', '篤志奉佛'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 绝句形制：每层恰 1 行，合计 4
    if sum(len(v) for v in BG_LINES.values()) != 4 or any(len(v) != 1 for v in BG_LINES.values()):
        bad.append('绝句 background_line 必须是每层恰 1 行（4 层共 4 行）')
    if len(re.findall(r"text-work-t300-148-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V040 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V040 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-148' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V040 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-148' AS subject_id" in sql:
        bad.append('V040 的 claim 主语应全部是 bg-99-*，work-t300-148 不该做主语')
    # 底注年岁不得被铸成任何 claim 值文本里的系年事实（粗检：claim 值文本含「十七岁作」类句式即违规）
    for k, v in CLAIMS.items():
        if re.search(r'十七岁写|十七岁作|作于十七', v[2]):
            bad.append(f'{k} 值文本把底注年岁铸成系年事实')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V040 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V040 零新 source（卷128 V026 已立/通鉴已立），不该出现 INSERT INTO poetry_source')
    body_all = ''.join(BG.values()) + sql
    if '页注系年' not in body_all or '史无系年' not in body_all:
        bad.append('BG/文件头须含「页注系年，史无系年」判决声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 16 切片逐字过审且全部进引文；'
              f'切片传区间/通鉴年标题位置断言（V034 立规）；兄弟齐名两源断言；'
              f'底注照登+非史料声明+不铸系年三重断言；判例只引不重开断言（V039/V037 关键语零入引文）；'
              f'{{{{别|為|爲}}}} 标记照录断言；绝句每层一行形制断言；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'零新 source 已断言；诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
