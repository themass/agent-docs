#!/usr/bin/env python3
"""阶段 D 第 42 首：生成 V061——王維《送別》(work-t300-145「山中相送罷」, V018 已立) 四层背景。

「为什么写」走到「王孫」两界（同字两界第六形态，V056 泪/V057 已矣/V058 琴·流水/
V059 故鄉/V060 閉關之后）：**題有送目，送目在史部七十五卷全零；詩有王孫，
王孫在史部唯宗室之裔與君長之孫**——

通鉴「送別」「送友」两个送别诗类名**全零**（类名不进史部第二例，V059 雜詩之后），
「柴扉」「歸不歸」「年年」也全零；而「王孫」恰二处（闭域+双窗口机器断言）：
建中四年（癸亥，七八三）朱泚之乱，張休勸朱泚「誅翦宗室在京城者以絕人望，
殺郡王、王子、**王孫**凡七十七人」（tj-228——史部的王孫是被屠杀的皇族后裔）；
貞元九年（癸酉，七九三）南诏王異牟尋上表「自稱唐故雲南**王孫**、吐蕃贊普義弟」（
tj-234——史部的王孫是君长之孙的政治头衔）。**诗的「王孫歸不歸」是楚辞
「王孫游兮不歸」的温柔典——问的是朋友回不回来；史部的王孫是族谱与封号——
被杀七十七人，或自称以要盟**。同字两界，在册入引为判决证据。
**「春草」恰一处**（闭域+窗口断言）：貞元三年（丁卯，七八七）突厥语者言
「吾在河曲，**春草**未生，馬不能舉足」（tj-232——史部的春草是马料季：
春草未生则马不能行）；诗的「春草明年綠」是候归之草——**史的春草系马，
诗的春草系人**（在册入引为判决证据）。「歸不歸」全唐詩恰一处=vol523
他人宫词「今宵歸不歸」（撞句在册不引不牵合，机器断言）。

CITY 层：**同名诗的消歧谱**——《唐詩三百首》里王维有两首《送別》：
054「下馬飲君酒」（V037 已立背景）与本首 145「山中相送罷」——
ws 页文件名靠首句消歧（送別__山中相送罷_.txt），卷128 的消歧锚
「==[[送別 (山中相送罷)|送別]]==」把首句写进锚点、把题目留给展示
（**首句消歧式首见**——V059 是作者消歧式「(王維)」，本篇是首句消歧式，
同一体系两种消歧器）；两页 title 行形制互异：054 页简体「送别」、
本篇繁体「送別」（V037 已录 054 简形——同名两页繁简各按各页原样照登）。
底注尾巴**双一作异题注**「一作山中送別，一作送友」（一页同时两异题候选，
纯文本第四形态：V052 署名异说/V055 川一作水/V057 一名式/本篇一题两案）。
{{另}}×1（明年/年年）×75%；V018 正文归一取首项「明年」——同页两形并存再验。
source-quantangshi-128 V026/V040 已立、**第六次复用零新源**。

PERSON 层首引：新传「**久乃召縉為左散騎常侍。**」（全库查重既往零入引）——
V040 已引王维上表「願歸所任官，放田里」换弟弟王縉还京（在册零重开，audit 硬卡），
新传紧接着记了结局：朝廷终究召王縉回朝做了左散騎常侍——**诗里说「但去莫復問」，
传里他为一问（弟弟何时回来）真写了一表**：问而不复问是诗，问而上表是史
（读法声明，非史实）。**两传王维段「送」字全零**（机器断言——
写尽送别的人，传里一个送字没有）。

四句绝句 1/1/1/1 形制第二次（V056 首用）；正文第二引上限用满第九例
（V018 归一形一引在先，查重针「王孫歸不歸」恰一处）。

用法: python3 -I emit_v061.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/送別__山中相送罷_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS2 = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
V128 = pathlib.Path('/tmp/src-dl/quantangshi/vol128.txt').read_text(encoding='utf-8')
V523 = pathlib.Path('/tmp/src-dl/quantangshi/vol523.txt').read_text(encoding='utf-8')
TJ228 = pathlib.Path('/tmp/src-dl/tongjian/tj-228.txt').read_text(encoding='utf-8')
TJ232 = pathlib.Path('/tmp/src-dl/tongjian/tj-232.txt').read_text(encoding='utf-8')
TJ234 = pathlib.Path('/tmp/src-dl/tongjian/tj-234.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 送別', '| title    = 送別', 'ws header title(繁体送別——对照 054 页简体送别,同名两页繁简互异)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS,
                        '| notes    = {{Textquality|75%}}↑ [[全唐詩/卷128#送別|全唐詩·卷128]] 一作山中送別，一作送友',
                        '一作送友',
                        'ws 页底注(75%+全锚+尾巴双一作异题注——一题两案纯文本第四形态)')
WS_CAT = slice_between(WS, '[[Category:送別詩]]', '[[Category:送別詩]]', 'ws 分类行(送別詩——整理者分类;V048 分类行判例)')
WS_L1 = slice_between(WS, '山中相送罷，日暮掩柴扉。', '日暮掩柴扉。', 'ws第1联(山中送罢归来掩门——送与掩一贯到底)')
WS_L2 = slice_between(WS, '春草{{另|明年|年年}}綠，王孫歸不歸。', '王孫歸不歸。', 'ws第2联(春草绿时你回不回来——明年/年年异文,王孙=楚辞典)')
XTS_J = slice_between(XTS2, '久乃召縉為左散騎常侍。', '左散騎常侍。',
                      '新传召缙句(从未入引,PERSON 首引——願歸所任官 V040 已引之后朝廷的结局一句)')
TJ_WS1 = slice_between(TJ228, '殺郡王、王子、王孫凡七十七人。', '凡七十七人。',
                       '通鉴建中四年朱泚杀宗室段(王孫史部一处——宗室之裔被屠;窗口断言)')
TJ_WS2 = slice_between(TJ234, '自稱唐故雲南王孫、吐蕃贊普義弟日東王。', '義弟日東王。',
                       '通鉴贞元九年异牟寻表段(王孫史部二处——君长之孙的政治头衔;窗口断言)')
TJ_CC = slice_between(TJ232, '吾在河曲，春草未生，馬不能舉足', '馬不能舉足',
                      '通鉴贞元三年突厥语者言(春草史部唯一一处——马料季;窗口断言)')
Q128 = slice_between(V128, '==[[送別 (山中相送罷)|送別]]==', '==[[送別 (山中相送罷)|送別]]==',
                     '卷128 本篇篇题锚点(首句消歧式首见——消歧器是首句,展示名留题目)')
Q128_S = slice_between(V128, '{{:送別 (山中相送罷)}}', '{{:送別 (山中相送罷)}}', '卷128 本篇转引桩')

# ---------- 传区间归属复验（V036 立规） ----------
_xa = XTS2.find('==王維==')
_xm = re.search(r'\n==[^=\n]{1,10}==', XTS2[_xa + 8:])
_seg_x = XTS2[_xa:_xa + 8 + _xm.start()]
_ja = JTS.find('=王維=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
if not (0 <= _xa and '久乃召縉' in _seg_x):
    raise SystemExit('切片越出王维段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；三扇窗口） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ228, TJ_WS1, '建中四年')
_window(TJ234, TJ_WS2, '貞元九年')
_window(TJ232, TJ_CC, '貞元三年')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：送别类名全零；王孫恰二=tj-228/tj-234；春草恰一=tj-232；柴扉/歸不歸/年年全零
for _w in ('送別', '送友', '柴扉', '歸不歸', '年年', '山中送別'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——送目/掩扉语进不了史部的判决失效，须重读')
_ws = {n: t.count('王孫') for n, t in _tjf.items() if '王孫' in t}
if _ws != {'tj-228.txt': 1, 'tj-234.txt': 1}:
    raise SystemExit(f'通鉴「王孫」分布变了（实 {_ws}）——同字两界第六形态判决须重估')
_cc = {n: t.count('春草') for n, t in _tjf.items() if '春草' in t}
if _cc != {'tj-232.txt': 1}:
    raise SystemExit(f'通鉴「春草」不是恰一处（实 {_cc}）——史的春草系马论断须重估')
# ② 全唐詩：歸不歸恰一=vol523 他人句（在册不引）；柴扉恰 8 册数；本篇锚桩各恰一
_gb = {n: t.count('歸不歸') for n, t in _qtf.items() if '歸不歸' in t}
if _gb != {'vol523.txt': 1}:
    raise SystemExit(f'全唐詩「歸不歸」册数变了（实 {_gb}）——撞句在册不引须重估')
if V523.count('今宵歸不歸') != 1:
    raise SystemExit('vol523 撞句「今宵歸不歸」结构变了——在册句须重读')
_cf = {n: t.count('柴扉') for n, t in _qtf.items() if '柴扉' in t}
if _cf != {'vol226.txt': 1, 'vol230.txt': 5, 'vol524.txt': 1, 'vol539.txt': 1}:
    raise SystemExit(f'全唐詩「柴扉」册数分布变了（实 {_cf}）——柴扉在册册数须重估')
if V128.count('送別') != 3 or (V128.count('==[[送別 (山中相送罷)|送別]]==') != 1
                               or V128.count('{{:送別 (山中相送罷)}}') != 1):
    raise SystemExit('卷128 送別恰 3（锚2+桩1）结构变了——首句消歧式在册断言失效')
# ③ ws：{{另}}恰一 + 他标记全零 + 75% + 双一作尾巴 + 繁体 title
if WS.count('{{另') != 1 or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页标记结构不再是 {{另}}×1 全他零——单枚异文判决失效，须重读快照')
if WS.count('{{Textquality|75%}}') != 1 or WS.count('卷128#送別|') != 1:
    raise SystemExit('ws 页 75%/全锚结构变了——底注断言失效')
if WS.count('一作山中送別，一作送友') != 1 or WS.count('| title    = 送別') != 1:
    raise SystemExit('ws 页双一作尾巴/繁体 title 结构变了——一题两案第四形态断言失效')
# ④ 两传王维段负证与首引/二引/零重开前提
for _seg, _nm in ((_seg_j, '旧传'), (_seg_x, '新传')):
    for _w in ('送', '柴扉', '王孫'):
        if _w in _seg:
            raise SystemExit(f'「{_w}」落在{_nm}王维段——传无送字负证失效，须重读原文')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
for _premise, _needle, _want in (
        ('新传召缙句', '召縉為左散騎常侍', []),
        ('願歸所任官', '願歸所任官', ['V040']),
        ('本诗正文', '王孫歸不歸', ['V018']),
        ('054 送别正文', '下馬飲君酒', ['V018', 'V037'])):
    _prev = sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                    if not f.name.startswith('V061')
                    for _ln in f.read_text(encoding='utf-8').splitlines()
                    if 'evidence_excerpt' in _ln and _needle in _ln})
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')

BG = {
    'bg-145-scene': (
        '四句是送罢人回家的一路安静：山里送走朋友回来，天黑了，把柴门掩上'
        '（「山中相送罷，日暮掩柴扉」——送与掩，一贯到底：门掩上，心还开着）；'
        '明年春草再绿的时候，你回不回来呢'
        '（「春草{{另|明年|年年}}綠，王孫歸不歸」——明年一作年年，照登；'
        '王孫用的是《楚辞》「王孫游兮不歸」的典——问的是朋友，此读法系本层声明，'
        '页上无一字自注；此诗正文系**第二引**：V018 text claim 已一引在先'
        '（其形系异文取首项的归一文本），全库查重恰一处，两度上限至此用满，'
        '此诗正文对后来迁移关闭）。'),
    'bg-145-city': (
        '《唐詩三百首》里王维有**两首《送別》**：054「下馬飲君酒」（V037 已立背景）'
        '与本首 145「山中相送罷」——同名两首靠首句消歧：ws 页文件名'
        '送別__山中相送罷_.txt 是消歧的，卷128 的锚点'
        '「==[[送別 (山中相送罷)|送別]]==」把首句写进消歧器、把「送別」留给展示'
        '（**首句消歧式首见**：V059 雜詩是作者消歧式「(王維)」，本篇是首句消歧式，'
        '同一体系两种消歧器，audit 照登硬卡）。两页 title 行形制互异：054 页简体'
        '「送别」（V037 已录）、本篇繁体「送別」——同名两页繁简各按各页原样照登。'
        '底注尾巴「一作山中送別，一作送友」：**一页同时两异题候选（一题两案，'
        '纯文本异注第四形态**：V052 署名异说、V055 川一作水、V057 一名式之后），'
        '照登不裁决（audit 硬卡字样）。页 {{另}}×1（明年/年年）而其余标记全零、75%；'
        'V018 正文归一形与本迁移标记原样形**同页两形并存再验**。底注全锚'
        '（卷128#送別，同 V058–V060 全锚形态）；source-quantangshi-128 系 V026/V040'
        '已立、第六次复用**零新源**；分类行「送別詩」系整理者动作（V048 判例）——'
        '「送別詩」这个类目与 WORLD 层「送目」的通鉴全零恰成一对：'
        '整理者建了柜，史部不收。'),
    'bg-145-world': (
        '**題有送目，送目在史部七十五卷全零**：通鉴「送別」「送友」两个类名'
        '零命中（类名不进史部第二例，V059 雜詩之后），「柴扉」「歸不歸」「年年」'
        '也全零——送别的语汇整场进不了史部。而「王孫」恰二处'
        '（文件闭域+双年标题窗口机器断言），处处不是这场相送：'
        '建中四年（癸亥，七八三）朱泚之乱，「**殺郡王、王子、王孫凡七十七人**」'
        '——史部的王孫是被屠戮的宗室之裔；貞元九年（癸酉，七九三）南诏'
        '異牟尋上表「**自稱唐故雲南王孫、吐蕃贊普義弟日東王**」'
        '——史部的王孫是君长之孙的政治头衔。**诗的「王孫歸不歸」用楚辞的典'
        '问朋友回不回来；史部的王孫是族谱与封号：七十七人被杀，或自称以要盟**'
        '（同字两界第六形态，三段史文逐字入引为判决证据，audit 硬卡）。'
        '**「春草」恰一处**（闭域+窗口断言）：貞元三年（丁卯，七八七）'
        '突厥语者追忆「**吾在河曲，春草未生，馬不能舉足**」——'
        '史的春草是马料季：春草未生则马不能行；诗的春草明年绿是候归之草——'
        '**史的春草系马，诗的春草系人**。全唐詩「歸不歸」恰一处=vol523 他人句'
        '「今宵歸不歸」（撞句在册不引不牵合，机器断言）；「柴扉」恰 8 处他卷在册。'
        '本层零铸造零 relation。'),
    'bg-145-person': (
        '诗里说「但去莫復問」——你去吧，我不再问了；传里他却为一问写过表：'
        'V040 已引新传他自表「願歸所任官，放田里」求换弟弟王縉还京'
        '（在册零重开，audit 硬卡字样）；本迁移首引紧接的结局一句——'
        '「**久乃召縉為左散騎常侍。**」（生成时全库查重：既往零入引，'
        'audit 硬卡）：朝廷终究把王縉召回朝做了左散騎常侍。'
        '**问而不复问是诗，问而上表是史**：「春草明年綠，王孫歸不歸」'
        '的问出口就收在诗里；「弟弟几时回来」的问，他写成了一道表'
        '（读法声明，非史实）。\n'
        '**两传王维段「送」字全零**（机器断言——写尽送别的人，传里一个'
        '送字没有；「柴扉」「王孫」两传段亦全零）；已用判例句'
        '（願歸所任官 V040/柴毁骨立 V057/歴右拾遺三连 V059/服除句 V060/'
        '輞川系列 V035 起）一个不重开；certainty 不覆盖任何系年。'),
}
CLAIMS = {
    'claim-bg-145-scene': (
        'FACT', 'LIKELY',
        '四句全诗本文（ws 页 {{另}}×1、其余标记全零、Textquality 75%——单枚异文'
        '与不完备并存，正交横截面第五度复现）；异文（明年/年年）引文含标记原样'
        '照登不裁决；同页两形并存再验：V018 正文引文系异文取首项的归一文本，'
        '本迁移 SCENE 引文含标记原样，各从其录；王孫=楚辞「王孫游兮不歸」之典'
        '系读法声明非史料断言（页上无自注）；全句第二引：正文 V018 text claim'
        '一引在先（生成时全库查重恰一处，查重针取归一形「王孫歸不歸」），'
        '两度上限至此用满、此诗正文对后来迁移关闭（audit 硬卡）。'),
    'claim-bg-145-city': (
        'FACT', 'LIKELY',
        '同名诗的消歧谱首录：三百首里王维两首《送別》（054 V037 已立/本篇 145），'
        '卷128 锚点系首句消歧式「(山中相送罷)|送別」（首句消歧式首见——对照 V059'
        '作者消歧式「(王維)」，同一体系两种消歧器，audit 照登硬卡）；'
        '同名两页 title 行繁简互异（054 简体送别 V037 已录/本篇繁体送別）各按'
        '原样；底注尾巴双一作异题注「一作山中送別，一作送友」=一题两案纯文本'
        '第四形态（V052/V055/V057 之后，audit 硬卡字样）；底注全锚'
        '（同 V058–V060）；卷128「送別」恰 3=锚 2+桩 1（机器断言闭域）；'
        'source-quantangshi-128 V026/V040 已立、第六次复用零新源；分类行'
        '「送別詩」照登+非史料声明+不升格；题有送目而无时→零铸造零 relation。'),
    'claim-bg-145-world': (
        'FACT', 'LIKELY',
        '通鉴「送別」「送友」类名全零（类名不进史部第二例，V059 之后）+柴扉/'
        '歸不歸/年年全零；王孫恰二（闭域+双窗口机器断言）=tj-228 建中四年'
        '（癸亥，七八三）杀郡王王子王孫凡七十七人+tj-234 貞元九年（癸酉，七九三）'
        '異牟尋自稱唐故雲南王孫——史部的王孫一为宗室之裔一为君长之孙，与诗中'
        '楚辞典同字两界（第六形态），三段史文逐字入引为判决证据（audit 硬卡）；'
        '春草恰一处（闭域+窗口断言）=tj-232 貞元三年（丁卯，七八七）'
        '「吾在河曲，春草未生，馬不能舉足」——史的春草系马、诗的春草系人'
        '（入引为判决证据）；全唐詩「歸不歸」恰一=vol523 他人句今宵歸不歸'
        '（撞句在册不引，机器断言）；「柴扉」恰 8 他卷在册；certainty 不覆盖'
        '任何系年，诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-145-person': (
        'FACT', 'LIKELY',
        '新传召缙结局句首引（生成时全库引文域查重：召縉為左散騎常侍既往零命中，'
        'audit 硬卡）；其前句「願歸所任官，放田里」V040 已引在册零重开'
        '（audit 硬卡字样）；问而不复问是诗/问而上表是史为读法声明非史实；'
        '两传王维段送字/柴扉/王孫全零（机器断言——写尽送别的人传无送字）；'
        '已用判例句零重开；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-145-scene', 'source-ws-t300-145',
     '页面 送別 (山中相送罷)（header author+两联四句，三段以「……」相連——全句**第二引**：'
     '正文 V018 text claim 一引在先（其形系异文取首项的归一文本，本引文含 {{另}} '
     '标记原样——同页两形并存各从其录），生成时全库查重恰一处，'
     '**两度上限至此用满，此诗正文对后来迁移关闭**；{{别}}/{{*}}/<ref> 全零、75%；'
     '王孫之典页上无自注，系引者读法声明）',
     join(WS_AUTHOR, WS_L1, WS_L2)),
    ('claim-bg-145-city', 'source-ws-t300-145',
     '页面 送別 (山中相送罷)（header title+页底注+分类行三段并收——title 行繁体'
     '「送別」（同名两首之另一页 054 系简体，各按各页原样）；底注尾巴双一作'
     '异题注「一作山中送別，一作送友」=一题两案纯文本第四形态，照登不裁决；'
     '分类行系整理者动作：非史料声明、不升格）',
     join(WS_TITLE, WS_NOTE, WS_CAT)),
    ('claim-bg-145-city', 'source-quantangshi-128',
     '卷一百二十八·王維《送別》篇题锚点+转引桩（**首句消歧式首见**：锚点'
     '「(山中相送罷)|送別」把首句写进消歧器、题目留给展示——对照 V059 作者消歧式；'
     '卷128「送別」恰 3=锚 2+桩 1 机器断言；源行系 V026/V040 已立、本迁移'
     '第六次复用零新源）',
     join(Q128, Q128_S)),
    ('claim-bg-145-world', 'source-zizhi-tongjian-events',
     '卷二百二十八·建中四年（癸亥，七八三）殺郡王王子王孫段……卷二百三十四·'
     '貞元九年（癸酉，七九三）異牟尋自稱雲南王孫段……卷二百三十二·貞元三年'
     '（丁卯，七八七）春草未生馬不能舉足段'
     '（**通鉴「送別」「送友」类名全零、王孫恰二、春草恰一**：文件闭域+三处'
     '年标题窗口机器断言——史部的王孫一为被屠宗室一为君长头衔，与诗中楚辞典'
     '同字两界第六形态；史的春草系马，诗的春草系人；三段史文逐字入引为判决证据；'
     'vol523 他人撞句「今宵歸不歸」在册零入引）',
     join(TJ_WS1, TJ_WS2, TJ_CC)),
    ('claim-bg-145-person', 'source-xintangshu-wenyi',
     '卷二百二·文艺中·王維传召缙结局句（生成时全库引文域查重：既往零入引，'
     '本迁移首引；其前「願歸所任官，放田里」V040 已引零重开；与诗中'
     '「但去莫復問」并置是读法声明；两传王维段送字全零——传无送字，机器断言）', XTS_J),
]
BG_LINES = {'bg-145-scene': (1,), 'bg-145-city': (2,),
            'bg-145-world': (3,), 'bg-145-person': (4,)}
BG_AUDIENCE = {'bg-145-scene': 'PRIMARY', 'bg-145-city': 'JUNIOR',
               'bg-145-world': 'SENIOR', 'bg-145-person': 'JUNIOR'}
BG_TITLES = {'bg-145-scene': '眼前：送罢人掩门的一路安静',
             'bg-145-city': '这座城：两首同名诗的消歧谱',
             'bg-145-world': '这个天下：史的春草系马，诗的春草系人',
             'bg-145-person': '这个人：传里一个送字没有'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 42 首·四句绝句 1/1/1/1 第二次）；史实句均有逐字引证；'
                 '系年第三十六次判决（题证系列第廿四状·送目与王孫）'
                 '「題有送目，送目在史部七十五卷全零；詩有王孫，王孫在史部唯宗室之裔與君長之孫」——'
                 '通鉴「送別」「送友」类名全零（类名不进史部第二例，V059 雜詩之后）'
                 '而王孫恰二（闭域+双窗口）：建中四年（癸亥，七八三）杀郡王王子'
                 '王孫凡七十七人+貞元九年（癸酉，七九三）異牟尋自稱唐故雲南王孫'
                 '（同字两界第六形态，三段史文逐字入引为判决证据）；'
                 '春草恰一=貞元三年（丁卯，七八七）「春草未生，馬不能舉足」'
                 '（史的春草系马，诗的春草系人，入引）；'
                 '全唐詩「歸不歸」恰一=vol523 今宵歸不歸（撞句在册不引）+「柴扉」恰 8 在册；'
                 '同名诗的消歧谱首录（三百首王维两首《送別》054/145——'
                 '卷128 首句消歧式锚点首见，对照 V059 作者消歧式；'
                 '同名两页 title 繁简互异各按原样）；底注尾巴双一作异题注'
                 '「一作山中送別，一作送友」=一题两案纯文本第四形态照登；'
                 '{{另}}×1×75% 正交第五度+同页两形并存再验；'
                 '零新源（卷128 源 V026/V040 已立第六次复用）；'
                 '此诗正文第二引上限用满对后来关闭（V018 在先+全库查重归一形针）；'
                 'PERSON 首引新传召缙结局句（願歸所任官 V040 零重开；'
                 '两传王维段送字全零——传无送字）；'
                 'KNOWN 零如实记录（第十七例，audit 反向断言）；判例关键语零入引文。' for k in BG}


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
    A("""-- V061：王維《送別》(work-t300-145「山中相送罷」) 四层背景（阶段 D 第 42 首·送目与王孫）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V026、V037、V040、V057、V059、V060 已执行
--       （work-t300-145 与其 text-work-t300-145-ws、source-ws-t300-145 是 V018 的行；
--       source-quantangshi-128 是 V026/V040 已立的卷128 源行（本迁移第六次复用，零新源）；
--       source-xintangshu-wenyi 是 V016 的行；source-zizhi-tongjian-events 是 V014/V015
--       已立的通鉴事件源；同名另一首 054「下馬飲君酒」的背景是 V037）。
--       本迁移零新 source（audit 断言无诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v061.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/送別__山中相送罷_.txt（{{另}}×1×75%+底注尾巴双一作异题注+繁体 title 行）、
--   舊唐書卷190下/新唐書卷202（传无送字负证+召缙句首引+願歸所任官零重开）、
--   全唐詩卷128（首句消歧锚+桩）/卷523（归不归撞句在册）、
--   通鑑卷228/232/234（王孫恰二+春草恰一+三处年标题窗口）+ 通鑑 75 卷/全唐詩 118 卷
--   存快照负证计数扫描（送別/送友/柴扉/歸不歸/年年/王孫/春草）+
--   既有迁移引文域逐句查重——传区间归属、首引/二引/零重开前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 行 background_line（四句绝句 1/1/1/1 第二次（V056 首用）：scene→1 city→2 world→3 person→4，
--   绑 text-work-t300-145-ws 的 4 行）+ 零 poetry_source 行 + 不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有送目，送目在史部七十五卷全零；詩有王孫，王孫在史部唯宗室之裔與君長之孫」）：
--   * 送目/送友类名全零（类名不进史部第二例）；王孫恰二+春草恰一逐卷闭域+三窗口入引为判决证据；
--   * 王孫之楚辞典与问而不复问/问而上表均标明读法声明非史实（页上无自注）；
--   * 异文明年/年年引文含标记原样；同页两形并存再验（V018 归一形 vs 本迁移原样形）；
--   * 双一作异题注（一作山中送別，一作送友）一题两案照登不裁决（audit 硬卡）；
--   * 同名两首（054/145）消歧谱：首句消歧式首见（对照 V059 作者消歧式）；
--   * 此诗正文第二引上限用满：V018 一引在先（查重针归一形恰一处），对后来迁移关闭；
--   * vol523 撞句「今宵歸不歸」在册不引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第十七例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 願歸所任官（V040）/柴毁骨立（V057）/歴右拾遺三连（V059）/服除句（V060）判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 60，不含 61
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-145-%';             -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-128';     -- 恰 1（V026/V040 已立，本迁移复用不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-145-ws';  -- 恰 4
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-145-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-145';                                  -- 4（1/1/1/1）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-145-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-145'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-145';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-145-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-quantangshi-128';  -- 恰 1（复用，非本迁移所立）
-- 回滚: recovery/V061_rollback.sql（按 id 全枚举删除；零 source 删除——卷128 源行为 V026/V040 所立）
START TRANSACTION;""")

    A('\n-- ---------- 1. 零新 source（卷128 源行 V026/V040 已立，本迁移第六次复用） ----------')

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
    brows = [{'id': k, 'work_id': 'work-t300-145',
              'layer': {'bg-145-scene': 'SCENE', 'bg-145-city': 'CITY',
                        'bg-145-world': 'WORLD', 'bg-145-person': 'PERSON'}[k],
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

    A('\n-- ---------- 6. background_line（四句绝句 1/1/1/1 第二次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-145-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 7. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 61, 'Wang Wei''s Farewell (the mountain poem, work-t300-145) background layers (stage-D poem 42, quatrain 1/1/1/1, second use): dating verdict thirty-six, twenty-fourth shape of the title-evidence series -- the farewell label and the prince''s grandson in two realms: the character-strings farewell/farewell-to-a-friend (the category names of parting poetry) score zero across all seventy-five Tongjian volumes (second instance of category-names-barred-from-the-histories after za-shi in V059), and brush-gate, will-he-return, year-upon-year likewise zero; yet prince''s grandson appears exactly twice (file-closed, twin year-heading windows): in 783, during the Zhu Ci coup, commandery princes, princes and prince''s-grandsons -- seventy-seven imperial kinsmen -- were slaughtered to cut off the people''s hope, and in 793 the Nanzhao king Yimouxun styled himself in his throne table "grandson of a former king of Yunnan under Tang, sworn younger brother of the Tibetan emperor" -- in the histories a prince''s grandson is either butchered kin or a political title, while the poem''s "prince, will you return?" borrows the Chuci''s gentle allusion to ask a friend: the sixth same-character split (three history sentences excerpted as the verdict''s evidence, audit hard-assert); spring grass exactly once (file-closed, windowed): in 787 a Turkic-speaker recalls that at the He-qu bend when spring grass had not yet grown the horses could not lift a foot -- the histories'' spring grass tethers horses, the poem''s spring grass tethers the homeward hope of a friend; quan tang shi holds exactly one will-he-return line (vol 523, someone else''s palace verse: logged never quoted) and eight brush-gate lines logged elsewhere; the disambiguation genealogy of same-titled poems first recorded: the Three Hundred Poems carry two Farewells by Wang Wei (054 done in V037, this 145) -- juan 128''s anchor is a first-line-disambiguation (the disambiguator is the opening line, the display name stays Farewell; against V059''s author-disambiguation: two disambiguators in one system), and the two ws pages differ in script (054 simplified, 145 traditional, each logged as found); the base-note tail carries a double alternative-title gloss (one title, two candidates: the fourth plain-text form) logged never adjudicated; one {{另}} marker with 75% (orthogonality fifth time) and same-page two-forms co-existence re-verified; zero new sources (juan 128''s row reused for the sixth time); the poem body hits its two-use ceiling (V018 first, normalized needle, closure declared); PERSON first-cites the New History''s sentence on the court finally recalling Wang Jin as 左散騎常侍 (the earlier self-immolation table sentence stays closed to V040; both biographies contain not one occurrence of the character farewell -- the man who wrote parting for the ages, machine-asserted); KNOWN zero honestly recorded (seventeenth instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 61);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V061 精确回滚：只删 V061 插入的行（id 全枚举）。零 source 删除：',
         '-- source-quantangshi-128 是 V026/V040 已立的卷128 源行（本迁移第六次复用），绝不删；',
         '-- work-t300-145 本体、其 text_line 4 行与 source-ws-t300-145 都是 V018 的行，绝不删；',
         '-- source-xintangshu-wenyi/zizhi-tongjian-events 均为他迁移所立，零删除；V061 零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 61;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_L1, WS_L2,
              XTS_J, TJ_WS1, TJ_WS2, TJ_CC, Q128, Q128_S]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 双一作尾巴 + 繁体 title 照登硬卡（CITY 引文）
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-145-city' and s == 'source-ws-t300-145')
    if '一作山中送別，一作送友' not in city_ws:
        bad.append('底注双一作异题注未逐字入 CITY 引文（一题两案第四形态照登硬卡）')
    if '| title    = 送別' not in city_ws:
        bad.append('繁体 title 行未逐字入 CITY 引文（同名两页繁简互异照登硬卡）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-145-city' and s == 'source-ws-t300-145'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # 首句消歧锚照登硬卡
    city_q = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-145-city' and s == 'source-quantangshi-128')
    if '==[[送別 (山中相送罷)|送別]]==' not in city_q:
        bad.append('首句消歧锚点未逐字入 CITY 引文（消歧式首见照登硬卡）')
    # SCENE 标记原样 + 第二引上限声明硬卡
    s_ex = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-145-scene')
    if '{{另|明年|年年}}' not in s_ex:
        bad.append('SCENE 引文缺标记原样「{{另|明年|年年}}」（照登硬卡）')
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-145-scene')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054–V060 同款硬卡）')
    # WORLD：三段史文必须在引文内（判决证据）；撞句/零命中词零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-145-world')
    for tok in ('王孫凡七十七人', '雲南王孫', '春草未生'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（王孫两界/春草系马必须入引）')
    for tok in ('今宵歸不歸', '柴扉', '年年綠'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入在册零入引项「{tok}」（撞句/柴扉/异文支不得入引）')
    # PERSON：召缙句在引 + 願歸所任官零重开
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-145-person')
    if '召縉為左散騎常侍' not in p_ex:
        bad.append('PERSON 引文缺召缙结局句（首引前提）')
    if '願歸所任官' in p_ex or '放田里' in p_ex:
        bad.append('「願歸所任官/放田里」V040 已引零重开——不得入本迁移引文')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-145':
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
                '白雲無盡', '服闋，拜吏部郎中', '隱於嵩山之陽', '閉關以拒之'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 四句绝句 1/1/1/1 形制
    if {k: len(v) for k, v in BG_LINES.items()} != {k: 1 for k in BG}:
        bad.append('四句 background_line 须每层恰 1（1/1/1/1）')
    if sorted(n for seqs in BG_LINES.values() for n in seqs) != [1, 2, 3, 4]:
        bad.append('1/1/1/1 须覆盖 1-4 句各一次')
    if len(re.findall(r"text-work-t300-145-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    # 零新 source（V052 教训：断言文案也不得出现该字面量）
    if 'INSERT INTO poetry_' + 'source' in sql:
        bad.append('V061 有意零新 source，但 SQL 里出现了诗源表新建插入语句')
    if 'DELETE FROM poetry_source' in build_rollback():
        bad.append('回滚不得删任何 source 行（卷128 源行为 V026/V040 所立）')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V061 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V061 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-145' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V061 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-145' AS subject_id" in sql:
        bad.append('V061 的 claim 主语应全部是 bg-145-*，work-t300-145 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V061 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '宗室之裔與君長之孫' not in body_all:
        bad.append('BG/文件头须含「王孫在史部唯宗室之裔與君長之孫」判决声明')
    if '同字两界第六形态' not in body_all:
        bad.append('BG 须含「同字两界第六形态」声明')
    if '史的春草系马，诗的春草系人' not in body_all:
        bad.append('BG 须含「史的春草系马，诗的春草系人」对句')
    if '首句消歧' not in body_all:
        bad.append('BG/CITY 须含「首句消歧」结构首见声明')
    if '一题两案' not in body_all:
        bad.append('BG/CITY 须含「一题两案」双一作注声明')
    if '传无送字' not in body_all and '「送」字全零' not in body_all:
        bad.append('BG/PERSON 须含「两传送字全零」负证声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 12 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（新传王维段）；'
              f'三处年标题窗口断言（建中四年七八三/貞元九年七九三/貞元三年七八七）；'
              f'负证机器复查五层（通鉴送別/送友/柴扉/歸不歸/年年/山中送別全零+'
              f'王孫恰二=tj-228+tj-234 闭域+春草恰一=tj-232 闭域/'
              f'全唐詩歸不歸恰一=vol523 今宵歸不歸在册+柴扉恰八精确闭域四卷/'
              f'卷128 送別恰三=锚二桩一闭域+锚桩各恰一/'
              f'ws {{另}}恰一具体字样+他标记全零+75%+双一作尾巴恰一+繁体 title 恰一/'
              f'两传王段送/柴扉/王孫全零，快照变动即中止）；'
              f'前提全库查重硬卡四件（召缙句零引+願歸所任官恰一=V040+'
              f'正文恰一=V018 归一形针+054 正文恰一=V018）；'
              f'双一作注+繁体 title+首句消歧锚照登硬卡；SCENE 标记原样+第二引/上限硬卡；'
              f'王孫两界/春草系马入引+今宵歸不歸/柴扉/年年綠零混入断言；'
              f'願歸所任官零重开断言；判例只引不重开断言（含下馬飲君酒/歸臥南山陲/白雲無盡——'
              f'同名另一首 054 已用语一个不重开）；'
              f'四句 1/1/1/1 形制断言；零 KNOWN 反向断言；零新 source 反向断言（回滚零 source 删除）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
