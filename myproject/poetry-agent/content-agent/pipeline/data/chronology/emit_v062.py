#!/usr/bin/env python3
"""阶段 D 第 43 首：生成 V062——王維《酬張少府》(work-t300-063, V018 已立) 四层背景。

「为什么写」走到**同一首诗里两对字同时两界**（同字两界第七形态·双对首见；
V056 泪痕/V057 已矣/V058 琴·流水/V059 故鄉/V060 閉關/V061 王孫之后）：
**「題有官名，官名在史部只為監署；詩有長策解帶，長策在史部只經國是，
解帶在史部只急變須臾」**——

通鉴「張少府」全零：「少府」恰十二处（文件闭域+少府監恰七/少府少監恰四机器断言）
全是**官署与职事**（少府監、少府少監、送少府銷毀），**没有一个「某少府」式的人**——
题目里的友人，在史部只存在为一座衙门。「長策」恰七处（闭域断言），全是**国是**：
貞觀四年（庚寅，六三〇）安突厥「此**安邊之長策**也」、貞元十年（甲戌，七九四）
陸贄彈延齡「以**聚斂為長策**」——好的坏的策都是治国的策；诗的「自顧無長策」
是自查，答曰「没有」。「解帶」恰二处（闭域+双窗口）且**全引**：貞觀五年
（辛卯，六三一）執失思力「**脫巾解帶**，跪而固諫」、光啟二年（丙午，八八六）
杜讓能亂中奔鑾「**解帶**繫頸而乘之」——史部的解帶是**最急的瞬間**（跪諫、
追鑾）；诗的「松風吹解帶」是**最閑的瞬間**（松風、山月）——同字两界，
**急閑异位**（audit 正入两语+负向零混入）。

**詩的問答在兩界之外**：「窮通」「舊林」**通鉴+全唐詩双双全零**（穷通之理
在史与集里都无处问），所以诗只能「漁歌入浦深」作答——「漁歌」全唐詩恰二处
（vol524/vol525 他人句在册零入引，机器断言），通鉴全零。

CITY 层：**三种消歧形态至此齐备**——V059 作者消歧「(王維)」、V061 首句消歧
「(山中相送罷)」、本篇**裸名锚**「==[[酬張少府]]==」（无同名诗则无消歧器）；
卷126 锚+桩恰 2（闭域）；底注全锚「卷126#酬張少府|」（同 V058–V061 全锚形态）；
{{唐詩三百首}} 标记在本页（与 V061 送別页无标记互为有无）；
source-quantangshi-126 系 V035/V039/V052/V054/V060 已立、**第六次复用零新源**。

PERSON 层首引：新传「**議者不之罪。**」（全库查重既往零入引）——那道换官的表
（願歸所任官 V040 在册零重开）史家只留四字考语：**不置可否**；而**两传全文
「靜」字全零**（机器断言——写「晚年唯好靜」的人，两篇传里没有靜字；
「長策」「解帶」「漁歌」「少府」「窮通」「舊林」两传亦全零）——
**诗面字不进传**系列第二例（V061 送字全零→本篇靜字全零）。

八句五律 2/2/2/2 第四次（V054/V058/V060）；正文第二引上限用满第十例
（V018 归一形一引在先，查重针「晚年唯好靜」「漁歌入浦深」各恰一处）。

用法: python3 -I emit_v062.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/酬張少府.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
V126 = pathlib.Path('/tmp/src-dl/quantangshi/vol126.txt').read_text(encoding='utf-8')
TJ193 = pathlib.Path('/tmp/src-dl/tongjian/tj-193.txt').read_text(encoding='utf-8')
TJ235 = pathlib.Path('/tmp/src-dl/tongjian/tj-235.txt').read_text(encoding='utf-8')
TJ256 = pathlib.Path('/tmp/src-dl/tongjian/tj-256.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 酬張少府', '| title    = 酬張少府', 'ws header title(酬答体题面)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS,
                        '| notes    = {{Textquality|75%}}↑ [[全唐詩/卷126#酬張少府|全唐詩·卷126]]',
                        '全唐詩·卷126]]',
                        'ws 页底注(75%+非空全锚——同 V058-V061 全锚形态)')
WS_CAT = slice_between(WS, '[[Category:五言律詩]]', '[[Category:五言律詩]]', 'ws 分类行(五言律詩——整理者分类;V048 分类行判例)')
WS_L1 = slice_between(WS, '晚年唯好靜，萬事不關心。', '萬事不關心。', 'ws第1联(晚年唯好靜——诗眼静字两传全零)')
WS_L2 = slice_between(WS, '自顧無長策，空知返舊林。', '空知返舊林。', 'ws第2联(长策自查答曰无——史部长策只经国是)')
WS_L3 = slice_between(WS, '松風吹解帶，山月照彈琴。', '山月照彈琴。', 'ws第3联(解带最闲——史部解带最急)')
WS_L4 = slice_between(WS, '{{另|君|若}}問窮通理', '漁歌入浦深。', 'ws第4联(穷通无问处渔歌作答——君/若异文照登)')
XTS_Y = slice_between(XTS, '議者不之罪。', '議者不之罪。',
                      '新传议者不之罪(从未入引,PERSON 首引——换官表的史家考语:不置可否)')
TJ_CC1 = slice_between(TJ193, '此安邊之長策也。', '此安邊之長策也。',
                       '通鉴贞观四年安突厥段(长策史部一处——安边国是;窗口断言)')
TJ_CC2 = slice_between(TJ235, '延齡以聚斂為長策', '以詭妄為嘉謀',
                       '通鉴贞元十年陆贄弹延龄段(长策国是反面——聚敛亦策;窗口断言)')
TJ_XD1 = slice_between(TJ193, '脫巾解帶', '跪而固諫',
                       '通鉴贞观五年执失思力段(解带史部一处——跪谏之急;窗口断言)')
TJ_XD2 = slice_between(TJ256, '解帶繫頸而乘之', '解帶繫頸而乘之',
                       '通鉴光启二年杜让能奔銮段(解带史部二处——追銮之急;窗口断言)')
Q126 = slice_between(V126, '==[[酬張少府]]==', '==[[酬張少府]]==',
                     '卷126 本篇篇题锚点(裸名锚——无同名诗则无消歧器,三形态至此齐备)')
Q126_S = slice_between(V126, '{{:酬張少府}}', '{{:酬張少府}}', '卷126 本篇转引桩')

# ---------- 传区间归属复验（V036 立规） ----------
_xa = XTS.find('==王維==')
_xm = re.search(r'\n==[^=\n]{1,10}==', XTS[_xa + 8:])
_seg_x = XTS[_xa:_xa + 8 + _xm.start()]
_ja = JTS.find('=王維=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
if not (0 <= _xa and '議者不之罪' in _seg_x):
    raise SystemExit('切片越出王维段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；四扇窗口） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ193, TJ_CC1, '貞觀四年')
_window(TJ235, TJ_CC2, '貞元十年')
_window(TJ193, TJ_XD1, '貞觀五年')
_window(TJ256, TJ_XD2, '光啟二年')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：官名/诗语全零；長策恰七闭域；解帶恰二闭域
for _w in ('張少府', '窮通', '舊林', '松風', '漁歌', '山月', '好靜', '不關心', '空知', '浦深'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——官名/穷通/解带闲语进不了史部的判决失效，须重读')
_cc = {n: t.count('長策') for n, t in _tjf.items() if '長策' in t}
if _cc != {'tj-193.txt': 1, 'tj-213.txt': 1, 'tj-235.txt': 1, 'tj-238.txt': 3, 'tj-248.txt': 1}:
    raise SystemExit(f'通鉴「長策」分布变了（实 {_cc}）——长策只经国是（恰七闭域）判决须重估')
_xd = {n: t.count('解帶') for n, t in _tjf.items() if '解帶' in t}
if _xd != {'tj-193.txt': 1, 'tj-256.txt': 1}:
    raise SystemExit(f'通鉴「解帶」分布变了（实 {_xd}）——解带最急（恰二闭域全引）判决须重估')
_sf = {n: t.count('少府') for n, t in _tjf.items() if '少府' in t}
if _sf != {'tj-196.txt': 1, 'tj-197.txt': 1, 'tj-201.txt': 1, 'tj-202.txt': 1, 'tj-208.txt': 1,
           'tj-212.txt': 1, 'tj-213.txt': 2, 'tj-215.txt': 1, 'tj-218.txt': 1, 'tj-222.txt': 1, 'tj-228.txt': 1}:
    raise SystemExit(f'通鉴「少府」分布变了（实 {_sf}）——官名只为监署（恰十二闭域）判决须重估')
if _alltj.count('少府監') != 7 or _alltj.count('少府少監') != 4:
    raise SystemExit('通鉴「少府監」恰七/「少府少監」恰四结构变了——监署构成断言失效')
# ② 全唐詩：穷通/旧林亦全零（两界之外）；渔歌恰二/解带恰一/好静恰一他卷在册
for _w in ('窮通', '舊林'):
    if _allq.count(_w) != 0:
        raise SystemExit(f'全唐詩「{_w}」不再全零——「诗问穷通在史与集之外」论断失效，须重读')
_ys = {n: t.count('漁歌') for n, t in _qtf.items() if '漁歌' in t}
if _ys != {'vol524.txt': 1, 'vol525.txt': 1}:
    raise SystemExit(f'全唐詩「漁歌」册数变了（实 {_ys}）——渔歌在册不引须重估')
if {n: t.count(w) for n, t, w in (('vol524.txt', _qtf['vol524.txt'], '漁歌聽不唱'),
                                  ('vol525.txt', _qtf['vol525.txt'], '漁歌對月聽'))
        if t.count(w) != 1} or _qtf['vol511.txt'].count('金魚聊解帶') != 1 or _qtf['vol218.txt'].count('好靜心迹素') != 1:
    raise SystemExit('他卷在册句结构变了（vol524/525 渔歌·vol511 解带·vol218 好静）——在册不引断言须重读')
if {n: t.count('解帶') for n, t in _qtf.items() if '解帶' in t} != {'vol511.txt': 1}:
    raise SystemExit('全唐詩「解帶」不再是恰一处——解带在册册数须重估')
if {n: t.count('好靜') for n, t in _qtf.items() if '好靜' in t} != {'vol218.txt': 1}:
    raise SystemExit('全唐詩「好靜」不再是恰一处（杜甫怀赞公句）——好静在册册数须重估')
if V126.count('酬張少府') != 2 or (V126.count('==[[酬張少府]]==') != 1 or V126.count('{{:酬張少府}}') != 1):
    raise SystemExit('卷126 酬張少府恰 2（锚1+桩1）结构变了——裸名锚在册断言失效')
# ③ ws：{{另}}恰一 + 他标记全零 + 75% + 三百首标记在页 + 全锚
if WS.count('{{另') != 1 or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页标记结构不再是 {{另}}×1 全他零——单枚异文判决失效，须重读快照')
if WS.count('{{Textquality|75%}}') != 1 or WS.count('卷126#酬張少府|') != 1:
    raise SystemExit('ws 页 75%/全锚结构变了——底注断言失效')
if WS.count('{{唐詩三百首}}') != 1 or WS.count('| title    = 酬張少府') != 1:
    raise SystemExit('ws 页三百首标记/题行结构变了——选本标记照登断言失效')
# ④ 两传全文负证（诗面字不进传）与首引/零重开前提
for _f, _nm in ((JTS, '旧传全文'), (XTS, '新传全文')):
    for _w in ('靜', '長策', '解帶', '漁歌', '少府', '窮通', '舊林', '張少府'):
        if _w in _f:
            raise SystemExit(f'「{_w}」落在{_nm}——诗面字不进传负证失效，须重读原文')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
for _premise, _needle, _want in (
        ('新传议者不之罪', '議者不之罪', []),
        ('本诗正文', '晚年唯好靜', ['V018']),
        ('本诗尾句', '漁歌入浦深', ['V018']),
        ('願歸所任官', '願歸所任官', ['V040', 'V061']),
        ('V061 召缙句', '召縉為左散騎常侍', ['V061']),
        ('V044 焚香句', '焚香獨坐', ['V044']),
        ('V039 长斋句', '晚年長齋', ['V039'])):
    _prev = sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                    if not f.name.startswith('V062')
                    for _ln in f.read_text(encoding='utf-8').splitlines()
                    if 'evidence_excerpt' in _ln and _needle in _ln})
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')

BG = {
    'bg-063-scene': (
        '四联是一场晚年自述的静：晚年只爱清静，万事不关心'
        '（「晚年唯好靜，萬事不關心」——诗眼落在一个靜字上，此字两传全文全零，'
        '见 PERSON 层）；回头看自己并无治国的长策，只空知要返归旧林'
        '（「自顧無長策，空知返舊林」——长策二字史部只作经国是用，'
        '诗的长策却是对自己查问、答曰「无」，见 WORLD 层）；'
        '松风吹着解开的衣带，山月照着弹奏的琴'
        '（「松風吹解帶，山月照彈琴」——解带一刻是全诗最闲的瞬间，'
        '而史部的解带恰是跪谏、追銮的最急瞬间，急閑异位，见 WORLD 层）；'
        '你若问穷通之理，渔歌已深入水浦——不答是答'
        '（「{{另|君|若}}問窮通理，漁歌入浦深」——君一作若，照登；'
        '穷通二字史部诗集双双全零，此问在两界之外，不答是答系读法声明，'
        '页上无一字自注；此诗正文系**第二引**：V018 text claim 已一引在先'
        '（其形系异文取首项的归一文本），全库查重恰一处，两度上限至此用满，'
        '此诗正文对后来迁移关闭）。'),
    'bg-063-city': (
        '篇题锚点是**裸名**的：「==[[酬張少府]]==」没有括号——'
        '《唐詩三百首》里没有第二首《酬張少府》，便不需要消歧器。'
        '至此同一体系的三种消歧形态齐备：V059 雜詩是**作者消歧**「(王維)」，'
        'V061 送別是**首句消歧**「(山中相送罷)」，本篇是**无消歧裸名**——'
        '消歧器的有无本身就是同名登记（audit 照登硬卡）。卷126 本篇锚+桩恰 2'
        '（闭域机器断言）；底注「↑[[全唐詩/卷126#酬張少府|全唐詩·卷126]]」'
        '锚点片段非空（同 V058–V061 全锚形态）；页带 {{唐詩三百首}} 标记'
        '（与 V061 送別页无标记互为有无，各按各页原样）；'
        'source-quantangshi-126 系 V035/V039/V052/V054/V060 已立、'
        '**第六次复用零新源**；分类行「五言律詩」系整理者动作（V048 判例：'
        '非史料声明、不升格）；题面「酬」是唱和体例——通鉴「酬答」全零，'
        '赠答往还整个不在史部（本层零铸造零 relation）。'),
    'bg-063-world': (
        '**題有官名，官名在史部只為監署**：通鉴「張少府」全零；「少府」恰十二处'
        '（文件闭域+少府監恰七/少府少監恰四构成断言）——全是官署职事'
        '（少府監、少府少監、送少府銷毀），**没有一个「某少府」式的人**：'
        '题目里的友人，在史部只存在为一座衙门。**詩有長策解帶，两对字同时两界'
        '（同字两界第七形态·一首诗双对首见）**。「長策」恰七处（闭域断言）'
        '全是经国是：貞觀四年（庚寅，六三〇）安突厥「**此安邊之長策也**」、'
        '貞元十年（甲戌，七九四）陸贄彈延齡「**以聚斂為長策**」——'
        '好策坏策都是治国的策；诗的「自顧無長策」是自查，答曰「无」'
        '（两句史文逐字入引为判决证据，audit 硬卡）。「解帶」恰二处'
        '（闭域+双窗口）且全引：貞觀五年（辛卯，六三一）執失思力「**脫巾解帶**，'
        '跪而固諫」、光啟二年（丙午，八八六）杜讓能亂中奔鑾「**解帶**繫頸而乘之」——'
        '史部的解帶是**最急的瞬間**（跪諫、追鑾）；诗的「松風吹解帶」是'
        '**最閑的瞬間**（松風、山月）——同字两界，急閑异位（两语入引+诗句零混入'
        '双向断言）。**詩的問答在兩界之外**：「窮通」「舊林」通鉴与全唐詩双双全零'
        '——穷通之理在史与集里都无处问，所以「漁歌入浦深」；「漁歌」全唐詩恰二处'
        '（vol524「漁歌聽不唱」/vol525「漁歌對月聽」他人句在册零入引，'
        '机器断言）、通鉴全零；「好靜」全唐詩恰一处=vol218 杜甫'
        '「好靜心迹素」（他人在册不牵合）。本层零铸造零 relation。'),
    'bg-063-person': (
        '诗里自查「无长策」，传里他上过一道关涉官位的表：V040 已引新传'
        '「願歸所任官，放田里」求换弟弟王縉还京（在册零重开，audit 硬卡字样）；'
        '本迁移首引史家对那道表的考语——「**議者不之罪。**」'
        '（生成时全库查重：既往零入引，audit 硬卡）：议者不罪，'
        '也不褒——**四字考语，不置可否**（读法声明，非史实）。\n'
        '**两传全文「靜」字全零**（机器断言——写「晚年唯好靜」的人，'
        '两篇传里没有靜字；「長策」「解帶」「漁歌」「少府」「窮通」「舊林」'
        '两传亦全零）——**诗面字不进传**系列第二例（V061 送字全零之后）：'
        '诗的自画像（晚年唯好靜）两传无一字对应，传所记惟仕历与佛事'
        '（晚年長齋不衣文綵 V039/退朝之後焚香獨坐 V044 在册零重开）。'
        '已用判例句（願歸所任官 V040/召縉句 V061/柴毁骨立 V057/歴右拾遺三连 V059/'
        '服除句 V060/輞川系列 V035 起）一个不重开；certainty 不覆盖任何系年。'),
}
CLAIMS = {
    'claim-bg-063-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页 {{另}}×1、其余标记全零、Textquality 75%——单枚异文'
        '与不完备并存，正交横截面第六度复现）；异文（君/若）引文含标记原样'
        '照登不裁决；同页两形并存三度再验：V018 正文引文系异文取首项的归一文本，'
        '本迁移 SCENE 引文含 {{另}} 标记原样，各从其录；穷通之问「不答是答」'
        '系读法声明非史料断言（页上无自注）；全句第二引：正文 V018 text claim'
        '一引在先（生成时全库查重恰一处，查重针「晚年唯好靜」「漁歌入浦深」'
        '各恰一处），两度上限至此用满、此诗正文对后来迁移关闭（audit 硬卡）。'),
    'claim-bg-063-city': (
        'FACT', 'LIKELY',
        '三种消歧形态至此齐备：V059 作者消歧「(王維)」/V061 首句消歧'
        '「(山中相送罷)」/本篇裸名锚「==[[酬張少府]]==」（无同名则无消歧器，'
        '消歧器有无本身即同名登记，audit 照登硬卡）；卷126 锚+桩恰 2 闭域'
        '（机器断言）；底注全锚（同 V058–V061）；{{唐詩三百首}} 标记在本页'
        '（与 V061 送別页无标记互为有无）；source-quantangshi-126 系'
        'V035/V039/V052/V054/V060 已立、第六次复用零新源；分类行「五言律詩」'
        '照登+非史料声明+不升格；通鉴「酬答」全零（赠答往还不进史部）；'
        '题面酬答体而无时→零铸造零 relation。'),
    'claim-bg-063-world': (
        'FACT', 'LIKELY',
        '通鉴「張少府」全零+「少府」恰十二闭域（少府監恰七/少府少監恰四构成'
        '断言）——官名在史部只為監署；長策恰七闭域（tj-193/213/235/238×3/248）'
        '经国是双句入引=貞觀四年（庚寅，六三〇）安邊之長策+貞元十年（甲戌，'
        '七九四）聚斂為長策（闭域+双窗口断言）；解帶恰二闭域全引=貞觀五年'
        '（辛卯，六三一）脫巾解帶跪而固諫+光啟二年（丙午，八八六）解帶繫頸而乘之'
        '（闭域+双窗口断言）——同字两界第七形态·一首诗双对首见·急閑异位'
        '（audit 正入负零双向硬卡）；窮通/舊林通鉴+全唐詩双双全零（诗的问答'
        '在两界之外，机器断言）；漁歌全唐詩恰二（vol524/vol525 他人句在册零入引）'
        '+好靜恰一（vol218 杜甫句在册不牵合）；certainty 不覆盖任何系年，'
        '诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-063-person': (
        'FACT', 'LIKELY',
        '新传「議者不之罪」首引（生成时全库引文域查重：既往零命中，audit 硬卡）；'
        '其前换官表句「願歸所任官，放田里」V040 已引在册零重开（audit 硬卡字样）；'
        '四字考语不置可否为读法声明非史实；**两传全文靜/長策/解帶/漁歌/少府/'
        '窮通/舊林全零**（机器断言——诗面字不进传系列第二例，V061 送字全零之后）；'
        '长斋焚香句 V039/V044 在册零重开；已用判例句零重开；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-063-scene', 'source-ws-t300-063',
     '页面 酬張少府（header author+四联八句，五段以「……」相連——全句**第二引**：'
     '正文 V018 text claim 一引在先（其形系异文取首项的归一文本，本引文含 {{另}} '
     '标记原样——同页两形并存各从其录），生成时全库查重恰一处，'
     '**两度上限至此用满，此诗正文对后来迁移关闭**；{{别}}/{{*}}/<ref> 全零、75%；'
     '穷通之问不答是答系引者读法声明）',
     join(WS_AUTHOR, WS_L1, WS_L2, WS_L3, WS_L4)),
    ('claim-bg-063-city', 'source-ws-t300-063',
     '页面 酬張少府（header title+页底注+分类行三段并收——题面「酬」系唱和体例；'
     '底注全锚「卷126#酬張少府」（同 V058–V061 全锚形态）；{{唐詩三百首}} 标记'
     '在本页（与 V061 送別页无标记互为有无，各按各页原样照登）；'
     '分类行系整理者动作：非史料声明、不升格）',
     join(WS_TITLE, WS_NOTE, WS_CAT)),
    ('claim-bg-063-city', 'source-quantangshi-126',
     '卷一百二十六·王維《酬張少府》篇题锚点+转引桩（**裸名锚**——无同名诗则'
     '无消歧器：对照 V059 作者消歧「(王維)」、V061 首句消歧「(山中相送罷)」，'
     '三种消歧形态至此齐备；卷126「酬張少府」恰 2=锚 1+桩 1 机器断言；'
     '源行系 V035/V039/V052/V054/V060 已立、本迁移第六次复用零新源）',
     join(Q126, Q126_S)),
    ('claim-bg-063-world', 'source-zizhi-tongjian-events',
     '卷一百九十三·貞觀四年（庚寅，六三〇）安邊之長策段……卷二百三十五·'
     '貞元十年（甲戌，七九四）聚斂為長策段……卷一百九十三·貞觀五年（辛卯，六三一）'
     '脫巾解帶跪而固諫段……卷二百五十六·光啟二年（丙午，八八六）解帶繫頸而乘之段'
     '（**通鉴「張少府」全零、少府恰十二只为监署、長策恰七、解帶恰二**：'
     '文件闭域+四处年标题窗口机器断言——长策只经国是、解带只急变须臾，'
     '与诗之自查无策/松风解带同字两界第七形态·双对首见；四句史文逐字入引'
     '为判决证据；「窮通」「舊林」通鉴全零——诗的问答在两界之外）',
     join(TJ_CC1, TJ_CC2, TJ_XD1, TJ_XD2)),
    ('claim-bg-063-person', 'source-xintangshu-wenyi',
     '卷二百二·文艺中·王維传议者不之罪句（生成时全库引文域查重：既往零入引，'
     '本迁移首引；其前换官表句「願歸所任官，放田里」V040 已引零重开；'
     '四字考语不置可否是读法声明；两传全文靜字全零——诗面字不进传，机器断言）', XTS_Y),
]
BG_LINES = {'bg-063-scene': (1, 2), 'bg-063-city': (3, 4),
            'bg-063-world': (5, 6), 'bg-063-person': (7, 8)}
BG_AUDIENCE = {'bg-063-scene': 'PRIMARY', 'bg-063-city': 'JUNIOR',
               'bg-063-world': 'SENIOR', 'bg-063-person': 'JUNIOR'}
BG_TITLES = {'bg-063-scene': '眼前：晚年只爱清静的自述',
             'bg-063-city': '这座城：不需要消歧器的篇题',
             'bg-063-world': '这个天下：史的解带最急，诗的解带最闲',
             'bg-063-person': '这个人：两传全文一个静字没有'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 43 首·八句五律 2/2/2/2 第四次）；史实句均有逐字引证；'
                 '系年第三十七次判决（题证系列第廿五状·官名与长策解带）'
                 '「題有官名，官名在史部只為監署；詩有長策解帶，'
                 '長策在史部只經國是，解帶在史部只急變須臾」——'
                 '通鉴「張少府」全零、少府恰十二（监署七+少府少監四+机构一，'
                 '闭域+构成断言）；長策恰七闭域（国是双句入引：安邊之長策'
                 '貞觀四年庚寅六三〇+聚斂為長策貞元十年甲戌七九四）；'
                 '解帶恰二闭域全引（脫巾解帶跪而固諫貞觀五年辛卯六三一+'
                 '解帶繫頸而乘之光啟二年丙午八八六）——同字两界第七形态·'
                 '一首诗双对首见·急閑异位（史最急/诗最闲，audit 双向硬卡）；'
                 '窮通/舊林通鉴+全唐詩双双全零（诗的问答在两界之外）；'
                 '漁歌全唐詩恰二在册零入引+好靜恰一（杜甫句）在册不牵合；'
                 '三种消歧形态至此齐备（V059 作者/V061 首句/本篇裸名——'
                 '消歧器有无本身即同名登记）；卷126 恰二闭域+底注全锚；'
                 '零新源（卷126 源 V035/V039/V052/V054/V060 已立第六次复用）；'
                 '{{另}}×1×75% 正交第六度+同页两形并存三度再验；'
                 '此诗正文第二引上限用满第十例对后来关闭（V018 在先+双针查重）；'
                 'PERSON 首引新传「議者不之罪」（願歸所任官 V040 零重开；'
                 '两传全文靜字全零——诗面字不进传第二例）；'
                 'KNOWN 零如实记录（第十八例，audit 反向断言）；判例关键语零入引文。' for k in BG}


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
    A("""-- V062：王維《酬張少府》(work-t300-063) 四层背景（阶段 D 第 43 首·官名与长策解带）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V039、V040、V044、V052、V054、V059、V060、V061 已执行
--       （work-t300-063 与其 text-work-t300-063-ws、source-ws-t300-063 是 V018 的行；
--       source-quantangshi-126 是 V035/V039/V052/V054/V060 已立的卷126 源行（本迁移第六次复用，零新源）；
--       source-xintangshu-wenyi 是 V016 的行；source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       判例在册句长斋（V039）/焚香（V044）/願歸所任官（V040）/召缙（V061）只引不重开）。
--       本迁移零新 source（audit 断言无诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v062.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/酬張少府.txt（{{另}}×1×75%+底注全锚+三百首标记在页）、
--   舊唐書卷190下/新唐書卷202（两传全文靜字全零负证+議者不之罪首引+願歸所任官零重开）、
--   全唐詩卷126（裸名锚+桩）/卷218/卷511/卷524/卷525（好静/解带/渔歌在册句闭域）、
--   通鑑卷193/235/256（長策恰七+解帶恰二+四处年标题窗口）+ 通鑑 75 卷/全唐詩 118 卷
--   存快照负证计数扫描（張少府/少府/少府監/少府少監/長策/解帶/窮通/舊林/松風/漁歌/
--   山月/好靜/不關心/空知/浦深/酬答）+
--   既有迁移引文域逐句查重——传区间归属、首引/二引/零重开前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 background_line（八句五律 **2/2/2/2 第四次**（V054/V058/V060）：scene→1-2 city→3-4
--   world→5-6 person→7-8，绑 text-work-t300-063-ws 的 8 行）+ 零 poetry_source 行 + 不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有官名，官名在史部只為監署；詩有長策解帶，長策在史部只經國是，
--   解帶在史部只急變須臾」）：
--   * 張少府/窮通/舊林/松風/漁歌/山月/好靜通鉴全零+少府恰十二只监署（闭域+构成断言）；
--   * 長策恰七+解帶恰二闭域；国是双句+急变双句共四句史文入引为判决证据（audit 硬卡）；
--   * 不答是答与四字考语不置可否均标明读法声明非史实（页上无自注）；
--   * 异文君/若引文含标记原样；同页两形并存三度再验（V018 归一形 vs 本迁移原样形）；
--   * 三种消歧形态齐备照登（V059 作者/V061 首句/本篇裸名——消歧器有无即同名登记）；
--   * 此诗正文第二引上限用满：V018 一引在先（双针查重各恰一处），对后来迁移关闭；
--   * vol218/511/524/525 他卷在册句零入引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第十八例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 願歸所任官（V040）/召缙句（V061）/长斋（V039）/焚香（V044）判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 61，不含 62
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-063-%';             -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-126';     -- 恰 1（五迁移已立，本迁移复用不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-063-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-063-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-063';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-063-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-063'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-063';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-063-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-quantangshi-126';  -- 恰 1（复用，非本迁移所立）
-- 回滚: recovery/V062_rollback.sql（按 id 全枚举删除；零 source 删除——卷126 源行为五迁移所立）
START TRANSACTION;""")

    A('\n-- ---------- 1. 零新 source（卷126 源行五迁移已立，本迁移第六次复用） ----------')

    A('-- ---------- 2. BACKGROUND content identities ----------')
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
    brows = [{'id': k, 'work_id': 'work-t300-063',
              'layer': {'bg-063-scene': 'SCENE', 'bg-063-city': 'CITY',
                        'bg-063-world': 'WORLD', 'bg-063-person': 'PERSON'}[k],
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

    A('\n-- ---------- 6. background_line（八句五律 2/2/2/2 第四次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-063-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 7. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 62, 'Wang Wei''s Response to Vice-Prefect Zhang (work-t300-063) background layers (stage-D poem 43, five-character regulated octet 2/2/2/2 fourth time): dating verdict thirty-seven, twenty-fifth shape of the title-evidence series -- the office title and the two character-pairs in two realms: the string Zhang-Shaofu (the friend named in the title) scores zero across all Tongjian volumes while shaofu appears exactly twelve times (file-closed, constitution-asserted: seven Shofu-jian superintendencies plus four Shao-fu-shao-jian plus one bureau-as-actor) -- never a person, only an office; chang-ce (long stratagem) appears exactly seven times, always statecraft, two lines excerpted as verdict evidence (630 the pacification of the Turks "this is the long stratagem for settling the border", 794 Lu Zhi denouncing Yan Ling "he took hoarding as his long stratagem"), while the poem asks itself for a long stratagem and answers "none"; jie-dai (loosening the sash) appears exactly twice (file-closed, windowed) and both are quoted: in 631 the Turkic commander Chishi Sili removing his cap and loosening his sash to kneel and remonstrate, and in 886 Du Rangneng in the flight toward the emperor loosening his sash to tether a found horse -- in the histories untying the sash marks the most urgent instant, in the poem ("the pine wind blows on my loosened sash") the most leisured: the seventh same-character split, the first time one poem splits two character-pairs at once, urgency against leisure (audit asserts both the four history lines in and the poem''s lines out); qiong-tong (poverty and success) and jiu-lin (the old woods) score zero in BOTH the Tongjian and the Quan Tangshi -- the poem''s question lives outside both realms, hence the answering fisherman''s song (yu-ge: two lines in juan 524/525 by other poets, logged never quoted; hao-jing "loving stillness": exactly one line, Du Fu on the monk Zan, logged never conflated); the disambiguation trio completed: author-disambiguation (V059), first-line disambiguation (V061), and this bare unparenthesized anchor -- whether a disambiguator exists is itself the homonym registry (audit hard-assert); juan 126''s anchor-plus-transclusion exactly two (file-closed) with the base note''s full non-empty fragment (as V058-V061); zero new sources (juan 126''s row reused for the sixth time); one {{另}} marker with 75% (orthogonality sixth time) and same-page two-forms co-existence re-verified a third time; the poem body hits its two-use ceiling (V018 first, twin normalized needles, closure declared); PERSON first-cites the New History''s four-character verdict on his exchange-of-office memorial -- "the deliberators did not blame him" (neither praise nor blame: the earlier memorial sentence stays closed to V040) -- while both entire biographies contain not one occurrence of the character jing (stillness), nor chang-ce, jie-dai, yu-ge, shaofu, qiong-tong or jiu-lin: the poem''s own words never enter the biographies (second instance after the character farewell in V061, machine-asserted); KNOWN zero honestly recorded (eighteenth instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 62);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V062 精确回滚：只删 V062 插入的行（id 全枚举）。零 source 删除：',
         '-- source-quantangshi-126 是 V035/V039/V052/V054/V060 已立的卷126 源行（本迁移第六次复用），绝不删；',
         '-- work-t300-063 本体、其 text_line 8 行与 source-ws-t300-063 都是 V018 的行，绝不删；',
         '-- source-xintangshu-wenyi/zizhi-tongjian-events 均为他迁移所立，零删除；V062 零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 62;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_L1, WS_L2, WS_L3, WS_L4,
              XTS_Y, TJ_CC1, TJ_CC2, TJ_XD1, TJ_XD2, Q126, Q126_S]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 底注全锚 + 题行照登硬卡（CITY ws 引文）
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-063-city' and s == 'source-ws-t300-063')
    if '卷126#酬張少府|' not in city_ws:
        bad.append('底注全锚未逐字入 CITY 引文（全锚形态照登硬卡）')
    if '| title    = 酬張少府' not in city_ws:
        bad.append('题行未逐字入 CITY 引文（酬答体题面照登硬卡）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-063-city' and s == 'source-ws-t300-063'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # 裸名锚照登硬卡
    city_q = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-063-city' and s == 'source-quantangshi-126')
    if '==[[酬張少府]]==' not in city_q:
        bad.append('裸名锚点未逐字入 CITY 引文（三形态齐备照登硬卡）')
    # SCENE 标记原样 + 第二引上限声明硬卡
    s_ex = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-063-scene')
    if '{{另|君|若}}' not in s_ex:
        bad.append('SCENE 引文缺标记原样「{{另|君|若}}」（照登硬卡）')
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-063-scene')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054–V061 同款硬卡）')
    # WORLD：四段史文必须在引文内（判决证据）；诗句/在册句零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-063-world')
    for tok in ('安邊之長策', '聚斂為長策', '脫巾解帶', '解帶繫頸'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（长策两界/解带急闲必须入引）')
    for tok in ('松風', '彈琴', '漁歌', '窮通', '舊林', '晚年', '金魚聊解帶', '好靜心迹素',
                '漁歌聽不唱', '漁歌對月聽'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入在册/诗句项「{tok}」（他卷在册句与诗语不得入 WORLD 引文）')
    # PERSON：议者句在引 + 换官表句零重开
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-063-person')
    if '議者不之罪' not in p_ex:
        bad.append('PERSON 引文缺议者不之罪句（首引前提）')
    for tok in ('願歸所任官', '放田里', '使縉得還京師', '召縉為左散騎常侍',
                '晚年長齋', '不衣文綵', '焚香獨坐'):
        if tok in p_ex:
            bad.append(f'「{tok}」他迁移已引零重开——不得入本迁移引文')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-063':
            for w in ('謫仙', '脫靴', '賜金放還', '宮錦袍', '夜郎', '山東人'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山', '隠鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒', '刻碑鳳林山南',
                '仕宦之疾徑', '進止仍有風範', '茶鐺', '事母崔氏', '解官以贖',
                '柴毁骨立', '毀幾不生', '大招權利', '車如流水馬如龍',
                '歴右拾遺', '天寳末，為給事中', '或牒歸故鄉', '見郭子儀',
                '昆仲宦遊兩都', '輞口', '藍田别墅', '下馬飲君酒', '歸臥南山陲',
                '白雲無盡', '服闋，拜吏部郎中', '隱於嵩山之陽', '閉關以拒之',
                '殺郡王', '雲南王孫', '春草未生', '今宵歸不歸',
                '山中相送罷', '日暮掩柴扉', '一作山中送別'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句五律 2/2/2/2 第四次
    if {k: len(v) for k, v in BG_LINES.items()} != {k: 2 for k in BG}:
        bad.append('八句 background_line 须每层恰 2（2/2/2/2）')
    if sorted(n for seqs in BG_LINES.values() for n in seqs) != list(range(1, 9)):
        bad.append('2/2/2/2 须覆盖 1-8 句各一次')
    if len(re.findall(r"text-work-t300-063-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # 零新 source（V052 教训：断言文案也不得出现该字面量）
    if 'INSERT INTO poetry_' + 'source' in sql:
        bad.append('V062 有意零新 source，但 SQL 里出现了诗源表新建插入语句')
    if 'DELETE FROM poetry_source' in build_rollback():
        bad.append('回滚不得删任何 source 行（卷126 源行为五迁移所立）')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V062 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V062 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-063' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V062 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-063' AS subject_id" in sql:
        bad.append('V062 的 claim 主语应全部是 bg-063-*，work-t300-063 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V062 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '官名在史部只為監署' not in body_all:
        bad.append('BG/文件头须含「官名在史部只為監署」判决声明')
    if '同字两界第七形态' not in body_all:
        bad.append('BG 须含「同字两界第七形态」声明')
    if '最急' not in body_all or '最閑' not in body_all:
        bad.append('BG 须含「史最急/诗最闲」急闲对句')
    if '三种消歧形态' not in body_all:
        bad.append('BG/CITY 须含「三种消歧形态齐备」结构声明')
    if '詩的問答在兩界之外' not in body_all and '在两界之外' not in body_all:
        bad.append('BG 须含「诗的问答在两界之外」（穷通旧林双零）声明')
    if '静' in ' '.join((WS_TITLE,)) or '詩面字不進傳' not in body_all.replace('进传', '不進傳') and '诗面字不进传' not in body_all:
        bad.append('BG/PERSON 须含「两传靜字全零/诗面字不进传」负证声明')
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
              f'切片传区间归属断言（新传王维段）；'
              f'四处年标题窗口断言（貞觀四年六三〇/貞元十年七九四/貞觀五年六三一/光啟二年八八六）；'
              f'负证机器复查五层（通鉴張少府/窮通/舊林/松風/漁歌/山月/好靜/不關心/空知/浦深全零+'
              f'長策恰七闭域(tj-193/213/235/238×3/248)+解帶恰二闭域(tj-193/tj-256)+'
              f'少府恰十二闭域+少府監七/少府少監四构成/全唐詩窮通舊林亦全零+漁歌恰二(vol524/525)+'
              f'解帶恰一(vol511)+好靜恰一(vol218) 四在册句恰一/'
              f'卷126 酬張少府恰二=锚一桩一闭域/ws {{另}}恰一具体字样+他标记全零+75%+三百首标记恰一+全锚/'
              f'两传全文靜/長策/解帶/漁歌/少府/窮通/舊林/張少府全零，快照变动即中止）；'
              f'前提全库查重硬卡七件（议者句零引+正文双针恰一=V018+願歸所任官恰一=V040+'
              f'召缙句恰一=V061+焚香恰一=V044+长斋恰一=V039）；'
              f'底注全锚+题行+裸名锚照登硬卡；SCENE 标记原样+第二引/上限硬卡；'
              f'长策两界/解带急闲入引+松風彈琴漁歌窮通舊林与四在册句零混入断言；'
              f'願歸所任官/召缙/长斋/焚香零重开断言；判例只引不重开断言（含 V061 送別诸语——'
              f'上一迁移已用语一个不重开）；'
              f'八句 2/2/2/2 形制断言；零 KNOWN 反向断言；零新 source 反向断言（回滚零 source 删除）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
