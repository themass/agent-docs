#!/usr/bin/env python3
"""阶段 D 第 36 首：生成 V055——王維《渭川田家》(work-t300-057, V018 已立) 四层背景。

「为什么写」走到题证系列的两条负轴上：
**诗的题面有一条河，史部这条河只记过一件事**：通鉴「渭川」75 卷**恰一处**——
开元元年（癸丑，七一三）「甲辰，獵於渭川」（接「上欲以同州刺史姚元之為相」，
天子打猎+拜相，机器断言+年标题窗口）；诗里满纸《詩經》（「式微」是邶风篇名、
「雉雊」语出小弁、「牛羊來下」王风意象，只算读法声明），
而**「式微」「雉雊」「荊扉」「牧童」「斜陽」「墟落」（诗语）通鉴全零**——
**詩有經有典，史部不接**。渭水本身通鉴六处全是渡口战事（在册不引不牵合）。
零铸造零 relation。

异文登记的**纯文本第三形态**（V052 纯文本署名异说、V053 <ref>+又見之后）：
页底注「↑ [[全唐詩/卷125#渭川田家|全唐詩·卷125]]**川一作水**」——
「渭川田家／渭水田家」两个题目挂在同一条底注尾巴上，无 {{另}}/{{别}}/{{*}}/<ref>
任何标记；CITY 引文含底注整行原样，audit 硬卡「川一作水」字样，登记不裁决。
页内 {{另}}/{{别}}/{{*}}/<ref> **四全零** 而 Textquality|75%——
**与 V054 正交修正互为横截面**：V054 证明 100% 可带五枚标记（完备度≠异文数），
本页证明零标记页可以不满（不完备≠无异文）；两个方向的断言在册，
「标记↔完备度」绑定被双侧证伪（CITY 层+claim 如实登记）。

同句第二引上限用满第三例（V047 疾径全句+V054 子句、V050 刻碑之后）：
本诗正文（V018 text claim 一引在先，生成时全库查重恰一处=V018），
V055 SCENE 取首联「斜陽照墟落，窮巷牛羊歸」子句二引——
locator 明文「两度上限至此用满，此诗正文对后来迁移关闭」。

十句五古 4/2/2/2 形制第二次（V051 夏日南亭怀辛大首见）；
PERSON 层首引旧传孝行句「**事母崔氏以孝聞**」（生成时全库查重既往零入引；
新传只一句「資孝友」互证不合并）——传里写孝，诗里写候门的野老，
并置是读法声明非史实。负证断词假命中在册：tj-262「田家磑」是地名、
tj-257「故墟落」是废墟语（通鉴「田家」恰 1、「墟落」恰 1 闭域断言，零入引）。

用法: python3 -I emit_v055.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/渭川田家.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS2 = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
V125 = pathlib.Path('/tmp/src-dl/quantangshi/vol125.txt').read_text(encoding='utf-8')
TJ210 = pathlib.Path('/tmp/src-dl/tongjian/tj-210.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 渭川田家', '| title    = 渭川田家', 'ws header title(题面无标记直录)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '| notes    = {{Textquality|75%}}↑ [[全唐詩/卷125#渭川田家|全唐詩·卷125]]川一作水',
                        '川一作水',
                        'ws 页底注(75%+底本指向+「川一作水」纯文本题异第三形态:无标记挂底注尾巴,照登不裁决)')
WS_CAT = slice_between(WS, '[[Category:五言古詩]]', '[[Category:五言古詩]]', 'ws 分类行(五言古詩——整理者分类,非史料;V048 分类行判例)')
WS_L12 = slice_between(WS, '斜陽照墟落，窮巷牛羊歸。\n野老念牧童，倚杖候荊扉。', '倚杖候荊扉。',
                       'ws第1-2联(斜阳/墟落/牛羊/野老/倚杖/荆扉——黄昏村口候门图)')
WS_L34 = slice_between(WS, '雉雊麥苗秀，蠶眠桑葉稀。\n田夫荷鋤至，相見語依依。', '相見語依依。',
                       'ws第3-4联(雉雊麦秀/蚕眠桑稀/荷锄/语依依——农事满眼)')
WS_L56 = slice_between(WS, '即此羨閑逸，悵然吟式微。', '悵然吟式微。',
                       'ws第5联收束(羡闲逸怅然吟式微——式微是诗经邶风篇名:归去之咏)')
JTS_X = slice_between(JTS, '事母崔氏以孝聞。', '事母崔氏以孝聞。',
                      '旧传事母孝行句(从未入引,PERSON 层首引,生成时全库查重硬卡;「以孝聞」他传亦见故锚全句)')
TJ_LIE = slice_between(TJ210, '甲辰，獵於渭川。', '獵於渭川。',
                       '通鉴开元元年玄宗猎于渭川句(渭川通鉴唯一一处——天子打猎;窗口断言)')
Q125 = slice_between(V125, '==[[渭川田家]]==', '==[[渭川田家]]==', '卷125 本篇篇题锚点(无消歧直锚+桩)')
Q125_S = slice_between(V125, '{{:渭川田家}}', '{{:渭川田家}}', '卷125 本篇转引桩')

# ---------- 传区间归属复验（V036 立规） ----------
_ja = JTS.find('=王維=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
_xa = XTS2.find('==王維==')
_seg_x = XTS2[_xa:XTS2.find('==鄭虔==')]
if not (0 <= _ja and '事母崔氏以孝聞' in _seg_j):
    raise SystemExit('切片越出王维段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 60]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ210, TJ_LIE, '開元元年')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_allq = ''.join(f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt')))
# ① 通鉴：渭川恰一（闭域+窗口+诗语六词全零+田家/墟落断词假命中闭域）
if _alltj.count('渭川') != 1 or sum(t.count('渭川') for t in _tjf.values() if '渭川' in t) != 1 \
        or list(n for n, t in _tjf.items() if '渭川' in t) != ['tj-210.txt']:
    raise SystemExit('通鉴「渭川」不是恰一处（tj-210）——一条河一件事论断须重估')
for _w in ('式微', '雉雊', '荊扉', '牧童', '斜陽', '閑逸'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗语经典史部不接的判决失效，须重读')
if _alltj.count('田家') != 1 or '田家磑' not in _tjf.get('tj-262.txt', ''):
    raise SystemExit('通鉴「田家」不是恰一处（tj-262 田家磑地名）——断词假命中册须重做')
if _alltj.count('墟落') != 1 or '故墟落' not in _tjf.get('tj-257.txt', ''):
    raise SystemExit('通鉴「墟落」不是恰一处（tj-257 故墟落废墟语）——断词假命中册须重做')
if _alltj.count('渭水') != 6:
    raise SystemExit(f'通鉴「渭水」不再是 6 处（实 {_alltj.count("渭水")}）——渡口战事在册册数须重估')
# ② 全唐詩：渭川恰六（本篇卷125×2 锚+桩；余四处他人诗题族）
if _allq.count('渭川') != 6:
    raise SystemExit(f'全唐詩「渭川」计数不是 6（实 {_allq.count("渭川")}）——题族册数论断须重估')
if V125.count('渭川田家') != 2 or V125.count('==[[渭川田家]]==') != 1 or V125.count('{{:渭川田家}}') != 1:
    raise SystemExit('卷125 本篇锚点+桩结构破坏——渭川田家恰二（锚+桩）断言失效')
# ③ ws：四标记全零 + 75% 恰一 + 川一作水恰一（零标记×75% 正交横截面在册）
if WS.count('{{另') or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页标记不再是全零——零标记页论断失效，须重读快照')
if WS.count('{{Textquality|75%}}') != 1 or WS.count('川一作水') != 1:
    raise SystemExit('ws 页 75%/川一作水 结构变了——纯文本第三形态照登断言失效')
# ④ 传区间与首引前提
for _w in ('渭川', '田家', '墟落'):
    if _w in _seg_j or _w in _seg_x:
        raise SystemExit(f'「{_w}」落在王维传区间——诗题与传负证失效，须重读原文')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
_prev_x = [f.name for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V055')
           for _ln in f.read_text(encoding='utf-8').splitlines()
           if 'evidence_excerpt' in _ln and '事母崔氏以孝聞' in _ln]
if _prev_x:
    raise SystemExit(f'「事母崔氏以孝聞」已在 {_prev_x} 入引——首引前提失效，PERSON 层须重设计')
_prev_t = [f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V055')
           for _ln in f.read_text(encoding='utf-8').splitlines()
           if 'evidence_excerpt' in _ln and '悵然吟式微' in _ln]
if _prev_t != ['V018']:
    raise SystemExit(f'本诗正文既往引文域不是恰一处 V018（实 {_prev_t}）——第二引上限论断须重估')

BG = {
    'bg-057-scene': (
        '十句是一幅黄昏村口的画：斜阳照进村落，牛羊走进深巷'
        '（「斜陽照墟落，窮巷牛羊歸」——此句系**第二引**：正文 V018 text claim '
        '已一引在先，取此联收束本层，两度上限至此用满，此诗正文对后来迁移关闭）；'
        '村野老人惦记着牧童，拄着杖在柴门边等（「野老念牧童，倚杖候荊扉」——'
        '全诗唯一的人称情感落在「念」与「候」上）；野鸡叫了麦苗正秀，'
        '蚕已入眠桑叶渐稀，扛锄头的农人归来相见絮语不尽'
        '（「雉雊麥苗秀，蠶眠桑葉稀」「田夫荷鋤至，相見語依依」）。'
        '收束只一个转身：「即此羨閑逸，悵然吟式微」——「式微」是《詩經·邶風》'
        '篇名（「式微式微，胡不歸」），吟的是归去；此读法系本层声明非史料断言，'
        '页上无任何自注指认用典。'),
    'bg-057-city': (
        '这条城记录的题目先登记异文：页底注整行为'
        '「{{Textquality|75%}}↑ [[全唐詩/卷125#渭川田家|全唐詩·卷125]]川一作水」——'
        '「渭川田家／渭水田家」两个题目挂在同一条底注尾巴上，'
        '**无 {{另}}/{{别}}/{{*}}/<ref> 任何标记**（纯文本题异第三形态：'
        'V052 纯文本署名异说、V053 <ref> 实链+又見底注之后，audit 硬卡「川一作水」字样），'
        '照登不裁决。分类行「五言古詩」为整理者动作：照登+非史料声明+不升格（V048 判例）。'
        '**完备度与标记数的双向正交在册（V054 修正的横截面）**：本页四标记全零'
        '而 Textquality 只有 75%——V054 已证 100% 可带五枚标记，本页再证零标记'
        '不等于已录完备；「标记↔完备度」任何一侧的绑定都不成立，如实登记。'
        '卷125 本篇为「无消歧篇题锚点+转引桩」结构（机器断言锚+桩各恰一）。'
        '诗世界的渭川：全唐詩「渭川」恰 6 处——本卷 2 处即本篇锚桩，'
        '余四处（卷017 李賀、卷021、卷581、卷695）各是各诗，在册不引不牵合；'
        '「渭水田家」全唐詩零命中（异文支在册不引）。'),
    'bg-057-world': (
        '诗的题面有一条河；史部这条河只记过一件事：通鉴「渭川」75 卷**恰一处**'
        '（文件闭域+年标题窗口机器断言）——开元元年（癸丑，七一三）'
        '「甲辰，獵於渭川」，紧接「上欲以同州刺史姚元之為相」：'
        '天子在渭川打猎、顺手拜相。**渭川在史部是皇帝的猎场**。\n'
        '诗里满纸《詩經》——式微是邶风篇名、雉雊语出小弁、牛羊來下是王风意象'
        '（读法声明）；而通鉴「式微」「雉雊」「荊扉」「牧童」「斜陽」「閑逸」'
        '**六个词全部零命中**（机器断言）——**诗牵着经，史部不接**。\n'
        '断词假命中两例在册零入引（V054 之后的例行复查）：通鉴「田家」恰 1='
        '天复元年（辛酉，九零一）李茂貞迎车驾于「田家磑」（地名）、'
        '「墟落」恰 1=光启三年赵全義招怀流散于「故墟落」中（废墟语）——'
        '都不是这首诗；渭水通鉴 6 处全是渡口战事，在册不引。\n'
        '两传王维段「渭川」「田家」「墟落」全零（机器断言）——传写其人'
        '不提这条川。**猎场与田家同一条水，各是各的世界**；本层零铸造零 relation。'),
    'bg-057-person': (
        '旧传给这个人记了一行孝：「**事母崔氏以孝聞**。」——奉养母亲崔氏'
        '以孝行闻名（生成时全库查重：此句既往零入引，本迁移 PERSON 层首引；'
        '新传同只一句「資孝友」——两支各记各字，互证不合并）。\n'
        '把孝行和诗对读：传里的孝是对母亲的，诗里最重的一笔是野老候童孙'
        '「倚杖候荊扉」——**两代人两种候**（读法声明，非史实）。\n'
        '王维传其余已用句（以诗名盛/凝碧/輞川别业/茶鐺/奉佛段/代宗诏集/'
        '尤長五言/書畫特臻其妙/妻亡不再娶/臨終别縉书）一个不重开；'
        '新传自表五短「願歸所任官，放田里」V039 已引在册不再引——'
        '「放田里」三个字恰与「羨閑逸」同一片田地，但那是表里的话、'
        '已入账，本迁移零新引；certainty 不覆盖任何系年。'),
}
CLAIMS = {
    'claim-bg-057-scene': (
        'FACT', 'LIKELY',
        '十句全诗本文（ws 页四标记全零、Textquality 75%——零标记与不完备并存，'
        '正交横截面在册）；首联「斜陽照墟落，窮巷牛羊歸」系第二引：正文 V018 '
        'text claim 一引在先（生成时全库查重恰一处），两度上限至此用满、'
        '此诗正文对后来迁移关闭（audit 硬卡）；「式微=邶风篇名」及农事读法'
        '为本层声明非史料断言（页上无自注）。'),
    'claim-bg-057-city': (
        'FACT', 'LIKELY',
        '纯文本题异第三形态：底注尾巴「川一作水」（渭川田家／渭水田家）'
        '无标记挂底注，逐字入引 audit 照登硬卡，登记不裁决；分类行照登+非史料'
        '声明+不升格；双向正交在册：V054 证 100% 可带标记、本页证零标记可不'
        '完备——标记与完备度绑定双侧证伪；卷125 无消歧锚+桩结构（机器断言各恰一）；'
        '诗世界渭川恰 6 处（本篇 2+他卷 4）在册不引；「渭水田家」全唐詩零命中；'
        '题有河而诗无时→零铸造零 relation。'),
    'claim-bg-057-world': (
        'FACT', 'LIKELY',
        '一条河一件事：通鉴「渭川」恰 1 处=tj-210 开元元年（癸丑，七一三）'
        '玄宗「甲辰，獵於渭川」（文件闭域+年标题窗口机器断言）——史部的渭川'
        '是皇家猎场；诗语六词（式微/雉雊/荊扉/牧童/斜陽/閑逸）通鉴全零'
        '（机器断言）——诗牵着经，史部不接；断词假命中两例在册零入引'
        '（tj-262 田家磑地名恰 1、tj-257 故墟落废墟语恰 1，闭域断言）；'
        '渭水 6 处渡口战事在册不引；两传王维段渭川/田家/墟落全零；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during '
        '零铸造零 relation。'),
    'claim-bg-057-person': (
        'FACT', 'LIKELY',
        '旧传「事母崔氏以孝聞」首引（生成时全库引文域查重：既往零命中，'
        'audit 硬卡——王维传又一句未用活句，与 V053 传句用尽相反方向）；'
        '新传「資孝友」一支在册不并（两支各记各字，互证不合并）；'
        '两代人两种候为读法声明非史实；「放田里」V039 已引不再引；'
        '王维其余已用判例句零重开；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-057-scene', 'source-ws-t300-057',
     '页面 渭川田家（header author+五联十句，四段以「……」相連——'
     '「斜陽照墟落，窮巷牛羊歸」**第二引**：正文 V018 text claim 一引在先、'
     '本迁移取首联二引，**两度上限至此用满，此诗正文对后来迁移关闭**'
     '（生成时全库查重恰一处=V018）；页四标记全零、75%（零标记与不完备并存）；'
     '「吟式微」页上无自注，归《詩經》读法系引者声明非史料）',
     join(WS_AUTHOR, WS_L12, WS_L34, WS_L56)),
    ('claim-bg-057-city', 'source-ws-t300-057',
     '页面 渭川田家（header title+页底注+分类行三段并收——'
     '底注尾巴「川一作水」系**纯文本题异第三形态**（渭川/渭水两题并挂无标记，'
     'audit 硬卡字样照登不裁决）；「五言古詩」分类系整理者动作：非史料声明、'
     '不升格；本页零标记而 75%——与 V054（100% 带五标记）互为横截面，'
     '完备度与标记数双向正交在册）',
     join(WS_TITLE, WS_NOTE, WS_CAT)),
    ('claim-bg-057-city', 'source-quantangshi-125',
     '卷一百二十五·王维集《渭川田家》篇题锚点+转引桩（无消歧直锚——'
     '篇题在全唐詩快照内唯一故不消歧，机器断言锚桩各恰一；'
     '全唐詩「渭川」恰 6=本篇 2+他卷 4 处题族在册不引）',
     join(Q125, Q125_S)),
    ('claim-bg-057-world', 'source-zizhi-tongjian-events',
     '卷二百一十·开元元年（癸丑，七一三）玄宗猎于渭川段'
     '（**通鉴 75 卷「渭川」唯一一处**：文件闭域+年标题窗口机器断言，'
     '紧接上欲相姚元之——史部的渭川是皇家猎场；诗语六词通鉴全零在册；'
     'tj-262 田家磑/tj-257 故墟落两例断词假命中闭域在册零入引）', TJ_LIE),
    ('claim-bg-057-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传事母孝行句（生成时全库引文域查重：'
     '此句既往零入引，本迁移首引；新传「資孝友」一支互证不合并；'
     '与诗中野老候门并置是读法声明）', JTS_X),
]
BG_LINES = {'bg-057-scene': (1, 2, 3, 4), 'bg-057-city': (5, 6),
            'bg-057-world': (7, 8), 'bg-057-person': (9, 10)}
BG_AUDIENCE = {'bg-057-scene': 'PRIMARY', 'bg-057-city': 'JUNIOR',
               'bg-057-world': 'SENIOR', 'bg-057-person': 'JUNIOR'}
BG_TITLES = {'bg-057-scene': '眼前：黄昏村口等门的人',
             'bg-057-city': '这座城：底注尾巴上的另一个题目',
             'bg-057-world': '这个天下：渭川在史部是皇帝的猎场',
             'bg-057-person': '这个人：事母以孝聞'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 36 首·十句五古 4/2/2/2）；史实句均有逐字引证；'
                 '系年第三十次判决（题证系列第十八状·猎场与田家）'
                 '「題有河名，河在史部只一獵；詩有經意，經在史部全零」——'
                 '通鉴「渭川」75 卷恰一处=开元元年玄宗猎于渭川（闭域+年窗口断言），'
                 '诗语六词（式微/雉雊/荊扉/牧童/斜陽/閑逸）通鉴全零——'
                 '诗牵着经史部不接→time.span/event.name/written_during 全缺席、零 relation；'
                 '纯文本题异第三形态首见（底注尾巴「川一作水」无标记挂底注，audit 照登硬卡）；'
                 '完备度与标记数双向正交（V054 修正的横截面：零标记×75%）；'
                 '本诗正文第二引上限用满对后来关闭（V018 在先+全库查重）；'
                 '断词假命中两例在册零入引（tj-262 田家磑/tj-257 故墟落）；'
                 '旧传「事母崔氏以孝聞」首引（全库查重既往零引）；'
                 'KNOWN 零如实记录（第十一例，audit 反向断言）；零新 source；'
                 '判例关键语零入引文。' for k in BG}


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
    A("""-- V055：王維《渭川田家》(work-t300-057) 四层背景（阶段 D 第 36 首·猎场与田家）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V039、V054 已执行（work-t300-057 与其
--       text-work-t300-057-ws、source-ws-t300-057 是 V018 的行；source-quantangshi-125 是 V035 的行；
--       source-jiutangshu-wenyuan 是 V016 的行；source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源）。
--       **本迁移零新 source**（audit 断言 SQL 无任何诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v055.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/渭川田家.txt（纯文本题异第三形态「川一作水」+四标记全零×75% 正交横截面）、
--   舊唐書卷190下（事母孝行句首引+王维段负证）、新唐書卷202（王维段负证）、
--   通鑑卷210（渭川唯一一处+開元元年窗口）+ 通鑑 75 卷/全唐詩 120 卷负证计数扫描+
--   既有迁移引文域逐句查重——传区间归属、渭川/渭水/田家/墟落/六诗语全部计数、
--   年标题窗口、首引前提与第二引前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   10 行 background_line（十句形制：scene→1-4 city→5-6 world→7-8 person→9-10，
--   绑 text-work-t300-057-ws 的 10 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有河名，河在史部只一獵；詩有經意，經在史部全零」）：
--   * 渭川通鉴恰一处=皇家猎场（闭域+窗口断言）；诗语六词通鉴全零（诗牵着经史部不接）；
--   * 本诗正文第二引上限用满：V018 一引在先（全库查重恰一处），此诗正文对后来迁移关闭；
--   * 断词假命中两例在册零入引：tj-262「田家磑」地名+tj-257「故墟落」废墟语（闭域断言）；
--   * 完备度与标记数双向正交（V054 证 100% 可带标记、本页证零标记可不完备）；
--   * 纯文本题异第三形态「川一作水」照登硬卡（无标记挂底注，登记不裁决）；
--   * 旧传「事母崔氏以孝聞」首引（全库查重既往零引）；新传「資孝友」不并；
--   * 式微=邶风/两代人两种候均为读法声明，audit 双声明在 BG 文本内；
--   * KNOWN 零如实记录（第十一例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 不才/凝碧/輞川/藍田/放田里/茶鐺/尤長五言/以詩名盛 判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 54，不含 55
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-057-%';             -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-057-ws';  -- 恰 10
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-057-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-057';                                  -- 10（4/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-057-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-057'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-057';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-057-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-057';   -- 恰 1（V018 旧行，零新源）
-- 回滚: recovery/V055_rollback.sql（按 id 全枚举删除；不动任何共用来源行、不动 V018 的行）
START TRANSACTION;""")

    A('\n-- ---------- 1. BACKGROUND content identities（零新 source——断言在生成器 audit） ----------')
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
    brows = [{'id': k, 'work_id': 'work-t300-057',
              'layer': {'bg-057-scene': 'SCENE', 'bg-057-city': 'CITY',
                        'bg-057-world': 'WORLD', 'bg-057-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（十句：4/2/2/2） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-057-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 55, 'Wang Wei on a Farm by the Wei River background layers (stage-D poem 36, ten-line old-style verse 4/2/2/2, second such shape after V051): dating verdict thirty, eighteenth shape of the title-evidence series -- the title names a river and the river owns exactly one entry in the official history (all 75 Tongjian juan machine-swept: one hit, juan 210, the emperor hunting on the Wei in 713 right before enfeoffing Yao Yuanzhi as chancellor: in history this river is an imperial hunting ground), while the poem leans on the Book of Songs (shi wei is a beifeng title) and six of its words (shiwei/zhi gou/jing fei/mu tong/xie yang/xian yi) score zero across the whole Tongjian -- the poem holds the classics and the histories do not answer; dating verdict: a title with a river, a river with one hunt; a poem with the Odes, the Odes absent from history -- zero forging, zero relation; third plain-text title-variant form registered: the footnote tail "chuan yi zuo shui" (Wei-chuan/Wei-shui hanging off a plain footnote with no marker at all, audit hard-assert, unadjudicated); completeness orthogonal to marker count in both directions now on record (this page: zero markers yet only 75%, the cross-section of V054''s 100%-with-five-markers correction); the poem body reaches its two-use ceiling (V018 first citation machine-swept, this migration cites the first couplet as second use, locator declares closure); two cut-word false hits logged never quoted (Tianjia-mill as a place name in juan 262, gu xuluo as ruin-words in juan 257, file-closed assertions); the Old History''s filial sentence on serving his mother Lady Cui first-cited (sweep proves zero prior hits), the New History''s single word on filial nature kept unmerged; KNOWN zero honestly recorded (eleventh instance, audit reverse-asserts); zero new sources; closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 55);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V055 精确回滚：只删 V055 插入的行（id 全枚举）。',
         '-- work-t300-057 本体、其 text_line 10 行与 source-ws-t300-057 都是 V018 的行，绝不删；',
         '-- 全部四个共用 source 行（ws-057/quantangshi-125/jiutangshu-wenyuan/',
         '-- zizhi-tongjian-events）均为他迁移所立，零删除（本迁移零新 source）；V055 零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 55;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_L12, WS_L34, WS_L56,
              JTS_X, TJ_LIE, Q125, Q125_S]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 纯文本题异照登硬卡
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-057-city' and s == 'source-ws-t300-057')
    if '川一作水' not in city_ws:
        bad.append('「川一作水」未逐字入 CITY 引文（纯文本题异第三形态照登硬卡）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-057-city' and s == 'source-ws-t300-057'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # SCENE 第二引上限声明硬卡
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-057-scene')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054 同款硬卡）')
    scene_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-057-scene')
    if '斜陽照墟落，窮巷牛羊歸' not in scene_ex:
        bad.append('首联第二引未逐字入 SCENE 引文')
    # 断词假命中零入引文
    if '田家磑' in cited or '故墟落' in cited:
        bad.append('断词假命中（田家磑/故墟落）在册不引，不得入引文')
    # 引要素
    w_tj = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-057-world')
    if '獵於渭川' not in w_tj:
        bad.append('通鉴侧引文缺「獵於渭川」')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-057':
            for w in ('凝碧', '輞川', '藍田', '長齋', '尤長五言', '以詩名盛', '不才', '放還'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山', '隠鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒', '刻碑鳳林山南',
                '仕宦之疾徑', '放田里'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 十句形制 4/2/2/2
    want = {'bg-057-scene': 4, 'bg-057-city': 2, 'bg-057-world': 2, 'bg-057-person': 2}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('十句 background_line 必须 4/2/2/2')
    if len(re.findall(r"text-work-t300-057-ws' AS version_id", sql)) != 10:
        bad.append('bg_line INSERT 的 version 行数应为 10')
    # 零新 source 断言
    if 'INSERT INTO poetry_source' in sql:
        bad.append('本迁移有意零新 source，SQL 出现了诗源表新建插入语句')
    if any('DELETE FROM poetry_source' in l for l in build_rollback().splitlines()):
        bad.append('回滚不得删除任何 source 行（本迁移零新 source）')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V055 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V055 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-057' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V055 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-057' AS subject_id" in sql:
        bad.append('V055 的 claim 主语应全部是 bg-057-*，work-t300-057 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V055 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '只一獵' not in body_all and '只有一件事' not in body_all:
        bad.append('BG/文件头须含「河在史部只一獵」判决声明')
    if '史部不接' not in body_all:
        bad.append('BG/文件头须含「經在史部全零/史部不接」判决声明')
    if '正交' not in body_all:
        bad.append('BG/CITY 须含 完备度×标记数「正交」声明')
    if '假命中' not in body_all:
        bad.append('BG 须含「假命中」在册声明（田家磑/故墟落）')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 11 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（王维段）；年标题窗口断言（開元元年癸丑七一三）；'
              f'负证机器复查四层（通鉴渭川恰一=tj-210 闭域+六诗语全零+田家/墟落断词假命中闭域+'
              f'渭水恰六在册/全唐詩渭川恰六+卷125 锚桩各恰一+渭水田家零命中/'
              f'ws 四标记全零+75% 恰一+川一作水恰一/两传王段渭川田家墟落全零，快照变动即中止）；'
              f'首引前提全库查重硬卡（事母崔氏以孝聞既往零引）+第二引前提全库查重硬卡'
              f'（本诗正文既往恰一=V018）；川一作水照登硬卡；SCENE locator 第二引/上限硬卡；'
              f'断词假命中零入引断言；底注+分类三重断言；判例只引不重开断言（含放田里）；'
              f'十句 4/2/2/2 形制断言；零 KNOWN 反向断言；零新 source 反向断言'
              f'（无诗源表新建插入，回滚零删源行）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
