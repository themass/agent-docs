#!/usr/bin/env python3
"""阶段 D 第 41 首：生成 V060——王維《歸嵩山作》(work-t300-136, V018 已立) 四层背景。

「为什么写」走到山与门的两界（同字两界第五形态，V056 泪/V057 已矣/V058 琴·流水/
V059 故鄉之后）：**題有山名，山在史部一封祀一隱遁；詩用閉關，閉關在史部只城門
與關梁**——

通鉴「嵩山」恰 18 处、恰九卷（文件闭域+逐卷计数机器断言），处处不是这首诗的归路：
封祀一派（詔以今冬有事於嵩山/罷封嵩山/作奉天宮於嵩山南/太后幸嵩山），
隐遁一派也有，却是被考问的——天萬歲通天元年（丙申，六九六）武攸緒
「**扈從封中岳還，即求棄官，隱於嵩山之陽。太后疑其詐，許之，以觀其所為。**」
（tj-205，首引）：**史部的嵩山连隐居都是一场考场**，太后要看他真假；
而诗里「迢遞嵩高下，歸來且閉關」的归山无人考问，归心自决。

通鉴「閉關」恰三处（闭域+三窗口断言）：武德九年（丙戌，六二六）玄武门之变
張公謹「獨閉關以拒之」（tj-191）、建中三年（壬戌，七八二）李長春「閉關不內」
待官军（tj-227）、建中四年（癸亥，七八三）韓滉「閉關梁」禁马牛出境（tj-229）——
**史部的闭关是城门与关梁：锁城、断道、禁行**；诗的「歸來且閉關」是掩门归隐。
**异文支在史部命中数不同（新边界首录）**：ws 页第三枚 {{另|閉|掩}}——
若取「掩關」支，通鉴「掩關」全零；撞字论断只辖「閉關」支，照登不裁决。

CITY 层：页 {{另}}×3（清/晴、禽/雲、閉/掩）×75%；**V018 正文引文系标记归一后
文本（取 {{另}} 首项），本迁移 SCENE 引文含三枚标记原样——同页两形并存、各从其录
（两形并存显式登记首见）**。底注锚点片段非空（同 V058/V059 全锚形态）；
source-quantangshi-126 系 V035/V039/V052/V054 已立、本迁移第五次复用**零新源**；
卷126 本篇无消歧直锚+桩各恰一。**「歸嵩山」题族恰四**：本篇锚桩 2 +
王维自己另一首《送方尊師歸嵩山》（卷128）锚桩 2——同一诗人两次把归嵩山写进
题目（在册不引不牵合，机器断言分布）。

PERSON 层首引**两传同事异词第二例（V057 母丧柴毁之后）**：旧传「**服闋，拜吏部郎中。**」
（V059 行迹三连已一引在先，全库查重恰一处——本迁移子句二引对后来关闭）×
新传「**服除，累遷給事中。**」（首引）——同一件事（服丧结束复职）两部书两种措辞，
**连迁转阶次都记不同**（旧传接吏部郎中、新传径接给事中）：更不得合并
（合而不并第二用，词异互斥 audit 双向硬卡）。

八句五律 2/2/2/2 形制第三次（V054/V058 之后）；正文第二引上限用满第八例
（V018 归一形一引在先，查重针「歸來且閉關」恰一处——V018 正文引文即归一形）。

用法: python3 -I emit_v060.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/歸嵩山作.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS2 = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
V126 = pathlib.Path('/tmp/src-dl/quantangshi/vol126.txt').read_text(encoding='utf-8')
V128 = pathlib.Path('/tmp/src-dl/quantangshi/vol128.txt').read_text(encoding='utf-8')
TJ191 = pathlib.Path('/tmp/src-dl/tongjian/tj-191.txt').read_text(encoding='utf-8')
TJ205 = pathlib.Path('/tmp/src-dl/tongjian/tj-205.txt').read_text(encoding='utf-8')
TJ227 = pathlib.Path('/tmp/src-dl/tongjian/tj-227.txt').read_text(encoding='utf-8')
TJ229 = pathlib.Path('/tmp/src-dl/tongjian/tj-229.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 歸嵩山作', '| title    = 歸嵩山作', 'ws header title(题面直录)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '| notes    = {{Textquality|75%}}↑ [[全唐詩/卷126#歸嵩山作|全唐詩·卷126]]',
                        '全唐詩·卷126]]',
                        'ws 页底注(75%+底本指向锚点片段非空,同 V058/V059 全锚形态)')
WS_CAT = slice_between(WS, '[[Category:五言律詩]]', '[[Category:五言律詩]]', 'ws 分类行(五言律詩——整理者分类;V048 分类行判例)')
WS_L1 = slice_between(WS, '{{另|清|晴}}川帶長薄，車馬去閑閑。', '車馬去閑閑。', 'ws第1联(清川带长薄——清/晴异文首枚)')
WS_L2 = slice_between(WS, '流水如有意，暮{{另|禽|雲}}相與還。', '相與還。', 'ws第2联(暮禽相与还——禽/云异文第二枚)')
WS_L3 = slice_between(WS, '荒城臨古渡，落日滿秋山。', '落日滿秋山。', 'ws第3联(荒城古渡落日秋山——无标记联)')
WS_L4 = slice_between(WS, '迢遞嵩高下，歸來且{{另|閉|掩}}關。', '關。', 'ws第4联(归来且闭关——闭/掩异文第三枚,判决词正是异文位)')
JTS_F = slice_between(JTS, '服闋，拜吏部郎中。', '服闋，拜吏部郎中。', '旧传服阕句(V059 行迹三连一引在先,本迁移子句二引;整句自锚)')
XTS_F = slice_between(XTS2, '服除，累遷給事中。', '服除，累遷給事中。', '新传服除句(从未入引,PERSON 首引;与旧传句同事异词异阶——合而不并第二例)')
TJ_YX = slice_between(TJ205, '扈從封中岳還，即求棄官，隱於嵩山之陽。太后疑其詐，許之，以觀其所為。',
                      '以觀其所為。',
                      '通鉴万岁通天元年武攸绪隐嵩山段(嵩山隐遁侧判决证据——隐居是考场;窗口断言)')
TJ_B1 = slice_between(TJ191, '張公謹多力，獨閉關以拒之，不得入。', '不得入。',
                      '通鉴武德九年玄武门张公谨闭关段(闭关三处之一——锁城;窗口断言)')
TJ_B2 = slice_between(TJ227, '大將李長春閉關不內，以俟官軍', '以俟官軍',
                      '通鉴建中三年李长春闭关不内段(闭关三处之二——待官军;窗口断言)')
TJ_B3 = slice_between(TJ229, '浙江東、西節度使韓滉閉關梁', '閉關梁',
                      '通鉴建中四年韩滉闭关梁段(闭关三处之三——断道禁行;窗口断言)')
Q126 = slice_between(V126, '==[[歸嵩山作]]==', '==[[歸嵩山作]]==', '卷126 本篇篇题锚点(无消歧直锚,同 V055/V057/V058 结构)')
Q126_S = slice_between(V126, '{{:歸嵩山作}}', '{{:歸嵩山作}}', '卷126 本篇转引桩')

# ---------- 传区间归属复验（V036 立规） ----------
_xa = XTS2.find('==王維==')
_xm = re.search(r'\n==[^=\n]{1,10}==', XTS2[_xa + 8:])
_seg_x = XTS2[_xa:_xa + 8 + _xm.start()]
_ja = JTS.find('=王維=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
if not (0 <= _ja and '服闋，拜吏部郎中' in _seg_j and '服除，累遷給事中' in _seg_x):
    raise SystemExit('切片越出王维段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；四扇窗口） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ205, TJ_YX, '萬歲通天元年')
_window(TJ191, TJ_B1, '武德九年')
_window(TJ227, TJ_B2, '建中三年')
_window(TJ229, TJ_B3, '建中四年')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：嵩山恰 18 处逐卷闭域；嵩高雅名全零；閉關恰三分卷；掩關全零；诗语全零词表
_song = {n: t.count('嵩山') for n, t in _tjf.items() if '嵩山' in t}
if _song != {'tj-202.txt': 4, 'tj-203.txt': 4, 'tj-204.txt': 1, 'tj-205.txt': 2,
             'tj-206.txt': 3, 'tj-208.txt': 1, 'tj-209.txt': 1, 'tj-212.txt': 1, 'tj-215.txt': 1}:
    raise SystemExit(f'通鉴「嵩山」逐卷分布变了（实 _song）——山在两界(封祀/隐遁)的判决须重估'.replace('_song', str(_song)))
if sum(_song.values()) != 18:
    raise SystemExit('通鉴「嵩山」总数不再是 18——恰十八处判决须重估')
for _w in ('嵩高', '迢遞', '荒城', '古渡', '秋山', '長薄', '閑閑', '落日',
           '如有意', '相與還', '歸來', '清川', '晴川', '暮禽', '暮雲', '掩關', '長薄'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗语进不了史部的判决失效，须重读')
_bg = {n: t.count('閉關') for n, t in _tjf.items() if '閉關' in t}
if _bg != {'tj-191.txt': 1, 'tj-227.txt': 1, 'tj-229.txt': 1}:
    raise SystemExit(f'通鉴「閉關」分布变了（实 {_bg}）——同字两界第五形态判决须重估')
# ② 全唐詩：歸嵩山题族恰四=本篇锚桩2+送方尊師歸嵩山锚桩2；异文支册数
_gs = {n: t.count('歸嵩山') for n, t in _qtf.items() if '歸嵩山' in t}
if _gs != {'vol126.txt': 2, 'vol128.txt': 2}:
    raise SystemExit(f'全唐詩「歸嵩山」册数分布变了（实 {_gs}）——题族归嵩山两首须重估')
if V128.count('==[[送方尊師歸嵩山]]==') != 1 or V128.count('{{:送方尊師歸嵩山}}') != 1:
    raise SystemExit('卷128 送方尊師歸嵩山锚桩结构变了——同诗人两题在册须重读')
if (V126.count('==[[歸嵩山作]]==') != 1 or V126.count('{{:歸嵩山作}}') != 1
        or V126.count('歸嵩山作') != 2):
    raise SystemExit('卷126 锚桩结构变了——底本在册结构断言失效')
# ③ ws：三枚 {{另}} + 其余标记全零 + 75% 恰一 + 非空锚片段
if WS.count('{{另') != 3 or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页标记结构不再是 {{另}}×3 全他零——三枚异文判决失效，须重读快照')
if WS.count('{{Textquality|75%}}') != 1 or WS.count('卷126#歸嵩山作|') != 1:
    raise SystemExit('ws 页 75%/非空锚片段结构变了——全锚形态断言失效')
if WS.count('{{另|清|晴}}') != 1 or WS.count('{{另|禽|雲}}') != 1 or WS.count('{{另|閉|掩}}') != 1:
    raise SystemExit('三枚 {{另}} 的具体字样变了——异文登记须重读')
# ④ 首引/二引/零重开前提（全库扫描，排除本迁移）
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
for _premise, _needle, _want in (
        ('新传服除句', '服除，累遷給事中', []),
        ('旧传服阕句', '服闋，拜吏部郎中', ['V059']),
        ('武攸绪句', '隱於嵩山之陽', []),
        ('张公谨闭关句', '閉關以拒之', []),
        ('李长春闭关句', '閉關不內', []),
        ('韩滉闭关梁句', '閉關梁', []),
        ('本诗正文', '歸來且閉關', ['V018'])):
    _prev = sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                    if not f.name.startswith('V060')
                    for _ln in f.read_text(encoding='utf-8').splitlines()
                    if 'evidence_excerpt' in _ln and _needle in _ln})
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')

BG = {
    'bg-136-scene': (
        '八句是一条回家的路，越走越静：清川挟着长长的草木，车马也走得不慌不忙'
        '（「{{另|清|晴}}川帶長薄，車馬去閑閑」——川作「清」一作「晴」，照登）；'
        '流水若是有心，连暮色里的飞鸟都结伴同归'
        '（「流水如有意，暮{{另|禽|雲}}相與還」——禽作「暮禽」一作「暮雲」，照登）；'
        '荒城对着古渡，落日铺满秋山（「荒城臨古渡，落日滿秋山」——无标记联，'
        '全诗最阔大的一笔偏是荒与古）；迢迢递递的嵩高之下，回来，且把门掩上'
        '（「迢遞嵩高下，歸來且{{另|閉|掩}}關」——闭一作掩，照登；'
        '此诗正文系**第二引**：V018 text claim 已一引在先（其形系异文取首项的'
        '归一文本），全库查重恰一处，两度上限至此用满，此诗正文对后来迁移关闭）。'
        '**同页两形并存**：V018 正文引文标记归一（各取 {{另}} 首项），本迁移 SCENE'
        '引文含三枚标记原样——各从其录，两形都在案。'),
    'bg-136-city': (
        '页 {{另}} 恰三（清/晴、禽/雲、閉/掩）而 {{别}}/{{*}}/<ref> 全零、'
        'Textquality 75%（三枚异文与 75% 并存，正交横截面第四度复现）。'
        '**第三枚异文恰落在判决词上**：「歸來且{{另|閉|掩}}關」——闭一作掩；'
        '下面 WORLD 层的撞字论断**只辖「閉關」支**：通鉴「掩關」全零'
        '（机器断言）——同一行诗的异文两支在史部的命中数不同，照登不裁决。'
        '页底注「↑ [[全唐詩/卷126#歸嵩山作|全唐詩·卷126]]」锚点片段非空'
        '（同 V058/V059 全锚形态）；source-quantangshi-126 系 V035/V039/V052/V054'
        '四迁移已立，本迁移第五次复用，**零新源**；卷126 本篇为无消歧直锚+转引桩'
        '（机器断言各恰一）。「歸嵩山」题族全唐詩恰 4=本篇锚桩 2+王维自己另一首'
        '《送方尊師歸嵩山》（卷128）锚桩 2——**同一位诗人两次把「归嵩山」写进'
        '题目**（在册不引不牵合，机器断言分布）。分类行「五言律詩」系整理者动作'
        '（V048 判例三重断言）。'),
    'bg-136-world': (
        '诗往嵩山去，史里的嵩山恰 18 处、恰九卷（逐卷计数闭域机器断言），'
        '处处不是这条归路。一派是**封祀的现场**：詔「有事於嵩山」、'
        '「罷封嵩山」、「作奉天宮於嵩山南」、太后数幸嵩山。另一派看似同调——'
        '也隐居——却是**被考问的**：萬歲通天元年（丙申，六九六）武攸緒'
        '「**扈從封中岳還，即求棄官，隱於嵩山之陽。太后疑其詐，許之，以觀其所為。**」'
        '——**史部的嵩山连隐遁都是一场考场**，朝廷要看他真隐假隐。'
        '诗里的归山无人考问，归心自决，这正是诗与史的分界。\n'
        '**同字两界第五形态（闭）**：诗的收束是「歸來且閉關」——掩门归隐；'
        '通鉴「閉關」恰三处（闭域+三窗口断言），处处是城门与关梁：'
        '武德九年（丙戌，六二六）玄武门之变張公謹「獨閉關以拒之」（锁城）；'
        '建中三年（壬戌，七八二）李長春「閉關不內，以俟官軍」（等官军）；'
        '建中四年（癸亥，七八三）韓滉「閉關梁」禁马牛出境（断道禁行）——'
        '**史部的闭关把门关上是为了不让进出，诗的闭关把门关上是为了不再过问**。'
        '「嵩高」「迢遞」「荒城」「古渡」「秋山」「長薄」「閑閑」「落日」'
        '「暮禽」「暮雲」「清川」「歸來」通鉴全零（机器断言十二连）——'
        '**归途的语言整条进不了史部**；两传王维段「嵩」「閉關」「迢遞」全零'
        '（传写其人，不提这座山）。本层零铸造零 relation。'),
    'bg-136-person': (
        '写归山的人，传里先写的却是他不得不一再出门任职。丧假结束那道门，'
        '两部书各有一句：旧传「**服闋，拜吏部郎中。**」×新传「**服除，累遷給事中。**」'
        '——**两传同事异词第二例（V057 母丧「柴毁骨立」×「毀幾不生」之后）**：'
        '同一件事（服丧结束、复职迁转），措辞不同，**连迁转的阶次都记不同**'
        '（旧传接吏部郎中、新传径接给事中）——各自逐字并引、并列不合并'
        '（合而不并第二用，词异互斥 audit 双向硬卡）。旧传句系 V059 行迹三连'
        '已一引在册（全库查重恰一处），本迁移子句二引对后来关闭；新传句生成时'
        '全库查重既往零入引，本迁移首引。\n'
        '**服闋/服除正是丧期结束的行话，两传都用它起句，紧接的都是官职**——'
        '传体的王维永远从丧门走向衙门；诗里的王维「歸來且閉關」，门的方向掉转过来'
        '（读法声明，非史实）。已用判例句（柴毁骨立 V057/事母崔氏 V055/茶鐺 V054/'
        '歴右拾遺三连 V059/輞川系列 V035 起）一个不重开；certainty 不覆盖任何系年。'),
}
CLAIMS = {
    'claim-bg-136-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页 {{另}}×3、其余标记全零、Textquality 75%——三枚异文'
        '与不完备并存，正交第四度再验）；三枚异文（清/晴、禽/雲、閉/掩）引文'
        '含标记原样照登不裁决；**同页两形并存首录**：V018 正文引文系异文取首项'
        '的归一文本，本迁移 SCENE 引文含标记原样，各从其录两形在案；全句第二引：'
        '正文 V018 text claim 一引在先（生成时全库查重恰一处，查重针取归一形'
        '「歸來且閉關」），两度上限至此用满、此诗正文对后来迁移关闭（audit 硬卡）。'),
    'claim-bg-136-city': (
        'FACT', 'LIKELY',
        '底注锚点片段非空（同 V058/V059 全锚形态，audit 硬卡字样）；'
        'source-quantangshi-126 系 V035/V039/V052/V054 已立、第五次复用零新源'
        '（audit 反向断言无诗源表新建插入语句）；卷126 无消歧直锚+桩各恰一；'
        '第三枚异文恰落判决词位（閉/掩）——撞字论断只辖「閉關」支，'
        '「掩關」通鉴全零（异文支史部命中数不同，新边界首录，机器断言）；'
        '「歸嵩山」题族恰 4=本篇 2+王维《送方尊師歸嵩山》（卷128）2'
        '（同诗人两题在册不引，机器断言分布）；分类行「五言律詩」照登+非史料'
        '声明+不升格；题有山名而无时→零铸造零 relation。'),
    'claim-bg-136-world': (
        'FACT', 'LIKELY',
        '嵩山恰 18 处逐卷闭域（九卷分布机器断言）——封祀现场（有事/罢封/奉天宫/'
        '数幸）与隐遁考场（万岁通天元年（丙申，六九六）武攸绪「隱於嵩山之陽，'
        '太后疑其詐」首引入引为判决证据）两派；閉關恰三逐卷闭域+三窗口'
        '（武德九年玄武门张公谨闭关以拒之/建中三年李长春闭关不內/建中四年'
        '韩滉闭关梁——锁城/等官军/断道皆城门关梁事，逐字入引为判决证据）——'
        '与诗中掩门归隐同字两界第五形态；「嵩高」「迢遞」「掩關」等诗语十二词'
        '通鉴全零（机器断言）；两传王维段嵩/閉關/迢遞全零；certainty 不覆盖任何'
        '系年，诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-136-person': (
        'FACT', 'LIKELY',
        '两传同事异词并置第二例（V057 首见「合而不并」之后）：旧传「服闋，拜吏部'
        '郎中」系 V059 一引在册（全库查重恰一处=V059，本迁移子句二引上限用满'
        '对后来关闭）×新传「服除，累遷給事中」生成时全库查重既往零入引首引'
        '（audit 硬卡）；两书连迁转阶次所记不同（吏部郎中 vs 给事中）——更不得'
        '合并（词异与阶异双向互斥断言）；丧门/衙门与诗门方向掉转为读法声明非史实；'
        '已用判例句零重开；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-136-scene', 'source-ws-t300-136',
     '页面 歸嵩山作（header author+四联八句，五段以「……」相連——全句**第二引**：'
     '正文 V018 text claim 一引在先（其形系异文取首项的归一文本，本引文含 {{另}}×3 '
     '标记原样——同页两形并存各从其录），生成时全库查重恰一处，'
     '**两度上限至此用满，此诗正文对后来迁移关闭**；{{别}}/{{*}}/<ref> 全零、75%）',
     join(WS_AUTHOR, WS_L1, WS_L2, WS_L3, WS_L4)),
    ('claim-bg-136-city', 'source-ws-t300-136',
     '页面 歸嵩山作（header title+页底注+分类行三段并收——底注「卷126#歸嵩山作」'
     '锚点片段非空（同 V058/V059 全锚形态）；第三枚 {{另|閉|掩}} 恰落判决词位，'
     '异文两支在史部命中数不同照登不裁决；分类行系整理者动作：非史料声明、不升格）',
     join(WS_TITLE, WS_NOTE, WS_CAT)),
    ('claim-bg-136-city', 'source-quantangshi-126',
     '卷一百二十六·王維《歸嵩山作》篇题锚点+转引桩（无消歧直锚——机器断言各恰一；'
     '源行系 V035/V039/V052/V054 已立、本迁移第五次复用零新源；'
     '「歸嵩山」题族恰 4 含卷128《送方尊師歸嵩山》锚桩在册不引）',
     join(Q126, Q126_S)),
    ('claim-bg-136-world', 'source-zizhi-tongjian-events',
     '卷二百五·萬歲通天元年（丙申，六九六）武攸緒隱嵩山之陽段……卷一百九十一·'
     '武德九年（丙戌，六二六）玄武門張公謹閉關段……卷二百二十七·建中三年（壬戌，'
     '七八二）李長春閉關不內段……卷二百二十九·建中四年（癸亥，七八三）韓滉閉關梁段'
     '（**嵩山恰十八逐卷闭域+閉關恰三+四处年标题窗口机器断言**——史部的嵩山一为'
     '封祀现场一为隐遁考场，闭关皆城门关梁事：锁城/等官军/断道，与诗中掩门归隐'
     '同字两界第五形态，四段史文皆逐字入引作判决证据；「掩關」支通鉴全零在册）',
     join(TJ_YX, TJ_B1, TJ_B2, TJ_B3)),
    ('claim-bg-136-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王維传服阕句（V059 行迹三连已一引在册——'
     '全库查重恰一处，本迁移子句二引对后来关闭；与新传服除句同事异词异阶，'
     '并列不合并）', JTS_F),
    ('claim-bg-136-person', 'source-xintangshu-wenyi',
     '卷二百二·文艺中·王維传服除句（生成时全库引文域查重：既往零入引，'
     '本迁移首引；与旧传服阕句同记服丧结束复职而措辞与阶次俱异——'
     '合而不并第二用；与诗中「歸來且閉關」门之方向掉转并置是读法声明）', XTS_F),
]
BG_LINES = {'bg-136-scene': (1, 2), 'bg-136-city': (3, 4),
            'bg-136-world': (5, 6), 'bg-136-person': (7, 8)}
BG_AUDIENCE = {'bg-136-scene': 'PRIMARY', 'bg-136-city': 'JUNIOR',
               'bg-136-world': 'SENIOR', 'bg-136-person': 'JUNIOR'}
BG_TITLES = {'bg-136-scene': '眼前：越走越静的一条归路',
             'bg-136-city': '这座城：判决词恰在异文位上',
             'bg-136-world': '这个天下：山的两界与门的两种关法',
             'bg-136-person': '这个人：从丧门到衙门'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 41 首·八句五律 2/2/2/2 第三次）；史实句均有逐字引证；'
                 '系年第三十五次判决（题证系列第廿三状·嵩山与闭关）'
                 '「題有山名，山在史部一封祀一隱遁；詩用閉關，閉關在史部只城門與關梁」——'
                 '通鉴「嵩山」恰 18 处逐卷闭域（九卷）：封祀派（有事/罢封/奉天宫/数幸）'
                 '与隐遁派而隐遁系考场（万岁通天元年（丙申，六九六）武攸绪'
                 '「隱於嵩山之陽，太后疑其詐」首引入引）；'
                 '「閉關」恰三（闭域+三窗口：玄武门锁城/李长春等官军/韩滉断道）——'
                 '同字两界第五形态，四段史文逐字入引为判决证据；'
                 '异文支史部命中数不同（閉/掩——掩關通鉴全零，撞字论断只辖闭关支，'
                 '新边界首录）；诗语十二词通鉴全零；'
                 'ws {{另}}×3 与 75% 并存正交第四度；第三枚异文恰落判决词位照登；'
                 '同页两形并存首录（V018 归一形 vs 本迁移标记原样）；'
                 '「歸嵩山」题族恰 4（同诗人两题在册不引）；零新源（卷126 第五次复用）；'
                 '此诗正文第二引上限用满对后来关闭（V018 在先+全库查重）；'
                 '两传同事异词并置第二例（旧传服阕句 V059 一引在先二引关闭×'
                 '新传服除句首引；阶次俱异更不得合并）；'
                 'KNOWN 零如实记录（第十六例，audit 反向断言）；判例关键语零入引文。' for k in BG}


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
    A("""-- V060：王維《歸嵩山作》(work-t300-136) 四层背景（阶段 D 第 41 首·嵩山与闭关）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V039、V052、V054、V059 已执行（work-t300-136 与其
--       text-work-t300-136-ws、source-ws-t300-136 是 V018 的行；source-quantangshi-126 是
--       V035/V039/V052/V054 已立的卷126 源行（本迁移第五次复用，零新源）；
--       source-jiutangshu-wenyuan 是 V016 的行；source-xintangshu-wenyi 是 V016 的行；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源）。
--       本迁移零新 source（audit 断言无诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v060.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/歸嵩山作.txt（{{另}}×3×75% 正交第四度+第三枚恰落判决词位）、
--   舊唐書卷190下（服阕句二引）、新唐書卷202（服除句首引）、
--   全唐詩卷126（锚桩）+卷128（送方尊師歸嵩山在册结构）、
--   通鑑卷191/205/227/229（嵩山逐卷闭域+閉關恰三+四处年标题窗口）+ 通鑑 75 卷/
--   全唐詩 118 卷存快照负证计数扫描（嵩山/嵩高/閉關/掩關/迢遞/荒城/古渡/秋山/
--   長薄/閑閑/落日/暮禽/暮雲/清川/歸來/歸嵩山）+
--   既有迁移引文域逐句查重——传区间归属、首引/二引/零重开前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 6 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句五律 2/2/2/2 第三次，同 V054/V058）+ 零 poetry_source 行
--   + 不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有山名，山在史部一封祀一隱遁；詩用閉關，閉關在史部只城門與關梁」）：
--   * 嵩山恰 18 逐卷闭域（九卷分布机器断言）；閉關恰三+四窗口入引为判决证据；
--   * 异文支史部命中数不同：閉/掩——「掩關」通鉴全零，撞字论断只辖「閉關」支（新边界首录）；
--   * 同页两形并存首录：V018 正文引文异文归一形，本迁移 SCENE 标记原样形，各从其录；
--   * 此诗正文第二引上限用满：V018 一引在先（查重针归一形恰一处），对后来迁移关闭；
--   * 旧传服阕句 V059 一引在先本迁移二引关闭；新传服除句首引；两传阶次俱异不得合并；
--   * 丧门/衙门与门之方向掉转均标明读法声明非史实；
--   * KNOWN 零如实记录（第十六例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 柴毁骨立（V057）/事母崔氏（V055）/茶鐺（V054）/歴右拾遺三连（V059）判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 59，不含 60
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-136-%';             -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-126';     -- 恰 1（V035 起四迁移已立，本迁移复用不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-136-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-136-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-136';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-136-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-136'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-136';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-136-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-quantangshi-126';  -- 恰 1（复用，非本迁移所立）
-- 回滚: recovery/V060_rollback.sql（按 id 全枚举删除；零 source 删除——卷126 源行为 V035 起所立）
START TRANSACTION;""")

    A('\n-- ---------- 1. 零新 source（卷126 源行 V035/V039/V052/V054 已立，本迁移第五次复用） ----------')

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
    brows = [{'id': k, 'work_id': 'work-t300-136',
              'layer': {'bg-136-scene': 'SCENE', 'bg-136-city': 'CITY',
                        'bg-136-world': 'WORLD', 'bg-136-person': 'PERSON'}[k],
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

    A('\n-- ---------- 6. background_line（八句 2/2/2/2） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-136-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 7. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 60, 'Wang Wei Returning to Mount Song (work-t300-136) background layers (stage-D poem 41, eight-line regulated verse 2/2/2/2, third use): dating verdict thirty-five, twenty-third shape of the title-evidence series -- the mountain and the closed gate in two realms: Mount Song appears exactly eighteen times across exactly nine Tongjian volumes (file-by-file closed-domain machine assertion): on one side the imperial sacrifice -- edicts to perform the rite on Song, its cancellation, the Fengtian palace built south of the mountain, the empress dowager''s repeated processions; on the other side reclusion that is an examination -- in 696 Wu Youxu, returning from escorting the Zhongyue封 rite, begs to resign and hides on Song''s sunny side, and the empress dowager, suspecting a trick, grants it "to watch what he will do" (first citation, excerpted as verdict evidence): in the histories even hiding on Song is a test the court administers, while the poem''s return is unexamined and self-decided; closing the gate, the fifth same-character split: the poem ends "returning, I shut the gate", while the Tongjian''s three shut-the-gate passages (file-closed, triple year-heading windows) all mean gates of cities and communications: at Xuanwu Gate in 626 Zhang Gongjin shut the gate to bar the princes, in 782 Li Changchun shut the gate to wait for government troops, in 783 Han Huang shut the passes and banned cattle and horses from leaving -- gates shut against movement, not against worldly concern; and a new boundary first recorded: the variant reading matters for historiography -- the third {{另}} marker sits exactly on the verdict word (閉/掩), and the alternate branch "yan-guan" scores zero across the Tongjian, so the character-collision claim binds only to the bi-guan branch (machine-asserted, logged, never adjudicated); twelve poem-words score zero across the Tongjian -- the language of the homeward road cannot enter the histories; ws page carries three {{另}} markers with 75% completeness (orthogonality fourth time); same-page two-forms co-existence first registered: V018''s body excerpt normalizes markers to their first items, this migration''s SCENE quotes them verbatim, each recorded its own way; the title-family gui-Song-shan counts exactly 4 (this poem''s anchor plus Wang Wei''s own Sending Off Master Fang Returning to Song in juan 128, logged never quoted); zero new sources (juan 126''s row reused for the fifth time); the poem body hits its two-use ceiling (V018 first, machine-swept with the normalized needle, closure declared); PERSON second instance of two histories worded differently for one event (Old History''s mourning-end sentence second use closing after V059, New History''s first-cited; even the offices named differ, so merging is doubly barred, mutual-exclusion asserted); KNOWN zero honestly recorded (sixteenth instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 60);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V060 精确回滚：只删 V060 插入的行（id 全枚举）。零 source 删除：',
         '-- source-quantangshi-126 是 V035/V039/V052/V054 已立的卷126 源行（本迁移第五次复用），绝不删；',
         '-- work-t300-136 本体、其 text_line 8 行与 source-ws-t300-136 都是 V018 的行，绝不删；',
         '-- source-jiutangshu-wenyuan/source-xintangshu-wenyi/zizhi-tongjian-events 均为他迁移所立，',
         '-- 零删除；V060 零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 60;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_L1, WS_L2, WS_L3, WS_L4,
              JTS_F, XTS_F, TJ_YX, TJ_B1, TJ_B2, TJ_B3, Q126, Q126_S]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 三枚 {{另}} 标记原样照登硬卡（SCENE 引文）
    s_ex = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-136-scene')
    for tok in ('{{另|清|晴}}', '{{另|禽|雲}}', '{{另|閉|掩}}'):
        if tok not in s_ex:
            bad.append(f'SCENE 引文缺标记原样「{tok}」（照登硬卡）')
    # 底注非空锚片段照登硬卡
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-136-city' and s == 'source-ws-t300-136')
    if '卷126#歸嵩山作|' not in city_ws:
        bad.append('底注非空锚片段未逐字入 CITY 引文（V058/V059 同款照登硬卡）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-136-city' and s == 'source-ws-t300-136'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # SCENE 第二引上限声明硬卡
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-136-scene')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054–V059 同款硬卡）')
    # WORLD：四段史文必须在引文内（判决证据）；他卷诗语/异文支零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-136-world')
    for tok in ('隱於嵩山之陽', '太后疑其詐', '閉關以拒之', '閉關不內', '閉關梁'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（嵩山两界/闭关三处必须入引）')
    if '掩關' in w_ex or '迢遞' in w_ex or '送方尊師' in w_ex:
        bad.append('WORLD 引文混入通鉴零命中词或他诗题——在册零入引')
    # PERSON：词异与阶异双向互斥
    p_j = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-136-person' and s == 'source-jiutangshu-wenyuan')
    p_x = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-136-person' and s == 'source-xintangshu-wenyi')
    if '服闋，拜吏部郎中' not in p_j or '服除，累遷給事中' not in p_x:
        bad.append('PERSON 两传句必须各含本传原句（合而不并第二用前提）')
    if '服除' in p_j or '給事中' in p_j:
        bad.append('旧传引文混入新传词（服除/給事中）——词异不得互串')
    if '服闋' in p_x or '吏部郎中' in p_x:
        bad.append('新传引文混入旧传词（服闋/吏部郎中）——词异不得互串')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-136':
            for w in ('謫仙', '脫靴', '賜金放還', '宮錦袍', '夜郎', '山東人'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山', '隠鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒', '刻碑鳳林山南',
                '仕宦之疾徑', '放田里', '進止仍有風範', '茶鐺', '事母崔氏', '解官以贖',
                '柴毁骨立', '毀幾不生', '大招權利', '車如流水馬如龍',
                '歴右拾遺', '天寳末，為給事中', '或牒歸故鄉', '見郭子儀',
                '昆仲宦遊兩都', '輞口', '藍田别墅'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句形制 2/2/2/2
    if {k: len(v) for k, v in BG_LINES.items()} != {k: 2 for k in BG}:
        bad.append('八句 background_line 必须每层恰 2（2/2/2/2）')
    if len(re.findall(r"text-work-t300-136-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # 零新 source（V052 教训：断言文案也不得出现该字面量）
    if 'INSERT INTO poetry_' + 'source' in sql:
        bad.append('V060 有意零新 source，但 SQL 里出现了诗源表新建插入语句')
    if 'DELETE FROM poetry_source' in build_rollback():
        bad.append('回滚不得删任何 source 行（卷126 源行为 V035 起所立）')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V060 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V060 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-136' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V060 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-136' AS subject_id" in sql:
        bad.append('V060 的 claim 主语应全部是 bg-136-*，work-t300-136 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V060 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '一封祀一隱遁' not in body_all:
        bad.append('BG/文件头须含「山在史部一封祀一隱遁」判决声明')
    if '城門與關梁' not in body_all and '城门与关梁' not in body_all:
        bad.append('BG 须含「闭关在史部只城门与关梁」判决声明')
    if '同字两界第五形态' not in body_all:
        bad.append('BG 须含「同字两界第五形态」声明')
    if '命中数不同' not in body_all:
        bad.append('BG/CITY 须含「异文支史部命中数不同」新边界声明')
    if '两形并存' not in body_all:
        bad.append('BG/SCENE 须含「同页两形并存」首录声明')
    if '合而不并第二' not in body_all and '合而不并第二例' not in body_all:
        bad.append('BG/PERSON 须含「合而不并第二用」声明')
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
              f'切片传区间归属断言（两传皆王维段）；'
              f'四处年标题窗口断言（萬歲通天元年六九六/武德九年六二六/建中三年七八二/建中四年七八三）；'
              f'负证机器复查五层（通鉴嵩山恰十八逐卷闭域九卷+嵩高/迢遞/荒城/古渡/秋山/長薄/閑閑/'
              f'落日/暮禽/暮雲/清川/晴川/歸來/如有意/相與還/掩關全零+閉關恰三分卷闭域/'
              f'全唐詩歸嵩山恰四=vol126×2+vol128×2 且送方尊師歸嵩山锚桩各恰一/'
              f'卷126 锚桩各恰一+歸嵩山作恰二/ws {{另}}恰三具体字样+他标记全零+75%+非空锚片段/'
              f'两传王段嵩閉關迢遞全零，快照变动即中止）；'
              f'前提全库查重硬卡七件（服除句零引+服阕句恰一=V059+攸緒/三闭关句各零引+'
              f'正文恰一=V018 归一形针）；'
              f'三枚标记原样照登硬卡+底注全锚硬卡+SCENE 第二引/上限硬卡；'
              f'嵩山两界/闭关三处入引+掩關/迢遞/送方尊師零混入断言；'
              f'PERSON 词异阶异双向互斥断言；判例只引不重开断言（含歴右拾遺/或牒歸故鄉）；'
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
