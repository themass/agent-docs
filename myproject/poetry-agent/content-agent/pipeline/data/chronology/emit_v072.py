#!/usr/bin/env python3
"""阶段 D 第 53 首：生成 V072——李商隱《蟬》(work-t300-011, V018 已立) 四层背景。

**本迁移零新建 source——连续第四首**（V069/V070/V071 之后；
source-ws-t300-011 与 source-quantangshi-539 皆 V018 所立，539 第七次复用）。

绑定形态：V071《錦瑟》首见的**互指循环指针本篇第二次在场**——ws notes 带
「↑ [[全唐詩/卷539#蟬|…]]」向上回指，539 本篇正文恰是「{{:蟬 (李商隱)}}」向下转引；
且本篇壳锚是 300 系壳侧**首个带作者消歧器**的锚「==[[蟬 (李商隱)|蟬]]==」——
**壳侧消歧首见**（V059 作者消歧/V061 首句消歧/V062,V063 裸名/V067 反例/V069–V071 裸名壳
——消歧谱至此从裸名侧补到壳侧）。

「为什么写」走到**清直两界**（同字两界第十七形态·清直形态首见）：
**通鉴 75 卷连一个「蟬」字都没有（机器断言）——咏物诗的物名史部全库不识；
可通鉴有清直，且恰二：一条是政敌递出去的梯子（逢吉荐李绅清直宜居风宪——挤走），
一条是为弃主喊冤贬回去的代价（丁柔立以清直荐、德裕不能用、后讼德裕冤、坐阿附贬南阳尉）
——史部的清直两头都在人事的账上；诗的「我亦舉家清」是一家人在薄宦里清着，蝉是证人**——
「舉家」恰七入侧档：拒位西归（李建）/义不臣贼举家自尽（郑綦郑系）——
**史部的举家要么拒位要么赴死，诗的举家清是活着清**。

ws 页形制（SCENE/CITY 层）：**零标记页×100% 满级**（{{另}}/{{別}}/{{*}}/<ref>/{{reflist}}
全零——V069 满级无标记同形第二例，与 V071 双{{另}}×100% 对照成谱）；
**Vtext/poem 双转录句读分工首见**（Vtext 行全裸无句读、poem 块全带句读——
夜雨寄北是两侧皆裸、寄令狐郎中 poem 无句读，本篇 Vtext 裸+poem 句读=分工形态）；
**跨迁移异体分工**：V018 文本行存「五更疎欲斷/薄宦梗猶汎」（ws-fold 折叠面），
本快照 ws 页存「五更疏欲斷/薄宦梗猶泛」——两侧逐行对读、折叠判一致（生成时双向断言）；
notes 三连一行（与錦瑟/韓碑同形——全库恰三页机器断言）；**分类四行含作者分类+
「詠蟬詩」类目首见**（对照 V071 錦瑟两行无作者分类——分类行数本身也是形态）。

8 句七律 shape：**2/2/2/2 顺次**（scene→1,2 city→3,4 world→5,6 person→7,8）。

用法: python3 -I emit_v072.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402

WS = pathlib.Path('/tmp/src-dl/ws-poems/蟬__李商隱_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
V539 = pathlib.Path('/tmp/src-dl/quantangshi/vol539.txt').read_text(encoding='utf-8')
V018 = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/V018__tang300_ws_verified.sql').read_text(encoding='utf-8')
TJ224 = pathlib.Path('/tmp/src-dl/tongjian/tj-224.txt').read_text(encoding='utf-8')
TJ243 = pathlib.Path('/tmp/src-dl/tongjian/tj-243.txt').read_text(encoding='utf-8')
TJ248 = pathlib.Path('/tmp/src-dl/tongjian/tj-248.txt').read_text(encoding='utf-8')
TJ254 = pathlib.Path('/tmp/src-dl/tongjian/tj-254.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 蟬', '| title    = 蟬',
                         'ws header title(裸名题面——蟬字通鉴全库零)')
WS_AUTHOR = slice_between(WS, '| author   = 李商隱', '| author   = 李商隱', 'ws header author(署名直证)')
WS_VT1 = slice_between(WS, '{{VtextStart}}本以高難飽{{VtextEnd}}', '{{VtextStart}}本以高難飽{{VtextEnd}}',
                       'ws Vtext 行裸面无句读(poem 面全句读——双转录句读分工首见)')
WS_POEM = slice_between(WS, '本以高難飽，徒勞恨費聲。', '我亦舉家清。\n</poem>',
                        'ws poem 块存原样疏/泛面(正文第二引——与 V018 疎/汎面异体分工)')
WS_NOTE3 = slice_between(
    WS,
    '| notes    = {{唐詩三百首}}{{Textquality|100%}}↑ [[全唐詩/卷539#蟬|全唐詩·卷五百三十九]]',
    '| notes    = {{唐詩三百首}}{{Textquality|100%}}↑ [[全唐詩/卷539#蟬|全唐詩·卷五百三十九]]',
    'ws notes 三连一行(与錦瑟/韓碑同形全库恰三页——↑回指互指之诗页侧)')
WS_CAT4 = slice_between(WS, '[[Category:李商隱]]', '[[Category:詠蟬詩]]',
                        'ws 分类四行连片(含作者分类——对照 V071 锦瑟两行无；詠蟬詩类目首见)')
V539_SHELL = slice_between(V539, '==[[蟬 (李商隱)|蟬]]==\n{{:蟬 (李商隱)}}',
                           '==[[蟬 (李商隱)|蟬]]==\n{{:蟬 (李商隱)}}',
                           '卷539 消歧壳(壳侧作者消歧器首见——显示名仍裸蟬)')
TJ_QZ1 = slice_between(TJ243, '會御史中丞缺，逢吉薦紳清直', '不疑而可之。',
                       '通鉴长庆三年李逢吉荐李绅清直(清直作政敌梯子;窗口断言)')
TJ_QZ2 = slice_between(TJ248, '初，李德裕執政，有薦丁柔立清直', '坐阿附貶南陽尉。',
                       '通鉴大中二年丁柔立讼德裕冤坐阿附(清直者贬回去;窗口断言)')
TJ_JJ1 = slice_between(TJ254, '將作監鄭綦、庫部郎中鄭系義不臣賊，舉家自殺。',
                       '將作監鄭綦、庫部郎中鄭系義不臣賊，舉家自殺。',
                       '通鉴广明元年郑綦郑系举家自尽(史部举家赴义;窗口断言)')
TJ_JJ2 = slice_between(TJ224, '建誓死不從，舉家西歸。', '建誓死不從，舉家西歸。',
                       '通鉴大历八年李建辞留举家西归(史部举家拒位;窗口断言)')
JTS_W = slice_between(JTS, '文思清丽', '庭筠过之。',
                      '旧传李商隐段(文思清丽庭筠过之——传的清在笔底;PERSON 首引)')

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

_window(TJ243, TJ_QZ1, '長慶三年')
_window(TJ248, TJ_QZ2, '大中二年')
_window(TJ254, TJ_JJ1, '廣明元年')
_window(TJ224, TJ_JJ2, '大曆八年')

# ---------- 负证机器复查 ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：蟬字全库不识+诗面语全零；清直恰二、舉家恰七、异体汎全零；侧档计数
for _w in ('蟬', '蝉', '鳴蟬', '蜩', '高難飽', '費聲', '疏欲', '碧無情', '梗猶',
           '故園蕪已平', '煩君', '舉家清', '薄宦'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——咏物诗的物名史部不识的判决失效，须重读')
if _alltj.count('汎') != 0:
    raise SystemExit('通鉴「汎」不再全零——异体侧档须重估')
if _alltj.count('清直') != 2 or _tjf['tj-243.txt'].count('清直') != 1 or _tjf['tj-248.txt'].count('清直') != 1:
    raise SystemExit('通鉴「清直」不再恰二（243/248 各一）——清直两界判决须重估')
_jj = {n: t.count('舉家') for n, t in _tjf.items() if '舉家' in t}
if sum(_jj.values()) != 7:
    raise SystemExit(f'通鉴「舉家」不再恰七（实 {sum(_jj.values())}）——举家侧档须重估')
for _w, _n in (('家無', 9), ('飽', 18), ('梗', 4), ('清', 297), ('高', 896)):
    if _alltj.count(_w) != _n:
        raise SystemExit(f'通鉴「{_w}」不再恰{_n}——题字侧闭域档扫须重估')
# ② 全唐诗：壳锚/转引全库唯一；八句全库零；539 侧档
if _allq.count('==[[蟬 (李商隱)|蟬]]==') != 1 or _allq.count('{{:蟬 (李商隱)}}') != 1:
    raise SystemExit('《全唐詩》蟬壳锚/转引不再全库唯一——壳侧消歧首见判决失效')
if V539.count(V539_SHELL) != 1:
    raise SystemExit('卷539 消歧壳结构变了（互指之卷页侧断言失效）')
for _ln in ('本以高難飽', '徒勞恨費聲', '五更疏欲斷', '一樹碧無情', '薄宦梗猶泛',
            '故園蕪已平', '煩君最相警', '我亦舉家清'):
    if _allq.count(_ln) != 0:
        raise SystemExit(f'全唐詩语料「{_ln}」不再全零——诗八行只活在诗页的判决失效')
if V539.count('蟬') != 8:
    raise SystemExit('卷539「蟬」不再恰八（壳二+他诗六）——壳侧闭域档扫须重估')
# ③ ws：零标记×满级；双转录句读分工；notes 三连恰三页；分类四行含作者+詠蟬詩恰二页；疏/泛面
for _w in ('{{另', '{{別', '{{*', '<ref>', '{{reflist}}', '{{Textquality|75%}}'):
    if WS.count(_w) != 0:
        raise SystemExit(f'ws 页「{_w}」不再全零（零标记×满级断言失效）')
if WS.count('{{Textquality|100%}}') != 1:
    raise SystemExit('ws 页 100% 满级计数变了')
if WS.count('疏') != 2 or WS.count('泛') != 2 or WS.count('疎') != 0 or WS.count('汎') != 0:
    raise SystemExit('ws 页 疏/泛 面结构变了（与 V018 疎/汎 面的异体分工断言失效）')
if WS.count('本以高難飽') != 2 or WS.count('我亦舉家清') != 2:
    raise SystemExit('ws 页 Vtext/poem 双转录结构变了（首末句页内应各恰 2）')
if '本以高難飽，' not in WS:
    raise SystemExit('ws poem 块句读面缺失（双转录句读分工首见断言失效）')
if WS.count('{{VtextStart}}') != 8 or WS.count('{{VH1|蟬}}') != 1 or WS.count('{{clr}}') != 1:
    raise SystemExit('ws Vtext/VH1/clr 排版结构变了')
_wsf = {p.name: p.read_text(encoding='utf-8')
        for p in sorted(pathlib.Path('/tmp/src-dl/ws-poems').glob('*.txt'))}
_tri = {n for n, t in _wsf.items() if '{{唐詩三百首}}{{Textquality|100%}}↑ [[全唐詩/卷539#' in t}
if _tri != {'蟬__李商隱_.txt', '錦瑟.txt', '韓碑.txt'}:
    raise SystemExit(f'539-notes 三连页不再恰三（实 {sorted(_tri)}）——三连同形档扫须重估')
_cat = {n for n, t in _wsf.items() if '[[Category:詠蟬詩]]' in t}
if _cat != {'蟬__李商隱_.txt', '在獄詠蟬.txt'}:
    raise SystemExit(f'「詠蟬詩」类目页不再恰二（实 {sorted(_cat)}）——类目档扫须重估')
if WS.count('[[Category:李商隱]]') != 1:
    raise SystemExit('ws 分类含作者分类形态变了（对照 V071 锦瑟无——分类行数即形态）')
if WS.count('| times') != 0 or WS.count('| type') != 0 or WS.count('| from') != 0:
    raise SystemExit('ws 无 times/type/from 字段形态变了（无空格排版对照组断言失效）')
# ④ 旧传李商隐段负证（段内蟬与诗面题字零——清字恰一恰在「文思清丽」）
for _w in ('蟬', '飽', '費', '斷', '碧', '蕪', '煩', '警', '薄宦', '故園', '舉家'):
    if _seg_j.count(_w) != 0:
        raise SystemExit(f'「{_w}」落在旧传李商隐段——传段题字零判决失效，须重读原文')
if _seg_j.count('清') != 1 or _seg_j.count('文思清丽') != 1:
    raise SystemExit('旧传段「清」不再恰一恰在文思清丽——传的清在笔底判决须重估')
# ⑤ 跨迁移异体分工双向断言（V018 存疎/汎面，本快照 ws 页存疏/泛面）
if "'五更疎欲斷，'" not in V018 or "'薄宦梗猶汎，'" not in V018:
    raise SystemExit('V018 文本行不再存 疎/汎 面（异体分工断言失效——读法甲折叠判须重估）')

POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V072')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

def _domain_src(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V072')
                   and needle in f.read_text(encoding='utf-8')})

for _premise, _needle, _want in (
        ('本诗首句(V018 句读式一引)', '本以高難飽', ['V018']),
        ('本诗末句(V018 句读式收尾)', '我亦舉家清', ['V018']),
        ('V018 句读式全引不重开', '本以高難飽，……我亦舉家清。', ['V018']),
        ('V018 异体行在册(疎/汎面)', '五更疎欲斷', ['V018']),
        ('故园字面 V018 在册(春晓先占)', '故園', ['V018']),
        ('ws 诗页源在先', 'source-ws-t300-011', ['V018']),
        ('卷页源六次在册(本迁移第七次复用)', 'source-quantangshi-539',
         ['V018', 'V067', 'V068', 'V069', 'V070', 'V071']),
        ('V069 底本回指链接在册', '↑ [[全唐詩/卷539#寄令狐郎中', ['V069']),
        ('V071 互指锦瑟在册', '{{:錦瑟}}', ['V071']),
        ('V016 在册诸句', '商隐随亚在岭表累载', ['V016'])):
    _prev = _domain_src(_needle) if (_needle.startswith('source-') or _needle == '五更疎欲斷') else _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
for _first, _needle in (('消歧壳锚', '==[[蟬 (李商隱)|蟬]]=='),
                        ('消歧转引', '{{:蟬 (李商隱)}}'),
                        ('本页↑回指', '↑ [[全唐詩/卷539#蟬'),
                        ('逢吉荐绅', '會御史中丞缺，逢吉薦紳清直'),
                        ('丁柔立案', '初，李德裕執政，有薦丁柔立清直'),
                        ('坐阿附贬', '坐阿附貶南陽尉。'),
                        ('郑綦举家', '義不臣賊，舉家自殺。'),
                        ('李建西归', '舉家西歸。'),
                        ('旧传清丽', '文思清丽'),
                        ('庭筠过之', '庭筠过之。'),
                        ('Vtext裸行', '{{VtextStart}}本以高難飽{{VtextEnd}}'),
                        ('詠蟬类目', '[[Category:詠蟬詩]]'),
                        ('诗原样块', '本以高難飽，徒勞恨費聲。')):
    if _domain(_needle):
        raise SystemExit(f'首引前提破了：「{_needle}」（{_first}）既往有引（{_domain(_needle)}）——须重设计')

BG = {
    'bg-011-scene': (
        '八句是一封写给蝉的回信（2/2/2/2 起两句入眼前层）：你因栖高所以难饱，'
        '白白空费鸣声（「本以高難飽，徒勞恨費聲。」——本诗对蝉说话，第二人称从第一句'
        '就开始）；五更鸣声疏得快要断，一树碧绿毫无情味（「五更疏欲斷，一樹碧無情。」）；'
        '薄宦如梗飘泛，故园荒秽已平（「薄宦梗猶泛，故園蕪已平。」）；劳你最能警我——'
        '我也举家清廉（「煩君最相警，我亦舉家清。」）。**咏物诗的对像开口了：**'
        '全诗八句句句是对蝉说——史部没有任何东西对李商隐开过口。'
        'ws 诗页：**零标记页×100% 满级**（{{另}}/{{別}}/{{*}}/<ref>/{{reflist}} 全零，'
        '机器断言——V069 寄令狐郎中满级无标记同形第二例，与 V071 錦瑟双{{另}}×100% 对照：'
        '评级度量转录完备，与异文多寡正交）；**双转录句读分工首见**：Vtext 行全裸无句读、'
        'poem 块全带句读（夜雨寄北两侧皆裸、寄令狐郎中 poem 无句读——本篇一裸一读=分工形态，'
        '照登不判）；**跨迁移异体分工**：V018 文本行存「五更疎欲斷／薄宦梗猶汎」'
        '（ws-fold 归一面），本快照 ws 页存「五更疏欲斷／薄宦梗猶泛」——同一页两次快照'
        '异体不同，逐行对读折叠判读法甲一致（生成时双向断言），异体只登记不裁决；'
        '分类四行**含作者分类**+「詠蟬詩」类目首见（对照 V071 錦瑟页两行无作者分类——'
        '分类行数本身也是形态；类目系整理者归类非史料声明不升格，V048 判例）。'
        '**此诗正文系第二引（上限用满第二十例）**：V018 已引句读式'
        '（「本以高難飽，……我亦舉家清。」——疎/汎面），本迁移二引 poem 块存原样'
        '（疏/泛面，各从其录；V018 句读式引文零重开，生成时硬断言）；此后此诗正文关闭。'),
    'bg-011-city': (
        '卷539 侧把 V071 立的形态坐实成系列：**互指循环指针第二次在场**——ws notes 带'
        '「↑ [[全唐詩/卷539#蟬|全唐詩·卷五百三十九]]」向上回指，卷539 本篇正文恰是'
        '转引壳向下引回诗页（机器断言：notes 三连一行页全库恰三——蟬/錦瑟/韓碑，'
        '本页与韓碑同形；壳外全卷无本篇一行——八句全唐诗语料全零）。'
        '本篇新增一层：**壳侧作者消歧器首见**——锚是「==[[蟬 (李商隱)|蟬]]==」，'
        '转引是「{{:蟬 (李商隱)}}」：**消歧器第一次出现在壳侧**（V059 作者消歧在卷页锚、'
        'V061 首句消歧在卷页锚、V062/V063 裸名、V067 同名裸锚反例、V069–V071 壳侧皆裸名——'
        '本篇壳侧带消歧器，显示名仍裸「蟬」；机器断言锚与转引全唐诗各恰一）。'
        '**消歧理由在册可查**：ws 库蟬名页恰三（在獄詠蟬/塞下曲「蟬鳴空桑林」/本篇），'
        '《全唐诗》蟬字八十三处（539 卷内八处=壳二+他诗六：韓翃「蟬是怨齊王」/李商隱'
        '《桂林路中作》「空餘蟬嘒嘒」/自《柳》「已帶斜陽又帶蟬」等——闭域档扫）：'
        '同名风险真实存在，壳侧才挂了消歧器。**零新建 source 连续第四首**：'
        'source-ws-t300-011 与 source-quantangshi-539 皆 V018 所立，539 第七次复用——'
        '壳本身就是证据，带消歧器的壳是更重的证据。（本层零 relation。）'),
    'bg-011-world': (
        '**通鉴七十五卷连一个「蟬」字都没有；可它有清直，且清直两头都在人事的账上**'
        '（同字两界第十七形态·清直形态首见）：通鉴「**蟬/蝉/鳴蟬/蜩/高難飽/費聲/疏欲/'
        '碧無情/梗猶/故園蕪已平/煩君/舉家清/薄宦**」全零（机器断言）——咏物诗的物名'
        '史部全库不识，题字「蟬」连字面都不进。可通鉴不是没有清与举家：'
        '① 「**清直**」恰二：長慶三年（癸卯，八二三）李逢吉患李紳排抑自己，'
        '「**會御史中丞缺，逢吉薦紳清直，宜居風憲之地。上以中丞亦次對官，不疑而可之**」'
        '——荐完就把他与韩愈挤去外任；又大中二年（戊辰，八四八）「**初，李德裕執政，'
        '有薦丁柔立清直可任諫官者，德裕不能用……德裕貶潮州，柔立上疏訟其冤。'
        '丙寅，坐阿附貶南陽尉**」——当年以清直被荐、后来为贬官的前宰相喊冤，'
        '贬回去当尉。「**史部的清直两头都在人事的账上：一头是政敌递出去的梯子，'
        '一头是还不清的代价**；诗的「我亦舉家清」不在任何账上——'
        '一家人在薄宦里清着，蝉是证人；'
        '② 「**舉家**」恰七（闭域档扫），最近诗面的两条：廣明元年（庚子，八八〇）'
        '黄巢入京「**將作監鄭綦、庫部郎中鄭系義不臣賊，舉家自殺**」；大曆八年'
        '（癸丑，七七三）李忠臣子建拒被拥立「**建誓死不從，舉家西歸**」——'
        '**史部的举家要么拒位要么赴死；诗的举家清是活着清**（「薄宦梗猶泛」——'
        '漂着的清）。题字侧「清」恰二百九十七/「高」恰八百九十六/「飽」恰十八'
        '在册零入引（闭域档扫）；异体「汎」通鉴全零（V018 面的异体在史部无位置）。'
        '本层零铸造零 relation。'),
    'bg-011-person': (
        '旧传李商隐段（**简化字录入**，V016 locator 同款标注，引文照登简体原样）'
        '首引一段（零域）：「**文思清丽，庭筠过之。**」\n'
        '传里唯一一个「清」字（机器断言：段内「清」恰一）恰在**笔底**——文思清丽，'
        '而且还不全是他的：温庭筠超过他。**史部给这个人的清在文章里；诗自己把清认领'
        '到门第上**：「我亦舉家清」——一家人的清，不是文思的清（对照判决，非史实因果）。'
        '紧接着史臣自断：「而俱无持操，恃才诡激，为当涂者所薄。名宦不进，坎壈终身。」'
        '（V066/V067/V068 在册零重开，域断言）——**传说他无持操，诗说举家清；'
        '同一个人的清，两部书各执一词**（读法声明：诗不自证操守，史不裁诗）。\n'
        '**段内题字零**：蟬/飽/費/斷/碧/蕪/煩/警/薄宦/故園/舉家全零（机器断言）——'
        '**写蝉的人，传里无一蝉字**（V071「写尽锦瑟的人传里无一瑟字」同款，蝉是题面'
        '通名比瑟更冷）；「举家清」的举家在传里只剩官历（V016 在册句零重开）。'
        '本诗 ws 页 notes 有回指注（与 V071 同形）；certainty 不覆盖任何系年，'
        '诗 time.span/event.name/written_during 仍零铸造（audit 硬卡）。'),
}
CLAIMS = {
    'claim-bg-011-scene': (
        'FACT', 'LIKELY',
        '八句七律本文**第二引上限用满第二十例**：V018 句读式一引在先'
        '（「本以高難飽，……我亦舉家清。」——疎/汎面），本迁移二引 ws 页 poem 块'
        '**存原样**（疏/泛面，各从其录；生成时断言 V018 句读式引文不重开），此后正文'
        '对后来迁移关闭；**跨迁移异体分工首见**：V018 文本行存疎/汎（ws-fold 归一面）、'
        '本快照页存疏/泛——同一页两次快照异体不同，逐行对读折叠判一致（双向断言），'
        '异体只登记不裁决；**零标记页×100% 满级**（{{另}}/{{別}}/{{*}}/<ref>/{{reflist}}'
        '全零机器断言——V069 同形第二例，与 V071 双{{另}}×100% 对照成谱）；'
        '**双转录句读分工首见**（Vtext 全裸/poem 全句读）；分类四行含作者分类+「詠蟬詩」'
        '类目首见照登（V048 不升格）；八句对蝉说话的第二人称形态照登；系年零铸造。'),
    'claim-bg-011-city': (
        'FACT', 'LIKELY',
        '**互指循环指针第二次在场**（V071 首见本篇坐实成系列）：ws notes「↑ 卷539#蟬」'
        '向上回指+539 本篇「{{:蟬 (李商隱)}}」向下转引（机器断言：notes 三连页全库恰三'
        '蟬/錦瑟/韓碑；八句全唐诗语料全零——诗只活在诗页）；**壳侧作者消歧器首见**：'
        '锚「==[[蟬 (李商隱)|蟬]]==」+转引「{{:蟬 (李商隱)}}」全唐诗各恰一——消歧器'
        '第一次挂上壳侧且显示名仍裸（V059/V061 卷页锚侧消歧/V062,V063 裸名/V067 同名'
        '裸锚反例/V069–V071 壳侧裸名——消歧谱补全壳侧一层）；消歧理由在册可查：ws 蟬名页'
        '恰三+全唐诗蟬字 83（539 内八=壳二+他诗六闭域）；**零新建 source 连续第四首**'
        '（两源皆 V018 所立，539 第七次复用）。'),
    'claim-bg-011-world': (
        'FACT', 'LIKELY',
        '通鉴「蟬/蝉/鳴蟬/蜩/高難飽/費聲/疏欲/碧無情/梗猶/故園蕪已平/煩君/舉家清/薄宦」'
        '全零（机器断言——咏物诗的物名史部全库不识）而清与举家在他字：「清直」恰二分'
        '長慶三年癸卯八二三（逢吉荐李绅清直宜居风宪——政敌的梯子）与大中二年戊辰八四八'
        '（丁柔立以清直荐、德裕不能用、讼德裕冤、坐阿附贬南阳尉——还不清的代价）——'
        '**史部的清直两头都在人事的账上；诗的我亦舉家清不在任何账上**；「舉家」恰七闭域'
        '（廣明元年庚子八八〇鄭綦鄭系義不臣賊舉家自殺=赴死+大曆八年癸丑七七三李建举家'
        '西归=拒位——**史部的举家要么拒位要么赴死，诗的举家清是活着清**）（同字两界'
        '第十七形态·清直形态首见，audit 硬卡）；清297/高896/飽18/汎0 在册闭域零入引；'
        'certainty 不覆盖任何系年，time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-011-person': (
        'FACT', 'LIKELY',
        '旧传李商隐段（简化字录入照登原样）首引一段零域=「文思清丽，庭筠过之。」'
        '（传区间归属机器断言）；**段内「清」恰一恰在笔底**（机器断言）——史部给他的清'
        '在文章里（且庭筠过之），诗自己把清认领到门第上「我亦舉家清」（对照判决非因果）；'
        '「传说他无持操/诗说举家清——同一个人的清两部书各执一词」系读法声明；'
        '**段内题字十一项全零**（蟬/飽/費/斷/碧/蕪/煩/警/薄宦/故園/舉家——机器断言）'
        '**写蝉的人传里无一蝉字**（V071 无一瑟字同款）；V016/V066–V068/V070/V071 在册句'
        '零重开（域断言）；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-011-scene', 'source-ws-t300-011',
     '页面 蟬（《唐詩三百首》第 11 首选本页，页题裸名；title+author+Vtext 首行裸面+poem 块'
     '以「……」相连——**双转录句读分工首见**：Vtext 行全裸无句读、poem 块全带句读；poem 块'
     '存原样：八句疏/泛面（V018 文本行系疎/汎归一面——跨迁移异体分工，各从其录，'
     '逐行对读折叠判一致生成时双向断言）；零标记×100% 满级（{{另}}/{{別}}/{{*}}/<ref>/'
     '{{reflist}} 全零机器断言）；正文第二引上限用满第二十例（V018 句读式一引在先，'
     '本迁移引原样面，生成时断言 V018 句读式引文不重开）',
     join(WS_TITLE, WS_AUTHOR, WS_VT1, WS_POEM)),
    ('claim-bg-011-city', 'source-quantangshi-539',
     '卷五百三十九·李商隱《蟬》**消歧壳转引块**（「==[[蟬 (李商隱)|蟬]]==」+「{{:蟬 (李商隱)}}」'
     '——**壳侧作者消歧器首见**：消歧器第一次挂上壳侧且显示名仍裸「蟬」（V059/V061 锚侧/'
     'V062,V063 裸名/V067 反例/V069–V071 壳侧裸名——消歧谱补全壳侧一层；机器断言锚与转引'
     '全唐诗各恰一）；壳外全卷无本篇一行（八句全唐诗语料全零；卷内蟬八处=壳二+他诗六闭域）；'
     '**与本页 notes ↑回指互指**（V071 首见本篇第二次在场——循环指针成系列）；'
     '源行系 V018 已立、本迁移第七次复用零新建）',
     V539_SHELL),
    ('claim-bg-011-city', 'source-ws-t300-011',
     '页面 蟬（notes 三连一行整值入引（{{唐詩三百首}}+{{Textquality|100%}}+↑底本回指同挤一值——'
     '与錦瑟/韓碑同形全库恰三页机器断言；↑ 指向恰是转引本篇的 539 消歧壳——互指之诗页侧）'
     '+分类四行连片（**含作者分类 [[Category:李商隱]]**——对照 V071 錦瑟页两行无作者分类，'
     '分类行数本身也是形态；「詠蟬詩」类目首见照登——全库恰二页：本篇+在獄詠蟬机器断言；'
     '分类行系整理者分类动作：非史料声明、不升格，V048 判例）；本迁移零新建源连续第四首）',
     join(WS_NOTE3, WS_CAT4)),
    ('claim-bg-011-world', 'source-zizhi-tongjian-events',
     '卷二百四十三·長慶三年（癸卯，八二三）逢吉荐李绅清直段（「宜居風憲之地…不疑而可之」'
     '——清直作政敌的梯子）……卷二百四十八·大中二年（戊辰，八四八）丁柔立案（荐以清直/德裕'
     '不能用/讼德裕冤/坐阿附貶南陽尉——清直者贬回去）……卷二百五十四·廣明元年（庚子，八八〇）'
     '鄭綦鄭系「義不臣賊，舉家自殺」段（举家赴义）……卷二百二十四·大曆八年（癸丑，七七三）'
     '李建「舉家西歸」段（举家拒位）；通鉴蟬/蝉/鳴蟬/蜩及诗面语全零（咏物诗物名不识），'
     '清直恰二/舉家恰七（四段逐字入引为判决证据）',
     join(TJ_QZ1, TJ_QZ2, TJ_JJ1, TJ_JJ2)),
    ('claim-bg-011-person', 'source-jiutangshu-wenyuan',
     '舊唐書卷一九〇下·李商隱（**简化字录入**照登原样，V016 locator 同款标注）'
     '（「文思清丽，庭筠过之」段（段内「清」字恰一恰在笔底——传的清在文章里；全库查重'
     '恰零域首引；传区间归属机器断言；段内题字蟬/飽/費/斷/碧/蕪/煩/警/薄宦/故園/舉家'
     '全零——写蝉的人传里无一蝉字；「无持操对举家清各执一词」系读法声明；'
     'V016/V066–V068/V070/V071 在册句零重开）',
     JTS_W),
]
BG_LINES = {'bg-011-scene': (1, 2), 'bg-011-city': (3, 4),
            'bg-011-world': (5, 6), 'bg-011-person': (7, 8)}
BG_AUDIENCE = {'bg-011-scene': 'PRIMARY', 'bg-011-city': 'JUNIOR',
               'bg-011-world': 'SENIOR', 'bg-011-person': 'JUNIOR'}
BG_TITLES = {'bg-011-scene': '眼前：对蝉开口的八句',
             'bg-011-city': '这座城：带消歧器的壳',
             'bg-011-world': '这个天下：账上的清直',
             'bg-011-person': '这个人：清在笔底'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 53 首·八句七律 2/2/2/2）；史实句均有逐字引证；'
                 '系年第四十七次判决（题证系列第卅五状·蟬无一字与清直恰二）'
                 '「通鉴七十五卷连一个蟬字都没有；可它有清直，且两头都在人事的账上」——'
                 '同字两界第十七形态·清直形态首见：通鉴蟬/蝉/鳴蟬/蜩/高難飽/費聲/疏欲/'
                 '碧無情/梗猶/故園蕪已平/煩君/舉家清/薄宦全零（机器断言——咏物诗的物名'
                 '史部全库不识）；「清直」恰二分長慶三年癸卯八二三（逢吉荐李绅清直宜居'
                 '风宪——政敌递出去的梯子）与大中二年戊辰八四八（丁柔立以清直荐、德裕不'
                 '能用、讼德裕冤、坐阿附贬南阳尉——还不清的代价）——**史部的清直两头都在'
                 '人事的账上；诗的我亦舉家清不在任何账上**；「舉家」恰七闭域，廣明元年'
                 '庚子八八〇鄭綦鄭系義不臣賊舉家自殺（赴死）+大曆八年癸丑七七三李建举家'
                 '西归（拒位）——**史部的举家要么拒位要么赴死，诗的举家清是活着清**；'
                 '清297/高896/飽18/汎0 在册闭域；**互指循环指针第二次在场**（V071 首见'
                 '本篇坐实成系列）：ws notes「↑ 卷539#蟬」向上回指+539 本篇「{{:蟬 (李商隱)}}」'
                 '向下转引（机器断言：notes 三连页全库恰三——蟬/錦瑟/韓碑；八句全唐诗语料'
                 '全零——诗只活在诗页）；**壳侧作者消歧器首见**：锚「==[[蟬 (李商隱)|蟬]]==」'
                 '+转引「{{:蟬 (李商隱)}}」全唐诗各恰一——消歧器第一次挂上壳侧且显示名仍裸'
                 '（V059/V061 锚侧消歧/V062,V063 裸名/V067 同名裸锚反例/V069–V071 壳侧裸名'
                 '——消歧谱补全壳侧一层）；消歧理由在册可查：ws 蟬名页恰三+全唐诗蟬字 83'
                 '（539 内八=壳二+他诗六闭域档扫）；**零新建 source 连续第四首**（两源皆'
                 'V018 所立，539 第七次复用）；正文第二引上限用满第二十例（V018 句读式'
                 '疎/汎面在先+本迁移 ws 原样疏/泛面，各从其录，V018 句读式引文零重开断言）；'
                 '**跨迁移异体分工首见**（V018 存疎/汎归一面、本快照存疏/泛面——同一页两次'
                 '快照异体不同，逐行对读折叠判一致，双向断言）；**零标记页×100% 满级**'
                 '（V069 同形第二例，与 V071 双{{另}}×100% 对照成谱：评级与异文多寡正交）+,'
                 '**双转录句读分工首见**（Vtext 全裸/poem 全句读——夜雨寄北两侧皆裸的反面）'
                 '+分类四行含作者分类（对照 V071 两行无）+「詠蟬詩」类目首见（全库恰二页：'
                 '本篇+在獄詠蟬机器断言；非史料声明不升格 V048）；八句对蝉说话的第二人称'
                 '形态照登；PERSON 旧传简化段首引一段（文思清丽庭筠过之——**段内清字恰一'
                 '恰在笔底：史部给他的清在文章里，诗自己把清认领到门第上**；**段内题字'
                 '十一项全零：写蝉的人传里无一蝉字**——V071 无一瑟字同款）；「无持操对'
                 '举家清两部书各执一词」读法声明；V016/V066–V068/V070/V071 在册句零重开'
                 '（域断言）；KNOWN 零如实记录（第廿八例，audit 反向断言）；'
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
    A("""-- V072：李商隱《蟬》(work-t300-011) 四层背景（阶段 D 第 53 首·清直两界）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V026、V033、V035、V039、V048、V053、V057、
--       V058、V059、V060、V061、V062、V063、V064、V065、V066、V067、V068、V069、V070、
--       V071 已执行
--       （work-t300-011 与其 text-work-t300-011-ws（version_code=ws-fold，八行带句读、
--       第三行「五更疎欲斷」、第五行「薄宦梗猶汎」——**V018 存疎/汎归一面**）
--       与其源 source-ws-t300-011（edition 字段即底本「全唐詩」）都是 V018 的行；
--       source-quantangshi-539 是 V018 已立的卷539 卷页源（V018/V067/V068/V069/V070/V071
--       已引，本迁移第七次复用——**这次引到的是带作者消歧器的壳 {{:蟬 (李商隱)}}**）；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       source-jiutangshu-wenyuan 是 V016 已立的旧唐书文苑传源（李商隐传在此，简化字录入）；
--       判例在册句（义山/开成二年/岭表/三十六体/未几病卒/大中末/仲郢坐/还郑州 V016、
--       绹不之省/坎壈终身 V066/V067、以所业文干之/下笔不能自休 V067、恃才诡激/
--       为当涂者所薄 V068、茂元爱其才/背恩无行 V069、锦瑟句读式正文与故园（春晓）
--       V018、{{:錦瑟}}/↑…錦瑟 V071、{{:夜雨寄北}}/↑…寄令狐郎中 V069/V070、
--       穆王何事不重來/雲能合長生藥 V068、別來滄海事 V033、得宋之問藍田别墅 V035/V039）
--       只对照不重开。
--       **本迁移零新建 source（连续第四首）——
--       audit 断言本文件零 poetry_source INSERT、回滚零 source 删除。**
--
-- 数据源（可复现）：emit_v072.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/蟬__李商隱_.txt（零标记×100% 满级+双转录句读分工（Vtext 裸/poem 句读）+
--   疏/泛面（对 V018 疎/汎面——跨迁移异体分工双向断言）+notes 三连一行（全库恰三页）+
--   分类四行含作者分类+詠蟬詩类目（全库恰二页）+无 times/type/from 字段）、
--   全唐詩卷539（锚 ==[[蟬 (李商隱)|蟬]]== 与 {{:蟬 (李商隱)}} 各全唐诗唯一（机器断言）+
--   **壳外全卷无本篇一行**（八句全库零）+卷内蟬八=壳二+他诗六闭域）、
--   舊唐書卷190下（李商隐段首引一段+**段内清恰一恰在文思清丽+题字十一项全零**+段边界断言）、
--   通鑑卷224/243/248/254（四段逐字入引+四处年标题窗口断言：大曆八年七七三/長慶三年八二三/
--   大中二年八四八/廣明元年八八〇）+
--   通鑑 75 卷负证计数扫描（蟬/蝉/鳴蟬/蜩/高難飽/費聲/疏欲/碧無情/梗猶/故園蕪已平/煩君/
--   舉家清/薄宦 全零+清直恰二（243/248）+舉家恰七+家無9/飽18/梗4/清297/高896/汎0 闭域）+
--   既有迁移引文域逐句查重——传区间归属、二引/零重开/首引零域前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 background_line（八句七律 **2/2/2/2 顺次**：scene→1,2 city→3,4 world→5,6 person→7,8，
--   绑 text-work-t300-011-ws 的 8 行）+ 不碰 poetry_text_line。
-- 不做：**不新建任何 source（连续第四首）**；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「咏物诗的物名史部全库不识；史部的清直两头都在人事的账上」）：
--   * 「清直两界」系通鉴四段逐字入引支撑的对照判决，非史实因果——通鉴不记这首诗本身；
--     亦不考本诗系年（旧注系大中十年等说一律不采信不铸造）；
--   * 「我亦舉家清」不自证操守、「传说他无持操/诗说举家清各执一词」标明读法声明；
--   * 异体疏/疎、泛/汎只登记不裁决——V018 面与本快照面并存各从其录（生成时双向断言）；
--   * 通鉴清直恰二是逢吉荐绅/丁柔立案（长庆/大中）、舉家恰七含郑綦举家自尽（广明）——
--     与诗之清只共享字面，绝不当同一事；
--   * 正文第二引上限用满：V018 句读式一引在先，本迁移引 ws 页 poem 块存原样面——
--     各从其录，V018 句读式引文不重开（生成时硬断言），此后此诗正文关闭；
--   * 「壳侧消歧首见」「互指第二次」「零标记×满级」「句读分工」「分类行数形态」
--     均照登不判；
--   * 通鉴清297/高896/飽18/汎0 在册零入引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第廿八例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * V011/V016/V018/V026/V033/V035/V039/V053/V063/V066–V071 已引诸句只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 71，不含 72
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-011-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-011','source-quantangshi-539');
--    -- 两行（均 V018 所立，本迁移不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-011-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-011-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-011';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-011-%';  -- 四行全 LIKELY
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-011';   -- 恰 1（V018 所立）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-011'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-011';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-011-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V072_rollback.sql（按 id 全枚举删除；**零 source 删除**——
--   source-ws-t300-011 与 source-quantangshi-539 皆 V018 所立，绝不删）
START TRANSACTION;""")

    A('\n-- ---------- 0. 零新建 source（连续第四首；两源皆 V018 所立复用） ----------')

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
    brows = [{'id': k, 'work_id': 'work-t300-011',
              'layer': {'bg-011-scene': 'SCENE', 'bg-011-city': 'CITY',
                        'bg-011-world': 'WORLD', 'bg-011-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-011-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 72, 'Li Shang-yin''s Cicada (work-t300-011) background layers (stage-D poem 53, eight-line regulated verse 2/2/2/2): dating verdict forty-seven, thirty-fifth shape of the title-evidence series -- not one graph of the cicada in all seventy-five juan of the Tongjian, yet the histories have "pure and upright" (qingzhi) exactly twice, and both times on the payroll of office-seeking. Same-character-two-realms, seventeenth shape: the qingzhi shape, first seen. The Tongjian scores zero on cicada, the simplified cicada, sounding cicada, tiao (the old word), and on every phrase of the poem -- "built high, hard to be full", "wasting one''s cry", "sparse near to snapping", "one tree, green and heartless", "thin office, like driftwood still afloat", "the old garden, weeds leveled flat", "troubling you, most alerting me", "I too, my whole household pure" -- the object of the thing-poem is not even a word the histories recognize. Yet qingzhi appears exactly twice, and both times inside personnel politics: in Changqing 3, guimao, 823, Li Fengji, troubled by Li Shen''s strictures, "recommended Shen as pure and upright, fit to occupy the post of Censor-in-Chief; the emperor, taking the office likewise one of attested rank, suspected nothing and approved" -- a ladder handed to a rival, and Shen was shunted to Jiangxi within months; and in Dazhong 2, wuchen, 848: "at first, when Li Deyu was in government, one recommended Ding Rouli as pure and upright, fit for a remonstrance office; Deyu could not use him... after Deyu was demoted to Chaozhou, Rouli memorialized in plead his injustice; on bingyin, for fawning attachment he was demoted to County Commandant of Nanyang" -- the man certified pure and upright pays for defending the man who had refused him: the histories'' purity sits on either end of an office ledger, a political ladder or an unpaid debt; the poem''s "I too, my whole household pure" sits on no ledger at all. "Whole household" (jüjia) appears exactly seven times (closed-set archive), the two nearest the poem: in Guangming 1, gengzi, 880, when Chang''an fell, "Zheng Qi and Zheng Xi, deeming it unrighteous to serve the rebel, killed themselves, whole household together" -- a household that dies for purity; and in Dali 8, guichou, 773, when the soldiers tried to proclaim Li Jian after his father''s death, "Jian swore he would not obey, and led his whole household west back home" -- a household that refuses office: the histories'' whole households either die or refuse; the poem''s whole household is pure while living, afloat in a thin post with the cicada as its only witness. The mutual-pointer binding, first seen in V071, recurs here and becomes a series: the ws page''s notes carry the up-arrow back-reference to 卷539#蟬 while the scroll page''s text is the transclusion stub pointing back (machine-asserted: exactly three pages in the whole ws corpus carry this 539 notes triple -- Cicada, Inscribed Harps, Han Stele; all eight lines of the poem score zero across the Quan Tangshi corpus -- the text lives only on the poem page). New in this poem: the first time the stub itself wears an author-disambiguator -- the anchor is "==[[蟬 (李商隱)|蟬]]==" and the transclusion "{{:蟬 (李商隱)}}", machine-asserted each unique in the whole Quan Tangshi -- the disambiguator climbs onto the shell side for the first time (V059/V061 anchored it scroll-side, V062/V063 sat bare, V067 proved a bare twin-anchor can fail to disambiguate, V069-V071 shells were bare), while the display name stays bare 蟬. Why a disambiguator is warranted is on the record: exactly three cicada-named ws pages and 83 cicada graphs in the Quan Tangshi (eight inside juan 539: two in the shell plus six in other poems -- closed set). ZERO new sources, fourth poem running (audit asserts zero poetry_source INSERT and zero source deletion); both sources date from V018, the 539 source at its seventh reuse. Body use-ceiling reached, twentieth instance: V018 quoted the punctuated abbreviation built from the folded-variant reading (with graphs shu-variant/fan-variant); this migration quotes the ws page''s raw poem block in the graph forms the live page now carries (shu/fan) -- a cross-migration variant division of labor never before seen (one page, two snapshots, two graph sets; line-by-line collation confirms the fold reading; generator asserts both sides and that V018''s punctuated excerpt is never re-used); the body is now closed. The page is a zero-mark 100 percent page (no variant braces, no refs, no reflist -- machine-asserted; second specimen of V069''s满-level shape, and with V071''s double-brace 100 percent page it completes the orthogonality of rating and variant count); the dual transcription divides punctuation labor for the first time (Vtext lines bare, poem block fully punctuated -- the inverse of the Night Rain page where both sides run bare); the category footer is four lines and includes the author category (against V071''s two-line author-less footer -- the line count itself is the form) with the 詠蟬詩 (poems-on-cicadas) tag, first seen, exactly two such category pages in the corpus (machine-asserted; editorial, not a source claim, not upgraded, V048 precedent); the eight lines all speak to the cicada in the second person -- logged as form. PERSON first-cites one zero-domain simplified JTS passage -- "his writing was pure and beautiful; Tingyun surpassed him" -- the one and only "pure" graph in the whole biography segment (machine-asserted), and it sits in his prose style, not his household, and is even rated below Wen Tingyun''s; the histories put his purity in the writing while the poem claims it for the whole household, and the same historian elsewhere calls him unprincipled (V068 closed) -- two books hold rival verdicts on one man''s purity; readings declared, not facts; the segment holds none of the eleven title-side graphs -- the man who wrote the cicada leaves not one cicada-graph in his biography (same shape as V068''s no-immortal-graph, V071''s no-harp-graph). KNOWN zero honestly recorded (twenty-eighth instance, audit reverse-asserts); closed precedent keywords (including V016''s Lingbiao years and V018''s punctuated cicada and old-garden lines) stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 72);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V072 精确回滚：只删 V072 插入的行（id 全枚举）。',
         '-- **零 source 删除**：source-ws-t300-011（V018 所立的 ws 选本页源）与',
         '-- source-quantangshi-539（V018 所立的卷539 卷页源）本迁移皆复用，绝不删；',
         '-- work-t300-011 本体、其 text_line 8 行都是 V018 的行，绝不删；',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 72;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_VT1, WS_POEM, WS_NOTE3, WS_CAT4, V539_SHELL,
              TJ_QZ1, TJ_QZ2, TJ_JJ1, TJ_JJ2, JTS_W]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # SCENE：双转录分工+疏/泛面必须逐字入引 + V018 句读式引文零重开
    scene_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-011-scene')
    if '{{VtextStart}}本以高難飽{{VtextEnd}}' not in scene_ws:
        bad.append('Vtext 裸行未入 SCENE 引文（双转录句读分工首见照登硬卡）')
    if '五更疏欲斷' not in scene_ws or '薄宦梗猶泛' not in scene_ws:
        bad.append('疏/泛面未逐字入 SCENE 引文（跨迁移异体分工照登硬卡）')
    if '五更疎' in scene_ws or '梗猶汎' in scene_ws:
        bad.append('SCENE 引文混入疎/汎面——异体分工两面对写，本面只存疏/泛')
    if '本以高難飽，' not in scene_ws:
        bad.append('poem 句读面未入 SCENE 引文（句读分工硬卡）')
    if '本以高難飽，……我亦舉家清。' in cited:
        bad.append('V018 句读式引文重开了——本迁移引原样面，句读式不重开')
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-011-city' and s == 'source-ws-t300-011')
    if '↑ [[全唐詩/卷539#蟬|全唐詩·卷五百三十九]]' not in city_ws:
        bad.append('↑回指注未逐字入 CITY 引文（互指诗页侧照登硬卡）')
    if '[[Category:李商隱]]' not in city_ws:
        bad.append('CITY 分类引文缺作者分类——本页含作者分类（对照 V071 无）正是标本')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-011-city' and s == 'source-ws-t300-011'):
        bad.append('CITY ws locator 须含「不升格」声明（分类行三重断言失效）')
    city_q = next(ex for c, s, _, ex in CITATIONS if s == 'source-quantangshi-539')
    if '{{:蟬 (李商隱)}}' not in city_q:
        bad.append('消歧壳转引未逐字入 CITY 引文（壳侧消歧首见照登硬卡）')
    if '徒勞恨費聲' in city_q or '舉家清' in city_q:
        bad.append('CITY 卷页引文混入本篇正文语——壳外无正文一行正是本迁移的标本')
    c_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-011-city' and s == 'source-quantangshi-539')
    if '壳侧' not in c_loc or '消歧' not in c_loc:
        bad.append('CITY 卷页 locator 须含「壳侧/消歧」声明（消歧谱补壳侧硬卡）')
    # WORLD：四段史文必须在引文内；诗语零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-011-world')
    for tok in ('逢吉薦紳清直', '宜居風憲之地', '不疑而可之', '有薦丁柔立清直',
                '坐阿附貶南陽尉', '義不臣賊，舉家自殺', '舉家西歸'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（四段必须入引）')
    for tok in ('蟬', '高難飽', '費聲', '疏欲', '碧無情', '煩君', '薄宦', '故園'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文）')
    w_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-011-world')
    if '清直' not in w_loc or '舉家' not in w_loc:
        bad.append('WORLD locator 须点出清直/舉家（两界柄词声明）')
    # PERSON 首引句必须在引文内 + 在册句零重开
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-011-person')
    for tok in ('文思清丽', '庭筠过之'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺首引要素「{tok}」（简化字段首引照登硬卡）')
    for tok in ('{{:夜雨寄北}}', '{{:錦瑟}}', '↑ [[全唐詩/卷539#寄令狐郎中',
                '↑ [[全唐詩/卷539#錦瑟', '君問歸期未有期', '俄而茂元卒', '检校水部员外郎',
                '天子何在', '亞貶循州刺史', '京兆尹黎幹奏秋霖損稼', '商隐能为古文',
                '不喜偶对', '初聞此語，能不惘然', '東拒滄海', '胡為自棄滄海之外',
                '言與淚俱', '錦瑟無端五十', '只是當時已惘然', '別來滄海事',
                '得宋之問藍田别墅', '凝碧池頭奏筦絃', '樹杪百重泉', '家書抵萬金',
                '感時花濺淚', '春眠不覺曉', '穆王何事不重來', '雲能合長生藥',
                '乘興南遊不戒嚴', '孫處約諫書', '嵩雲秦樹久離居', '茂陵秋雨病相如',
                '商隐随亚在岭表累载', '李商隐，字义山，怀州河内人。', '开成二年',
                '未几病卒', '大中末', '仲郢坐', '还郑州', '绹不之省', '坎壈终身',
                '恃才诡激', '为当涂者所薄', '以所业文干之', '下笔不能自休',
                '本以高難飽，……我亦舉家清。'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    if BG_LINES != {'bg-011-scene': (1, 2), 'bg-011-city': (3, 4),
                    'bg-011-world': (5, 6), 'bg-011-person': (7, 8)}:
        bad.append('八句 background_line 须 2/2/2/2 顺次（V020 以来八句篇常规）')
    if len(re.findall(r"text-work-t300-011-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # **零新建 source**（连续第四首）
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
        bad.append("V072 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V072 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-011' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V072 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-011' AS subject_id" in sql:
        bad.append('V072 的 claim 主语应全部是 bg-011-*，work-t300-011 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V072 不碰 poetry_text_line')
    body_all = ''.join(BG.values())
    if '清直形态首见' not in body_all:
        bad.append('BG 须含「清直形态首见」（同字两界第十七形态）声明')
    if '人事的账上' not in body_all:
        bad.append('BG/WORLD 须含「史部的清直两头都在人事的账上」判决')
    if '活着清' not in body_all:
        bad.append('BG/WORLD 须含「诗的举家清是活着清」判决')
    if '第二次在场' not in body_all:
        bad.append('BG/CITY 须含「互指循环指针第二次在场」声明')
    if '壳侧' not in body_all:
        bad.append('BG/CITY 须含「壳侧作者消歧器首见」声明')
    if '异体分工' not in body_all:
        bad.append('BG/SCENE 须含「跨迁移异体分工首见」声明')
    if '满级' not in body_all:
        bad.append('BG/SCENE 须含「零标记页×100% 满级」声明')
    if '句读分工' not in body_all:
        bad.append('BG/SCENE 须含「双转录句读分工首见」声明')
    if '无一蝉字' not in body_all:
        bad.append('BG/PERSON 须含「写蝉的人传里无一蝉字」段级零证声明')
    if '零新建' not in body_all:
        bad.append('BG/CITY 须含「零新建 source（连续第四首）」声明')
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
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 72)' not in vblk:
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
              f'四处年标题窗口断言（長慶三年八二三/大中二年八四八/廣明元年八八〇/大曆八年七七三）；'
              f'负证机器复查六层（通鉴蟬/蝉/鳴蟬/蜩/高難飽/費聲/疏欲/碧無情/梗猶/故園蕪已平/'
              f'煩君/舉家清/薄宦全零+汎全零+清直恰二243,248+舉家恰七+家無9/飽18/梗4/清297/'
              f'高896 闭域/全唐诗壳锚与转引各恰一+八句全库零+539 蟬恰八闭域/'
              f'ws 零标记×满级+疏2泛2疎0汎0+双转录首末句各恰二+Vtext裸面+三连notes页恰三+'
              f'詠蟬类目页恰二+作者分类恰一+无times/type/from/旧传段题字十一项全零+清恰一'
              f'恰在文思清丽+V018 疎/汎面双向断言，快照变动即中止）；'
              f'前提全库查重硬卡十件+十三首引句零域断言；消歧壳/↑回指/Vtext裸行照登硬卡；'
              f'SCENE 疏/泛面入引+疎/汎零混入+V018 句读式引文零重开断言；CITY 壳侧/消歧硬卡；'
              f'CITY「不升格」硬卡；四段通鉴史文入引+诗语零混入断言；'
              f'PERSON 首引要素入引硬卡+V016/V018/V066–V071 诸句零重开硬卡；'
              f'判例只引不重开断言（含 V018 故园/锦瑟句读式与 V033,V035,V039 在册语在内）；'
              f'八句 2/2/2/2 形制断言；零 KNOWN 反向断言；'
              f'**零新建 source 断言（INSERT 恰零+回滚零 source 删除）**——连续第四首；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
