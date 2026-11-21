#!/usr/bin/env python3
"""阶段 D 第 40 首：生成 V059——王維《雜詩三首·其二》(work-t300-146, V018 已立) 四层背景。

「为什么写」走到连题目本身都是问题（题证系列第廿二状）：**题有杂目，杂目在史部
七十五卷全零；诗问寒梅，寒梅在史部只无花可问**——通鉴 75 卷「雜詩」二字零命中：
「杂诗」是诗集自家人给「无题可归」的组诗起的类名，史部连这个名目都不收录；
而「梅」字通鉴 19 处**全是专名**（梅福/梅叔焉/梅祿啜/梅錄/黃梅/梅山/梅金錄——
人名与地名，「寒梅」「梅花」二字全零）——**史部有十九个梅字，一朵梅花都没有**；
问梅之问在史部无处可问（机器断言六连）。

**同字两界第四形态（V056 泪/V057 已矣/V058 琴之后）**：诗的「君自故鄉來」
故鄉是乡愁的方向；通鉴「故鄉」恰一处=tj-212 開元九年（辛酉，七二一）玄宗制
逃戸自首「或於所在附籍，或牒歸故鄉」——故鄉在史部是户籍行政的去向
（闭域+窗口机器断言，在册入引为判决证据）。**绮字三名**：诗「綺窗」之绮是
织品；通鉴「綺」恰四处：tj-196 紈綺/綾綺二处（丝帛之名）+ tj-236「綺為和王」+
tj-244「和王綺薨」（皇子名——同名有主，在册不引不牵合）。

CITY 层**组诗切选结构首录**：ws 页 title=「雜詩三首」而 **section=「二」**——
标题是整组、section 指其一：《唐詩三百首》从三首组诗里选了第二首，
切选动作就写在 header 字段里（section 字段承载选本动作首见——V054 section
装题异注、本篇 section 装选第几，同字段第二用途）；{{further|雜詩}} 消歧链接
**首见**——快照内「雜詩」页恰三（王維/沈佺期/無名氏，{{唐詩三百首}} 标记各在，
同名三首全入选本的机器断言）。底注锚点片段非空（同 V058 全锚形态）；
页 {{另}}/{{别}}/{{*}}/<ref> 四全零而 100%。卷128 源行 V026/V040 已立**零新源**；
卷128 本篇「一锚三桩」结构首见：篇题锚点恰一，三首各一转引桩
（{{:雜詩 (家住孟津河)}}/{{:雜詩 (君自故鄉來)}}/{{:雜詩 (已見寒梅發)}}）。

PERSON 层首引**旧传行迹三连**（全库查重三句既往零入引）：「歴右拾遺、監察御史、
左補闕、庫部郎中。」「服闋，拜吏部郎中。」「天寳末，為給事中。」——问故乡的
人，传里写他自己在官职上辗转（旧传单得；XTS 王维段「故鄉」「綺」「梅」全零，
旧传全卷「故鄉」亦零，机器断言）；V057 已引「柴毁骨立」句夹在三句之间——
**逐字跳过不重开**（audit 硬卡引文中无柴毁字样）。

四句绝句 1/1/1/1 形制第二次（V056 首用于李白，此为王维首用）；正文第二引上限
用满第七例（V018 text claim 一引在先，查重针取末句尾段「寒梅着花未」）。

用法: python3 -I emit_v059.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/雜詩__君自故鄉來_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS2 = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
V128 = pathlib.Path('/tmp/src-dl/quantangshi/vol128.txt').read_text(encoding='utf-8')
TJ212 = pathlib.Path('/tmp/src-dl/tongjian/tj-212.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 雜詩三首', '| title    = 雜詩三首', 'ws header title(整组题——选本选其第二)')
WS_SECTION = slice_between(WS, '| section  = 二', '| section  = 二', 'ws header section(二——选本切选动作在字段里,首见)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证)')
WS_FURTHER = slice_between(WS, '{{further|雜詩}}', '{{further|雜詩}}', 'ws 页首消歧链接(雜詩同名页,further首见)')
WS_NOTE = slice_between(WS, '| notes    = {{Textquality|100%}}↑ [[全唐詩/卷128#雜詩三首|全唐詩·卷128]]',
                        '全唐詩·卷128]]',
                        'ws 页底注(100%+底本指向锚点片段非空,同 V058 全锚形态)')
WS_CAT = slice_between(WS, '[[Category:五言絕句]]', '[[Category:五言絕句]]', 'ws 分类行(五言絕句——整理者分类;V048 分类行判例)')
WS_L1 = slice_between(WS, '君自故鄉來，應知故鄉事。', '故鄉事。', 'ws第1联(问乡事——乡在来人口中,连字面两现)')
WS_L2 = slice_between(WS, '來日綺窗前，寒梅着花未。', '寒梅着花未。', 'ws第2联(只问窗前寒梅花开了没——全诗落在一问)')
JTS_J1 = slice_between(JTS, '歴右拾遺、監察御史、左補闕、庫部郎中。', '庫部郎中。',
                       '旧传官历句(从未入引,PERSON 首引三连之一;居母丧句夹后逐字跳过)')
JTS_J2 = slice_between(JTS, '服闋，拜吏部郎中。', '吏部郎中。', '旧传服阕句(从未入引,PERSON 首引三连之二)')
JTS_J3 = slice_between(JTS, '天寳末，為給事中。', '天寳末，為給事中。', '旧传天宝末句(从未入引,PERSON 首引三连之三;整句自锚——尾片段為給事中。不唯一)')
TJ_GX = slice_between(TJ212, '州縣逃亡戶口聽百日自首，或於所在附籍，或牒歸故鄉，各從所欲。', '各從所欲。',
                      '通鉴开元九年逃戸自首制(故鄉通鉴唯一一处——户籍行政的去向;窗口断言)')
Q128 = slice_between(V128, '==[[雜詩 (王維)|雜詩三首]]==', '==[[雜詩 (王維)|雜詩三首]]==', '卷128 本篇篇题锚点(消歧锚,一锚)')
Q128_S1 = slice_between(V128, '{{:雜詩 (家住孟津河)}}', '{{:雜詩 (家住孟津河)}}', '卷128 组诗第一首转引桩')
Q128_S2 = slice_between(V128, '{{:雜詩 (君自故鄉來)}}', '{{:雜詩 (君自故鄉來)}}', '卷128 组诗第二首转引桩(本篇)')
Q128_S3 = slice_between(V128, '{{:雜詩 (已見寒梅發)}}', '{{:雜詩 (已見寒梅發)}}', '卷128 组诗第三首转引桩(已見寒梅發——组诗里寒梅有前文!)')

# ---------- 传区间归属复验（V036 立规） ----------
_xa = XTS2.find('==王維==')
_xm = re.search(r'\n==[^=\n]{1,10}==', XTS2[_xa + 8:])
_seg_x = XTS2[_xa:_xa + 8 + _xm.start()]
_ja = JTS.find('=王維=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
if not (0 <= _ja and '歴右拾遺' in _seg_j):
    raise SystemExit('切片越出王维段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ212, TJ_GX, '開元九年')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：雜詩类名全零；故鄉恰一=tj-212；梅恰19而寒梅/梅花/梅開/折梅/寄梅全零；綺恰四=丝帛+皇子名
if _alltj.count('雜詩') != 0:
    raise SystemExit('通鉴「雜詩」不再全零——类名不进史部的判决失效，须重读')
_gx = {n: t.count('故鄉') for n, t in _tjf.items() if '故鄉' in t}
if _gx != {'tj-212.txt': 1}:
    raise SystemExit(f'通鉴「故鄉」不是恰一处（实 {_gx}）——故鄉两界论断须重估')
_mei = sum(t.count('梅') for t in _tjf.values())
if _mei != 19:
    raise SystemExit(f'通鉴「梅」不再是 19 处（实 {_mei}）——十九梅无梅花的判决须重估')
for _w in ('寒梅', '梅花', '梅開', '折梅', '寄梅'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——史部无梅花的判决失效，须重读')
_qi = {n: t.count('綺') for n, t in _tjf.items() if '綺' in t}
if _qi != {'tj-196.txt': 2, 'tj-236.txt': 1, 'tj-244.txt': 1}:
    raise SystemExit(f'通鉴「綺」分布变了（实 {_qi}）——绮字三名论断须重估')
if '綺為和王' not in _tjf['tj-236.txt'] or '和王綺薨' not in _tjf['tj-244.txt']:
    raise SystemExit('皇子名「綺」的两句结构变了——同名有主在册须重读')
if _alltj.count('綺窗') != 0:
    raise SystemExit('通鉴「綺窗」不再全零——诗中绮窗在册论断失效')
# ② 全唐詩：雜詩题族 6 卷 20 处；本篇锚一桩三；寒梅五处唯 vol128 属本篇
_qs = {n: t.count('雜詩') for n, t in _qtf.items() if '雜詩' in t}
if _qs != {'vol047.txt': 7, 'vol126.txt': 3, 'vol128.txt': 5, 'vol225.txt': 1, 'vol286.txt': 3, 'vol340.txt': 1}:
    raise SystemExit(f'全唐詩「雜詩」题族册数变了（实 {_qs}）——题族在册数须重估')
if (V128.count('==[[雜詩 (王維)|雜詩三首]]==') != 1
        or V128.count('{{:雜詩 (家住孟津河)}}') != 1 or V128.count('{{:雜詩 (君自故鄉來)}}') != 1
        or V128.count('{{:雜詩 (已見寒梅發)}}') != 1):
    raise SystemExit('卷128 一锚三桩结构变了——组诗切选在册结构断言失效')
_hm = {n: t.count('寒梅') for n, t in _qtf.items() if '寒梅' in t}
if _hm != {'vol128.txt': 1, 'vol359.txt': 1, 'vol539.txt': 1, 'vol581.txt': 1, 'vol582.txt': 1}:
    raise SystemExit(f'全唐詩「寒梅」册数变了（实 {_hm}）——他卷寒梅在册不引须重估')
if _allq.count('綺窗') != 3:
    raise SystemExit(f'全唐詩「綺窗」不再是 3 处（实 {_allq.count("綺窗")}）——绮窗题族在册须重估')
# ③ ws：四标记全零 + 100% 恰一 + section=二 + further + 非空锚片段
if WS.count('{{另') or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页标记不再是全零——零标记页论断失效，须重读快照')
if (WS.count('{{Textquality|100%}}') != 1 or WS.count('卷128#雜詩三首|') != 1
        or WS.count('| section  = 二') != 1 or WS.count('{{further|雜詩}}') != 1):
    raise SystemExit('ws 页 100%/非空锚/section=二/further 结构变了——切选结构断言失效')
_zpages = sorted(pathlib.Path('/tmp/src-dl/ws-poems').glob('雜詩*.txt'))
if len(_zpages) != 3 or sum(1 for f in _zpages if '{{唐詩三百首}}' in f.read_text(encoding='utf-8')) != 3:
    raise SystemExit(f'快照「雜詩」页不再是恰三且皆入选（实 {len(_zpages)}）——同名三首全入选断言失效')
# ④ 传区间与首引前提
for _w in ('故鄉', '綺', '梅'):
    if _w in _seg_j or _w in _seg_x:
        raise SystemExit(f'「{_w}」落在王维传区间——传不系乡/梅负证失效，须重读原文')
if JTS.count('故鄉') != 0:
    raise SystemExit('旧传所在卷竟有故鄉——旧传全卷无乡论断失效，须重读')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
for _premise, _needle in (('歴右拾遺', '歴右拾遺'), ('服闋句', '服闋，拜吏部郎中'),
                          ('天寶末句', '天寳末，為給事中')):
    _prev = sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                    if not f.name.startswith('V059')
                    for _ln in f.read_text(encoding='utf-8').splitlines()
                    if 'evidence_excerpt' in _ln and _needle in _ln})
    if _prev:
        raise SystemExit(f'PERSON 前提句「{_premise}」已在 {_prev} 入引——首引前提失效，须重设计')
_prev_z = sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V059')
                  for _ln in f.read_text(encoding='utf-8').splitlines()
                  if 'evidence_excerpt' in _ln and '寒梅着花未' in _ln})
if _prev_z != ['V018']:
    raise SystemExit(f'本诗正文既往引文域不是恰一处 V018（实 {_prev_z}）——第二引上限论断须重估')
_prev_c = sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V059')
                  for _ln in f.read_text(encoding='utf-8').splitlines()
                  if 'evidence_excerpt' in _ln and '柴毁骨立' in _ln})
if _prev_c != ['V057']:
    raise SystemExit(f'「柴毁骨立」既往引文域不是恰一处 V057（实 {_prev_c}）——跳过不重开前提须重估')

BG = {
    'bg-146-scene': (
        '四句是一个人在驿路上拦住老乡：你从故乡来，该知道故乡的事'
        '（「君自故鄉來，應知故鄉事」——「故鄉」二字一句里连说两遍，急处即在这里）；'
        '那么——你动身那天，绮窗前那株寒梅，开花了没有'
        '（「來日綺窗前，寒梅着花未」——千言万语，千挑万选，只问这一株花；'
        '此诗正文系**第二引**：V018 text claim 已一引在先，全库查重恰一处，'
        '两度上限至此用满，此诗正文对后来迁移关闭）。'),
    'bg-146-city': (
        '这首诗的「户口」比诗本身有意思：页首 {{further|雜詩}} 消歧链接在先——'
        '快照里「雜詩」页恰三（王維/沈佺期/無名氏，{{唐詩三百首}} 标记各在：'
        '同名三首全入选本，机器断言）。header 里 title=「雜詩三首」而 '
        'section=「二」：**标题是整组，section 指其一**——《唐詩三百首》从组诗里'
        '只挑了第二首，切选动作就写在字段里（section 字段承载选本动作首见：'
        'V054 装题异注、本篇装选第几，同字段第二用途）。页底注'
        '「↑ [[全唐詩/卷128#雜詩三首|全唐詩·卷128]]」锚点片段非空（同 V058 全锚形态）；'
        '卷128 源行 V026/V040 已立，本迁移零新源。卷128 本篇为「一锚三桩」：'
        '篇题锚点恰一，三首各一转引桩——**组诗在卷里是一户三门**'
        '（第三首桩题「已見寒梅發」：寒梅在组诗里本有前文，选本选走的中段'
        '恰把前后文切断了——照登不裁决）。页四标记全零而 100%；'
        '分类行「五言絕句」系整理者动作（V048 判例）。全唐詩「寒梅」恰 5 处'
        '唯 vol128 属本篇，他卷四处在册不引不牵合。'),
    'bg-146-world': (
        '**题有杂目，杂目在史部七十五卷全零**：通鉴「雜詩」二字零命中——'
        '「杂诗」是诗集自家人给无题可归的组诗起的类名，史部连这个名目都不收。'
        '**诗问寒梅，寒梅在史部只无花可问**：「梅」字通鉴 19 处全是专名'
        '（梅福/梅叔焉/梅祿啜/梅錄/黃梅/梅山/梅金錄——人名与地名），'
        '「寒梅」「梅花」「梅開」「折梅」「寄梅」五词全零（机器断言六连）——'
        '**史部有十九个梅字，一朵梅花都没有**。'
        '**故鄉同字两界第四形态**（V056 泪/V057 已矣/V058 琴之后）：'
        '开元九年（辛酉，七二一）玄宗制逃戸自首'
        '「或於所在附籍，或牒歸故鄉，各從所欲」——故鄉在史部是户籍行政的去向'
        '（恰一处，文件闭域+年标题窗口机器断言，逐字入引为判决证据）：'
        '诗里的故乡是心的方向，史里的故乡是籍的去处。**绮字三名**：诗「綺窗」'
        '之绮是织品；通鉴「綺」恰四处——丝帛之名二（紈綺/綾綺）+皇子名二'
        '（「和王」名「綺」：tj-236 封号序列+tj-244 薨条），同名有主，在册不引'
        '不牵合（audit 硬卡皇子名两条不混入引文）。本层零铸造零 relation。'),
    'bg-146-person': (
        '问故乡的人，传里写他自己在官职上辗转：旧传三句连引——'
        '「**歴右拾遺、監察御史、左補闕、庫部郎中。**」「**服闋，拜吏部郎中。**」'
        '「**天寳末，為給事中。**」——拾遗、御史、补阙、郎中一路迁转，'
        '丧假结束又回吏部，天宝末年做到给事中（生成时全库查重：三句既往零入引，'
        '本迁移首引；三句之间原有一句「居母䘮，柴毁骨立」V057 已引在册'
        '——**逐字跳过零重开**，audit 硬卡）。**诗里他问别人故乡的事，'
        '史里他自己是宦游辗转的那个人**：问乡者即羁旅者（读法声明，非史实）。\n'
        '旧传所在卷「故鄉」二字全卷零（机器断言——传不提他的故乡）；'
        '两传王维段「故鄉」「綺」「梅」全零；已用判例句（柴毁骨立 V057 一引/'
        '事母崔氏 V055/茶鐺 V054/輞川 V035 系列）一个不重开；certainty 不覆盖任何系年。'),
}
CLAIMS = {
    'claim-bg-146-scene': (
        'FACT', 'LIKELY',
        '四句全诗本文（ws 页四标记全零、Textquality 100%——零标记与完备并存，'
        '同 V048/V053 判例）；全句第二引：正文 V018 text claim 已一引在先'
        '（生成时全库查重恰一处，查重针取末句尾段），两度上限至此用满、此诗正文'
        '对后来迁移关闭（audit 硬卡）；「故鄉二字连说两遍即急处」系读法声明。'),
    'claim-bg-146-city': (
        'FACT', 'LIKELY',
        '组诗切选结构首录：title=雜詩三首 而 section=二——选本从组诗挑第二首，'
        '切选动作在 header 字段（section 字段第二用途，对照 V054 题异注）；'
        '{{further|雜詩}} 消歧链接首见——快照雜詩页恰三皆入选（机器断言）；'
        '底注锚点片段非空（同 V058 全锚形态）；卷128 源行 V026/V040 已立零新源；'
        '卷128 一锚三桩（三首各一桩，第三首桩题「已見寒梅發」——组诗里寒梅'
        '有前文，选本切断前后文，照登不裁决）；全唐詩「雜詩」题族六卷二十处、'
        '「寒梅」五处唯此属本篇；分类行「五言絕句」系整理者动作；'
        '题有杂目而无时→零铸造零 relation。'),
    'claim-bg-146-world': (
        'FACT', 'LIKELY',
        '通鉴「雜詩」全零（类名不进史部）；「梅」恰 19 处全专名而'
        '寒梅/梅花/梅開/折梅/寄梅五词全零（机器断言六连——史部十九梅无一梅花）；'
        '故鄉恰一处=tj-212 開元九年（辛酉，七二一）逃戸自首制「或牒歸故鄉」'
        '（闭域+窗口断言，逐字入引为判决证据——同字两界第四形态）；'
        '綺恰四处=丝帛二+皇子和王名綺二（同名有主在册零入引，audit 硬卡）；'
        '两传王维段乡/綺/梅全零+旧传所在卷故鄉全零；certainty 不覆盖任何系年，'
        '诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-146-person': (
        'FACT', 'LIKELY',
        '旧传行迹三句连引首引（生成时全库引文域查重：歴右拾遺句/服闋句/'
        '天寳末句既往各零命中，audit 硬卡；三句之间「柴毁骨立」V057 一引在册'
        '逐字跳过零重开，audit 硬卡）；问乡者即羁旅者为读法声明非史实；'
        '旧传所在卷故鄉全零、两传王维段乡/綺/梅全零（机器断言）；'
        '已用判例句零重开；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-146-scene', 'source-ws-t300-146',
     '页面 雜詩 (君自故鄉來)（header author+两联四句，三段以「……」相連——'
     '全句**第二引**：正文 V018 text claim 一引在先（生成时全库查重恰一处），'
     '**两度上限至此用满，此诗正文对后来迁移关闭**；页 {{别}}/{{*}}/<ref>/{{另}} 全零、100%）',
     join(WS_AUTHOR, WS_L1, WS_L2)),
    ('claim-bg-146-city', 'source-ws-t300-146',
     '页面 雜詩 (君自故鄉來)（页首消歧链接+header title+section+页底注+分类行五段并收——'
     'title=整组题而 section=二：选本切选动作在字段（首见）；further 消歧在先：'
     '快照雜詩页恰三皆入选；底注「卷128#雜詩三首」锚点片段非空（同 V058 全锚）；'
     '分类行系整理者动作：非史料声明、不升格）',
     join(WS_FURTHER, WS_TITLE, WS_SECTION, WS_NOTE, WS_CAT)),
    ('claim-bg-146-city', 'source-quantangshi-128',
     '卷一百二十八·王維《雜詩三首》篇题锚点+三首转引桩（**一锚三桩**：组诗在卷里'
     '是一户三门——机器断言各恰一；第三首桩题「已見寒梅發」：寒梅在组诗里本有前文）',
     join(Q128, Q128_S1, Q128_S2, Q128_S3)),
    ('claim-bg-146-world', 'source-zizhi-tongjian-events',
     '卷二百一十二·開元九年（辛酉，七二一）逃戸自首制段'
     '（**通鉴「故鄉」恰一处**：文件闭域+年标题窗口机器断言——故鄉在史部是'
     '户籍行政的去向，与诗中乡愁同字两界，逐字入引为判决证据；'
     '「雜詩」类名全零、「梅」19 处全专名、「綺」四处分属丝帛与皇子名'
     '——在册零入引项此处均零混入）', TJ_GX),
    ('claim-bg-146-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王維传行迹三句连引（生成时全库引文域查重：三句既往'
     '各零入引，本迁移首引；三句之间原句「柴毁骨立」V057 已引——逐字跳过零重开；'
     '与诗中问乡并置是读法声明）', join(JTS_J1, JTS_J2, JTS_J3)),
]
BG_LINES = {'bg-146-scene': (1, 2), 'bg-146-city': (3, 4),
            'bg-146-world': (3, 4), 'bg-146-person': (1, 2)}
BG_AUDIENCE = {'bg-146-scene': 'PRIMARY', 'bg-146-city': 'JUNIOR',
               'bg-146-world': 'SENIOR', 'bg-146-person': 'JUNIOR'}
BG_TITLES = {'bg-146-scene': '眼前：千言万语只问一株花',
             'bg-146-city': '这座城：选本从组诗里挑走的那一首',
             'bg-146-world': '这个天下：十九个梅字无一梅花',
             'bg-146-person': '这个人：问乡的人自己就在路上'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 40 首·四句绝句 2/2 联）；史实句均有逐字引证；'
                 '系年第三十四次判决（题证系列第廿二状·杂目与寒梅）'
                 '「題有雜目，雜目在史部七十五卷全零；詩問寒梅，寒梅在史部只無花可問」——'
                 '通鉴「雜詩」零命中（类名不进史部）；「梅」恰 19 处全专名而'
                 '寒梅/梅花/梅開/折梅/寄梅五词全零（机器断言六连）；'
                 '「故鄉」恰一处=开元九年（辛酉，七二一）逃戸制「或牒歸故鄉」'
                 '（闭域+窗口，同字两界第四形态，入引为判决证据）；'
                 '「綺」恰四处=丝帛二+皇子和王名綺二（同名有主在册零入引）；'
                 '组诗切选结构首录（title=整组题而 section=二+further 消歧首见+'
                 '快照雜詩页恰三皆入选）；卷128 一锚三桩（第三首桩「已見寒梅發」——'
                 '寒梅在组诗里有前文，选本切断，照登不裁决）；零新源（卷128 源 V026/V040 已立）；'
                 '此诗正文第二引上限用满对后来关闭（V018 在先+全库查重）；'
                 '旧传行迹三句连引首引（柴毁骨立 V057 逐字跳过零重开）；'
                 'KNOWN 零如实记录（第十五例，audit 反向断言）；判例关键语零入引文。' for k in BG}


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
    A("""-- V059：王維《雜詩三首·其二》(work-t300-146) 四层背景（阶段 D 第 40 首·杂目与寒梅）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V026、V040、V057 已执行（work-t300-146 与其
--       text-work-t300-146-ws、source-ws-t300-146 是 V018 的行；source-quantangshi-128 是
--       V026/V040 已立的卷128 源行（本迁移复用，零新源）；source-jiutangshu-wenyuan 是 V016 的行；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源）。
--       本迁移零新 source（audit 断言无诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v059.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/雜詩__君自故鄉來_.txt（四标记全零×100%+section=二 切选结构+further 消歧首见）、
--   舊唐書卷190下（行迹三句首引+全卷无故鄉断言）、新唐書卷202（王维段乡綺梅全零负证）、
--   全唐詩卷128（一锚三桩）、通鑑卷212（故鄉恰一+年标题窗口）+ 通鑑 75 卷/全唐詩 118 卷
--   存快照负证计数扫描（雜詩/故鄉/梅/寒梅/梅花/綺/綺窗）+ 快照雜詩页恰三断言 +
--   既有迁移引文域逐句查重——传区间归属、首引/第二引/零重开前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（四句绝句：scene→1-2 city→3-4 world→3-4 person→1-2，
--   绑 text-work-t300-146-ws 的 4 行；绝句四句承载四层，一、二联可跨层复用——
--   V056 1/1/1/1 之后第二种四句挂载：2/2 联跨层）+ 零 poetry_source 行 + 不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有雜目，雜目在史部七十五卷全零；詩問寒梅，寒梅在史部只無花可問」）：
--   * 雜詩类名全零+梅 19 全专名而寒梅/梅花等五词全零——问梅之问史部无处可问（机器六连断言）；
--   * 故鄉恰一（开元九年逃戸制）入引为判决证据，诗集侧他卷寒梅四处/綺窗三处零入引；
--   * 皇子名「和王綺」在册不引（同名有主，audit 硬卡）；
--   * 此诗正文第二引上限用满：V018 一引在先（全库查重恰一处），对后来迁移关闭；
--   * 组诗切选（section=二）与第三首桩「已見寒梅發」系结构照登——选本切断前后文如实登记、不裁决；
--   * 读法声明（问乡者即羁旅者/故乡二字连说即急处）均标明非史实；
--   * KNOWN 零如实记录（第十五例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 柴毁骨立（V057）/事母崔氏（V055）/茶鐺（V054）判例只引不重开——行迹三连逐字跳过 V057 句。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 58，不含 59
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-146-%';             -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-128';     -- 恰 1（V026/V040 已立，本迁移复用不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-146-ws';  -- 恰 4
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-146-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-146';                                  -- 8（四句×四层，2/2 联跨层）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-146-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-146'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-146';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-146-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-quantangshi-128';  -- 恰 1（复用，非本迁移所立）
-- 回滚: recovery/V059_rollback.sql（按 id 全枚举删除；零 source 删除——卷128 源行为 V026/V040 所立）
START TRANSACTION;""")

    A('\n-- ---------- 1. 零新 source（卷128 源行 V026/V040 已立，本迁移复用） ----------')

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
    brows = [{'id': k, 'work_id': 'work-t300-146',
              'layer': {'bg-146-scene': 'SCENE', 'bg-146-city': 'CITY',
                        'bg-146-world': 'WORLD', 'bg-146-person': 'PERSON'}[k],
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

    A('\n-- ---------- 6. background_line（四句绝句：scene→1-2 city→3-4 world→3-4 person→1-2） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-146-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 7. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 59, 'Wang Wei Miscellaneous Poems, part two of three (work-t300-146) background layers (stage-D poem 40, quatrain, couplet-mapping 2/2 across four layers): dating verdict thirty-four, twenty-second shape of the title-evidence series -- the category name and the plum that never blooms: the character-string za-shi (miscellaneous poem) scores zero across all seventy-five Tongjian volumes (a poets'' own label for unclassifiable verse: the histories do not even carry the category name), while the character mei (plum) appears nineteen times and every one of them is a proper noun -- Mei Fu the official, Mei Lu the envoy, Huang-mei and Mei-shan the place-names -- with cold-plum, plum-blossom, plum-opening, breaking-plum and sending-plum all zero: nineteen mei-characters in the histories and not one plum blossom, so the poem''s question has nowhere in the histories to be asked (six-fold machine assertion); native-village, the fourth same-character split: the Tongjian''s single native-village is the 721 edict on registering fugitive households -- "or by warrant return to the native village" -- native village as the destination of household-registration administration, against the poem''s hometown of the heart (file-closed, year-heading windowed, excerpted as the verdict''s evidence); qi (figured silk) exactly four times -- two bolts of silk and two entries naming the Prince of He as Qi: namesakes have owners and are logged never quoted (audit hard-assert); the anthology''s cutting act recorded for the first time: the page title is the whole three-poem group while the section field says "two" -- the Three Hundred Poems lifted part two out of the group, and the cut itself sits in the header; further-disambiguation notice first seen, three Miscellaneous-Poem pages all anthologized; quan tang shi juan 128 one anchor with three transclusion stubs -- stub three reads "already saw the cold plum sprout": the cold plum had a context in the group that the anthology cut away, logged as found, never adjudicated; zero new sources (juan 128''s source row registered by V026/V040); the poem body hits its two-use ceiling (V018 first, machine-swept, closure declared); PERSON first-cites three Old History career sentences while literally skipping the mother''s-mourning sentence V057 already quoted (audit hard-assert); KNOWN zero honestly recorded (fifteenth instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 59);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V059 精确回滚：只删 V059 插入的行（id 全枚举）。零 source 删除：',
         '-- source-quantangshi-128 是 V026/V040 已立的卷128 源行（本迁移复用），绝不删；',
         '-- work-t300-146 本体、其 text_line 4 行与 source-ws-t300-146 都是 V018 的行，绝不删；',
         '-- source-jiutangshu-wenyuan/zizhi-tongjian-events 均为他迁移所立，零删除；V059 零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 59;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_SECTION, WS_AUTHOR, WS_FURTHER, WS_NOTE, WS_CAT, WS_L1, WS_L2,
              JTS_J1, JTS_J2, JTS_J3, TJ_GX, Q128, Q128_S1, Q128_S2, Q128_S3]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # section=二 与 further 照登硬卡（切选结构首见）
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-146-city' and s == 'source-ws-t300-146')
    if '| section  = 二' not in city_ws or '{{further|雜詩}}' not in city_ws:
        bad.append('section=二 与 further 消歧未逐字入 CITY 引文（切选结构首见照登硬卡）')
    if '卷128#雜詩三首|' not in city_ws:
        bad.append('底注非空锚片段未逐字入 CITY 引文（V058 同款照登硬卡）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-146-city' and s == 'source-ws-t300-146'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # 一锚三桩照登硬卡
    city_q = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-146-city' and s == 'source-quantangshi-128')
    for tok in ('==[[雜詩 (王維)|雜詩三首]]==', '{{:雜詩 (家住孟津河)}}', '{{:雜詩 (君自故鄉來)}}', '{{:雜詩 (已見寒梅發)}}'):
        if tok not in city_q:
            bad.append(f'卷128 一锚三桩要素「{tok[:14]}…」未逐字入 CITY 引文')
    # SCENE 第二引上限声明硬卡
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-146-scene')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054–V058 同款硬卡）')
    # WORLD：故鄉制句必须入引（判决证据）；皇子名綺/类名零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-146-world')
    if '或牒歸故鄉' not in w_ex:
        bad.append('WORLD 引文缺通鉴故鄉制句（同字两界第四形态的判决证据必须入引）')
    for tok in ('和王綺', '紈綺', '綾綺', '雜詩'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入在册零入引项「{tok}」（皇子名/丝帛/类名不得入引）')
    # PERSON：三连齐备 + V057 句逐字跳过
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-146-person')
    for tok in ('歴右拾遺', '服闋，拜吏部郎中', '天寳末，為給事中'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺行迹三连「{tok}」（首引前提）')
    if '柴毁骨立' in p_ex or '居母䘮' in p_ex:
        bad.append('「柴毁骨立」V057 已引零重开——行迹三连必须逐字跳过该句')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-146':
            for w in ('謫仙', '脫靴', '賜金放還', '宮錦袍', '夜郎', '青山', '山東人'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山', '隠鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒', '刻碑鳳林山南',
                '仕宦之疾徑', '放田里', '進止仍有風範', '茶鐺', '事母崔氏', '解官以贖',
                '柴毁骨立', '毀幾不生', '大招權利', '車如流水馬如龍'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 四句绝句 2/2 联跨层形制
    if {k: len(v) for k, v in BG_LINES.items()} != {k: 2 for k in BG}:
        bad.append('四句 background_line 须每层恰 2（2/2 联跨层）')
    if len(re.findall(r"text-work-t300-146-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8（四句×四层 2/2）')
    # 零新 source（V052 教训：断言文案也不得出现该字面量）
    if 'INSERT INTO poetry_' + 'source' in sql:
        bad.append('V059 有意零新 source，但 SQL 里出现了诗源表新建插入语句')
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
        bad.append("V059 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V059 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-146' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V059 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-146' AS subject_id" in sql:
        bad.append('V059 的 claim 主语应全部是 bg-146-*，work-t300-146 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V059 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '無花可問' not in body_all and '无花可问' not in body_all:
        bad.append('BG/文件头须含「寒梅在史部只无花可问」判决声明')
    if '十九' not in body_all:
        bad.append('BG 须含「十九个梅字」计数声明')
    if '切选' not in body_all:
        bad.append('BG/CITY 须含「切选」结构首见声明（section=二）')
    if '同名有主' not in body_all:
        bad.append('BG/WORLD 须含皇子名「同名有主」在册声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 16 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（王维段，旧传所在卷无故鄉）；'
              f'年标题窗口断言（開元九年辛酉七二一）；'
              f'负证机器复查五层（通鉴雜詩类名全零+故鄉恰一=tj-212 闭域+'
              f'梅恰十九而寒梅/梅花/梅開/折梅/寄梅五词全零+綺恰四分=tj-196×2/tj-236/tj-244 且皇子名两句在册+'
              f'全唐詩雜詩题族六卷二十处精确闭域+寒梅五卷册数+綺窗恰三在册/'
              f'卷128 一锚三桩各恰一/ws 四标记全零+100% 恰一+section=二+further+非空锚片段恰一/'
              f'快照雜詩页恰三皆入选/两传王段乡綺梅全零，快照变动即中止）；'
              f'首引前提全库查重硬卡（行迹三句各既往零引）+第二引前提硬卡（本诗正文恰一=V018）+'
              f'零重开前提硬卡（柴毁骨立恰一=V057）；'
              f'section=二+further+一锚三桩照登硬卡；SCENE locator 第二引/上限硬卡；'
              f'故鄉制句入引+皇子名/丝帛/类名零混入断言；判例只引不重开断言（含柴毁骨立/大招權利）；'
              f'四句 2/2 联跨层形制断言；零 KNOWN 反向断言；零新 source 反向断言（回滚零 source 删除）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
