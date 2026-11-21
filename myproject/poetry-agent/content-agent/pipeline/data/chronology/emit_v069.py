#!/usr/bin/env python3
"""阶段 D 第 50 首：生成 V069——李商隱《寄令狐郎中》(work-t300-016, V018 已立) 四层背景。

**本迁移零新建 source**——连续三首开新源（V066/V067/V068）到此终结，回到零新源侧。
理由是本诗恰是那三首的**镜像**：V018 给本诗立正文用的是 **ws《唐詩三百首》诗页**
（text-work-t300-016-ws，version_code **'ws-raw'**，source-ws-t300-016 已存在，域
['V018']）——《全唐詩》卷539 卷页这个见证面**从未被引过**。V066–V068 是「底本=卷页、
欠诗页」，本篇是「底本=诗页、欠卷页」：**两个见证面先入哪个，另一个就欠着**；
本迁移补引卷页（source-quantangshi-539 第四次复用，V018/V067/V068 在册），
正文**第二引上限用满**——两引两面（诗页+卷页）不重叠。

「为什么写」走到**寄与不省两界**（同字两界第十四形态·寄答形态首见）：
**诗一纸书寄往的收件人，通鉴里做到十年宰相，史部给他的考语是「忌」，
他自己在皇帝面前汗湿了衣裳；通鉴唯一的司马相如，是奏疏里"当不了大官"的反面教材**——

诗题「寄令狐郎中」是这首诗唯一的史实锚点（收件人姓名+官衔），通鉴以繁体「令狐綯」
恰十八处五卷把他写成一个宰相（机器断言；通鉴简体「令狐绹」全零——**同一人跨库
字体分工：通鉴繁体「綯」，旧传简体「绹」**）。四层判决：
① 通鉴记他进身靠的是父亲——大中元年（丁卯，八四七）宣宗追元和旧事「惟山陵使
長而多髯，攀靈駕不去」问「有子乎？」答「次子綯，前湖州刺史，有才器。」大中二年
（戊辰，八四八）「以知制誥令狐綯為翰林學士」：**诗的收件人第一次进通鉴，
是以孝子的儿子身份**；
② 大中十一年（丁丑，八五七）窗口三连：**李远案**「令狐綯擬李遠杭州刺史，上曰：
『吾聞遠詩云：「長日惟消一局棋」，安能理人！』綯曰：『詩人托此為高興耳，未必實然。』」
——**宰相替诗人向皇帝解释"那句诗只是写着玩"；诗寄令狐郎中求的正是提拔，
通鉴记他反着办**（另一处「然竟以剛直為令狐綯所忌而出之」——**史部给綯的考语
是忌贤**）+「吾十年秉政，最承恩遇；然每延英奏事，未嘗不汗沾衣也！」——
**十年宰相的病是汗，诗人自比的病是雨**；
③ 通鉴「司馬相如」恰一处（長壽元年壬辰六九二奏疏「昔漢武帝見司馬相如賦，
恨不同時，及置之朝廷，終文園令」）——**通鉴唯一的司马相如是"虚文不堪公卿之任"的
教材；诗自比"病相如"，史部说相如本来就做不了大官**；
④ 通鉴「背恩」恰一处（永泰元年乙巳七六五郭子仪责回纥「背恩德而助叛臣」），
而旧传用同一顶帽子判李商隐（简体「以商隐背恩」）——**同一词，史部扣外族，
传部扣诗人**；诗面「茂陵/梁園/秋雨/一紙書/舊賓客/病相如/雙鯉/嵩雲/秦樹」通鉴全零。

ws 页形制（SCENE/CITY 层）：**{{Textquality|100%}} 满级页首见**（V055/V057/V061/
V062 75% 侧、V066/V067/V068 无评级侧、本篇 100% 侧——**评级谱三态齐备**）；
**notes 行内嵌「↑ [[全唐詩/卷539#寄令狐郎中|全唐詩·卷五百三十九]]」底本回指链接
首见**（选本页自己指回底本卷页——**卷页/诗页两个见证面在页面内部自我声明**）；
poem 块四句**全无句读**第三见（V067 首见/V068 第二）——**100% 评级与无句读并存：
评级度量转录完备，与句读正交**；{{另}}/{{別}}/{{*}}/<ref> 全零；分类三行简繁混排
第四见；title 裸名+ws 文件名裸名+卷539 锚裸名**两端皆裸名**（无同名诗，消歧链
裸侧第四见，V061/V062/V063 判例——全唐诗「寄令狐郎中」恰一，机器断言闭域）。

PERSON 层：旧传（**简化字**）段首引二句（皆零域）——「**子绹为员外郎，以商隐背恩，
尤恶其无行。**」「**茂元爱其才，以子妻之。**」：诗题官衔「郎中」对上史传官衔
「员外郎」（郎之副），**一纸书要泯的正是这一行里的"背恩""无行"四字**；下句给出
"背恩"之实（改投王茂元、尚其女）——**一封短信抵不上一次婚姻**（读法声明）；
段内相如/茂陵/秋雨/双鲤/一纸/旧宾/梁园全零；V016/V066/V067/V068 在册句零重开。

4 句七绝 shape：1/1/1/1 第六次（V056/V061/V066/V067/V068 之后）。

用法: python3 -I emit_v069.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402

WS = pathlib.Path('/tmp/src-dl/ws-poems/寄令狐郎中.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
V539 = pathlib.Path('/tmp/src-dl/quantangshi/vol539.txt').read_text(encoding='utf-8')
TJ205 = pathlib.Path('/tmp/src-dl/tongjian/tj-205.txt').read_text(encoding='utf-8')
TJ223 = pathlib.Path('/tmp/src-dl/tongjian/tj-223.txt').read_text(encoding='utf-8')
TJ248 = pathlib.Path('/tmp/src-dl/tongjian/tj-248.txt').read_text(encoding='utf-8')
TJ249 = pathlib.Path('/tmp/src-dl/tongjian/tj-249.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 寄令狐郎中', '| title    = 寄令狐郎中',
                         'ws header title(裸名题面=收件人官衔题)')
WS_AUTHOR = slice_between(WS, '| author   = 李商隱', '| author   = 李商隱', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS,
                        '| notes    = {{Textquality|100%}}↑ [[全唐詩/卷539#寄令狐郎中|全唐詩·卷五百三十九]]{{唐詩三百首}}',
                        '| notes    = {{Textquality|100%}}↑ [[全唐詩/卷539#寄令狐郎中|全唐詩·卷五百三十九]]{{唐詩三百首}}',
                        'ws 页底注行(100% 满级+↑底本回指链接首见——选本页自己指回卷页)')
WS_CAT = slice_between(WS, '[[Category:李商隱]]', '[[Category:唐詩三百首|李]]',
                       'ws 分类三行连片(简繁混排第四见)')
V539_BLOCK = slice_between(V539, '==[[寄令狐郎中]]==\n<poem>\n嵩雲秦樹久離居', '茂陵秋雨病相如\n</poem>',
                           '卷539 本篇块(锚==[[寄令狐郎中]]==全唐诗唯一;本诗卷页见证面首引)')
TJ_SB1 = slice_between(TJ248, '惟山陵使長而多髯，攀靈駕不去，誰也？', '次子綯，前湖州刺史，有才器。」',
                       '通鉴大中元年宣宗问元和旧事(令狐綯入通鉴以孝子之子身份;窗口断言)')
TJ_SB2 = slice_between(TJ248, '以知制誥令狐綯為翰林學士', '以知制誥令狐綯為翰林學士',
                       '通鉴大中二年令狐綯除翰林学士(收件人的官历;窗口断言)')
TJ_LY = slice_between(TJ249, '令狐綯擬李遠杭州刺史', '未必實然。」',
                      '通鉴大中十一年李远案(宰相替诗人解释那句诗;窗口断言)')
TJ_JI = slice_between(TJ249, '然竟以剛直為令狐綯所忌而出之。', '然竟以剛直為令狐綯所忌而出之。',
                      '通鉴大中十一年刚直为綯所忌(史部给綯考语=忌贤;窗口断言)')
TJ_HAN = slice_between(TJ249, '吾十年秉政，最承恩遇；然每延英奏事，未嘗不汗沾衣也！」',
                       '吾十年秉政，最承恩遇；然每延英奏事，未嘗不汗沾衣也！」',
                       '通鉴大中十一年綯自言汗沾衣(十年宰相的病是汗;窗口断言)')
TJ_XRW = slice_between(TJ205, '昔漢武帝見司馬相如賦，恨不同時', '終文園令',
                       '通鉴长寿元年奏疏引司马相如(通鉴唯一司马相如=不堪公卿之任教材;窗口断言)')
TJ_BY = slice_between(TJ223, '背恩德而助叛臣', '背恩德而助叛臣',
                      '通鉴永泰元年郭子仪责回纥(通鉴唯一背恩——同一帽旧传扣诗人;窗口断言)')
JTS_P1 = slice_between(JTS, '子绹为员外郎，以商隐背恩', '尤恶其无行。',
                       '旧传李商隐段(令狐绹员外郎+背恩无行——诗题官衔与史传官衔对上;PERSON 首引)')
JTS_P2 = slice_between(JTS, '茂元爱其才', '以子妻之。',
                       '旧传李商隐段(茂元以子妻之——"背恩"之实;PERSON 首引)')

# ---------- 传区间归属复验（段界 ==弟 羲叟==） ----------
_ja = JTS.find('=李商隱=')
_jm = re.search(r'\n==[^=\n]{1,12}==', JTS[_ja + 8:])
_seg_j = JTS[_ja:_ja + 8 + _jm.start()]
for _needle in (JTS_P1, JTS_P2):
    if _needle not in _seg_j:
        raise SystemExit('PERSON 首引句越出旧传李商隐段——修订后重生成')

# ---------- 通鉴年标题窗口断言 ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 90]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ248, TJ_SB1, '大中元年')
_window(TJ248, TJ_SB2, '大中二年')
_window(TJ249, TJ_LY, '大中十一年')
_window(TJ249, TJ_JI, '大中十一年')
_window(TJ249, TJ_HAN, '大中十一年')
_window(TJ205, TJ_XRW, '長壽元年')
_window(TJ223, TJ_BY, '永泰元年')

# ---------- 负证机器复查 ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：诗面语全零；令狐綯恰十八五卷；简体绹全零；司馬相如/文園/背恩各恰一；汗沾衣恰二
for _w in ('茂陵', '梁園', '秋雨', '一紙書', '舊賓客', '病相如', '雙鯉', '嵩雲', '秦樹', '令狐綯郎中'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗面不进史部的判决失效，须重读')
if _alltj.count('令狐绹') != 0:
    raise SystemExit('通鉴出现简体「令狐绹」——跨库字体分工（通鉴繁体綯/旧传简体绹）判决须重估')
_ld = {n: t.count('令狐綯') for n, t in _tjf.items() if '令狐綯' in t}
if sum(_ld.values()) != 18 or len(_ld) != 5:
    raise SystemExit(f'通鉴「令狐綯」不再恰十八处五卷（实 {sum(_ld.values())}）——收件人成宰相判决须重估')
if _alltj.count('司馬相如') != 1 or _alltj.count('文園') != 1:
    raise SystemExit('通鉴「司馬相如/文園」不再各恰一——唯一相如教材判决须重估')
if _alltj.count('背恩') != 1:
    raise SystemExit('通鉴「背恩」不再恰一——同一帽两处扣判决须重估')
if _alltj.count('汗沾衣') != 2:
    raise SystemExit('通鉴「汗沾衣」不再恰二（另一处林甫/禄山在册）——闭域须重估')
if _alltj.count('長日惟消一局棋') != 1:
    raise SystemExit('通鉴「長日惟消一局棋」不再恰一——李远案在册须重估')
# ② 全唐诗：锚全库唯一；字面恰一；卷内三语自足
if _allq.count('==[[寄令狐郎中]]==') + _allq.count('==寄令狐郎中==') != 1:
    raise SystemExit('《全唐詩》「寄令狐郎中」锚不再全库唯一——裸名标本判决失效')
if _allq.count('寄令狐郎中') != 1:
    raise SystemExit('全唐詩「寄令狐郎中」字面不再恰一——两端裸名无同名判决须重估')
for _w in ('寄令狐郎中', '一紙書', '舊賓客', '病相如', '茂陵秋雨'):
    if V539.count(_w) != 1:
        raise SystemExit(f'卷539「{_w}」不再恰一——诗语卷内自足闭域失效')
if V539.count('秋雨') != 2 or V539.count('相如') != 4 or V539.count('離居') != 2:
    raise SystemExit('卷539「秋雨/相如/離居」他诗混片计数变了——闭域档扫须重估')
# ③ ws：满级评级 + 底本回指 + 零标记 + poem 无句读 + 双转录 + 分类三行
if WS.count('{{Textquality|100%}}') != 1:
    raise SystemExit('ws 页不再恰一枚 Textquality|100%——满级页首见断言失效')
if WS.count('↑ [[全唐詩/卷539#寄令狐郎中|全唐詩·卷五百三十九]]') != 1:
    raise SystemExit('ws 页底本回指链接结构变了（↑底本回指首见断言失效）')
if WS.count('{{另') or WS.count('{{別') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页出现异文/注记标记——零标记断言失效')
if '茂陵秋雨病相如。' in WS or '嵩雲秦樹久離居，' in WS:
    raise SystemExit('ws poem 块出现句读——100% 评级×无句读正交断言失效')
if WS.count('嵩雲秦樹久離居') != 2 or WS.count('茂陵秋雨病相如') != 2:
    raise SystemExit('ws 页 Vtext/poem 双转录结构变了（首末句页内应各恰 2）')
_cat = '[[Category:李商隱]]\n[[Category:唐诗]]\n[[Category:唐詩三百首|李]]'
if WS.count(_cat) != 1:
    raise SystemExit('ws 页分类三行连片结构变了（简繁混排第四见断言失效）')
# ④ 旧传李商隐段负证（简体诗语全零）
for _w in ('相如', '茂陵', '秋雨', '双鲤', '一纸', '旧宾', '梁园'):
    if _seg_j.count(_w) != 0:
        raise SystemExit(f'「{_w}」落在旧传李商隐段——段级零证失效，须重读原文')

POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V069')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

def _domain_src(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V069')
                   and needle in f.read_text(encoding='utf-8')})

for _premise, _needle, _want in (
        ('本诗首句(V018 诗页一引)', '嵩雲秦樹久離居', ['V018']),
        ('本诗末句', '茂陵秋雨病相如', ['V018']),
        ('卷页源复用面', 'source-quantangshi-539', ['V018', 'V067', 'V068']),
        ('诗页源在先', 'source-ws-t300-016', ['V018']),
        ('V066 不之省句', '绹不之省', ['V066', 'V067']),
        ('V068 当涂薄句', '为当涂者所薄', ['V068'])):
    _prev = _domain_src(_needle) if _needle.startswith('source-') else _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
for _first, _needle in (('孝子之子', '次子綯，前湖州刺史'), ('綯入翰林', '以知制誥令狐綯為翰林學士'),
                        ('李远案', '令狐綯擬李遠杭州刺史'), ('綯忌贤', '為令狐綯所忌而出之'),
                        ('綯汗衣', '未嘗不汗沾衣也'), ('相如教材', '終文園令'),
                        ('史部背恩', '背恩德而助叛臣'), ('员外郎恶无行', '尤恶其无行'),
                        ('茂元妻女', '以子妻之')):
    if _domain(_needle):
        raise SystemExit(f'首引前提破了：「{_needle}」（{_first}）既往有引（{_domain(_needle)}）——须重设计')

BG = {
    'bg-016-scene': (
        '四句是一封短信：嵩山的云、秦地的树，我与你久隔（「嵩雲秦樹久離居」）；'
        '双鲤（古乐府「客从远方来，遗我双鲤鱼」——函札）迢迢送来一纸书'
        '（「雙鯉迢迢一紙書」）；别再问当年梁园（梁孝王游士之园，借指令狐楚幕）的旧宾客了'
        '（「休問梁園舊賓客」）——我如今像茂陵秋雨里病着的司马相如'
        '（「茂陵秋雨病相如」）。'
        'ws 诗页 notes **内嵌「↑ [[全唐詩/卷539#寄令狐郎中|全唐詩·卷五百三十九]]」'
        '底本回指链接——选本页自己指回底本卷页首见**（两个见证面在页面内部自我声明）；'
        '**{{Textquality|100%}} 满级页首见**（V055/V057/V061/V062 75% 侧、'
        'V066/V067/V068 无评级侧、本篇 100% 侧——**评级谱三态齐备**）；'
        'poem 块四句**全无句读**第三见（V067 首见）——**100% 评级与无句读并存：'
        '评级度量转录完备，与句读正交**；title 裸名、{{另}}/{{別}}/{{*}}/<ref> 全零；'
        '页内 Vtext/poem 双转录并存（首末句页内各恰 2）。'
        '**此诗正文系第二引**：V018 已引 ws 诗页（text-work-t300-016-ws，'
        'version_code 「ws-raw」，source-ws-t300-016）在先，本迁移改引《全唐詩》卷539 卷页'
        '（CITY 层）——**两引两面（诗页+卷页）不重叠，上限恰满**；本 SCENE 只引页形制'
        '三行（title/author/notes）不复引正文，生成时断言首末句不入 SCENE 引文。'),
    'bg-016-city': (
        '卷539 侧：本篇锚「==[[寄令狐郎中]]==」**全《全唐詩》唯一**（机器断言：'
        '全库扫描锚恰一，且字面「寄令狐郎中」全唐诗**恰一**——无同名诗，两端裸名'
        '（ws 文件名/卷页锚点皆裸名，消歧链裸侧第四见，V061/V062/V063 判例——'
        '无同名则无消歧器））；卷内「一紙書/舊賓客/病相如/茂陵秋雨」各恰一=诗面自足，'
        '「秋雨/相如/離居」为 2/4/2 他诗混片（闭域档扫）。（本层零 relation。）'
        '**本迁移零新建 source——连续三首开新源（V066/V067/V068）到此终结，回到零新源侧**；'
        '理由是本诗是那三首的**镜像**：V018 给本诗立正文用的是 ws 诗页（ws-raw，'
        'source-ws-t300-016 已存在），《全唐詩》卷539 卷页这个见证面从未被引过——'
        '那三首是「底本=卷页、欠诗页」，本篇是「底本=诗页、欠卷页」；'
        '**两个见证面先入哪个，另一个就欠着**。本迁移补引卷页'
        '（source-quantangshi-539 第四次复用，V018/V067/V068 在册），'
        '正文**第二引上限用满第十七例**。ws 页 notes 底本回指（↑卷539 链接）'
        '与分类三行简繁混排第四见（整理者分类：非史料声明、不升格，V048 判例）——'
        '**选本页用一行底本注，把自己与底本卷页焊成一个证据对**。'),
    'bg-016-world': (
        '**诗一纸书寄往的人，通鉴里做了十年宰相；史部给他的考语是「忌」，'
        '他自己在皇帝面前汗湿了衣裳**（同字两界第十四形态·寄答形态首见）：'
        '诗题「寄令狐郎中」是这首诗唯一的史实锚点（收件人姓名+官衔），通鉴以繁体'
        '「**令狐綯**」恰十八处五卷把他写成宰相（机器断言；通鉴简体「令狐绹」全零——'
        '**同一人跨库字体分工：通鉴繁体「綯」，旧传简体「绹」**）。'
        '① 他进身靠父亲：大中元年（丁卯，八四七）宣宗追元和旧事「**惟山陵使長而多髯，'
        '攀靈駕不去，誰也？**」对以令狐楚，问「有子乎？」——「**次子綯，前湖州刺史，'
        '有才器。**」大中二年（戊辰，八四八）「**以知制誥令狐綯為翰林學士。**」：'
        '**诗的收件人第一次进通鉴，是以孝子的儿子身份**；'
        '② 大中十一年（丁丑，八五七）三连：**李远案**「**令狐綯擬李遠杭州刺史，上曰：'
        '「吾聞遠詩云：『長日惟消一局棋』，安能理人！」綯曰：「詩人托此為高興耳，'
        '未必實然。」**」——**宰相替诗人向皇帝解释「那句诗只是写着玩」；诗寄令狐郎中'
        '求的正是提拔，通鉴记他反着办**；又「**然竟以剛直為令狐綯所忌而出之。**」——'
        '**史部给綯的考语是忌贤**；又「**吾十年秉政，最承恩遇；然每延英奏事，'
        '未嘗不汗沾衣也！**」——**十年宰相的病是汗，诗人自比的病是雨**；'
        '③ 通鉴「**司馬相如**」恰一处（長壽元年壬辰六九二奏疏「**昔漢武帝見司馬相如賦，'
        '恨不同時，及置之朝廷，終文園令**」）——**通鉴唯一的司马相如是「虚文不堪公卿之任」'
        '的教材；诗自比「病相如」，史部却说相如本来就做不了大官**；'
        '④ 通鉴「**背恩**」恰一处（永泰元年乙巳七六五郭子仪责回纥「**背恩德而助叛臣**」），'
        '而旧传用同一顶帽子判李商隐（简体「以商隐背恩」，PERSON 层）——'
        '**同一词，史部扣外族，传部扣诗人**；'
        '诗面「茂陵/梁園/秋雨/一紙書/舊賓客/病相如/雙鯉/嵩雲/秦樹」通鉴全零（机器断言）；'
        '「汗沾衣」恰二（另一处 tj-216 禄山见李林甫常汗沾衣在册零入引）、「長日惟消一局棋」'
        '恰一在册。本层零铸造零 relation。'),
    'bg-016-person': (
        '旧传李商隐段（**简化字录入**，V016 locator 同款标注，引文照登简体原样）'
        '首引二句（皆零域）：「**子绹为员外郎，以商隐背恩，尤恶其无行。**」'
        '「**茂元爱其才，以子妻之。**」\n'
        '诗题官衔「寄令狐**郎中**」对上史传官衔「员外**郎**」（郎之副）——'
        '这封信寄到的时刻，收件人正卡在这一行官阶上；而这一行同时落下"背恩""无行"'
        '四字——**一纸书要泯的，正是这一行里的「背恩」「无行」**。\n'
        '下句给出"背恩"之实：王茂元爱其才把女儿嫁他（转投与李德裕交好的王家，'
        '时令狐楚已卒、牛李党争方炽）——**一封短信抵不上一次婚姻**（读法声明，非史实）。'
        '「以商隐背恩，尤恶其无行」系**史臣笔底绹意**（照登，certainty LIKELY——'
        '非自家供状）；段内**相如/茂陵/秋雨/双鲤/一纸/旧宾/梁园全零**（机器断言，'
        '段级零证）；V016「字义山/开成二年/岭表/三十六体」、V066「绹不之省/坎壈终身」、'
        'V067「以所业文干之/下笔不能自休」、V068「为当涂者所薄」在册句零重开（域断言）；'
        '本诗无底注（无注可登）；certainty 不覆盖任何系年，诗 time.span/event.name/'
        'written_during 仍零铸造（audit 硬卡）。'),
}
CLAIMS = {
    'claim-bg-016-scene': (
        'FACT', 'LIKELY',
        '四句七绝本文（ws 选本页 poem 块四句**全无句读**第三见，各从其录）；'
        'notes 内嵌「↑ [[全唐詩/卷539#…]]」底本回指链接首见（选本页自指底本卷页）；'
        '{{Textquality|100%}} 满级页首见（75%/无评级/100% 评级谱三态齐备）；'
        '**100% 评级×poem 无句读并存（评级度量转录完备，与句读正交）**；title 裸名；'
        '{{另}}/{{別}}/{{*}}/<ref> 全零；页内 Vtext/poem 双转录并存首末句各恰 2；'
        '全句**第二引**：V018 已引 ws 诗页（source-ws-t300-016，ws-raw）在先，'
        '本迁移改引卷页（两引两面不重叠，上限恰满第十七例），本 SCENE 只引页形制'
        '三行不复引正文（生成时断言首末句不入 SCENE 引文）；此后此诗正文对后来迁移关闭。'),
    'claim-bg-016-city': (
        'FACT', 'LIKELY',
        '本篇锚「==[[寄令狐郎中]]==」**全《全唐詩》唯一**（机器断言：锚恰一，'
        '字面恰一——无同名诗则两端裸名，消歧链裸侧第四见，V061/V062/V063 判例）；'
        '卷内一紙書/舊賓客/病相如/茂陵秋雨各恰一（诗面自足），秋雨/相如/離居'
        '2/4/2 他诗混片闭域档扫；**零新建 source（连续三首开新源终结，回零新源侧）——'
        '本诗是 V066–V068 的镜像：V018 底本是 ws 诗页（ws-raw）、卷页从未被引**；'
        '「两个见证面先入哪个，另一个就欠着」；补引 source-quantangshi-539'
        '（第四次复用，V018/V067/V068 在册）；ws notes 底本回指+分类三行简繁混排'
        '第四见（非史料声明、不升格，V048 判例）——选本页以底本注与卷页焊成证据对。'),
    'claim-bg-016-world': (
        'FACT', 'LIKELY',
        '通鉴以繁体「令狐綯」恰十八处五卷写成宰相（机器断言；通鉴简体「令狐绹」全零——'
        '跨库字体分工：通鉴繁体綯/旧传简体绹）；诗面茂陵/梁園/秋雨/一紙書/舊賓客/'
        '病相如/雙鯉/嵩雲/秦樹通鉴全零；大中元年（丁卯，八四七）宣宗问元和旧事'
        '「惟山陵使長而多髯攀靈駕不去」+「次子綯前湖州刺史有才器」+大中二年'
        '（戊辰，八四八）「以知制誥令狐綯為翰林學士」三窗口逐字入引——**收件人'
        '第一次进通鉴以孝子之子身份**；大中十一年（丁丑，八五七）三连入引=李远案'
        '「令狐綯擬李遠杭州刺史…『長日惟消一局棋』安能理人…詩人托此為高興耳」'
        '**宰相替诗人解释那句诗**+「剛直為令狐綯所忌而出之」**史部考语忌贤**+'
        '「吾十年秉政…未嘗不汗沾衣也」**宰相病在汗、诗人病在雨**（同字两界第十四'
        '形态·寄答形态首见，audit 硬卡）；通鉴司馬相如恰一（長壽元年壬辰六九二'
        '「昔漢武帝見司馬相如賦恨不同時終文園令」——唯一相如=不堪公卿教材）；'
        '通鉴背恩恰一（永泰元年乙巳七六五郭子仪责回纥「背恩德而助叛臣」——'
        '同一帽旧传扣诗人）；汗沾衣恰二/長日惟消一局棋恰一在册零入引；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-016-person': (
        'FACT', 'LIKELY',
        '旧传李商隐段（简化字录入，照登原样）首引二句皆生成时全库查重域恰零='
        '「子绹为员外郎，以商隐背恩，尤恶其无行。」+「茂元爱其才，以子妻之。」'
        '（传区间归属机器断言）；诗题官衔「郎中」对史传官衔「员外郎」（郎之副）——'
        '一纸书要泯的正是「背恩」「无行」；「一封短信抵不上一次婚姻」系读法声明；'
        '「以商隐背恩，尤恶其无行」系史臣笔底绹意（照登 LIKELY）；段内相如/茂陵/'
        '秋雨/双鲤/一纸/旧宾/梁园全零（机器断言，段级零证）；V016/V066/V067/V068 '
        '在册句零重开（域断言）；本诗无底注；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-016-scene', 'source-ws-t300-016',
     '页面 寄令狐郎中（《唐詩三百首》第 16 首选本页，页题裸名；title+author+notes 三行'
     '——**notes 内嵌「↑ [[全唐詩/卷539#寄令狐郎中|全唐詩·卷五百三十九]]」底本回指链接'
     '首见**（选本页自指底本卷页）+{{Textquality|100%}} 满级页首见；poem 块全无句读'
     '（100% 评级×无句读正交，评级度量转录完备）；本 SCENE 不复引正文——正文 V018'
     '诗页一引在先，本迁移引卷页，两引两面不重叠（生成时断言首末句不入此引文）；'
     '{{另}}/{{別}}/{{*}}/<ref> 全零）',
     join(WS_TITLE, WS_AUTHOR, WS_NOTE)),
    ('claim-bg-016-city', 'source-quantangshi-539',
     '卷五百三十九·李商隱《寄令狐郎中》块（锚「==[[寄令狐郎中]]==」**全《全唐詩》唯一**'
     '——字面恰一无同名诗，两端裸名消歧链裸侧第四见；卷内一紙書/舊賓客/病相如/茂陵秋雨'
     '各恰一（诗面自足），秋雨/相如/離居他诗混片闭域；**正文第二引两面之卷页见证面**'
     '（V018 底本是 ws 诗页、卷页从未被引——本诗系 V066–V068 之镜像）；'
     '源行系 V018 已立、本迁移复用零新建）',
     V539_BLOCK),
    ('claim-bg-016-city', 'source-ws-t300-016',
     '页面 寄令狐郎中（整页 notes 行（↑底本回指链接）+分类三行连片（简体「唐诗」与'
     '繁体「唐詩三百首」同页混排第四见）；分类行系整理者/编排动作：非史料声明、不升格；'
     '**本迁移零新建源（V066–V068 三连开新源终结）**）',
     join(WS_NOTE, WS_CAT)),
    ('claim-bg-016-world', 'source-zizhi-tongjian-events',
     '卷二百四十八·大中元年（丁卯，八四七）宣宗问元和山陵使旧事（惟山陵使長而多髯+'
     '次子綯有才器）段……大中二年（戊辰，八四八）以知制誥令狐綯為翰林學士段……'
     '卷二百四十九·大中十一年（丁丑，八五七）李远案（宰相替诗人解释『長日惟消一局棋』）'
     '+剛直為令狐綯所忌而出之（考语忌贤）+十年秉政未嘗不汗沾衣三段……卷二百零五·'
     '長壽元年（壬辰，六九二）奏疏引司馬相如終文園令段（通鉴唯一相如）……卷二百二十三·'
     '永泰元年（乙巳，七六五）郭子仪责回纥背恩德而助叛臣段（通鉴唯一背恩——旧传以'
     '同一帽扣诗人）；通鉴令狐綯恰十八处五卷/简体绹全零；汗沾衣恰二、背恩恰一'
     '（七段逐字入引为判决证据）',
     join(TJ_SB1, TJ_SB2, TJ_LY, TJ_JI, TJ_HAN, TJ_XRW, TJ_BY)),
    ('claim-bg-016-person', 'source-jiutangshu-wenyuan',
     '舊唐書卷一九〇下·李商隱（**简化字录入**照登原样，V016 locator 同款标注）'
     '（「子绹为员外郎，以商隐背恩，尤恶其无行」句（诗题官衔郎中对史传员外郎+背恩无行'
     '四字）+「茂元爱其才，以子妻之」句（背恩之实）——皆全库查重恰零域首引；传区间'
     '归属机器断言；「以商隐背恩，尤恶其无行」系史臣笔底绹意非自家供状；「一封短信'
     '抵不上一次婚姻」系读法声明；段内相如/茂陵/秋雨/双鲤/一纸/旧宾/梁园全零；'
     'V016/V066/V067/V068 在册句零重开）',
     join(JTS_P1, JTS_P2)),
]
BG_LINES = {'bg-016-scene': (1,), 'bg-016-city': (2,),
            'bg-016-world': (3,), 'bg-016-person': (4,)}
BG_AUDIENCE = {'bg-016-scene': 'PRIMARY', 'bg-016-city': 'JUNIOR',
               'bg-016-world': 'SENIOR', 'bg-016-person': 'JUNIOR'}
BG_TITLES = {'bg-016-scene': '眼前：一纸书寄往嵩云秦树',
             'bg-016-city': '这座城：底本回指的一行注',
             'bg-016-world': '这个天下：十年宰相汗沾衣',
             'bg-016-person': '这个人：背恩无行那一行'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 50 首·四句七绝 1/1/1/1 第六次）；史实句均有逐字引证；'
                 '系年第四十四次判决（题证系列第卅二状·寄令狐郎中与汗沾衣）'
                 '「诗一纸书寄往的人，通鉴里做了十年宰相；史部给他的考语是忌，'
                 '他自己在皇帝面前汗湿了衣裳」——同字两界第十四形态·寄答形态首见：'
                 '通鉴以繁体「令狐綯」恰十八处五卷写成宰相（通鉴简体令狐绹全零——'
                 '**同一人跨库字体分工：通鉴繁体綯/旧传简体绹**）；诗面茂陵/梁園/秋雨/'
                 '一紙書/舊賓客/病相如/雙鯉/嵩雲/秦樹通鉴全零；大中元年丁卯八四七'
                 '宣宗问元和山陵使旧事「惟山陵使長而多髯攀靈駕不去…次子綯前湖州刺史'
                 '有才器」+大中二年戊辰八四八「以知制誥令狐綯為翰林學士」（**收件人'
                 '第一次进通鉴以孝子之子身份**）；大中十一年丁丑八五七三连入引=李远案'
                 '「令狐綯擬李遠杭州刺史…『長日惟消一局棋』安能理人…詩人托此為高興耳」'
                 '（**宰相替诗人解释那句诗是写着玩，通鉴记他反着办提拔诗人**）+「剛直'
                 '為令狐綯所忌而出之」（**史部考语忌贤**）+「吾十年秉政…未嘗不汗沾衣也」'
                 '（**十年宰相的病是汗，诗人自比的病是雨**）；通鉴司馬相如恰一'
                 '（長壽元年壬辰六九二奏疏「昔漢武帝見司馬相如賦恨不同時終文園令」——'
                 '唯一相如=不堪公卿教材，**诗自比病相如，史部说相如本做不了大官**）；'
                 '通鉴背恩恰一（永泰元年乙巳七六五郭子仪责回纥「背恩德而助叛臣」——'
                 '**同一帽史部扣外族、传部扣诗人**）；汗沾衣恰二/長日惟消一局棋恰一在册；'
                 '本篇锚「==[[寄令狐郎中]]==」全唐诗唯一（字面恰一无同名，两端裸名'
                 '消歧链裸侧第四见 V061/V062/V063）；卷内一紙書/舊賓客/病相如/茂陵秋雨'
                 '各恰一（诗面自足）；**零新建 source（V066–V068 三连开新源终结回零'
                 '新源侧）——本诗是 V066–V068 的镜像：V018 底本是 ws 诗页（ws-raw）、'
                 '卷页从未被引，两个见证面先入哪个另一个就欠着；补引 source-quantangshi'
                 '-539 第四次复用**；正文第二引上限用满第十七例（V018 诗页在先+本迁移'
                 '卷页，两面不重叠，SCENE 不复引正文断言）；ws 页 {{Textquality|100%}}'
                 '满级页首见（75%/无评级/100% 评级谱三态齐备）+**notes 内嵌 ↑ 底本回指'
                 '链接首见（选本页自指底本卷页，两见证面页内自我声明）**+poem 全无句读'
                 '第三见（**100% 评级×无句读正交**）+{{另}}/{{別}}/{{*}}/<ref> 全零+'
                 '分类三行简繁混排第四见；PERSON 旧传简化段首引二句（子绹为员外郎以'
                 '商隐背恩尤恶其无行+茂元爱其才以子妻之——诗题官衔郎中对史传员外郎，'
                 '一纸书要泯的正是背恩无行四字；**一封短信抵不上一次婚姻**读法声明；'
                 '背恩无行系史臣笔底绹意照登 LIKELY）；段内相如/茂陵/秋雨/双鲤/一纸/'
                 '旧宾/梁园全零；V016/V066/V067/V068 在册句零重开（域断言）；KNOWN 零'
                 '如实记录（第廿五例，audit 反向断言）；判例关键语零入引文。' for k in BG}


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
    A("""-- V069：李商隱《寄令狐郎中》(work-t300-016) 四层背景（阶段 D 第 50 首·寄与不省）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V048、V057、V058、V059、V060、V061、
--       V062、V063、V064、V065、V066、V067、V068 已执行
--       （work-t300-016 与其 text-work-t300-016-ws 与其源 source-ws-t300-016 都是 V018 的行
--       （V018 以 **ws《唐詩三百首》选本页** 立本诗正文，version_code=ws-raw——
--       与 V066/V067/V068 相反：那三首底本是卷页、欠诗页；本诗底本是诗页、欠卷页）；
--       source-quantangshi-539 是 V018 已立的卷539 卷页源（V018/V067/V068 已引，
--       本迁移复用补上卷页见证面，零新建）；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       source-jiutangshu-wenyuan 是 V016 已立的旧唐书文苑传源（李商隐传在此，简化字录入）；
--       判例在册句（义山/开成二年/岭表/三十六体 V016、绹不之省/坎壈终身 V066、
--       乘興南遊/孫處約諫書/以所业文干之/下笔不能自休 V067、置瑤池都督府/恃才诡激
--       为当涂者所薄 V068）只对照不重开）。
--       **本迁移零新建 source——连续三首开新源（V066/V067/V068）到此终结；
--       audit 断言本文件零 poetry_source INSERT、回滚零 source 删除。**
--
-- 数据源（可复现）：emit_v069.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/寄令狐郎中.txt（100% 满级页+↑底本回指链接+零标记+poem 无句读+双转录+分类三行）、
--   全唐詩卷539（锚 ==[[寄令狐郎中]]== 全唐诗唯一+字面恰一+卷内四语各恰一自足+
--   秋雨/相如/離居他诗混片闭域；全唐诗 寄令狐郎中字面恰一/茂陵恰18/相如恰29 档扫闭域）、
--   舊唐書卷190下（李商隐段首引二句+段内相如/茂陵/秋雨/双鲤/一纸/旧宾/梁园全零+段边界断言）、
--   通鑑卷205/223/248/249（七段逐字入引+七处年标题窗口断言）+
--   通鑑 75 卷负证计数扫描（茂陵/梁園/秋雨/一紙書/舊賓客/病相如/雙鯉/嵩雲/秦樹 全零+
--   令狐綯恰十八处五卷/令狐绹简体全零/司馬相如恰一/文園恰一/背恩恰一/汗沾衣恰二/
--   長日惟消一局棋恰一 闭域）+
--   既有迁移引文域逐句查重——传区间归属、二引/零重开/首引零域前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 background_line（四句七绝 **1/1/1/1 第六次**（V056/V061/V066/V067/V068 之后）：scene→1
--   city→2 world→3 person→4，绑 text-work-t300-016-ws 的 4 行）+ 不碰 poetry_text_line。
-- 不做：**不新建任何 source**（连续三首开新源到此终结）；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「诗一纸书寄往的人，做了十年宰相；史部考他是忌，他汗湿了衣裳」）：
--   * 通鉴令狐綯恰十八（跨库字体分工声明：通鉴繁体綯/旧传简体绹）+ 七处年标题窗口入引；
--   * 「寄答两界」系通鉴七段逐字入引支撑的对照判决，非史实因果——通鉴不记这次寄答本身；
--   * 「一封短信抵不上一次婚姻」「一纸书要泯背恩无行」标明读法声明；
--     「以商隐背恩，尤恶其无行」标明史臣笔底绹意（非自家供状）；
--   * 通鉴背恩恰一（回纥外交辞令）与旧传背恩扣诗人——词面相同，所指两截，绝不当同一事件；
--   * 正文第二引上限用满：V018 诗页一引在先，本迁移引卷页——两引两面不重叠，
--     SCENE 不复引正文（生成时断言首末句不入 SCENE 引文），此后此诗正文关闭；
--   * 「评级谱三态」「底本回指首见」「100%×无句读正交」均照登不判；
--   * 通鉴汗沾衣恰二（另一处林甫/禄山在册）、司馬相如恰六（司馬相如字面恰一，
--     「相如」二字恰六含他人事）、長日惟消一局棋恰一在册零入引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第廿五例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * V016/V066/V067/V068 已引诸句只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 68，不含 69
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-016-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-016','source-quantangshi-539');
--    -- 两行（均 V018 所立，本迁移不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-016-ws';  -- 恰 4
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-016-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-016';                                  -- 4（1/1/1/1）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-016-%';  -- 四行全 LIKELY
--   SELECT COUNT(*) FROM poetry_source WHERE id LIKE 'source-%t300-016' -- 恰 1（V018 所立）
--     AND id='source-ws-t300-016';
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-016'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-016';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-016-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V069_rollback.sql（按 id 全枚举删除；**零 source 删除**——
--   source-ws-t300-016 与 source-quantangshi-539 皆 V018 所立，绝不删）
START TRANSACTION;""")

    A('\n-- ---------- 0. 零新建 source（V066–V068 三连开新源终结；两源皆 V018 所立复用） ----------')

    A('\n-- ---------- 1. BACKGROUND content identities ----------')
    rows = [{'id': k, 'entity_type': 'BACKGROUND', 'slug': k[3:], 'title': BG_TITLES[k],
             'summary': BG_SUMMARY[k], 'time_precision': 'UNKNOWN'} for k in BG]
    A(guard('poetry_content', ['id', 'entity_type', 'slug', 'title', 'summary', 'time_precision'],
            rows, 'x.id = t.id'))

    A('\n-- ---------- 2. claims ----------')
    crows = [{'id': k, 'subject_id': k.replace('claim-', '', 1), 'property_key': 'context',
              'value_text': v[2], 'claim_kind': v[0], 'certainty': v[1]} for k, v in CLAIMS.items()]
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            crows, 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': k.replace('claim-', '', 1), 'property_key': 'context', 'claim_id': k}
             for k in CLAIMS],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))

    A('\n-- ---------- 3. background rows ----------')
    brows = [{'id': k, 'work_id': 'work-t300-016',
              'layer': {'bg-016-scene': 'SCENE', 'bg-016-city': 'CITY',
                        'bg-016-world': 'WORLD', 'bg-016-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（四句七绝 1/1/1/1 第六次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-016-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 69, 'Li Shang-yin''s Letter to Secretary Linghu (work-t300-016) background layers (stage-D poem 50, four-line jueju 1/1/1/1 sixth time): dating verdict forty-four, thirty-second shape of the title-evidence series -- the letter sent and the letter not read; the man the poem mails a single page to ends up running the government for ten years as grand councillor; the histories'' verdict on him is "jealous", and he himself sweats through his robe in the emperor''s presence; a sending-and-answering split across realms, fourteenth shape of same-character-two-realms. The histories carry him in the traditional form of his name, Linghu Tao, exactly eighteen times across five juan (machine-asserted); the simplified spelling used by the Old Book of Tang scores zero in the Tongjian -- one man, two scripts, a cross-repository font division. All the poem''s own words (mao-ling, liang-yuan, autumn rain, a single sheet of paper, old guest, sick Sima Xiangru, twin carp, Song clouds, Qin trees) score zero in the Tongjian. Dazhong 1st, dingmao, 847: Emperor Xuan recalls the Yuanhe-era funeral-bearer''s-escort "only the escort commissioner, tall with a long beard, clung to the spirit carriage and would not leave" and asks "has he a son?" -- answer: "his second son Tao, formerly Prefect of Huzhou, has talent and capacity"; Dazhong 2nd, wuchen, 848: "appoint the edict-drafter Linghu Tao as Hanlin academician" -- the poem''s addressee first enters the histories as a filial son''s son. Dazhong 11th, dingchou, 857, three-in-one window: the Li Yuan case -- "Linghu Tao nominated Li Yuan as Prefect of Hangzhou; the emperor said: I have heard Yuan''s verse -- 『a whole long day consumed by a single game of go』 -- how can such a one govern people! Tao said: a poet just leans on such lines for high spirits, not necessarily true" (the grand councillor explains to the emperor on a poet''s behalf that the line was only play; the poem mails the郎中 seeking exactly a posting, and the histories record him doing the reverse); "yet in the end, being upright and forthright, he was out of jealousy pushed out by Tao" (the histories'' rating of Tao: jealous of the able); and "I held the government ten years, most favored of all; yet each time I reported at the Yan-ying hall I never failed to sweat through my robe" -- the ten-year chancellor''s sickness is sweat, the poet''s self-compared sickness is rain. Sima Xiangru proper appears exactly once in the Tongjian (Changshou 1st, renchen, 692, a memorial: "of old Emperor Wu of Han read Sima Xiangru''s rhapsody and grieved he had not lived at the same time; once he set him in court he ended as Prefect of the Textual Garden") -- the one and only Sima Xiangru in the histories is a case-study that empty literature cannot bear noble office; the poem likens itself to the sick Sima Xiangru, and the histories say Xiangru was never fit for great office anyway. "Betraying favor" (bei-en) appears exactly once in the Tongjian (Yongtai 1st, yisi, 765, Guo Ziyi rebuking the Uyghurs: "betraying favor to aid a rebel minister") while the Old Book uses the same cap on Li Shang-yin (simplified) -- same word, one cap for a foreign power in the histories, another for a poet in the biographies. Two use-ceiling on the body reached, seventeenth instance: V018 already quoted the ws anthology page (ws-raw), this migration quotes the Quan Tangshi juan-539 scroll page instead -- two quotations, two witness faces, never overlapping; SCENE deliberately does not re-quote the body (generator asserts the first and last lines are absent from the SCENE excerpt); the poem''s body is now closed to later migrations. ZERO new sources -- the three-in-a-row new-source run of V066/V067/V068 ends here; this poem is their mirror image: V018''s base was the ws anthology page, the scroll page was never cited, so whichever of the two faces enters first leaves the other owed; source-quantangshi-539 reused for the fourth time (audit asserts zero poetry_source INSERT and zero source deletion in rollback). The ws page: {{Textquality|100%}} full-grade page first seen (the 75% side of V055/V057/V061/V062, the ungraded side of V066/V067/V068, and the 100% side of this poem -- the grading spectrum''s three states now complete); notes embeds an "up-arrow" back-reference link to the base scroll page, first seen (the anthology page points back to the base page inside itself -- the two witness faces self-declared within one page); a punctuation-free poem block, third time, coexisting with a 100% grade (grade measures transcription completeness, orthogonal to punctuation); zero variant markers; title bare; category triple in mixed scripts, fourth time. PERSON first-cites two zero-domain sentences from the simplified JTS biography -- "his son Tao, as Vice Director, holding Shang-yin to have betrayed favor, particularly loathed his lack of conduct" (the poem-title rank "Langzhong" matches the biography rank "Vice Director / Lang": what a single sheet tries to wipe out is exactly the words "betrayed favor" and "lack of conduct" on this very line) and "Mao-yuan loved his talent and gave him his daughter in marriage" (the substance of the alleged betrayal) -- one short letter is worth less than one marriage (reading declared, not fact); the judgment phrase is the historian''s rendering of Tao''s feeling (logged, LIKELY); the biography segment holds no Xiangru/maoling/autumn-rain/twin-carp/single-sheet/old-guest/liangyuan character (machine-asserted); V016/V066/V067/V068 quoted sentences stay closed (domains asserted); KNOWN zero honestly recorded (twenty-fifth instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 69);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V069 精确回滚：只删 V069 插入的行（id 全枚举）。',
         '-- **零 source 删除**：source-ws-t300-016（V018 所立的 ws 选本页源）与',
         '-- source-quantangshi-539（V018 所立的卷539 卷页源）本迁移皆复用，绝不删；',
         '-- work-t300-016 本体、其 text_line 4 行都是 V018 的行，绝不删；',
         '-- source-zizhi-tongjian-events / source-jiutangshu-wenyuan 为他迁移所立，零删除。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 69;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, V539_BLOCK,
              TJ_SB1, TJ_SB2, TJ_LY, TJ_JI, TJ_HAN, TJ_XRW, TJ_BY, JTS_P1, JTS_P2]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # SCENE：底本回指链接必须逐字入引 + 正文不得入 SCENE 引文
    scene_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-016-scene')
    if '↑ [[全唐詩/卷539#寄令狐郎中|全唐詩·卷五百三十九]]' not in scene_ws:
        bad.append('底本回指链接未逐字入 SCENE 引文（↑底本回指首见照登硬卡）')
    if '{{Textquality|100%}}' not in scene_ws:
        bad.append('满级评级未逐字入 SCENE 引文（评级谱三态齐备照登硬卡）')
    for _b in ('嵩雲秦樹久離居', '茂陵秋雨病相如'):
        if _b in scene_ws:
            bad.append(f'SCENE 复引正文「{_b}」——本迁移 SCENE 不复引正文（第二引让给卷页）')
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-016-city' and s == 'source-ws-t300-016')
    if '[[Category:唐诗]]' not in city_ws or '[[Category:唐詩三百首|李]]' not in city_ws:
        bad.append('分类简繁混排未逐字入 CITY 引文（第四见照登硬卡）')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-016-city' and s == 'source-ws-t300-016'):
        bad.append('CITY ws locator 须含「不升格」声明（分类行三重断言失效）')
    if '==[[寄令狐郎中]]==' not in next(ex for c, s, _, ex in CITATIONS if s == 'source-quantangshi-539'):
        bad.append('卷539 锚未逐字入 CITY 引文（全唐诗唯一锚标本照登硬卡）')
    c_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-016-city' and s == 'source-quantangshi-539')
    if '第二引' not in c_loc or '两面' not in c_loc:
        bad.append('CITY 卷页 locator 须含「第二引/两面」声明（上限用满硬卡）')
    # WORLD：七段史文必须在引文内；诗语零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-016-world')
    for tok in ('惟山陵使長而多髯', '次子綯，前湖州刺史', '以知制誥令狐綯為翰林學士',
                '令狐綯擬李遠杭州刺史', '未嘗不汗沾衣也', '終文園令', '背恩德而助叛臣'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（七段必须入引）')
    for tok in ('茂陵秋雨', '一紙書', '舊賓客', '雙鯉', '嵩雲', '秦樹'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文）')
    w_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-016-world')
    if '令狐綯' not in w_loc:
        bad.append('WORLD locator 须点出繁体令狐綯（跨库字体分工声明）')
    # PERSON 首引句必须在引文内 + 在册句零重开
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-016-person')
    for tok in ('尤恶其无行', '以子妻之'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺首引要素「{tok}」（简化字段首引照登硬卡）')
    for tok in ('绹不之省', '坎壈终身', '以所业文干之', '下笔不能自休', '为当涂者所薄',
                '恃才诡激', '置瑤池都督府', '明年，令狐绹作相'):
        if tok in cited:
            bad.append(f'V066/V067/V068 已引「{tok}」零重开——不得入本迁移引文')
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒',
                '仕宦之疾徑', '茶鐺', '解官以贖', '柴毁骨立', '毀幾不生',
                '車如流水馬如龍', '歴右拾遺', '天寳末，為給事中', '或牒歸故鄉',
                '昆仲宦遊兩都', '輞口', '藍田别墅', '下馬飲君酒', '歸臥南山陲',
                '閉關以拒之', '殺郡王', '雲南王孫', '春草未生', '今宵歸不歸',
                '山中相送罷', '日暮掩柴扉', '一作山中送別', '聚斂為長策',
                '脫巾解帶', '解帶繫頸', '議者不之罪', '晚年唯好靜', '漁歌入浦深',
                '貶晙為梓州刺史', '段子璋反', '參天可汗道', '火炬於樹杪',
                '九歲知屬辭', '別墅在輞川', '華子岡', '版圖墮於避地', '避地江左',
                '龍陽江漲', '仙源公主', '碧玉赴井死', '狂夫之言', '狂夫竊發',
                '不傷良人', '綠珠怨', '贈秘書監。', '停筆而化',
                '可為痛哭者一', '厝火積薪', '可憐彼翁', '虛前席', '不問蒼生問鬼神',
                '賈生年少虛垂涕', '宣室求賢訪逐臣',
                '乘興南遊不戒嚴', '半作障泥半作帆', '紫泉宮殿鎖煙霞', '一云隋堤',
                '襲亡隋之弊', '亡隋之弊俗', '孫處約諫書', '煬帝將幸江都',
                '何處更求長生', '穆王何事不重來', '雲能合長生藥', '一雲隋堤',
                '李商隐，字义山，怀州河内人。', '开成二年，方登进士第',
                '商隐随亚在岭表累载', '与太原温庭筠、南郡段成式齐名',
                '府罷，客滎陽，卒'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    if BG_LINES != {'bg-016-scene': (1,), 'bg-016-city': (2,),
                    'bg-016-world': (3,), 'bg-016-person': (4,)}:
        bad.append('四句 background_line 须 1/1/1/1（第六次）')
    if len(re.findall(r"text-work-t300-016-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    # **零新建 source**（V066–V068 三连终结）
    ins_src = sql.count('INSERT INTO poetry_' + 'source')
    if ins_src != 0:
        bad.append(f'本迁移应零新建 source（audit 判例），实 {ins_src}')
    rb = build_rollback()
    if 'DELETE FROM poetry_source' in rb:
        bad.append('回滚不得含任何 source 删除（两源皆 V018 复用）')
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V069 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V069 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-016' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V069 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-016' AS subject_id" in sql:
        bad.append('V069 的 claim 主语应全部是 bg-016-*，work-t300-016 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V069 不碰 poetry_text_line')
    body_all = ''.join(BG.values())
    if '汗沾衣' not in body_all:
        bad.append('BG/WORLD 须含「未嘗不汗沾衣也」史部正面回答声明')
    if '寄答形态首见' not in body_all:
        bad.append('BG 须含「寄答形态首见」（同字两界第十四形态）声明')
    if '跨库字体分工' not in body_all:
        bad.append('BG 须含「跨库字体分工（通鉴繁体綯/旧传简体绹）」声明')
    if '底本回指' not in body_all:
        bad.append('BG/SCENE 须含「↑底本回指链接首见」声明')
    if '评级谱三态' not in body_all and '三态齐备' not in body_all:
        bad.append('BG 须含「评级谱三态齐备」声明')
    if '正交' not in body_all:
        bad.append('BG/SCENE 须含「100% 评级×无句读正交」声明')
    if '镜像' not in body_all:
        bad.append('BG/CITY 须含「本诗是 V066–V068 的镜像」诚实开例声明')
    if '零新建' not in body_all:
        bad.append('BG/CITY 须含「零新建 source（三连终结）」声明')
    if '抵不上一次婚姻' not in body_all:
        bad.append('BG/PERSON 须含「一封短信抵不上一次婚姻」读法声明')
    if '读法声明' not in body_all:
        bad.append('BG 须含「读法声明」')
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
        if m.group(1) == 'poetry_schema_version':
            continue
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
    vblk = sql[sql.index('INSERT INTO poetry_schema_version'):]
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 69)' not in vblk:
        bad.append('poetry_schema_version INSERT 缺显式幂等守卫')
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
              f'切片传区间归属断言（旧传李商隐段二首引句，段界 ==弟 羲叟==）；'
              f'七处年标题窗口断言（大中元年八四七/大中二年八四八/大中十一年八五七×3/'
              f'長壽元年六九二/永泰元年七六五）；'
              f'负证机器复查五层（通鉴茂陵/梁園/秋雨/一紙書/舊賓客/病相如/雙鯉/嵩雲/秦樹全零+'
              f'令狐綯恰十八处五卷+令狐绹简体全零+司馬相如恰一+文園恰一+背恩恰一+汗沾衣恰二+'
              f'長日惟消一局棋恰一/全唐诗锚恰一+字面恰一+卷539 四语各恰一自足+秋雨相如離居混片/'
              f'ws 满级评级恰一+底本回指恰一+零标记+poem 无句读+首末句页内各恰二+分类三行连片/'
              f'旧传段相如茂陵秋雨双鲤一纸旧宾梁园全零，快照变动即中止）；'
              f'前提全库查重硬卡六件+九首引句零域断言；底本回指/满级/锚唯一照登硬卡；'
              f'SCENE 不复引正文断言（首末句不入 SCENE 引文）；CITY 第二引/两面硬卡；'
              f'CITY「不升格」硬卡；七段通鉴史文入引+诗语零混入断言；'
              f'PERSON 二首引句入引硬卡+V066/V067/V068 诸句零重开硬卡；'
              f'判例只引不重开断言（含 V016/V064/V065/V066/V067/V068 诸在册语）；'
              f'四句 1/1/1/1 形制断言；零 KNOWN 反向断言；'
              f'**零新建 source 断言（INSERT 恰零+回滚零 source 删除）**——'
              f'连续三首开新源终结，本诗系 V066–V068 之镜像；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
