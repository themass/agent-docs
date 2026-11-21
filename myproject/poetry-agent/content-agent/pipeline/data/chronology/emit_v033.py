#!/usr/bin/env python3
"""阶段 D 第 14 首：生成 V033——李益《喜見外弟又言別》(work-t300-087, V018 已立) 四层背景。

「为什么写」第六次成立，但这首的因果最小到只有一个动作：表兄弟十年后偶然认出彼此，
喜极而别。本地证据链把「十年」背后的大乱世钉死在通鉴：「離亂」能指的大事只有安史之乱，
而它的爆发日通鉴逐字可核——天寶十四年（乙未，公元七五五年）「十一月，甲子，
祿山發所部兵及同羅、奚、契丹、室韋凡十五萬眾，號二十萬，反於范陽」——
这是阶段 D 第一次把「诗里的乱」接到「史里的某一天」。

系年第八次判决：**全缺席，缺席原因是「诗自带时间记号，但起算点核不到」**。
「十年離亂後」有明示时长，下限锚（755）也硬——但从哪年起算、虚岁实岁、乱起还是乱盛，
本地无一可核：推 765/766 是年谱式演算，不是史料原文（V031 拒年谱 728 的同一纪律）。
time.span/event.name/written_during 零铸造 + 零 relation（V027–V032 形状断言累积）。

单传诗人第二次（V028 陈子昂先例）：李益在旧唐书零命中、通鉴全卷零命中（2026-11-20 重抓
11 个坏快照后全库复扫），本传只在新唐书卷203——KNOWN 标准降为「新传单一但无对立来源」：
本传内部无自相矛盾处按新传直记（名气：樂工賂求/圖繪天下；不調郁郁；幽州怨望降秩），
本传自相矛盾处（太子庶子同名李益的「文章李益」辨）照登。**新传含 {{PUA|}} 私用区字符两处**
（「世謂◯為『李益疾』」「累遷◯賢殿學士」——录入本字符丢失），引用绕开并在 locator 声明缺口：
「少癡而忌克」句切成 {{PUA}} 前后两半逐字并引，中间缺口写明——缺就写明缺，不假引用。

ws 诗页有 1 对页内异文（{{另|離亂|亂離}}，词序异文）——**登记先行**于
corpus/tang300-variants.md（「喜見外弟又言別 087」行，2026-11-20），引文取原始 wikitext（V024 判例）。

用法: python3 -I emit_v033.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/喜見外弟又言別.txt').read_text(encoding='utf-8')
V283 = pathlib.Path('/tmp/src-dl/quantangshi/vol283.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷203.txt').read_text(encoding='utf-8')
TJ217 = pathlib.Path('/tmp/src-dl/tongjian/tj-217.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_L12 = slice_between(WS, '十年{{另|離亂|亂離}}後，長大一相逢。', '長大一相逢。',
                       'ws首联(十年离乱——页内异文 離亂/亂離 原样)')
WS_L34 = slice_between(WS, '問姓驚初見，稱名憶舊容。', '稱名憶舊容。', 'ws二联(问姓称名)')
WS_L56 = slice_between(WS, '別來滄海事，語罷暮天鐘。', '語罷暮天鐘。', 'ws三联(沧海暮钟)')
WS_L78 = slice_between(WS, '明日巴陵道，秋山又幾重。', '秋山又幾重。', 'ws尾联(巴陵秋山)')
WS_HDR = slice_between(WS, '| title    = 喜見外弟又言別\n| section  =\n| author   = 李益',
                       '| author   = 李益', 'ws header title+author')
V283_NOTE = slice_between(V283, "'''李益'''", "'''李益'''", 'vol283 卷首作者注')
V283_ANCHOR = slice_between(V283, '==[[喜見外弟又言別]]==', '{{:喜見外弟又言別}}', 'vol283 锚点+转引用桩')
# 新传段全部绕开 {{PUA|}} 私用区字符（两处），缺口在 locator 声明
XTS_NAME = slice_between(XTS, '李益，故宰相揆族子，-{於}-詩尤所長。貞元末，名與宗人賀相埒。毎一篇成，樂工爭以賂求取之，被聲歌，供奉天子。至-{征}-人、早行等篇，天下皆施之圖繪。',
                         '天下皆施之圖繪。', '新传第一段(族子/名埒李贺/乐工赂求/图绘天下)')
XTS_JIA = slice_between(XTS, '少癡而忌克，防閑妻妾苛嚴，世謂', '世謂',
                        '新传第二段前残片(忌克——止于 {{PUA}} 字符前)')
XTS_JIB = slice_between(XTS, '爲「李益疾」。同輩行稍稍進顯，益獨不調，鬱鬱去。', '鬱鬱去。',
                        '新传第二段后残片(李益疾+独不调郁郁去——起于 {{PUA}} 字符后)')
XTS_YJ = slice_between(XTS, '-{游}-燕，劉濟-{辟}-置幕府，進爲營田副使。嘗與濟詩，語怨望。',
                       '語怨望。', '新传幽州幕段(刘济辟+诗语怨望)')
XTS_ZH = slice_between(XTS, '憲宗雅知名，召爲祕書少監、集不能堪，諫官因暴幽州時怨望語，詔降秩。',
                       '詔降秩。', '新传召还降秩段(怨望语被暴+降秩)')
XTS_WZ = slice_between(XTS, '時又有太子庶子李益同在朝，故世言「文章李益」以辨-{云}-。',
                       '以辨-{云}-。', '新传同名辨段(文章李益)')
TJ217_TITLE = slice_between(TJ217, '玄宗至道大聖大明孝皇帝下之下天寶十四年（乙未，公元七五五年）',
                            '天寶十四年（乙未，公元七五五年）', '通鉴217卷755年标题(标准形)')
TJ217_FB = slice_between(TJ217, '十一月，甲子，祿山發所部兵及同羅、奚、契丹、室韋凡十五萬眾，號二十萬，反於范陽。',
                         '反於范陽。', '通鉴755标题下爆发句(反于范阳)')

BG = {
    'bg-xy-scene': (
        '这首诗的全部事件小得只有一个房间：两个多年没见的人撞上了。'
        '「問姓驚初見，稱名憶舊容。」——先问姓，惊了一下；再报名，才想起旧时的模样。'
        '不是不相识，是**长到认不出了**：「長大一相逢」——十年乱世，各人长大成人，'
        '要用姓和名来重新对号。喜在这里，窘也在这里。\n'
        '「十年離亂後」的「離亂」是哪场乱：本库核到的只有通鉴那一条——'
        '天寶十四年（乙未，公元七五五年）十一月甲子安禄山反于范阳（见第 5、6 句那层）。'
        '十年后重逢，表兄弟要重新报名字，因为中间隔着的就是这场乱。'),
    'bg-xy-city': (
        '重逢没有固定的城——这首诗的城在尾联才出现，而且是「将去」的城：'
        '「明日巴陵道，秋山又幾重。」——明天就是巴陵道，秋山一层又一层，'
        '把人重新隔进乱世里去。喜见是今晚，言别已经排进明日。\n'
        '中间的「別來滄海事，語罷暮天鐘」把十年压进一席话：沧海的世事说完了，'
        '暮色里的钟声响了——钟一响，话就得断。这座「城」其实是驿站和路上的城：'
        '本传通篇没写他在巴陵停留过，巴陵是诗里唯一有名字的地名，'
        '它的功能只有一个：**下一条 separating 道路**（异文注：「離亂」页内又出「亂離」，'
        '登记在 corpus/tang300-variants.md，取首读不裁决）。'),
    'bg-xy-world': (
        '「離亂」两个字背后是一整个时代的开局，通鉴把它钉在具体的日子：'
        '天寶十四年（乙未，公元七五五年）标题下——「十一月，甲子，'
        '祿山發所部兵及同羅、奚、契丹、室韋凡十五萬眾，號二十萬，反於范陽。」\n'
        '从这一天起，十年是一个可以数出来的长度。李益这一代诗人就是被这个开局切开的：'
        '本传记他乱后「同輩行稍稍進顯，益獨不調，鬱鬱去」——同辈渐渐显达，'
        '他独自沉滞，郁郁离开；后来「游燕」入刘济幽州幕，「嘗與濟詩，語怨望」——'
        '诗里带怨气，多年后宪宗召他回朝，「諫官因暴幽州時怨望語，詔降秩」——'
        '旧怨被翻出来，降了级。\n'
        '**系年的诚实话**：这首诗自带时间记号「十年」，但**起算点核不到**——'
        '从 755 爆发算、从陷京算、虚指实指，本地无一记载；推 765/766 是年谱式演算，'
        '不是史料原文，不采信。time.span、event.name、written_during 全部缺席：'
        '「离乱之后」可以确定在 755 之后（下限是通鉴那天的硬事实），'
        '但一个确定的下限配一个算不清的时长，铸不成年份。'),
    'bg-xy-person': (
        '李益的本传只有一部——新唐书（旧唐书通篇无李益，通鉴全卷无李益；'
        '单传诗人，V028 陈子昂的先例）。单传不等于不硬：这一传的信息密度极高。\n'
        '他是名家的方式全库独一份：「毎一篇成，樂工爭以賂求取之，被聲歌，供奉天子」——'
        '乐工拿着贿赂来抢他的诗，唱给天子听；「至征人、早行等篇，天下皆施之圖繪」——'
        '《征人歌》《早行》这类诗，天下画成画。他生前就是流行歌的供稿人。\n'
        '官场他是另一个人：「同輩行稍稍進顯，益獨不調，鬱鬱去」；入刘济幽州幕，'
        '「嘗與濟詩，語怨望」，宪宗召还后「諫官因暴幽州時怨望語，詔降秩」——'
        '二十多年前的牢骚话被人翻出来当罪状。\n'
        '本传还有两笔丑闻与怪病：「少癡而忌克，防閑妻妾苛嚴」——后世成语「醋海翻波」'
        '文献级的源头就在「世謂◯為『李益疾』」一句（◯处维基文库录入本为私用区字符，'
        '无法逐字引用，本库只引 {{PUA}} 标记前后两半并在引文 locator 声明缺口）；'
        '以及同名之扰：「時又有太子庶子李益同在朝，故世言『文章李益』以辨」——'
        '满朝有两个李益，他得靠「文章」二字区分。\n'
        '全唐詩卷二百八十三整卷收他的诗，卷首注「李益」；本诗在卷内是锚点+转引用桩。'
        '「喜見外弟又言別」写得这样轻，对照他这样重的一生，恰是乱世把人的名字'
        '逼成相认暗号的证据。'),
}
CLAIMS = {
    'claim-bg-xy-scene': (
        'FACT', 'LIKELY',
        '问姓/称名/长大重逢全由诗本文内证；「離亂」唯一可核的大乱=通鉴 755 爆发句（world 层逐字）；'
        '页内异文離亂/亂離登记先行、取首读不裁决。'),
    'claim-bg-xy-city': (
        'FACT', 'LIKELY',
        '巴陵道/秋山/暮钟全诗本文；本传无巴陵行迹记载——城市层明说这是「路上的城」，'
        '本传不涉，无并列冲突。'),
    'claim-bg-xy-world': (
        'FACT', 'KNOWN',
        '755 年标题（标准形，乙巳…乙未对账由 audit 检查4 覆盖）+爆发句通鉴逐字——'
        '通鉴单源但为编年体直书，事件本体升 KNOWN（V028 契丹乱先例：事件年份比任何诗都硬）；'
        '此 KNOWN **只覆盖事件，不外溢到诗**：起算点核不到→诗 time.span/event.name/'
        'written_during 全缺席、零 relation。'),
    'claim-bg-xy-person': (
        'FACT', 'LIKELY',
        '单传诗人：新传单源，KNOWN 升格需两独立来源一致（V028 判例）——新传虽内部无矛盾，'
        '但旧传/通鉴俱无对证，全段按 LIKELY 陈述；{{PUA}} 缺口句只引前后残片，不转写缺字。'),
}
CITATIONS = [
    ('claim-bg-xy-scene', 'source-ws-t300-087',
     '页面 喜見外弟又言別（首联+二联逐字以「……」相連；首联页内异文 {{另|離亂|亂離}} 原样照登'
     '——登记先行于 corpus/tang300-variants.md「喜見外弟又言別 087」行；'
     '全文另见 V018 claim-t300-087-text 引文）', join(WS_L12, WS_L34)),
    ('claim-bg-xy-city', 'source-ws-t300-087',
     '页面 喜見外弟又言別（三联+尾联逐字以「……」相連——巴陵/秋山为将别之路，'
     '新传无巴陵行迹，城市层纯内证）', join(WS_L56, WS_L78)),
    ('claim-bg-xy-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百十七·唐紀三十三·玄宗·天寶十四年（乙未，公元七五五年）标题+爆发句'
     '（两段以「……」相連，年标题归属已分记——安史之乱爆发「反於范陽」）',
     join(TJ217_TITLE, TJ217_FB)),
    ('claim-bg-xy-world', 'source-ws-t300-087',
     '页面 喜見外弟又言別（首联原始 wikitext 重引——「離亂」一词两读原样在场，'
     'world 层读法之证；与 SCENE 行同 (claim≠) 不同 claim，主键不冲突）', WS_L12),
    ('claim-bg-xy-person', 'source-xintangshu-wenyi',
     '卷二百零三·文藝下·李益传（第一段+忌克段前残片（止于 {{PUA}} 前）+忌克段后残片'
     '（起于 {{PUA}} 后）+幽州幕段+召还降秩段+同名辨段；六段以「……」相連——'
     '「世謂」与「爲李益疾」之间的页面私用区字符为**声明缺口**，非删节非转写；'
     '「累遷◯賢殿學士」处同类缺口在本传第二段，本引文段未取到该句）',
     join(XTS_NAME, XTS_JIA, XTS_JIB, XTS_YJ, XTS_ZH, XTS_WZ)),
    ('claim-bg-xy-person', 'source-quantangshi-283',
     '页面 全唐詩/卷283（卷首作者注＋本诗锚点与转引用桩 {{:喜見外弟又言別}}；'
     '卷页无正文，正文证据在诗页；同 V022/V025–V031 桩教训）',
     join(V283_NOTE, V283_ANCHOR)),
    ('claim-bg-xy-person', 'source-ws-t300-087',
     '页面 喜見外弟又言別（header title+author 字段逐字——署名第三证，V029/V031 路数；'
     '本传唯一但署名三处（选本/诗页/全唐詩卷注）独立在场）', WS_HDR),
]
BG_LINES = {'bg-xy-scene': (1, 2), 'bg-xy-city': (3, 4),
            'bg-xy-world': (5, 6), 'bg-xy-person': (7, 8)}
BG_AUDIENCE = {'bg-xy-scene': 'PRIMARY', 'bg-xy-city': 'JUNIOR',
               'bg-xy-world': 'SENIOR', 'bg-xy-person': 'SENIOR'}
BG_TITLES = {'bg-xy-scene': '眼前：靠报名字重新认识',
             'bg-xy-city': '这座城：明日的巴陵道',
             'bg-xy-world': '这个天下：十年从哪一天起算',
             'bg-xy-person': '这个人：乐工抢着要的诗'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 14 首）；史实句均有逐字引证；'
                 '755 爆发日通鉴逐字（事件 KNOWN 不外溢到诗）；诗自带「十年」而起算点核不到→'
                 'time.span/event.name/written_during 全缺席、零 relation；'
                 '新传 {{PUA}} 缺口声明引用；页内异文先登记后原样引。' for k in BG}


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
    A("""-- V033：李益《喜見外弟又言別》(work-t300-087) 四层背景（阶段 D 第 14 首）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-087 与其 text-work-t300-087-ws、
--       source-ws-t300-087 都是 V018 的行；source-xintangshu-wenyi 是 V016 的行（引 卷203）；
--       source-zizhi-tongjian-events 是 V015 的行（引 卷217）——都不另开行）。
--
-- 数据源（可复现）：emit_v033.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/喜見外弟又言別.txt（含 {{另|離亂|亂離}} 页内异文原样——登记先行）、
--   全唐詩/卷283（卷首注+锚点+转引用桩）、新唐書卷203（**含 {{PUA|}} 私用区字符，切片绕开+声明**）、
--   資治通鑑卷217（755 年标题标准形+爆发句；快照为 2026-11-20 坏页重抓后版本）。
--
-- 做：1 个新 source 登记（全唐詩卷283，PENDING——登记不等于核验）+
--   4 BACKGROUND content/claim/background + 7 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（scene→1,2｜city→3,4｜world→5,6｜person→7,8，绑 text-work-t300-087-ws）。
--   本迁移不碰 poetry_text_line（087 的 8 行 V018 落得正确）。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「诗自带时长，起算点核不到」）：
--   * 「離亂」=安史之乱由通鉴爆发句锚定 755（事件层升 KNOWN——V028 事件先例），
--     但诗的「十年」从爆发/陷京/家难哪年起算、虚实如何，本地无一记载——
--     推 765/766 是年谱式演算，不采信；下限硬≠年份可得，time.span 不铸；
--   * 单传诗人（V028 判例）：旧传/通鉴零命中（2026-11-20 重抓 11 卷坏快照后全库复扫）——
--     新传再详也按 LIKELY，PERSON 不升 KNOWN；
--   * 新传 {{PUA|}} 私用区字符两处：「世謂◯為李益疾」「累遷◯賢殿學士」——
--     引文只取缺口前后残片并在 locator 声明，缺就写明缺，不转写不脑补；
--   * 巴陵无本传行迹对应，城市层写明「路上的城」，不编行迹。
--
-- 干支对账：755=乙未（天寶十四年，通鉴 217 标准形年标题，audit 检查4 覆盖）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 32，不含 33
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-xy-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-087-ws';  -- 恰 8
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-283';     -- 空
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-xy-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-087';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-xy-world';    -- KNOWN（仅事件）
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-xy-person';   -- LIKELY（单传不升）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-087'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-087';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-xy-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V033_rollback.sql（按 id 全枚举删除；不动 V018 的行，不动共用来源行）
START TRANSACTION;""")

    A('\n-- ---------- 1. 来源登记（一律 PENDING：登记不等于核验） ----------')
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            [{'id': 'source-quantangshi-283',
              'title': '《全唐詩》全唐詩/卷283（维基文库录入本）',
              'author': None,
              'edition': '全唐詩/卷283（维基文库《全唐詩》录入本）',
              'url': 'https://zh.wikisource.org/wiki/全唐詩/卷283',
              'rights_note': '维基文库录入本，公有领域古籍。本卷为李益诗卷，卷首 Collection header '
                             "notes 标作者（李益）。本诗条目只有锚点+转引用桩，正文在诗页。"
                             '本行由 emit_v033.py 对快照逐字定位。核验状态保持 PENDING。',
              'verification_status': 'PENDING', 'source_kind': 'POETRY_COLLECTION',
              'reliability': 'HIGH'}],
            'x.id = t.id'))

    A('\n-- ---------- 2. BACKGROUND content identities ----------')
    rows = [{'id': k, 'entity_type': 'BACKGROUND', 'slug': k[3:], 'title': BG_TITLES[k],
             'summary': BG_SUMMARY[k], 'time_precision': 'UNKNOWN'} for k in BG]
    A(guard('poetry_content', ['id', 'entity_type', 'slug', 'title', 'summary', 'time_precision'],
            rows, 'x.id = t.id'))

    A('\n-- ---------- 3. claims（主语=BACKGROUND content 行；claim id 带 claim- 前缀，V004 同款） ----------')
    crows = [{'id': k, 'subject_id': k.replace('claim-', '', 1), 'property_key': 'context',
              'value_text': v[2], 'claim_kind': v[0], 'certainty': v[1]} for k, v in CLAIMS.items()]
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            crows, 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': k.replace('claim-', '', 1), 'property_key': 'context', 'claim_id': k}
             for k in CLAIMS],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))

    A('\n-- ---------- 4. background rows ----------')
    brows = [{'id': k, 'work_id': 'work-t300-087',
              'layer': {'bg-xy-scene': 'SCENE', 'bg-xy-city': 'CITY',
                        'bg-xy-world': 'WORLD', 'bg-xy-person': 'PERSON'}[k],
              'body_text': BG[k], 'audience': BG_AUDIENCE[k], 'claim_id': 'claim-' + k} for k in BG]
    A(guard('poetry_background', ['id', 'work_id', 'layer', 'body_text', 'audience', 'claim_id'],
            brows, 'x.id = t.id'))

    A('\n-- ---------- 5. 逐字引文（(claim,source) 主键每对恰一行） ----------')
    L.append('INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(c)} AS claim_id, {sql_s(s)} AS source_id, {sql_s(loc)} AS locator, "
        f"{sql_s(ex)} AS evidence_excerpt FROM DUAL"
        for c, s, loc, ex in CITATIONS))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_citation x '
             'WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);')

    A('\n-- ---------- 6. background_line ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-087-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 7. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 33, 'Li Yi Xi-jian wai-di you yan-bie background layers (stage-D poem 14): the poem names its own duration (ten years after the diaspora-war) and the Tongjian pins that war-s first day verbatim (Tian-bao 14, yi-wei 755, the eleventh-month jia-zi outbreak at Fan-yang) -- event-level KNOWN per the V028 event precedent, deliberately not overflowing to the poem: the counting origin of the ten years (outbreak? fall of the capital? family flight? nominal or real age?) is unrecorded locally, so 765/766 would be chronology arithmetic, not source text -- NO time.span, NO event.name, NO written_during, zero relation rows; single-biography poet a second time (JTS and the whole re-fetched Tongjian scan have no Li Yi) so the rich Xin Tang-shu biography stays LIKELY by the V028 rule; two private-use-area characters (PUA slots) in the biography page are quoted around, never rewritten, the gap declared in the locator; the page-internal variant of the first line was registered in corpus/tang300-variants.md before this migration quotes it raw'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 33);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V033 精确回滚：只删 V033 插入的行（id 全枚举）。',
         '-- work-t300-087 本体、其 text_line 8 行与 source-ws-t300-087 都是 V018 的行，绝不删；',
         '-- 共用 source 行（xintangshu-wenyi/tongjian-events）不删；V033 零 poetry_relation 行。',
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
    dels('poetry_source', 'id', ['source-quantangshi-283'])
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 33;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (WS_L12, WS_L34, WS_L56, WS_L78, WS_HDR, V283_NOTE, V283_ANCHOR,
              XTS_NAME, XTS_JIA, XTS_JIB, XTS_YJ, XTS_ZH, XTS_WZ, TJ217_TITLE, TJ217_FB):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in (WS_L12, WS_L34, WS_L56, WS_L78, WS_HDR, V283_NOTE, V283_ANCHOR,
              XTS_NAME, XTS_JIA, XTS_JIB, XTS_YJ, XTS_ZH, XTS_WZ, TJ217_TITLE, TJ217_FB):
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # {{PUA}} 私用区标记绝不允许进**引文字段**（locator/注释里作为缺口声明提及是有意措辞，
    # 机器保证有两层：evidence_excerpt 值级检查 + 全文件私用区码位检查）
    for _, _, _, ex in CITATIONS:
        if '{{PUA' in ex:
            bad.append(f'{{PUA 标记混入引文字段: {ex[:24]}…')
    for ch in flat:
        if 0xE000 <= ord(ch) <= 0xF8FF:
            bad.append(f'私用区字符混入 SQL: U+{ord(ch):04X}')
    # 页内异文标记原样在场
    if '{{另|離亂|亂離}}' not in flat:
        bad.append('页内异文标记未原样进入 SQL')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V033 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V033 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-087' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V033 有意不给诗铸 {pk}，但该主语组合出现了')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V033 不碰 poetry_text_line')
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
              f'页内异文原样+PUA 缺口零混入已断言；(claim,source) 主键 '
              f'{len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
