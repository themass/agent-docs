#!/usr/bin/env python3
"""阶段 D 第 55 首：生成 V074——李商隱《涼思》(work-t300-032, V018 已立) 四层背景。

**本迁移新建一枚 source：source-ws-t300-032**——「零新建 source 连续五首」在此正当终结：
V018 给《涼思》立正文时用的是《全唐詩》卷540 卷页（version_code vol-raw、source-quantangshi-540），
此《唐詩三百首》选本页当时未建源——卷页与诗页是两个独立见证面（V066 賈生判例：
「本诗 V018 立正文时用的是卷页，此选本页当时未建源——卷页与诗页是两个独立见证面，
本迁移引诗页非新源不能承载」。本篇沿用同款，新建 ws 选本页源承载诗页署名/双转录/页形制；
卷540 卷页源第三次复用，V018/V066 已引）。

绑定形态：跨迁移**跨源零分歧面首见**——V018 文本行八句取自卷540（vol-raw），本快照 ws 页
poem 块与之逐字同面（ws 面 ≡ 540 面，生成时八行双向断言）：**同一首诗的选本页与卷页两
独立见证面在此逐字相合**——与 V073「八句全唐诗语料全零、诗只活在诗页」恰成两极（本篇诗八句
全唐诗语料恰一，恰在 540 卷页内联：诗同时活在诗页与卷页两处）；与 V072「异体分工」也成对照
（那首两快照异体不同，这首两见证面异体全同）。

540 卷页新形态：**旧式裸名锚「==涼思==」+正文内联**（V066 賈生旧式裸锚判例延展——本篇锚
无消歧器、无 {{:}} 转引壳，八句正文直接内联在锚下：与 V072/V073 的空壳转引「{{:蟬 (…)}}」
/{{:風雨 (…)}}」恰成卷页见证面两极——内联 vs 空壳）；**卷页并置**：卷540 里《江上》块
（尾句「吾道豈淹留」）与本篇直接相接、「==涼思==」块与《鸞鳳》块直接相接（机器断言各恰一）
——选本把「吾道豈淹留」（我这条路哪能留下）压在「南陵寓使遲」（托寓居南陵的人送信迟迟）
头上：前一首诗的收句成了下一首的注脚（读法声明）。

「为什么写」走到**三远两界**（同字两界第十九形态·寄远形态首见）：诗里有三处「远」——
「北斗兼春遠」「南陵寓使遲」「天涯占夢數」。通鉴这三处地名各有所指，**没有一处是寄信**：
北斗恰一（開元十二年王皇后使其兄祭「南北斗」咒求生子——史的北斗是废后的符咒，诗的北斗是兼春之远）；
南陵恰二（上元元年傅子昂「屯南陵」将下江州 / 乾符五年黄巢攻宣州「敗於南陵」——史的南陵只有
屯兵与败军，诗的南陵是一封迟迟寄不出的信）；天涯恰一（會昌二年李德裕论回鹘「累代可汗墳墓，
隔在天涯」——史的天涯是汗祖坟的隔绝，诗的天涯是占梦的游子）；「占夢」「新知」「涼思」通鉴
全零（诗想寄一封信问一个梦，史部连「占夢」这个动作都不识）。

ws 页形制（SCENE/CITY 层）：**五成页第二次在场**（{{Textquality|50%}}——V073 首见、本篇成系列
第二枚；已落李商隱诗页 TQ 谱档扫）；**零标记页×五成**第二枚标本（另/别/*/ref/reflist 全零——
评级与标记多寡正交）；notes **二连无↑**（{{Textquality|50%}}{{唐詩三百首}}，无底本回指——
V073 三连带↑/V066 无评级二连/本篇五成二连无↑：排序谱再补一态）；**{{VH1|涼思}} 排版模板**
（全库 22 页闭域档扫）；分类**四行含作者+「詠懷詩」类目**（全库恰三页带詠懷詩：夜雨寄北/涼思/
登岳陽樓机器断言；V048 判例不升格）；双转录句读分工**第三次在场**（Vtext 裸行/poem 句读——
V072 首见、V073 第二次、本篇成连续系列）；无 {{clr}}（V073 有 {{clr}}，本篇无——排版收尾形态
照登）。

8 句五律 shape：**2/2/2/2 顺次**（scene→1,2 city→3,4 world→5,6 person→7,8）。

用法: python3 -I emit_v074.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402

WS = pathlib.Path('/tmp/src-dl/ws-poems/涼思.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
V540 = pathlib.Path('/tmp/src-dl/quantangshi/vol540.txt').read_text(encoding='utf-8')
V018 = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/V018__tang300_ws_verified.sql').read_text(encoding='utf-8')
TJ212 = pathlib.Path('/tmp/src-dl/tongjian/tj-212.txt').read_text(encoding='utf-8')
TJ221 = pathlib.Path('/tmp/src-dl/tongjian/tj-221.txt').read_text(encoding='utf-8')
TJ253 = pathlib.Path('/tmp/src-dl/tongjian/tj-253.txt').read_text(encoding='utf-8')
TJ246 = pathlib.Path('/tmp/src-dl/tongjian/tj-246.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 涼思', '| title    = 涼思',
                         'ws header title(裸名题面——涼思二字通鉴全零)')
WS_AUTHOR = slice_between(WS, '| author   = 李商隱', '| author   = 李商隱',
                          'ws header author(署名直证)')
WS_VH1 = slice_between(WS, '{{VH1|涼思}}', '{{VH1|涼思}}',
                       'ws VH1 排版模板锚(全库恰22页闭域档扫)')
WS_VSIG = slice_between(WS, '{{Vtext|}}\n{{Vtext|李商隱}}\n{{Vtext|}}',
                        '{{Vtext|}}\n{{Vtext|李商隱}}\n{{Vtext|}}',
                        'ws Vtext 署名行(李商隱页群闭域)')
WS_VT1 = slice_between(WS, '{{VtextStart}}客去波平檻{{VtextEnd}}', '疑誤有新知{{VtextEnd}}',
                       'ws Vtext 八行全裸无句读整片(双转录句读分工第三次——V072首见V073第二次)')
WS_POEM = slice_between(WS, '客去波平檻，蟬休露滿枝。', '疑誤有新知。\n</poem>',
                        'ws poem 块八句存原样(跨源零分歧面——与V018取自540之八句逐字同面,双向断言)')
WS_NOTE2 = slice_between(WS, '| notes    = {{Textquality|50%}}{{唐詩三百首}}',
                         '| notes    = {{Textquality|50%}}{{唐詩三百首}}',
                         'ws notes 二连一行(五成居首+三百首+无↑底本回指——排序谱再补一态)')
WS_CAT4 = slice_between(WS, '[[Category:李商隱]]\n[[Category:唐诗]]\n[[Category:唐詩三百首|李]]\n[[Category:詠懷詩]]',
                        '[[Category:李商隱]]\n[[Category:唐诗]]\n[[Category:唐詩三百首|李]]\n[[Category:詠懷詩]]',
                        'ws 分类四行连片(含作者+詠懷詩——詠懷詩类目全库恰三页闭域)')
V540_BLOCK = slice_between(V540, '==涼思==\n<poem>\n客去波平檻，蟬休露滿枝。',
                           '疑誤有新知。\n</poem>',
                           '卷540 本篇内联块(旧式裸名锚+正文内联——V066判例延展;跨源零分歧面之卷页侧)')
V540_PREV = slice_between(V540, '吾道豈淹留。\n</poem>\n\n==涼思==',
                          '吾道豈淹留。\n</poem>\n\n==涼思==',
                          '卷540 江上块尾接涼思锚(卷页并置——吾道豈淹留压在南陵寓使遲头上)')
V540_NEXT = slice_between(V540, '疑誤有新知。\n</poem>\n\n==鸞鳳==',
                          '疑誤有新知。\n</poem>\n\n==鸞鳳==',
                          '卷540 涼思块尾接鸞鳳锚(并置第二向——机器断言)')
TJ_DB = slice_between(TJ212, '使僧明悟為後祭南北斗', '合而佩之，',
                      '通鉴開元十二年王皇后祭南北斗咒(北斗兼春远之通鉴侧;窗口断言)')
TJ_NL1 = slice_between(TJ221, '傅子昂屯南陵', '徇江西。',
                       '通鉴上元元年傅子昂屯南陵(南陵寓使迟之通鉴侧——屯兵;窗口断言)')
TJ_NL2 = slice_between(TJ253, '黃巢寇宣州', '敗於南陵。',
                       '通鉴乾符五年黄巢敗於南陵(南陵之通鉴侧——败军;窗口断言)')
TJ_TY = slice_between(TJ246, '累代可汗墳墓，隔在天涯', '不施於彼',
                      '通鉴會昌二年论回鹘隔在天涯(天涯占梦数之通鉴侧;窗口断言)')
JTS_P = slice_between(JTS, '三年入朝，京兆尹卢弘正奏署掾曹，令典笺奏。',
                      '三年入朝，京兆尹卢弘正奏署掾曹，令典笺奏。',
                      '旧传李商隐段首引(简化字段——寄远无账,传段无一寄书字;段边界断言)')

# ---------- 旧传段边界与首引句区间归属断言 ----------
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

_window(TJ212, TJ_DB, '開元十二年')
_window(TJ221, TJ_NL1, '上元元年')
_window(TJ253, TJ_NL2, '乾符五年')
_window(TJ246, TJ_TY, '會昌二年')

# ---------- 负证机器复查 ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：三远各恰一/二/一（寄远无账）、占梦/新知/涼思全零
if _alltj.count('北斗') != 1:
    raise SystemExit(f'通鉴「北斗」不再恰一（实 {_alltj.count("北斗")}）——三远两界判决须重估')
if _alltj.count('南北斗') != 1 or _alltj.count('祭南北斗') != 1:
    raise SystemExit('通鉴「南北斗/祭南北斗」不再恰一——王皇后咒术案闭域须重估')
if _alltj.count('南陵') != 2:
    raise SystemExit(f'通鉴「南陵」不再恰二（实 {_alltj.count("南陵")}）——南陵两界（屯兵/败军）判决须重估')
_nl = sorted(int(n[3:6]) for n, t in _tjf.items() if '南陵' in t)
if _nl != [221, 253]:
    raise SystemExit(f'通鉴「南陵」闭域分布变了（实 {_nl}）——两处落主档扫须重估')
if _alltj.count('天涯') != 1:
    raise SystemExit('通鉴「天涯」不再恰一——回鹘坟墓案闭域须重估')
for _w, _n in (('占夢', 0), ('數夢', 0), ('新知', 0), ('涼思', 0), ('波平', 0), ('露滿', 0),
               ('蟬休', 0), ('倚立', 0), ('永懷', 0), ('寓使', 0), ('客去', 0), ('移時寄', 0),
               ('占夢數', 0), ('有新知', 0), ('當此節', 0)):
    if _alltj.count(_w) != _n:
        raise SystemExit(f'通鉴「{_w}」不再恰{_n}——诗面语侧闭域档扫须重估')
# 「疑誤」通鉴恰一（247「欲以疑誤官軍」——史的疑误是军间诈术；诗作「疑誤有新知」）
if _alltj.count('疑誤') != 1 or _tjf.get('tj-247.txt', '').count('疑誤') != 1:
    raise SystemExit('通鉴「疑誤」不再恰一恰在 247（军间诈术案）——疑誤两界档扫须重估')
    if _alltj.count(_w) != _n:
        raise SystemExit(f'通鉴「{_w}」不再恰{_n}——诗面语侧闭域档扫须重估')
# ② 全唐诗：本篇八句恰一（只在540——与 V073 八句全零恰成两极）；邻块并置各恰一
for _ln in ('客去波平檻，蟬休露滿枝。', '永懷當此節，倚立自移時。',
            '北斗兼春遠，南陵寓使遲。', '天涯占夢數，疑誤有新知。'):
    if _allq.count(_ln) != 1:
        raise SystemExit(f'全唐詩「{_ln[:8]}…」不再恰一（实 {_allq.count(_ln)}）——跨源零分歧面须重估')
if _allq.count('==涼思==') != 1:
    raise SystemExit('全唐詩「==涼思==」锚不再全库唯一——旧式裸锚断言失效')
if V540.count('==涼思==') != 1 or V540.count('==江上==') != 1 or V540.count('==鸞鳳==') != 1:
    raise SystemExit('卷540 涼思/江上/鸞鳳锚结构变了（并置断言失效）')
if V540.count('吾道豈淹留。\n</poem>\n\n==涼思==') != 1:
    raise SystemExit('江上块与涼思块不再直接相接——卷页并置（上压）判决须重估')
if V540.count('疑誤有新知。\n</poem>\n\n==鸞鳳==') != 1:
    raise SystemExit('涼思块与鸞鳳块不再直接相接——卷页并置（下接）断言须重估')
# ③ ws：五成第二枚+零标记；双转录第三次；VH1 22页闭域；notes 二连无↑；分类四行含詠懷詩三页
for _w in ('{{另', '{{別', '{{*', '<ref>', '{{reflist}}', '↑', '{{clr}}'):
    if WS.count(_w) != 0:
        raise SystemExit(f'ws 页「{_w}」不再全零（零标记×五成/无回指/无clr断言失效）')
if WS.count('{{Textquality|50%}}') != 1 or WS.count('{{Textquality|100%}}') != 0:
    raise SystemExit('ws 页五成级计数变了（五成第二枚断言失效）')
if WS.count('客去波平檻') != 2 or WS.count('疑誤有新知') != 2:
    raise SystemExit('ws 页 Vtext/poem 双转录结构变了（首末句页内应各恰 2）')
if WS.count('{{VtextStart}}') != 8 or WS.count('{{VH1|涼思}}') != 1:
    raise SystemExit('ws Vtext/VH1 排版结构变了')
_wsf = {p.name: p.read_text(encoding='utf-8')
        for p in sorted(pathlib.Path('/tmp/src-dl/ws-poems').glob('*.txt'))}
_vh1 = {n for n, t in _wsf.items() if '{{VH1|' in t}
if len(_vh1) != 22:
    raise SystemExit(f'ws {{VH1|}} 页不再恰 22（实 {len(_vh1)}）——排版模板闭域档扫须重估')
_yh = {n for n, t in _wsf.items() if '[[Category:詠懷詩]]' in t}
if _yh != {'夜雨寄北.txt', '涼思.txt', '登岳陽樓__杜甫_.txt'}:
    raise SystemExit(f'詠懷詩 类目页不再恰三（实 {sorted(_yh)}）——类目闭域档扫须重估')
if WS.count('[[Category:李商隱]]') != 1 or WS.count('[[Category:唐诗]]') != 1:
    raise SystemExit('ws 分类四行含作者分类形态变了')
if WS.count('| times') != 0 or WS.count('| type') != 0 or WS.count('| from') != 0:
    raise SystemExit('ws 无 times/type/from 字段形态变了')
# ④ 旧传李商隐段负证（段内寄面题字全零——「寄远」的人传里无一寄书字；思恰一恰在文思）
for _w in ('客', '波', '檻', '蟬', '露', '枝', '永', '節', '倚', '立', '移', '北', '斗',
           '春', '遠', '陵', '寓', '遲', '涯', '占', '夢', '數', '疑', '誤', '知', '寄',
           '書', '信', '涼'):
    if _seg_j.count(_w) != 0:
        raise SystemExit(f'「{_w}」落在旧传李商隐段——传段寄面题字零判决失效，须重读原文')
if _seg_j.count('思') != 1 or '文思清丽' not in _seg_j:
    raise SystemExit('旧传段「思」不再恰一恰在文思——思字谱须重估')

# ---------- 四层背景正文 ----------
BG = {
    'bg-032-scene': (
        '**诗的第一笔是一场刚送客的空**：「客去波平檻，蟬休露滿枝」——人走了，水波正好平到'
        '栏杆，蝉声停了、露水满在枝头：整首凉思从「声音停了」开始。**ws 页是五成页第二次'
        '在场**（{{Textquality|50%}}——V073 首见、本篇成系列第二枚；已落李商隱诗页 TQ 谱'
        '档扫机器断言）；**零标记页×五成第二枚标本**（{{另}}/{{別}}/{{*}}/<ref>/{{reflist}}'
        '全零——评级与标记多寡正交）。**双转录句读分工第三次在场**（Vtext 行全裸、poem 块'
        '全句读——V072 首见、V073 第二次，本篇成连续系列）。**跨源零分歧面首见**：V018 给'
        '此诗立正文用的是卷540 卷页面（vol-raw），本快照 ws 诗页 poem 块与之逐字同面——'
        '同一首诗的选本页与卷页两个独立见证面在此逐字相合（生成时八行双向断言；与 V072'
        '异体分工、V073 八句全唐诗零恰成两极）。正文第二引上限用满第二十二例（V018 句读式'
        '一引在先，本迁移引 ws 页 poem 块原样面——同面各从其录，V018 句读式引文零重开'
        '硬断言），此后此诗正文关闭。',
     ),
    'bg-032-city': (
        '**这座城的档案员把两首诗钉成上下页**：卷540 里《江上》块尾句「吾道豈淹留」之后'
        '空一行直接接「==涼思==」锚、本篇块尾又直接接「==鸞鳳==」锚（机器断言各恰一——'
        '卷页并置第二次在场，V073 首见）：选本自己把「我这条路哪能留下」压在「托南陵的'
        '人送信迟迟」头上（读法声明）。**卷页是旧式裸名锚+正文内联**——「==涼思==」无'
        '消歧器、无「{{:}}」转引壳，八句直接内联锚下（V066 賈生旧式裸锚判例延展；与 V072/'
        'V073 的空壳转引恰成卷页见证面两极——内联 vs 空壳）；本篇八句在全唐诗语料恰一、'
        '恰在这一块（与 V073「八句全库零、诗只活在诗页」恰成两极——这首诗同时活在诗页与'
        '卷页两处）。ws 页 notes 是**二连无↑**（{{Textquality|50%}}{{唐詩三百首}}，无底本'
        '回指——V073 三连带↑/V066 无评级二连/本篇五成二连无↑：notes 排序谱再补一态）；'
        '分类**四行**含作者分类与「詠懷詩」类目（詠懷詩全库恰三页：夜雨寄北/涼思/登岳陽樓'
        '机器断言——类目行数与类目本身都是形态；分类行系整理者动作非史料声明、不升格，'
        'V048 判例）。**本迁移新建一枚 source**：source-ws-t300-032（V018 立正文时用卷页、'
        '选本页当时未建源——卷页与诗页是两个独立见证面，V066 賈生判例同款）；'
        'source-quantangshi-540 第三次复用（V018/V066 已引）。',
     ),
    'bg-032-world': (
        '**诗里有三处远，通鉴里这三处没有一个在寄信**（同字两界第十九形态·寄远形态首见）：'
        '「北斗兼春遠」——通鉴「北斗」恰一：開元十二年（甲子，七二四）王皇后使其兄太子少保'
        '守一「**使僧明悟為後祭南北斗**，剖霹靂木，書天地字及上名，合而佩之」祝曰「佩此'
        '有子」——史的北斗是求子的符咒（事觉后废为庶人，守一赐死）；诗的北斗是连着春天'
        '一起远去的那颗星。「南陵寓使遲」——通鉴「南陵」恰二（221/253 闭域，机器断言）：'
        '上元元年（庚子，七六〇）「**傅子昂屯南陵**，将下江州，徇江西」（史'
        '的南陵是军队的驻地）；乾符五年（戊戌，八七八）黄巢攻宣州不克、「**敗於南陵**」'
        '（史的南陵是败军的方向）——诗的南陵是一封迟迟寄不出的信（「寓使」=托寓居的人'
        '捎信，通鉴连「寓使」这个词都不识）。「天涯占夢數」——通鉴「天涯」恰一：會昌二年'
        '（壬戌，八四二）李德裕论回鹘「**累代可汗墳墓，隔在天涯**」——史的天涯是汗祖坟'
        '的隔绝，诗的天涯是游子反复占梦的距离。**三远各有其账，寄信没有账**：「占夢」'
        '「新知」「涼思」通鉴全零（闭域档扫，机器断言）——史部连占梦这个动作都不记录；'
        '诗的三处远，一处都没落进任何人的账上（对照判决，非史实因果）。',
     ),
    'bg-032-person': (
        '**旧传这一段给了这个人一段没有信的生活**：「三年入朝，京兆尹卢弘正奏署掾曹，'
        '**令典笺奏**」——史部记他替人管笺奏（公文），全库查重恰零域首引（简化字录入照登'
        '原样，V016 locator 同款标注）；诗的「南陵寓使遲」是他自己要寄的那封信，传里只有'
        '他替官府管的公文。**段内寄面题字三十一项全零**（客/波/檻/蟬/露/枝/永/節/倚/立/'
        '移/北/斗/春/遠/陵/寓/遲/涯/占/夢/數/疑/誤/知/寄/書/信/涼+思谱外二字，机器断言）'
        '——**写寄远的人，传里无一寄字无一书字无一信字**（V068 无一仙字/V071 无一瑟字/'
        'V072 无一蝉字/V073 无一风雨字同款第五枚）；**段内「思」字恰一恰在「文思清丽」**'
        '（V072 在册零重开，机器断言）：史部给他的思在文章的清丽里，诗的「永懷當此節」'
        '不是（读法声明，非史实因果）。紧接着「明年，令狐绹作相，商隐屡启陈情，绹不之省」'
        '在册零重开（V066/V067）——诗里数着占梦的人，史书里是他屡次递信、不看的人是他'
        '想寄信的人；「寄远的人没有信」系读法声明。KNOWN 零如实记录（第卅例，audit'
        '反向断言）。',
     ),
}
# chunk D 正文值带尾逗号成单元素元组——归一为字符串（与 V072/V073 BG 同形）
BG = {k: (v[0] if isinstance(v, tuple) else v) for k, v in BG.items()}

BG_LINES = {'bg-032-scene': (1, 2), 'bg-032-city': (3, 4),
            'bg-032-world': (5, 6), 'bg-032-person': (7, 8)}
BG_AUDIENCE = {'bg-032-scene': 'PRIMARY', 'bg-032-city': 'JUNIOR',
               'bg-032-world': 'SENIOR', 'bg-032-person': 'JUNIOR'}
BG_TITLES = {
    'bg-032-scene': '眼前：客去之后，声停之夜',
    'bg-032-city': '这座城：江上压在涼思头上',
    'bg-032-world': '这个天下：三远各有账，寄信没有账',
    'bg-032-person': '这个人：典笺奏的人没有自己的信',
}
CLAIMS = {
    'claim-bg-032-scene': ('FACT', 'LIKELY',
        '凉思八句取 ws 选本页 poem 块原样面入引（V018 句读式「客去波平檻，……疑誤有新知。」'
        '一引在先，零重开硬断言——正文第二引第二十二例）；双转录句读分工第三次在场；'
        '跨源零分歧面首见（ws 面≡V018 取自 540 之面，八行双向断言）；五成页第二次+零标记页'
        '（评级与标记正交第二枚标本）'),
    'claim-bg-032-city': ('FACT', 'LIKELY',
        '卷540 旧式裸名锚「==涼思==」+八句正文内联（V066 判例延展，与空壳转引成两极）；'
        '卷页并置第二次在场（江上尾句吾道豈淹留接涼思锚、涼思块尾接鸞鳳锚各恰一——并置系'
        '选本版式事实，「上压」读法声明）；ws notes 二连无↑+分类四行含詠懷詩（类目全库恰三页'
        '闭域，V048 不升格）；新建 source-ws-t300-032 一枚（V066 判例同款），540 第三次复用'),
    'claim-bg-032-world': ('FACT', 'LIKELY',
        '通鉴北斗恰一（開元十二年王皇后祭南北斗咒）/南陵恰二（上元元年傅子昂屯/乾符五年'
        '黄巢敗於）/天涯恰一（會昌二年回鹘坟墓隔在天涯）闭域入引；占夢/新知/涼思全零；'
        '三远各有其账、寄信没有账（同字两界第十九形态·寄远形态首见，对照判决非史实因果）'),
    'claim-bg-032-person': ('FACT', 'LIKELY',
        '旧传（简化字段）首引一段「三年入朝，京兆尹卢弘正奏署掾曹，令典笺奏。」（恰零域'
        '首引）；段内寄面题字三十一项全零——写寄远的人传里无一寄字书字信字（系列第五枚）；'
        '段内思字恰一恰在文思清丽（V072 在册零重开）；「寄远的人没有信」读法声明'),
}
CITATIONS = [
    ('claim-bg-032-scene', 'source-ws-t300-032',
     '页面 涼思（《唐詩三百首》第 32 首选本页，页题裸名；title+author+VH1 模板锚+署名行'
     '+Vtext 八行裸片+poem 存原样块以「……」相连——poem 带句读而 Vtext 全裸（双转录句读'
     '分工第三次成连续系列）；**五成页第二次在场**（V073 首见）+零标记页第二枚标本'
     '（{{另}}/{{別}}/{{*}}/<ref>/{{reflist}} 全零——评级与标记正交）；**跨源零分歧面首见**'
     '（V018 文本行取自卷540（vol-raw）与本快照 poem 块逐字同面——两独立见证面逐字相合，'
     '八行双向断言）；正文第二引第二十二例（V018 句读式一引在先不重开）',
     join(WS_TITLE, WS_AUTHOR, WS_VH1, WS_VSIG, WS_VT1, WS_POEM)),
    ('claim-bg-032-city', 'source-quantangshi-540',
     '卷五百四十·李商隱《涼思》块（旧式裸名锚「==涼思==」+八句正文内联——V066 賈生旧式'
     '裸锚判例延展，与 V072/V073 空壳转引恰成卷页见证面两极；锚全唐诗唯一机器断言）；'
     '**卷页并置第二次在场**（V073 首见）：《江上》块尾句「吾道豈淹留」与本篇锚直接相接'
     '恰一+本篇块尾与《鸞鳳》锚直接相接恰一（选本版式事实——「上压」系读法声明）；'
     '八句全唐诗语料各恰一恰在此块（与 V073 全零成两极）；source-quantangshi-540 '
     '第三次复用零新建）',
     join(V540_PREV, V540_BLOCK, V540_NEXT)),
    ('claim-bg-032-city', 'source-ws-t300-032',
     '页面 涼思（notes 二连一行整值入引（{{Textquality|50%}} 居首+{{唐詩三百首}}，**无↑'
     '底本回指**——排序谱再补一态：V073 三连带↑/V066 无评级/本篇五成二连无↑）+页尾分类'
     '四行（简繁并立含 [[Category:李商隱]] 与 [[Category:詠懷詩]]——**詠懷詩类目全库恰三页**：'
     '夜雨寄北/涼思/登岳陽樓机器断言；分类行系整理者分类动作：非史料声明、不升格，'
     'V048 判例）；**新建 source-ws-t300-032 一枚**（V018 立正文用卷页、选本页当时未建源'
     '——卷页与诗页是两个独立见证面，V066 賈生判例同款）',
     join(WS_NOTE2, WS_CAT4)),
    ('claim-bg-032-world', 'source-zizhi-tongjian-events',
     '卷二百一十二·開元十二年（甲子，七二四）王皇后案「使僧明悟為後祭南北斗，剖霹靂木，'
     '書天地字及上名，合而佩之」（**史的北斗是求子符咒**）……卷二百二十一·上元元年'
     '（庚子，七六〇）「傅子昂屯南陵，将下江州，徇江西」（**史的南陵是屯兵驻地**）……'
     '卷二百五十三·乾符五年（戊戌，八七八）黄巢「敗於南陵」（**史的南陵是败军方向**）……'
     '卷二百四十六·會昌二年（壬戌，八四二）李德裕论回鹘「累代可汗墳墓，隔在天涯」（'
     '**史的天涯是汗祖坟隔绝**）；通鉴北斗恰一/南陵恰二（221/253 闭域）/天涯恰一/'
     '占夢/新知/涼思全零（机器断言）——四段逐字入引为三远两界判决证据）',
     join(TJ_DB, TJ_NL1, TJ_NL2, TJ_TY)),
    ('claim-bg-032-person', 'source-jiutangshu-wenyuan',
     '舊唐書卷一九〇下·李商隱（**简化字录入**照登原样，V016 locator 同款标注）「三年入朝，'
     '京兆尹卢弘正奏署掾曹，令典笺奏。」段（全库查重恰零域首引；传区间归属机器断言；'
     '**段内寄面题字三十一项全零**（客/波/檻/蟬/露/枝/永/節/倚/立/移/北/斗/春/遠/陵/寓/'
     '遲/涯/占/夢/數/疑/誤/知/寄/書/信/涼——**写寄远的人传里无一寄字书字信字**，系列第五枚）；'
     '**段内思字恰一恰在「文思清丽」**（V072 在册零重开，机器断言）——史部给他的思在'
     '文章清丽里，诗的永懷不是（读法声明）；V016/V066–V073 在册句零重开）',
     JTS_P),
]
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 55 首·八句五律 2/2/2/2）；史实句均有逐字引证；'
                 '系年第四十九次判决（题证系列第卅七状·三远各有账寄信无账）'
                 '「诗的三处远，通鉴里各有一本账，没有一本是寄信的」——'
                 '同字两界第十九形态·寄远形态首见：北斗恰一（開元十二年祭南北斗咒）/'
                 '南陵恰二（屯兵/败军）/天涯恰一（回鹘坟墓）闭域入引；占夢/新知/涼思全零；'
                 '跨源零分歧面首见（选本页≡卷页八行逐字同面，双向断言）+五成页第二次+零标记'
                 '正交第二枚；旧式裸锚+正文内联（与空壳转引成两极）；卷页并置第二次在场'
                 '（江上「吾道豈淹留」压「南陵寓迟」头上——读法声明）；新建 ws 源一枚'
                 '（V066 判例终结零新源五连）+540 第三次复用；写寄远的人传里无一寄字'
                 '（系列第五枚）+思恰一恰在文思（V072 在册）；正文第二引第二十二例零重开；'
                 'KNOWN 零如实记录第卅例（audit 反向断言）；判例关键语零入引文。' for k in BG}


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
    A("""-- V074：李商隱《涼思》(work-t300-032) 四层背景（阶段 D 第 55 首·寄远两界）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V026、V033、V035、V039、V048、V053、V057、
--       V058、V059、V060、V061、V062、V063、V064、V065、V066、V067、V068、V069、V070、
--       V071、V072、V073 已执行
--       （work-t300-032 与其 text-work-t300-032-ws（version_code=vol-raw——V018 立此诗正文
--       用的是卷540 卷页面，八行带句读，与本快照 ws 诗页 poem 块逐字同面零分歧——跨源零分歧
--       面首见）与其源 source-quantangshi-540（V018 已立的卷540 卷页源，V018/V066 已引，
--       本迁移第三次复用）都是 V018 的行；**source-ws-t300-032 是本迁移新建的选本页源**
--       （V066 賈生判例同款：卷页与诗页是两个独立见证面，引诗页非新源不能承载）；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       source-jiutangshu-wenyuan 是 V016 已立的旧唐书文苑传源（李商隐传在此，简化字录入）；
--       判例在册句（义山/开成二年/岭表/三十六体/未几病卒/大中末/仲郢坐/还郑州 V016、
--       绹不之省/坎壈终身/令狐绹作相 V066/V067、以所业文干之/下笔不能自休 V067、恃才诡激/
--       为当涂者所薄 V068、俄而茂元卒/检校水部员外郎 V070、文思清丽/庭筠过之 V072、
--       复以文章干襜/府罢入朝 V073、北斗七星高（西鄙人）/憐君何事到天涯（賈誼宅）/
--       客去波平檻句读式全引 V018）只对照不重开。
--       **本迁移新建 source 恰一枚（零新源连续五首在此正当终结）——
--       audit 断言本文件恰一枚 poetry_source INSERT（source-ws-t300-032）、回滚恰删此一枚。**
--
-- 数据源（可复现）：emit_v074.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/涼思.txt（五成页第二次+零标记页（正交第二枚标本）+VH1 模板锚（全库恰22页闭域）+
--   Vtext 裸/poem 句读双转录分工第三次+notes 二连无↑（排序谱再补一态）+分类四行含詠懷詩
--   （全库恰三页闭域）+无 times/type/from/无 {{clr}}/无↑）、
--   全唐詩卷540（旧式裸名锚「==涼思==」全库唯一+八句正文内联（与 V072/V073 空壳转引成两极）+
--   江上块与涼思块直接相接恰一+涼思块与鸞鳳块直接相接恰一（卷页并置第二次在场））、
--   舊唐書卷190下（李商隐段首引一段+段内寄面题字三十一项全零+思恰一恰在文思清丽+段边界断言）、
--   通鑑卷212/221/253/246（三远四段逐字入引+年标题窗口：開元十二年七二四/上元元年七六〇/
--   乾符五年八七八/會昌二年八四二）+
--   通鑑 75 卷负证计数扫描（北斗恰一+南北斗/祭南北斗恰一+南陵恰二闭域221/253+天涯恰一+
--   占夢/數夢/新知/涼思/波平/露滿/蟬休/倚立/永懷/寓使/客去/疑誤全零）+
--   既有迁移引文域逐句查重——传区间归属、二引/零重开/首引零域前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 background_line（八句五律 **2/2/2/2 顺次**：scene→1,2 city→3,4 world→5,6 person→7,8，
--   绑 text-work-t300-032-ws 的 8 行）+ 1 枚新建 source（source-ws-t300-032）+
--   不碰 poetry_text_line。
-- 不做：**不新建第二枚 source**；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「诗的三处远，通鉴各有一本账，没有一本是寄信的」）：
--   * 「三远两界」「寄远形态首见」系通鉴四段逐字入引支撑的对照判决，非史实因果——通鉴不记这首诗；
--     亦不考本诗系年（编年诸说一律不采信不铸造）；
--   * 「江上吾道豈淹留压在南陵寓迟头上」「寄远的人没有信」标明读法声明；
--   * 開元十二年北斗案主角是王皇后/王守一/僧明悟，与诗作者无涉——只作两界对照不作因果；
--   * 正文第二引上限用满：V018 句读式一引在先，本迁移引 ws 页 poem 块存原样面——
--     同面各从其录，V018 句读式引文不重开（生成时硬断言），此后此诗正文关闭；
--   * 「旧式裸锚内联」「卷页并置」「五成第二次」「VH1 22页闭域」均照登不判；
--   * 分类四行与詠懷詩类目系整理者动作：非史料声明、不升格，V048 判例；
--   * KNOWN 零如实记录（第卅例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * V011/V016/V018/V026/V033/V035/V039/V053/V063/V066–V073 已引诸句只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 73，不含 74
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-032-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-032','source-quantangshi-540');
--    -- 一行（540 系 V018 所立；ws 页源本迁移新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-032-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-032-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-032';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-032-%';  -- 四行全 LIKELY
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-032';   -- 恰 1（本迁移所立）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-032'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-032';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-032-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V074_rollback.sql（按 id 全枚举删除；**source 只删一行**——
--   source-ws-t300-032 是本迁移新建的选本页源（恰一枚，审计断言）按 id 删除；
--   source-quantangshi-540 是 V018 所立的卷540 卷页源（本迁移复用），绝不删；
--   work-t300-032 本体与其 text_line 8 行都是 V018 的行，绝不删）
START TRANSACTION;""")

    A('\n-- ---------- 0. 新建选本页源一枚（V066 賈生判例同款） ----------')
    src = [{'id': 'source-ws-t300-032', 'title': '维基文库《唐詩三百首》页面：涼思',
            'author': None, 'edition': '全唐詩',
            'url': 'https://zh.wikisource.org/wiki/涼思',
            'rights_note': '维基文库录入本，公有领域古籍。本行由 emit_v074.py 对 /tmp/src-dl 快照逐字定位。本诗 V018 立正文时用的是《全唐詩》卷540 卷页（source-quantangshi-540，version_code vol-raw），此《唐詩三百首》选本页当时未建源——卷页与诗页是两个独立见证面（卷页锚点归属 vs 选本页 header 署名/底注/分类），本迁移引诗页非新源不能承载。页面 {{Textquality|50%}} 五成评级+零异文标记（正交标本）；页内 Vtext/poem 双转录并存（Vtext 全裸/poem 句读）；notes 二连无底本回指；分类四行含简体「唐诗」与繁体「唐詩三百首」同页混排+「詠懷詩」类目（照登）。核验状态保持 PENDING。',
            'verification_status': 'PENDING', 'source_kind': 'POETRY_COLLECTION',
            'reliability': 'HIGH'}]
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            src, 'x.id = t.id'))

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
    brows = [{'id': k, 'work_id': 'work-t300-032',
              'layer': {'bg-032-scene': 'SCENE', 'bg-032-city': 'CITY',
                        'bg-032-world': 'WORLD', 'bg-032-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-032-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 74, 'Li Shang-yin''s Cool Thought (work-t300-032) background layers (stage-D poem 55, eight-line regulated verse 2/2/2/2): dating verdict forty-nine, thirty-seventh shape of the title-evidence series -- the poem holds three distances; the histories keep a ledger for each, and none of them is a letter. Same-character-two-realms, nineteenth shape: the long-distance (jiyuan) shape, first seen. Beidou appears exactly once in the Tongjian (Kaiyuan 12, jiazi, 724: deposed Empress Wang had her brother Wang Shouyi ask the monk Mingwu to sacrifice to the Northern and Southern Dipoles, split thunderstruck wood, write the characters of Heaven and Earth plus her name, wear the bundle, and pray "wearing this I shall have a son; make me like the Empress Wu" -- the history''s Dipper is a barren woman''s spell, exposed; she was deposed to commoner status and Shouyi was executed on the road; the poem''s Dipper is a star receding together with spring). Nanling appears exactly twice (closed set 221/253, machine-asserted): Shangyuan 1, gengzi, 760, "Fu Zi''ang encamped at Nanling, about to move down on Jiangzhou" (the history''s Nanling is a troop camp); Qianfu 5, wuxu, 878, Huang Chao "defeated at Nanling" (the history''s Nanling is the direction of a routed army); the poem''s Nanling is a letter that never arrives -- the Tongjian does not even know the word yushi (a lodged courier). Tianya appears exactly once (Huichang 2, renxu, 842, Li Deyu on the Uyghurs: "the tombs of their khans, generation upon generation, lie severed at the sky''s edge" -- the history''s sky''s-edge is ancestral graves; the poem''s sky''s-edge is distance for a dream-diviner''s bed). Zhanmeng (dream divination), xinzhi (new acquaintances), liangsi (cool thought) all score zero in the Tongjian (machine-asserted): the histories do not record the very act of counting dream-omens; the poem''s three distances land in no ledger. Cross-source zero-divergence face, first seen: V018 stored this poem''s eight lines from the juan-540 anthology page (vol-raw), and this snapshot''s wiki source-page poem block matches line for line -- the two independent witnesses (anthology page and source page) agree verbatim (generator asserts both directions; the mirror of V072''s variant division and V073''s zero-across-Quan-Tangshi face: here the eight lines score exactly one each in the Quan Tangshi, inside the juan-540 inline block). The 540 page shows the old-style bare anchor "==涼思==" with the poem inlined under it (extending V066''s bare-anchor precedent; the opposite pole from V072/V073''s empty transclusion shells). Page-placement, second appearance (first in V073): the Jiangshang block''s last line "how could my way be long detained" sits directly above the Liangsi anchor, and the Liangsi block sits directly above the Luanfeng anchor (each exactly one join, machine-asserted; the reading "the previous poem''s closing line becomes the next poem''s footnote" is declared as reading, not fact). The ws page: 50-percent grade for the second time (V073 first), zero-mark page (second orthogonal specimen), {{VH1}} layout template (closed set: exactly 22 pages corpus-wide), notes two-token row without the back-reference (notes ordering, a further state), four category lines including 詠懷詩 (exactly three pages corpus-wide: Ye Yu Ji Bei, Liangsi, Deng Yuelou -- machine-asserted; editorial, not a source claim, not upgraded, V048 precedent). Double transcription division of labor, third appearance, a continuous series (naked Vtext lines / punctuated poem block). NEW SOURCE, exactly one: source-ws-t300-032 (V066 precedent -- V018 registered this poem''s text from the anthology page; the source-page witness had no source row; the anthology page and the source page are two independent witnesses), ending the five-poem zero-new-source streak legitimately; the 540 source at its third reuse. Body use-ceiling, twenty-second instance: V018''s punctuated excerpt stands first and is never re-opened (hard assertion); the body is now closed. PERSON first-cites one zero-domain simplified JTS passage -- "in the third year he entered court; the prefect of Jingzhao, Lu Hongzheng, memorialized to seat him in the adjutant''s office, ordering him to keep charge of documents and memorials" -- the histories record him drafting other men''s letters and record no letter of his own; the biography segment holds none of the thirty-one letter-side graphs (qi/ji/shu/xin and every title-side graph -- the man who wrote of sending far leaves no send-graph, no letter-graph in his biography, fifth of the series after V068/V071/V072/V073); the single si (thought) graph inside the segment is exactly the one inside "his writing''s thought is clean and beautiful" (closed in V072, never reopened): the thought the histories grant him lives in his prose style, not in "forever cherishing, facing this season" (declared as reading, not fact). KNOWN zero honestly recorded (thirtieth instance, audit reverse-asserts); closed precedent keywords (V018''s Beidou qixing gao and Liangsi punctuated full quote, V018''s tianya from the Jia Yi house poem, V067/V072/V073''s biography sentences, V070/V066/V016 lines) stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 74);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V074 精确回滚：只删 V074 插入的行（id 全枚举）。source 只删一行：',
         '-- source-ws-t300-032 是本迁移新建的选本页源（恰一枚，审计断言）——按 id 删除；',
         '-- source-quantangshi-540 是 V018 已立的卷540 卷页源（本迁移复用），绝不删；',
         '-- work-t300-032 本体、其 text_line 8 行都是 V018 的行，绝不删；',
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
    L.append('DELETE FROM poetry_source WHERE id = ' + sql_s('source-ws-t300-032') + ';')
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 74;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V074')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

def _domain_src(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V074')
                   and needle in f.read_text(encoding='utf-8')})

for _premise, _needle, _want in (
        ('本诗首句(V018 句读式一引)', '客去波平檻', ['V018']),
        ('本诗末句(V018 句读式收尾)', '疑誤有新知', ['V018']),
        ('V018 句读式全引不重开', '客去波平檻，……疑誤有新知。', ['V018']),
        ('北斗字面在册(V018 西鄙人先占——照登不重开)', '北斗七星高', ['V018']),
        ('天涯字面在册(V018 賈誼宅先占——照登不重开)', '憐君何事到天涯', ['V018']),
        ('卷页源二次在册(本迁移第三次复用)', 'source-quantangshi-540', ['V018', 'V066']),
        ('V066 判例在册(卷页诗页两见证面新建源判例——V067/V068 rights_note 亦及之)',
         'source-ws-t300-031', ['V066', 'V067', 'V068']),
        ('旧传在册句零重开谱(复以文章干襜)', '复以文章干襜', ['V073']),
        ('旧传在册句零重开谱(府罢入朝)', '府罢入朝', ['V073']),
        ('旧传在册句零重开谱(文思清丽)', '文思清丽', ['V072']),
        ('旧传在册句零重开谱(庭筠过之)', '庭筠过之', ['V072']),
        ('旧传在册句零重开谱(以所业文干之)', '以所业文干之', ['V067']),
        ('旧传在册句零重开谱(令狐绹作相)', '令狐绹作相', ['V066']),
        ('V016 在册诸句', '商隐随亚在岭表累载', ['V016']),
        ('V070 詠懷詩类目首见在册(照登不重开)', '詠懷詩', ['V070'])):
    _prev = _domain_src(_needle) if (_needle.startswith('source-')) else _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
if _domain_src('source-ws-t300-032'):
    raise SystemExit('source-ws-t300-032 已存在于既往迁移——新建源前提失效')
for _first, _needle in (('VH1 模板锚', '{{VH1|'),
                        ('裸锚内联块', '==涼思==\n<poem>'),
                        ('江上并置', '吾道豈淹留。\n</poem>\n\n==涼思=='),
                        ('鸞鳳并置', '==鸞鳳=='),
                        ('北斗咒术案', '祭南北斗'),
                        ('霹雳木', '剖霹靂木'),
                        ('傅子昂屯南陵', '傅子昂屯南陵'),
                        ('黄巢寇宣州', '黃巢寇宣州'),
                        ('黄巢败南陵', '敗於南陵'),
                        ('回鹘天涯', '累代可汗墳墓，隔在天涯'),
                        ('旧传典笺奏段', '三年入朝，京兆尹卢弘正奏署掾曹'),
                        ('令典笺奏', '令典笺奏'),
                        ('notes 二连整值', '{{Textquality|50%}}{{唐詩三百首}}\n'),
                        ('分类四行整值', '[[Category:唐詩三百首|李]]\n[[Category:詠懷詩]]'),
                        ('poem 存原样块', '客去波平檻，蟬休露滿枝。'),
                        ('Vtext 裸首行', '{{VtextStart}}客去波平檻{{VtextEnd}}')):
    if _domain(_needle):
        raise SystemExit(f'首引句「{_first}」既往域非零——须换句或降级')


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_VH1, WS_VSIG, WS_VT1, WS_POEM, WS_NOTE2, WS_CAT4,
              V540_BLOCK, V540_PREV, V540_NEXT, TJ_DB, TJ_NL1, TJ_NL2, TJ_TY, JTS_P]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # SCENE：裸/句读分工+跨源零分歧面必须逐字入引 + V018 句读式引文零重开
    scene_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-032-scene')
    if '{{VtextStart}}客去波平檻{{VtextEnd}}' not in scene_ws:
        bad.append('Vtext 裸行未入 SCENE 引文（双转录句读分工第三次照登硬卡）')
    if '客去波平檻，' not in scene_ws:
        bad.append('poem 句读面未入 SCENE 引文（句读分工硬卡）')
    if '{{Textquality|50%}}' not in next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-032-city' and s == 'source-ws-t300-032'):
        bad.append('五成页注记标记未入 CITY 诗页引文（五成第二次硬卡——notes 整值入引侧）')
    if '客去波平檻，……疑誤有新知。' in cited:
        bad.append('V018 句读式引文重开了——本迁移引 poem 原样面，句读式不重开')
    # CITY：旧式裸锚内联+并置必须在卷页引文内；notes/分类在诗页引文内
    city_q = next(ex for c, s, _, ex in CITATIONS if s == 'source-quantangshi-540')
    if '==涼思==\n<poem>' not in city_q:
        bad.append('旧式裸锚+正文内联未逐字入 CITY 卷页引文（V066 判例延展硬卡）')
    if '吾道豈淹留。\n</poem>\n\n==涼思==' not in city_q or '疑誤有新知。\n</poem>\n\n==鸞鳳==' not in city_q:
        bad.append('卷页并置两向未入 CITY 卷页引文（第二次在场硬卡）')
    c_loc = next(loc for c, s, loc, _ in CITATIONS if s == 'source-quantangshi-540')
    if '裸锚' not in c_loc or '内联' not in c_loc or '并置' not in c_loc:
        bad.append('CITY 卷页 locator 须含「裸锚/内联/并置」声明')
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-032-city' and s == 'source-ws-t300-032')
    if '{{Textquality|50%}}{{唐詩三百首}}' not in city_ws:
        bad.append('notes 二连整值未入 CITY 诗页引文（排序谱再补一态硬卡）')
    if '[[Category:詠懷詩]]' not in city_ws:
        bad.append('詠懷詩 类目未入 CITY 诗页引文（三页闭域硬卡）')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-032-city' and s == 'source-ws-t300-032'):
        bad.append('CITY 诗页 locator 须含「不升格」声明')
    # WORLD：四段史文必须在引文内；诗语零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-032-world')
    for tok in ('祭南北斗', '剖霹靂木', '傅子昂屯南陵', '敗於南陵', '隔在天涯', '累代可汗墳墓'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（四段必须入引）')
    for tok in ('客去', '波平', '露滿', '蟬休', '永懷', '倚立', '占夢', '疑誤', '涼思', '寓使'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文）')
    w_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-032-world')
    if '北斗' not in w_loc or '南陵' not in w_loc or '天涯' not in w_loc:
        bad.append('WORLD locator 须点出北斗/南陵/天涯（三远两界声明）')
    # PERSON：首引句必须在引文内+在册句零重开
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-032-person')
    for tok in ('三年入朝', '令典笺奏'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺首引要素「{tok}」（简化字段首引照登硬卡）')
    for tok in ('寄', '書', '信', '涼') :
        pass
    for tok in ('北斗七星高', '憐君何事到天涯', '客去波平檻，……疑誤有新知。', '复以文章干襜',
                '府罢入朝', '文思清丽', '庭筠过之', '以所业文干之', '令狐绹作相',
                '下笔不能自休', '绹不之省', '坎壈终身', '恃才诡激', '为当涂者所薄',
                '俄而茂元卒', '检校水部员外郎', '亚坐德裕党', '商隐随亚在岭表累载',
                '李商隐，字义山，怀州河内人。', '开成二年', '未几病卒', '大中末', '仲郢坐',
                '还郑州', '惟山陵使長而多髯', '次子綯有才器', '淒涼寶劍篇，……銷愁斗幾千。',
                '本以高難飽', '我亦舉家清', '初聞此語', '東拒滄海', '言與淚俱',
                '錦瑟無端五十', '君問歸期未有期', '灞原風雨定', '夜來風雨聲', '春眠不覺曉',
                '逢吉薦紳清直', '坐阿附貶南陽尉', '義不臣賊', '舉家西歸', '高難飽',
                '風雨', '{{:風雨 (李商隱)}}', '==[[風雨 (李商隱)|風雨]]==',
                '{{:蟬 (李商隱)}}', '{{:錦瑟}}', '↑ [[全唐詩/卷539#風雨'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    if BG_LINES != {'bg-032-scene': (1, 2), 'bg-032-city': (3, 4),
                    'bg-032-world': (5, 6), 'bg-032-person': (7, 8)}:
        bad.append('八句 background_line 须 2/2/2/2 顺次（V020 以来八句篇常规）')
    if len(re.findall(r"text-work-t300-032-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # 恰一枚新建 source（V066 判例终结零新源五连）
    ins_src = sql.count('INSERT INTO poetry_' + 'source')
    if ins_src != 1:
        bad.append(f'本迁移应恰新建一枚 source（V066 判例同款），实 {ins_src}')
    if sql.count("'source-ws-t300-032' AS id") != 1:
        bad.append('source-ws-t300-032 INSERT 应恰一枚')
    rb = build_rollback()
    if rb.count('DELETE FROM poetry_' + 'source') != 1 or sql_s('source-ws-t300-032') not in rb:
        bad.append('回滚应恰删一枚 source（source-ws-t300-032）')
    if 'DELETE FROM poetry_' + 'source' in sql:
        bad.append('正向迁移不得含 source 删除')
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V074 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V074 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-032' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V074 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-032' AS subject_id" in sql:
        bad.append('V074 的 claim 主语应全部是 bg-032-*，work-t300-032 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V074 不碰 poetry_text_line')
    body_all = ''.join(BG.values())
    if '寄远形态首见' not in body_all:
        bad.append('BG 须含「寄远形态首见」（同字两界第十九形态）声明')
    if '没有一个在寄信' not in body_all:
        bad.append('BG/WORLD 须含「三处远没有一个在寄信」判决')
    if '无一寄字' not in body_all:
        bad.append('BG/PERSON 须含「写寄远的人传里无一寄字」段级零证声明')
    if '跨源零分歧面首见' not in body_all:
        bad.append('BG/SCENE 须含「跨源零分歧面首见」声明')
    if '五成页第二次' not in body_all:
        bad.append('BG/SCENE 须含「五成页第二次在场」声明')
    if '新建一枚 source' not in body_all and '新建 source' not in body_all:
        bad.append('BG/CITY 须含「新建 source 一枚（V066 判例）」声明')
    if '卷页并置' not in body_all:
        bad.append('BG/CITY 须含「卷页并置第二次在场」声明')
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
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 74)' not in vblk:
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 16 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（旧传李商隐段一首引句，段界 ==弟 羲叟==）；'
              f'四处年标题窗口断言（開元十二年七二四/上元元年七六〇/乾符五年八七八/會昌二年八四二）；'
              f'负证机器复查五层（通鉴北斗恰一+南北斗祭南北斗恰一+南陵恰二闭域221,253+天涯恰一+'
              f'占夢/數夢/新知/涼思/波平/露滿/蟬休/倚立/永懷/寓使/客去全零+疑誤恰一恰在247/'
              f'全唐诗八句各恰一恰在540+==涼思==锚全库唯一+江上/鸞鳳并置各恰一+'
              f'ws 零标记+五成恰一+双转录首末句各恰二+VH1 恰22页+詠懷詩恰三页+无↑无clr无times/type/from/'
              f'旧传段寄面题字三十一项全零+思恰一恰在文思清丽，快照变动即中止）；'
              f'前提全库查重硬卡十五件+十六首引句零域断言+source-ws-t300-032 不存在断言；'
              f'SCENE 五成+裸面+句读面入引+V018 句读式引文零重开断言；CITY 裸锚/内联/并置硬卡；'
              f'CITY「不升格」硬卡；四段通鉴史文入引+诗语零混入断言；'
              f'PERSON 首引要素入引硬卡+V016/V018/V053/V066–V073 诸句零重开硬卡；'
              f'判例只引不重开断言（含 V018 北斗七星高/天涯/涼思句读式与 V073 干襜在内）；'
              f'八句 2/2/2/2 形制断言；零 KNOWN 反向断言；'
              f'**恰一枚新建 source 断言（INSERT 恰一+回滚恰删一枚 source-ws-t300-032）**——'
              f'V066 判例终结零新源五连；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
