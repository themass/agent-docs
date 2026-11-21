#!/usr/bin/env python3
"""阶段 D 第 54 首：生成 V073——李商隱《風雨》(work-t300-015, V018 已立) 四层背景。

**本迁移零新建 source——连续第五首**（V069/V070/V071/V072 之后；
source-ws-t300-015 与 source-quantangshi-539 皆 V018 所立，539 第八次复用）。

绑定形态：互指循环指针**第三次在场**（V071 首见、V072 第二次，本篇成连续系列）——
ws notes 带「↑ [[全唐詩/卷539#風雨|…]]」向上回指，539 本篇正文恰是「{{:風雨 (李商隱)}}」
向下转引；壳侧作者消歧器第二次在场（V072 首见），且本篇**新形态：整理者作者注直接挂锚**
「==[[杜司勳]]{{*|牧}}==」——同页相邻的杜牧诗题带 {{*|牧}} 注（壳侧注记首见）。
**卷页并置机器断言**：哭劉蕡块与杜司勳块在 539 里直接相接（「不敢同君哭寢門\n</poem>
\n\n==[[杜司勳]]{{*|牧}}==」恰一）——李商隱哭刘蕡的诗与杜牧「高樓風雨感斯文」隔一个
换行并排：选本自己把「风雨」两案放在同一页上下。

「为什么写」走到**风雨两界**（同字两界第十八形态·风雨形态首见）：
**通鉴七十五卷有风有雨，且恰九处**（202/204/210/211/248/250/254/257/261 闭域）——
四段逐字入引：裴行儉黑山 before 移营高岡「是夜，風雨暴至，前所營地，水深丈餘」（自然事件+
先见）；盧懷慎「所居不蔽風雨」（清谨俭素的卿相，风雨落在他家屋顶上）；吕用之「每對駢
呵叱風雨」（高骈案里风雨是方士骗人的道具）；**大中元年宣宗对白敏中自忆宪宗之丧
「道遇風雨，百官、六宮四散避去」——风雨里攀灵驾不去的那个人叫令狐楚**：把诗作者
终身挡在门外的令狐绹，他家的大门第正是在一场风雨里定下的（V069 在册句「惟山陵使長而多髯」
只对照不重开，本迁移引的是风雨本身）——**史部的风雨各有落主：落进军令、落在屋顶、
落成骗术、落在忠勤赏价上；诗的「黃葉仍風雨」不落在任何人的账上**。
旧字面同样在册而两界：「舊好」恰六（213/222/232/250/253/264 闭域）**全部是国与国、
镇与镇之间复盟修好，无一字落在朋友身上**；诗的「舊好隔良緣」隔的是令狐绹。
新豐恰九而**新豐酒零**；馬周一十五处全在官迹、传段无一杯酒；寶劍两处（李愬赠剑/
吕用之伪剑）无一是剑篇事——诗借的典故，史部只借出地名和人名。

ws 页形制（SCENE/CITY 层）：**五成页首见**（{{Textquality|50%}}——已落九首李商隱诗页
无此级；300 语料 TQ 谱 50:92/75:142/100:26 闭域档扫）；**零标记页×五成**（另/别/*/ref/
reflist 全零——满级零标记谱（V069/V072）向低级的延伸：评级与标记多寡正交的第三枚标本）；
notes 排序谱补全：本页「五成→三百首→↑」其中**「{{唐詩三百首}}↑」相邻形全库恰一页**
（机器断言）；分类三行含作者分类（三形态 2/3/4 行至此全齐——V071 两行/V072 四行/本篇三行）；
Vtext 署名行「{{Vtext|李商隱}}」恰十六页（李商隱页群档扫）；双转录句读分工第二次在场
（Vtext 裸行/poem 句读——V072 首见成系列）；**跨迁移零分歧面**：V018 文本行八句与本快照
poem 块逐字同面（ws-raw 对 ws-raw——V072 异体分工的反面，生成时八行双向断言）。

8 句五律 shape：**2/2/2/2 顺次**（scene→1,2 city→3,4 world→5,6 person→7,8）。

用法: python3 -I emit_v073.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402

WS = pathlib.Path('/tmp/src-dl/ws-poems/風雨__李商隱_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
V539 = pathlib.Path('/tmp/src-dl/quantangshi/vol539.txt').read_text(encoding='utf-8')
V018 = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/V018__tang300_ws_verified.sql').read_text(encoding='utf-8')
TJ202 = pathlib.Path('/tmp/src-dl/tongjian/tj-202.txt').read_text(encoding='utf-8')
TJ211 = pathlib.Path('/tmp/src-dl/tongjian/tj-211.txt').read_text(encoding='utf-8')
TJ248 = pathlib.Path('/tmp/src-dl/tongjian/tj-248.txt').read_text(encoding='utf-8')
TJ254 = pathlib.Path('/tmp/src-dl/tongjian/tj-254.txt').read_text(encoding='utf-8')
TJ193 = pathlib.Path('/tmp/src-dl/tongjian/tj-193.txt').read_text(encoding='utf-8')
TJ213 = pathlib.Path('/tmp/src-dl/tongjian/tj-213.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 風雨', '| title    = 風雨',
                         'ws header title(裸名题面——风雨二字通鉴各有九处落主)')
WS_AUTHOR = slice_between(WS, '| author   = 李商隱', '| author   = 李商隱',
                          'ws header author(署名直证)')
WS_VSIG = slice_between(WS, '{{Vtext|}}\n{{Vtext|李商隱}}\n{{Vtext|}}',
                        '{{Vtext|}}\n{{Vtext|李商隱}}\n{{Vtext|}}',
                        'ws Vtext 署名行(李商隱页群恰十六页闭域——Vtext 裸面署名)')
WS_POEM = slice_between(WS, '淒涼寶劍篇，羈泊欲窮年。', '銷愁斗幾千。\n</poem>',
                        'ws poem 块八句存原样(正文第二引——与 V018 同面零分歧，跨迁移八行双向断言)')
WS_VT1 = slice_between(WS, '{{VtextStart}}淒涼寶劍篇{{VtextEnd}}', '銷愁斗幾千{{VtextEnd}}',
                       'ws Vtext 八行全裸无句读整片(双转录句读分工第二次——V072 首见成系列)')
WS_NOTE3 = slice_between(
    WS,
    '| notes    = {{Textquality|50%}}{{唐詩三百首}}↑ [[全唐詩/卷539#風雨|全唐詩·卷五百三十九]]',
    '| notes    = {{Textquality|50%}}{{唐詩三百首}}↑ [[全唐詩/卷539#風雨|全唐詩·卷五百三十九]]',
    'ws notes 三连一行(五成居首——排序谱第三态；↑回指互指之诗页侧)')
WS_CAT3 = slice_between(WS, '[[Category:李商隱]]\n[[Category:唐诗]]\n[[Category:唐詩三百首|李]]',
                        '[[Category:李商隱]]\n[[Category:唐诗]]\n[[Category:唐詩三百首|李]]',
                        'ws 分类三行连片(三形态 2/3/4 行至此全齐——对照 V071 两行/V072 四行)')
V539_SHELL = slice_between(V539, '==[[風雨 (李商隱)|風雨]]==\n{{:風雨 (李商隱)}}',
                           '==[[風雨 (李商隱)|風雨]]==\n{{:風雨 (李商隱)}}',
                           '卷539 消歧壳(壳侧作者消歧器第二次在场——V072 首见成系列)')
V539_DM = slice_between(V539, '==[[杜司勳]]{{*|牧}}==\n<poem>\n高樓風雨感斯文　短翼差池不及群\n刻意傷春復傷別　人間惟有杜司勳',
                        '人間惟有杜司勳\n</poem>',
                        '卷539 杜牧《杜司勳》块(高樓風雨感斯文——同页他诗带雨恰一+整理者作者注挂锚)')
TJ_FY1 = slice_between(TJ202, '軍至單于府北，抵暮，下營', '不必問其所由知也。',
                       '通鉴永隆元年裴行俭移营高岡避风雨(风雨落进军令;窗口断言)')
TJ_FY2 = slice_between(TJ211, '懷慎清謹儉素', '所居不蔽風雨。',
                       '通鉴开元三年卢怀慎所居不蔽风雨(风雨落在清谨卿相屋顶;窗口断言)')
TJ_FY3A = slice_between(TJ248, '上請白敏中曰', '四散避去',
                        '通鉴大中元年宣宗忆宪宗之丧道遇风雨避去(风雨落在忠勤赏价上;窗口断言)')
TJ_FY3B = slice_between(TJ248, '攀靈駕不去', '對曰：「令狐楚。」',
                        '通鉴大中元年攀灵驾独对令狐楚(跳过 V069 在册句只引不重开)')
TJ_FY4 = slice_between(TJ254, '用之每對駢呵叱風雨', '雲有神仙過雲表。',
                       '通鉴中和二年吕用之呵叱风雨(风雨成方士骗术道具;窗口断言)')
TJ_JH = slice_between(TJ213, '倘使復修舊好', '死無所恨！」',
                      '通鉴开元十八年吐蕃乞复旧好(旧好恰六之最近诗面者——全在邦交;窗口断言)')
JTS_P = slice_between(JTS, '府罢入朝，复以文章干襜', '乃补太学博士。',
                      '旧传李商隐段(复以文章干襜——干字二见谱；PERSON 首引零域)')

# ---------- 传区间归属复验（段界 ==弟 羲叟==） ----------
_ja = JTS.find('=李商隱=')
_jm = re.search(r'\n==[^=\n]{1,12}==', JTS[_ja + 8:])
_seg_j = JTS[_ja:_ja + 8 + _jm.start()]
for _needle in (JTS_P,):
    if _needle not in _seg_j:
        raise SystemExit('PERSON 首引句越出旧传李商隐段——修订后重生成')

# ---------- 通鉴年标题窗口断言 ----------
_HEAD = re.compile(r'[^\n]*(?:（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][，、]公元[〇零一二三四五六七八九十百千]+年）'
                   r'|\{\{\*\|[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，西元[〇零一二三四五六七八九十百千]+年\}\})')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 90]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ202, TJ_FY1, '永隆元年')
_window(TJ211, TJ_FY2, '開元三年')
_window(TJ248, TJ_FY3A, '大中元年')
_window(TJ254, TJ_FY4, '中和二年')

_window(TJ213, TJ_JH, '開元十八年')

# ---------- 负证机器复查 ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：风雨恰九（各有落主）、旧好恰六（全在邦交）、新豐恰九而新豐酒零、宝剑恰二无一剑篇
if _alltj.count('風雨') != 9:
    raise SystemExit(f'通鉴「風雨」不再恰九（实 {_alltj.count("風雨")}）——风雨两界判决须重估')
_fy = {n: t.count('風雨') for n, t in _tjf.items() if '風雨' in t}
if sorted(int(n[3:6]) for n in _fy) != [202, 204, 210, 211, 248, 250, 254, 257, 261]:
    raise SystemExit(f'通鉴「風雨」闭域分布变了（实 {sorted(_fy)}）——九处落主档扫须重估')
if _alltj.count('舊好') != 6 or _alltj.count('修舊好') != 6:
    raise SystemExit('通鉴「舊好/修舊好」不再恰六——旧好两界（全在邦交）判决须重估')
for _w, _n in (('新豐', 9), ('新豐酒', 0), ('寶劍', 2), ('郭震', 1), ('青樓', 0), ('管絃', 0),
               ('黃葉', 0), ('羈泊', 0), ('銷愁', 0), ('淒涼', 0), ('窮年', 0), ('斗幾千', 0),
               ('薄俗', 0), ('新知', 0), ('淒涼寶劍篇', 0), ('高難飽', 0)):
    if _alltj.count(_w) != _n:
        raise SystemExit(f'通鉴「{_w}」不再恰{_n}——诗面语侧闭域档扫须重估')
if _alltj.count('馬周') != 15:
    raise SystemExit('通鉴「馬周」不再恰十五——马周无酒杯档扫须重估')
# ② 全唐诗：壳锚/转引全库唯一；八句全库零；杜司勳诗恰一；539 壳侧并置断言
if _allq.count('==[[風雨 (李商隱)|風雨]]==') != 1 or _allq.count('{{:風雨 (李商隱)}}') != 1:
    raise SystemExit('《全唐詩》風雨壳锚/转引不再全库唯一——壳侧消歧系列断言失效')
if _allq.count('高樓風雨感斯文') != 1 or _allq.count('短翼差池不及群') != 1:
    raise SystemExit('《全唐詩》杜牧「高樓風雨感斯文」不再恰一——同页他诗带雨档扫须重估')
for _ln in ('淒涼寶劍篇', '羈泊欲窮年', '黃葉仍風雨', '青樓自管絃',
            '新知遭薄俗', '舊好隔良緣', '心斷新豐酒', '銷愁斗幾千'):
    if _allq.count(_ln) != 0:
        raise SystemExit(f'全唐詩语料「{_ln}」不再全零——诗八行只活在诗页的判决失效')
if V539.count('==[[風雨 (李商隱)|風雨]]==') != 1 or V539.count('==[[杜司勳]]{{*|牧}}==') != 1:
    raise SystemExit('卷539 风雨壳/杜司勳锚结构变了（并置断言失效）')
if V539.count('不敢同君哭寢門\n</poem>\n\n==[[杜司勳]]{{*|牧}}==') != 1:
    raise SystemExit('哭劉蕡块与杜司勳块不再直接相接——卷页并置判决须重估')
if V539.count('{{:風 (李商隱)}}') != 1 or V539.count('==[[春風 (李商隱)|春風]]==') != 1:
    raise SystemExit('卷539 风味壳/春風锚恰一变了——卷内风案闭域档扫须重估'
                       '（春風块系正文内联非转引壳——风三壳形态：带消歧转引/带消歧内联/带消歧转引本篇）')
# ③ ws：五成页首见+零标记；双转录句读分工第二次；notes 三连「三百首↑」相邻恰一页；分类三行
for _w in ('{{另', '{{別', '{{*', '<ref>', '{{reflist}}'):
    if WS.count(_w) != 0:
        raise SystemExit(f'ws 页「{_w}」不再全零（零标记×五成断言失效）')
if WS.count('{{Textquality|50%}}') != 1 or WS.count('{{Textquality|100%}}') != 0:
    raise SystemExit('ws 页五成级计数变了（已落九首李商隱页无此级——五成页首见断言失效）')
if WS.count('風雨') != 5:
    raise SystemExit('ws 页「風雨」不再恰五（题+注+回指+诗两处）——页内风案档扫须重估')
if WS.count('淒涼寶劍篇') != 2 or WS.count('銷愁斗幾千') != 2:
    raise SystemExit('ws 页 Vtext/poem 双转录结构变了（首末句页内应各恰 2）')
if '淒涼寶劍篇，' not in WS or '{{VtextStart}}淒涼寶劍篇{{VtextEnd}}' not in WS:
    raise SystemExit('ws poem 句读面或 Vtext 裸面缺失（双转录句读分工第二次断言失效）')
if WS.count('{{VtextStart}}') != 8 or WS.count('{{VH1|風雨}}') != 1 or WS.count('{{clr}}') != 1:
    raise SystemExit('ws Vtext/VH1/clr 排版结构变了')
_wsf = {p.name: p.read_text(encoding='utf-8')
        for p in sorted(pathlib.Path('/tmp/src-dl/ws-poems').glob('*.txt'))}
_adj = {n for n, t in _wsf.items() if '{{唐詩三百首}}↑' in t}
if _adj != {'風雨__李商隱_.txt'}:
    raise SystemExit(f'「{{{{唐詩三百首}}}}↑」相邻页不再恰一（实 {sorted(_adj)}）——notes 排序谱第三态断言须重估')
_up = {n for n, t in _wsf.items() if '[[全唐詩/卷539#' in t}
if _up != {'寄令狐郎中.txt', '蟬__李商隱_.txt', '錦瑟.txt', '韓碑.txt', '風雨__李商隱_.txt'}:
    raise SystemExit(f'539 回指页不再恰五（实 {sorted(_up)}）——互指系列闭域档扫须重估')
if WS.count('[[Category:李商隱]]') != 1 or WS.count('[[Category:唐诗]]') != 1:
    raise SystemExit('ws 分类三行含作者分类形态变了（三形态 2/3/4 行齐——分类行数即形态）')
if WS.count('| times') != 0 or WS.count('| type') != 0 or WS.count('| from') != 0:
    raise SystemExit('ws 无 times/type/from 字段形态变了')
# ④ 旧传李商隐段负证（段内诗面题字零+酒/饮/愁零+干恰二）
for _w in ('風', '雨', '劍', '篇', '羈', '黃', '葉', '青', '樓', '管', '絃', '新', '舊',
           '俗', '愁', '斗', '銷', '淒', '窮', '酒', '飲'):
    if _seg_j.count(_w) != 0:
        raise SystemExit(f'「{_w}」落在旧传李商隐段——传段题字零判决失效，须重读原文')
if _seg_j.count('干') != 2 or JTS.count('干') != 11:
    raise SystemExit('旧传段「干」不再恰二（干之/干襜）或全卷恰十一——干字谱须重估')
if '复以文章干襜，乃补太学博士。' not in _seg_j:
    raise SystemExit('PERSON 首引句不在段内原位')
# ⑤ 跨迁移零分歧面双向断言（V018 八行与本快照 poem 块同面——ws-raw 对 ws-raw）
for _ln in ('淒涼寶劍篇，', '羈泊欲窮年。', '黃葉仍風雨，', '青樓自管絃。',
            '新知遭薄俗，', '舊好隔良緣。', '心斷新豐酒，', '銷愁斗幾千。'):
    if f"'{_ln}'" not in V018 or _ln not in WS_POEM:
        raise SystemExit(f'V018 与本快照「{_ln}」不再同面（零分歧面断言失效——与 V072 异体分工对照）')

POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V073')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

def _domain_src(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V073')
                   and needle in f.read_text(encoding='utf-8')})

for _premise, _needle, _want in (
        ('本诗首句(V018 句读式一引)', '淒涼寶劍篇', ['V018']),
        ('本诗末句(V018 句读式收尾)', '銷愁斗幾千', ['V018']),
        ('V018 句读式全引不重开', '淒涼寶劍篇，……銷愁斗幾千。', ['V018']),
        ('风雨字面在册(V018 灞上秋居+V053 春晓先占——照登不重开)', '風雨', ['V018', 'V053']),
        ('ws 诗页源在先', 'source-ws-t300-015', ['V018']),
        ('卷页源七次在册(本迁移第八次复用)', 'source-quantangshi-539',
         ['V018', 'V067', 'V068', 'V069', 'V070', 'V071', 'V072']),
        ('V069 底本回指链接在册', '↑ [[全唐詩/卷539#寄令狐郎中', ['V069']),
        ('V071 互指锦瑟在册', '{{:錦瑟}}', ['V071']),
        ('V072 消歧壳在册', '{{:蟬 (李商隱)}}', ['V072']),
        ('V069 山陵使在册(只对照不重开)', '惟山陵使長而多髯', ['V069']),
        ('V069 次子绯在册(只对照不重开)', '次子綯有才器', ['V069']),
        ('V016 在册诸句', '商隐随亚在岭表累载', ['V016'])):
    _prev = _domain_src(_needle) if (_needle.startswith('source-')) else _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
for _first, _needle in (('消歧壳锚', '==[[風雨 (李商隱)|風雨]]=='),
                        ('消歧转引', '{{:風雨 (李商隱)}}'),
                        ('本页↑回指', '↑ [[全唐詩/卷539#風雨'),
                        ('五成注', '{{Textquality|50%}}{{唐詩三百首}}'),
                        ('Vtext署名行', '{{Vtext|}}\n{{Vtext|李商隱}}\n{{Vtext|}}'),
                        ('分类三行', '[[Category:李商隱]]\n[[Category:唐诗]]\n[[Category:唐詩三百首|李]]'),
                        ('裴行俭风雨', '是夜，風雨暴至，前所營地，水深丈餘'),
                        ('卢怀慎风雨', '所居不蔽風雨。'),
                        ('宣宗风雨', '道遇風雨，百官、六宮四散避去'),
                        ('吕用之风雨', '用之每對駢呵叱風雨'),
                        ('杜牧司勋', '高樓風雨感斯文　短翼差池不及群'),
                        ('作者注挂锚', '==[[杜司勳]]{{*|牧}}=='),
                        ('旧传干襜', '复以文章干襜'),
                        ('吐蕃乞复旧好', '倘使復修舊好'),
                        ('马周条', '茌平人馬周'),
                        ('诗原样块', '淒涼寶劍篇，羈泊欲窮年。')):
    if _domain(_needle):
        raise SystemExit(f'首引句「{_first}」既往域非零——须换句或降级')

TJ_MZ = slice_between(TJ193, '茌平人馬周', '上以常何為知人，賜絹三百匹。',
                      '通鉴贞观三年马周客常何家代陈便宜(史部马周无一字酒;窗口断言)')
_window(TJ193, TJ_MZ, '貞觀三年')
if '酒' in TJ_MZ or '新豐' in TJ_MZ:
    raise SystemExit('马周段不再无酒/无新豐——新豐酒两界判决须重估')

# ---------- 四层背景正文 ----------
BG = {
    'bg-015-scene': (
        '**诗一开口就借别人的一首诗**：「淒涼寶劍篇」——那篇宝剑歌行是郭震的（通鉴七十五卷'
        '郭震恰一、只在他劾相那页，剑篇零——机器断言），李商隱把别人的剑篇当作自己风雨夜的'
        '开场白，第二句才轮到「羈泊欲窮年」：一整年漂着。**ws 页是五成页首见**（'
        '{{Textquality|50%}}——已落九首李商隱诗页从无此级；300 语料 TQ 谱 50:92/75:142/'
        '100:26 闭域档扫）；**零标记页×五成**（{{另}}/{{別}}/{{*}}/<ref>/{{reflist}} 全零，'
        '机器断言——V069/V072 满级零标记谱向低级的延伸：**评级与标记多寡正交的第三枚标本**）。'
        '**双转录句读分工第二次在场**（Vtext 行全裸、poem 块全句读——V072 首见成系列）；'
        '**跨迁移零分歧面**：V018 文本行八句与本快照 poem 块逐字同面（ws-raw 对 ws-raw——'
        '与 V072 异体分工恰成对照组，生成时八行双向断言）。正文第二引上限用满第二十一例'
        '（V018 句读式一引在先，本迁移引 poem 块原样面——同面各从其录，V018 句读式引文'
        '零重开硬断言），此后此诗正文关闭。',
     ),
    'bg-015-city': (
        '**这座城的档案员把两案风雨钉在同一页上下**：ws notes「↑ [[全唐詩/卷539#風雨|…]]」'
        '向上回指、539 本篇正文恰是「{{:風雨 (李商隱)}}」向下转引——**互指循环指针第三次在场**'
        '（V071 首见、V072 第二次，本篇成连续系列；539 回指页闭域恰五：寄令狐郎中/蟬/錦瑟/'
        '韓碑/風雨，机器断言）；壳侧作者消歧器第二次在场（「==[[風雨 (李商隱)|風雨]]==」+转引'
        '各全唐诗恰一——消歧器上壳是 V072 首见的常规化）。**新形态：整理者作者注直接挂锚**——'
        '同卷杜牧诗题作「==[[杜司勳]]{{*|牧}}==」（{{*|牧}} 作者注挂题锚，壳侧注记首见，'
        '机器断言恰一），其诗首句恰是「高樓風雨感斯文」；**卷页并置机器断言**：李商隱《哭劉蕡》'
        '块与杜牧《杜司勳》块在 539 里直接相接（「不敢同君哭寢門」句尾与「==[[杜司勳]]'
        '{{*|牧}}==」锚之间只隔块界空行，机器断言恰一）——**选本自己把李商隱哭刘蕡和杜牧'
        '读他的高楼风雨放在同一个换行上下**。'
        '本页八句在《全唐詩》语料全零——诗只活在诗页；同卷青樓/管絃/寶劍/新豐全零（闭域）。'
        'ws notes 排序谱补全第三态：**「{{唐詩三百首}}↑」相邻形全库恰一页**（机器断言——'
        'V071 三连序/V072 三百首居首/本篇五成居首）；分类三行含作者分类（分类形态 2/3/4 行'
        '至此全齐——V071 两行无/V072 四行带类目/本篇三行；分类行系整理者动作非史料声明、'
        '不升格，V048 判例）。**零新建 source 连续第五首**（两源皆 V018 所立，539 第八次复用）。',
     ),
    'bg-015-world': (
        '**通鉴七十五卷有风雨，恰九处，且每一处都有落主**（闭域 202/204/210/211/248/250/'
        '254/257/261，机器断言）：永隆元年（庚辰，六八〇）裴行儉黑山 before 移营高岡，'
        '「是夜，風雨暴至，前所營地，水深丈餘」——风雨落进将令，诸将从此不敢多问；'
        '開元三年（乙卯，七一五）盧懷慎「虽贵为卿相……**所居不蔽風雨**」——风雨落在清谨'
        '卿相的屋顶上；大中元年（丁卯，八四七）宣宗对白敏中自忆宪宗之丧「**道遇風雨，'
        '百官、六宮四散避去**，惟山陵使長而多髯，攀灵驾不去」，答案是「令狐楚」——'
        '**风雨成了忠勤的赏价：令狐家的门第正是在这场雨里定下的**（V069 在册句只对照'
        '不重开）；中和二年（壬寅，八八二）高骈府里吕用之「每對駢**呵叱風雨**」——'
        '风雨沦为方士的道具。五段逐字入引为判决证据。**同字两界第十八形态·风雨形态首见**：'
        '**史部的风雨各有落主——落进军令、落在屋顶、骗进宫闱、定下门第；诗的「黃葉仍風雨」'
        '不落在任何人的账上**。**旧字面同样在册而两界**：「舊好」恰六（213/222/232/250/'
        '253/264 闭域，机器断言）**全部是国与国、镇与镇之间复盟修好，无一字落在朋友身上**'
        '（開元十八年吐蕃乞「倘使復修舊好，死無所恨」逐字入引）；'
        '诗的「舊好隔良緣」隔的是令狐绹。青樓/管絃/薄俗/新知通鉴全零（闭域）。',
     ),
    'bg-015-person': (
        '**旧传这一段只给了这个人与酒无关的一笔**：「府罢入朝，复以文章**干**襜，乃补太学'
        '博士」——段内「干」字恰二（「以所业文干之」/「复以文章干襜」，前者 V067 在册零重开，'
        '机器断言）：**这个人一生在敲门，史部记他敲门，没记他喝酒**——诗的「心斷新豐酒，'
        '銷愁斗幾千」要一杯新豐酒来销愁，通鉴的馬周恰十五处全在官迹、代陈便宜直门下省，'
        '**传里无一字酒**（贞观三年段机器断言）；新豐恰九全是地名人名（新豐县/新豐丞/新豐'
        '王孝傑——闭域档扫），**新豐酒零**。**段内题字全零**（風/雨/劍/篇/羈/黃/葉/青/樓/'
        '管/絃/新/舊/俗/愁/斗/銷/淒/窮+酒/飲 二十一项，机器断言）——**写风雨的人，'
        '传里无一风雨字**（V068 无一仙字/V071 无一瑟字/V072 无一蝉字同款第四枚）。'
        '紧接着史臣总评「无持操……坎壈终身」（V066/V068 在册零重开）——**诗里借剑借酒'
        '的人，史书里只剩敲门的两下**（读法声明，非史实因果）；KNOWN 零如实记录'
        '（第廿九例，audit 反向断言）。',
     ),
}
# chunk D 里正文值带尾逗号成单元素元组——归一为字符串（与 V072 BG 同形）
BG = {k: (v[0] if isinstance(v, tuple) else v) for k, v in BG.items()}

BG_LINES = {'bg-015-scene': (1, 2), 'bg-015-city': (3, 4),
            'bg-015-world': (5, 6), 'bg-015-person': (7, 8)}
BG_AUDIENCE = {'bg-015-scene': 'PRIMARY', 'bg-015-city': 'JUNIOR',
               'bg-015-world': 'SENIOR', 'bg-015-person': 'JUNIOR'}
BG_TITLES = {'bg-015-scene': '眼前：借来的剑篇',
             'bg-015-city': '这座城：同页并置的两案风雨',
             'bg-015-world': '这个天下：各有落主的风雨',
             'bg-015-person': '这个人：传里无一风雨字'}

CLAIMS = {
    'claim-bg-015-scene': (
        'FACT', 'LIKELY',
        '首联「淒涼寶劍篇，羈泊欲窮年」：借郭震剑篇开自己的场，第二句自陈羁泊经年——'
        '通鉴郭震恰一（劾相页）、剑篇零，新豐酒零、传段无一字酒（机器断言闭域）；'
        'ws 页五成级首见（已落九首李商隱页无此级）+零标记页（正交第三枚标本）；'
        'Vtext 裸/poem 句读双转录分工第二次在场+跨迁移零分歧面（与 V072 异体分工成对照组）'),
    'claim-bg-015-city': (
        'FACT', 'LIKELY',
        '互指循环指针第三次在场（↑ 回指+{{:風雨 (李商隱)}} 转引，539 回指页闭域恰五）；'
        '壳侧消歧器第二次在场+**整理者作者注挂锚首见**（==[[杜司勳]]{{*|牧}}== 恰一）；'
        '**卷页并置**：哭劉蕡块与杜司勳块直接相接恰一——选本把两案风雨排在同一换行上下；'
        '八句全唐诗语料全零；notes 排序谱第三态（「{{唐詩三百首}}↑」相邻全库恰一页）；'
        '分类三行（2/3/4 行三形态齐）；零新建 source 连续第五首'),
    'claim-bg-015-world': (
        'FACT', 'LIKELY',
        '通鉴風雨恰九（闭域 202/204/210/211/248/250/254/257/261）且各有落主（将令/屋顶/'
        '忠勤赏价/骗术——四段逐字入引）；**旧好恰六全在邦交**（213/222/232/250/253/264'
        '闭域，无一字落在朋友身上；開元十八年吐蕃乞复旧好段入引）——同字两界第十八形态·风雨形态首见：史部风雨各有落主，'
        '诗的黃葉仍風雨不落在任何人的账上；旧好两界：邦交之好有账，故人之好无账'),
    'claim-bg-015-person': (
        'FACT', 'LIKELY',
        '旧传简化字段首引「府罢入朝，复以文章干襜，乃补太学博士」——段内干字恰二谱'
        '（干之在册零重开/干襜首引）；**段内题字二十一项全零：写风雨的人传里无一风雨字**'
        '（V068/V071/V072 同款第四枚）；通鉴馬周恰十五无酒杯、新豐恰九无新豐酒——'
        '诗要销愁的酒，史部只借出地名；「无持操/坎壈终身」在册零重开；读法声明非史实因果'),
}
CITATIONS = [
    ('claim-bg-015-scene', 'source-ws-t300-015',
     '页面 風雨（《唐詩三百首》第 15 首选本页，页题裸名；title+author+署名行+Vtext 八行'
     '裸片+poem 存原样块+notes 行以「……」相连——poem 带句读而 Vtext 全裸（双转录句读分工'
     '第二次——V072 首见成系列）；**五成页首见**（注记 {{Textquality|50%}} 入引——已落九首'
     '李商隱诗页从无此级）+零标记页（{{另}}/{{別}}/{{*}}/<ref>/{{reflist}} 全零——评级与'
     '标记正交第三枚标本）；**与 V018 零分歧面**（ws-raw 八行逐字同面，双向断言）；'
     '正文第二引第二十一例（V018 句读式一引在先不重开）',
     join(WS_TITLE, WS_AUTHOR, WS_VSIG, WS_VT1, WS_POEM, WS_NOTE3)),
    ('claim-bg-015-city', 'source-quantangshi-539',
     '卷五百三十九·李商隱《風雨》消歧壳（壳侧作者消歧器第二次在场——V072 首见成常规，'
     '显示名仍裸風雨）；壳外全卷无本篇正文一字（八句全唐诗语料全零机器断言）；**与本页 '
     'notes ↑回指互指第三次在场**（539 回指页闭域恰五）；**卷页并置**：「==[[杜司勳]]'
     '{{*|牧}}==」恰一——整理者作者注直接挂题锚（壳侧挂锚注记首见），相邻《哭劉蕡》块与之'
     '直接相接恰一（杜牧「高樓風雨感斯文」全唐诗恰一——两案风雨同页上下）；'
     '源行 V018 已立、本迁移第八次复用零新建）',
     join(V539_SHELL, V539_DM)),
    ('claim-bg-015-city', 'source-ws-t300-015',
     '页面 風雨（notes 三连一行整值入引（{{Textquality|50%}} 居首+{{唐詩三百首}}+↑底本回指'
     '——**notes 排序谱第三态**：「{{唐詩三百首}}↑」相邻形全库恰一页机器断言；↑ 指向恰是'
     '转引本篇的 539 壳——互指之诗页侧）+页尾分类三行（简繁并立，含 [[Category:李商隱]]；'
     '**分类三形态 2/3/4 行至此全齐**——V071 两行无作者/V072 四行带类目/本篇三行；'
     '分类行系整理者分类动作：非史料声明、不升格，V048 判例）；本迁移零新建源连续第五首）',
     join(WS_NOTE3, WS_CAT3)),
    ('claim-bg-015-world', 'source-zizhi-tongjian-events',
     '卷二百零二·永隆元年裴行儉移营「是夜，風雨暴至」（风雨落进军令）……卷二百一十一·'
     '開元三年盧懷慎「所居不蔽風雨」（风雨落卿相屋顶）……卷二百四十八·大中元年宣宗忆'
     '宪宗之喪「道遇風雨，百官、六宮四散避去」对曰「令狐楚」（风雨成忠勤赏价——令狐家'
     '门第在此雨定下；V069 山陵使在册句只对照不重开，引文越句而取）……卷二百五十四·'
     '中和二年吕用之「每對駢呵叱風雨」（风雨成方士道具）；通鉴風雨恰九九卷闭域/'
     '舊好恰六全在邦交（213 吐蕃開元十八年闭域）——五段逐字入引为判决证据）',
     join(TJ_FY1, TJ_FY2, TJ_FY3A, TJ_FY3B, TJ_FY4, TJ_JH)),
    ('claim-bg-015-person', 'source-jiutangshu-wenyuan',
     '舊唐書卷一九〇下·李商隱（**简化字录入**照登原样，V016 locator 同款标注）'
     '（「府罢入朝，复以文章干襜，乃补太学博士」段（史部记他敲门不记他喝酒——全库查重'
     '恰零域首引；段内干字恰二谱：干之 V067 在册零重开/干襜首引；传区间归属机器断言；'
     '段内诗面题字二十一项全零——風/雨/劍/篇/羈/黃/葉/青/樓/管/絃/新/舊/俗/愁/斗/銷/淒/'
     '窮+酒/飲——**写风雨的人传里无一风雨字**（V068 无一仙/V071 无一瑟/V072 无一蝉同款）；'
     '「干字谱」系读法声明；V016/V066–V069/V072 在册句零重开）',
     JTS_P),
    ('claim-bg-015-person', 'source-zizhi-tongjian-events',
     '卷一百九十三·貞觀三年（己丑，六二九）馬周条（茌平人馬周客游长安舍常何家代陈便宜'
     '二十余条——**史部马周恰十五处全在官迹、此段无一字酒无一字新豐**（机器断言）：'
     '诗要销愁的新豐酒，通鉴新豐恰九全是地名人名而新豐酒零——诗借的酒史部只借出地名）',
     TJ_MZ),
]
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 54 首·八句五律 2/2/2/2）；史实句均有逐字引证；'
                 '系年第四十八次判决（题证系列第卅六状·风雨落主与旧好无账）'
                 '「通鉴的风雨每一处都有落主；诗的黃葉仍風雨不落在任何人的账上」——'
                 '同字两界第十八形态·风雨形态首见：通鉴風雨恰九（202/204/210/211/248/250/'
                 '254/257/261 闭域，机器断言）四段落主：裴行儉移营避雨（将令）、盧懷慎'
                 '所居不蔽雨（屋顶）、宣宗忆宪宗之喪风雨独令狐楚攀灵驾（忠勤赏价——'
                 '令家门第在此雨定下）、吕用之呵叱风雨（骗术）；**诗的「黃葉仍風雨」'
                 '不落在任何人的账上**；「舊好」恰六（213/222/232/250/253/264 闭域）'
                 '**全部是国与镇之间复盟修好，无一字落在朋友身上**——诗的「舊好隔良緣」'
                 '隔的是令狐绹：邦交之好有账，故人之好无账；青樓/管絃/薄俗/新知/淒涼/'
                 '羈泊/銷愁/斗幾千 通鉴全零在册闭域；新豐恰九全是地名人名而**新豐酒零**、'
                 '馬周恰十五全在官迹无一杯酒、寶劍恰二无一剑篇事——诗借的典故史部只'
                 '借出地名人名；**互指循环指针第三次在场成连续系列**（↑ 回指+{{:風雨 (李商隱)}} '
                 '转引；539 回指页闭域恰五：寄令狐郎中/蟬/錦瑟/韓碑/風雨）；**壳侧作者'
                 '消歧器第二次在场**（V072 首见成常规）+**整理者作者注挂锚首见**（'
                 '==[[杜司勳]]{{*|牧}}== 恰一）+**卷页并置机器断言**（哭劉蕡块与杜司勳块'
                 '直接相接恰一——选本把李商隱哭刘蕡和杜牧读他的高楼风雨放在同一个换行上下；'
                 '「高樓風雨感斯文」全唐诗恰一）；**零新建 source 连续第五首**（两源皆'
                 'V018 所立，539 第八次复用）；正文第二引上限用满第二十一例（V018 句读式'
                 '一引在先+本迁移 poem 原样面，同面各从其录，V018 句读式引文零重开断言）；'
                 '**跨迁移零分歧面**（ws-raw 对 ws-raw 八行逐字同面——与 V072 异体分工'
                 '恰成对照组，生成时双向断言）；**五成页首见**（{{Textquality|50%}}——'
                 '已落九首李商隱页无此级；TQ 谱 50:92/75:142/100:26 闭域）+**零标记页×五成**'
                 '（正交第三枚标本）；notes 排序谱第三态（「{{唐詩三百首}}↑」相邻全库恰'
                 '一页）；分类三行（2/3/4 行三形态齐——分类行数即形态，不升格 V048）；'
                 'PERSON 旧传简化段首引一段（复以文章干襜——段内干字恰二谱：干之在册/'
                 '干襜首引；**段内题字二十一项全零：写风雨的人传里无一风雨字**——'
                 'V068/V071/V072 同款第四枚；无持操在册零重开；「史书里只剩敲门的两下」'
                 '读法声明）；V016/V018/V053/V066–V072 在册句零重开（域断言）；'
                 'KNOWN 零如实记录（第廿九例，audit 反向断言）；判例关键语零入引文。' for k in BG}


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
    A("""-- V073：李商隱《風雨》(work-t300-015) 四层背景（阶段 D 第 54 首·风雨两界）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V026、V033、V035、V039、V048、V053、V057、
--       V058、V059、V060、V061、V062、V063、V064、V065、V066、V067、V068、V069、V070、
--       V071、V072 已执行
--       （work-t300-015 与其 text-work-t300-015-ws（version_code=ws-raw，八行带句读，
--       与本快照 ws 页 poem 块逐字同面零分歧——与 V072 的 ws-fold 异体分工恰成对照组）
--       与其源 source-ws-t300-015（edition 字段即底本「全唐詩」）都是 V018 的行；
--       source-quantangshi-539 是 V018 已立的卷539 卷页源（V018/V067/V068/V069/V070/
--       V071/V072 已引，本迁移第八次复用——这次引到的是消歧壳+杜司勳注锚两块）；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       source-jiutangshu-wenyuan 是 V016 已立的旧唐书文苑传源（李商隐传在此，简化字录入）；
--       判例在册句（义山/开成二年/岭表/三十六体/未几病卒/大中末/仲郢坐/还郑州 V016、
--       绹不之省/坎壈终身 V066/V067、以所业文干之/下笔不能自休 V067、恃才诡激/
--       为当涂者所薄 V068、惟山陵使長而多髯/次子綯有才器/背恩 V069、锦瑟句读式正文与
--       灞上秋居风雨 V018、春晓风雨 V053、{{:蟬 (李商隱)}}/↑…蟬 V072、{{:錦瑟}}/
--       ↑…錦瑟 V071、{{:夜雨寄北}}/↑…寄令狐郎中 V069/V070、文思清丽/庭筠过之 V072、
--       逢吉薦紳清直/丁柔立/義不臣賊/舉家西歸 V072）只对照不重开。
--       **本迁移零新建 source（连续第五首）——
--       audit 断言本文件零 poetry_source INSERT、回滚零 source 删除。**
--
-- 数据源（可复现）：emit_v073.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/風雨__李商隱_.txt（五成页首见+零标记页（正交第三枚标本）+Vtext 裸/poem 句读
--   双转录分工第二次+与 V018 零分歧面（ws-raw 对 ws-raw 八行双向断言）+notes 三连五成居首
--   （「{{唐詩三百首}}↑」相邻全库恰一页）+分类三行（2/3/4 行三形态齐）+无 times/type/from）、
--   全唐詩卷539（锚 ==[[風雨 (李商隱)|風雨]]== 与 {{:風雨 (李商隱)}} 各全唐诗唯一（机器断言）+
--   壳外全卷无本篇一行（八句全库零）+==[[杜司勳]]{{*|牧}}== 恰一（作者注挂锚首见）+
--   哭劉蕡块与杜司勳块直接相接恰一（卷页并置）+風/春風味壳各恰一闭域）、
--   舊唐書卷190下（李商隐段首引一段+段内题字二十一项全零+干恰二+段边界断言）、
--   通鑑卷202/211/248/254（风雨四段逐字入引+年标题窗口：永隆元年六八〇/開元三年七一五/
--   大中元年八四七/中和二年八八二）+卷213 吐蕃乞复旧好段入引（開元十八年七三〇窗口）
--   +卷193 马周段无酒无新豐断言+
--   通鑑 75 卷负证计数扫描（風雨恰九闭域 202/204/210/211/248/250/254/257/261+舊好恰六+
--   新豐恰九而新豐酒零+寶劍恰二+郭震恰一+青樓/管絃/薄俗/新知/淒涼/羈泊/銷愁/斗幾千全零）+
--   既有迁移引文域逐句查重——传区间归属、二引/零重开/首引零域前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 background_line（八句五律 **2/2/2/2 顺次**：scene→1,2 city→3,4 world→5,6 person→7,8，
--   绑 text-work-t300-015-ws 的 8 行）+ 不碰 poetry_text_line。
-- 不做：**不新建任何 source（连续第五首）**；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「史部的风雨各有落主；诗的风雨不落在任何人的账上」）：
--   * 「风雨两界」「旧好两界」系通鉴五段逐字入引支撑的对照判决，非史实因果——通鉴不记这首诗；
--     亦不考本诗系年（编年诸说一律不采信不铸造）；
--   * 「令狐家门第在此雨里定下」「史书里只剩敲门的两下」标明读法声明；
--   * 大中元年风雨对答与诗作者本人无涉——令狐楚是令狐绹之父，只作门第背景读法不作因果；
--   * 正文第二引上限用满：V018 句读式一引在先，本迁移引 ws 页 poem 块存原样面——
--     同面各从其录，V018 句读式引文不重开（生成时硬断言），此后此诗正文关闭；
--   * 「作者注挂锚首见」「卷页并置」「五成页首见」「三形态齐」均照登不判；
--   * 分类三行系整理者动作：非史料声明、不升格，V048 判例；
--   * 通鉴風雨恰九闭域档扫（204 倪斌疏/210 宋务光疏/250 田牟犒军/257 大风雨/261 大风雨
--     震电五处不入引，只计数）；
--   * KNOWN 零如实记录（第廿九例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * V011/V016/V018/V026/V033/V035/V039/V053/V063/V066–V072 已引诸句只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 72，不含 73
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-015-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-015','source-quantangshi-539');
--    -- 两行（均 V018 所立，本迁移不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-015-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-015-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-015';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-015-%';  -- 四行全 LIKELY
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-015';   -- 恰 1（V018 所立）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-015'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-015';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-015-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V073_rollback.sql（按 id 全枚举删除；**零 source 删除**——
--   source-ws-t300-015 与 source-quantangshi-539 皆 V018 所立，绝不删）
START TRANSACTION;""")

    A('\n-- ---------- 0. 零新建 source（连续第五首；两源皆 V018 所立复用） ----------')

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
    brows = [{'id': k, 'work_id': 'work-t300-015',
              'layer': {'bg-015-scene': 'SCENE', 'bg-015-city': 'CITY',
                        'bg-015-world': 'WORLD', 'bg-015-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（八句五律 2/2/2/2 顺次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-015-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 73, 'Li Shang-yin''s Storm (work-t300-015) background layers (stage-D poem 54, eight-line regulated verse 2/2/2/2): dating verdict forty-eight, thirty-sixth shape of the title-evidence series -- every rain in the histories has an owner; the poem''s rain falls on no one''s ledger. Same-character-two-realms, eighteenth shape: the storm (fengyu) shape, first seen. The Tongjian carries exactly nine storms across seventy-five juan (closed set 202/204/210/211/248/250/254/257/261, machine-asserted); four are cited verbatim as verdict evidence: in Yonglong 1, gengzi, 680, Pei Xingjian orders the camp moved to high ground before the night -- "that night the wind and rain came violently; the ground they had camped on was a zhang deep in water" (the storm inside a commander''s order); in Kaiyuan 3, yimao, 715, Lu Huaishan, though a chancellor, "dwelt where roof and eaves did not keep out wind and rain" (the storm on a clean minister''s roof); in Dazhong 1, dingmao, 847, Emperor Xuanzong recalls his own youth at Xianzong''s funeral procession -- "we met wind and rain on the road; the hundred officials and the six palaces all scattered to shelter," and the one man who clung to the royal carriage and would not leave was Linghu Chu (the storm becomes the price tag of loyalty: the Linghu family''s rise to great-house status was set in that rain -- V069''s closed sentence quoted for contrast, never reopened); in Zhonghe 2, renyin, 882, Lu Yunzhi at Gao Pian''s court "scolded the wind and rain in front of Pian" (the storm becomes a charlatan''s prop). The poem''s "yellow leaves, still wind and rain" falls on none of these ledgers. The old-friendship word likewise on the books but in two realms: "jiuhao" (old friendship) appears exactly six times (213/222/232/250/253/264, closed set, machine-asserted), every one of them a treaty reconciliation between states or garrisons -- not once does the word touch a friend; the poem''s "old friends cut off by a thin affinity" cuts against Linghu Tao: state friendships have ledgers, friendships between old friends do not. The Tongjian scores zero on blue tower, pipes-and-strings, thin mores, new acquaintances; Xin丰 appears nine times, all place-names and籍贯, and "Xinfeng wine" zero times; Ma Zhou appears fifteen times, all in official careers, never with a cup; the two treasure-swords (Li Su gifting a sword, Lu Yunzhi faking one) are never the sword-song -- the allusions the poem borrows: the histories lend out only place-names and names of men. The mutual-pointer binding, first seen V071 and twice in V072, recurs a third time and becomes a continuous series (machine-asserted: exactly five ws pages carry the 539 back-reference -- Ji Linghu, Cicada, Inscribed Harps, Han Stele, Storm). The author-disambiguator sits on the shell side a second time (normalized from V072''s first), and in a NEW shape the compilers'' author-note hangs directly on an anchor: "==[[杜司勳]]{{*|牧}}==" (exactly one, machine-asserted) whose first line is "High tower, wind and rain: I feel the sense of this writing" -- and the page-placement assertion: in juan 539 the block of Li Shang-yin''s "Weeping over Liu Fen" and the block of Du Mu''s "Du Sixun" are directly adjacent (exactly one join), so the anthology itself stacks the two storm cases across a single line-break. The eight lines score zero across the Quan Tangshi corpus (the text lives only on the poem page). ZERO new sources, fifth poem running; both sources from V018, the 539 source at its eighth reuse. Body use-ceiling reached, twenty-first instance, and a new counter-pair to V072: V018 stored ws-raw with punctuation and this snapshot''s poem block matches it line-for-line with zero variant divergence (cross-migration zero-divergence face, the mirror image of V072''s variant division of labor; generator asserts both sides and that V018''s punctuated excerpt is never re-used); the body is now closed. Page forms: first 50 percent-grade page among the landed Li Shang-yin poems (TQ spectrum closed set 50:92/75:142/100:26), a zero-mark page at 50 percent (third specimen proving rating and mark-count orthogonal), notes ordering third state ("{{唐詩三百首}}↑" adjacency exactly one page in the corpus, machine-asserted), and the category footer three lines with the author category (forms 2/3/4 lines now complete -- the line count itself is the form; editorial, not a source claim, not upgraded, V048 precedent). PERSON first-cites one zero-domain simplified JTS passage -- "the office ended, he entered court, and again pressed for a posting with his writing, and was appointed Chancellery Academician" -- the second "press" graph in the biography (the first, pressed with his compositions, closed in V067, never reopened): the histories record the man knocking on doors and never record him drinking; the poem asks for a cup of Xinfeng wine to dissolve grief, and the Tongjian has nine Xinfengs but no Xinfeng wine, and fifteen Ma Zhous but no cup; the biography segment holds none of the twenty-one title-side graphs -- the man who wrote the storm leaves not one wind-or-rain graph in his biography (same shape as V068''s no-immortal-graph, V071''s no-harp-graph, V072''s no-cicada-graph, the fourth of the series); "the histories leave only two knocks on the door" is declared as reading, not fact. KNOWN zero honestly recorded (twenty-ninth instance, audit reverse-asserts); closed precedent keywords (including V018''s Babu Autumn Dwelling storm and V053''s Spring Dawn storm and V069''s mountain-tomb-marshal sentence) stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 73);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V073 精确回滚：只删 V073 插入的行（id 全枚举）。',
         '-- **零 source 删除**：source-ws-t300-015（V018 所立的 ws 选本页源）与',
         '-- source-quantangshi-539（V018 所立的卷539 卷页源）本迁移皆复用，绝不删；',
         '-- work-t300-015 本体、其 text_line 8 行都是 V018 的行，绝不删；',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 73;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_VSIG, WS_VT1, WS_POEM, WS_NOTE3, WS_CAT3, V539_SHELL,
              V539_DM, TJ_FY1, TJ_FY2, TJ_FY3A, TJ_FY3B, TJ_FY4, TJ_JH, TJ_MZ, JTS_P]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # SCENE：裸/句读分工+零分歧面必须逐字入引 + V018 句读式引文零重开
    scene_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-015-scene')
    if '{{VtextStart}}淒涼寶劍篇{{VtextEnd}}' not in scene_ws:
        bad.append('Vtext 裸行未入 SCENE 引文（双转录句读分工第二次照登硬卡）')
    if '淒涼寶劍篇，' not in scene_ws:
        bad.append('poem 句读面未入 SCENE 引文（句读分工硬卡）')
    if '{{Textquality|50%}}' not in scene_ws:
        bad.append('五成页注记标记未入 SCENE 引文（硬卡）')
    if '淒涼寶劍篇，……銷愁斗幾千。' in cited:
        bad.append('V018 句读式引文重开了——本迁移引 poem 原样面，句读式不重开')
    # CITY：壳侧消歧+作者注挂锚+并置必须在引文内
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-015-city' and s == 'source-ws-t300-015')
    if '↑ [[全唐詩/卷539#風雨|全唐詩·卷五百三十九]]' not in city_ws:
        bad.append('↑回指注未逐字入 CITY 引文（互指诗页侧照登硬卡）')
    if '[[Category:李商隱]]' not in city_ws:
        bad.append('CITY 分类引文缺作者分类（三形态齐的标本硬卡）')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-015-city' and s == 'source-ws-t300-015'):
        bad.append('CITY ws locator 须含「不升格」声明')
    city_q = next(ex for c, s, _, ex in CITATIONS if s == 'source-quantangshi-539')
    if '{{:風雨 (李商隱)}}' not in city_q:
        bad.append('消歧壳转引未逐字入 CITY 引文（壳侧消歧第二次照登硬卡）')
    if '==[[杜司勳]]{{*|牧}}==' not in city_q:
        bad.append('杜司勳作者注挂锚未入 CITY 引文（壳侧注记首见硬卡）')
    if '羈泊欲窮年' in city_q or '銷愁斗幾千' in city_q:
        bad.append('CITY 卷页引文混入本篇正文语——壳外无正文一行正是本迁移标本')
    c_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-015-city' and s == 'source-quantangshi-539')
    if '壳侧' not in c_loc or '消歧' not in c_loc or '挂锚' not in c_loc:
        bad.append('CITY 卷页 locator 须含「壳侧/消歧/挂锚」声明')
    # WORLD：五段史文必须在引文内；诗语零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-015-world')
    for tok in ('是夜，風雨暴至', '所居不蔽風雨', '道遇風雨', '百官、六宮四散避去',
                '令狐楚', '每對駢呵叱風雨', '倘使復修舊好', '死無所恨'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（五段必须入引）')
    for tok in ('寶劍篇', '心斷新豐酒', '銷愁', '舊好隔良緣', '薄俗', '新知', '青樓自管絃'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文）')
    w_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-015-world')
    if '风雨' not in w_loc or '舊好' not in w_loc or '邦交' not in w_loc:
        bad.append('WORLD locator 须点出风雨/舊好/邦交（两界柄词声明）')
    # PERSON：首引句必须在引文内+在册句零重开+马周段无酒
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-015-person')
    for tok in ('复以文章干襜', '乃补太学博士'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺首引要素「{tok}」（简化字段首引照登硬卡）')
    if '酒' in p_ex:
        bad.append('PERSON 引文混入酒字——传段无酒正是标本')
    for tok in ('{{:夜雨寄北}}', '{{:錦瑟}}', '{{:蟬 (李商隱)}}',
                '↑ [[全唐詩/卷539#寄令狐郎中', '↑ [[全唐詩/卷539#蟬', '↑ [[全唐詩/卷539#錦瑟',
                '君問歸期未有期', '俄而茂元卒', '检校水部员外郎', '亚坐德裕党', '白敏中执政',
                '令狐绹在内署', '商隐随亚在岭表累载', '李商隐，字义山，怀州河内人。',
                '开成二年', '未几病卒', '大中末', '仲郢坐', '还郑州', '绹不之省', '坎壈终身',
                '恃才诡激', '为当涂者所薄', '以所业文干之', '下笔不能自休', '文思清丽',
                '庭筠过之', '商隐能为古文', '不喜偶对', '茂元爱其才', '本以高難飽',
                '我亦舉家清', '逢吉薦紳清直', '坐阿附貶南陽尉', '義不臣賊，舉家自殺',
                '舉家西歸', '初聞此語，能不惘然', '東拒滄海', '言與淚俱', '錦瑟無端五十',
                '只是當時已惘然', '灞原風雨定', '夜來風雨聲', '春眠不覺曉', '高難飽',
                '惟山陵使長而多髯', '次子綯有才器', '淒涼寶劍篇，……銷愁斗幾千。'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    if BG_LINES != {'bg-015-scene': (1, 2), 'bg-015-city': (3, 4),
                    'bg-015-world': (5, 6), 'bg-015-person': (7, 8)}:
        bad.append('八句 background_line 须 2/2/2/2 顺次（V020 以来八句篇常规）')
    if len(re.findall(r"text-work-t300-015-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # 零新建 source（连续第五首）
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
        bad.append("V073 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V073 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-015' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V073 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-015' AS subject_id" in sql:
        bad.append('V073 的 claim 主语应全部是 bg-015-*，work-t300-015 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V073 不碰 poetry_text_line')
    body_all = ''.join(BG.values())
    if '风雨形态首见' not in body_all:
        bad.append('BG 须含「风雨形态首见」（同字两界第十八形态）声明')
    if '各有落主' not in body_all:
        bad.append('BG/WORLD 须含「史部的风雨各有落主」判决')
    if '无一风雨字' not in body_all:
        bad.append('BG/PERSON 须含「写风雨的人传里无一风雨字」段级零证声明')
    if '第三次在场' not in body_all:
        bad.append('BG/CITY 须含「互指循环指针第三次在场」声明')
    if '挂锚' not in body_all:
        bad.append('BG/CITY 须含「整理者作者注挂锚首见」声明')
    if '零分歧面' not in body_all:
        bad.append('BG/SCENE 须含「跨迁移零分歧面」声明')
    if '五成页首见' not in body_all:
        bad.append('BG/SCENE 须含「五成页首见」声明')
    if '零新建' not in body_all:
        bad.append('BG/CITY 须含「零新建 source（连续第五首）」声明')
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
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 73)' not in vblk:
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 15 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（旧传李商隐段一首引句，段界 ==弟 羲叟==）；'
              f'六处年标题窗口断言（永隆元年六八〇/開元三年七一五/大中元年八四七/中和二年八八二/貞觀三年六二九/開元十八年七三〇）；'
              f'负证机器复查六层（通鉴風雨恰九闭域202,204,210,211,248,250,254,257,261+舊好恰六+'
              f'新豐恰九新豐酒零+寶劍恰二+郭震恰一+馬周恰十五+青樓/管絃/薄俗/新知/淒涼/羈泊/'
              f'銷愁/斗幾千/淒涼寶劍篇全零/全唐诗风雨壳锚与转引各恰一+杜司勳锚恰一+八句全库零+'
              f'哭劉蕡块与杜司勳块相接恰一+風/春風壳各恰一闭域/ws 五成恰一满级零+零标记五型全零+'
              f'页内風雨恰五+双转录首末句各恰二+Vtext裸面+三百首↑相邻恰一页+539回指页恰五+'
              f'分类三行含作者+无times/type/from/旧传段题字二十一项全零+干恰二卷十一+'
              f'V018 八行同面双向断言，快照变动即中止）；'
              f'前提全库查重硬卡十二件+十四首引句零域断言；消歧壳/↑回指/Vtext署名行照登硬卡；'
              f'SCENE 五成+裸面+句读面入引+V018 句读式引文零重开断言；CITY 壳侧/消歧/挂锚硬卡；'
              f'CITY「不升格」硬卡；五段通鉴史文入引+诗语零混入断言；'
              f'PERSON 首引要素入引硬卡+段内无酒硬卡+V016/V018/V053/V066–V072 诸句零重开硬卡；'
              f'判例只引不重开断言（含 V018 灞上秋居风雨与 V053 春晓风雨与 V069 山陵使在册句在内）；'
              f'八句 2/2/2/2 形制断言；零 KNOWN 反向断言；'
              f'**零新建 source 断言（INSERT 恰零+回滚零 source 删除）**——连续第五首；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
