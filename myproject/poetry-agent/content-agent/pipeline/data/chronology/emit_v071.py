#!/usr/bin/env python3
"""阶段 D 第 52 首：生成 V071——李商隱《錦瑟》(work-t300-010, V018 已立) 四层背景。

**本迁移零新建 source——连续第三首**（V069/V070 之后）。
本篇与 V070 同卷同源（source-quantangshi-539 第六次复用），但绑定形态更奇：
ws 页 notes 带「↑ [[全唐詩/卷539#錦瑟|全唐詩·卷五百三十九]]」**向上回指卷页**，
而卷539 的本篇正文恰恰是「{{:錦瑟}}」**向下转引诗页**——同一首诗两个方向互指，
**底本声明与转引方向相反：底本是个循环指针**（V018 底本字段「全唐詩」指向 539，
539 正文又是 ws 页的转引）。V069 单向↑、V070 单向{{:}}、本篇互指闭环——绑定三角齐。

「为什么写」走到**惘然两界**（同字两界第十六形态·惘然形态首见）：
**通鉴「錦瑟/莊生/望帝/杜鵑/蝴蝶/春心/華年/無端/追憶/滄海月」全零，
唯一的惘然却是太后慰谕老臣的诏书——「初聞此語，能不惘然；靜而思之，是為龜鏡」：
史部的惘然有龟镜（回思即规戒），诗的惘然没有（只是當時已惘然）**——

四层判决：
① 通鉴「錦瑟/莊生/庄生/望帝/杜鵑/蝴蝶/春心/華年/無端/追憶/滄海月/曉夢」全零
   （机器断言）——诗面典故群史部一个都不接；
② 「惘然」恰一在光宅元年（甲申，六八四）太后慰谕刘仁轨：「**初聞此語，能不惘然；
   靜而思之，是為龜鏡**」——**史部的惘然有龟镜，诗的惘然没有**；
   「滄海」恰二：神功元年（丁酉，六九七）狄仁傑上疏「**東拒滄海，西阻流沙**」=国界，
   天復二年（壬戌，九〇二）杨行密说冯弘鐸「**胡為自棄滄海之外**」=弃路——
   **史部的沧海分中外弃路，诗的沧海藏珠泪**（滄海月明珠有淚）；
   「淚」恰三，最近诗的一条在天寶六年（丁亥，七四七）哥舒翰救王忠嗣「**言與淚俱**」
   ——**史部的泪落在官位旁边，诗的泪在月明的海上**；
③ 全唐詩「錦瑟」恰四：225 杜甫「何時詔此金錢會，暫醉佳人錦瑟旁」+539 壳二+
   540 李賀《房中曲》「歸來已不見，錦瑟長於人」——**此诗以宾语在他诗里活在《全唐诗》，
   本篇六整句在全唐诗语料零存在**（机器断言——完整正文只活在诗页，卷页只挂壳）；
④ 旧传（**简化字**）首引「**商隐能为古文，不喜偶对。**」——史部记他早年的文学习惯；
   段内锦瑟诗面十六字全零（瑟、弦单字亦零，机器断言）——
   **写尽锦瑟的人，传里无一瑟字**；「不喜偶对的人留下最工偶对的诗」系读法声明。

ws 页形制（SCENE/CITY 层）：**一枚诗行内两枚 {{另|絃|弦}}——全 ws 库独串**（机器断言）；
**notes 三连一行**（三百首在首+100% 评级在中+↑底本回指在尾——V069 是↑+评级在 notes、
三百首在 header 外尾：顺序形态相反）；**页尾分类仅两行、无 [[Category:李商隱]]**
（李商隱署名 21 页中无作者分类仅 3 页：春雨/籌筆驛/錦瑟——照登不升格）；
无空格排版「| times=唐」照登。**正文第二引上限第十九例**：V018 一引带句读
（'錦瑟無端五十絃，……只是當時已惘然。'——絃已展开），本迁移二引 ws 页 poem 块
**存原样含双 {{另}} 折叠**（各从其录；V018 句读式引文零重开，生成时硬断言）。

8 句七律 shape：**2/2/2/2 顺次**（scene→1,2 city→3,4 world→5,6 person→7,8；
V020 以来八句篇常规）。

用法: python3 -I emit_v071.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402

WS = pathlib.Path('/tmp/src-dl/ws-poems/錦瑟.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
V539 = pathlib.Path('/tmp/src-dl/quantangshi/vol539.txt').read_text(encoding='utf-8')
TJ203 = pathlib.Path('/tmp/src-dl/tongjian/tj-203.txt').read_text(encoding='utf-8')
TJ206 = pathlib.Path('/tmp/src-dl/tongjian/tj-206.txt').read_text(encoding='utf-8')
TJ215 = pathlib.Path('/tmp/src-dl/tongjian/tj-215.txt').read_text(encoding='utf-8')
TJ263 = pathlib.Path('/tmp/src-dl/tongjian/tj-263.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 錦瑟', '| title    = 錦瑟',
                         'ws header title(裸名题面——錦瑟二字通鉴全零)')
WS_TIME = slice_between(WS, '| times=唐', '| times=唐',
                        'ws 无空格排版形态(此前库内多作 "| times  = 唐"——照登)')
WS_AUTHOR = slice_between(WS, '| author   = 李商隱', '| author   = 李商隱', 'ws header author(署名直证)')
WS_NOTE3 = slice_between(
    WS,
    '| notes    = {{唐詩三百首}}{{Textquality|100%}}↑ [[全唐詩/卷539#錦瑟|全唐詩·卷五百三十九]]',
    '| notes    = {{唐詩三百首}}{{Textquality|100%}}↑ [[全唐詩/卷539#錦瑟|全唐詩·卷五百三十九]]',
    'ws notes 三连一行(三百首在首+100%评级在中+↑底本回指在尾——V069 顺序形态相反)')
WS_POEM = slice_between(WS,
                        '錦瑟無端五十{{另|絃|弦}}，一{{另|絃|弦}}一柱思華年。',
                        '只是當時已惘然。\n</poem>',
                        'ws poem 块存原样含双{{另|絃|弦}}折叠(正文第二引——只登记不裁决)')
WS_CAT2 = slice_between(WS, '[[Category:唐诗]]\n[[Category:唐詩三百首|李]]',
                        '[[Category:唐诗]]\n[[Category:唐詩三百首|李]]',
                        'ws 页尾分类仅两行(无 [[Category:李商隱]]——署名 21 页中仅 3 页如此)')
V539_SHELL = slice_between(V539, '==[[錦瑟]]==\n{{:錦瑟}}', '==[[錦瑟]]==\n{{:錦瑟}}',
                           '卷539 空壳转引(与 V069 ↑回指同页互指——循环指针之卷页侧)')
TJ_WR = slice_between(TJ203, '初聞此語，能不惘然；靜而思之，是為龜鏡。',
                      '初聞此語，能不惘然；靜而思之，是為龜鏡。',
                      '通鉴光宅元年太后慰谕刘仁轨诏(史部唯一惘然有龟镜;窗口断言)')
TJ_CH1 = slice_between(TJ206, '東拒滄海，西阻流沙，北橫大漠，南阻五嶺，',
                       '東拒滄海，西阻流沙，北橫大漠，南阻五嶺，',
                       '通鉴神功元年狄仁傑上疏(史部沧海=国界;窗口断言)')
TJ_CH2 = slice_between(TJ263, '胡為自棄滄海之外！', '胡為自棄滄海之外！',
                       '通鉴天复二年杨行密说冯弘鐸(史部沧海=弃路;窗口断言)')
TJ_LEI = slice_between(TJ215,
                       '力陳忠嗣之冤，且請以己官爵贖忠嗣罪；上起，入禁中，翰叩頭隨之，言與淚俱。',
                       '力陳忠嗣之冤，且請以己官爵贖忠嗣罪；上起，入禁中，翰叩頭隨之，言與淚俱。',
                       '通鉴天宝六年哥舒翰救王忠嗣(史部之泪落在官位旁;窗口断言)')
JTS_W = slice_between(JTS, '商隐能为古文', '不喜偶对。',
                      '旧传李商隐段(能为古文不喜偶对——史部记文学习惯;PERSON 首引)')

# ---------- 传区间归属复验（段界 ==弟 羲叟==） ----------
_ja = JTS.find('=李商隱=')
_jm = re.search(r'\n==[^=\n]{1,12}==', JTS[_ja + 8:])
_seg_j = JTS[_ja:_ja + 8 + _jm.start()]
for _needle in (JTS_W,):
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

_window(TJ203, TJ_WR, '光宅元年')
_window(TJ206, TJ_CH1, '神功元年')
_window(TJ263, TJ_CH2, '天復二年')
_window(TJ215, TJ_LEI, '天寶六年')

# ---------- 负证机器复查 ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：诗面语全零；惘然恰一在 203；滄海恰二（206/263）；淚恰三（215/236/256）；在册档
for _w in ('錦瑟', '莊生', '庄生', '望帝', '杜鵑', '蝴蝶', '春心', '華年', '無端',
           '追憶', '滄海月', '曉夢'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗面典故群不进史部的判决失效，须重读')
if _alltj.count('惘然') != 1 or _tjf['tj-203.txt'].count('惘然') != 1:
    raise SystemExit('通鉴「惘然」不再恰一（tj-203 太后诏）——惘然两界判决须重估')
_chd = {n: t.count('滄海') for n, t in _tjf.items() if '滄海' in t}
if sum(_chd.values()) != 2 or _chd != {'tj-206.txt': 1, 'tj-263.txt': 1}:
    raise SystemExit(f'通鉴「滄海」不再恰二分在 206/263（实 {_chd}）——中外/弃路两界判决须重估')
_lei = {n: t.count('淚') for n, t in _tjf.items() if '淚' in t}
if sum(_lei.values()) != 3 or set(_lei) != {'tj-215.txt', 'tj-236.txt', 'tj-256.txt'}:
    raise SystemExit(f'通鉴「淚」不再恰三（215/236/256）——泪字侧闭域档扫须重估')
if _alltj.count('能不惘然') != 1 or _alltj.count('是為龜鏡') != 1:
    raise SystemExit('通鉴「能不惘然/是為龜鏡」不再恰一——太后诏在册须重估')
for _w, _n in (('珠', 57), ('煙', 26), ('五十', 172)):
    if _alltj.count(_w) != _n:
        raise SystemExit(f'通鉴「{_w}」不再恰{_n}——珠/煙/五十侧闭域档扫须重估')
# ② 全唐诗：锚全库唯一；字面恰四（225/539×2/540）；539 全卷零本篇正文；六整句全库零
if _allq.count('==[[錦瑟]]==') != 1:
    raise SystemExit('《全唐詩》「==[[錦瑟]]==」锚不再全库唯一——壳标本判决失效')
_js = {n: t.count('錦瑟') for n, t in _qtf.items() if '錦瑟' in t}
if sum(_js.values()) != 4 or _js != {'vol225.txt': 1, 'vol539.txt': 2, 'vol540.txt': 1}:
    raise SystemExit(f'全唐詩「錦瑟」不再恰四（225/539×2/540）——他诗宾语判决须重估')
if V539.count(V539_SHELL) != 1 or V539.count('{{:錦瑟}}') != 1:
    raise SystemExit('卷539 空壳转引结构变了（循环指针之卷页侧断言失效）')
for _w in ('莊生', '望帝', '蝴蝶', '杜鵑', '惘然', '華年', '追憶', '藍田', '五十絃',
           '錦瑟無端', '思華年'):
    if V539.count(_w) != 0:
        raise SystemExit(f'卷539「{_w}」不再全零——**壳内无本篇正文一字**机器断言失效')
for _w in ('春心', '無端', '滄海'):
    if V539.count(_w) != 1:
        raise SystemExit(f'卷539「{_w}」他诗混片计数变了（各恰一——闭域档扫须重估）')
for _ln in ('錦瑟無端五十', '莊生曉夢迷蝴蝶', '望帝春心託杜鵑', '滄海月明珠有淚',
            '藍田日暖玉生煙', '此情可待成追憶', '只是當時已惘然'):
    if _allq.count(_ln) != 0:
        raise SystemExit(f'全唐詩语料「{_ln}」不再全零——六整句只活在诗页的判决失效')
if _allq.count('房中曲') != 1 or _allq.count('錦瑟長於人') != 1 or _allq.count('何時詔此金錢會') != 1:
    raise SystemExit('全唐詩他诗锦瑟语（杜甫/李賀）计数变了——宾语侧闭域须重估')
# ③ ws：双{{另}}独串；notes 三连；分类两行无作者分类；无 reflist；无 from 行
if WS.count('{{另|絃|弦}}') != 2:
    raise SystemExit('ws 一枚诗行双 {{另|絃|弦}} 结构变了（独串硬卡失效）')
_wsf = {p.name: p.read_text(encoding='utf-8')
        for p in sorted(pathlib.Path('/tmp/src-dl/ws-poems').glob('*.txt'))}
_duo = {n for n, t in _wsf.items() if '錦瑟無端五十{{另|絃|弦}}，一{{另|絃|弦}}一柱思華年' in t}
if _duo != {'錦瑟.txt'}:
    raise SystemExit(f'一行双{{另}}独串不再本页独有（实 {sorted(_duo)}）——全 ws 库独串判决须重估')
if WS.count('{{reflist}}') != 0 or WS.count('<ref>') != 0 or WS.count('| from') != 0:
    raise SystemExit('ws 无注表/无<ref>/无 from 行形态变了（异文只页内折叠断言失效）')
if WS.count('[[Category:李商隱]]') != 0 or WS.count('[[Category:唐诗]]') != 1:
    raise SystemExit('ws 页尾分类两行无作者分类形态变了（三页孤例档扫失效）')
_nocat = sorted(n for n in _wsf if '| author   = 李商隱' in _wsf[n] and '[[Category:李商隱]]' not in _wsf[n])
if _nocat != ['春雨__李商隱_.txt', '籌筆驛__李商隱_.txt', '錦瑟.txt']:
    raise SystemExit(f'李商隱署名无作者分类不再恰三页（实 {_nocat}）——孤例档扫须重估')
if WS.count('只是當時已惘然') != 1:
    raise SystemExit('ws 页惘然句计数变了（单转录断言失效）')
if WS.count(WS_NOTE3) != 1 or WS.count(WS_CAT2) != 1 or WS.count('| times=唐') != 1:
    raise SystemExit('ws notes 三连/分类两行/无空格排版结构变了')
# ④ 旧传李商隐段负证（段内诗面十六字全零——瑟、弦单字亦零）
for _w in ('錦', '瑟', '絃', '弦', '柱', '蝶', '望帝', '杜鵑', '滄海', '藍田',
           '珠', '淚', '煙', '惘然', '追憶', '華年'):
    if _seg_j.count(_w) != 0:
        raise SystemExit(f'「{_w}」落在旧传李商隐段——传段十六诗字全零判决失效，须重读原文')

POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V071')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

def _domain_src(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V071')
                   and needle in f.read_text(encoding='utf-8')})

for _premise, _needle, _want in (
        ('本诗首句(V018 句读式一引)', '錦瑟無端五十絃', ['V018']),
        ('本诗末句(V018 句读式收尾)', '只是當時已惘然', ['V018']),
        ('V018 句读式全引不重开', '錦瑟無端五十絃，……只是當時已惘然。', ['V018']),
        ('ws 诗页源在先', 'source-ws-t300-010', ['V018']),
        ('卷页源五次在册(本迁移第六次复用)', 'source-quantangshi-539',
         ['V018', 'V067', 'V068', 'V069', 'V070']),
        ('V069 底本回指链接在册', '↑ [[全唐詩/卷539#寄令狐郎中', ['V069']),
        ('V070 壳转引在册', '{{:夜雨寄北}}', ['V070']),
        ('V033 滄海诗语在册', '別來滄海事', ['V033']),
        ('V035/V039 藍田史语在册', '得宋之問藍田别墅', ['V035', 'V039']),
        ('V016 在册诸句', '商隐随亚在岭表累载', ['V016'])):
    _prev = _domain_src(_needle) if _needle.startswith('source-') else _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
for _first, _needle in (('惘然诏书', '初聞此語，能不惘然；靜而思之，是為龜鏡。'),
                        ('狄疏沧海', '東拒滄海，西阻流沙，北橫大漠，南阻五嶺，'),
                        ('行密沧海', '胡為自棄滄海之外！'),
                        ('哥舒翰泪', '言與淚俱'),
                        ('旧传文学习惯', '商隐能为古文'),
                        ('不喜偶对', '不喜偶对。'),
                        ('互指壳', '{{:錦瑟}}'),
                        ('本页↑回指', '↑ [[全唐詩/卷539#錦瑟'),
                        ('双另折叠串', '五十{{另|絃|弦}}，一{{另|絃|弦}}'),
                        ('本页notes三连', '{{唐詩三百首}}{{Textquality|100%}}↑'),
                        ('无空格排版', '| times=唐'),
                        ('唐诗分类行', '[[Category:唐诗]]'),
                        ('诗原样块', '錦瑟無端五十{{另|絃|弦}}')):
    if _domain(_needle):
        raise SystemExit(f'首引前提破了：「{_needle}」（{_first}）既往有引（{_domain(_needle)}）——须重设计')

BG = {
    'bg-010-scene': (
        '八句是一架瑟上的终身账（2/2/2/2 起两句入眼前层）：锦瑟无端五十弦，'
        '一弦一柱思华年——瑟为什么是五十弦？「无端」（「錦瑟無端五十{{另|絃|弦}}，'
        '一{{另|絃|弦}}一柱思華年。」）。此后的六个意象只并置不解释：庄生晓梦、望帝春心、'
        '沧海月明、蓝田日暖、可待追忆、当时惘然。**此诗没有本事，本迁移不铸造本事**'
        '（适梦/悼亡/自悼诸旧说一律不裁决——引文一字不能裁决）。'
        'ws 诗页：**一枚诗行内两枚 {{另|絃|弦}} 折叠——全 ws 库独串**（机器断言：'
        '该串全库仅此页有；异文絃/弦只页内折叠，无 <ref> 无 {{reflist}} 无 from 行——'
        '与 V070 三件套页恰成两极）；**notes 三连一行**：{{唐詩三百首}}+{{Textquality|100%}}'
        '+↑底本回指挤在同一 notes 值里（V069 是↑+评级在 notes、三百首在 header 外尾——'
        '顺序形态相反，照登）；页尾分类仅两行、**无 [[Category:李商隱]]**'
        '（李商隱署名 21 页中无作者分类仅 3 页：春雨/籌筆驛/錦瑟——机器断言；'
        '整理者分类动作非史料声明、不升格，V048 判例）；无空格排版「| times=唐」照登。'
        '**此诗正文系第二引（上限用满第十九例）**：V018 已引句读式'
        '（「錦瑟無端五十絃，……只是當時已惘然。」——絃已展开），本迁移改引 ws 页 poem 块'
        '**存原样**：八句带句读、首行两枚 {{另|絃|弦}} 原样保留（各从其录；'
        '生成时断言 V018 句读式引文不重开）；异文絃/弦只登记不裁决；此后此诗正文关闭。'),
    'bg-010-city': (
        '卷539 侧是本迁移最特殊的一块——**同一首诗，两个页面互相指向对方**：'
        'ws 诗页 notes 带「↑ [[全唐詩/卷539#錦瑟|全唐詩·卷五百三十九]]」向上回指卷页，'
        '而卷539 的本篇正文恰恰是「==[[錦瑟]]==」+「{{:錦瑟}}」向下转引诗页——'
        '**底本声明与转引方向相反：底本是个循环指针**（V018 底本字段「全唐詩」指向 539，'
        '539 正文又是 ws 页的转引；机器断言：{{:錦瑟}} 壳恰一，壳外全卷无本篇正文——'
        '莊生/望帝/蝴蝶/杜鵑/惘然/華年/追憶/藍田/五十絃/錦瑟無端/思華年 全零，'
        '春心/無端/滄海各恰一皆他诗闭域）。绑定形态至此三角齐：V069 诗页单向↑回指、'
        'V070 卷页单向{{:}}转引、**本篇同一首诗两面互指**——V070 说「双向绑定集齐」'
        '是两个方向各见过一次，本篇是**两个方向同时在场**（闭环）。壳本身就是证据：'
        '编诗者视此诗归属已定、不必重抄。**全唐诗语料里本篇六整句零存在**'
        '（机器断言：錦瑟無端五十/莊生曉夢迷蝴蝶/……/只是當時已惘然 七段全零）——'
        '**此诗以宾语在他诗里活在《全唐诗》**：「錦瑟」全唐诗恰四=225 杜甫'
        '「何時詔此金錢會，暫醉佳人錦瑟旁」+539 壳二+540 李賀《房中曲》'
        '「歸來已不見，錦瑟長於人」——杜甫酒边的锦瑟、李贺悼亡的锦瑟，都不是这一首。'
        '（本层零 relation。）**本迁移零新建 source（连续第三首）**：'
        'source-ws-t300-010 与 source-quantangshi-539 皆 V018 所立，539 第六次复用。'),
    'bg-010-world': (
        '**诗里那一架瑟，通鉴全库没有；通鉴唯一的惘然，是太后慰谕老臣的诏书**'
        '（同字两界第十六形态·惘然形态首见）：'
        '通鉴「**錦瑟/莊生/庄生/望帝/杜鵑/蝴蝶/春心/華年/無端/追憶/滄海月/曉夢**」'
        '全零（机器断言）——诗面典故群史部一个都不接。可通鉴不是没有惘然与沧海：'
        '① 「**惘然**」恰一，在光宅元年（甲申，六八四）：太后代亲政，刘仁轨上疏'
        '以吕后祸败申规戒，太后使武承嗣赍玺书慰谕：「**初聞此語，能不惘然；'
        '靜而思之，是為龜鏡**」——**史部的惘然有龟镜**：惘然之后静而思之，'
        '老臣的逆耳话被供为镜鉴；**诗的惘然没有**：「只是當時已惘然」——'
        '当时已惘然，何况成追忆，无镜可照（对照判决，非史实因果——通鉴不记这首诗本身）；'
        '② 「**滄海**」恰二：神功元年（丁酉，六九七）狄仁傑上疏「**東拒滄海，'
        '西阻流沙，北橫大漠，南阻五嶺**，此天所以限夷狄而隔中外也」——沧海是国界；'
        '天復二年（壬戌，九〇二）冯弘鐸兵败将入海，杨行密说之「**胡為自棄滄海之外**！'
        '吾府雖小，足以容公之眾」——沧海是弃路。**史部的沧海分中外、标弃路；'
        '诗的沧海藏珠泪**（「滄海月明珠有淚」——同一个沧海，史部用来划界，'
        '诗用来藏一颗眼泪）；'
        '③ 「**淚**」恰三（215/236/256 闭域），最近诗面的一条在天寶六年（丁亥，七四七）'
        '三司按王忠嗣，哥舒翰「**力陳忠嗣之冤，且請以己官爵贖忠嗣罪；上起，入禁中，'
        '翰叩頭隨之，言與淚俱**」——**史部的泪落在官位旁边**（叩头随驾、请以官爵赎罪）；'
        '诗的泪在月明的海上，无官可赎。「珠」恰五十七/「煙」恰二十六/「五十」恰一百七十二'
        '在册零入引（闭域档扫）。本层零铸造零 relation。'),
    'bg-010-person': (
        '旧传李商隐段（**简化字录入**，V016 locator 同款标注，引文照登简体原样）'
        '首引一段（零域）：「**商隐能为古文，不喜偶对。**」\n'
        '史部记他早年的文学习惯：能写古文，不喜欢对偶——**而《锦瑟》恰恰是律对'
        '最工的诗**：莊生对望帝、沧海对蓝田、晓梦梦迷对春心托—（读法声明：'
        '「不喜偶对的人留下最工偶对的诗」是读者的一句感叹，非史实因果）。\n'
        '**写尽锦瑟的人，传里无一瑟字**：段内诗面十六字「錦/瑟/絃/弦/柱/蝶/望帝/'
        '杜鵑/滄海/藍田/珠/淚/煙/惘然/追憶/華年」全零（机器断言——瑟、弦单字亦零，'
        '比历篇段级零证更强），连「梦」字也无。史部给他的是另一串事：令狐楚幕、'
        '今体章奏、茂元娶、牛李党隙（V016 在册诸句零重开，域断言）——'
        '传把这个人写成官历与党籍，诗把这个人写成一架瑟（读法声明）。\n'
        '本诗 ws 页 notes **有**回指注（V070 空壳的反面：注的有无本身也是形态，'
        '且本页注与卷页壳互指）；certainty 不覆盖任何系年，诗 time.span/event.name/'
        'written_during 仍零铸造（audit 硬卡）。'),
}
CLAIMS = {
    'claim-bg-010-scene': (
        'FACT', 'LIKELY',
        '八句七律本文**第二引上限用满第十九例**：V018 句读式一引在先'
        '（「錦瑟無端五十絃，……只是當時已惘然。」——絃已展开），本迁移二引 ws 页 poem 块'
        '**存原样**（八句带句读、首行两枚 {{另|絃|弦}} 原样保留，各从其录；生成时断言'
        'V018 句读式引文不重开），此后正文对后来迁移关闭；异文絃/弦只页内折叠登记不裁决'
        '（无 <ref> 无 {{reflist}} 无 from 行——与 V070 三件套页恰成两极）；'
        '**一枚诗行双 {{另}} 全 ws 库独串**（机器断言）；**notes 三连一行**'
        '（三百首+100%+↑回指同值——V069 顺序形态相反）；页尾分类仅两行无作者分类'
        '（21 页署名中仅 3 页——机器断言；分类非史料声明不升格 V048）；'
        '无空格排版「| times=唐」照登；本事诸旧说（适梦/悼亡/自悼）一律不裁决，系年零铸造。'),
    'claim-bg-010-city': (
        'FACT', 'LIKELY',
        '本篇系**互指循环指针**：ws 诗页 notes「↑ [[全唐詩/卷539#錦瑟|全唐詩·卷五百三十九]]」'
        '向上回指，卷539 本篇正文恰为「{{:錦瑟}}」向下转引——底本声明与转引方向相反'
        '（V018 底本字段「全唐詩」指向 539、539 正文又是诗页转引；机器断言：壳锚唯一）；'
        '绑定三角至此齐（V069 单向↑/V070 单向{{:}}/本篇互指闭环——V070 是两个方向各见一次，'
        '本篇是同时在场）；壳外 539 全卷无本篇正文（莊生/望帝/蝴蝶/杜鵑/惘然/華年/追憶/'
        '藍田/五十絃/錦瑟無端/思華年 全零；春心/無端/滄海各恰一皆他诗闭域——机器断言）；'
        '**本篇六整句全唐诗语料零存在**而「錦瑟」恰四：杜甫「何時詔此金錢會暫醉佳人錦瑟旁」+'
        '李賀《房中曲》「歸來已不見錦瑟長於人」+壳二——**此诗以宾语在他诗里活在《全唐诗》**；'
        '**零新建 source 连续第三首**（source-ws-t300-010 与 source-quantangshi-539 皆'
        'V018 所立，539 第六次复用——壳本身就是证据）。'),
    'claim-bg-010-world': (
        'FACT', 'LIKELY',
        '通鉴「錦瑟/莊生/庄生/望帝/杜鵑/蝴蝶/春心/華年/無端/追憶/滄海月/曉夢」全零'
        '（机器断言）而惘然沧海泪在他字：「惘然」恰一在光宅元年甲申六八四太后慰谕刘仁轨'
        '（「初聞此語能不惘然靜而思之是為龜鏡」——**史部的惘然有龟镜，诗的惘然没有**）；'
        '「滄海」恰二分神功元年丁酉六九七狄仁傑疏（東拒滄海西阻流沙——国界）与天復二年'
        '壬戌九〇二杨行密说冯弘鐸（胡為自棄滄海之外——弃路）——**史部的沧海分中外弃路，'
        '诗的沧海藏珠泪**；「淚」恰三（215/236/256），天寶六年丁亥七四七哥舒翰救王忠嗣'
        '「力陳忠嗣之冤請以己官爵贖之叩頭隨之言與淚俱」——**史部的泪落在官位旁边，'
        '诗的泪在月明的海上无官可赎**（同字两界第十六形态·惘然形态首见，audit 硬卡）；'
        '珠57/煙26/五十172 在册零入引；certainty 不覆盖任何系年，'
        'time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-010-person': (
        'FACT', 'LIKELY',
        '旧传李商隐段（简化字录入照登原样）首引一段零域=「商隐能为古文，不喜偶对。」'
        '（传区间归属机器断言）；**段级十六诗字全零**：段内錦/瑟/絃/弦/柱/蝶/望帝/杜鵑/'
        '滄海/藍田/珠/淚/煙/惘然/追憶/華年全零（机器断言，瑟弦单字亦零）——'
        '**写尽锦瑟的人传里无一瑟字**；「不喜偶对的人留下最工偶对的诗」「官历党籍对一架瑟」'
        '系读法声明非史实因果；本诗 ws 页 notes 有回指注（V070 空壳的反面）；'
        'V016 在册句（字义山/开成二年/岭表/三十六体/未几病卒/大中末/仲郢坐/还郑州）'
        '零重开（域断言）；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-010-scene', 'source-ws-t300-010',
     '页面 錦瑟（《唐詩三百首》第 10 首选本页，页题裸名；title+无空格排版 times+author+poem 块'
     '以「……」相连——poem 块**存原样**：八句带句读、首行一枚诗行内两枚 {{另|絃|弦}} 折叠'
     '（絃/弦异文只页内登记不裁决，无 <ref> 无 {{reflist}} 无 from 行——与 V070 三件套页'
     '恰成两极）；正文第二引上限用满第十九例（V018 句读式一引在先，本迁移引原样面，'
     '各从其录，生成时断言 V018 句读式引文不重开）',
     join(WS_TITLE, WS_TIME, WS_AUTHOR, WS_POEM)),
    ('claim-bg-010-city', 'source-quantangshi-539',
     '卷五百三十九·李商隱《錦瑟》**空壳转引块**（「==[[錦瑟]]==」+「{{:錦瑟}}」——'
     '壳外全卷无本篇正文一字：莊生/望帝/蝴蝶/杜鵑/惘然/華年/追憶/藍田/五十絃/錦瑟無端/'
     '思華年 全零机器断言；春心/無端/滄海各恰一皆他诗闭域；**与本页 notes ↑回指互指**'
     '——底本声明与转引方向相反，循环指针（V069 单向↑/V070 单向{{:}}之三角第三态）；'
     '锚全唐诗唯一；源行系 V018 已立、本迁移第六次复用零新建）',
     V539_SHELL),
    ('claim-bg-010-city', 'source-ws-t300-010',
     '页面 錦瑟（notes 三连一行整值入引（{{唐詩三百首}}+{{Textquality|100%}}+↑底本回指'
     '同挤一个 notes 值——V069 顺序形态相反；↑ 指向恰是转引本篇的 539 壳——互指之诗页侧）'
     '+页尾分类两行（简繁并立；**无 [[Category:李商隱]]**——李商隱署名 21 页中无作者'
     '分类仅 3 页机器断言；分类行系整理者分类动作：非史料声明、不升格，V048 判例）；'
     '本迁移零新建源连续第三首）',
     join(WS_NOTE3, WS_CAT2)),
    ('claim-bg-010-world', 'source-zizhi-tongjian-events',
     '卷二百零三·光宅元年（甲申，六八四）太后慰谕刘仁轨诏（「初聞此語能不惘然靜而思之'
     '是為龜鏡」——史部唯一惘然有龟镜）……卷二百零六·神功元年（丁酉，六九七）狄仁傑上疏'
     '「東拒滄海西阻流沙」（国界）……卷二百六十三·天復二年（壬戌，九〇二）杨行密说'
     '冯弘鐸「胡為自棄滄海之外」（弃路）……卷二百一十五·天寶六年（丁亥，七四七）哥舒翰'
     '救王忠嗣「叩頭隨之言與淚俱」（泪落官位旁）；通鉴诗面錦瑟/莊生等十二语全零，'
     '惘然恰一/滄海恰二/淚恰三（四段逐字入引为判决证据）',
     join(TJ_WR, TJ_CH1, TJ_CH2, TJ_LEI)),
    ('claim-bg-010-person', 'source-jiutangshu-wenyuan',
     '舊唐書卷一九〇下·李商隱（**简化字录入**照登原样，V016 locator 同款标注）'
     '（「商隐能为古文，不喜偶对」段（史部记他早年的文学习惯——全库查重恰零域首引；'
     '传区间归属机器断言；段内诗面十六字錦/瑟/絃/弦/柱/蝶/望帝/杜鵑/滄海/藍田/珠/淚/'
     '煙/惘然/追憶/華年全零——写尽锦瑟的人传里无一瑟字；「最工偶对」系读法声明；'
     'V016/V070 在册句零重开）',
     JTS_W),
]
BG_LINES = {'bg-010-scene': (1, 2), 'bg-010-city': (3, 4),
            'bg-010-world': (5, 6), 'bg-010-person': (7, 8)}
BG_AUDIENCE = {'bg-010-scene': 'PRIMARY', 'bg-010-city': 'JUNIOR',
               'bg-010-world': 'SENIOR', 'bg-010-person': 'JUNIOR'}
BG_TITLES = {'bg-010-scene': '眼前：五十弦的无端',
             'bg-010-city': '这座城：互相指向的两个页面',
             'bg-010-world': '这个天下：有龟镜的惘然',
             'bg-010-person': '这个人：传里无一瑟字'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 52 首·八句七律 2/2/2/2）；史实句均有逐字引证；'
                 '系年第四十六次判决（题证系列第卅四状·锦瑟无端与能不惘然）'
                 '「诗里那一架瑟通鉴全库没有；通鉴唯一的惘然是太后慰谕老臣的诏书」——'
                 '同字两界第十六形态·惘然形态首见：通鉴錦瑟/莊生/庄生/望帝/杜鵑/蝴蝶/'
                 '春心/華年/無端/追憶/滄海月/曉夢全零（机器断言）；'
                 '「惘然」恰一在光宅元年甲申六八四太后使武承嗣赍玺书慰谕刘仁轨'
                 '（「初聞此語能不惘然靜而思之是為龜鏡」——**史部的惘然有龟镜'
                 '（回思即规戒），诗的惘然没有**（只是當時已惘然，无镜可照））；'
                 '「滄海」恰二分神功元年丁酉六九七狄仁傑疏（東拒滄海西阻流沙北橫大漠'
                 '南阻五嶺——国界）与天復二年壬戌九〇二杨行密说冯弘鐸（胡為自棄滄海'
                 '之外——弃路）——**史部的沧海分中外弃路，诗的沧海藏珠泪**；'
                 '「淚」恰三（215/236/256 闭域），天寶六年丁亥七四七哥舒翰救王忠嗣'
                 '「力陳忠嗣之冤請以己官爵贖之叩頭隨之言與淚俱」——**史部的泪落在'
                 '官位旁边，诗的泪在月明的海上无官可赎**；珠57/煙26/五十172 在册闭域；'
                 '**绑定形态三角齐·互指循环指针首见**：ws 诗页 notes「↑ 卷539#錦瑟」'
                 '向上回指、卷539 本篇正文恰为「{{:錦瑟}}」向下转引——同一首诗两面互指，'
                 '底本声明与转引方向相反（V069 单向↑/V070 单向{{:}}各见一次，本篇'
                 '**同时在场成闭环**；壳外 539 全卷无本篇正文——莊生/望帝/蝴蝶/杜鵑/'
                 '惘然/華年/追憶/藍田/五十絃/錦瑟無端/思華年 全零机器断言，'
                 '春心/無端/滄海各恰一皆他诗闭域）；**本篇六整句全唐诗语料零存在**'
                 '而「錦瑟」恰四：杜甫「何時詔此金錢會暫醉佳人錦瑟旁」+李賀《房中曲》'
                 '「歸來已不見錦瑟長於人」+539 壳二——**此诗以宾语在他诗里活在《全唐诗》**；'
                 '**零新建 source 连续第三首**（source-ws-t300-010 与 source-quantangshi-539'
                 '皆 V018 所立，539 第六次复用——壳本身就是证据）；正文第二引上限用满'
                 '第十九例（V018 句读式在先+本迁移 ws 原样面含双 {{另|絃|弦}}，各从其录，'
                 'V018 句读式引文零重开断言）；异文絃/弦只页内折叠登记不裁决（无 <ref>'
                 '无 {{reflist}} 无 from 行——与 V070 三件套页恰成两极）；**一枚诗行双'
                 '{{另}} 全 ws 库独串**+**notes 三连一行**（三百首+100%+↑同值——V069'
                 '顺序形态相反）+**页尾分类仅两行无 [[Category:李商隱]]**（21 页署名中'
                 '仅 3 页：春雨/籌筆驛/錦瑟——机器断言；非史料声明不升格 V048）'
                 '+无空格排版「| times=唐」照登；本事诸旧说一律不裁决；PERSON 旧传'
                 '简化段首引一段（商隐能为古文不喜偶对——**史部记他文学习惯，锦瑟恰是'
                 '律对典范**：读法声明）；**段内十六诗字全零（瑟弦单字亦零）：写尽锦瑟'
                 '的人传里无一瑟字**——段级零证机器断言；V016 在册句零重开（域断言）；'
                 'KNOWN 零如实记录（第廿七例，audit 反向断言）；判例关键语零入引文。'
                 for k in BG}


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
    A("""-- V071：李商隱《錦瑟》(work-t300-010) 四层背景（阶段 D 第 52 首·惘然两界）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V033、V035、V039、V048、V053、V057、V058、
--       V059、V060、V061、V062、V063、V064、V065、V066、V067、V068、V069、V070 已执行
--       （work-t300-010 与其 text-work-t300-010-ws（version_code=ws-raw，八行带句读）
--       与其源 source-ws-t300-010（edition 字段即底本「全唐詩」）都是 V018 的行；
--       source-quantangshi-539 是 V018 已立的卷539 卷页源（V018/V067/V068/V069/V070 已引，
--       本迁移第六次复用——**这次引到的是与诗页互指的空壳 {{:錦瑟}}**）；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       source-jiutangshu-wenyuan 是 V016 已立的旧唐书文苑传源（李商隐传在此，简化字录入）；
--       判例在册句（义山/开成二年/岭表/三十六体/未几病卒/大中末/仲郢坐/还郑州 V016、
--       锦瑟句读式正文与春眠不覺曉/穆王何事不重來/嵩雲秦樹/茂陵秋雨/乘興南遊 V018、
--       家書抵萬金/感時花濺淚 V011/V017、別來滄海事 V033、得宋之問藍田别墅 V035/V039、
--       凝碧池頭奏筦絃 V026/V035、樹杪百重泉 V063、雲能合長生藥 V068、
--       ↑ [[全唐詩/卷539#寄令狐郎中 V069、{{:夜雨寄北}}/秋霖双案/天子何在/亞貶循州/
--       俄而茂元卒/检校水部员外郎 V070）只对照不重开。
--       **本迁移零新建 source（连续第三首）——
--       audit 断言本文件零 poetry_source INSERT、回滚零 source 删除。**
--
-- 数据源（可复现）：emit_v071.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/錦瑟.txt（一枚诗行双 {{另|絃|弦}} 全库独串+notes 三连一行+页尾分类两行
--   无作者分类+无空格排版 times+poem 存原样+无注表无<ref>无from行）、
--   全唐詩卷539（锚 ==[[錦瑟]]== 全唐诗唯一+壳 {{:錦瑟}} 恰一+
--   **壳外全卷无本篇正文十一语全零**+春心/無端/滄海各恰一闭域）、
--   舊唐書卷190下（李商隐段首引一段+**段内诗面十六字全零（瑟弦单字亦零）**+段边界断言）、
--   通鑑卷203/206/215/263（四段逐字入引+四处年标题窗口断言：光宅元年六八四/
--   神功元年六九七/天復二年九〇二/天寶六年七四七）+
--   通鑑 75 卷负证计数扫描（錦瑟/莊生/庄生/望帝/杜鵑/蝴蝶/春心/華年/無端/追憶/滄海月/
--   曉夢 全零+惘然恰一在 203/滄海恰二分 206,263/淚恰三 215,236,256/能不惘然恰一/
--   是為龜鏡恰一/珠57/煙26/五十172 闭域）+
--   全唐詩负证（錦瑟恰四 225/539×2/540+本篇六整句全库零+房中曲恰一/錦瑟長於人恰一/
--   何時詔此金錢會恰一）+
--   既有迁移引文域逐句查重——传区间归属、二引/零重开/首引零域前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 background_line（八句七律 **2/2/2/2 顺次**（V020 以来八句篇常规）：
--   scene→1,2 city→3,4 world→5,6 person→7,8，绑 text-work-t300-010-ws 的 8 行）+ 不碰 poetry_text_line。
-- 不做：**不新建任何 source（连续第三首）**；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「通鉴唯一的惘然是太后诏——史部的惘然有龟镜，诗的惘然没有」）：
--   * 「惘然两界」系通鉴四段逐字入引支撑的对照判决，非史实因果——通鉴不记这首诗本身；
--   * 「本事」（适梦/悼亡/自悼诸旧说）不裁决——本迁移引文一字不能裁决；系年零铸造；
--   * 「不喜偶对的人留下最工偶对的诗」「官历党籍对一架瑟」「藏珠泪」标明读法声明；
--     异文絃/弦只页内折叠登记不裁决；
--   * 通鉴惘然恰一是太后慰谕诏（光宅元年）、滄海恰一是狄疏国界恰一是杨行密弃路（天復二年）、
--     淚恰三是哥舒翰/杜甫语/御袍（与诗只共享字面，绝不当同一事）；
--   * 正文第二引上限用满：V018 句读式一引在先，本迁移引 ws 页 poem 块存原样面——
--     各从其录，V018 句读式引文不重开（生成时硬断言），此后此诗正文关闭；
--   * 「互指循环指针」「六整句只活在诗页」「双{{另}}独串」「notes 三连」「分类无作者」
--     均照登不判；
--   * 通鉴珠57/煙26/五十172 在册零入引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第廿七例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * V011/V016/V018/V026/V033/V035/V039/V053/V063/V066–V070 已引诸句只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 70，不含 71
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-010-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-010','source-quantangshi-539');
--    -- 两行（均 V018 所立，本迁移不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-010-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-010-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-010';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-010-%';  -- 四行全 LIKELY
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-010';   -- 恰 1（V018 所立）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-010'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-010';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-010-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V071_rollback.sql（按 id 全枚举删除；**零 source 删除**——
--   source-ws-t300-010 与 source-quantangshi-539 皆 V018 所立，绝不删）
START TRANSACTION;""")

    A('\n-- ---------- 0. 零新建 source（连续第三首；两源皆 V018 所立复用） ----------')

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
    brows = [{'id': k, 'work_id': 'work-t300-010',
              'layer': {'bg-010-scene': 'SCENE', 'bg-010-city': 'CITY',
                        'bg-010-world': 'WORLD', 'bg-010-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（八句七律 2/2/2/2 顺次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-010-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 71, 'Li Shang-yin''s Inscribed Harps (work-t300-010) background layers (stage-D poem 52, eight-line regulated verse 2/2/2/2): dating verdict forty-six, thirty-fourth shape of the title-evidence series -- the harp in the poem is nowhere in the whole Zizhi Tongjian, and the histories'' one and only "wangran" (dazed) is an empress dowager''s console to an old minister. Same-character-two-realms, sixteenth shape: the wangran shape, first seen. The Tongjian scores zero on every allusion of the poem -- jinse (inscribed harp), Zhuangzi, Wangdi, the cuckoo, the butterfly, spring heart, florid years, "without reason", "recollecting", "the moon over the dark blue sea", "dawn dream" (machine-asserted). Yet "wangran" appears exactly once, in Guangzhai 1, jiashen, 684: when Liu Ren-gui remonstrated by citing the fall of the吕 clan, the empress dowager had Wu Chengsi carry a seal-letter consoling him: "at first hearing these words, how could I not feel dazed; ponder them in stillness, and they become a mirror" -- the histories'' daze has a mirror (reflection turns into admonition); the poem''s daze has none (it was already dazed at the time -- 只是當時已惘然 -- no mirror to hold it up). "Dark blue sea (canghai)" appears exactly twice, in two different worlds: in Shengong 1, dingyou, 697, Di Renjie memorialises that "east it bars the dark blue sea, west the flowing sands, north the great desert, south the five ridges -- this is how heaven limits the barbarians and separates inside from outside" (a frontier); in Tianfu 2, renxu, 902, Yang Xingmi persuades Feng Hongduo: "why cast yourself beyond the dark blue sea!" (a road of no return) -- the histories'' dark blue sea draws borders and marks desperate roads; the poem''s dark blue sea hides a pearl''s tear. "Tears" appear exactly three times, the closest in Tianbao 6, dinghai, 747, when Geshu Han pleads for the wrongfully condemned Wang Zhongsi: "he kowtowed following the emperor into the forbidden precincts, his words and his tears together" -- the histories'' tears fall beside an office, begged away from a throne; the poem''s tear sits on the moonlit sea with no office to redeem it. The binding forms of scroll page and poem page now form a closed triangle: V069 pointed up (the poem page''s arrow), V070 pointed down (the scroll page''s transclusion), and this poem is pointed at from both sides at once -- the ws page''s notes carry the back-reference arrow to 卷539#錦瑟 while the scroll page''s text of this very poem is the transclusion stub {{:錦瑟}} -- base-text declaration and transclusion direction reversed: the base text is a circular pointer (machine-asserted: exactly one stub; outside the shell, not one phrase of this poem anywhere in juan 539 -- Zhuangzi/Wangdi/butterfly/cuckoo/wangran/florid years/recollecting/Lantian/fifty-strings all zero; three lone other-poem fragments closed out). All seven full lines of this poem score zero across the whole Quan Tangshi corpus, yet the two words "錦瑟" appear exactly four times -- Du Fu''s "drunk a while beside a lady''s inscribed harp", Li He''s "home again, it is no longer seen; the inscribed harp lingers longer than the person" from his Chamber Song, plus the two shell graphs: this poem lives inside the Quan Tangshi only as other poems'' object; the text itself lives only on the poem page. ZERO new sources, third poem running (audit asserts zero poetry_source INSERT and zero source deletion); both sources were established by V018, the 539 source at its sixth reuse. Body use-ceiling reached, nineteenth instance: V018 quoted the punctuated abbreviation (fifty strings... already dazed at the time); this migration quotes the ws page''s raw poem block, first line keeping both inline {{另}} variant folds (xian vs. xian-simplified) -- registering only, never adjudicating, and the apparatus here is the mirror opposite of V070''s page (no <ref>, no reflist, no from-chain; machine-asserted unique two-fold line across the whole ws corpus); the notes field packs the anthology tag, the 100 percent rating and the base-text arrow into one value (reverse order-shape of V069); the category footer is just two lines with no author category (only three of the 21 Li Shang-yin pages, machine-asserted; editorial, not a source claim, not upgraded, V048 precedent); the spacing form | times=唐 logged as-is. The poem''s old biographical readings (dream, mourning, self-mourning) are all left undecided -- no本事 is cast; dating stays unforged. PERSON first-cites one zero-domain simplified JTS passage -- "Shang-yin could write old-style prose and disliked parallel pairs" -- while the biography segment holds not one of the sixteen character-words of the poem''s imagery, neither se nor xian even singly (machine-asserted): the man who wrote the harp out of existence leaves not one harp-graph in his biography; "the man who disliked parallel pairs left the most perfectly paired poem" is a reading declared, not a fact. KNOWN zero honestly recorded (twenty-seventh instance, audit reverse-asserts); closed precedent keywords (including V033''s sea of parting, V035/V039''s Lantian villa and V070''s empty shell) stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 71);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V071 精确回滚：只删 V071 插入的行（id 全枚举）。',
         '-- **零 source 删除**：source-ws-t300-010（V018 所立的 ws 选本页源）与',
         '-- source-quantangshi-539（V018 所立的卷539 卷页源）本迁移皆复用，绝不删；',
         '-- work-t300-010 本体、其 text_line 8 行都是 V018 的行，绝不删；',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 71;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_TIME, WS_AUTHOR, WS_NOTE3, WS_POEM, WS_CAT2, V539_SHELL,
              TJ_WR, TJ_CH1, TJ_CH2, TJ_LEI, JTS_W]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # SCENE：双{{另}}独串必须逐字入引 + V018 句读式引文零重开
    scene_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-010-scene')
    if scene_ws.count('{{另|絃|弦}}') < 2:
        bad.append('{{另|絃|弦}} 双枚未逐字入 SCENE 引文（全库独串照登硬卡）')
    if '錦瑟無端五十{{另' not in scene_ws:
        bad.append('原样块首行未入 SCENE 引文（第二引第十九例硬卡）')
    if '只是當時已惘然。' not in scene_ws:
        bad.append('原样块末句未入 SCENE 引文（存原样硬卡）')
    if '錦瑟無端五十絃，……只是當時已惘然。' in cited:
        bad.append('V018 句读式引文重开了——本迁移引原样面，句读式不重开')
    if '| times=唐' not in scene_ws:
        bad.append('无空格排版形态未入 SCENE 引文（照登硬卡）')
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-010-city' and s == 'source-ws-t300-010')
    if '↑ [[全唐詩/卷539#錦瑟|全唐詩·卷五百三十九]]' not in city_ws:
        bad.append('↑回指注未逐字入 CITY 引文（互指诗页侧照登硬卡）')
    if '[[Category:李商隱]]' in city_ws:
        bad.append('CITY 分类引文混入作者分类——本页无 [[Category:李商隱]] 正是标本')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-010-city' and s == 'source-ws-t300-010'):
        bad.append('CITY ws locator 须含「不升格」声明（分类行三重断言失效）')
    city_q = next(ex for c, s, _, ex in CITATIONS if s == 'source-quantangshi-539')
    if '{{:錦瑟}}' not in city_q:
        bad.append('空壳转引未逐字入 CITY 引文（循环指针之卷页侧照登硬卡）')
    if '莊生' in city_q or '惘然' in city_q or '藍田' in city_q or '華年' in city_q:
        bad.append('CITY 卷页引文混入本篇正文语——壳外无正文一字正是本迁移的标本')
    c_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-010-city' and s == 'source-quantangshi-539')
    if '互指' not in c_loc or '循环指针' not in c_loc:
        bad.append('CITY 卷页 locator 须含「互指/循环指针」声明（绑定三角第三态硬卡）')
    # WORLD：四段史文必须在引文内；诗语零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-010-world')
    for tok in ('初聞此語，能不惘然；靜而思之，是為龜鏡。', '東拒滄海，西阻流沙',
                '胡為自棄滄海之外！', '力陳忠嗣之冤', '言與淚俱'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（四段必须入引）')
    for tok in ('錦瑟', '莊生', '望帝', '杜鵑', '蝴蝶', '藍田', '曉夢', '追憶', '華年'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文）')
    w_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-010-world')
    if '惘然' not in w_loc or '滄海' not in w_loc or '淚' not in w_loc:
        bad.append('WORLD locator 须点出惘然/滄海/淚（三柄词声明）')
    # PERSON 首引句必须在引文内 + 在册句零重开
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-010-person')
    for tok in ('商隐能为古文', '不喜偶对'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺首引要素「{tok}」（简化字段首引照登硬卡）')
    for tok in ('{{:夜雨寄北}}', '君問歸期未有期', '↑ [[全唐詩/卷539#寄令狐郎中',
                '京兆尹黎幹奏秋霖損稼', '亞貶循州刺史', '俄而茂元卒', '检校水部员外郎',
                '天子何在', '公家無恙', '商隐随亚在岭表累载', '李商隐，字义山，怀州河内人。',
                '开成二年', '未几病卒', '大中末', '仲郢坐', '还郑州', '别来沧海事',
                '別來滄海事', '得宋之問藍田别墅', '凝碧池頭奏筦絃', '樹杪百重泉',
                '家書抵萬金', '感時花濺淚', '春眠不覺曉', '穆王何事不重來',
                '嵩雲秦樹久離居', '茂陵秋雨病相如', '乘興南遊不戒嚴', '孫處約諫書',
                '雲能合長生藥', '何處更求長生', '穆天子', '锦瑟无端五十',
                '只是当时已惘然', '沧海月明', '蓝田日暖'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    if BG_LINES != {'bg-010-scene': (1, 2), 'bg-010-city': (3, 4),
                    'bg-010-world': (5, 6), 'bg-010-person': (7, 8)}:
        bad.append('八句 background_line 须 2/2/2/2 顺次（V020 以来八句篇常规）')
    if len(re.findall(r"text-work-t300-010-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # **零新建 source**（连续第三首）
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
        bad.append("V071 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V071 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-010' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V071 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-010' AS subject_id" in sql:
        bad.append('V071 的 claim 主语应全部是 bg-010-*，work-t300-010 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V071 不碰 poetry_text_line')
    body_all = ''.join(BG.values())
    if '惘然形态首见' not in body_all:
        bad.append('BG 须含「惘然形态首见」（同字两界第十六形态）声明')
    if '龟镜' not in body_all:
        bad.append('BG/WORLD 须含「史部的惘然有龟镜，诗的惘然没有」判决')
    if '循环指针' not in body_all:
        bad.append('BG/CITY 须含「互指循环指针」声明')
    if '三角' not in body_all:
        bad.append('BG/CITY 须含「绑定形态三角齐」声明')
    if '宾语' not in body_all:
        bad.append('BG/CITY 须含「此诗以宾语在他诗里活在《全唐诗》」判决')
    if '藏珠泪' not in body_all:
        bad.append('BG/WORLD 须含「诗的沧海藏珠泪」判决')
    if '无官可赎' not in body_all:
        bad.append('BG/WORLD 须含「诗的泪在月明的海上无官可赎」判决')
    if '只登记不裁决' not in body_all:
        bad.append('BG/SCENE 须含「异文只登记不裁决」声明')
    if '独串' not in body_all:
        bad.append('BG/SCENE 须含「一枚诗行双 {{另}} 全 ws 库独串」声明')
    if '无一瑟字' not in body_all:
        bad.append('BG/PERSON 须含「写尽锦瑟的人传里无一瑟字」段级零证声明')
    if '零新建' not in body_all:
        bad.append('BG/CITY 须含「零新建 source（连续第三首）」声明')
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
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 71)' not in vblk:
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 12 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（旧传李商隐段一首引句，段界 ==弟 羲叟==）；'
              f'四处年标题窗口断言（光宅元年六八四/神功元年六九七/天復二年九〇二/天寶六年七四七）；'
              f'负证机器复查五层（通鉴錦瑟/莊生/庄生/望帝/杜鵑/蝴蝶/春心/華年/無端/追憶/'
              f'滄海月/曉夢全零+惘然恰一在203+滄海恰二分206,263+淚恰三215,236,256+'
              f'能不惘然恰一/是為龜鏡恰一+珠57/煙26/五十172 闭域/全唐诗锚恰一+錦瑟恰四'
              f'225,539×2,540+壳恰一+壳外全卷十一语全零+春心/無端/滄海各恰一闭域+'
              f'本篇六整句全库零+房中曲/錦瑟長於人/何時詔此金錢會各恰一/'
              f'ws 双{{另}}独串全库+无注表无<ref>无from+分类两行无作者分类+21页中3页孤例档/'
              f'旧传段十六诗字全零（瑟弦单字亦零），快照变动即中止）；'
              f'前提全库查重硬卡十件+十三首引句零域断言；双{{另}}/↑回指/壳转引照登硬卡；'
              f'SCENE 正文原样面入引+V018 句读式引文零重开断言；CITY 互指/循环指针硬卡；'
              f'CITY「不升格」硬卡；四段通鉴史文入引+诗语零混入断言；'
              f'PERSON 首引要素入引硬卡+V016/V018/V033/V035/V039/V070 诸句零重开硬卡；'
              f'判例只引不重开断言（含 V033 別來滄海事/V035,V039 藍田别墅在内）；'
              f'八句 2/2/2/2 形制断言；零 KNOWN 反向断言；'
              f'**零新建 source 断言（INSERT 恰零+回滚零 source 删除）**——连续第三首；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
