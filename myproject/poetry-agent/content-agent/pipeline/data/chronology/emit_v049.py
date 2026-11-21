#!/usr/bin/env python3
"""阶段 D 第 30 首：生成 V049——孟浩然《秦中感秋寄遠上人》(work-t300-112, V018 已立) 四层背景。

「为什么写」撞上了比系年更上游的东西：**这首诗连署名都带着异说**——

系年第二十四次判决（题证系列第十二状·首见断链在署名）：
「題有地而地屬它事、詩有主而主有異說」——
V045 地有传见而见必它事（土地版）、这首是**都邑版**：题眼「秦中」即京畿，
两传孟区间「秦中」零见、「京師」凡三处且生成时位置断言全落
「年四十來遊京師」「韓朝宗約浩然偕至京師」两条**已两入/三入旧事**内——
地有传见、见必它事，且它事已触两度上限，零重引；
「遠上人」两传零见（上人一词通鉴 6 处皆它人）、全唐詩恰六处（卷160 恰四=两枚篇题各两次+卷237 恰二，
机器断言）——**人有诗证而无史证**：孟集内《晚春題遠上人南亭》锚点为第二首诗证；
而诗的署名本身带异说：ws 页底注照登「《河嶽英靈集》稱崔國輔作，惟題下有小注曰：
『一刻，下三首孟浩然作，崔集亦不載。』」——题异 <ref>（感秋/感興、遠/逺）同页并收。
系年链条断在**作者**这一环之前：连「谁的」都并列着，「哪一年」更无从属。
零铸造零 relation；异说登记不裁决（tang300-variants.md 新行已入）。

<ref> 标记体系首见：本页异文不挂 {{另}} 而挂 <ref> 注（河嶽英靈集/文苑英華三处）——
异文照登断言（V044 反向极性判例）**首次跨标记体系复用**：audit 硬卡
「北上」「旦夕」两支字样必在 SCENE 引文中（页 HAS 异文注且已登记 → 注必逐字入引）。

KNOWN 零（如实记录第五例，audit 反向断言 SQL 无 KNOWN 字面量）：
匿床对诗一段新传单得（旧传孟段无此轶）；远上人诗证/署名异说皆单源侧——
claim 四行全 LIKELY。

负证机器复查三层（生成时断言，快照变动即中止）：
① 秦中/上人（作远上人解）在两传孟区间计数全零，京師三处逐一定位进已用旧事句；
② 「慧遠」通鉴 75 卷+全唐詩 120 卷计数全零——东林典的本名在快照史部+集部
   皆零见（远公 全唐詩恰九处、卷160 零处——典在它诗不在此集，断言精确计数）；
③ 全唐詩「遠上人」恰六处（卷160 恰四处=本篇与《晚春題遠上人南亭》两枚篇题各两次：
   标题行+转引桩；卷237 恰二处），通鉴零见。

判例零重开（audit 关键语硬卡）：不才明主棄/奈何誣我/放還/韓朝宗/遑恤他/
鹿門/孟亭/畫浩然像/年四十/應進士不第/署為從事/不逹而卒/以詩自適/隱鹿門山。

八句律詩 2/2/2/2 形制；零新 source
（ws-112/xts/quantangshi-160 三源行均已立——通鉴本迁移零入引，只做负证扫描）。

用法: python3 -I emit_v049.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/秦中感秋寄遠上人.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷203.txt').read_text(encoding='utf-8')
V160 = pathlib.Path('/tmp/src-dl/quantangshi/vol160.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 秦中感秋寄遠上人<ref>《河嶽英靈集》題作〈秦中感興寄逺上人〉</ref>',
                         '題作〈秦中感興寄逺上人〉</ref>', 'ws header title(含题异<ref>——河嶽英靈集题感興寄逺,跨集题异A面)')
WS_AUTHOR = slice_between(WS, '| author   = 孟浩然', '| author   = 孟浩然', 'ws header author(署名直证——选本系统一路)')
WS_NOTES = slice_between(WS, '| notes    = 《河嶽英靈集》稱崔國輔作，惟題下有小注曰：「一刻，下三首孟浩然作，崔集亦不載。」',
                         '崔集亦不載。」', 'ws 页底注(署名异说照登——河嶽稱崔作/小注归孟/崔集不载,三重异说,非史料声明+不升格)')
WS_L12 = slice_between(WS, '一丘常欲臥，三徑苦無資。', '三徑苦無資。', 'ws第1联(一丘欲卧/三径无资——归隐之愿与无资之窘)')
WS_L34 = slice_between(WS, '北土非吾願，東林懷我師。<ref>北土：《河嶽英靈集》作「北上」；《文苑英華》作「北山」</ref>',
                        '《文苑英華》作「北山」</ref>', 'ws第2联(北土非愿/东林怀师——含北土/北上/北山三源异文<ref>)')
WS_L56 = slice_between(WS, '黃金然桂盡，壯志逐年衰。', '壯志逐年衰。', 'ws第5联(黄金尽/壮志衰——长安米贵句法,PERSON 层对读)')
WS_L78 = slice_between(WS, '日夕涼風至，聞蟬但益悲。<ref>日夕：《文苑英華》作「旦夕」</ref>',
                        '《文苑英華》作「旦夕」</ref>', 'ws第4联(日夕凉风/闻蝉益悲——含日夕/旦夕异文<ref>)')
XTS_NC = slice_between(XTS, '維私邀入内署，俄而玄宗至，浩然匿床下，維以實對，帝喜曰：「朕聞其人而未見也，何懼而匿？」詔浩然出。',
                       '詔浩然出。', '新传匿床对诗段(王维私邀/玄宗猝至/匿床下/自诵至不才句的前半——新传单得;PERSON 层本体;句止于诏浩然出,放还语触上限零引)')
QTS_YUAN = slice_between(V160, '==[[晚春題遠上人南亭]]==', '晚春題遠上人南亭]]==',
                         '全唐詩卷160 篇题锚点(孟集内远上人第二首——人有诗证而无史证的诗证本体)')
QTS_CUI = slice_between(V160, '==[[宿永嘉江寄山陰崔少府國輔]]==', '宿永嘉江寄山陰崔少府國輔]]==',
                        '全唐詩卷160 篇题锚点(孟集内有寄崔少府国辅诗——署名异说所涉人物在孟自有交游痕迹;只登语境不裁决)')

# ---------- 传区间归属复验（V036 立规） ----------
_ja, _jb = JTS.find('=孟浩然='), JTS.find('=元德秀=')
_xa, _xb = XTS.find('==孟浩然=='), XTS.find('===附 王昌齡===')
if not (0 <= _ja < _jb and 0 <= _xa <= XTS.find(XTS_NC) <= _xb):
    raise SystemExit('切片越出孟浩然传区块——修订后重生成')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_seg_j, _seg_x = JTS[_ja:_jb], XTS[_xa:_xb]
# ① 秦中两传孟区间零见；京師凡三处且逐处落进已两入/三入旧事句内（位置断言）
if '秦中' in _seg_j or '秦中' in _seg_x:
    raise SystemExit('「秦中」落在两传孟区间——地属它事的负证失效，须重读原文')
_jing = [m.start() for m in re.finditer('京師', _seg_j)] + [m.start() for m in re.finditer('京師', _seg_x)]
for _i in _jing:
    _seg = _seg_j if _i in [m.start() for m in re.finditer('京師', _seg_j)] else _seg_x
    _win = _seg[max(0, _i - 40):_i + 10]
    if not ('來遊京師' in _win or '乃-{游}-京師' in _win or '偕至京師' in _win):
        raise SystemExit('两传孟区间有一处「京師」不在已用旧事句内——都邑负证须重估')
if len(_jing) != 3:
    raise SystemExit(f'两传孟区间「京師」计数不是 3（实 {len(_jing)}）——都邑负证须重估')
# ② 东林典本名零见 + 远公精确计数（典在它诗不在此集）
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
def _cnt(w):
    return (sum(len(re.findall(w, f.read_text(encoding='utf-8'))) for f in sorted(_tj.glob('tj-*.txt'))),
            sum(len(re.findall(w, f.read_text(encoding='utf-8'))) for f in sorted(_qts.glob('vol*.txt'))))
_tj_hy, _qts_hy = _cnt('慧遠')
if _tj_hy or _qts_hy:
    raise SystemExit(f'「慧遠」史部+集部计数非零（{_tj_hy}/{_qts_hy}）——东林典无史证论断须重估')
_tj_yg, _qts_yg = _cnt('遠公')
if (_tj_yg, _qts_yg) != (0, 9) or V160.count('遠公') != 0:
    raise SystemExit(f'「遠公」计数不是 通鉴0/全唐詩9/卷160零（实 {_tj_yg}/{_qts_yg}/{V160.count("遠公")}）——典在它诗论断须重估')
# ③ 远上人恰六处（卷160恰四=本篇+晚春题南亭两枚篇题各两次；卷237恰二），通鉴零见
_tj_yr, _qts_yr = _cnt('遠上人')
if (_tj_yr, _qts_yr) != (0, 6) or V160.count('遠上人') != 4:
    raise SystemExit(f'「遠上人」计数不是 通鉴0/全唐詩6/卷160四（实 {_tj_yr}/{_qts_yr}/{V160.count("遠上人")}）——人有诗证论断须重估')

BG = {
    'bg-112-scene': (
        '八句是一场秋天里的自辩：想卧一丘，苦于没有三径的本钱'
        '（「一丘常欲臥，三徑苦無資」——归隐也是要盘缠的）；'
        '北边的都城不是我的心愿，东林的山林才配叫我怀念的师父'
        '（「北土非吾願，東林懷我師」——一句里两个方向，'
        '此句页内挂 <ref> 异文注：北土一支，河嶽英靈集作「北上」、文苑英華作「北山」，'
        '照登不裁决）；黄金像桂一样烧尽了，壮志逐年往下掉'
        '（「黃金然桂盡，壯志逐年衰」——「然桂」即长安居大不易的米价语法）；'
        '傍晚凉风一来，听见蝉声只更添悲'
        '（「日夕涼風至，聞蟬但益悲」——此句 <ref> 注：日夕一支，文苑英華作「旦夕」，'
        '照登不裁决）。'),
    'bg-112-city': (
        '这座「城」是秦中、是京畿——但史部不给它系年：两传孟浩然区间'
        '「秦中」计数全零、「京師」凡三处，生成时逐处定位，'
        '全落在「年四十來遊京師」「韓朝宗約浩然偕至京師」两条旧事里'
        '——地有传见、见必它事（V045 判例·都邑版），而那些它事已触两度上限，零重引。\n'
        '更硬的一层在题目：页题「秦中感**秋**寄**遠**上人」，题面 <ref> 注'
        '《河嶽英靈集》题作「秦中感**興**寄**逺**上人」；页底注再照登一重异说——'
        '「《河嶽英靈集》稱崔國輔作，惟題下有小注曰：『一刻，下三首孟浩然作，'
        '崔集亦不載。』」三重说法（河嶽正文稱崔/河嶽小注归孟/崔集无此诗）并列在场，'
        '这是选本层的署名异说，非史料声明、不升格、不裁决'
        '（底注三重断言判例；tang300-variants.md 新行已登记）。'
        '连「谁的」都并列着，「哪一年」便无从属起。'),
    'bg-112-world': (
        '诗里的「我師」挂着东林典：东林=庐山东林寺，典的主人是慧远——'
        '而快照里**慧远这个名字通鉴 75 卷、全唐詩 120 卷计数全零**'
        '（生成时机器断言）；「遠公」全唐詩恰九处、卷160 零处——'
        '典在唐人它诗里活着，在史部里没有档案：与 V046 牛渚典同族——'
        '**典无史源，系年链条断在典这一环**。\n'
        '收信人本身也一样：「遠上人」通鉴零见、全唐詩恰六处'
        '（卷160 恰四处——本篇与《晚春題遠上人南亭》两枚篇题各两次；卷237 恰二处，机器断言）——'
        '这个人只在诗的世界里往来：**人有诗证而无史证**。\n'
        '全诗唯一的时间感「涼風至」「聞蟬」是季节不是年份。'
        '本层到此为止，不给诗铸时间。'),
    'bg-112-person': (
        '新传给了一段宫廷失仪：王维私把孟浩然邀进内署，玄宗猝至，'
        '他躲到床下，王维如实回奏，帝说「朕聞其人而未見也，何懼而匿？」'
        '诏他出来对诗——这一段**新传单得**（旧传孟段只有'
        '「年四十來遊京師，應進士不第」的骨架句，无此轶，不合龙→LIKELY；'
        '骨架句与「不才明主棄」句均已触两度上限，零重引——audit 关键语硬卡）。\n'
        '把匿床一段和「黃金然桂盡，壯志逐年衰」并排：传里他见皇帝会躲，'
        '诗里他自陈壮志年年往下掉——**躲床的人与自陈志衰的人**是同一位处士'
        '的两份档案。这是读法声明，不是史实；史实只有新传一段。'
        '判例零重开（audit 硬卡）：不才明主弃、奈何诬我、放还、'
        '韩朝宗遑恤他、鹿门、孟亭、画浩然像，本层一个不引。'),
}
CLAIMS = {
    'claim-bg-112-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页 <ref> 标记体系首见——异文注两处挂 <ref> 不挂 {{另}}，'
        'audit 异文照登断言首次跨标记体系复用：北上/旦夕两支字样必在引文；'
        'Textquality 75% 如实记）；归隐本钱/米价语法为本层读法声明，非史料断言。'),
    'claim-bg-112-city': (
        'FACT', 'LIKELY',
        '署名异说照登不裁决：河嶽英靈集稱崔作/其小注归孟/崔集不载三重并列'
        '（ws 页底注+题面题异<ref>，底注三重断言+非史料声明+不升格）；'
        '地属它事：秦中两传孟区间零见、京師三处逐处落进已两入/三入旧事句'
        '（位置断言，两度上限零重引）；孟集内有寄崔少府国辅诗篇题锚点'
        '（异说所涉人物在孟自有交游痕迹——只登语境，不构成任何裁决）；'
        '断链在署名→time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-112-world': (
        'FACT', 'LIKELY',
        '典无史源：慧遠通鉴+全唐詩计数全零、遠公全唐詩恰九处而卷160 零处'
        '（机器精确计数断言，快照变动即中止）——与 V046 同族；'
        '人有诗证无史证：遠上人通鉴零、全唐詩恰六处（卷160 恰四=两枚篇题各两次），'
        '卷160 篇题锚点逐字入引；季节非年份；certainty 不覆盖任何系年。'),
    'claim-bg-112-person': (
        'FACT', 'LIKELY',
        '匿床对诗段新传单得（旧传孟段无此轶，不合龙）→不升；'
        '旧传骨架句与不才句均触两度上限零重引（audit 关键语硬卡）；'
        '躲床者与志衰者并置为读法声明；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-112-scene', 'source-ws-t300-112',
     '页面 秦中感秋寄遠上人（header author+四联八句，五段以「……」相連——'
     '正文两处 <ref> 异文注原样入引（<ref> 标记体系首见，异文照登断言跨体系复用：'
     '北上/旦夕两支在场，登记先行于引用，tang300-variants.md 新行；无裁决）；'
     '同一 (claim,source) 主键下一行容全文判例；正文另见 V018 claim-t300-112-text——'
     '本诗正文两度上限至此用满，后来者不得三引）',
     join(WS_AUTHOR, WS_L12, WS_L34, WS_L56, WS_L78)),
    ('claim-bg-112-city', 'source-ws-t300-112',
     '页面 秦中感秋寄遠上人（header title 含题异<ref>+页底注两字段并收——'
     '题异（感秋/感興、遠/逺）与署名异说（河嶽稱崔/小注归孟/崔集不载）'
     '均为选本层记载：照登+非史料声明+不升格（底注三重断言判例），登记不裁决；'
     '地属它事的负证为两传区间秦中零见+京師三处位置断言，生成时机器复查）',
     join(WS_TITLE, WS_NOTES)),
    ('claim-bg-112-city', 'source-quantangshi-160',
     '卷一百六十·孟浩然集篇题锚点（孟集内另有《宿永嘉江寄山陰崔少府國輔》——'
     '署名异说所涉人物崔国辅在孟浩然自己的集子里有交游痕迹；'
     '只登语境，不构成任何裁决——异说两侧不挪砝码）', QTS_CUI),
    ('claim-bg-112-world', 'source-quantangshi-160',
     '卷一百六十·孟浩然集篇题锚点（《晚春題遠上人南亭》——卷160「遠上人」'
     '恰两处之一：收信人在诗的世界里有第二首，在史部零档案；'
     '人有诗证而无史证的诗证本体，机器精确计数断言）', QTS_YUAN),
    ('claim-bg-112-person', 'source-xintangshu-wenyi',
     '卷二百零三·文藝下·孟浩然传匿床对诗段（王维私邀/玄宗猝至/匿床下/'
     '诏浩然出——新传单得；句止于诏浩然出，放还及不才句触两度上限零引）', XTS_NC),
]
BG_LINES = {'bg-112-scene': (1, 2), 'bg-112-city': (3, 4),
            'bg-112-world': (5, 6), 'bg-112-person': (7, 8)}
BG_AUDIENCE = {'bg-112-scene': 'PRIMARY', 'bg-112-city': 'SENIOR',
               'bg-112-world': 'SENIOR', 'bg-112-person': 'JUNIOR'}
BG_TITLES = {'bg-112-scene': '眼前：秋天的自辩',
             'bg-112-city': '这座城：连作者都并列着',
             'bg-112-world': '这个天下：只在诗里往来的人',
             'bg-112-person': '这个人：躲床的人与志衰的人'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 30 首·八句律詩 2/2/2/2）；史实句均有逐字引证；'
                 'background_line 八句形制：每层 2 行；系年第二十四次判决'
                 '「題有地而地屬它事、詩有主而主有異說」（题证系列第十二状·'
                 '首见断链在署名——署名异说三重并列在场，系年链条断在作者之前）'
                 '→time.span/event.name/written_during 全缺席、零 relation；'
                 'KNOWN 零如实记录（匿床段单得、典与人都无史证——都不升）；'
                 '负证机器复查三层（秦中零见+京師三处位置断言/慧遠全库零见+'
                 '遠公精确九处/遠上人精确六处且卷160 精确四处）；<ref> 标记体系首见——'
                 '异文照登断言首次跨标记体系复用（北上/旦夕两支硬卡）；'
                 '底注三重断言用于署名异说（非史料+不升格+不裁决）；'
                 '判例与两度上限零重引（不才/放還/韓朝宗/京師诸旧事句关键语硬卡）。' for k in BG}


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
    A("""-- V049：孟浩然《秦中感秋寄遠上人》(work-t300-112) 四层背景（阶段 D 第 30 首·八句律詩）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V031 已执行（work-t300-112 与其 text-work-t300-112-ws、
--       source-ws-t300-112 是 V018 的行；source-xintangshu-wenyi 是 V016 的行；
--       source-quantangshi-160 是 V031 的行——均不另开；本迁移通鉴只做负证扫描零入引）。
--       本迁移零新 source（断言）。
--
-- 数据源（可复现）：emit_v049.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/秦中感秋寄遠上人.txt（<ref> 标记体系首见，异文照登断言跨体系复用）、
--   舊唐書卷190下 / 新唐書卷203（孟段负证+匿床段）、全唐詩卷160（两枚篇题锚点）、
--   通鑑卷191–265+全唐詩 120 卷（负证计数扫描）——
--   传区间归属、京師三处位置、慧遠/遠公/遠上人精确计数全部生成时断言。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   5 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句形制 2/2/2/2，绑 text-work-t300-112-ws 的 8 行）。
--   本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--   **不裁决署名异说**（河嶽稱崔/小注归孟/崔集不载三重并列；孟集寄崔锚点只登语境不挪砝码）。
--
-- 诚实边界（这首的边界是「題有地而地屬它事、詩有主而主有異說」）：
--   * 系年链条断在**作者**这一环之前——异说登记不裁决，年份更无从属；
--   * 秦中=京畿：两传孟区间零见、京師三处全落已两入/三入旧事（位置断言，零重引）；
--   * 东林典：慧遠通鉴+全唐詩计数全零、遠公全唐詩恰九处而卷160 零——典无史源（V046 同族）；
--   * 遠上人：通鉴零、全唐詩恰六处（卷160 恰四=两枚篇题各两次）——人有诗证而无史证；
--   * KNOWN 零如实记录（audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 归隐本钱/米价语法/躲床与志衰并置均为读法声明，audit 双声明在 BG 文本内；
--   * 不才明主棄/奈何誣我/放還/韓朝宗/遑恤他/鹿門/孟亭/畫浩然像/年四十/
--     應進士不第/署為從事/不逹而卒/以詩自適 判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 48，不含 49
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-112-%';             -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-112-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-112-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-112';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-112-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-112'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-112';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-112-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V049_rollback.sql（按 id 全枚举删除；不动 V014/V015/V016/V018/V031 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-112',
              'layer': {'bg-112-scene': 'SCENE', 'bg-112-city': 'CITY',
                        'bg-112-world': 'WORLD', 'bg-112-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（八句：2/2/2/2） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-112-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 49, 'Meng Haoran Autumn Thoughts in the West of the Passes, Sent to Monk Yuan background layers (stage-D poem 30, eight-line regulated verse 2/2/2/2): dating verdict twenty-four, twelfth shape of the title-evidence series and the first case where the chain breaks before authorship itself -- the title names a capital region the biographies tie only to other years (zero Qinzhong hits inside the Meng spans; all three occurrences of the capital sit inside career episodes already cited to their two-use ceiling, position-asserted, zero re-quote), the addressee monk exists only in the poetry world (zero in Tongjian; exactly six Quantangshi hits, four in juan 160 as two title anchors counted twice each, one of them a second addressed poem quoted verbatim here), the Donglin allusion has no historical trace (Huiyuan zero across both corpora; the alternative title-form exactly nine hits, none in juan 160 -- machine-counted) -- and the authorship itself carries a registered dispute: the Heiyue yingling ji names Cui Guofu while its own subnote returns the poem to Meng and the Cui collection does not carry it at all; all three claims transcribed verbatim from the page note, declared non-source, never ruled, and the same juan-160 anchor showing Meng addressing Cui in his own collection is registered strictly as context, adding no weight to either side; a first for the <ref> marker system: variant notes ride on <ref> rather than the ye-ling template, and the verbatim-variant assertion (V044 polarity) is reused across marker systems for the first time (the beishang/danxi branches hard-required in the scene excerpt); the hiding-under-the-bed audience with the emperor is new-history only (old history keeps a skeleton already at ceiling -- no agreement, no promotion); KNOWN zero honestly recorded (audit reverse-asserts); readings of retreat-as-price and the shrinking of ambition declared as readings; fourteen closed precedent keywords stay out of citations; zero new sources'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 49);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V049 精确回滚：只删 V049 插入的行（id 全枚举）。',
         '-- work-t300-112 本体、其 text_line 8 行与 source-ws-t300-112 都是 V018 的行，绝不删；',
         '-- 共用 source 行（xintangshu-wenyi/quantangshi-160）与既往迁移的行不删；',
         '-- V049 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 49;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTES, WS_L12, WS_L34, WS_L56, WS_L78,
              XTS_NC, QTS_YUAN, QTS_CUI]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # <ref> 体系异文照登断言（V044 极性跨体系首用）：两支字样必在 SCENE 引文
    scene_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-112-scene')
    for tok in ('北上', '北山', '旦夕'):
        if tok not in scene_ex:
            bad.append(f'异文支「{tok}」未入 SCENE 引文（<ref> 照登断言）')
    # 署名异说照登断言：题异+崔字必在 CITY 引文
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-112-city' and s == 'source-ws-t300-112')
    for tok in ('秦中感興寄逺上人', '崔國輔', '崔集亦不載'):
        if tok not in city_ws:
            bad.append(f'署名异说要素「{tok}」未入 CITY 引文（照登断言）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-112-city' and s == 'source-ws-t300-112'):
        bad.append('CITY ws locator 须含「非史料」声明（底注三重断言）')
    # ws 零模板标记反向断言（本页异文走 <ref>，{{}} 三类仍不得出现）
    ws_ex = ''.join(ex for _, s, _, ex in CITATIONS if s == 'source-ws-t300-112')
    for tok in ('{{另', '{{别|', '{{*|'):
        if tok in ws_ex:
            bad.append(f'ws 引文不得含模板标记 {tok}（本页异文体系是 <ref>）')
    # 史书/集部侧引文禁代拟+禁已用句
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-112':
            for w in ('不才', '放還', '韓朝宗', '遑恤他', '鹿門', '孟亭', '畫浩然像',
                      '年四十', '應進士不第', '署為從事', '不逹而卒', '以詩自適'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例/触上限语「{w}」')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '卒不赴',
                '隱鹿門山', '隠鹿門山', '孟亭', '畫浩然像', '太學賦詩',
                '皆位不顯', '病疽背卒', '開元、天寶間'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句形制 2/2/2/2
    want = {'bg-112-scene': 2, 'bg-112-city': 2, 'bg-112-world': 2, 'bg-112-person': 2}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('八句 background_line 必须 2/2/2/2')
    if len(re.findall(r"text-work-t300-112-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # KNOWN 零如实记录（V042/V046/V048 判例）
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V049 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V049 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-112' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V049 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-112' AS subject_id" in sql:
        bad.append('V049 的 claim 主语应全部是 bg-112-*，work-t300-112 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V049 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V049 零新 source，不该出现 INSERT INTO poetry_source')
    body_all = ''.join(BG.values()) + sql
    if '主有異說' not in body_all:
        bad.append('BG/文件头须含「主有異說」判决声明')
    if '断在作者' not in body_all and '断在**作者**' not in body_all:
        bad.append('BG/文件头须含「断链在作者」判决声明')
    if '读法声明' not in body_all:
        bad.append('BG 须含两处「读法声明」（归隐本钱/躲床与志衰）')
    if '不裁决' not in body_all:
        bad.append('BG/CITY 须含「不裁决」（署名异说三重并列）')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 10 切片逐字过审且全部进引文；'
              f'切片传区间归属断言；负证机器复查三层（秦中零见+京師三处位置断言/'
              f'慧遠史部+集部全零+遠公精确九处/遠上人精确六处且卷160精确四处，快照变动即中止）；'
              f'<ref> 体系异文照登断言（北上/北山/旦夕三支硬卡——跨标记体系首用）；'
              f'署名异说照登断言（感興寄逺/崔國輔/崔集不载）+非史料声明断言；'
              f'ws 零模板标记反向断言（<ref> 体系下 {{{{另}}}}/{{{{别}}}}/{{{{*}}}} 仍禁）；'
              f'非 ws 引文禁触上限语断言；判例只引不重开断言；'
              f'八句 2/2/2/2 形制断言；零 KNOWN 反向断言；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'零新 source 已断言；诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
