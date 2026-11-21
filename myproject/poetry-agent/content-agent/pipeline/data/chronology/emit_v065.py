#!/usr/bin/env python3
"""阶段 D 第 46 首：生成 V065——王維《洛陽女兒行》(work-t300-061, V018 已立) 四层背景。

「为什么写」走到**闺阁三词在史部全是受害者的身份**（同字两界第十形态·
闺阁形态首见；V056 泪/V057 已矣/V058 琴·流水/V059 故鄉/V060 閉關/V061 王孫/
V062 長策·解帶/V063 梓州/V064 桃源之后）：**「詩有碧玉，史部碧玉是奪死之妾；
詩有狂夫，史部狂夫是諫君之夫；詩有良人，史部良人是掠賣之身」**——

通鉴「洛陽女兒」「女兒行」「越女」「浣紗」「季倫」「石崇」「珊瑚」「九微」
「七香車」「趙李」「繁華」「西施」全零（诗的世界不进史部）；而三个闺阁词恰在史部：
「**碧玉**」恰二（同卷同案两处，闭域+窗口入引）——則天順聖皇后神功元年
（丁酉，六九七）喬知之「有美妾曰碧玉……武承嗣藉以教諸姬，遂留不還……
碧玉赴井死」：**史部碧玉是被权贵夺走后投井的妾；诗「自憐碧玉親教舞」的碧玉
是自己教舞的主人**。「**狂夫**」恰二（闭域+双窗口入引）——武德九年（丙戌，六二六）
「萬一有狂夫竊發」、貞觀八年（甲午，六三四）「狂夫之言，聖人擇焉」：
**史部狂夫是直谏者的自谦；诗「狂夫富貴在青春」的狂夫是娇贵的夫婿**。「**良人**」
恰六（闭域；tj-209/237/255 三处落在零年标题 50% 页只入闭域——50% 页永不入围窗口
三连实例）——咸通十年（己丑，八六九）「朝廷唯誅逆黨，不傷良人」入引：
**史部良人是良家身份（掠賣/贖身的户口范畴）；诗「良人玉勒乘驄馬」的良人
是丈夫的称呼**——**同一个词，史部记受害者身份，诗记闺阁的自主**。

诗题侧新亮点：「**綠珠**」通鉴恰一处=喬知之「作《綠珠怨》詩以寄之」——
**诗题《綠珠怨》以案件证据（裙帶得詩）进史部（系列首见）**：
《桃源行》整个世界不进史部，《綠珠怨》以罪证进史部——诗题进史部的通道是刑案；
而《洛陽女兒行》诗题通鉴全零、全唐詩恰 2 自名。

PERSON 层**满传逐句扫描后唯一零域句**：新传「**停筆而化。贈秘書監。**」——
诗以「妝成秪是薰香坐」收束（一生闲静），传以「停筆而化」收束（一生到写为止）。
底注尾巴「時年十六，一作十八。」=**系年注带异说双案首见（第六形态）**：
岁数注（V064）与一作案（V061）首次合体一句，两个候选岁数照登皆不采信。

20 句七古 shape：四层各绑 5 句（**5/5/5/5 首次**）。
正文第二引上限用满第十三例（V018 归一形一引在先，双针「洛陽女兒對門居」
「貧賤江頭自浣紗」各恰一处）。零新源（卷125 五连复用：V037/V055/V057/V064 已立）。

用法: python3 -I emit_v065.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/洛陽女兒行.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
V125 = pathlib.Path('/tmp/src-dl/quantangshi/vol125.txt').read_text(encoding='utf-8')
TJ192 = pathlib.Path('/tmp/src-dl/tongjian/tj-192.txt').read_text(encoding='utf-8')
TJ194 = pathlib.Path('/tmp/src-dl/tongjian/tj-194.txt').read_text(encoding='utf-8')
TJ206 = pathlib.Path('/tmp/src-dl/tongjian/tj-206.txt').read_text(encoding='utf-8')
TJ251 = pathlib.Path('/tmp/src-dl/tongjian/tj-251.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 洛陽女兒行', '| title    = 洛陽女兒行', 'ws header title(乐府题面)')
WS_NOTE = slice_between(WS,
                        '| notes    = {{Textquality|75%}}↑ [[全唐詩/卷125#洛陽女兒行|全唐詩·卷125]] 時年十六，一作十八。',
                        '一作十八。',
                        'ws 页底注(75%+全锚+尾巴系年注带异说双案「時年十六，一作十八。」首见——第六形态)')
WS_CAT1 = slice_between(WS, '[[Category:唐詩]]', '[[Category:唐詩]]', 'ws 分类行一(唐詩;V048 判例)')
WS_CAT2 = slice_between(WS, '[[Category:閨怨詩]]', '[[Category:閨怨詩]]', 'ws 分类行二(閨怨詩——整理者分类)')
WS_L1 = slice_between(WS, '洛陽女兒對門居，纔可容顏十五餘。', '十五餘。', 'ws第1联(洛阳女儿对门居)')
WS_L2 = slice_between(WS, '良人玉勒乘驄馬，侍女金盤鱠鯉魚。', '鱠鯉魚。', 'ws第2联(良人玉勒——判决词入诗)')
WS_L3 = slice_between(WS, '狂夫富貴在青春，意氣驕奢劇季倫。', '劇季倫。', 'ws第5联上段(狂夫富贵——判决词入诗)')
WS_L4 = slice_between(WS, '自憐碧玉親教舞，不惜珊瑚持與人。', '持與人。', 'ws第6联(自怜碧玉亲教舞——判决词入诗)')
WS_L5 = slice_between(WS, '春窗曙滅九微火，九微片片飛花璅。', '飛花璅。', 'ws第7联(九微火——通鉴全零词)')
WS_L6 = slice_between(WS, '戲罷曾無理曲時，妝成秪是薰香坐。', '薰香坐。', 'ws第8联(收闲——PERSON 对照)')
WS_L7 = slice_between(WS, '城中相識盡繁華，日夜經過趙李家。', '趙李家。', 'ws第9联(繁华赵李——通鉴全零词)')
WS_L8 = slice_between(WS, '誰憐越女顏如玉，貧賤江頭自浣紗。', '自浣紗。', 'ws第10联(越女浣纱收束——判决词)')
XTS_CTX = slice_between(XTS, '疾甚，縉在鳳翔，作書與別，又遺親故書數幅，停筆而化。贈秘書監。',
                        '停筆而化。贈秘書監。',
                        '新传临终段上下文(裸尾「贈秘書監。」XTS 恰二·他传同赠官故不唯一——'
                        '以停筆而化唯一前文定位后取尾)')
if XTS.count('停筆而化') != 1 or XTS_CTX.count('贈秘書監。') != 1 or not XTS_CTX.endswith('贈秘書監。'):
    raise SystemExit('PERSON 首引尾锚定位失效——须重读快照')
XTS_D = '贈秘書監。'  # 满传逐句扫描后唯一零域句（V039 已引「停筆而化」零重开——引文只取追赠官尾句）
TJ_BY = slice_between(TJ206, '右司郎中馮翊喬知之有美妾曰碧玉，知之為之不昏。武承嗣藉以教諸姬，遂留不還。知之作《綠珠怨》詩以寄之，碧玉赴井死。',
                      '碧玉赴井死。',
                      '通鉴神功元年乔知之碧玉案整案(碧玉恰二同案+绿珠怨诗题入史部;窗口断言)')
TJ_KF1 = slice_between(TJ192, '萬一有狂夫竊發，出於不意', '出於不意',
                       '通鉴武德九年切谏段(狂夫史部一处——帝王安危语境;窗口断言)')
TJ_KF2 = slice_between(TJ194, '所謂狂夫之言，聖人擇焉', '聖人擇焉',
                       '通鉴贞观八年上书段(狂夫史部二处——直谏自谦;窗口断言)')
TJ_LR = slice_between(TJ251, '朝廷唯誅逆黨，不傷良人', '不傷良人',
                      '通鉴咸通十年庞勋乱城喻段(良人史部六处之一——良家身份;窗口断言)')
Q125 = slice_between(V125, '==[[洛陽女兒行]]==', '==[[洛陽女兒行]]==',
                     '卷125 本篇篇题锚点(裸名锚第三见——同名则无消歧器)')
Q125_S = slice_between(V125, '{{:洛陽女兒行}}', '{{:洛陽女兒行}}', '卷125 本篇转引桩')

# ---------- 传区间归属复验（V036 立规） ----------
_xa = XTS.find('==王維==')
_xm = re.search(r'\n==[^=\n]{1,10}==', XTS[_xa + 8:])
_seg_x = XTS[_xa:_xa + 8 + _xm.start()]
_ja = JTS.find('=王維=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
if '停筆而化。贈秘書監。' not in _seg_x:
    raise SystemExit('PERSON 首引句越出新传王维段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；四扇窗口；零标题 50% 页不入窗） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ206, TJ_BY, '神功元年')
_window(TJ192, TJ_KF1, '武德九年')
_window(TJ194, TJ_KF2, '貞觀八年')
_window(TJ251, TJ_LR, '咸通十年')
# 良人六处中三处（tj-209/237/255）落零年标题 50% 页——50% 页永不入围窗口（三连实例）
for _f50 in ('tj-209.txt', 'tj-237.txt', 'tj-255.txt'):
    if len(_HEAD.findall(pathlib.Path(f'/tmp/src-dl/tongjian/{_f50}').read_text(encoding='utf-8'))) != 0:
        raise SystemExit(f'{_f50} 不再是零年标题 50% 页——良人只入闭域的断言须重估')

# ---------- 负证机器复查（V042 立规） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：闺阁诗语全零；碧玉恰二（同卷）；狂夫恰二；良人恰六；綠珠恰一
for _w in ('洛陽女兒', '女兒行', '越女', '浣紗', '季倫', '石崇', '珊瑚', '九微',
           '七香車', '趙李', '繁華', '西施'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗的世界不进史部的判决失效，须重读')
_by = {n: t.count('碧玉') for n, t in _tjf.items() if '碧玉' in t}
if _by != {'tj-206.txt': 2}:
    raise SystemExit(f'通鉴「碧玉」分布变了（实 {_by}）——碧玉夺死之妾判决须重估')
_kf = {n: t.count('狂夫') for n, t in _tjf.items() if '狂夫' in t}
if _kf != {'tj-192.txt': 1, 'tj-194.txt': 1}:
    raise SystemExit(f'通鉴「狂夫」分布变了（实 {_kf}）——狂夫谏君之夫判决须重估')
_lr = {n: t.count('良人') for n, t in _tjf.items() if '良人' in t}
if sum(_lr.values()) != 6 or len(_lr) != 5:
    raise SystemExit(f'通鉴「良人」不再是恰 6 处五卷（实 {sum(_lr.values())}/{len(_lr)} 卷）——良人掠卖之身闭域须重估')
if sum(t.count('綠珠') for t in _tjf.values()) != 1:
    raise SystemExit('通鉴「綠珠」不再恰一处（乔知之案）——绿珠怨诗题入史部首见断言失效')
# ② 全唐詩：诗题自名+在册词闭域
if sum(t.count('洛陽女兒') for t in _qtf.values()) != 2:
    raise SystemExit('全唐詩「洛陽女兒」不再恰 2（本篇自名）——诗题自名闭域须重估')
if sum(t.count('綠珠') for t in _qtf.values()) != 0 or sum(t.count('季倫') for t in _qtf.values()) != 0 or sum(t.count('九微') for t in _qtf.values()) != 0:
    raise SystemExit('全唐詩 綠珠/季倫/九微 不再全零——诗语无同源断言失效')
# ③ ws：零标记×75% + 三百首标记恰一 + 全锚 + 系年注带异说恰一
if WS.count('{{另') or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页出现异文/注记标记——零标记×75% 正交侧断言失效（须重读快照）')
if WS.count('{{Textquality|75%}}') != 1 or WS.count('卷125#洛陽女兒行|') != 1:
    raise SystemExit('ws 页 75%/全锚结构变了——底注断言失效')
if WS.count('{{唐詩三百首}}') != 1:
    raise SystemExit('ws 页三百首标记不再是恰一（有标记页——与 V064 无标记页对照）')
if WS.count('時年十六，一作十八。') != 1:
    raise SystemExit('系年注带异说双案不再恰一——第六形态断言失效')
# ④ 两传全文负证：闺阁词全零（比前迁移的「段内零」更强，两书全文级）
for _t, _nm in ((JTS, '旧唐书'), (XTS, '新唐书')):
    for _w in ('越女', '浣紗', '碧玉', '珊瑚', '狂夫', '良人', '繁華', '季倫', '石崇', '綠珠', '女兒'):
        if _t.count(_w) != 0:
            raise SystemExit(f'「{_w}」出现在{_nm}全文——两传闺阁词全零零证失效，须重读原文')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V065')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

for _premise, _needle, _want in (
        ('本诗首句', '洛陽女兒對門居', ['V018']),
        ('本诗末句', '貧賤江頭自浣紗', ['V018']),
        ('诗名盛期句', '名盛於開元', ['V016', 'V035']),
        ('九歲屬辭句', '九歲知屬辭', ['V040']),
        ('陷贼洛阳句', '迎置洛陽', ['V026', 'V035']),
        ('辋川别墅句', '別墅在輞川', ['V035', 'V039'])):
    _prev = _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
# 三首引+PERSON 首引句必须零域（本迁移首引）；满传扫描唯一零域尾句断言
for _first, _needle in (('碧玉案', '碧玉赴井死'), ('狂夫言', '狂夫之言'), ('良人喻', '不傷良人'),
                        ('PERSON', '贈秘書監')):
    if _domain(_needle):
        raise SystemExit(f'首引前提破了：「{_needle}」（{_first}）既往有引（{_domain(_needle)}）——须重设计')
# V039 已引「停筆而化」（长引文跨行在先）——本层零重开，引文只取其尾句追赠官
if _domain('停筆而化') != ['V039']:
    raise SystemExit('「停筆而化」既往引文域不再是 [V039]——首引尾句设计须重估')
for _cand in ('維以詩名盛於開元', '九歲知屬辭', '開元九年', '尤長五言詩', '維弟兄俱奉佛',
              '別墅在輞川', '昆仲宦遊兩都', '進士擢第', '事母崔氏', '柴毁骨立', '毀幾不生',
              '待之如師友', '拂席迎之', '妻亡不再娶', '孤居三十年', '絕迹天機', '畫思入神',
              '虛左以迎', '工草隸', '年六十一', '上元初卒', '閨門友悌', '遣人迎置洛陽'):
    if not _domain(_cand):
        raise SystemExit(f'满传唯一零域句前提破了：「{_cand}」既往零引——PERSON 首引候选须重选')

BG = {
    'bg-061-scene': (
        '二十句写一个洛阳女儿的闺阁自画像：她对门而居、十五余岁（「洛陽女兒對門居，'
        '纔可容顏十五餘」）；丈夫玉勒驄馬、侍女金盤鱠魚（「良人玉勒乘驄馬，'
        '侍女金盤鱠鯉魚」）；画阁朱楼相望、红桃绿柳垂檐；罗帏送上七香车、'
        '宝扇迎归九华帐；狂夫富贵正青春，意气骄奢过石崇（「狂夫富貴在青春，'
        '意氣驕奢劇季倫」——季倫即石崇，通鉴全唐詩皆不用此名，诗径用之）；'
        '她自怜碧玉亲自教舞、不惜珊瑚持赠于人（「自憐碧玉親教舞，不惜珊瑚持與人」）；'
        '春窗曙色灭九微火（「春窗曙滅九微火」——九微灯通鉴全唐詩俱零）；'
        '戏罢不曾理曲，妆成只是薰香坐（「戲罷曾無理曲時，妝成秪是薰香坐」——'
        '全诗以闲静收束）；末以越女浣纱对照（「誰憐越女顏如玉，貧賤江頭自浣紗」）。'
        '本页 **{{另}}×0 而 Textquality 75%**——零异文标记与不完备并存'
        '（正交横截面零标记侧首录：不完备来自转录质量，非异文）；'
        '此诗正文系**第二引**：V018 一引在先，全库查重双针各恰一处，'
        '两度上限至此用满，此诗正文对后来迁移关闭。'),
    'bg-061-city': (
        '**消歧链双向之二**：ws 文件名「洛陽女兒行.txt」与卷125 锚点'
        '「==[[洛陽女兒行]]==」**两端皆裸名**（裸名形态第三见，V062/V063 之后）——'
        '全唐詩「洛陽女兒」恰 2 处即本篇自名（机器断言）：**无同名诗则无消歧器，'
        '消歧器有无本身即同名登记**（V062 判例再验）；与 V064《桃源行》'
        '两端带作者消歧恰成消歧链的两个方向。底注尾巴「時年十六，一作十八。」：'
        '**系年注带异说双案首见（第六形态）**——V052 署名异说/V055 题异/'
        'V057 一名/V061 一题两案/V064 单岁数注之后，**岁数注与一作案首次合体一句**：'
        '十六与十八两个候选作年照登皆不采信（底注系编者语非史源，'
        'audit 硬卡诗 time.span 仍零铸造）。{{唐詩三百首}} 标记恰一（有标记页，'
        '与 V064 无标记页互为有无）；底注全锚（同 V058–V064）；分类双行'
        '「唐詩+閨怨詩」系整理者动作（第二首双分类，V063 判例：非史料声明、不升格）；'
        'source-quantangshi-125 系 V037/V055/V057/V064 已立、**第五次复用零新源**。'),
    'bg-061-world': (
        '**詩有碧玉，史部碧玉是奪死之妾；詩有狂夫，史部狂夫是諫君之夫；'
        '詩有良人，史部良人是掠賣之身**（同字两界第十形态·闺阁形态首见）：'
        '「碧玉」通鉴恰二（闭域，同卷同案两处，整案入引）——則天順聖皇后神功元年'
        '（丁酉，六九七）喬知之「有美妾曰碧玉……武承嗣藉以教諸姬，遂留不還……'
        '**碧玉赴井死**」：史部碧玉是被权贵夺走后投井的妾；诗「自憐碧玉親教舞」'
        '的碧玉是自己教舞的主人。「狂夫」恰二（闭域+双窗口入引）——武德九年'
        '（丙戌，六二六）切谏「**萬一有狂夫竊發，出於不意**」、貞觀八年（甲午，六三四）'
        '上书「**所謂狂夫之言，聖人擇焉**」：史部狂夫是直谏者的自谦与帝侧的隐患；'
        '诗「狂夫富貴在青春」的狂夫是娇贵的夫婿。「良人」恰六（闭域）——咸通十年'
        '（己丑，八六九）庞勋乱城喻「**朝廷唯誅逆黨，不傷良人**」入引，'
        '另有「掠良人賣爲奴婢」「立得爲良人」诸处：史部良人是良家身份'
        '（掠賣/贖身的户口范畴）；诗「良人玉勒乘驄馬」的良人是丈夫的称呼——'
        '**同一个词，史部记受害者身份，诗记闺阁的自主**。良人六处中三处'
        '（tj-209/237/255）落在**零年标题 50% 页**——50% 页永不入围窗口断言'
        '三连实例（audit 断言该三页零标题）。「**綠珠**」通鉴恰一处=喬知之'
        '「作《綠珠怨》詩以寄之」（裙帶得詩成罪证）——**诗题以刑案证据进史部'
        '（系列首见）**：《桃源行》的仙境整个不进史部，《綠珠怨》以罪证进——'
        '诗题进史部的通道是刑案；《洛陽女兒行》诗题通鉴全零、全唐詩恰 2 自名。'
        '诗语侧在册零入引（机器断言）：越女恰 7 五卷、浣紗恰 5 四卷、珊瑚恰 17'
        '十二卷、繁華恰 7 七卷、西施恰 12 六卷、碧玉恰 12 八卷（他卷他语境）、'
        '七香車恰 4 二卷、趙李恰 2 一卷、石崇恰一（vol539）；季倫/九微/綠珠'
        '全唐詩亦全零（诗语无同源）。本层零铸造零 relation。'),
    'bg-061-person': (
        '**满传逐句扫描后唯一零域尾句首引**：新传「疾甚……停筆而化。**贈秘書監。**」——'
        '「停筆而化」V039 已引在先（零重开，本层只取追赠官尾句），篇生成时对两传逐句查重，'
        '此句零域（audit 断言其余候选域全部非空、此句零域且「停筆而化」域恰 [V039]，破即中止重设计）。\n'
        '**诗以香收，人以笔收**（读法声明，非史实）：本诗收句「妝成秪是薰香坐」'
        '（一生闲静止于坐），本传收段「停筆而化」（一生到写为止）——'
        '底注说诗成于十六（或十八）岁，传里「九歲知屬辭」（V040 在册零重开）：'
        '少年笔力早已在册，而**两传无一字记少年诗**——传记官历与陷贼（「迎置洛陽，'
        '迫以偽署」V026/V035 在册），不记闺阁。**两书全文越女/浣紗/碧玉/珊瑚/'
        '狂夫/良人/繁華/季倫/石崇/綠珠/女兒全零**（机器断言——比历篇「段内零」'
        '更强的全文级零证）：写遍闺阁的人，两《唐书》里没有一个闺阁字；'
        '两传仅存的「洛陽」只在陷贼伪署语境内（在册零重开）——**诗的洛陽是'
        '繁华之乡，传的洛陽是失节之地**（读法声明）。certainty 不覆盖任何系年，'
        '底注「時年十六，一作十八」不铸 time.span（audit 硬卡）。'),
}
CLAIMS = {
    'claim-bg-061-scene': (
        'FACT', 'LIKELY',
        '二十句全诗本文选段（{{另}}×0 而 Textquality 75%——零异文标记与不完备并存，'
        '正交横截面零标记侧首录；本页 {{別}}/{{*}}/<ref> 亦全零）；'
        '季倫（石崇字）径用——通鉴全唐詩俱不用此名（机器断言）；'
        '九微/繁华/赵李通鉴全零词入诗（照登）；'
        '全句第二引：正文 V018 text claim 一引在先（生成时全库查重双针'
        '「洛陽女兒對門居」「貧賤江頭自浣紗」各恰一处），两度上限至此用满、'
        '此诗正文对后来迁移关闭（audit 硬卡）；SCENE 引文系二十句长篇选段'
        '（八句判决词所在+首尾联），余句以 background_line 繫行。'),
    'claim-bg-061-city': (
        'FACT', 'LIKELY',
        '消歧链双向之二（ws 文件名与卷125 锚点两端皆裸名——裸名形态第三见；'
        '无同名诗则无消歧器，消歧器有无本身即同名登记，V062 判例；audit 照登硬卡'
        '裸名锚字样）；全唐詩「洛陽女兒」恰 2=本篇自名（机器断言闭域）；'
        '底注尾巴系年注带异说双案「時年十六，一作十八。」首见（第六形态：'
        '岁数注 V064 与一作案 V061 首次合体一句）——照登皆不采信为系年'
        '（编者语非史源，audit 硬卡仍零铸造）；卷125「洛陽女兒行」恰 2=锚 1+桩 1'
        '机器断言；底注全锚（同 V058–V064）；{{唐詩三百首}} 标记恰一照登；'
        '分类双行唐詩+閨怨詩照登+非史料声明+不升格（V048/V063 判例）；'
        'source-quantangshi-125 V037/V055/V057/V064 已立、第五次复用零新源；'
        '行体乐府题而无时→零铸造零 relation。'),
    'claim-bg-061-world': (
        'FACT', 'LIKELY',
        '通鉴「洛陽女兒/女兒行/越女/浣紗/季倫/石崇/珊瑚/九微/七香車/趙李/繁華/西施」'
        '全零（机器断言）；「碧玉」恰二闭域整案入引（神功元年丁酉六九七乔知之案：'
        '美妾碧玉/武承嗣留不还/碧玉赴井死——史部碧玉=夺死之妾）；「狂夫」恰二'
        '闭域双窗口入引（武德九年丙戌六二六萬一有狂夫竊發+貞觀八年甲午六三四'
        '狂夫之言聖人擇焉——史部狂夫=谏君之夫）；「良人」恰六闭域入引一句'
        '（咸通十年己丑八六九朝廷唯誅逆黨不傷良人——史部良人=掠卖之身/良家身份；'
        '三处落零年标题 50% 页 tj-209/237/255——50% 页永不入围窗口三连实例，'
        '生成时断言三页零标题）；「綠珠」恰一=《綠珠怨》诗题以裙帶得詩罪证入史部'
        '（诗题以刑案进史部首见）；同字两界第十形态·闺阁形态首见（audit 硬卡）；'
        '全唐詩越女/浣紗/珊瑚/繁華/西施/碧玉/七香車/趙李/石崇 在册零入引+'
        '季倫/九微/綠珠全唐詩亦全零（机器断言）；certainty 不覆盖任何系年，'
        '诗 time.span/event.name/written_during 零铸造零 relation（audit 硬卡）。'),
    'claim-bg-061-person': (
        'FACT', 'LIKELY',
        '满传逐句扫描后唯一零域尾句首引=新传「贈秘書監。」（「停筆而化」V039 已引零重开；生成时断言'
        '二十四候选句域全部非空、此句零域，破即中止重设计）；'
        '「诗以香收，人以笔收」「诗的洛陽是繁华之乡、传的洛陽是失节之地」'
        '「两传无一字记少年诗」均标明读法声明；九歲知屬辭（V040）、'
        '名盛於開元天寶（V016/V035）、迎置洛陽迫以偽署（V026/V035）、'
        '別墅在輞川（V035/V039）在册零重开；两书全文越女/浣紗/碧玉/珊瑚/狂夫/'
        '良人/繁華/季倫/石崇/綠珠/女兒全零（机器断言，全文级零证首用——'
        '强于历篇段内级）；certainty 不覆盖任何系年，底注双案岁数不铸 time.span。'),
}
CITATIONS = [
    ('claim-bg-061-scene', 'source-ws-t300-061',
     '页面 洛陽女兒行（二十句长篇**引文選段**——(claim,source) 主键唯一行内'
     '判决词三词所在联+首尾联共八句逐句全引、以「……」相連，余句以 background_line 繫行；'
     '全句**第二引**：正文 V018 text claim 一引在先，生成时全库查重双针恰一处，'
     '**两度上限至此用满，此诗正文对后来迁移关闭**；{{另}}/{{別}}/{{*}}/<ref> 全零而 75%；'
     '九微/繁华/赵李通鉴全零词照登）',
     join(WS_L1, WS_L2, WS_L3, WS_L4, WS_L5, WS_L6, WS_L7, WS_L8)),
    ('claim-bg-061-city', 'source-ws-t300-061',
     '页面 洛陽女兒行（header title+页底注+分类双行四段并收——底注尾巴系年注带异说'
     '双案「時年十六，一作十八。」=第六形态照登（岁数注与一作案首次合体；'
     '编者语非史源，两个候选岁数皆不采信为系年，audit 硬卡仍零铸造）；'
     '底注全锚「卷125#洛陽女兒行」（同 V058–V064）；{{唐詩三百首}} 标记恰一照登；'
     '分类双行唐詩+閨怨詩系整理者动作：非史料声明、不升格）',
     join(WS_TITLE, WS_NOTE, WS_CAT1, WS_CAT2)),
    ('claim-bg-061-city', 'source-quantangshi-125',
     '卷一百二十五·王維《洛陽女兒行》篇题锚点+转引桩（**裸名锚**——'
     '同名则无消歧器，全唐詩「洛陽女兒」恰 2=本篇自名（机器断言）；'
     '与 V064 桃源行两端作者消歧恰成消歧链两方向；卷125「洛陽女兒行」'
     '恰 2=锚 1+桩 1；源行系 V037/V055/V057/V064 已立、本迁移第五次复用零新源）',
     join(Q125, Q125_S)),
    ('claim-bg-061-world', 'source-zizhi-tongjian-events',
     '卷二百零六·神功元年（丁酉，六九七）喬知之碧玉案整案……卷一百九十二·'
     '武德九年（丙戌，六二六）狂夫竊發段……卷一百九十四·貞觀八年（甲午，六三四）'
     '狂夫之言段……卷二百五十一·咸通十年（己丑，八六九）不傷良人段'
     '（**通鉴碧玉恰二同案+狂夫恰二+良人恰六+綠珠恰一（《綠珠怨》诗题罪证入史）**：'
     '文件闭域+四处年标题窗口机器断言；良人另三处 tj-209/237/255 落零年标题 50% 页'
     '只入闭域——50% 页永不入围窗口三连实例；四段史文逐字入引为判决证据；'
     '闺阁诗语十二词通鉴全零；全唐詩在册句零入引）',
     join(TJ_BY, TJ_KF1, TJ_KF2, TJ_LR)),
    ('claim-bg-061-person', 'source-xintangshu-wenyi',
     '新唐書卷二〇二·王維临终段（追赠官尾句「贈秘書監。」——满传逐句扫描后'
     '唯一零域尾句首引（「停筆而化」V039 已引零重开）；段内传区间归属机器断言；「诗以香收，人以笔收」系读法声明'
     '非史实；九歲知屬辭/名盛開元天寶/迎置洛陽诸在册句零重开）',
     XTS_D),
]
BG_LINES = {'bg-061-scene': tuple(range(1, 6)), 'bg-061-city': tuple(range(6, 11)),
            'bg-061-world': tuple(range(11, 16)), 'bg-061-person': tuple(range(16, 21))}
BG_AUDIENCE = {'bg-061-scene': 'PRIMARY', 'bg-061-city': 'JUNIOR',
               'bg-061-world': 'SENIOR', 'bg-061-person': 'JUNIOR'}
BG_TITLES = {'bg-061-scene': '眼前：洛阳女儿的闺阁自画像',
             'bg-061-city': '这座城：两端皆裸名的消歧链',
             'bg-061-world': '这个天下：闺阁词在史部是受害者身份',
             'bg-061-person': '这个人：满传唯一零域句'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 46 首·二十句七古 5/5/5/5 首次）；史实句均有逐字引证；'
                 '系年第四十次判决（题证系列第廿八状·碧玉与良人）'
                 '「詩有碧玉，史部碧玉是奪死之妾；詩有狂夫，史部狂夫是諫君之夫；'
                 '詩有良人，史部良人是掠賣之身」——同字两界第十形态·闺阁形态首见：'
                 '通鉴碧玉恰二整案入引（神功元年丁酉六九七乔知之碧玉赴井死——'
                 '史部碧玉=夺死之妾/诗碧玉=教舞主人）+狂夫恰二双窗口入引'
                 '（武德九年丙戌六二六狂夫竊發+貞觀八年甲午六三四狂夫之言聖人擇焉'
                 '——谏君之夫/娇贵夫婿）+良人恰六闭域入引（咸通十年己丑八六九'
                 '不傷良人——掠卖之身/丈夫称呼；三处落零标题 50% 页 tj-209/237/255'
                 '三连不入窗）；綠珠恰一=《綠珠怨》诗题以罪证进史部（诗题进史部'
                 '通道是刑案，系列首见）；洛陽女兒/女兒行/越女/浣紗/季倫/石崇/'
                 '珊瑚/九微/七香車/趙李/繁華/西施通鉴全零；全唐詩越女/浣紗/珊瑚/'
                 '繁華/西施/碧玉/七香車/趙李/石崇在册零入引+季倫/九微/綠珠亦全零；'
                 '消歧链双向之二（ws 文件名+卷125 锚点两端裸名第三见+自名恰二闭域）；'
                 '底注系年注带异说双案「時年十六，一作十八。」第六形态（合体首见）'
                 '照登皆不采信（audit 硬卡仍零铸造）；{{另}}×0×75% 正交零标记侧首录；'
                 '三百首标记恰一+分类双行閨怨詩；零新源（卷125 第五次复用）；'
                 '正文第二引上限用满第十三例对后来关闭；PERSON 满传逐句扫描唯一'
                 '零域句首引（停筆而化。贈秘書監。——诗以香收人以笔收读法声明）；'
                 '两书全文闺阁十一词全零（全文级零证首用）；KNOWN 零如实记录'
                 '（第廿一例，audit 反向断言）；判例关键语零入引文。'
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
    A("""-- V065：王維《洛陽女兒行》(work-t300-061) 四层背景（阶段 D 第 46 首·碧玉与良人）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V026、V035、V037、V039、V040、V055、V057、V064 已执行
--       （work-t300-061 与其 text-work-t300-061-ws、source-ws-t300-061 是 V018 的行；
--       source-quantangshi-125 是 V037/V055/V057/V064 已立的卷125 源行（本迁移第五次复用，零新源）；
--       source-xintangshu-wenyi 是 V016 已立的新唐书文艺传源；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       判例在册句（九歲知屬辭 V040/名盛開元天寶 V016+V035/迎置洛陽迫以偽署 V026+V035/
--       別墅在輞川 V035+V039）只对照不重开）。
--       本迁移零新 source（audit 断言无诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v065.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/洛陽女兒行.txt（{{另}}×0×75%+底注全锚+尾巴系年注带异说双案+三百首标记恰一）、
--   新唐書卷202（满传逐句扫描唯一零域句首引+停筆而化传区间断言）、
--   舊唐書卷190下/新唐書卷202（两书全文闺阁十一词全零零证）、
--   全唐詩卷125（裸名锚+桩；洛陽女兒恰二自名/綠珠季倫九微全零扫描）、
--   通鑑卷192/194/206/251（碧玉恰二同案+狂夫恰二+良人恰六+綠珠恰一+四处年标题窗口+
--   tj-209/237/255 零标题断言）+ 通鑑 75 卷/全唐詩 118 卷存快照负证计数扫描
--   （洛陽女兒/女兒行/越女/浣紗/季倫/石崇/珊瑚/九微/七香車/趙李/繁華/西施/綠珠）+
--   既有迁移引文域逐句查重——传区间归属、二引/零重开/唯一零域句前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行；
--   scene 二十句长篇选段八句——判决词三词所在联+首尾联，余句 background_line 繫行；
--   32 行 background_line 改 20 行（**5/5/5/5 首次**：scene→1-5 city→6-10
--   world→11-15 person→16-20，绑 text-work-t300-061-ws 的 20 行）+ 零 poetry_source 行 + 不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span（底注「時年十六，一作十八。」亦不铸）、不写 event.name、
--   不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「詩有碧玉，史部碧玉是奪死之妾；詩有狂夫，史部狂夫是
-- 諫君之夫；詩有良人，史部良人是掠賣之身」）：
--   * 碧玉恰二整案+狂夫恰二双窗口+良人恰六闭域入引一句+綠珠恰一（40% 页三连不入窗）；
--   * 「诗以香收，人以笔收」「诗的洛陽繁华之乡/传的洛陽失节之地」「两传无少年诗」标明读法声明；
--   * 系年注带异说双案照登皆不采信（编者语非史源，audit 硬卡仍零铸造）；
--   * 裸名锚+裸名文件名照登（消歧链双向之二，同名登记 V062 判例）；
--   * 此诗正文第二引上限用满（V018 在先+双针查重各恰一处），对后来迁移关闭；
--   * 全唐詩越女/浣紗/珊瑚/繁華/西施/碧玉/七香車/趙李/石崇在册零入引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第廿一例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 九歲屬辭（V040）/名盛開元天寶（V016/V035）/迎置洛陽（V026/V035）判例只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 64，不含 65
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-061-%';             -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-125';     -- 恰 1（四迁移已立，本迁移复用不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-061-ws';  -- 恰 20
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-061-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-061';                                  -- 20（5/5/5/5）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-061-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-061'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-061';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-061-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-quantangshi-125';  -- 恰 1（复用，非本迁移所立）
-- 回滚: recovery/V065_rollback.sql（按 id 全枚举删除；零 source 删除——卷125 源行为四迁移所立）
START TRANSACTION;""")

    A('\n-- ---------- 1. 零新 source（卷125 源行四迁移已立，本迁移第五次复用） ----------')

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
    brows = [{'id': k, 'work_id': 'work-t300-061',
              'layer': {'bg-061-scene': 'SCENE', 'bg-061-city': 'CITY',
                        'bg-061-world': 'WORLD', 'bg-061-person': 'PERSON'}[k],
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

    A('\n-- ---------- 6. background_line（二十句七古 5/5/5/5 首次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-061-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 7. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 65, 'Wang Wei''s Ballad of the Daughters of Luoyang (work-t300-061) background layers (stage-D poem 46, twenty-line geyue quintet 5/5/5/5 first time): dating verdict forty, twenty-eighth shape of the title-evidence series -- bishi and liangren, the boudoir words split in two realms: the poem''s bishi (green jade) is a wife who teaches her own dances; the Tongjian''s bishi (exactly 2, one case, quoted whole) is Qiao Zhizhi''s beautiful concubine taken by Wu Chengsi, who "went and threw herself into the well" (Shenggong 1st year, dingyou, 697); the poem''s kuangfu ("mad husband") is her pampered young spouse; the Tongjian''s kuangfu (exactly 2, windowed, quoted) is a censor''s self-deprecation -- "the words of a mad man" for the sage to weigh (Zhenguan 8th, jiawu, 634) and a feared stray shot near the emperor (Wude 9th, bingxu, 626); the poem''s liangren ("good man") is the polite word for husband; the Tongjian''s liangren (exactly 6, one quoted) is commoner status bought, sold and pardoned -- "the court punishes only the rebels, it will not harm the good" (Xiantong 10th, jichou, 869): one word, the histories record victims'' statuses, the poem records a wife''s agency (the tenth same-character split, first boudoir shape); liuren''s other three hits sit on heading-less 50%-pages tj-209/237/255 (triple instance of the 50%-page window ban, asserted at build); lüzhu appears exactly once -- Qiao''s poem-title "Lament of the Green Pearl", seized from her sash and used as execution evidence: a poem title enters the histories by way of a criminal case (first in the series); luoyang-nver/daughter-ballad/Yue-woman/launders silk/Jilun/Shi Chong/coral/jiawei/seven-fragrance carriage/Zhao-and-Li/splendour/Xishi score zero across the Tongjian; on the poetry side logged never quoted (machine-asserted); the disambiguation chain runs bare-name on both ends for the third time (ws filename + juan 125 bare anchor; luoyang-nver counts exactly 2 = self-naming); the base-note tail is a dating gloss with its own variant: "written at sixteen, alternatively at eighteen" (sixth form, first merger of the age-gloss and the one-said variant) -- both ages logged, neither promoted to chronology (audit hard-assert); zero 另 markers with 75% (orthogonality''s zero-marker side, first); the 三百首 marker present exactly once; paired category rows (唐詩+閨怨詩) per V048/V063; zero new sources (juan 125''s row reused for the fifth time); body quotes hit their two-use ceiling (V018 first, twin needles); PERSON first-cite is the single zero-domain tail sentence left after a sentence-by-sentence scan of both biographies -- "posthumously made Secretary Supervisor" ("he set down the brush and passed away" was cited by V039 and stays unquoted) (build-time asserts all 24 other candidates non-empty, this one empty): the poem ends in incense, the man ends in writing; both full histories contain none of eleven boudoir words (whole-book zero, stronger than the per-segment zero of earlier migrations); KNOWN zero honestly recorded (twenty-first instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 65);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V065 精确回滚：只删 V065 插入的行（id 全枚举）。零 source 删除：',
         '-- source-quantangshi-125 是 V037/V055/V057/V064 已立的卷125 源行（本迁移第五次复用），绝不删；',
         '-- work-t300-061 本体、其 text_line 20 行与 source-ws-t300-061 都是 V018 的行，绝不删；',
         '-- source-xintangshu-wenyi / source-zizhi-tongjian-events 为他迁移所立，零删除。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 65;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_NOTE, WS_CAT1, WS_CAT2,
              WS_L1, WS_L2, WS_L3, WS_L4, WS_L5, WS_L6, WS_L7, WS_L8,
              TJ_BY, TJ_KF1, TJ_KF2, TJ_LR, Q125, Q125_S, XTS_D]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 底注全锚 + 系年注带异说 + 题行照登硬卡（CITY ws 引文）
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-061-city' and s == 'source-ws-t300-061')
    if '卷125#洛陽女兒行|' not in city_ws:
        bad.append('底注全锚未逐字入 CITY 引文（全锚形态照登硬卡）')
    if '時年十六，一作十八。' not in city_ws:
        bad.append('系年注带异说双案未逐字入 CITY 引文（第六形态照登硬卡）')
    if '閨怨詩' not in city_ws or 'Category:唐詩' not in city_ws:
        bad.append('分类双行未逐字入 CITY 引文（閨怨詩照登硬卡）')
    if '不采信' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-061-city' and s == 'source-ws-t300-061'):
        bad.append('CITY ws locator 须含「不采信」（双案岁数不升格断言失效）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-061-city' and s == 'source-ws-t300-061'):
        bad.append('CITY ws locator 须含「非史料」声明（分类行三重断言失效）')
    # 裸名锚照登硬卡
    city_q = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-061-city' and s == 'source-quantangshi-125')
    if '==[[洛陽女兒行]]==' not in city_q:
        bad.append('裸名锚点未逐字入 CITY 引文（消歧链双向之二照登硬卡）')
    # SCENE 第二引上限声明硬卡
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-061-scene' and s == 'source-ws-t300-061')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054–V064 同款硬卡）')
    # WORLD：四段史文必须在引文内（判决证据）；诗语零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-061-world')
    for tok in ('碧玉赴井死', '狂夫竊發', '狂夫之言', '不傷良人', '綠珠怨'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（碧玉/狂夫/良人/綠珠怨必须入引）')
    for tok in ('洛陽女兒', '越女', '浣紗', '珊瑚', '妝成', '薰香', '九微火', '趙李家'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文）')
    # PERSON 首引尾句必须在引文内（「停筆而化」V039 已引零重开，不得入本层引文）
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-061-person')
    if '贈秘書監' not in p_ex:
        bad.append('PERSON 引文缺首引要素「贈秘書監」（唯一零域尾句照登硬卡）')
    if '停筆而化' in p_ex:
        bad.append('「停筆而化」V039 已引零重开，不得入本层引文')
    for c, s, _, ex in CITATIONS:
        if not s.startswith('source-ws-t300-'):
            for w in ('謫仙', '脫靴', '賜金放還', '宮錦袍', '夜郎', '山東人'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
    # 判例只引不重开（引文域全扫；不含本迁移三首引词）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山', '隠鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒', '刻碑鳳林山南',
                '仕疾徑', '茶鐺', '事母崔氏', '解官以贖',
                '柴毁骨立', '毀幾不生', '大招權利', '車如流水馬如龍',
                '歴右拾遺', '天寳末，為給事中', '或牒歸故鄉', '見郭子儀',
                '昆仲宦遊兩都', '輞口', '藍田别墅', '下馬飲君酒', '歸臥南山陲',
                '白雲無盡', '服闋，拜吏部郎中', '隱於嵩山之陽', '閉關以拒之',
                '殺郡王', '雲南王孫', '春草未生', '今宵歸不歸',
                '山中相送罷', '日暮掩柴扉', '一作山中送別',
                '聚斂為長策', '脫巾解帶', '解帶繫頸', '議者不之罪',
                '晚年唯好靜', '漁歌入浦深', '貶晙為梓州刺史', '段子璋反',
                '參天可汗道', '火炬於樹杪', '九歲知屬辭', '別墅在輞川', '華子岡',
                '版圖墮於避地', '避地江左', '龍陽江漲', '仙源公主',
                '迎置洛陽', '普施寺', '凝碧'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 二十句七古 5/5/5/5 首次
    if {k: len(v) for k, v in BG_LINES.items()} != {k: 5 for k in BG}:
        bad.append('二十句 background_line 须每层恰 5（5/5/5/5）')
    if sorted(n for seqs in BG_LINES.values() for n in seqs) != list(range(1, 21)):
        bad.append('5/5/5/5 须覆盖 1-20 句各一次')
    if len(re.findall(r"text-work-t300-061-ws' AS version_id", sql)) != 20:
        bad.append('bg_line INSERT 的 version 行数应为 20')
    # 零新 source（断言文案也不得出现该字面量）
    if 'INSERT INTO poetry_' + 'source' in sql:
        bad.append('V065 有意零新 source，但 SQL 里出现了诗源表新建插入语句')
    # 版本账本 INSERT 必须含 version_no=65 反查守卫
    vblk = sql[sql.index('INSERT INTO poetry_schema_version'):]
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 65)' not in vblk:
        bad.append('poetry_schema_version 的 INSERT 缺 version_no=65 幂等守卫')
    if 'DELETE FROM poetry_source' in build_rollback():
        bad.append('回滚不得删任何 source 行（卷125 源行为四迁移所立）')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V065 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V065 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-061' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V065 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-061' AS subject_id" in sql:
        bad.append('V065 的 claim 主语应全部是 bg-061-*，work-t300-061 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V065 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '閨閣形态首见' not in body_all and '闺阁形态首见' not in body_all:
        bad.append('BG 须含「闺阁形态首见」（同字两界第十形态）声明')
    if '掠賣之身' not in ''.join(BG.values()):
        bad.append('BG/WORLD 须含「史部良人是掠賣之身」判决声明')
    if '第六形态' not in body_all:
        bad.append('BG/CITY 须含「第六形态」（系年注带异说）声明')
    if '唯一零域句' not in body_all:
        bad.append('BG/PERSON 须含「唯一零域句」首引声明')
    if '50% 页永不入围' not in body_all:
        bad.append('BG/WORLD 须含「50% 页永不入围窗口」三连断言声明')
    if '诗题' not in body_all or '刑案' not in body_all:
        bad.append('BG/WORLD 须含「诗题以刑案进史部」系列首见声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 20 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（新传王维段唯一零域句）；'
              f'四处年标题窗口断言（神功元年六九七/武德九年六二六/貞觀八年六三四/咸通十年八六九）'
              f'+tj-209/237/255 三页零年标题断言（50% 页永不入围窗口三连实例）；'
              f'负证机器复查五层（通鉴洛陽女兒/女兒行/越女/浣紗/季倫/石崇/珊瑚/九微/'
              f'七香車/趙李/繁華/西施全零+碧玉恰二同卷(tj-206)+狂夫恰二(tj-192/194)+'
              f'良人恰六五卷+綠珠恰一/全唐詩洛陽女兒恰二自名+綠珠季倫九微全零/'
              f'ws 零标记×75%+三百首恰一+全锚+系年注带异说恰一/'
              f'两书全文闺阁十一词全零，快照变动即中止）；'
              f'前提全库查重硬卡六件+四首引句零域断言+满传二十四候选句域全非空断言；'
              f'底注全锚+時年十六一作十八双案+题行+分类双行+裸名锚照登硬卡；'
              f'CITY「不采信/非史料」硬卡；SCENE 第二引/上限硬卡；'
              f'碧玉狂夫良人绿珠怨入引+诗语零混入断言；PERSON 首引句入引硬卡；'
              f'判例只引不重开断言（含 V064 桃源诸语与陷贼洛阳语——已用语一个不重开）；'
              f'二十句 5/5/5/5 形制断言；零 KNOWN 反向断言；零新 source 反向断言'
              f'（回滚零 source 删除）；(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言（双案岁数注亦不铸）')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
