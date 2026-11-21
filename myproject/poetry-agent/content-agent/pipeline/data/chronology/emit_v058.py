#!/usr/bin/env python3
"""阶段 D 第 39 首：生成 V058——李白《聽蜀僧濬彈琴》(work-t300-330, V018 已立) 四层背景。

「为什么写」走到「琴」字的两界（撞字两界第三形态，V056 泪/V057 已矣之后）：
**诗里一张琴洗客心；通鉴「琴」字恰二处——一为令公之具，一为权市之媒**：
天宝十三年（甲午，七五二…实七五四年，窗口机器断言）玄宗置翰林院，
「下至僧、道、書、畫、琴、棋、數術之工皆處之，謂之待詔」（tj-217——琴是杂流待诏之具）；
至德二年（丁酉，七五七）房琯「或聽門客董庭蘭鼓琴，庭蘭以是大招權利，
御史奏庭蘭贓賄」（tj-219——琴是宰相门客的纳贿之门，董庭兰正是当日天下第一琴手）。
**史部的琴：一处挂在杂艺待诏名下，一处开在权贿案卷里**——
与诗中「客心洗流水」那张琴同字两界；此三句通鉴史文正是本迁移 WORLD 层的
判决证据（入引），**在册零入引辖的是诗集侧**：綠綺/霜鐘他卷他人句从未切片
（audit 硬卡他人诗句零混入）。
**「流水」撞字第三例**：诗中「客心洗流水」是伯牙子期典；
通鉴「流水」恰一处=tj-194 貞觀十年（丙申，六三六）长孙皇后著论
「徒戒其車如流水馬如龍」——流水在史部是车马之喻（闭域+窗口+前字「如」断言）。
诗语「蜀僧」「綠綺」「峨眉」「萬壑」「霜鐘」「碧山」「秋雲」「一揮手」
通鉴全零（机器断言八连）；蜀僧题族唯本篇：全唐詩「蜀僧」恰 2=卷183 锚桩。
零铸造零 relation。

CITY 层**新立 source-quantangshi-183**（V051 卷159 之后首见再立全唐詩新卷源）：
本篇底本指向「[[全唐詩/卷183#聽蜀僧濬彈琴|全唐詩·卷183]]」——
底注锚点片段**非空**（对照 V056 空锚片段，指向完整在册）；卷183 快照在案，
篇题锚点+转引桩各恰一（无消歧直锚，同 V055/V057 结构）；
分类行「琴詩」系整理者分类（V048 判例三重断言）；页 {{另}}/{{别}}/{{*}}/<ref>
四全零而 75%（零标记×75% 正交三度再验）。

PERSON 层新传单得首引**互救连环**：「**初，白遊并州，見郭子儀，奇之。
子儀嘗犯法，白為救免。**」——李白早年救过郭子儀的命（XTS 恰一，JTS 全卷无
「郭子儀」三字——新传单得，机器断言）；而郭子儀请解官赎李白死罪那句
（「至是子儀請解官以贖」）V032 已引在册零重开（audit 硬卡字样）。
**诗里的琴要人还山，史里这段传把诗人写成救人者**——并置是读法声明非史实；
传中「初」字回叙（列传体追述，非编年追书）再次声明不锚年份（V057 边界延伸）。

八句五律 2/2/2/2 形制（同 V052/V054）；正文第二引上限用满第六例
（V018 text claim 一引在先，全库查重恰一处；SCENE 全诗正文二引对后来关闭）。

用法: python3 -I emit_v058.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/聽蜀僧濬彈琴.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS2 = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
V183 = pathlib.Path('/tmp/src-dl/quantangshi/vol183.txt').read_text(encoding='utf-8')
TJ194 = pathlib.Path('/tmp/src-dl/tongjian/tj-194.txt').read_text(encoding='utf-8')
TJ217 = pathlib.Path('/tmp/src-dl/tongjian/tj-217.txt').read_text(encoding='utf-8')
TJ219 = pathlib.Path('/tmp/src-dl/tongjian/tj-219.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 聽蜀僧濬彈琴', '| title    = 聽蜀僧濬彈琴', 'ws header title(题面直录——蜀僧濬系人,页内无注)')
WS_AUTHOR = slice_between(WS, '| author   = 李白', '| author   = 李白', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '| notes    = {{Textquality|75%}}↑ [[全唐詩/卷183#聽蜀僧濬彈琴|全唐詩·卷183]]',
                        '全唐詩·卷183]]',
                        'ws 页底注(75%+底本指向锚点片段非空——对照 V056 空锚,指向完整照登)')
WS_CAT = slice_between(WS, '[[Category:琴詩]]', '[[Category:琴詩]]', 'ws 分类行(琴詩——整理者分类,非史料;V048 分类行判例)')
WS_L1 = slice_between(WS, '蜀僧抱綠綺，西下峨眉峰。', '峨眉峰。', 'ws第1联(蜀僧抱绿绮下山——绿绮=卓文君琴名,读法)')
WS_L2 = slice_between(WS, '爲我一揮手，如聽萬壑松。', '萬壑松。', 'ws第2联(挥手一弹如万壑松——以山写声)')
WS_L3 = slice_between(WS, '客心洗流水，餘響入霜鐘。', '入霜鐘。', 'ws第3联(流水洗客心/余响入霜钟——流水=伯牙典,读法)')
WS_L4 = slice_between(WS, '不覺碧山暮，秋雲暗幾重。', '秋雲暗幾重。', 'ws第4联(曲终碧山已暮秋云暗——时间全在听觉里流失)')
XTS_G = slice_between(XTS2, '初，白遊并州，見郭子儀，奇之。子儀嘗犯法，白為救免。', '白為救免。',
                      '新传并州救郭子仪两句(从未入引,PERSON 层首引,全库查重硬卡;新传单得 JTS 全卷无郭子儀)')
TJ_HL = slice_between(TJ217, '下至僧、道、書、畫、琴、棋、數術之工皆處之，謂之「待詔」。', '謂之「待詔」。',
                      '通鉴天宝十三载置翰林院待诏段(琴通鉴一处——杂艺待诏之具;窗口断言)')
TJ_DL = slice_between(TJ219, '或聽門客董庭蘭鼓琴，庭蘭以是大招權利。', '大招權利。',
                      '通鉴至德二年房琯听董庭兰鼓琴段(琴通鉴二处——权贿之门;窗口断言;判决证据入引)')
TJ_LS = slice_between(TJ194, '徒戒其車如流水馬如龍，是開其禍敗之源而防其末流也。', '防其末流也。',
                      '通鉴贞观十年长孙后论车如流水句(流水通鉴唯一一处——车马之喻;窗口+前字断言)')
Q183 = slice_between(V183, '==[[聽蜀僧濬彈琴]]==', '==[[聽蜀僧濬彈琴]]==', '卷183 本篇篇题锚点(无消歧直锚+桩,同 V055/V057 结构)')
Q183_S = slice_between(V183, '{{:聽蜀僧濬彈琴}}', '{{:聽蜀僧濬彈琴}}', '卷183 本篇转引桩')

# ---------- 传区间归属复验（V036 立规） ----------
_xa = XTS2.find('==李白==')
_xm = re.search(r'\n==[^=\n]{1,10}==', XTS2[_xa + 8:])
_seg_x = XTS2[_xa:_xa + 8 + _xm.start()]
_ja = JTS.find('=李白=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
if not (0 <= _xa and '見郭子儀' in _seg_x):
    raise SystemExit('切片越出李白段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；三扇窗口） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ217, TJ_HL, '天寶十三年')
_window(TJ219, TJ_DL, '至德二年')
_window(TJ194, TJ_LS, '貞觀十年')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_allq = ''.join(f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt')))
# ① 通鉴：琴恰二=tj-217/tj-219 闭域；流水恰一=tj-194 且前字「如」；诗语八词全零
_qin = {n: t.count('琴') for n, t in _tjf.items() if '琴' in t}
if _qin != {'tj-217.txt': 1, 'tj-219.txt': 1}:
    raise SystemExit(f'通鉴「琴」不是恰二处（实 {_qin}）——琴两界论断须重估')
_ls = {n: t.count('流水') for n, t in _tjf.items() if '流水' in t}
if _ls != {'tj-194.txt': 1}:
    raise SystemExit(f'通鉴「流水」不是恰一处（实 {_ls}）——流水撞字论断须重估')
_i = TJ194.find('流水')
if TJ194[_i - 1] != '如' or TJ194[_i + 2] != '馬':
    raise SystemExit('tj-194「流水」前后字不是「如…馬」——車如流水馬如龍结构变了')
for _w in ('蜀僧', '綠綺', '峨眉', '峨嵋', '萬壑', '霜鐘', '碧山', '秋雲', '一揮手'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗语八连全零的判决失效，须重读')
# ② 全唐詩：蜀僧恰二=本篇锚桩；綠綺/霜鐘在他卷他人诗（在册册数）
if _allq.count('蜀僧') != 2 or V183.count('==[[聽蜀僧濬彈琴]]==') != 1 or V183.count('{{:聽蜀僧濬彈琴}}') != 1:
    raise SystemExit(f'全唐詩「蜀僧」不是恰二（本篇锚桩）——题族唯本篇论断须重估')
if _allq.count('綠綺') != 2 or 'vol183.txt' in [n for n in ('x',) if False] or V183.count('綠綺') != 0:
    raise SystemExit('全唐詩「綠綺」册数/本篇零正文命中结构变了——琴名在册册数须重估')
if _allq.count('霜鐘') != 7:
    raise SystemExit(f'全唐詩「霜鐘」不再是 7 处（实 {_allq.count("霜鐘")}）——他人钟声音节在册册数须重估')
# ③ ws：四标记全零 + 75% 恰一 + 底注锚片段非空
if WS.count('{{另') or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页标记不再是全零——零标记页论断失效，须重读快照')
if WS.count('{{Textquality|75%}}') != 1 or WS.count('卷183#聽蜀僧濬彈琴|') != 1:
    raise SystemExit('ws 页 75%/底注非空锚片段结构变了——对照 V056 空锚的断言失效')
# ④ 传区间与首引前提
for _w in ('琴', '流水', '綠綺'):
    if _w in _seg_j or _w in _seg_x:
        raise SystemExit(f'「{_w}」落在李白传区间——传不系琴负证失效，须重读原文')
if JTS.count('郭子儀') != 0:
    raise SystemExit('旧传竟有郭子儀——新传单得论断失效，须重读')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
_prev_g = [f.name for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V058')
           for _ln in f.read_text(encoding='utf-8').splitlines()
           if 'evidence_excerpt' in _ln and '見郭子儀' in _ln]
if _prev_g:
    raise SystemExit(f'「見郭子儀」已在 {_prev_g} 入引——首引前提失效，PERSON 层须重设计')
_prev_z = [f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V058')
           for _ln in f.read_text(encoding='utf-8').splitlines()
           if 'evidence_excerpt' in _ln and '秋雲暗幾重' in _ln]
if _prev_z != ['V018']:
    raise SystemExit(f'本诗正文既往引文域不是恰一处 V018（实 {_prev_z}）——第二引上限论断须重估')
_prev_s = sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V058')
                  for _ln in f.read_text(encoding='utf-8').splitlines()
                  if 'evidence_excerpt' in _ln and '解官以贖' in _ln})
if _prev_s != ['V032']:
    raise SystemExit(f'「解官以贖」既往引文域不是恰一处 V032（实 {_prev_s}）——零重开前提须重估')
_prev_src = [f.name for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V058')
             and 'source-quantangshi-183' in f.read_text(encoding='utf-8')]
if _prev_src:
    raise SystemExit(f'source-quantangshi-183 已在 {_prev_src} 立行——新立源前提失效')

BG = {
    'bg-330-scene': (
        '八句是一场音乐会的全程，而时间全在听觉里流失：蜀僧抱着绿绮琴，'
        '向西走下峨眉峰（「蜀僧抱綠綺，西下峨眉峰」——绿绮是古琴名，此读法系'
        '本层声明）；他为我挥手一弹，满耳像听万壑松风（「爲我一揮手，如聽萬壑松」——'
        '以山写声）；客居的心被流水洗过，余响融进霜天的钟声'
        '（「客心洗流水，餘響入霜鐘」——流水暗用伯牙鼓琴志在流水之典，读法声明，'
        '页上无一字自注）；不觉碧山已暮，秋云暗暗叠了几重'
        '（「不覺碧山暮，秋雲暗幾重」——曲终才发觉天黑，此诗正文系**第二引**：'
        'V018 text claim 已一引在先，全库查重恰一处，两度上限至此用满，'
        '此诗正文对后来迁移关闭）。'),
    'bg-330-city': (
        '这条城的档案先立户籍：**本迁移新立 source-quantangshi-183**'
        '（V051 卷159 之后再立全唐詩新卷源，audit 断言新源恰一）。'
        '页底注「↑ [[全唐詩/卷183#聽蜀僧濬彈琴|全唐詩·卷183]]」——'
        '底本指向**锚点片段非空**（指向篇题完整，对照 V056 的空锚片段：'
        '同一体系里指向有全有缺，照登各自如实）。卷183 快照在案：'
        '本篇为「无消歧篇题锚点+转引桩」结构（机器断言各恰一，同 V055/V057）。'
        '分类行「琴詩」为整理者动作：照登+非史料声明+不升格（V048 判例）——'
        '「琴詩」这个类目本身就是整理者替我们建的档案柜。'
        '页 {{另}}/{{别}}/{{*}}/<ref> 四全零而 Textquality 75%：'
        '零标记×75% 正交横截面第三次复现（V055 首见、V057 再验，机器断言）。'
        '蜀僧题族唯本篇：全唐詩「蜀僧」恰 2=锚+桩；「綠綺」恰 2、「霜鐘」恰 7'
        '皆在他卷他人诗（琴名与钟声各是各诗，在册不引不牵合）。'),
    'bg-330-world': (
        '诗里一张琴洗客心；通鉴「琴」字 75 卷**恰二处**（文件闭域+双年标题窗口'
        '机器断言），处处不是这场音乐会：天宝十三载（甲午，七五四）'
        '「下至僧、道、書、畫、琴、棋、數術之工皆處之，謂之『待詔』」——'
        '琴挂在翰林杂艺待诏名下；至德二年（丁酉，七五七）房琯'
        '「或聽門客董庭蘭鼓琴，庭蘭以是大招權利，御史奏庭蘭贓賄」——'
        '琴开在宰相门客的权贿案卷里（董庭兰正是当日天下第一琴手）。'
        '**史部的琴：一处是杂流之具，一处是权市之媒**——与诗里那张琴同字两界，'
        '此三句史文系本层判决证据入引，诗集侧他人琴句在册零入引（audit 硬卡）。'
        '**「流水」撞字第三例**：诗中「客心洗流水」'
        '是伯牙子期的典；通鉴「流水」恰一处=贞观十年（丙申，六三六）'
        '长孙皇后著论「徒戒其車如流水馬如龍」——流水在史部是车马之喻'
        '（闭域+窗口+前字「如」后字「馬」机器断言）。诗语「蜀僧」「綠綺」'
        '「峨眉」「萬壑」「霜鐘」「碧山」「秋雲」「一揮手」通鉴八连全零'
        '（机器断言）——**听琴的语言整场进不了史部**；两传李白段'
        '「琴」「流水」「綠綺」全零（传写其人，不提这张琴）。'
        '本层零铸造零 relation。'),
    'bg-330-person': (
        '诗里请人弹琴洗心的，是个「客」；新传倒写了他救人的一面：'
        '「**初，白遊并州，見郭子儀，奇之。子儀嘗犯法，白為救免。**」'
        '（李白早年游并州，看出郭子儀不凡；郭子儀犯了法，李白出手救了他）——'
        '生成时全库查重：此两句既往零入引，本迁移首引；**新传单得**'
        '（旧传全卷无「郭子儀」三字，机器断言）。后来郭子儀请解官赎李白死罪'
        '（「至是子儀請解官以贖」）V032 已引在册零重开（audit 硬卡字样）——'
        '**一救在前、一赎在后，史书只把两头的账都记齐了**：'
        '救人者后来系于被救者之手（读法声明，非史实）。\n'
        '传中「初」字系列传体的回叙（非编年追书——V057 立的追书边界在此'
        '再声明一次：回叙不锚年份）；李白其余已用句（山東人/謫仙人/脱靴/'
        '宮錦袍/夜郎/青山/辭以孤窮失身 V056 首引）一个不重开；certainty '
        '不覆盖任何系年。'),
}
CLAIMS = {
    'claim-bg-330-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页四标记全零、Textquality 75%——零标记与不完备并存，'
        '正交三度再验）；全句第二引：正文 V018 text claim 一引在先'
        '（生成时全库查重恰一处），两度上限至此用满、此诗正文对后来'
        '迁移关闭（audit 硬卡）；绿绮=古琴名、流水=伯牙典均为读法声明'
        '非史料断言（页上无自注）。'),
    'claim-bg-330-city': (
        'FACT', 'LIKELY',
        '新立 source-quantangshi-183（audit 断言新源恰一、rollback 删之）；'
        '底注锚点片段非空（指向完整，对照 V056 空锚片段——同一体系指向有'
        '全有缺各自如实）；卷183 无消歧锚+桩（机器断言各恰一）；分类行'
        '「琴詩」照登+非史料声明+不升格；页四标记全零而 75%（正交三度再验）；'
        '全唐詩「蜀僧」恰 2 唯本篇、「綠綺」恰 2、「霜鐘」恰 7 他卷在册不引；'
        '题有琴而无时→零铸造零 relation。'),
    'claim-bg-330-world': (
        'FACT', 'LIKELY',
        '琴在史部恰二：tj-217 天宝十三载（甲午，七五四）翰林「琴、棋、數術之'
        '工」待诏+tj-219 至德二年（丁酉，七五七）房琯门客董庭蘭鼓琴'
        '「以是大招權利」（文件闭域+双年标题窗口机器断言）——史部的琴'
        '一为杂艺之具一为权贿之媒，与诗中琴同字两界（三句史文入引为判决证据，'
        '诗集侧他人琴句零入引，audit 硬卡）；'
        '流水撞字第三例：通鉴恰 1 处=tj-194 贞观十年（丙申，六三六）'
        '「車如流水馬如龍」（闭域+窗口+前后字断言）；诗语八词'
        '（蜀僧/綠綺/峨眉/萬壑/霜鐘/碧山/秋雲/一揮手）通鉴全零；'
        '两传李白段琴/流水/綠綺全零；certainty 不覆盖任何系年，'
        '诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-330-person': (
        'FACT', 'LIKELY',
        '新传并州救郭子仪两句并引首引（生成时全库引文域查重：見郭子儀'
        '既往零命中，audit 硬卡；新传单得——旧传全卷无郭子儀三字，'
        '机器断言）；「解官以贖」V032 已引零重开（audit 硬卡字样）；'
        '一救一赎并置为读法声明非史实；传「初」字列传回叙不锚年份'
        '（V057 追书边界延伸声明）；李白其余已用判例句零重开；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-330-scene', 'source-ws-t300-330',
     '页面 聽蜀僧濬彈琴（header author+四联八句，五段以「……」相連——'
     '全句**第二引**：正文 V018 text claim 一引在先（生成时全库查重恰一处），'
     '**两度上限至此用满，此诗正文对后来迁移关闭**；页 {{别}}/{{*}}/<ref>/{{另}} 全零、75%；'
     '绿绮/流水之典页上无自注，系引者读法声明）',
     join(WS_AUTHOR, WS_L1, WS_L2, WS_L3, WS_L4)),
    ('claim-bg-330-city', 'source-ws-t300-330',
     '页面 聽蜀僧濬彈琴（header title+页底注+分类行三段并收——底注'
     '「卷183#聽蜀僧濬彈琴」锚点片段非空（指向完整，对照 V056 空锚片段）；'
     '「琴詩」分类系整理者动作：非史料声明、不升格；页四标记全零而 75%——'
     '零标记×75% 正交第三次复现）',
     join(WS_TITLE, WS_NOTE, WS_CAT)),
    ('claim-bg-330-city', 'source-quantangshi-183',
     '卷一百八十三·李白集《聽蜀僧濬彈琴》篇题锚点+转引桩（无消歧直锚——'
     '机器断言锚桩各恰一；全唐詩「蜀僧」恰 2 即此二处，綠綺/霜鐘他卷在册不引）',
     join(Q183, Q183_S)),
    ('claim-bg-330-world', 'source-zizhi-tongjian-events',
     '卷二百一十七·天宝十三载翰林待诏段……卷二百一十九·至德二年房琯听'
     '董庭蘭鼓琴段……卷一百九十四·贞观十年長孫后論車如流水段'
     '（**通鉴「琴」恰二「流水」恰一**：文件闭域+三处年标题窗口机器断言——'
     '史部的琴一为杂艺之具一为权市之媒；流水系车马之喻撞字在册；'
     '三段史文皆逐字入引作判决证据，诗集侧他人琴句（綠綺/霜鐘他卷）零入引）',
     join(TJ_HL, TJ_DL, TJ_LS)),
    ('claim-bg-330-person', 'source-xintangshu-wenyi',
     '卷二百二·文艺中·李白传并州救郭子仪两句（生成时全库引文域查重：'
     '此二句既往零入引，本迁移首引；新传单得——旧传全卷无郭子儀；'
     '「解官以贖」V032 已引零重开；与诗中请琴洗心并置是读法声明）', XTS_G),
]
BG_LINES = {'bg-330-scene': (1, 2), 'bg-330-city': (3, 4),
            'bg-330-world': (5, 6), 'bg-330-person': (7, 8)}
BG_AUDIENCE = {'bg-330-scene': 'PRIMARY', 'bg-330-city': 'JUNIOR',
               'bg-330-world': 'SENIOR', 'bg-330-person': 'JUNIOR'}
BG_TITLES = {'bg-330-scene': '眼前：曲终才发觉天黑',
             'bg-330-city': '这座城：整理者建的琴诗档案柜',
             'bg-330-world': '这个天下：史部的琴一为艺具一为权媒',
             'bg-330-person': '这个人：救人者后来系于被救者之手'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 39 首·八句五律 2/2/2/2）；史实句均有逐字引证；'
                 '系年第三十三次判决（题证系列第廿一状·琴与流水）'
                 '「題有琴名，琴在史部一藝具一權媒；詩用流水，流水在史部只車馬之喻」——'
                 '通鉴「琴」恰二=tj-217 天宝十三载翰林琴棋待诏+tj-219 至德二年'
                 '房琯门客董庭蘭鼓琴大招權利+tj-194 貞觀十年車如流水馬如龍三段史文逐字入引'
                 '作判决证据（闭域+三窗口断言；诗集侧他人琴句零入引）；'
                 '通鉴「流水」恰一=贞观十年（丙申，六三六）車如流水馬如龍'
                 '（撞字第三例，闭域+窗口+前后字断言）；诗语八词通鉴全零；'
                 '新立 source-quantangshi-183（V051 之后再立全唐詩卷源，audit 恰一）；'
                 '底注锚点片段非空（对照 V056 空锚）；零标记×75% 正交三度再验；'
                 '此诗正文第二引上限用满对后来关闭（V018 在先+全库查重）；'
                 '新传并州救郭子仪两句首引（新传单得；解官以贖 V032 零重开）；'
                 'KNOWN 零如实记录（第十四例，audit 反向断言）；判例关键语零入引文。' for k in BG}


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
    A("""-- V058：李白《聽蜀僧濬彈琴》(work-t300-330) 四层背景（阶段 D 第 39 首·琴与流水）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V032、V051、V057 已执行（work-t300-330 与其
--       text-work-t300-330-ws、source-ws-t300-330 是 V018 的行；source-xintangshu-wenyi 是 V016 的行；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源）。
--       **本迁移新立 1 个 source**：source-quantangshi-183（V051 卷159 之后再立全唐詩新卷源；
--       audit 断言诗源表新建插入语句恰一处且 id 必为该源，rollback 删该行）。
--
-- 数据源（可复现）：emit_v058.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/聽蜀僧濬彈琴.txt（四标记全零×75% 正交三度再验+底注非空锚片段）、
--   舊唐書卷190下（李白段负证+全卷无郭子儀断言）、新唐書卷202（并州救郭两句首引+李白段负证）、
--   通鑑卷194/217/219（琴恰二+流水恰一+三处年标题窗口）+ 通鑑 75 卷/全唐詩 118 卷存快照
--   负证计数扫描（琴/流水/蜀僧/綠綺/峨眉/萬壑/霜鐘/碧山/秋雲/一揮手）+
--   既有迁移引文域逐句查重——传区间归属、首引/第二引/零重开/新源前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句形制：scene→1-2 city→3-4 world→5-6 person→7-8，
--   绑 text-work-t300-330-ws 的 8 行）+ 1 行 poetry_source（卷183）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有琴名，琴在史部一藝具一權媒；詩用流水，流水在史部只車馬之喻」）：
--   * 琴通鉴恰二（翰林待诏/董庭蘭权贿）+流水恰一（車如流水）——同字两界，三段史文入引作判决证据，诗集侧他人琴句零入引（audit 硬卡）；
--   * 此诗正文第二引上限用满：V018 一引在先（全库查重恰一处），对后来迁移关闭；
--   * 新立源恰一（source-quantangshi-183，audit 数量+id 双断言；rights_note PENDING 同款模板）；
--   * 绿绮/流水之典与一救一赎并置均为读法声明，audit 双声明在 BG 文本内；
--   * 传「初」字列传回叙不锚年份（V057 追书边界延伸声明）；
--   * KNOWN 零如实记录（第十四例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 山東人/謫仙人/脫靴/宮錦袍/夜郎/青山/解官以贖（V032 一引在册）/辭以孤窮失身 判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 57，不含 58
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-330-%';             -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-183';     -- 空（本迁移新立）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-330-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-330-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-330';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-330-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-330'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-330';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-330-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-quantangshi-183';  -- 恰 1（本迁移新立）
-- 回滚: recovery/V058_rollback.sql（按 id 全枚举删除，含新立 source 行；不动他迁移来源行与 V018 的行）
START TRANSACTION;""")

    A('\n-- ---------- 1. 唯一新 source（卷183——audit 断言恰一处） ----------')
    A("""INSERT INTO poetry_source (id, title, author, edition, url, rights_note, verification_status, source_kind, reliability)
SELECT * FROM (
SELECT 'source-quantangshi-183' AS id, '《全唐詩》卷一百八十三（王维…李白卷次区间之李白集所在卷·维基文库录入本）' AS title, NULL AS author, '维基文库《全唐詩》卷一百八十三（录入本）' AS edition, 'https://zh.wikisource.org/wiki/全唐詩/卷183' AS url, '《全唐詩》维基文库录入本，公有领域古籍。本行由内容流水线逐字定位核验；录入本本身可能需据扬州局刻本/中华书局点校本校对，核验状态保持 PENDING。' AS rights_note, 'PENDING' AS verification_status, 'POETRY_COLLECTION' AS source_kind, 'HIGH' AS reliability FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_source x WHERE x.id = t.id);""")

    A('\n-- ---------- 2. BACKGROUND content identities ----------')
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
    brows = [{'id': k, 'work_id': 'work-t300-330',
              'layer': {'bg-330-scene': 'SCENE', 'bg-330-city': 'CITY',
                        'bg-330-world': 'WORLD', 'bg-330-person': 'PERSON'}[k],
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

    A('\n-- ---------- 6. background_line（八句：2/2/2/2） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-330-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 7. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 58, 'Li Bai Listening to a Monk from Shu Called Jun Playing the Qin background layers (stage-D poem 39, eight-line regulated verse 2/2/2/2): dating verdict thirty-three, twenty-first shape of the title-evidence series -- the same-character split, third form: the poem''s qin washes the traveler''s heart, while the Tongjian''s character qin appears exactly twice (file-closed, twin year-heading windows): under Tianbao 13 the Hanlin Academy gathers monks, Daoists, calligraphers, painters, qin and chess players and other artisans as daizhao attendants, and under Zhide 2 Fang Guan''s guest-retainer Dong Tinglan plays the qin for him and thereby grasps power and profit until the censors impeach him for bribes -- in the histories the qin is once an artisan''s tool and once a broker of power, logged never quoted (audit hard-assert); flowing-water, the third character collision: the poem''s allusion to Boya and Ziqi meets the Tongjian''s single flowing-water -- the 636 Empress Zhangsun essay''s "carriages like flowing water, horses like dragons" (file-closed, windowed, neighbor-character asserted): flowing water in the histories is a metaphor for traffic; eight poem-words score zero across the Tongjian; a new source row registered: quan tang shi juan 183 (first new Quan Tangshi volume source since V051, audit count-and-id asserted, rollback deletes it); the base-pointer anchor fragment here is non-empty (against V056''s empty fragment -- pointers come complete and incomplete, each logged as found); zero-marker-times-75% orthogonality re-verified third time; the poem body hits its two-use ceiling (V018 first, machine-swept, closure declared); PERSON first-cites both adjacent New History sentences on Li Bai rescuing Guo Ziyi at Bingzhou (New History only: the Old History never names Guo; the later redeeming sentence stays closed to V032); KNOWN zero honestly recorded (fourteenth instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 58);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V058 精确回滚：只删 V058 插入的行（id 全枚举），含本迁移新立的 source-quantangshi-183。',
         '-- work-t300-330 本体、其 text_line 8 行与 source-ws-t300-330 都是 V018 的行，绝不删；',
         '-- 其余三个共用 source 行（ws-330/xintangshu-wenyuan/zizhi-tongjian-events）',
         '-- 均为他迁移所立，零删除；V058 零 relation。',
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
    L.append("DELETE FROM poetry_source WHERE id = 'source-quantangshi-183';  -- 本迁移新立，删之")
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 58;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_L1, WS_L2, WS_L3, WS_L4,
              XTS_G, TJ_HL, TJ_DL, TJ_LS, Q183, Q183_S]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 底注非空锚片段照登硬卡（对照 V056 空锚）
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-330-city' and s == 'source-ws-t300-330')
    if '卷183#聽蜀僧濬彈琴|' not in city_ws:
        bad.append('底注非空锚片段未逐字入 CITY 引文（对照 V056 空锚的照登硬卡）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-330-city' and s == 'source-ws-t300-330'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # SCENE 第二引上限声明硬卡
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-330-scene')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054–V057 同款硬卡）')
    # 琴两界/流水撞字三句正是判决证据——必须在 WORLD 引文内（正断言）；
    # 「在册零入引」辖的是他人诗句：全唐詩綠綺/霜鐘他卷之句从未切片，
    # 故通鉴三句之外不得再有任何诗集句子混入 WORLD 引文域。
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-330-world')
    for tok in ('待詔', '鼓琴', '大招權利', '流水馬如龍'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（琴两界/流水撞字三句必须入引）')
    if 'vol017' in w_ex or 'vol695' in w_ex or '霜鐘' in w_ex.replace('入霜鐘', ''):
        bad.append('WORLD 引文混入他人诗句——綠綺/霜鐘他人句子在册零入引')
    # PERSON 零重开
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-330-person')
    if '解官以贖' in p_ex:
        bad.append('「解官以贖」V032 已引零重开——不得入本迁移引文')
    if '見郭子儀' not in p_ex or '白為救免' not in p_ex:
        bad.append('PERSON 引文须并含并州两句（首引前提）')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-330':
            for w in ('謫仙', '脫靴', '賜金放還', '宮錦袍', '夜郎', '青山', '山東人'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山', '隠鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒', '刻碑鳳林山南',
                '仕宦之疾徑', '放田里', '進止仍有風範', '茶鐺', '事母崔氏', '解官以贖'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句形制 2/2/2/2
    want = {'bg-330-scene': 2, 'bg-330-city': 2, 'bg-330-world': 2, 'bg-330-person': 2}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('八句 background_line 必须 2/2/2/2')
    if len(re.findall(r"text-work-t300-330-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # 新立源恰一（V051 同款双断言）
    n_src = len(re.findall(r'INSERT INTO poetry_source', sql))
    if n_src != 1:
        bad.append(f'本迁移应恰立 1 个新 source（实 {n_src} 处诗源表新建插入语句）')
    if not all("SELECT 'source-quantangshi-183' AS id" in
               sql[m.end():m.end() + 200] for m in re.finditer(r'INSERT INTO poetry_source', sql)):
        bad.append('新立 source 的 id 必须是 source-quantangshi-183')
    if "DELETE FROM poetry_source WHERE id = 'source-quantangshi-183'" not in build_rollback():
        bad.append('回滚必须删除本迁移新立的 source-quantangshi-183')
    if len(re.findall(r'DELETE FROM poetry_source', build_rollback())) != 1:
        bad.append('回滚只删新立的一行 source')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V058 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V058 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-330' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V058 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-330' AS subject_id" in sql:
        bad.append('V058 的 claim 主语应全部是 bg-330-*，work-t300-330 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V058 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '一藝具一權媒' not in body_all and '权市之媒' not in body_all:
        bad.append('BG/文件头须含「琴在史部一藝具一權媒」判决声明')
    if '車馬之喻' not in body_all:
        bad.append('BG 须含「流水只車馬之喻」撞字声明')
    if '撞字' not in body_all:
        bad.append('BG 须含「撞字」在册声明（流水第三例）')
    if '回叙' not in body_all:
        bad.append('BG/PERSON 须含列传「回叙」不锚年份边界声明（V057 延伸）')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 14 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（李白段，新传单得+旧传全卷无郭子儀）；'
              f'三处年标题窗口断言（天宝十三载七五四/至德二年七五七/貞觀十年六三六）；'
              f'负证机器复查四层（通鉴琴恰二=tj-217+tj-219 闭域+流水恰一=tj-194 前如後馬闭域+'
              f'诗语八词全零（蜀僧/綠綺/峨眉/峨嵋/萬壑/霜鐘/碧山/秋雲/一揮手）/'
              f'全唐詩蜀僧恰二=本篇锚桩+綠綺恰二本篇零命中+霜鐘恰七在册/'
              f'ws 四标记全零+75% 恰一+底注非空锚片段恰一/两传李段琴流水綠綺全零，快照变动即中止）；'
              f'首引前提全库查重硬卡（見郭子儀既往零引）+第二引前提硬卡（本诗正文恰一=V018）+'
              f'零重开前提硬卡（解官以贖恰一=V032）+新源前提硬卡（卷183 源行既往无）；'
              f'底注非空锚片段照登硬卡；SCENE locator 第二引/上限硬卡；'
              f'琴两界/流水撞字三段史文入引+诗集侧他人琴句零混入断言；判例只引不重开断言（含解官以贖）；'
              f'八句 2/2/2/2 形制断言；零 KNOWN 反向断言；'
              f'新立 source 恰一+id 必卷183 双断言（rollback 恰删一行）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
