#!/usr/bin/env python3
"""阶段 D 第 44 首：生成 V063——王維《送梓州李使君》(work-t300-064, V018 已立) 四层背景。

「为什么写」走到**地名两界（同字两界第八形态·地名形态首见；V056 泪/V057 已矣/
V058 琴·流水/V059 故鄉/V060 閉關/V061 王孫/V062 長策·解帶之后）**：
**「題有梓州，梓州在史部只貶所與叛鎮；詩有文翁，文翁在史部七十五卷全零」**——

通鉴「梓州」恰 31 处十四卷（文件闭域断言），其中「**梓州刺史**」恰二：
開元九年（辛酉，七二一）王晙「**貶晙為梓州刺史**」（tj-212——史部的梓州是
贬官去处）＋上元二年（辛丑，七六一）「**梓州刺史段子璋反**」（tj-222——
史部的梓州是叛镇巢穴）：**史部仅有的两个梓州刺史，一个是贬官，一个是反将**；
送别诗题里那位要去做刺史「翻新教育」的李使君，通鉴「李使君」全零——
「使君」恰 14 处十一卷全是**称呼不是姓名**。诗的劝勉全凭**文翁**（蜀郡守
以教化著名的典），而「文翁」通鉴全零——**诗的全部劝勉内容，史部一字不载**；
「杜鵑」「橦布」「芋田」「漢女」「巴人」也全零——蜀地风物整场不进史部
（文翁全唐詩恰三处=杜甫《将赴成都草堂途中有作》「直爲文翁再剖符」等
同是送蜀官的劝勉语，在册零入引；杜鵑全唐詩恰 23 处九卷闭域在册）。

**三字撞字各恰一处**（闭域+窗口，全引为判决证据）：诗的「萬壑樹參天」——
史部的「參天」恰一处=貞觀二十一年（丁未，六四七）回紇諸部長請開「**參天可汗道**」
（參天是天至尊的称号，不是树）；诗的「樹杪百重泉」是最高最空之景——
史部的「樹杪」恰一处=天復三年（癸亥，九〇三）秦皋「**舉火炬於樹杪**」
诈敌救城（树梢是举火为号的军用高处）、「**百重**」恰一处=貞觀十九年（乙巳，
六四五）李世勣攻遼東城「圍其城數**百重**」（包围圈层数）。**诗把树梢水端
写成天景，史把树梢围重用作军号与兵形**。

CITY 层：**100% 自评×{{另}}×3**——V054「100% 带五枚标记」横截面形态再复现
（完备度与标记数正交：V055/V057/V061/V062 是 75%侧，本篇是 100%侧）；
**三枚异文三形态**：①「{{另|千山響|鄉音聽}}」**整语支异文**（两支各三字——
异文支不必是字，可以是整短语）②「{{另|夜|半}}」单字支异文（常式）
③「{{另|橦|一作[上宗下貝]}}」**支内含「一作」注+构件描述字**——第二支不是
字符而是造字说明「一作[上宗下貝]」（宗头贝底之字排不出，就以构件描述代之：
**缺字以构件描述入注**首见）。卷126 第七次复用**零新源**；底注全锚；
裸名锚+桩（同 V062，无同名无消歧器）；分类行**五言律詩+送別詩双行**。

PERSON 层首引：新传「**縉為蜀州刺史未還，**」（全库查重既往零入引）——
诗中送的是**别人入蜀**（劝他做文翁），传里记的是**弟弟正在蜀中**：
王縉做蜀州刺史没回来，王维自己上表求换官放归田里（自表诸句 V040 在册零重开，
audit 硬卡）——**送人入蜀劝以教化，求弟还京表以自贬：诗劝人，表求己**
（读法声明，非史实）。**两传「梓州」「使君」「杜鵑」「文翁」全零**
（机器断言——送尽天下刺史的人，传里没有一座梓州）。

八句五律 2/2/2/2 第五次（V054/V058/V060/V062）；正文第二引上限用满第十一例
（V018 归一形一引在先，查重双针「萬壑樹參天」「不敢倚先賢」各恰一处）。

用法: python3 -I emit_v063.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/送梓州李使君.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
V126 = pathlib.Path('/tmp/src-dl/quantangshi/vol126.txt').read_text(encoding='utf-8')
TJ197 = pathlib.Path('/tmp/src-dl/tongjian/tj-197.txt').read_text(encoding='utf-8')
TJ198 = pathlib.Path('/tmp/src-dl/tongjian/tj-198.txt').read_text(encoding='utf-8')
TJ212 = pathlib.Path('/tmp/src-dl/tongjian/tj-212.txt').read_text(encoding='utf-8')
TJ222 = pathlib.Path('/tmp/src-dl/tongjian/tj-222.txt').read_text(encoding='utf-8')
TJ264 = pathlib.Path('/tmp/src-dl/tongjian/tj-264.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 送梓州李使君', '| title    = 送梓州李使君', 'ws header title(送蜀刺史题面)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS,
                        '| notes    = {{Textquality|100%}} ↑ [[全唐詩/卷126#送梓州李使君|全唐詩·卷126]]',
                        '全唐詩·卷126]]',
                        'ws 页底注(100%自评+非空全锚——同 V058-V062 全锚形态)')
WS_CAT1 = slice_between(WS, '[[Category:五言律詩]]', '[[Category:五言律詩]]', 'ws 分类行一(五言律詩——整理者分类;V048 判例)')
WS_CAT2 = slice_between(WS, '[[Category:送別詩]]', '[[Category:送別詩]]', 'ws 分类行二(送別詩——分类双行本篇首见)')
WS_L1 = slice_between(WS, '{{另|千山響|鄉音聽}}杜鵑', '杜鵑。', 'ws第1联(千山杜鹃——整语支异文首见:两支各三字)')
WS_L2 = slice_between(WS, '山中一{{另|夜|半}}雨，樹杪百重泉', '樹杪百重泉。', 'ws第2联(树梢百重泉——单字支异文常式)')
WS_L3 = slice_between(WS, '漢女輸{{另|橦|一作[上宗下貝]}}布，巴人訟芋田', '巴人訟芋田。', 'ws第3联(橦布芋田——支内含一作注+构件描述字首见)')
WS_L4 = slice_between(WS, '文翁翻教授，不敢倚先賢。', '不敢倚先賢。', 'ws第4联(劝以文翁教化——史部文翁全零)')
XTS_S = slice_between(XTS, '縉為蜀州刺史未還', '未還',
                      '新传缙为蜀州刺史未还句(从未入引,PERSON 首引——自表换官句 V040 已引的前情一句)')
TJ_ZZ1 = slice_between(TJ212, '貶晙為梓州刺史', '梓州刺史',
                       '通鉴开元九年王晙贬梓州刺史段(史部梓州刺史一处——贬所;窗口断言)')
TJ_ZZ2 = slice_between(TJ222, '梓州刺史段子璋反', '段子璋反',
                       '通鉴上元二年段子璋反段(史部梓州刺史二处——叛镇;窗口断言)')
TJ_ST = slice_between(TJ198, '謂之參天可汗道', '可汗道',
                      '通鉴贞观二十一年参天可汗道段(参天史部一处——天至尊称号;窗口断言)')
TJ_SM = slice_between(TJ264, '舉火炬於樹杪', '於樹杪',
                      '通鉴天复三年火炬树杪诈敌段(树杪史部一处——军用高处;窗口断言)')
TJ_BC = slice_between(TJ197, '圍其城數百重', '數百重',
                      '通鉴贞观十九年辽东城围数百重段(百重史部一处——包围圈层数;窗口断言)')
Q126 = slice_between(V126, '==[[送梓州李使君]]==', '==[[送梓州李使君]]==',
                     '卷126 本篇篇题锚点(裸名锚——无同名诗则无消歧器,同 V062 形态)')
Q126_S = slice_between(V126, '{{:送梓州李使君}}', '{{:送梓州李使君}}', '卷126 本篇转引桩')

# ---------- 传区间归属复验（V036 立规） ----------
_xa = XTS.find('==王維==')
_xm = re.search(r'\n==[^=\n]{1,10}==', XTS[_xa + 8:])
_seg_x = XTS[_xa:_xa + 8 + _xm.start()]
_ja = JTS.find('=王維=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
if not (0 <= _xa and '縉為蜀州刺史未還' in _seg_x):
    raise SystemExit('切片越出王维段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；五扇窗口） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ212, TJ_ZZ1, '開元九年')
_window(TJ222, TJ_ZZ2, '上元二年')
_window(TJ198, TJ_ST, '貞觀二十一年')
_window(TJ264, TJ_SM, '天復三年')
_window(TJ197, TJ_BC, '貞觀十九年')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：文翁/蜀风/李使君全零；梓州恰 31 闭域；梓州刺史恰二；使君恰 14 闭域；撞字三词各恰一
for _w in ('文翁', '李使君', '杜鵑', '橦布', '芋田', '漢女', '巴人', '訟芋'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——文翁全零/蜀风不进史部的判决失效，须重读')
_zz = {f.name: t.count('梓州') for f in sorted(_tj.glob('tj-*.txt')) for t in [f.read_text(encoding='utf-8')] if '梓州' in t}
if sum(_zz.values()) != 31 or len(_zz) != 14:
    raise SystemExit(f'通鉴「梓州」不再是恰 31 处十四卷（实 {sum(_zz.values())}/{len(_zz)} 卷）——地名闭域判决须重估')
if _alltj.count('梓州刺史') != 2 or _alltj.count('李使君') != 0:
    raise SystemExit('通鉴「梓州刺史」恰二/「李使君」全零结构变了——贬所叛镇判决失效')
_sj = {f.name: t.count('使君') for f in sorted(_tj.glob('tj-*.txt')) for t in [f.read_text(encoding='utf-8')] if '使君' in t}
if sum(_sj.values()) != 14 or len(_sj) != 11:
    raise SystemExit(f'通鉴「使君」不再是恰 14 处十一卷（实 {sum(_sj.values())}/{len(_sj)} 卷）——称呼非姓名断言须重估')
for _w, _n in (('參天', 1), ('樹杪', 1), ('百重', 1)):
    if _alltj.count(_w) != _n:
        raise SystemExit(f'通鉴「{_w}」不再恰一处——三字撞字判决失效，须重读')
# ② 全唐詩：橦布/芋田/百重泉全零（诗语无同源）；文翁恰三/杜鵑恰 23/樹杪恰四闭域在册
for _w in ('橦布', '芋田', '百重泉', '漢女輸'):
    if _allq.count(_w) != 0:
        raise SystemExit(f'全唐詩「{_w}」不再全零——诗语无同源断言失效，须重读')
_ww = {f.name: t.count('文翁') for f in sorted(_qts.glob('vol*.txt')) for t in [f.read_text(encoding='utf-8')] if '文翁' in t}
if _ww != {'vol222.txt': 1, 'vol228.txt': 2}:
    raise SystemExit(f'全唐詩「文翁」册数分布变了（实 {sorted(_ww.items())}）——杜甫同语在册断言须重估')
if sum(t.count('杜鵑') for t in _qtf.values()) != 23 or sum(t.count('樹杪') for t in _qtf.values()) != 4:
    raise SystemExit('全唐詩「杜鵑」恰 23/「樹杪」恰四变了——在册册数断言须重估')
if V126.count('送梓州李使君') != 2 or (V126.count('==[[送梓州李使君]]==') != 1 or V126.count('{{:送梓州李使君}}') != 1):
    raise SystemExit('卷126 送梓州李使君恰 2（锚1+桩1）结构变了——裸名锚在册断言失效')
# ③ ws：{{另}}恰三具体字样 + 他标记全零 + 100% + 三百首 + 全锚 + 双分类行
for _mk in ('{{另|千山響|鄉音聽}}', '{{另|夜|半}}', '{{另|橦|一作[上宗下貝]}}'):
    if WS.count(_mk) != 1:
        raise SystemExit(f'ws 页异文标记 {_mk} 不再恰一枚——三枚异文三形态判决失效，须重读快照')
if WS.count('{{另') != 3 or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页标记结构不再是 {{另}}×3 全他零——横截面断言失效')
if WS.count('{{Textquality|100%}}') != 1 or WS.count('卷126#送梓州李使君|') != 1:
    raise SystemExit('ws 页 100%/全锚结构变了——底注断言失效')
if WS.count('{{唐詩三百首}}') != 1 or WS.count('| title    = 送梓州李使君') != 1:
    raise SystemExit('ws 页三百首标记/题行结构变了——选本标记照登断言失效')
if WS.count('[[Category:五言律詩]]') != 1 or WS.count('[[Category:送別詩]]') != 1:
    raise SystemExit('ws 页分类双行结构变了——双分类行照登断言失效')
# ④ 两传负证（传不载蜀）与首引/二引/零重开前提
for _f, _nm in ((JTS, '旧传全文'), (XTS, '新传全文')):
    for _w in ('梓州', '使君', '杜鵑', '文翁'):
        if _w in _f:
            raise SystemExit(f'「{_w}」落在{_nm}——传不载蜀负证失效，须重读原文')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
for _premise, _needle, _want in (
        ('新传蜀州刺史句', '縉為蜀州刺史未還', []),
        ('本诗首句', '萬壑樹參天', ['V018']),
        ('本诗末句', '不敢倚先賢', ['V018']),
        ('自表换官句', '己有五短', ['V040']),
        ('V061 召缙句', '召縉為左散騎常侍', ['V061']),
        ('V062 议者句', '議者不之罪', ['V062'])):
    _prev = sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                    if not f.name.startswith('V063')
                    for _ln in f.read_text(encoding='utf-8').splitlines()
                    if 'evidence_excerpt' in _ln and _needle in _ln})
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')

BG = {
    'bg-064-scene': (
        '四联是一场入蜀路上的视听盛景：万壑的树顶着天，千山响应着杜鹃'
        '（「萬壑樹參天，{{另|千山響|鄉音聽}}杜鵑」——千山響一作鄉音聽，'
        '**整语支异文首见**：异文支不必是字，可以是三字整短语，照登不裁决）；'
        '山里下一夜的雨，树梢上百重泉同时下来'
        '（「山中一{{另|夜|半}}雨，樹杪百重泉」——夜一作半，单字支常式）；'
        '蜀地的女子交纳橦布，巴人为芋田打官司'
        '（「漢女輸{{另|橦|一作[上宗下貝]}}布，巴人訟芋田」——橦一作[上宗下貝]：'
        '**支内含「一作」注+构件描述字首见**，第二支排不出字形、'
        '以「宗头贝底」的构件描述代字入注，照登不裁决）；'
        '愿使君像汉代文翁那样翻新教化，不敢倚仗先贤余荫'
        '（「文翁翻教授，不敢倚先賢」——文翁典页上无自注，系引者按典读法声明；'
        '此诗正文系**第二引**：V018 text claim 已一引在先'
        '（其形系异文取首项的归一文本），全库查重双针恰一处，两度上限至此用满，'
        '此诗正文对后来迁移关闭）。'),
    'bg-064-city': (
        '本页是**「100% 自评×异文多枚」横截面形态的再复现**：{{Textquality|100%}}'
        '而 {{另}}×3——完备度与标记数双向正交（V054「100% 带五枚标记」是首录，'
        'V055/V057/V061/V062 是 75%×异文侧；本篇补齐 100%×多枚侧）；'
        '三枚异文三种形态（整语支/单字支/构件描述支，见 SCENE 层逐枚照登）。'
        '篇题锚点是**裸名**「==[[送梓州李使君]]==」——无同名诗则无消歧器'
        '（同 V062 酬張少府：三种消歧形态中裸名式至此第二见）；卷126 锚+桩恰 2'
        '（闭域机器断言）；底注「↑[[全唐詩/卷126#送梓州李使君|全唐詩·卷126]]」'
        '锚点片段非空（同 V058–V062 全锚形态）；**分类行双行**（五言律詩+送別詩）'
        '系整理者动作（V048 判例：非史料声明、不升格）——「送別詩」柜里'
        '装着本篇，而「梓州」在史部只作贬所与叛镇（对照 WORLD 层）；'
        'source-quantangshi-126 系 V035/V039/V052/V054/V060/V062 已立、'
        '**第七次复用零新源**（本层零铸造零 relation）。'),
    'bg-064-world': (
        '**題有梓州，梓州在史部只貶所與叛鎮**：通鉴「梓州」恰 31 处十四卷'
        '（文件闭域断言），其中「梓州刺史」恰二（闭域+双窗口，逐字入引）：'
        '開元九年（辛酉，七二一）「**貶晙為梓州刺史**」——史部的梓州是贬官去处；'
        '上元二年（辛丑，七六一）「**梓州刺史段子璋反**」——史部的梓州是叛镇巢穴。'
        '**史部仅有的两个梓州刺史，一个是贬官，一个是反将**；本诗题里那位'
        '去翻新教化的李使君，通鉴「李使君」全零——「使君」恰 14 处十一卷'
        '（闭域断言）全是**称呼不是姓名**。**詩有文翁，文翁在史部七十五卷全零**：'
        '诗的劝勉全凭文翁（蜀守教化之典），史部一字不载；「杜鵑」「橦布」「芋田」'
        '「漢女」「巴人」也全零——蜀地风物整场不进史部。**三字撞字各恰一处**'
        '（闭域+窗口，入引为判决证据）：诗的「萬壑樹參天」——史部的「參天」'
        '恰一处=貞觀二十一年（丁未，六四七）回紇諸部長請開「**參天可汗道**」'
        '（參天是天至尊的称号，不是树）；诗的「樹杪百重泉」是最高最空之景——'
        '史部的「樹杪」恰一处=天復三年（癸亥，九〇三）秦皋「**舉火炬於樹杪**」'
        '举火诈敌救城（树梢是军用信号高处）、「**百重**」恰一处=貞觀十九年'
        '（乙巳，六四五）遼東城之役「圍其城數**百重**」（包围圈层数）——'
        '**诗把树梢水端写成天景，史把树梢围重用作军号与兵形**'
        '（同字两界第八形态·地名形态首见，五句史文入引，audit 硬卡）。'
        '诗集侧在册零入引（机器断言）：「文翁」全唐詩恰三处=杜甫'
        '「文翁儒化成」「直爲文翁再剖符」「直爲文翁」等——唐人送蜀官'
        '同用这个劝勉语，在册不牵合；「杜鵑」恰 23 处九卷、「樹杪」恰四处闭域在册；'
        '「橦布」「芋田」「百重泉」全唐詩亦全零（诗语无同源）。本层零铸造零 relation。'),
    'bg-064-person': (
        '诗中送的是**别人入蜀**——劝李使君去做文翁、翻新教授；传里记的是'
        '**弟弟正在蜀中**：本迁移首引新传「**縉為蜀州刺史未還，**」'
        '（生成时全库查重：既往零入引，audit 硬卡）——其后那道求换官放归田里'
        '的自表（「己有五短」诸句 V040 已引在册零重开，audit 硬卡）正是'
        '因这句前情而起。**送人入蜀劝以教化，求弟还京表以自贬：'
        '诗劝人，表求己**（读法声明，非史实）。\n'
        '**两传「梓州」「使君」「杜鵑」「文翁」全零**（机器断言——'
        '送尽天下刺史的人，传里没有一座梓州；诗题的字也不进传）；'
        '已用判例句（己有五短 V040/召縉句 V061/議者不之罪 V062/'
        '願歸所任官 V040/輞川系列 V035 起）一个不重开；certainty 不覆盖任何系年。'),
}
CLAIMS = {
    'claim-bg-064-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页 {{另}}×3、其余标记全零、Textquality 100%——'
        '100%×多枚横截面再复现，V054 首录/V055-V062 75%侧对照）；'
        '三枚异文三形态逐枚照登不裁决：整语支异文首见（千山響/鄉音聽两支各三字）、'
        '单字支常式（夜/半）、支内含「一作」注+构件描述字首见'
        '（橦/一作[上宗下貝]——第二支以构件描述代字）；引文含三枚标记原样；'
        '同页两形并存四度再验：V018 正文引文系异文取首项的归一文本，'
        '本迁移 SCENE 引文含 {{另}} 标记原样，各从其录；文翁典系读法声明非史料断言'
        '（页上无自注）；全句第二引：正文 V018 text claim 一引在先'
        '（生成时全库查重双针「萬壑樹參天」「不敢倚先賢」各恰一处），'
        '两度上限至此用满、此诗正文对后来迁移关闭（audit 硬卡）。'),
    'claim-bg-064-city': (
        'FACT', 'LIKELY',
        '100% 自评×{{另}}×3 横截面形态再复现（完备度与标记数正交双向在案）；'
        '裸名锚+桩（无同名诗则无消歧器——裸名式第二见，对照 V062 首录/V059 作者/'
        'V061 首句）；卷126「送梓州李使君」恰 2=锚 1+桩 1 机器断言闭域；'
        '底注全锚（同 V058–V062）；分类行双行（五言律詩+送別詩）照登+非史料声明'
        '+不升格（V048 判例）；source-quantangshi-126 系 V035/V039/V052/V054/'
        'V060/V062 已立、第七次复用零新源；题面送蜀刺史而无时→零铸造零 relation。'),
    'claim-bg-064-world': (
        'FACT', 'LIKELY',
        '通鉴「梓州」恰 31 处十四卷闭域+「梓州刺史」恰二（貶晙為梓州刺史'
        '開元九年辛酉七二一+梓州刺史段子璋反上元二年辛丑七六一——'
        '贬所与叛镇，闭域+双窗口入引）+「李使君」全零+「使君」恰 14 处十一卷'
        '闭域（称呼非姓名）；「文翁」通鉴全零（诗的全部劝勉内容史部不载）'
        '+杜鵑/橦布/芋田/漢女/巴人全零（蜀风不进史部）；撞字三词各恰一闭域'
        '入引=貞觀二十一年（丁未，六四七）參天可汗道+天復三年（癸亥，九〇三）'
        '舉火炬於樹杪+貞觀十九年（乙巳，六四五）圍其城數百重'
        '（同字两界第八形态·地名形态首见——诗写天景/史作军号兵形，audit 硬卡）；'
        '全唐詩「文翁」恰三（杜甫送蜀官同语）/杜鵑恰 23/樹杪恰四在册零入引'
        '（机器断言）+橦布/芋田/百重泉全唐詩亦全零；certainty 不覆盖任何系年，'
        '诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-064-person': (
        'FACT', 'LIKELY',
        '新传「縉為蜀州刺史未還」首引（生成时全库引文域查重：既往零命中，'
        'audit 硬卡）；其后自表句「己有五短」V040 已引在册零重开（audit 硬卡字样）；'
        '「诗劝人，表求己」为读法声明非史实；**两传全文梓州/使君/杜鵑/文翁全零**'
        '（机器断言——传不载蜀：送尽天下刺史的人传里没有一座梓州）；'
        '召缙句 V061/议者句 V062 在册零重开；已用判例句零重开；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-064-scene', 'source-ws-t300-064',
     '页面 送梓州李使君（header author+四联八句，五段以「……」相連——全句**第二引**：'
     '正文 V018 text claim 一引在先（其形系异文取首项的归一文本，本引文含三枚 {{另}} '
     '标记原样——同页两形并存各从其录），生成时全库查重双针恰一处，'
     '**两度上限至此用满，此诗正文对后来迁移关闭**；{{别}}/{{*}}/<ref> 全零、100%；'
     '三枚异文三形态照登不裁决（整语支/单字支/构件描述支）；文翁典页上无自注，系引者读法声明）',
     join(WS_AUTHOR, WS_L1, WS_L2, WS_L3, WS_L4)),
    ('claim-bg-064-city', 'source-ws-t300-064',
     '页面 送梓州李使君（header title+页底注+分类双行四段并收——100% 自评×{{另}}×3'
     '横截面形态再复现（V054 首录对照）；底注全锚「卷126#送梓州李使君」'
     '（同 V058–V062）；分类行双行（五言律詩+送別詩）系整理者动作：'
     '非史料声明、不升格）',
     join(WS_TITLE, WS_NOTE, WS_CAT1, WS_CAT2)),
    ('claim-bg-064-city', 'source-quantangshi-126',
     '卷一百二十六·王維《送梓州李使君》篇题锚点+转引桩（**裸名锚**——无同名诗'
     '则无消歧器（裸名式第二见，对照 V062）；卷126「送梓州李使君」恰 2=锚 1+桩 1'
     '机器断言；源行系 V035/V039/V052/V054/V060/V062 已立、本迁移第七次复用零新源）',
     join(Q126, Q126_S)),
    ('claim-bg-064-world', 'source-zizhi-tongjian-events',
     '卷二百一十二·開元九年（辛酉，七二一）貶晙為梓州刺史段……卷二百二十二·'
     '上元二年（辛丑，七六一）梓州刺史段子璋反段……卷一百九十八·貞觀二十一年'
     '（丁未，六四七）參天可汗道段……卷二百六十四·天復三年（癸亥，九〇三）'
     '舉火炬於樹杪段……卷一百九十七·貞觀十九年（乙巳，六四五）圍其城數百重段'
     '（**通鉴「梓州」恰 31 处十四卷闭域、梓州刺史恰二、李使君全零、使君恰 14 处、'
     '參天/樹杪/百重各恰一处**：文件闭域+五处年标题窗口机器断言——'
     '史部两个梓州刺史一贬一叛、树梢围重皆军用；五句史文逐字入引为判决证据；'
     '文翁/杜鵑/蜀风通鉴全零，杜甫文翁诸句全唐詩在册零入引）',
     join(TJ_ZZ1, TJ_ZZ2, TJ_ST, TJ_SM, TJ_BC)),
    ('claim-bg-064-person', 'source-xintangshu-wenyi',
     '卷二百二·文艺中·王維传缙为蜀州刺史未还句（生成时全库引文域查重：既往零入引，'
     '本迁移首引；其后自表「己有五短」诸句 V040 已引零重开；'
     '「诗劝人，表求己」是读法声明；两传全文梓州/使君/杜鵑/文翁全零——'
     '传不载蜀，机器断言）', XTS_S),
]
BG_LINES = {'bg-064-scene': (1, 2), 'bg-064-city': (3, 4),
            'bg-064-world': (5, 6), 'bg-064-person': (7, 8)}
BG_AUDIENCE = {'bg-064-scene': 'PRIMARY', 'bg-064-city': 'JUNIOR',
               'bg-064-world': 'SENIOR', 'bg-064-person': 'JUNIOR'}
BG_TITLES = {'bg-064-scene': '眼前：入蜀路上的视听盛景',
             'bg-064-city': '这座城：100% 自评带三枚异文的页',
             'bg-064-world': '这个天下：史部的梓州只贬所叛镇',
             'bg-064-person': '这个人：送人入蜀时弟弟还在蜀中'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 44 首·八句五律 2/2/2/2 第五次）；史实句均有逐字引证；'
                 '系年第三十八次判决（题证系列第廿六状·梓州与文翁）'
                 '「題有梓州，梓州在史部只貶所與叛鎮；詩有文翁，文翁在史部七十五卷全零」——'
                 '通鉴「梓州」恰 31 处十四卷闭域+「梓州刺史」恰二闭域双窗口入引'
                 '（開元九年辛酉七二一貶晙為梓州刺史+上元二年辛丑七六一段子璋反——'
                 '史部仅有的两个梓州刺史一贬一叛）；「李使君」全零+「使君」恰 14 处'
                 '十一卷闭域（称呼非姓名）；文翁/杜鵑/橦布/芋田/漢女/巴人通鉴全零'
                 '（诗的全部劝勉内容史部不载）；三字撞字各恰一处闭域窗口入引'
                 '（參天可汗道貞觀二十一年丁未六四七+舉火炬於樹杪天復三年癸亥九〇三+'
                 '圍其城數百重貞觀十九年乙巳六四五——诗写天景/史作军号兵形，'
                 '同字两界第八形态·地名形态首见）；杜甫文翁三处+杜鵑 23+樹杪四在册零入引；'
                 '100% 自评×{{另}}×3 横截面形态再复现（V054 首录侧补齐）+三枚异文三形态'
                 '（整语支异文首见/单字支/支内含一作注+构件描述字首见）照登不裁决；'
                 '同页两形并存四度再验；裸名锚第二见+卷126 恰二闭域+底注全锚+分类双行；'
                 '零新源（卷126 源第六次立前已用六迁移、第七次复用）；'
                 '此诗正文第二引上限用满第十一例对后来关闭（V018 在先+双针查重）；'
                 'PERSON 首引新传「縉為蜀州刺史未還」（自表己有五短 V040 零重开；'
                 '两传全文梓州/使君/杜鵑/文翁全零——传不载蜀）；'
                 'KNOWN 零如实记录（第十九例，audit 反向断言）；判例关键语零入引文。' for k in BG}


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
    A("""-- V063：王維《送梓州李使君》(work-t300-064) 四层背景（阶段 D 第 44 首·梓州与文翁）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V039、V040、V052、V054、V060、V061、V062 已执行
--       （work-t300-064 与其 text-work-t300-064-ws、source-ws-t300-064 是 V018 的行；
--       source-quantangshi-126 是 V035/V039/V052/V054/V060/V062 已立的卷126 源行（本迁移第七次复用，零新源）；
--       source-xintangshu-wenyi 是 V016 的行；source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       判例在册句自表己有五短（V040）/召缙（V061）/议者不之罪（V062）只引不重开）。
--       本迁移零新 source（audit 断言无诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v063.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/送梓州李使君.txt（{{另}}×3 三形态×100% 自评+底注全锚+分类双行）、
--   舊唐書卷190下/新唐書卷202（两传全文梓州/使君/杜鵑/文翁全零负证+蜀州刺史句首引+己有五短零重开）、
--   全唐詩卷126（裸名锚+桩）/卷222/卷228（杜甫文翁在册）/杜鵑 23 处/樹杪 4 处闭域扫描、
--   通鑑卷197/198/212/222/264（梓州恰 31 闭域+梓州刺史恰二+撞字三词各恰一+五处年标题窗口）+
--   通鑑 75 卷/全唐詩 118 卷存快照负证计数扫描（文翁/李使君/杜鵑/橦布/芋田/漢女/巴人/訟芋/
--   參天/樹杪/百重/梓州/使君/百重泉/漢女輸）+
--   既有迁移引文域逐句查重——传区间归属、首引/二引/零重开前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 background_line（八句五律 **2/2/2/2 第五次**（V054/V058/V060/V062）：scene→1-2 city→3-4
--   world→5-6 person→7-8，绑 text-work-t300-064-ws 的 8 行）+ 零 poetry_source 行 + 不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有梓州，梓州在史部只貶所與叛鎮；詩有文翁，文翁在史部七十五卷全零」）：
--   * 梓州恰 31 闭域/梓州刺史恰二双窗口入引/李使君全零/使君恰 14 闭域（贬所叛镇/称呼非姓名）；
--   * 文翁/杜鵑/蜀风通鉴全零+撞字三词各恰一闭域窗口入引（地名形态首见，audit 双向硬卡）；
--   * 文翁典与「诗劝人，表求己」均标明读法声明非史实（页上无自注）；
--   * 三枚异文三形态（整语支/单字支/构件描述支）引文含标记原样照登不裁决；
--   * 同页两形并存四度再验（V018 归一形 vs 本迁移三标记原样形）；
--   * 裸名锚第二见+分类双行照登（V048 判例三重断言）；
--   * 此诗正文第二引上限用满：V018 一引在先（双针查重各恰一处），对后来迁移关闭；
--   * 杜甫文翁三句/杜鵑 23/樹杪 4 他卷在册零入引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第十九例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 己有五短（V040）/召缙句（V061）/议者句（V062）判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 62，不含 63
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-064-%';             -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-126';     -- 恰 1（六迁移已立，本迁移复用不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-064-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-064-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-064';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-064-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-064'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-064';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-064-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-quantangshi-126';  -- 恰 1（复用，非本迁移所立）
-- 回滚: recovery/V063_rollback.sql（按 id 全枚举删除；零 source 删除——卷126 源行为六迁移所立）
START TRANSACTION;""")

    A('\n-- ---------- 1. 零新 source（卷126 源行六迁移已立，本迁移第七次复用） ----------')

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
    brows = [{'id': k, 'work_id': 'work-t300-064',
              'layer': {'bg-064-scene': 'SCENE', 'bg-064-city': 'CITY',
                        'bg-064-world': 'WORLD', 'bg-064-person': 'PERSON'}[k],
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

    A('\n-- ---------- 6. background_line（八句五律 2/2/2/2 第五次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-064-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 7. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 63, 'Wang Wei''s Farewell to Senator Li of Zizhou (work-t300-064) background layers (stage-D poem 44, five-character regulated octet 2/2/2/2 fifth time): dating verdict thirty-eight, twenty-sixth shape of the title-evidence series -- the place-name and the old governor in two realms: Zizhou appears exactly 31 times across 14 Tongjian volumes (file-closed) and Zizhou Cishi exactly twice (closed, windowed, quoted): in 721 Wang Jun was demoted to be Zizhou Cishi, and in 761 Duan Zi-zhang the Zizhou Cishi revolted -- the only two Zizhou governors in the histories are one demoted minister and one rebel general, while Senator Li of the poem''s title scores zero (shijun "senator" appears 14 times over 11 volumes: a form of address, never a name); and Wen Weng -- the poem''s entire exhortation, the Han governor famed for civilizing Shu -- scores zero across all seventy-five Tongjian volumes, as do cuckoo, tong-cloth, taro fields, Han women and Ba people: all the scenery and all the urging never enter the histories; three colliding words exactly once each (closed, windowed, quoted): in 647 the Uyghur chieftains asked to open the "Sky-Canan Khagan Road" (cantian = the heavenly sovereign''s title, not a tree), in 903 Qin Gao "raised fire-torops at the treetops" to fake a rescue (the treetop as military beacon), and in 645 the siege lines at Liaodong "encircled the city in several hundred folds" -- the poem lifts treetops and spring-mists into a sky-scene, the histories use treetops and hundred-folds for beacons and siege-works: the eighth same-character split, first place-name shape (five history sentences quoted as verdict evidence, audit hard-assert); on the poetry side logged never quoted: Wen Weng exactly three times in the Quan Tangshi (Du Fu, farewell-to-a-Shu-official language), cuckoo 23 times over nine volumes, treetop four times (file-closed), while tong-cloth, taro field and "hundred-fold springs" score zero in the poetry corpus too; the page is 100%-self-rated yet carries three 另 markers -- the completeness/markers orthogonality cross-section re-verified (first recorded 100%-side is V054) -- and its three variant pairs show three species: a whole-phrase branch variant (three characters against three), the plain single-character species, and a branch carrying an inner "one reads" gloss with a component-description stand-in for an unencodable graph (first recorded); bare-name anchor (second sighting, as V062), juan 126 anchor+stub exactly two (file-closed), base note full non-empty, double category lines logged with non-source disclaimers; zero new sources (juan 126''s row reused for the seventh time); the poem body hits its two-use ceiling (V018 first, twin normalized needles, closure declared); PERSON first-cites the New History''s "Jin was Shu-prefecture governor and had not returned" (the self-demotion memorial sentence stays closed to V040) -- the poem urges another man to go civilize Shu while the biography shows the poet memorializing to bring his own brother back from it: the poem exhorts others, the memorial pleads for family (reading stance, not history); both biographies contain not one occurrence of Zizhou, shijun, cuckoo or Wen Weng (machine-asserted); KNOWN zero honestly recorded (nineteenth instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 63);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V063 精确回滚：只删 V063 插入的行（id 全枚举）。零 source 删除：',
         '-- source-quantangshi-126 是 V035/V039/V052/V054/V060/V062 已立的卷126 源行（本迁移第七次复用），绝不删；',
         '-- work-t300-064 本体、其 text_line 8 行与 source-ws-t300-064 都是 V018 的行，绝不删；',
         '-- source-xintangshu-wenyi/zizhi-tongjian-events 均为他迁移所立，零删除；V063 零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 63;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT1, WS_CAT2,
              WS_L1, WS_L2, WS_L3, WS_L4,
              XTS_S, TJ_ZZ1, TJ_ZZ2, TJ_ST, TJ_SM, TJ_BC, Q126, Q126_S]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 底注全锚 + 题行 + 双分类行照登硬卡（CITY ws 引文）
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-064-city' and s == 'source-ws-t300-064')
    if '卷126#送梓州李使君|' not in city_ws:
        bad.append('底注全锚未逐字入 CITY 引文（全锚形态照登硬卡）')
    if '| title    = 送梓州李使君' not in city_ws:
        bad.append('题行未逐字入 CITY 引文（送蜀刺史题面照登硬卡）')
    if '[[Category:五言律詩]]' not in city_ws or '[[Category:送別詩]]' not in city_ws:
        bad.append('分类双行未逐字入 CITY 引文（双分类行首见照登硬卡）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-064-city' and s == 'source-ws-t300-064'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # 裸名锚照登硬卡
    city_q = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-064-city' and s == 'source-quantangshi-126')
    if '==[[送梓州李使君]]==' not in city_q:
        bad.append('裸名锚点未逐字入 CITY 引文（裸名式第二见照登硬卡）')
    # SCENE 三枚标记原样 + 第二引上限声明硬卡
    s_ex = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-064-scene')
    for mk in ('{{另|千山響|鄉音聽}}', '{{另|夜|半}}', '{{另|橦|一作[上宗下貝]}}'):
        if mk not in s_ex:
            bad.append(f'SCENE 引文缺标记原样「{mk}」（三形态照登硬卡）')
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-064-scene')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054–V062 同款硬卡）')
    # WORLD：五段史文必须在引文内（判决证据）；诗句/在册句零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-064-world')
    for tok in ('貶晙為梓州刺史', '段子璋反', '參天可汗道', '火炬於樹杪', '城數百重'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（贬所叛镇/三字撞字必须入引）')
    for tok in ('萬壑', '樹參天', '百重泉', '杜鵑', '文翁', '橦布', '芋田', '巴人', '漢女',
                '儒化成', '再剖符', '鄉音'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入在册/诗句项「{tok}」（诗语与杜甫在册句不得入通鉴引文）')
    # PERSON：蜀州刺史句在引 + 自表句零重开
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-064-person')
    if '蜀州刺史未還' not in p_ex:
        bad.append('PERSON 引文缺蜀州刺史未还句（首引前提）')
    for tok in ('己有五短', '願歸所任官', '放田里', '召縉為左散騎常侍', '議者不之罪'):
        if tok in p_ex:
            bad.append(f'「{tok}」他迁移已引零重开——不得入本迁移引文')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-064':
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
                '山中相送罷', '日暮掩柴扉', '一作山中送別',
                '聚斂為長策', '脫巾解帶', '解帶繫頸', '議者不之罪',
                '晚年唯好靜', '漁歌入浦深'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句五律 2/2/2/2 第五次
    if {k: len(v) for k, v in BG_LINES.items()} != {k: 2 for k in BG}:
        bad.append('八句 background_line 须每层恰 2（2/2/2/2）')
    if sorted(n for seqs in BG_LINES.values() for n in seqs) != list(range(1, 9)):
        bad.append('2/2/2/2 须覆盖 1-8 句各一次')
    if len(re.findall(r"text-work-t300-064-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # 零新 source（V052 教训：断言文案也不得出现该字面量）
    if 'INSERT INTO poetry_' + 'source' in sql:
        bad.append('V063 有意零新 source，但 SQL 里出现了诗源表新建插入语句')
    if 'DELETE FROM poetry_source' in build_rollback():
        bad.append('回滚不得删任何 source 行（卷126 源行为六迁移所立）')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V063 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V063 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-064' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V063 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-064' AS subject_id" in sql:
        bad.append('V063 的 claim 主语应全部是 bg-064-*，work-t300-064 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V063 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '只貶所與叛鎮' not in body_all:
        bad.append('BG/文件头须含「梓州在史部只貶所與叛鎮」判决声明')
    if '同字两界第八形态' not in body_all:
        bad.append('BG 须含「同字两界第八形态」声明')
    if '文翁在史部七十五卷全零' not in body_all:
        bad.append('BG 须含「文翁在史部七十五卷全零」判决声明')
    if '整语支' not in body_all or '构件描述' not in body_all:
        bad.append('BG/CITY 须含「整语支/构件描述支」异文三形态声明')
    if '诗劝人，表求己' not in body_all:
        bad.append('BG/PERSON 须含「诗劝人，表求己」对句')
    if '传不载蜀' not in body_all:
        bad.append('BG/PERSON 须含「传不载蜀」负证声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 17 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（新传王维段）；'
              f'五处年标题窗口断言（開元九年七二一/上元二年七六一/貞觀二十一年六四七/天復三年九〇三/貞觀十九年六四五）；'
              f'负证机器复查五层（通鉴文翁/李使君/杜鵑/橦布/芋田/漢女/巴人/訟芋全零+'
              f'梓州恰31十四卷闭域+梓州刺史恰二+使君恰14十一卷闭域+參天/樹杪/百重各恰一/'
              f'全唐詩橦布芋田百重泉漢女輸亦全零+文翁恰三(vol222/228)+杜鵑恰23+樹杪恰四闭域/'
              f'卷126 送梓州李使君恰二=锚一桩一闭域/ws 三枚标记各恰一具体字样+他标记全零+100%+三百首+全锚+分类双行/'
              f'两传全文梓州/使君/杜鵑/文翁全零，快照变动即中止）；'
              f'前提全库查重硬卡六件（蜀州刺史句零引+正文双针恰一=V018+己有五短恰一=V040+'
              f'召缙句恰一=V061+议者句恰一=V062）；'
              f'底注全锚+题行+裸名锚+分类双行照登硬卡；SCENE 三枚标记原样+第二引/上限硬卡；'
              f'贬所叛镇/三字撞字入引+诗语与杜甫在册句零混入断言；'
              f'己有五短/召缙/议者零重开断言；判例只引不重开断言（含 V061 送別/V062 酬張少府诸语——'
              f'前两迁移已用语一个不重开）；'
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
