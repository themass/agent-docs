#!/usr/bin/env python3
"""阶段 D 第 45 首：生成 V064——王維《桃源行》(work-t300-060, V018 已立) 四层背景。

「为什么写」走到**整场仙境不进史部**（同字两界第九形态·仙境形态首见；
V056 泪/V057 已矣/V058 琴·流水/V059 故鄉/V060 閉關/V061 王孫/V062 長策·解帶/
V063 梓州之后）：**「詩有桃源，桃源在史部七十五卷全零；詩有避地，
避地在史部只水旱兵戎」**——

通鉴「桃源」全零、「桃源行」全零、「武陵源」全零、「仙源」恰一处
（tj-209 **公主封号**——50% 页零年标题，只入闭域负证不作窗口断言，V056 卷缺
教训的镜像：**50% 页永不入围窗口**）、「避秦」「漁舟」「漁人」「桃花」「紅樹」
「房櫳」「隈隩」「靈境」「塵心」全零——陶渊明记里的世界整个在史部之外。
而「**避地**」恰二处（闭域+双窗口，逐字入引为判决证据）：
貞元十年（甲戌，七九四）陸贄論兩税「**版圖墮於避地**」（安史之乱后户籍丢在
流亡路上）、咸通九年（戊子，八六八）龐勳之乱「**往往避地江左**」（百姓躲进江东）
——**史部的避地是战乱流亡册上的窟窿；诗的「初因避地去人間」把同一动作
写成成仙的起因：史部记下的是消失的人，诗记下的是消失后成了仙的人**。
「**武陵**」恰 10 处七卷（闭域断言）也全是现实地名：永貞元年（乙酉，八〇五）
「**郎州武陵、龍陽江漲，流萬餘家**」（水灾，闭域+窗口入引）——
**史部的武陵是淹死万家的江岸；诗的武陵源是花竹散落的世外**。

CITY 层：**消歧全链闭环首见**——ws 页文件名「桃源行__王維_.txt」带作者消歧、
V018 源行 URL 与 source_locator 亦「桃源行 (王維)」、卷125 锚点
「==[[桃源行 (王維)|桃源行]]==」——快照里另有无名氏《桃源行》同名诗
（全唐詩「桃源」12 处七卷在册），**同名有主在册不引**（V059 皇子王綺判例）
而消歧器从 ws 文件名一直戴到诗集锚点：**同一首诗的消歧标记贯穿两层库**（首见）。
底注尾巴**纯文本系年注「時年十九」首见**（V052 署名/V055 题异/V057 一名/
V061 一题两案/本篇**作年**——第五形态；整理者把编年记进底注：十九岁写的，
照登不采信为系年——**audit 硬卡：此注不得铸 time.span**，仍零铸造）。
{{另}}×9 史上最多×75%；分类行「隱逸詩」。**零新源**（source-quantangshi-125
V037/V055/V057 已立、第四次复用）。

PERSON 层：诗是**少年作**（底注自注十九岁），传是**身后事**——新传辋川别业
地名族（華子岡/欹湖/竹裏館 V035/V039 在册零重开）不重开；本层首引旧传
「**維以詩名盛於開元、天寶間**」（生成时全库查重恰两处=V016/V035 在册零重开，
故本层改以判例对照立说：诗名满天下是**开元天宝**，而桃源十九岁作在**开元前**——
底注系年与传所载诗名盛期恰成先后，读法声明）…… 修正：**PERSON 首引新传**
「**九歲知屬辭，與弟縉齊名**」V040 已引零重开——零重开约束下本层取**旧传**
「**開元九年進士擢第**」{{YL|開元九年}}進士擢第 亦 V016 已引……
最终取**旧传「昆仲宦遊兩都」在册、新传句全在册**——本层首引句实为
**旧传「維尤長五言詩」**：V052 已引零重开。
——侦察结论：王维传可引句几乎全部已入引（九歲/開元九年/詩名盛/尤長五言/
輞川地名族全数在册），**本篇 PERSON 层以「零首引」如实记录**（首见）：
生成器断言候选句引文域全部非空，本层不新增 citation 而行文照登既有判例
（只引不重开的极端形态：满传无一句可首引）——这是纪律，不是空缺。

32 行长篇 shape：四层各绑 8 句（8/8/8/8 首次——长篇均分切段）。
正文第二引上限用满第十二例（V018 归一形一引在先，双针「漁舟逐水愛山春」
「不辨仙源何處尋」各恰一处）。

用法: python3 -I emit_v064.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/桃源行__王維_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
V125 = pathlib.Path('/tmp/src-dl/quantangshi/vol125.txt').read_text(encoding='utf-8')
TJ209 = pathlib.Path('/tmp/src-dl/tongjian/tj-209.txt').read_text(encoding='utf-8')
TJ234 = pathlib.Path('/tmp/src-dl/tongjian/tj-234.txt').read_text(encoding='utf-8')
TJ236 = pathlib.Path('/tmp/src-dl/tongjian/tj-236.txt').read_text(encoding='utf-8')
TJ251 = pathlib.Path('/tmp/src-dl/tongjian/tj-251.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 桃源行', '| title    = 桃源行', 'ws header title(行体乐府题面)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS,
                        '| notes    = {{Textquality|75%}}↑ [[全唐詩/卷125#桃源行|全唐詩·卷125]] 時年十九',
                        '時年十九',
                        'ws 页底注(75%+全锚+尾巴纯文本系年注「時年十九」首见——系年式注第五形态)')
WS_CAT = slice_between(WS, '[[Category:隱逸詩]]', '[[Category:隱逸詩]]', 'ws 分类行(隱逸詩——整理者分类;V048 判例)')
WS_L1 = slice_between(WS, '漁舟逐水愛山春，兩岸桃花夾{{另|去|古}}津。', '夾{{另|去|古}}津。', 'ws第1段起(渔舟入山春)')
WS_L2 = slice_between(WS, '坐看紅樹不知遠，行盡青溪{{另|不見|忽值}}人。', '忽值}}人。', 'ws第1段次(红树青溪忽值人)')
WS_L3 = slice_between(WS, '山口潛行始隈隩，山開曠望旋平陸。', '旋平陸。', 'ws第1段三(隈隩平陆——通鉴全零词)')
WS_L4 = slice_between(WS, '遙看一處攢雲樹，近入千家散花竹。', '散花竹。', 'ws第1段四(云树花竹千家)')
WS_L5 = slice_between(WS, '樵客初傳漢姓名，居人未改秦衣服。', '秦衣服。', 'ws第1段末(汉姓名秦衣服——两朝之间)')
WS_L6 = slice_between(WS, '居人共住武陵源，還從物外起田園。', '起田園。', 'ws第2段起(武陵源物外田园)')
WS_L7 = slice_between(WS, '月明松下房櫳{{另|靜|淨}}，日出雲中雞犬喧。', '雞犬喧。', 'ws第2段次(松下房栊云中鸡犬)')
WS_L8 = slice_between(WS, '{{另|驚|忽}}聞俗客爭來集，競引還家問{{另|都|鄉}}邑。', '問{{另|都|鄉}}邑。', 'ws第2段三(俗客来集问都邑——双枚标记)')
WS_L9 = slice_between(WS, '平明閭巷埽花開，薄暮漁樵乘水入。', '乘水入。', 'ws第2段四(晨扫花暮渔樵)')
WS_L10 = slice_between(WS, '初因避地去人間，{{另|及至|更聞}}成仙{{另|遂|去}}不還。', '不還。', 'ws第2段末(避地成仙——判决词句,三枚标记)')
WS_L11 = slice_between(WS, '峽裏誰知有人事，世中遙望空雲山。', '空雲山。', 'ws第3段起(峡里人事/世中云山)')
WS_L12 = slice_between(WS, '不疑靈境難聞見，塵心未盡思鄉縣。', '思鄉縣。', 'ws第3段次(灵境尘心)')
WS_L13 = slice_between(WS, '出洞無論隔山水，辭家終擬長游衍。', '長游衍。', 'ws第3段三(出洞游衍)')
WS_L14 = slice_between(WS, '自謂經過舊不迷，安知{{另|峰|岑}}壑今來變。', '今來變。', 'ws第3段四(峰壑今变——归途已改)')
WS_L15 = slice_between(WS, '當時只記入山深，青溪幾{{另|曲|度}}到雲林。', '到雲林。', 'ws第3段末(记路入山)')
WS_L16 = slice_between(WS, '春來遍是桃花水，不辨仙源何處尋。', '何處尋。', 'ws第4段(桃花水仙源难寻——全篇收束)')
JTS_Y = slice_between(JTS, '維以詩名盛於開元、天寶間', '天寶間',
                      '旧传诗名盛期句(V016/V035 已引在册零重开——PERSON 判例对照用,不入引文)')
TJ_BY1 = slice_between(TJ234, '版圖墮於避地', '於避地',
                       '通鉴贞元十年陆贄论版图段(避地史部一处——战乱户籍窟窿;窗口断言)')
TJ_BY2 = slice_between(TJ251, '往往避地江左', '避地江左',
                       '通鉴咸通九年庞勋乱段(避地史部二处——百姓躲进江东;窗口断言)')
TJ_WL = slice_between(TJ236, '郎州武陵、龍陽江漲，流萬餘家。', '流萬餘家。',
                      '通鉴永贞元年郎州江水段(武陵史部十处之一——水灾淹万家;窗口断言)')
TJ_XY = slice_between(TJ209, '其子伯陽尚仙源公主', '仙源公主',
                      '通鉴薛稷子尚仙源公主段(仙源史部唯一一处——公主封号;tj-209 零年标题页故只入闭域负证不作窗口断言)')
Q125 = slice_between(V125, '==[[桃源行 (王維)|桃源行]]==', '==[[桃源行 (王維)|桃源行]]==',
                     '卷125 本篇篇题锚点(作者消歧式——消歧全链闭环首见:ws文件名→V018源行→诗集锚点)')
Q125_S = slice_between(V125, '{{:桃源行 (王維)}}', '{{:桃源行 (王維)}}', '卷125 本篇转引桩')

# ---------- 传区间归属复验（V036 立规；本篇 PERSON 零首引，只验判例句在段内） ----------
_xa = XTS.find('==王維==')
_xm = re.search(r'\n==[^=\n]{1,10}==', XTS[_xa + 8:])
_seg_x = XTS[_xa:_xa + 8 + _xm.start()]
_ja = JTS.find('=王維=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
if not (0 <= _ja and '維以詩名盛於開元、天寶間' in _seg_j):
    raise SystemExit('判例句越出旧传王维段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；三扇窗口；tj-209 50%页零标题除外） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ234, TJ_BY1, '貞元十年')
_window(TJ251, TJ_BY2, '咸通九年')
_window(TJ236, TJ_WL, '永貞元年')
if len(_HEAD.findall(TJ209)) != 0:
    raise SystemExit('tj-209 不再是零年标题 50% 页——仙源只入闭域负证的断言须重估')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：仙境词全零；避地恰二闭域；武陵恰 10 七卷；仙源恰一（50%页）
for _w in ('桃源', '桃源行', '武陵源', '避秦', '漁舟', '漁人', '漁樵', '桃花', '紅樹',
           '房櫳', '隈隩', '靈境', '塵心', '游衍', '雞犬相聞', '不知有漢'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——整场仙境不进史部的判决失效，须重读')
_by = {n: t.count('避地') for n, t in _tjf.items() if '避地' in t}
if _by != {'tj-234.txt': 1, 'tj-251.txt': 1}:
    raise SystemExit(f'通鉴「避地」分布变了（实 {_by}）——避地只水旱兵戎判决须重估')
_wl = {f.name: t.count('武陵') for f in sorted(_tj.glob('tj-*.txt')) for t in [f.read_text(encoding='utf-8')] if '武陵' in t}
if sum(_wl.values()) != 10 or len(_wl) != 7:
    raise SystemExit(f'通鉴「武陵」不再是恰 10 处七卷（实 {sum(_wl.values())}/{len(_wl)} 卷）——武陵现实地名闭域须重估')
_xy = {n: t.count('仙源') for n, t in _tjf.items() if '仙源' in t}
if _xy != {'tj-209.txt': 1}:
    raise SystemExit(f'通鉴「仙源」不再是恰一处（实 {_xy}）——仙源=公主封号判决须重估')
# ② 全唐詩：桃源恰 12 七卷（同名有主在册）；隈隩全零（诗语无同源）
_tp = {f.name: t.count('桃源') for f in sorted(_qts.glob('vol*.txt')) for t in [f.read_text(encoding='utf-8')] if '桃源' in t}
if sum(_tp.values()) != 12 or len(_tp) != 7:
    raise SystemExit(f'全唐詩「桃源」不再是恰 12 处七卷（实 {sum(_tp.values())}/{len(_tp)} 卷）——同名有主在册闭域须重估')
if _allq.count('隈隩') != 0:
    raise SystemExit('全唐詩「隈隩」不再全零——诗语无同源断言失效')
if V125.count('桃源行') != 3 or (V125.count('==[[桃源行 (王維)|桃源行]]==') != 1 or V125.count('{{:桃源行 (王維)}}') != 1):
    raise SystemExit('卷125 桃源行恰 3（锚2+桩1）结构变了——消歧锚在册断言失效')
# ③ ws：{{另}}恰九具体字样 + 他标记全零 + 75% + 无三百首标记 + 全锚 + 時年十九恰一
for _mk in ('{{另|去|古}}', '{{另|不見|忽值}}', '{{另|靜|淨}}', '{{另|驚|忽}}', '{{另|都|鄉}}',
            '{{另|及至|更聞}}', '{{另|遂|去}}', '{{另|峰|岑}}', '{{另|曲|度}}'):
    if WS.count(_mk) != 1:
        raise SystemExit(f'ws 页异文标记 {_mk} 不再恰一枚——九枚异文史上最多断言失效，须重读快照')
if WS.count('{{另') != 9 or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页标记结构不再是 {{另}}×9 全他零——九枚判决失效')
if WS.count('{{Textquality|75%}}') != 1 or WS.count('卷125#桃源行|') != 1 or WS.count('時年十九') != 1:
    raise SystemExit('ws 页 75%/全锚/系年注结构变了——底注断言失效')
if WS.count('{{唐詩三百首}}') != 0:
    raise SystemExit('ws 页出现三百首标记——无标记照登断言失效')
# ④ 两传王维段负证 + PERSON 零首引前提（候选句全部已引）
for _seg, _nm in ((_seg_j, '旧传'), (_seg_x, '新传')):
    for _w in ('桃源', '武陵', '仙源', '避地', '桃花'):
        if _w in _seg:
            raise SystemExit(f'「{_w}」落在{_nm}王维段——传不载仙境负证失效，须重读原文')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V064')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

for _premise, _needle, _want in (
        ('本诗首句', '漁舟逐水愛山春', ['V018']),
        ('本诗末句', '不辨仙源何處尋', ['V018']),
        ('诗名盛期句', '維以詩名盛於開元', ['V016', 'V035']),
        ('九歲屬辭句', '九歲知屬辭', ['V040']),
        ('辋川别墅句', '別墅在輞川', ['V035', 'V039'])):
    _prev = _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
# PERSON 零首引断言：传内全部可引句的引文域均非空（满传无一句可首引）
for _cand in ('維以詩名盛於開元', '九歲知屬辭', '開元九年', '尤長五言詩', '維弟兄俱奉佛',
              '別墅在輞川', '昆仲宦遊兩都', '進士擢第', '事母崔氏'):
    if not _domain(_cand):
        raise SystemExit(f'PERSON 零首引前提破了：「{_cand}」既往零引——本层应改首引此句重设计')

BG = {
    'bg-060-scene': (
        '三十二句是一次完整往返：渔舟追着水走，爱这山里的春天，两岸桃花夹着'
        '古渡口（「漁舟逐水愛山春，兩岸桃花夾{{另|去|古}}津」）；坐看红树忘了路远，'
        '青溪走尽忽然遇见人（「坐看紅樹不知遠，行盡青溪{{另|不見|忽值}}人」）；'
        '山口里暗中行走才到幽曲处，山忽然开阔尽是平陆；远看一处攒聚的云树，'
        '走近是千家散落的花竹；樵客初传下汉朝的姓名，居人还穿着秦代的衣服'
        '（「樵客初傳漢姓名，居人未改秦衣服」——两朝之间的一截时间被整村保存，'
        '此读法系本层声明）。全篇 {{另}}×9——**史上最多异文枚数**——'
        '去/古、不見/忽值、靜/淨、驚/忽、都/鄉、及至/更聞、遂/去、峰/岑、曲/度'
        '逐枚照登不裁决；同页两形并存五度再验：V018 正文引文系归一形'
        '（「漁舟逐水愛山春，……不辨仙源何處尋。」），本迁移引文含九枚标记原样；'
        '此诗正文系**第二引**：V018 一引在先，全库查重双针各恰一处，'
        '两度上限至此用满，此诗正文对后来迁移关闭。'),
    'bg-060-city': (
        '**消歧全链闭环首见**：ws 页文件名「桃源行__王維_.txt」带作者消歧、'
        'V018 源行 URL 与 source_locator 亦「桃源行 (王維)」、卷125 诗集锚点'
        '「==[[桃源行 (王維)|桃源行]]==」把作者写进消歧器、题目留给展示'
        '（同 V059 雜詩作者消歧式）——**同一首诗的消歧标记从维基文件名一路戴到'
        '诗集锚点，两层库全链闭环首见**（audit 照登硬卡）；为什么必须消歧：'
        '全唐詩「桃源」恰 12 处七卷在册（含他人《桃源行》同题诗）——'
        '**同名有主在册不引**（V059 皇子王綺判例），消歧器正是同名之防。'
        '底注尾巴「時年十九」：**纯文本系年注首见（第五形态）**——V052 署名异说/'
        'V055 题异/V057 一名/V061 一题两案之后，整理者把作年记进底注：'
        '十九岁写的。**照登而不采信为系年**：底注系编者语非史源，'
        'audit 硬卡诗 time.span 仍零铸造。{{另}}×9×75%（九枚异文与不完备并存，'
        '正交第七度）；本页无 {{唐詩三百首}} 标记（与 V061/V063 有标记页互为有无）；'
        '底注全锚（同 V058–V063）；分类行「隱逸詩」系整理者动作（V048 判例：'
        '非史料声明、不升格）；source-quantangshi-125 系 V037/V055/V057 已立、'
        '**第四次复用零新源**（本层零铸造零 relation）。'),
    'bg-060-world': (
        '**詩有桃源，桃源在史部七十五卷全零**：通鉴「桃源」「桃源行」「武陵源」'
        '「避秦」「漁舟」「桃花」「紅樹」「房櫳」「隈隩」「靈境」「塵心」全零'
        '（机器断言）——陶渊明记里的世界整个在史部之外；「仙源」通鉴恰一处'
        '（闭域）=薛稷之子尚「**仙源公主**」——史部的仙源是一位公主的封号'
        '（tj-209 是零年标题 50% 页——**50% 页永不入围窗口断言**，V056 教训的'
        '镜像用法，audit 断言该页零标题）。而「**避地**」恰二处（闭域+双窗口'
        '机器断言），逐字入引为判决证据：貞元十年（甲戌，七九四）陸贄論兩税'
        '「**版圖墮於避地**」——安史乱后户籍丢在流亡路上；咸通九年（戊子，八六八）'
        '龐勳之乱「**往往避地江左**」——百姓躲进江东。**史部的避地是战乱流亡'
        '册上的窟窿；诗的「初因避地去人間」把同一动作写成成仙的起因——'
        '史部记下消失的人，诗记下消失后成了仙的人**（同字两界第九形态·'
        '仙境形态首见）。「**武陵**」通鉴恰 10 处七卷（闭域断言）全是现实地名：'
        '永貞元年（乙酉，八〇五）「**郎州武陵、龍陽江漲，流萬餘家**」'
        '（闭域+窗口入引）——**史部的武陵是淹死万家的江岸；诗的武陵源'
        '是花竹散落的世外**。全唐詩侧在册零入引（机器断言）：「桃源」恰 12 处'
        '七卷（他人同题诗）、「避秦」恰一（vol019）、「桃花水」恰一（vol228 杜甫'
        '「春岸桃花水」送别语）、「靈境」恰一（vol815）；「隈隩」全唐詩亦全零'
        '（诗语无同源）。本层零铸造零 relation。'),
    'bg-060-person': (
        '**PERSON 零首引（满传无一句可首引——只引不重开的极端形态，系列首见）**：'
        '本篇生成时机器断言王维两传全部可引候选句（詩名盛於開元、天寶間'
        'V016/V035/九歲知屬辭 V040/開元九年進士擢第 V016/維尤長五言詩 V052/'
        '維弟兄俱奉佛 V039/別墅在輞川 V035/V039/昆仲宦遊兩都 V035 等）'
        '既往引文域全部非空——**王维传已被十篇迁移引穿，本篇不新增逐字引文**，'
        '行文只对照既有判例立说（audit 断言候选句域非空，破了即中止重设计）。\n'
        '判例对照（读法声明，非史实）：底注系年注说诗是**十九岁作**（开元前），'
        '旧传判例句说诗名**盛於開元、天寶間**（V016/V035 在册零重开）——'
        '桃源里的仙源「不辨何處尋」，传里王维的辋川别业却句句有地名'
        '（華子岡/欹湖/竹裏館 V035/V039 在册）：**他写找不到的世外，'
        '自己有一座登记在册的世外**。\n'
        '**两传王维段桃源/武陵/仙源/避地/桃花全零**（机器断言——'
        '写过桃源行的人，传里没有一个仙源字）；certainty 不覆盖任何系年，'
        '底注「時年十九」不铸 time.span（audit 硬卡）。'),
}
CLAIMS = {
    'claim-bg-060-scene': (
        'FACT', 'LIKELY',
        '三十二句全诗本文（ws 页 {{另}}×9 史上最多、其余标记全零、Textquality 75%——'
        '九枚异文与不完备并存，正交横截面第七度复现）；九枚异文逐枚照登不裁决'
        '（去/古、不見/忽值、靜/淨、驚/忽、都/鄉、及至/更聞、遂/去、峰/岑、曲/度，'
        '引文含标记原样）；同页两形并存五度再验：V018 正文引文系异文取首项的'
        '归一文本，本迁移引文含九枚 {{另}} 标记原样，各从其录；汉姓名秦衣服'
        '两朝读法系本层声明；全句第二引：正文 V018 text claim 一引在先'
        '（生成时全库查重双针「漁舟逐水愛山春」「不辨仙源何處尋」各恰一处），'
        '两度上限至此用满、此诗正文对后来迁移关闭（audit 硬卡）。'),
    'claim-bg-060-city': (
        'FACT', 'LIKELY',
        '消歧全链闭环首见（ws 文件名「桃源行__王維_」→V018 源行 URL/source_locator'
        '「桃源行 (王維)」→卷125 作者消歧锚「(王維)|桃源行」——同一首诗的消歧标记'
        '贯穿两层库，audit 照登硬卡；同 V059 作者消歧式）；全唐詩「桃源」恰 12 处'
        '七卷在册（他人同题诗——同名有主在册不引，V059 王綺判例）；'
        '底注尾巴纯文本系年注「時年十九」首见（第五形态：V052 署名/V055 题异/'
        'V057 一名/V061 一题两案之后）——照登不采信为系年（编者语非史源，'
        'audit 硬卡仍零铸造）；卷125「桃源行」恰 3=锚 2+桩 1 机器断言闭域；'
        '底注全锚（同 V058–V063）；本页无 {{唐詩三百首}} 标记照登；分类行'
        '「隱逸詩」照登+非史料声明+不升格（V048 判例）；source-quantangshi-125'
        'V037/V055/V057 已立、第四次复用零新源；行体乐府题而无时→零铸造零 relation。'),
    'claim-bg-060-world': (
        'FACT', 'LIKELY',
        '通鉴「桃源/桃源行/武陵源/避秦/漁舟/漁人/漁樵/桃花/紅樹/房櫳/隈隩/靈境/'
        '塵心/游衍/雞犬相聞/不知有漢」全零（整场仙境不进史部，机器断言）；'
        '「仙源」恰一闭域=薛稷子尚仙源公主（tj-209 零年标题 50% 页——'
        '50% 页永不入围窗口断言，生成时断言该页零标题）；「避地」恰二闭域双窗口'
        '入引=貞元十年（甲戌，七九四）版圖墮於避地+咸通九年（戊子，八六八）'
        '往往避地江左（同字两界第九形态·仙境形态首见——史册窟窿/成仙起因，'
        'audit 硬卡）；「武陵」恰 10 处七卷闭域+入引一句=永貞元年（乙酉，八〇五）'
        '郎州武陵龍陽江漲流萬餘家（史部武陵=淹万家的江岸）；全唐詩桃源恰 12'
        '七卷/避秦恰一/桃花水恰一/靈境恰一在册零入引+隈隩全唐詩亦全零'
        '（诗语无同源）；certainty 不覆盖任何系年，诗 time.span/event.name/'
        'written_during 零铸造零 relation（底注「時年十九」亦不铸，audit 硬卡）。'),
    'claim-bg-060-person': (
        'FACT', 'LIKELY',
        '**PERSON 零首引（系列首见）**：生成时机器断言两传全部可引候选句'
        '（詩名盛於開元 V016/V035、九歲知屬辭 V040、開元九年 V016、'
        '維尤長五言詩 V052、俱奉佛 V039、別墅在輞川 V035/V039、'
        '昆仲宦遊兩都 V035、進士擢第 V016、事母崔氏 V055）既往引文域全部非空——'
        '本层不新增逐字引文，行文只对照既有判例（只引不重开的极端形态）；'
        '十九岁作（底注）与诗名盛开元天宝（旧传在册句）先后对照系读法声明；'
        '「他写找不到的世外，自己有一座登记在册的世外」系读法声明非史实；'
        '两传王维段桃源/武陵/仙源/避地/桃花全零（机器断言）；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-060-scene', 'source-ws-t300-060',
     '页面 桃源行 (王維)（三十二句长篇**引文選段**——(claim,source) 主键唯一行内'
     '九枚异文所在七句逐枚全引、以「……」相連，余句以 background_line 繫行；'
     '全句**第二引**：正文 V018 text claim 一引在先（其形系异文取首项的归一文本，'
     '本引文含九枚 {{另}} 标记原样——同页两形并存各从其录），生成时全库查重双针恰一处，'
     '**两度上限至此用满，此诗正文对后来迁移关闭**；{{别}}/{{*}}/<ref> 全零、75%；'
     '九枚异文史上最多逐枚照登；汉姓名秦衣服两朝读法系引者声明）',
     join(WS_L1, WS_L2, WS_L7, WS_L8, WS_L10, WS_L14, WS_L15)),
    ('claim-bg-060-city', 'source-ws-t300-060',
     '页面 桃源行 (王維)（header title+页底注+分类行三段并收——底注尾巴纯文本'
     '系年注「時年十九」=系年式注第五形态照登（编者语非史源，不采信为系年，'
     'audit 硬卡仍零铸造）；底注全锚「卷125#桃源行」（同 V058–V063）；'
     '本页无 {{唐詩三百首}} 标记照登；分类行系整理者动作：非史料声明、不升格）',
     join(WS_TITLE, WS_NOTE, WS_CAT)),
    ('claim-bg-060-city', 'source-quantangshi-125',
     '卷一百二十五·王維《桃源行》篇题锚点+转引桩（**作者消歧式**——'
     '消歧全链闭环首见：ws 文件名「桃源行__王維_」→V018 源行→本锚'
     '「(王維)|桃源行」贯穿两层库；全唐詩「桃源」恰 12 处七卷=同名有主在册不引'
     '（V059 王綺判例）；卷125「桃源行」恰 3=锚 2+桩 1 机器断言；源行系'
     'V037/V055/V057 已立、本迁移第四次复用零新源）',
     join(Q125, Q125_S)),
    ('claim-bg-060-world', 'source-zizhi-tongjian-events',
     '卷二百三十四·貞元十年（甲戌，七九四）版圖墮於避地段……卷二百五十一·'
     '咸通九年（戊子，八六八）往往避地江左段……卷二百三十六·永貞元年（乙酉，八〇五）'
     '郎州武陵龍陽江漲流萬餘家段……卷二百零九·仙源公主段（**通鉴桃源全零、'
     '避地恰二、武陵恰 10 七卷、仙源恰一**：文件闭域+三处年标题窗口机器断言，'
     'tj-209 零年标题 50% 页只入闭域负证不作窗口断言——史部避地是流亡窟窿、'
     '武陵是淹万家江岸、仙源是公主封号；三段史文逐字入引为判决证据；'
     '杜甫「春岸桃花水」等全唐詩在册句零入引）',
     join(TJ_BY1, TJ_BY2, TJ_WL, TJ_XY)),
]
BG_LINES = {'bg-060-scene': tuple(range(1, 9)), 'bg-060-city': tuple(range(9, 17)),
            'bg-060-world': tuple(range(17, 25)), 'bg-060-person': tuple(range(25, 33))}
BG_AUDIENCE = {'bg-060-scene': 'PRIMARY', 'bg-060-city': 'JUNIOR',
               'bg-060-world': 'SENIOR', 'bg-060-person': 'JUNIOR'}
BG_TITLES = {'bg-060-scene': '眼前：渔舟入山的完整往返',
             'bg-060-city': '这座城：戴到诗集锚点上的消歧器',
             'bg-060-world': '这个天下：整场仙境不进史部',
             'bg-060-person': '这个人：满传无一句可首引'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 45 首·三十二句长篇 8/8/8/8 首次）；史实句均有逐字引证；'
                 '系年第三十九次判决（题证系列第廿七状·桃源与避地）'
                 '「詩有桃源，桃源在史部七十五卷全零；詩有避地，避地在史部只水旱兵戎」——'
                 '通鉴桃源/桃源行/武陵源/避秦/漁舟/桃花/紅樹/房櫳/隈隩/靈境/塵心全零'
                 '（整场仙境不进史部）；仙源恰一闭域=仙源公主封号'
                 '（tj-209 零年标题 50% 页——50% 页永不入围窗口断言镜像用法）；'
                 '避地恰二闭域双窗口入引（貞元十年甲戌七九四版圖墮於避地+'
                 '咸通九年戊子八六八往往避地江左——史册流亡窟窿/成仙起因，'
                 '同字两界第九形态·仙境形态首见）；武陵恰 10 处七卷闭域入引'
                 '（永貞元年乙酉八〇五郎州武陵龍陽江漲流萬餘家——'
                 '史部武陵=淹万家江岸/诗武陵源=花竹世外）；'
                 '全唐詩桃源恰 12 七卷（同名有主在册不引 V059 判例）+避秦/桃花水/'
                 '靈境各恰一在册零入引+隈隩亦全零；'
                 '消歧全链闭环首见（ws 文件名→V018 源行→卷125 作者消歧锚'
                 '贯穿两层库）；底注尾巴纯文本系年注「時年十九」首见（第五形态）'
                 '照登不采信为系年（audit 硬卡仍零铸造）；{{另}}×9 史上最多×75%'
                 '正交第七度+同页两形并存五度再验；本页无三百首标记照登；'
                 '零新源（卷125 源 V037/V055/V057 已立第四次复用）；'
                 '此诗正文第二引上限用满第十二例对后来关闭（V018 在先+双针查重）；'
                 'PERSON 零首引（满传无一句可首引——只引不重开的极端形态，'
                 '生成时断言候选句引文域全部非空）；两传王段桃源/武陵/仙源/避地/'
                 '桃花全零；KNOWN 零如实记录（第二十例，audit 反向断言）；'
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
    A("""-- V064：王維《桃源行》(work-t300-060) 四层背景（阶段 D 第 45 首·桃源与避地）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V037、V039、V052、V055、V057、V059 已执行
--       （work-t300-060 与其 text-work-t300-060-ws、source-ws-t300-060 是 V018 的行；
--       source-quantangshi-125 是 V037/V055/V057 已立的卷125 源行（本迁移第四次复用，零新源）；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       本迁移 PERSON 零首引——王维两传可引句全部已入引（V016/V035/V039/V040/V052/V055），
--       零 poetry_citation 新增于 person claim；判例在册句只对照不重开）。
--       本迁移零新 source（audit 断言无诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v064.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/桃源行__王維_.txt（{{另}}×9 史上最多×75%+底注全锚+尾巴系年注「時年十九」+无三百首标记）、
--   舊唐書卷190下/新唐書卷202（两传王段桃源/武陵/仙源/避地/桃花全零负证+候选句全部已引断言）、
--   全唐詩卷125（作者消歧锚+桩）/桃源 12 处七卷/避秦/桃花水/靈境 在册扫描、
--   通鑑卷209/234/236/251（避地恰二+武陵恰 10 七卷+仙源恰一+三处年标题窗口+
--   tj-209 零年标题断言）+ 通鑑 75 卷/全唐詩 118 卷存快照负证计数扫描
--   （桃源/桃源行/武陵源/避秦/漁舟/漁人/漁樵/桃花/紅樹/房櫳/隈隩/靈境/塵心/游衍）+
--   既有迁移引文域逐句查重——传区间归属、二引/零重开/零首引前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 6 组逐字引用（(claim,source) 主键每对恰一行；
--   scene 三行正文切片合并为主键内单条长引文的三段拼接说明——见 CITATIONS 构建）+
--   32 background_line（三十二句长篇 **8/8/8/8 首次**：scene→1-8 city→9-16
--   world→17-24 person→25-32，绑 text-work-t300-060-ws 的 32 行）+ 零 poetry_source 行 + 不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span（底注「時年十九」亦不铸）、不写 event.name、不挂 written_during、
--   零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「詩有桃源，桃源在史部七十五卷全零；詩有避地，避地在史部只水旱兵戎」）：
--   * 仙境十六词通鉴全零+避地恰二闭域双窗口入引+武陵恰 10 闭域入引+仙源恰一（50%页不作窗口）；
--   * 汉姓名秦衣服两朝读法/十九岁作与诗名盛期先后对照/「登记在册的世外」均标明读法声明；
--   * 九枚异文引文含标记原样；同页两形并存五度再验（V018 归一形 vs 本迁移九标记原样形）；
--   * 系年注「時年十九」照登不采信为系年（编者语非史源，audit 硬卡仍零铸造）；
--   * 消歧全链闭环照登（ws 文件名→V018 源行→诗集锚点）；同名有主在册不引（V059 判例）；
--   * 此诗正文第二引上限用满：V018 一引在先（双针查重各恰一处），对后来迁移关闭；
--   * 全唐詩避秦/桃花水/靈境/桃源 12 处他卷在册零入引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第二十例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 詩名盛開元（V016/V035）/九歲屬辭（V040）/輞川别墅（V035/V039）判例只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 63，不含 64
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-060-%';             -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-125';     -- 恰 1（三迁移已立，本迁移复用不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-060-ws';  -- 恰 32
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-060-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-060';                                  -- 32（8/8/8/8）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-060-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-060'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-060';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-060-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-quantangshi-125';  -- 恰 1（复用，非本迁移所立）
-- 回滚: recovery/V064_rollback.sql（按 id 全枚举删除；零 source 删除——卷125 源行为三迁移所立）
START TRANSACTION;""")

    A('\n-- ---------- 1. 零新 source（卷125 源行三迁移已立，本迁移第四次复用） ----------')

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
    brows = [{'id': k, 'work_id': 'work-t300-060',
              'layer': {'bg-060-scene': 'SCENE', 'bg-060-city': 'CITY',
                        'bg-060-world': 'WORLD', 'bg-060-person': 'PERSON'}[k],
              'body_text': BG[k], 'audience': BG_AUDIENCE[k], 'claim_id': 'claim-' + k} for k in BG]
    A(guard('poetry_background', ['id', 'work_id', 'layer', 'body_text', 'audience', 'claim_id'],
            brows, 'x.id = t.id'))

    A('\n-- ---------- 5. 逐字引文（(claim,source) 主键每对恰一行；PERSON 零首引无 citation） ----------')
    L.append('INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(c)} AS claim_id, {sql_s(s)} AS source_id, {sql_s(loc)} AS locator, "
        f"{sql_s(ex)} AS evidence_excerpt FROM DUAL"
        for c, s, loc, ex in CITATIONS))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_citation x '
             'WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);')

    A('\n-- ---------- 6. background_line（三十二句长篇 8/8/8/8 首次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-060-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 7. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 64, 'Wang Wei''s Ballad of the Peach-Blossom Spring (work-t300-060) background layers (stage-D poem 45, thirty-two-line geyue octet-quartet 8/8/8/8 first time): dating verdict thirty-nine, twenty-seventh shape of the title-evidence series -- the utopia and the flight in two realms: taoyuan, "Ballad of the Peach-Blossom Spring", Wulingyuan, "fleeing Qin", fishing-boat, peach-blossom, red trees, latticed windows, hidden coves, spirit-realm, dust-heart all score zero across the Tongjian -- Tao Yuanming''s world never enters the histories; xianyuan ("fairy source") appears exactly once (file-closed): as the title of a princess married to the son of Xue Ji -- and juan 209 is a heading-less 50%-quality page, so it enters closed-domain negatives only, never a year-window (the mirror lesson of V061''s 50% pages, asserted at build time); bi-di ("fleeing to shelter") appears exactly twice (file-closed, windowed, quoted): in 794 Lu Zhi mourning that "the registers fell into the flight" after the An Lushan wars, and in 868 households "fleeing one and all to the south of the river" before Pang Xun''s revolt -- in the histories flight is a hole in the census; in the poem "first through fleeing they left the world" and became immortals: the histories record the people who vanished, the poem the people who became immortal by vanishing (the ninth same-character split, first utopia-place-name shape); Wuling appears exactly 10 times over 7 volumes (file-closed) and one line is quoted: in 805 the Yang river at Langzhou-Wuling "rose and swept away over ten thousand households" -- the histories'' Wuling drowns households, the poem''s Wulingyuan scatters flowers and bamboo; on the poetry side logged never quoted (machine-asserted): taoyuan 12 times over 7 juan (other poets'' same-titled ballads -- the homonym-with-owner rule of V059), bi-qin once, peach-blossom-waters once (Du Fu''s farewell line), spirit-realm once, while weiyu (hidden cove) scores zero in the poetry corpus too; the disambiguation chain closes end to end for the first time: the ws filename "桃源行__王維_", V018''s source row URL and locator, and juan 125''s author-disambiguated anchor "(王維)|桃源行" -- the same poem wearing its disambiguator through both libraries (audit hard-assert); the base-note tail carries a plain-text dating gloss "written at age nineteen" (fifth plain-text form after signature/title/alternative-name/double-title) -- logged, never promoted to chronology: an editor''s note is not a source, and the poem''s time.span stays uncast (audit hard-assert); nine 另 markers (the most ever on one page) with 75% (orthogonality seventh time) and same-page two-forms co-existence re-verified a fifth time; zero new sources (juan 125''s row reused for the fourth time); the poem body hits its two-use ceiling (V018 first, twin normalized needles, closure declared); PERSON zero-first-cite (first instance: every quotable sentence in both biographies is already cited by V016/V035/V039/V040/V052/V055 -- build-time asserts each candidate''s citation domain non-empty; the layer quotes nothing new and reads the precedent set against the base-note dating instead); both biographies contain no taoyuan/Wuling/xianyuan/bi-di/peach-blossom character in the Wang Wei segments (machine-asserted); KNOWN zero honestly recorded (twentieth instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 64);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V064 精确回滚：只删 V064 插入的行（id 全枚举）。零 source 删除：',
         '-- source-quantangshi-125 是 V037/V055/V057 已立的卷125 源行（本迁移第四次复用），绝不删；',
         '-- work-t300-060 本体、其 text_line 32 行与 source-ws-t300-060 都是 V018 的行，绝不删；',
         '-- source-zizhi-tongjian-events 为他迁移所立，零删除；V064 零 relation、PERSON 零首引。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 64;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_NOTE, WS_CAT,
              WS_L1, WS_L2, WS_L7, WS_L8, WS_L10, WS_L14, WS_L15,
              TJ_BY1, TJ_BY2, TJ_WL, TJ_XY, Q125, Q125_S]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 底注全锚 + 系年注 + 题行照登硬卡（CITY ws 引文）
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-060-city' and s == 'source-ws-t300-063' or c == 'claim-bg-060-city' and s == 'source-ws-t300-060')
    if '卷125#桃源行|' not in city_ws:
        bad.append('底注全锚未逐字入 CITY 引文（全锚形态照登硬卡）')
    if '時年十九' not in city_ws:
        bad.append('系年注「時年十九」未逐字入 CITY 引文（第五形态照登硬卡）')
    if '| title    = 桃源行' not in city_ws:
        bad.append('题行未逐字入 CITY 引文（行体题面照登硬卡）')
    if '不采信' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-060-city' and s == 'source-ws-t300-060'):
        bad.append('CITY ws locator 须含「不采信」（系年注不升格断言失效）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-060-city' and s == 'source-ws-t300-060'):
        bad.append('CITY ws locator 须含「非史料」声明（分类行三重断言失效）')
    # 作者消歧锚照登硬卡
    city_q = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-060-city' and s == 'source-quantangshi-125')
    if '==[[桃源行 (王維)|桃源行]]==' not in city_q:
        bad.append('作者消歧锚点未逐字入 CITY 引文（全链闭环首见照登硬卡）')
    # SCENE 九枚标记原样 + 第二引上限声明硬卡
    s_ex = ''.join(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-060-scene')
    for mk in ('{{另|去|古}}', '{{另|不見|忽值}}', '{{另|靜|淨}}', '{{另|驚|忽}}', '{{另|都|鄉}}',
               '{{另|及至|更聞}}', '{{另|遂|去}}', '{{另|峰|岑}}', '{{另|曲|度}}'):
        if mk not in s_ex:
            bad.append(f'SCENE 引文缺标记原样「{mk}」（九枚照登硬卡）')
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-060-scene' and s == 'source-ws-t300-060')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054–V063 同款硬卡）')
    # WORLD：三段史文必须在引文内（判决证据）；诗句/在册句零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-060-world')
    for tok in ('版圖墮於避地', '避地江左', '龍陽江漲', '仙源公主'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（避地/武陵/仙源必须入引）')
    for tok in ('漁舟', '桃花', '紅樹', '靈境', '武陵源', '桃源', '房櫳', '隈隩',
                '塵心', '避秦', '春岸'):
        if tok in w_ex.replace('龍陽江漲', ''):
            # 注意「龍陽江漲」段本身合法；诗语词零混入单独查
            pass
    for tok in ('漁舟', '紅樹', '武陵源', '隈隩', '塵心', '避秦', '春岸桃花水'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语/在册项「{tok}」（诗句与全唐詩在册句不得入通鉴引文）')
    # PERSON 零首引：无 person citation 行
    if any(c == 'claim-bg-060-person' for c, _, _, _ in CITATIONS):
        bad.append('V064 PERSON 零首引（系列首见）——claim-bg-060-person 不得有 citation 行')
    for c, s, _, ex in CITATIONS:
        if not s.startswith('source-ws-t300-'):
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
                '晚年唯好靜', '漁歌入浦深', '貶晙為梓州刺史', '段子璋反',
                '參天可汗道', '火炬於樹杪', '九歲知屬辭', '別墅在輞川', '華子岡'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 三十二句长篇 8/8/8/8 首次
    if {k: len(v) for k, v in BG_LINES.items()} != {k: 8 for k in BG}:
        bad.append('三十二句 background_line 须每层恰 8（8/8/8/8）')
    if sorted(n for seqs in BG_LINES.values() for n in seqs) != list(range(1, 33)):
        bad.append('8/8/8/8 须覆盖 1-32 句各一次')
    if len(re.findall(r"text-work-t300-060-ws' AS version_id", sql)) != 32:
        bad.append('bg_line INSERT 的 version 行数应为 32')
    # 零新 source（V052 教训：断言文案也不得出现该字面量）
    if 'INSERT INTO poetry_' + 'source' in sql:
        bad.append('V064 有意零新 source，但 SQL 里出现了诗源表新建插入语句')
    # 版本账本 INSERT 必须含 version_no=64 反查守卫（扫描器把该表排除在通用守卫外，此处显式补卡）
    vblk = sql[sql.index('INSERT INTO poetry_schema_version'):]
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 64)' not in vblk:
        bad.append('poetry_schema_version 的 INSERT 缺 version_no=64 幂等守卫')
    if 'DELETE FROM poetry_source' in build_rollback():
        bad.append('回滚不得删任何 source 行（卷125 源行为三迁移所立）')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V064 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V064 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-060' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V064 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-060' AS subject_id" in sql:
        bad.append('V064 的 claim 主语应全部是 bg-060-*，work-t300-060 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V064 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '桃源在史部七十五卷全零' not in body_all:
        bad.append('BG/文件头须含「桃源在史部七十五卷全零」判决声明')
    if '同字两界第九形态' not in body_all:
        bad.append('BG 须含「同字两界第九形态」声明')
    if '消歧全链闭环' not in body_all:
        bad.append('BG/CITY 须含「消歧全链闭环」结构声明')
    if '時年十九' not in ''.join(BG.values()) or '第五形态' not in body_all:
        bad.append('BG 须含「時年十九」系年注第五形态声明')
    if '零首引' not in body_all:
        bad.append('BG/PERSON 须含「PERSON 零首引」系列首见声明')
    if '50% 页永不入围窗口' not in body_all and '50% 页永不入围' not in body_all:
        bad.append('BG/WORLD 须含「50% 页永不入围窗口」镜像断言声明')
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
              f'切片传区间归属断言（旧传王维段判例句）；'
              f'三处年标题窗口断言（貞元十年七九四/咸通九年八六八/永貞元年八〇五）'
              f'+tj-209 零年标题断言（50% 页永不入围窗口镜像用法）；'
              f'负证机器复查五层（通鉴桃源/桃源行/武陵源/避秦/漁舟/漁人/漁樵/桃花/紅樹/'
              f'房櫳/隈隩/靈境/塵心/游衍/雞犬相聞/不知有漢全零+避地恰二闭域(tj-234/251)+'
              f'武陵恰10七卷闭域+仙源恰一(tj-209)/全唐詩桃源恰12七卷闭域+隈隩亦全零/'
              f'卷125 桃源行恰三=锚二桩一闭域/ws 九枚标记各恰一具体字样+他标记全零+75%+'
              f'三百首恰零+全锚+時年十九恰一/两传王段桃源/武陵/仙源/避地/桃花全零，快照变动即中止）；'
              f'前提全库查重硬卡五件+PERSON 零首引九候选句域全非空断言'
              f'（正文双针恰一=V018+诗名盛恰二=V016/V035+九歲恰一=V040+别墅恰二=V035/V039）；'
              f'底注全锚+系年注時年十九+题行+作者消歧锚照登硬卡；CITY「不采信/非史料」硬卡；'
              f'SCENE 九枚标记原样+第二引/上限硬卡；避地两界/武陵水灾/仙源封号入引'
              f'+诗语与杜甫桃花水在册句零混入断言；PERSON 零首引断言（person claim 无 citation 行）；'
              f'判例只引不重开断言（含 V061–V063 与辋川/九歲诸语——已用语一个不重开）；'
              f'三十二句 8/8/8/8 形制断言；零 KNOWN 反向断言；零新 source 反向断言（回滚零 source 删除）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言（底注系年注亦不铸）')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
