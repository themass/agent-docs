#!/usr/bin/env python3
"""阶段 D 第 25 首：生成 V044——王维《積雨輞川莊作》(work-t300-142, V018 已立) 四层背景。

「为什么写」再成立一次。这首的题是整个池子里**唯一带传记锚点的地名**：
「輞川莊」两传明记（V035/V039 已两度逐字立证）——但锚点本身在晃：
新传「母亡，表輞川第為寺，終葬其西」（**本迁移首引**，与 V035/V039 已两度
立证的两句是**同段异句**，V042 谱系）：母亲去世后端宅施寺，而两传都不记
母亲卒年——**「輞川莊」作为私宅的时间窗因此无法闭合**。

系年第十九次判决（题证系列第七状）：**「题有地名有天气，地有传锚而锚不系年」**——
V038 题有地无年（地不在传）、V039 题两地无一年、V040 页有年史无年、
V041 题有角色无人、V042 诗语有地地不在传、V043 题有时刻无地点——
这首是第一次**题中之地恰恰有传**，而传给的锚只到「母亡」为止：
地名钉死、天气钉死（積雨），年份仍无。零铸造零 relation。

KNOWN 一处（两源独立一致）：
**代宗诏集王维文集**——旧传「代宗時，縉為宰相……『卿之伯氏，天寳中詩名冠代，
朕嘗於諸王座聞其樂章』……『十不存一』……都得四百餘篇。翌日上之，帝優詔襃賞」+
新传「寶應中，代宗語縉曰：『朕嘗于諸王座聞維樂章，今傳幾何？』遣中人王承華
往取，縉裒集數十百篇上之」——事体三要素两源一致（代宗于诸王座闻维乐章+
缙奉诏裒集+上之）升 KNOWN；**数量分歧（四百餘篇/數十百篇）各归其侧照登
不裁决**（audit 互斥）；时间措辞「代宗時」／「寶應中」兼容不并轨
（V039 乾元/上元判例：兼容≠裁决）。

判例只引不重开（audit 关键语零入引文硬卡）：辋川两句（V035/V039——不三引）、
鳏居两句（V037 已立，本迁移零引）、奉佛段（V039）、画评天机（V043）、辨乐霓裳（V043）。

异文三类照登不裁决（先登记后引用，本次登记行新入 tang300-variants.md）：
题自注 {{*|一有上字}}、{{*|一作秋歸輞川莊作}}；「海鷗何{{另|事|處}}更相疑」事/處。
CITY 负证**机器复查**（V042 立规）：十个诗语在两传区间计数全零，快照变动即中止。

八句 2/2/2/2；零新 source（ws-142/jts/xts 三源行均已立）。

用法: python3 -I emit_v044.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/積雨輞川莊作.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 積雨輞川莊{{*|一有上字}}作{{*|一作秋歸輞川莊作}}',
                         '| title    = 積雨輞川莊{{*|一有上字}}作{{*|一作秋歸輞川莊作}}',
                         'ws header title(地名钉死+天气钉死;两条题目自注原样照登)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证)')
WS_L12 = slice_between(WS, '積雨空林煙火遲，蒸藜炊黍餉東菑。', '積雨空林煙火遲，蒸藜炊黍餉東菑。',
                       'ws第1-2句联(积雨/烟火迟/饷东菑——连阴天的庄园日程)')
WS_L34 = slice_between(WS, '漠漠水田飛白鷺，陰陰夏木囀黃鸝。', '漠漠水田飛白鷺，陰陰夏木囀黃鸝。',
                       'ws第3-4句联(叠字水田夏木——积雨的视觉听觉)')
WS_L56 = slice_between(WS, '山中習靜觀朝槿，松下清齋折露葵。', '山中習靜觀朝槿，松下清齋折露葵。',
                       'ws第5-6句联(习静观槿/清斋折葵——斋居功课)')
WS_L78 = slice_between(WS, '野老與人爭席罷，海鷗何{{另|事|處}}更相疑。', '野老與人爭席罷，海鷗何{{另|事|處}}更相疑。',
                       'ws第7-8句联(争席/海鸥——庄子列子两个典;「何{{另|事|處}}」异文原样照登)')
JTS_ZJ = slice_between(JTS, '在京師日飯十數名僧，以玄談為樂。', '以玄談為樂。',
                       '旧传京师段(日饭十数名僧/以玄谈为乐——旧传单得)')
JTS_CS = slice_between(JTS, '退朝之後，焚香獨坐，以禪誦為事。', '以禪誦為事。',
                       '旧传禅诵段(退朝焚香独坐/以禅诵为事——旧传单得)')
JTS_DZ = slice_between(JTS, '代宗時，縉為宰相，代宗好文，常謂縉曰：「卿之伯氏，天寳中詩名冠代，朕嘗於諸王座聞其樂章。今有多少文集，卿可進來。」縉曰：「臣兄開元中詩百千餘篇，天寳事後，十不存一。比於中外親故間相與編綴，都得四百餘篇。」翌日上之，帝優詔襃賞。',
                        '帝優詔襃賞。', '旧传代宗诏集段(诗名冠代/十不存一/四百余篇/翌日上之优诏褒赏——代宗诏集两源合龙旧传侧;数量措辞归旧侧)')
XTS_SI = slice_between(XTS, '母亡，表輞川第為寺，終葬其西。', '終葬其西。',
                       '新传施宅为寺句(母亡/表輞川第為寺/终葬其西——本迁移首引;与辋川两句同段异句;母亡无年=锚不系年)')
XTS_BY = slice_between(XTS, '寶應中，代宗語縉曰：「朕嘗于諸王座聞維樂章，今傳幾何？」遣中人王承華往取，縉裒集數十百篇上之。',
                        '裒集數十百篇上之。', '新传宝应诏集段(宝应中/诸王座闻乐章/遣王承华往取/裒集数十百篇——代宗诏集两源合龙新传侧;数量措辞归新侧;代宗时/宝应中兼容不并轨)')

# ---------- 传区间归属复验（V036 立规） ----------
_ja, _jb = JTS.find('=王維='), JTS.find('=李白=')
_xa, _xb = XTS.find('==王維=='), XTS.find('==鄭虔==')
for _s, _tag in [(JTS_ZJ, 'JTS_ZJ'), (JTS_CS, 'JTS_CS'), (JTS_DZ, 'JTS_DZ')]:
    if not (0 <= _ja <= JTS.find(_s) <= _jb):
        raise SystemExit(f'切片越出王维传区间：{_tag}——修订后重生成')
for _s, _tag in [(XTS_SI, 'XTS_SI'), (XTS_BY, 'XTS_BY')]:
    if not (0 <= _xa <= XTS.find(_s) <= _xb):
        raise SystemExit(f'切片越出王维传区块：{_tag}——修订后重生成')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
# 十个诗语在两传区间内必须计数全零——「积雨的庄园场景在传中零记录」由此可复查；
# 快照若变动（新增用例）即中止，防负证悄悄失效。
_seg_j, _seg_x = JTS[_ja:_jb], XTS[_xa:_xb]
for _w in ('積雨', '空林', '煙火', '蒸藜', '東菑', '漠漠', '白鷺', '黃鸝', '野老', '海鷗'):
    if _w in _seg_j or _w in _seg_x:
        raise SystemExit(f'两传王维区间出现「{_w}」——积雨庄场景零记录负证失效，须重读原文再设计')

BG = {
    'bg-jy-scene': (
        '连阴天把庄园的日程放慢了：湿柴点不着，炊烟迟滞（「積雨空林煙火遲」——'
        '第一句的因果是气象学的）；早饭蒸好黍米饭，送到东边的田头（「蒸藜炊黍餉東菑」——'
        '送饭到田里，是劳动日程的一部分）；水田上白鹭低飞，夏木深处黄鹂转声'
        '（「漠漠水田飛白鷺，陰陰夏木囀黃鸝」——两组叠字把雨天的湿度写进视野和听觉）；'
        '自己的日子则是另一套：看木槿朝开暮落修习静观，松下清斋折带露的葵菜'
        '（「山中習靜觀朝槿，松下清齋折露葵」）；末联连用两个典故收束——'
        '《庄子》的争席、《列子》的海鸥：老头子与人无争到连鸥鸟都不再疑他'
        '（「野老與人爭席罷，海鷗何事更相疑」——「何事/何處」页内自注照登不裁决）。\n'
        '这是辋川的诗，题把地点和天气都钉死了。'),
    'bg-jy-city': (
        '这是全池子里**唯一题中带传记锚点地名**的一首：「輞川莊」在两传明记'
        '（那两句 V035 辋川线、V039 别名侧已两度逐字立证——**同句两度为上限，'
        '本迁移不三引**）。但锚点自己在晃：新传「母亡，表輞川第為寺，終葬其西」'
        '——母亲去世后端宅施寺，**两传都不记母亲卒年**，「輞川莊」作为私宅'
        '的时间窗因此无法闭合。\n'
        '负证同样机器复查：积雨/空林/烟火/蒸藜/东菑/漠漠/白鹭/黄鹂/野老/海鸥'
        '十个诗语在两传王维区间计数全零（生成时断言，快照变动即中止）——'
        '庄园的这一日在传中零记录。题有地名有天气，地有传锚而锚不系年：'
        '这是题证七状里第一次「地终于对上了传」，而传仍然不交出年份。'),
    'bg-jy-world': (
        '王维身后，朝廷记得他。两唐书各自记下同一幕：\n'
        '旧传代宗对宰相王缙说「卿之伯氏，天寳中詩名冠代，朕嘗於諸王座聞其樂章」，'
        '缙答「開元中詩百千餘篇，天寳事後，十不存一」，编缀得「四百餘篇」，'
        '「翌日上之，帝優詔襃賞」；新传「寶應中」代宗语缙「朕嘗于諸王座聞維樂章，'
        '今傳幾何」，遣中人王承华往取，「縉裒集數十百篇上之」——'
        '**事体三要素两源一致**（代宗于诸王座闻王维乐章+王缙奉诏裒集+上进）：'
        '**代宗诏集王维文集升 KNOWN**。\n'
        '两处分歧照登不裁决：**数量**「四百餘篇」／「數十百篇」各归其侧'
        '（audit 互斥断言）；**时间措辞**「代宗時」／「寶應中」兼容而不并轨'
        '（V039 乾元二年卒/上元初卒判例：兼容≠裁决）。乱世之后一个王朝清点'
        '一位诗人的遗产——这是「天下」层能给这首诗的最硬的上下文，'
        '但它系的是身后之事，**不外溢为写作时间**。'),
    'bg-jy-person': (
        '旧传给这个人的日常留了两笔，都只见于旧传（单得，不升）：'
        '「在京師日飯十數名僧，以玄談為樂」——在京城的饭局是斋僧；'
        '「退朝之後，焚香獨坐，以禪誦為事」——退朝后的功课是禅诵。\n'
        '新传的庄园侧则留下一句本迁移首引的：**「母亡，表輞川第為寺，'
        '終葬其西」**——把辋川第宅上表施为寺院，身后葬在其西侧'
        '（与 V035/V039 已两度立证的两句**同段异句**，V042 谱系：'
        '同段之内首尾两句已两度、此句零度——引它的不是次数，是「锚不系年」'
        '这个新事实）。母之卒年两传俱无——这座宅子变成寺的时点因此悬置，'
        '而「輞川莊作」只能悬在私宅时间窗内，窗的两边都不明。\n'
        '鳏居（V037）、奉佛（V039）、天机画评（V043）判例本迁移零重开。'),
}
CLAIMS = {
    'claim-bg-jy-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页题目两条自注+「何{{另|事|處}}」异文原样照登——'
        '先登记后引用，tang300-variants.md 新行；Textquality 75% 如实记）；'
        '湿柴迟烟/送饭田头/典出庄列为本层读法声明，非史料断言。'),
    'claim-bg-jy-city': (
        'FACT', 'LIKELY',
        '题中地名有传锚（輞川）但锚不系年：新传「母亡，表輞川第為寺」同段异句'
        '首引，母亡之年两传俱无；辋川两句 V035/V039 已两度立证本迁移不三引'
        '（边界声明）；十个诗语两传区间计数全零为机器复查负证（生成时断言）；'
        '题有地名有天气，地有传锚而锚不系年→零铸造零 relation。'),
    'claim-bg-jy-world': (
        'FACT', 'KNOWN',
        '代宗诏集王维文集事体三要素两源一致（诸王座闻乐章+缙奉诏裒集+上进）'
        '→升 KNOWN；数量分歧四百餘篇/數十百篇各归其侧不裁决（audit 互斥）；'
        '时间措辞代宗時/寶應中兼容不并轨（V039 判例）；身后之事不外溢为写作时间；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during '
        '零铸造零 relation。'),
    'claim-bg-jy-person': (
        'FACT', 'LIKELY',
        '京师饭僧/退朝禅诵两笔旧传单得（不升）；「母亡，表輞川第為寺，終葬其西」'
        '新传单得（不升）且与辋川两句同段异句（V042 谱系，本迁移首引）；'
        '母亡无年=锚不系年；鳏居 V037/奉佛 V039/天机 V043 判例零重开'
        '（audit 关键语硬卡）；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-jy-scene', 'source-ws-t300-142',
     '页面 積雨輞川莊作（header title+author+八句四联，六段以「……」相連——'
     '题目两条自注与「何{{另|事|處}}」标记原样照登（先登记后引用，'
     'tang300-variants.md 新行）；同一 (claim,source) 主键下一行容全文，'
     'V037/V039/V040/V041/V042/V043 判例；全文另见 V018 claim-t300-142-text 引文）',
     join(WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56, WS_L78)),
    ('claim-bg-jy-city', 'source-ws-t300-142',
     '页面 積雨輞川莊作（header title 单字段——负证的引文形态：题中的地名天气'
     '即证据本体，八句诗身另在 SCENE 层；传锚侧的负证为两传区间十诗语计数全零，'
     '生成时机器复查；辋川两句 V035/V039 已两度立证本迁移不三引——边界声明）',
     WS_TITLE),
    ('claim-bg-jy-world', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传代宗诏集段（诗名冠代/十不存一/四百余篇/'
     '翌日上之优诏褒赏——两源合龙旧传侧逐字；数量措辞归旧侧）', JTS_DZ),
    ('claim-bg-jy-world', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王维传宝应诏集段（宝应中/诸王座闻维乐章/遣王承华往取/'
     '裒集数十百篇——两源合龙新传侧逐字；数量措辞归新侧，与旧侧各归其侧不裁决）',
     XTS_BY),
    ('claim-bg-jy-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传日常两笔（京师饭僧玄谈+退朝焚香禅诵，'
     '两段以「……」相連，同卷同传——皆旧传单得不升）', join(JTS_ZJ, JTS_CS)),
    ('claim-bg-jy-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王维传施宅为寺句（母亡/表輞川第為寺/终葬其西——'
     '本迁移首引；与辋川两句同段异句，V042 谱系声明在此；母亡之年两传俱无）',
     XTS_SI),
]
BG_LINES = {'bg-jy-scene': (1, 2), 'bg-jy-city': (3, 4), 'bg-jy-world': (5, 6), 'bg-jy-person': (7, 8)}
BG_AUDIENCE = {'bg-jy-scene': 'PRIMARY', 'bg-jy-city': 'JUNIOR',
               'bg-jy-world': 'SENIOR', 'bg-jy-person': 'SENIOR'}
BG_TITLES = {'bg-jy-scene': '眼前：连阴天把日程放慢',
             'bg-jy-city': '这座城：锚点在晃',
             'bg-jy-world': '这个天下：朝廷记得他',
             'bg-jy-person': '这个人：宅子施给了寺'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 25 首·八句 2/2/2/2）；史实句均有逐字引证；'
                 'background_line 八句形制：每层两行（1-2/3-4/5-6/7-8）；'
                 '系年第十九次判决「题有地名有天气，地有传锚而锚不系年」'
                 '（题证系列第七状·首见题地正有传）→time.span/event.name/'
                 'written_during 全缺席、零 relation；KNOWN 一处（代宗诏集'
                 '文集事体三要素两源一致）；数量分歧四百餘篇/數十百篇各归'
                 '其侧不裁决（audit 互斥）；负证机器复查十诗语两传区间计数全零；'
                 '辋川两句两度已立不三引、施宅为寺句同段异句首引；'
                 '鳏居/奉佛/天机判例只引不重开。' for k in BG}


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
    A("""-- V044：王维《積雨輞川莊作》(work-t300-142) 四层背景（阶段 D 第 25 首·八句 2/2/2/2）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-142 与其 text-work-t300-142-ws、
--       source-ws-t300-142 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行——均不另开）。本迁移零新 source（断言）。
--
-- 数据源（可复现）：emit_v044.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/積雨輞川莊作.txt（题目两条自注+一处 {{另}} 异文原样照登，先登记后引用）、
--   舊唐書卷190下（日常两笔+代宗诏集段）、新唐書卷202（施宅为寺句+宝应诏集段）——
--   五段切片传区间归属生成时断言；十个诗语两传区间计数全零生成时断言（负证机器复查）。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   6 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句形制：scene→1-2 city→3-4 world→5-6 person→7-8，
--   绑 text-work-t300-142-ws 的 8 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「题有地名有天气，地有传锚而锚不系年」）：
--   * 全池第一首题中之地正有传锚（輞川）——但新传「母亡，表輞川第為寺」不记母亡之年，
--     私宅时间窗两边不明；天气（積雨）钉死是体感/气象的，不是历法的；
--   * 辋川两句 V035/V039 已两度逐字立证——**同句两度为上限，本迁移不三引**；
--     本层新句「表輞川第為寺」为零度异句首引（V042 同段异句谱系）；
--   * KNOWN 一处：代宗诏集文集事体三要素两源一致——**身后之事不外溢为写作时间**；
--     数量分歧四百餘篇/數十百篇各归其侧不裁决（audit 互斥），
--     时间措辞代宗時/寶應中兼容不并轨（V039 判例）；
--   * 鳏居（V037）/奉佛（V039）/天机画评（V043）判例只引不重开（audit 关键语硬卡）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 43，不含 44
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-jy-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-142-ws';  -- 恰 8（七律）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-jy-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-142';                                  -- 8（每层两行）
--   SELECT certainty FROM poetry_claim WHERE id = 'claim-bg-jy-world';  -- KNOWN（代宗诏集两源）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-jy-scene','claim-bg-jy-city','claim-bg-jy-person');
--     -- LIKELY / LIKELY / LIKELY
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-142'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-142';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-jy-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V044_rollback.sql（按 id 全枚举删除；不动 V018/V035/V037/V039/V043 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-142',
              'layer': {'bg-jy-scene': 'SCENE', 'bg-jy-city': 'CITY',
                        'bg-jy-world': 'WORLD', 'bg-jy-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-142-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 44, 'Wang Wei Rainy Season at the Wang-chuan Estate background layers (stage-D poem 25, 2/2/2/2): dating verdict nineteen, seventh shape of the title-evidence series and the first where the place in the title does have a biography anchor -- the anchor itself wavers: XTS mu-wang, biao Wang-chuan di wei si (upon the death of his mother the estate was converted into a monastery) records no year for that death, so the time-window of the private estate cannot be closed; weather pinned (continuous rain), place pinned (Wang-chuan), year still absent -- zero forging, zero relation; the two established Wang-chuan sentences (quoted verbatim twice, V035 and V039) get no third citation -- the new same-paragraph different-sentence line is cited for the un-anchored anchor, not for count (V042 lineage); one KNOWN: Emperor Daizong ordered the collection of the works of Wang Wei -- substance agrees across both histories on three elements (heard his music at the seats of the princes, Wang Jin ordered to compile, compilation presented), while the count diverges (four hundred-odd vs several tens-to-hundreds, each kept on its own side, mutual-exclusion asserted) and the time wording (in the reign of Daizong vs in Baoying) is compatible but not merged (V039 precedent: compatibility is not a ruling) -- and a posthumous affair never overflows into the writing time of the poem; ten poem-words counted zero across both biography spans, asserted at generation time (machine re-check of the negative evidence); the widower/piety/tian-ji lines stay closed precedents (audit keyword zero-entry); zero new sources'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 44);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V044 精确回滚：只删 V044 插入的行（id 全枚举）。',
         '-- work-t300-142 本体、其 text_line 8 行与 source-ws-t300-142 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi）与 V035/V037/V039/V043 的行不删；',
         '-- V044 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 44;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_L12, WS_L34, WS_L56, WS_L78,
              JTS_ZJ, JTS_CS, JTS_DZ, XTS_SI, XTS_BY]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 异文照登断言：ws 页的三类标记必须原样进 ws 引文（有标记且已登记→必须照登）
    ws_ex = ''.join(ex for _, s, _, ex in CITATIONS if s == 'source-ws-t300-142')
    for tok in ('{{*|一有上字}}', '{{*|一作秋歸輞川莊作}}', '{{另|事|處}}'):
        if tok not in ws_ex:
            bad.append(f'ws 页内标记未原样照登: {tok}（先登记后引用，不可静默剥离）')
    # 代宗诏集两源合龙断言（事体三要素：诸王座闻乐章 / 缙（集/裒集）/ 上之）
    w_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-jy-world' and s == 'source-jiutangshu-wenyuan')
    w_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-jy-world' and s == 'source-xintangshu-wenyi')
    if '諸王座' not in w_jts or '諸王座' not in w_xts:
        bad.append('代宗诏集两源不齐（诸王座闻乐章须两侧在场）')
    if '縉' not in w_jts or '縉' not in w_xts:
        bad.append('代宗诏集两源不齐（王缙须两侧在场）')
    # 数量分歧互斥（四百餘篇归旧侧、數十百篇归新侧，不得串写）
    if '數十百篇' in w_jts:
        bad.append('数量分歧串侧（數十百篇不得入旧传侧）')
    if '四百餘篇' in w_xts:
        bad.append('数量分歧串侧（四百餘篇不得入新传侧）')
    # 锚不系年：CITY/PERSON 引文含施宅为寺句；且引文里不得混入母亡年号（本就无年可混）
    p_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-jy-person' and s == 'source-xintangshu-wenyi')
    if '表輞川第為寺' not in p_xts:
        bad.append('施宅为寺句未入 PERSON 新传侧（锚不系年的本体证据）')
    # CITY 负证：引文零诗语（题锚本体即证据，诗身不代拟）
    for c, s, _, ex in CITATIONS:
        if c == 'claim-bg-jy-city':
            for w in ('煙火', '蒸藜', '白鷺', '黃鸝', '朝槿', '露葵', '海鷗', '爭席'):
                if w in ex:
                    bad.append(f'CITY 层证据不得含诗语「{w}」')
    # 判例只引不重开（V035/V037/V039/V041/V043 关键语零入引文）
    for tok in ('得宋之問藍田别墅', '地奇勝，有華子岡', '妻亡不再娶', '喪妻不娶',
                '蔬食', '篤志奉佛', '竹溪六逸', '霓裳', '絕迹天機', '天機所到'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句形制
    if sum(len(v) for v in BG_LINES.values()) != 8 or any(len(v) != 2 for v in BG_LINES.values()):
        bad.append('八句 background_line 必须是每层恰 2 行（4 层共 8 行）')
    if len(re.findall(r"text-work-t300-142-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V044 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V044 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-142' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V044 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-142' AS subject_id" in sql:
        bad.append('V044 的 claim 主语应全部是 bg-jy-*，work-t300-142 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V044 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V044 零新 source，不该出现 INSERT INTO poetry_source')
    body_all = ''.join(BG.values()) + sql
    if '锚不系年' not in body_all:
        bad.append('BG/文件头须含「锚不系年」判决声明')
    if '不三引' not in body_all:
        bad.append('BG/文件头须含「辋川两句不三引」边界声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 11 切片逐字过审且全部进引文；'
              f'切片传区间归属断言；负证机器复查（十诗语两传区间计数全零，快照变动即中止）；'
              f'ws 三类异文标记原样照登断言；代宗诏集事体两源合龙断言（三要素）；'
              f'数量分歧互斥断言（四百餘篇/數十百篇各归其侧）；施宅为寺句入引断言；'
              f'CITY 零诗语断言；判例只引不重开断言（辋川两句/鳏居/奉佛/天机/霓裳关键语零入引文）；'
              f'不三引边界声明断言；八句每层两行形制断言；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'零新 source 已断言；诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
