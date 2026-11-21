#!/usr/bin/env python3
"""阶段 D 第 48 首：生成 V067——李商隱《隋宮》(work-t300-022, V018 已立) 四层背景。

**本迁移再新建 1 个 source（source-ws-t300-022）——连续第二首开新源**：V018 当时
以全唐詩卷539 卷页（source-quantangshi-539，version_code vol-raw）立本诗正文，
ws《唐詩三百首》诗页（页题带首句消歧「隋宮 (乘興南遊不戒嚴)」）从未建源——
与 V066《賈生》同构：卷页与诗页是两个独立见证面（ledger 145→146，
audit 断言恰一枚新源 INSERT、回滚按 id 删且只删此行）。

「为什么写」走到**亡国两界**（同字两界第十二形态·亡国形态首见）：
**「诗题隋宮在史部全零，亡隋只在谏臣嘴里；诗的谏书函九重不省，
史的谏书从叛家开箱反得赏」**——

通鉴「隋宮/南遊/不戒嚴/乘興/宮錦/障泥/紫泉/蕪城(诗面)/螢火/垂楊/迷樓/錦帆/
隋堤/日角/省諫」全零（隋炀帝南游这场亡国戏的诗面整个不在史部）；而
「**亡隋**」恰二（闭域+双窗口逐字入引）：貞觀四年（庚寅，六三〇）「陛下役
瘡痍之人，襲亡隋之弊，恐又甚於煬帝矣！」（洛阳宫营缮之谏）、貞觀十二年
（戊戌，六三八）「卿所為乃亡隋之弊俗也。」（长春宫供进之责）——**史部的
亡隋是谏臣手里的镜子（以亡为诫），诗的隋宮是锦帆未断的现场**；
「**諫書**」通鉴恰一处（闭域+窗口入引）——貞觀十七年（癸卯，六四三）齐王
祐乱平，「上檢祐家文疏，得記室郟城孫處約諫書，嗟賞之，累遷中書舍人」——
**诗「九重誰省諫書函」是写给不见省的九重；史部这封唯一进账的谏书，是皇帝
从叛臣箱底翻出来的，人还因此升了官——一函不省，一函得赏**；「**戒嚴**」恰十
处七卷闭域（全库扫描，全部军制急备在册零入引）——**诗偏偏只咬这一个词的
否定式「不戒嚴」：史部戒嚴是万乘之防，诗不戒嚴是乘兴之君**；「行留」恰一
（贞观元年邸怀道对：「煬帝將幸江都，召百官問行留之計……獨言不可。臣親見之」
入引）——**炀帝行幸当时真有人说过「不可」，且真有一个亲历者二十年后在朝堂
上讲给太宗听：省不省之间，通鉴留的是亲历者的声音**。

卷539 侧（CITY 层核心）：**同卷同题双《隋宮》**——「==[[隋宮]]==」恰二
（机器断言闭域）：前块紫泉七律（「紫泉宮殿鎖煙霞　欲取蕪城作帝家……」，
全唐诗名篇而**不入三百首**）、后块本篇乘興七绝+**「{{*|一云隋堤}}」异注行**
——**同名两见两锚皆裸名：消歧判例反例首见**（V059/V062–V065「无同名则无
消歧器」的反面——**有同名，锚仍裸名**，辨异全靠第二块孤挂的一行云注：
裸名锚不能自我消歧，本卷同名只能靠异注与选本各立一页）；ws 层同名两页
各以首句消歧（「隋宮 (乘興南遊不戒嚴)」）——**卷页裸名/诗页消歧的分层
消歧形态首见**；异注同variant两层照登：卷页简体「一云隋堤」vs ws 页
繁体「一雲隋堤」（title 行内嵌 {{*|}}——**异注进 title 行首见**）。
ws 诗页**poem 块四句全无句读**（对照 V066《賈生》页 poem 有标点——
**同一选本两种转录形态并存首见**）；无 Textquality 评级第二见（V066 首见）；
notes「{{唐詩三百首}}七绝」——**选本标记后挂诗体俗名「七绝」（不标「七言絕句」
正名）首见**；分类三行简繁混排第二见。全唐詩「隋宮」恰六处四卷闭域
（283/525 他人同题在册）+卷540《隋宮守歲》第三面（档扫闭域）——
**「隋宮」二字在《全唐詩》里活着，在《通鑑》里死了（全零），死而复活于谏语**。

PERSON 层：旧传李商隐段（简化字录入）再首引二句（皆零域）——「**商隐幼能
为文。令狐楚镇河阳，以所业文干之，年才及弱冠。**」「**博学强记，下笔不能自休，
尤善为诔奠之辞。**」：诗的谏书函无人省，人的所业文有人赏（弱冠即干谒得礼）——
**「下笔不能自休」的手，写进宫门的就是「誰省」二字**（读法声明）；V066 已引
「绹不之省」「名宦不进，坎壈终身」零重开（域恰 ['V066'] 断言）；
段内隋/煬/九重/諫/戒嚴/揚州/江都全零（机器断言）。

4 句七绝 shape：1/1/1/1 第四次（V056/V061/V066 之后）。
正文第二引上限用满第十五例（V018 卷539 一引在先，双针各恰一处——两引面不重叠）。

用法: python3 -I emit_v067.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/隋宮__乘興南遊不戒嚴_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
V539 = pathlib.Path('/tmp/src-dl/quantangshi/vol539.txt').read_text(encoding='utf-8')
V540 = pathlib.Path('/tmp/src-dl/quantangshi/vol540.txt').read_text(encoding='utf-8')
TJ192 = pathlib.Path('/tmp/src-dl/tongjian/tj-192.txt').read_text(encoding='utf-8')
TJ193 = pathlib.Path('/tmp/src-dl/tongjian/tj-193.txt').read_text(encoding='utf-8')
TJ195 = pathlib.Path('/tmp/src-dl/tongjian/tj-195.txt').read_text(encoding='utf-8')
TJ196 = pathlib.Path('/tmp/src-dl/tongjian/tj-196.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 隋宮{{*|一雲隋堤}}', '| title    = 隋宮{{*|一雲隋堤}}',
                         'ws header title(title 行内嵌 {{*|一雲隋堤}} 异注——异注进 title 行首见)')
WS_AUTHOR = slice_between(WS, '| author   = 李商隱', '| author   = 李商隱', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '| notes    = {{唐詩三百首}}七绝', '| notes    = {{唐詩三百首}}七绝',
                        'ws 页底注(选本标记后挂诗体俗名「七绝」首见;全无 Textquality 评级)')
WS_CAT = slice_between(WS, '[[Category:李商隱]]', '[[Category:唐詩三百首|李]]',
                       'ws 分类三行连片(第三行简体「唐诗」与第四行繁体「唐詩三百首」同页混排第二见)')
WS_BODY = slice_between(WS, '乘興南遊不戒嚴\n九重誰省諫書函', '半作障泥半作帆\n</poem>',
                        'ws 页 poem 块四句(全无句读——与《賈生》页有标点并存;第二引)')
V539_ZQ = slice_between(V539, '==[[隋宮]]==\n<poem>\n紫泉宮殿鎖煙霞', '欲取蕪城作帝家',
                        '卷539 前块紫泉七律(同卷同题第一锚——裸名;不入三百首名篇)')
V539_CX = slice_between(V539, '==[[隋宮]]==\n{{*|一云隋堤}}', '半作障泥半作帆\n</poem>',
                        '卷539 后块本篇七绝(同卷同题第二锚——裸名;孤挂 {{*|一云隋堤}} 异注行)')
TJ_XJD = slice_between(TJ192, '煬帝將幸江都，召百官問行留之計，懷道為吏部主事，獨言不可。臣親見之。',
                       '臣親見之。',
                       '通鉴贞观元年邸怀道对(炀帝幸江都行留之议唯一处——独言不可+亲见之;窗口断言)')
TJ_WS1 = slice_between(TJ193, '陛下役瘡痍之人，襲亡隋之弊，恐又甚於煬帝矣！', '甚於煬帝矣！',
                       '通鉴贞观四年洛阳宫营缮谏(亡隋史部一处——以亡为诫的镜子;窗口断言)')
TJ_WS2 = slice_between(TJ195, '卿所為乃亡隋之弊俗也。', '亡隋之弊俗也。',
                       '通鉴鉴贞观十二年长春宫供进之责(亡隋史部二处;窗口断言)')
TJ_JS = slice_between(TJ196, '上檢祐家文疏，得記室郟城孫處約諫書，嗟賞之，累遷中書舍人。',
                      '累遷中書舍人。',
                      '通鉴贞观十七年齐王祐乱平开箱得谏书(谏书通鉴唯一处——一函得赏;窗口断言)')
JTS_P1 = slice_between(JTS, '商隐幼能为文。令狐楚镇河阳，以所业文干之，年才及弱冠。', '年才及弱冠。',
                       '旧传李商隐段(弱冠以所业文干谒得礼——与诗「谁省」对;PERSON 首引)')
JTS_P2 = slice_between(JTS, '博学强记，下笔不能自休，尤善为诔奠之辞。', '诔奠之辞。',
                       '旧传李商隐段(下笔不能自休——写进宫门的是「谁省」;PERSON 首引)')

# ---------- 传区间归属复验（V036 立规；段界 ==弟 羲叟==） ----------
_ja = JTS.find('=李商隱=')
_jm = re.search(r'\n==[^=\n]{1,12}==', JTS[_ja + 8:])
_seg_j = JTS[_ja:_ja + 8 + _jm.start()]
for _needle in (JTS_P1, JTS_P2):
    if _needle not in _seg_j:
        raise SystemExit('PERSON 首引句越出旧传李商隐段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；四扇窗口） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ192, TJ_XJD, '貞觀元年')
_window(TJ193, TJ_WS1, '貞觀四年')
_window(TJ195, TJ_WS2, '貞觀十二年')
_window(TJ196, TJ_JS, '貞觀十七年')

# ---------- 负证机器复查（V042 立规） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：诗面词全零；亡隋恰二；谏书/行留/幸江都恰一；戒嚴恰十分布七卷
for _w in ('隋宮', '南遊', '不戒嚴', '乘興', '宮錦', '障泥', '紫泉', '螢火', '垂楊',
           '迷樓', '錦帆', '隋堤', '日角', '省諫'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗面亡国现场不进史部的判决失效，须重读')
_ws2 = {n: t.count('亡隋') for n, t in _tjf.items() if '亡隋' in t}
if _ws2 != {'tj-193.txt': 1, 'tj-195.txt': 1}:
    raise SystemExit(f'通鉴「亡隋」分布变了（实 {_ws2}）——亡隋只在谏臣嘴里判决须重估')
for _w, _want in (('諫書', {'tj-196.txt': 1}), ('行留', {'tj-192.txt': 1}), ('幸江都', {'tj-192.txt': 1})):
    _d = {n: t.count(_w) for n, t in _tjf.items() if _w in t}
    if _d != _want:
        raise SystemExit(f'通鉴「{_w}」不再是恰一处（实 {_d}）——一函得赏/行留独言判决须重估')
_jj = {n: t.count('戒嚴') for n, t in _tjf.items() if '戒嚴' in t}
if sum(_jj.values()) != 10 or len(_jj) != 7:
    raise SystemExit(f'通鉴「戒嚴」不再恰 10 处七卷（实 {sum(_jj.values())}）——万乘之防对乘兴之君判决须重估')
if _alltj.count('後庭花') != 1:
    raise SystemExit('通鉴「後庭花」不再恰一——在册闭域须重估')
# ② 全唐诗：隋宮恰六处四卷闭域；卷539 内部计数；卷540 守歲第三面
_qg = {name: t.count('隋宮') for name, t in sorted(_qtf.items()) if '隋宮' in t}
if _qg != {'vol283.txt': 2, 'vol525.txt': 1, 'vol539.txt': 2, 'vol540.txt': 1}:
    raise SystemExit(f'全唐詩「隋宮」分布变了（实 {_qg}）——同题在册闭域须重估')
if V539.count('==[[隋宮]]==') != 2 or V539.count('{{*|一云隋堤}}') != 1:
    raise SystemExit('卷539 同题双锚/异注行结构变了——消歧反例判决失效')
for _w in ('紫泉宮殿鎖煙霞', '欲取蕪城作帝家', '乘興南遊不戒嚴', '半作障泥半作帆', '諫書', '宮錦', '障泥'):
    if V539.count(_w) != 1:
        raise SystemExit(f'卷539「{_w}」不再恰一——同卷双块闭域失效')
if V540.count('==隋宮守歲==') != 1:
    raise SystemExit('卷540《隋宮守歲》锚不再恰一——「隋宮」第三面闭域须重估')
# ③ ws：无评级 + {{*}} 只在 title 行 + poem 无句读 + 双转录
if WS.count('{{Textquality') != 0:
    raise SystemExit('ws 页出现 Textquality 评级——无评级页第二见断言失效')
if WS.count('{{*|') != 1 or WS.count('{{另') or WS.count('{{別') or WS.count('<ref'):
    raise SystemExit('ws 页标记结构变了（{{*}} 应恰一枚在 title 行且零另/別/ref）')
if '半作障泥半作帆。' in WS or '乘興南遊不戒嚴，' in WS:
    raise SystemExit('ws poem 块出现句读——poem 无标点首见断言失效')
if WS.count('乘興南遊不戒嚴') != 2 or WS.count('半作障泥半作帆') != 2:
    raise SystemExit('ws 页 Vtext/poem 双转录结构变了（首末句页内应各恰 2）')
if WS.count('| notes    = {{唐詩三百首}}七绝') != 1:
    raise SystemExit('ws 页 notes「七绝」俗名结构变了——首见断言失效')
_cat = '[[Category:李商隱]]\n[[Category:唐诗]]\n[[Category:唐詩三百首|李]]'
if WS.count(_cat) != 1:
    raise SystemExit('ws 页分类三行连片结构变了（简繁混排第二见断言失效）')
# ④ 旧传李商隐段负证：诗面字全零（段级）
for _w in ('隋', '煬', '九重', '諫', '戒嚴', '揚州', '江都'):
    if _seg_j.count(_w) != 0:
        raise SystemExit(f'「{_w}」落在旧传李商隐段——传不涉隋宫事负证失效，须重读原文')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V067')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

for _premise, _needle, _want in (
        ('本诗首句', '乘興南遊不戒嚴', ['V018']),
        ('本诗末句', '半作障泥半作帆', ['V018']),
        ('V066 不之省句', '绹不之省', ['V066']),
        ('V066 坎壈断', '坎壈终身', ['V066']),
        ('义山署名句', '李商隐，字义山', ['V016'])):
    _prev = _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
if _domain('source-quantangshi-539') != ['V018']:
    raise SystemExit('source-quantangshi-539 域非恰 [V018]——本迁移复用对象须重估')
# 首引句必须零域；新源 id 必须全库不存在（确系 V018 未建）
for _first, _needle in (('紫泉块', '紫泉宮殿鎖煙霞'), ('简体云堤注', '一云隋堤'),
                        ('繁体雲堤注', '一雲隋堤'), ('行留对', '煬帝將幸江都'),
                        ('袭弊谏', '襲亡隋之弊'), ('弊俗责', '亡隋之弊俗'),
                        ('开箱谏书', '孫處約諫書'), ('弱冠干文', '以所业文干之'),
                        ('不自休断', '下笔不能自休')):
    if _domain(_needle):
        raise SystemExit(f'首引前提破了：「{_needle}」（{_first}）既往有引（{_domain(_needle)}）——须重设计')
if _domain('source-ws-t300-022'):
    raise SystemExit('source-ws-t300-022 已存在于既往迁移——本迁移不再新建源，设计须改')

BG = {
    'bg-022-scene': (
        '四句是一次没有刹车的人间巡幸：乘兴南游，连戒严都不要（「乘興南遊不戒嚴」）——'
        '皇帝尽兴出发，警卫仪程一概从简；九重宫门里，谁省得谏书的封皮（「九重誰省諫書函」）；'
        '春风里全国裁下来的宫锦，一半做了障泥、一半做了帆（「春風舉國裁宮錦，'
        '半作障泥半作帆」）——锦缎不是穿在人身上，是垫在马蹄下、挂在船帆上。'
        'ws 诗页 poem 块**四句全无句读**（对照 V066《賈生》页 poem 有标点——'
        '**同一《唐詩三百首》选本两种转录形态并存首见**，各从其录照登）；'
        'title 行内嵌 {{*|一雲隋堤}} 异注——**异注进 title 行首见**；'
        '{{另}}/{{別}}/<ref> 全零；页内 Vtext/poem 双转录并存（首末句页内各恰 2）。'
        '此诗正文系**第二引**：V018 卷539 卷页一引在先，本迁移引 ws 选本页——'
        '**两引两面（卷页+诗页），上限恰满而不重叠**；生成时全库查重双针各恰一处，'
        '两度上限至此用满，此诗正文对后来迁移关闭。'),
    'bg-022-city': (
        '卷539 侧：**同卷同题双《隋宮》**——「==[[隋宮]]==」恰二（机器断言闭域）：'
        '前块「紫泉宮殿鎖煙霞　欲取蕪城作帝家……」七律（全唐诗名篇而不入三百首），'
        '后块本篇七绝，锚下**孤挂「{{*|一云隋堤}}」异注行**——'
        '**同名两见两锚皆裸名：消歧判例反例首见**（V059「无同名则无消歧器」、'
        'V062/V063/V065 裸名锚诸判例的反面：**有同名，锚仍裸名**——辨异全靠第二块'
        '孤挂的一行云注；裸名锚不能自我消歧，本卷同名只靠异注与选本各立一页分家）。'
        'ws 层同名两页各以首句消歧（本页页题「隋宮 (乘興南遊不戒嚴)」）——'
        '**卷页裸名/诗页消歧的分层消歧形态首见**；异注同案两层照登：卷页简体'
        '「一云隋堤」vs ws 页繁体「一雲隋堤」。ws 页 notes「{{唐詩三百首}}七绝」——'
        '**选本标记后挂诗体俗名「七绝」（非「七言絕句」正名）首见**；无 Textquality '
        '评级第二见（V066 首见）；分类三行简繁混排第二见（整理者分类：非史料声明、'
        '不升格，V048 判例）。**本迁移再新建 1 个 source（source-ws-t300-022）**——'
        '连续第二首开新源：V018 以卷539 卷页立本诗（source-quantangshi-539，vol-raw），'
        'ws 选本页从未建源——卷页与诗页两个独立见证面（V066 判例同构）。'
        '全唐詩「隋宮」恰六处四卷闭域（283/525 他人同题在册零入引）+卷540'
        '《隋宮守歲》锚恰一（「隋宮」二字第三面，档扫闭域）。（本层零 relation。）'),
    'bg-022-world': (
        '**诗题隋宮在史部全零，亡隋只在谏臣嘴里**（同字两界第十二形态·亡国形态'
        '首见）：通鉴「隋宮/南遊/不戒嚴/乘興/宮錦/障泥/紫泉/螢火/垂楊/迷樓/錦帆/'
        '隋堤/日角/省諫」全零（机器断言——锦帆未断的亡国现场整个不在史部）；'
        '「**亡隋**」恰二（闭域+双窗口逐字入引）：貞觀四年（庚寅，六三〇）'
        '「**陛下役瘡痍之人，襲亡隋之弊，恐又甚於煬帝矣！**」（洛阳宫营缮之谏）、'
        '貞觀十二年（戊戌，六三八）「**卿所為乃亡隋之弊俗也。**」（长春宫供进之责）'
        '——**史部的亡隋是谏臣手里的镜子，诗的隋宮是锦帆底下的现场**；'
        '「**諫書**」通鉴恰一处（闭域+窗口入引）——貞觀十七年（癸卯，六四三）齐王祐'
        '乱平，「**上檢祐家文疏，得記室郟城孫處約諫書，嗟賞之，累遷中書舍人。**」——'
        '**诗「九重誰省諫書函」写给不见省的九重；史部唯一进账的谏书是皇帝从叛臣'
        '箱底翻出来的，人还因此升了官：一函不省，一函得赏**；「行留」恰一处入引'
        '——貞觀元年（丁亥，六二七）邸怀道对太宗「**煬帝將幸江都，召百官問行留之計，'
        '懷道為吏部主事，獨言不可。臣親見之。**」：**幸江都当时真有人言不可，'
        '且亲历者二十年后在朝堂上讲给太宗听——通鉴留的是亲历者的声音**；'
        '「戒嚴」恰十处七卷闭域（全库扫描在册零入引）——**诗偏偏只咬这词的否定式'
        '「不戒嚴」：史部戒嚴是万乘之防，诗不戒嚴是乘兴之君**。「後庭花」通鉴恰一'
        '在册零入引。本层零铸造零 relation。'),
    'bg-022-person': (
        '旧传李商隐段（**简化字录入**，V016 locator 已注，引文照登简体原样）'
        '再首引二句（皆生成时全库查重域恰零）：「**商隐幼能为文。令狐楚镇河阳，'
        '以所业文干之，年才及弱冠。**」「**博学强记，下笔不能自休，'
        '尤善为诔奠之辞。**」\n'
        '**谏书两界，人身为证**（读法声明，非史实）：诗里「九重誰省諫書函」——'
        '谏书进了宫门没人省；传里这个人弱冠之年「以所业文干」令狐楚，'
        '当场得礼遇——**同样的文字，干谒之门开，谏诤之门闭**；'
        '「下笔不能自休」的手，写进宫门的就是「誰省」二字。\n'
        'V066 已引段内二句「绹不之省」「名宦不进，坎壈终身」零重开'
        '（域恰 [V066] 生成时断言）；字义山/开成二年/岭表/三十六体（V016）'
        '在册句零重开；**旧传李商隐段隋/煬/九重/諫/戒嚴/揚州/江都全零**'
        '（机器断言——写下「隋宮」定谳的人，传里没有一个隋字）；'
        'certainty 不覆盖任何系年，本诗无底注（无注可登），'
        '诗 time.span/event.name/written_during 仍零铸造（audit 硬卡）。'),
}
CLAIMS = {
    'claim-bg-022-scene': (
        'FACT', 'LIKELY',
        '四句七绝本文（ws 选本页 poem 块四句**全无句读**——与《賈生》页有标点并存，'
        '同一选本两种转录形态首见，各从其录）；title 行内嵌 {{*|一雲隋堤}} 异注'
        '（异注进 title 行首见）；{{另}}/{{別}}/<ref> 全零；页内 Vtext/poem 双转录'
        '并存首末句各恰 2；全句**第二引**：正文 V018 卷539 卷页 claim 一引在先'
        '（生成时全库查重双针「乘興南遊不戒嚴」「半作障泥半作帆」各恰一处），'
        '本迁移引 ws 诗页——两引两面（卷页+诗页）上限恰满不重叠；'
        '两度上限至此用满、此诗正文对后来迁移关闭（audit 硬卡）。'),
    'claim-bg-022-city': (
        'FACT', 'LIKELY',
        '卷539「==[[隋宮]]==」恰二闭域（机器断言）=同卷同题双块：紫泉七律块+本篇'
        '七绝块（后块孤挂「{{*|一云隋堤}}」简体异注行恰一）——**同名两见两锚皆裸名：'
        '消歧判例反例首见**（无同名则无消歧器诸判例之反面；辨异全靠孤挂云注）；'
        'ws 层同名两页各首句消歧（本页页题「隋宮 (乘興南遊不戒嚴)」）——卷页裸名/'
        '诗页消歧分层消歧形态首见；异注同案两层（卷页简体「一云隋堤」/ws 页繁体'
        '「一雲隋堤」）照登；notes「{{唐詩三百首}}七绝」选本标记挂俗名首见；'
        '无评级页第二见；分类三行简繁混排第二见（分类行非史料声明+不升格，'
        'V048 判例）；全唐詩「隋宮」恰六处四卷闭域+卷540《隋宮守歲》锚恰一'
        '（「隋宮」第三面，档扫在册零入引）；**再新建 source-ws-t300-022 恰一枚'
        '（连续第二首开新源——V018 以卷页立诗、ws 选本页从未建源，'
        '卷页/诗页两个独立见证面，V066 判例同构；audit 断言恰一枚新源 INSERT）**。'),
    'claim-bg-022-world': (
        'FACT', 'LIKELY',
        '通鉴「隋宮/南遊/不戒嚴/乘興/宮錦/障泥/紫泉/螢火/垂楊/迷樓/錦帆/隋堤/'
        '日角/省諫」全零（诗面亡国现场不在史部，机器断言）；「亡隋」恰二闭域双窗口'
        '逐字入引=貞觀四年（庚寅，六三〇）「襲亡隋之弊，恐又甚於煬帝」谏+貞觀十二年'
        '（戊戌，六三八）「亡隋之弊俗」责（史部亡隋=谏臣的镜子，诗隋宮=锦帆的现场——'
        '同字两界第十二形态·亡国形态首见，audit 硬卡）；「諫書」恰一闭域窗口入引='
        '貞觀十七年（癸卯，六四三）开箱得孫處約諫書累遷中書舍人（一函不省/一函得赏）；'
        '「行留」恰一闭域窗口入引=貞觀元年（丁亥，六二七）「煬帝將幸江都……獨言不可。'
        '臣親見之」（亲历者的声音）；「戒嚴」恰十处七卷闭域在册零入引（诗咬否定式'
        '「不戒嚴」——万乘之防对乘兴之君）；「後庭花」恰一在册零入引；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during 零铸造'
        '零 relation（audit 硬卡）。'),
    'claim-bg-022-person': (
        'FACT', 'LIKELY',
        '旧传李商隐段（简化字录入，引文照登简体原样）再首引二句皆生成时全库查重'
        '域恰零=「商隐幼能为文。令狐楚镇河阳，以所业文干之，年才及弱冠。」+「博学强记，'
        '下笔不能自休，尤善为诔奠之辞。」（传区间归属机器断言）；「谏书两界，人身为证：'
        '干谒之门开/谏诤之门闭」系读法声明；V066 已引「绹不之省」「名宦不进，坎壈终身」'
        '零重开（域恰 [V066] 断言）；字义山/开成二年/岭表/三十六体诸在册句（V016）'
        '零重开；旧传李商隐段隋/煬/九重/諫/戒嚴/揚州/江都全零（机器断言）；'
        '本诗无底注（无注可登）；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-022-scene', 'source-ws-t300-022',
     '页面 隋宮 (乘興南遊不戒嚴)（《唐詩三百首》第 22 首选本页，页题带首句消歧；'
     'title+author+notes+poem 块四句——poem **全无句读**（与《賈生》页有标点并存，'
     '同一选本两种转录形态首见）；title 行内嵌 {{*|一雲隋堤}}（异注进 title 行首见）；'
     '全句**第二引**：V018 卷539 卷页一引在先——两引面不重叠，上限恰满，'
     '生成时全库查重双针恰一处，此后此诗正文关闭；{{另}}/{{別}}/<ref> 全零；'
     '页内 Vtext/poem 双转录并存各从其录）',
     join(WS_TITLE, WS_AUTHOR, WS_NOTE, WS_BODY)),
    ('claim-bg-022-city', 'source-quantangshi-539',
     '卷五百三十九·李商隱同题双《隋宮》块（**「==[[隋宮]]==」恰二'
     '机器断言**：前块紫泉七律锚+首联……后块本篇七绝锚+孤挂「{{*|一云隋堤}}」异注行'
     '+poem 四句——同名两见两锚皆裸名（消歧判例反例首见）；后块异注简体照登；'
     '源行系 V018 已立、本迁移复用零新建）',
     join(V539_ZQ, V539_CX)),
    ('claim-bg-022-city', 'source-ws-t300-022',
     '页面 隋宮 (乘興南遊不戒嚴)（header title 整行（内嵌 {{*|一雲隋堤}} 繁体异注，'
     '与卷页简体「一云隋堤」同案两层照登）+整页 notes 行（{{唐詩三百首}}后挂诗体'
     '俗名「七绝」首见；无 Textquality 评级第二见）+分类三行连片（简体「唐诗」与'
     '繁体「唐詩三百首」同页混排第二见）；分类行与页题消歧系整理者/编排动作：'
     '非史料声明、不升格）',
     join(WS_TITLE, WS_NOTE, WS_CAT)),
    ('claim-bg-022-world', 'source-zizhi-tongjian-events',
     '卷一百九十二·貞觀元年（丁亥，六二七）邸怀道对（煬帝將幸江都行留之议——'
     '独言不可+臣親見之）……卷一百九十三·貞觀四年（庚寅，六三〇）洛阳宫营缮谏段'
     '……卷一百九十五·貞觀十二年（戊戌，六三八）长春宫供进之责段……卷一百九十六·'
     '貞觀十七年（癸卯，六四三）齊王祐亂平开箱得孫處約諫書段（**通鉴隋宮/南遊/'
     '不戒嚴/乘興/宮錦/障泥全零、亡隋恰二、諫書/行留/幸江都各恰一、戒嚴恰十七卷'
     '闭域**：文件闭域+四处年标题窗口机器断言——亡隋只在谏臣嘴里；一函不省/一函得赏；'
     '四段史文逐字入引为判决证据；全唐詩在册句零入引）',
     join(TJ_XJD, TJ_WS1, TJ_WS2, TJ_JS)),
    ('claim-bg-022-person', 'source-jiutangshu-wenyuan',
     '舊唐書卷一九〇下·李商隱（**简化字录入**照登原样，V016 locator 同款标注）'
     '（「商隐幼能为文……年才及弱冠」句+「博学强记……诔奠之辞」句——皆全库查重'
     '恰零域首引；传区间归属机器断言；「干谒之门开/谏诤之门闭」系读法声明；'
     'V066 已引「绹不之省/坎壈终身」句与字义山/岭表/三十六体诸在册句零重开）',
     join(JTS_P1, JTS_P2)),
]
BG_LINES = {'bg-022-scene': (1,), 'bg-022-city': (2,),
            'bg-022-world': (3,), 'bg-022-person': (4,)}
BG_AUDIENCE = {'bg-022-scene': 'PRIMARY', 'bg-022-city': 'JUNIOR',
               'bg-022-world': 'SENIOR', 'bg-022-person': 'JUNIOR'}
BG_TITLES = {'bg-022-scene': '眼前：一场没有刹车的巡幸',
             'bg-022-city': '这座城：同卷两见的双隋宮',
             'bg-022-world': '这个天下：亡隋在谏臣嘴里',
             'bg-022-person': '这个人：下笔不能自休的手'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 48 首·四句七绝 1/1/1/1 第四次）；史实句均有逐字引证；'
                 '系年第四十二次判决（题证系列第卅状·隋宫与谏书）'
                 '「诗题隋宮在史部全零，亡隋只在谏臣嘴里；诗的谏书函九重不省，'
                 '史的谏书从叛家开箱反得赏」——同字两界第十二形态·亡国形态首见：'
                 '通鉴隋宮/南遊/不戒嚴/乘興/宮錦/障泥/紫泉/螢火/垂楊/迷樓/錦帆/'
                 '隋堤/日角/省諫全零；亡隋恰二闭域双窗口入引（貞觀四年庚寅六三〇'
                 '「襲亡隋之弊恐又甚於煬帝」+貞觀十二年戊戌六三八「亡隋之弊俗」——'
                 '谏臣的镜子对锦帆的现场）；諫書恰一闭域窗口入引（貞觀十七年癸卯'
                 '六四三开箱得孫處約諫書累遷中書舍人——一函不省/一函得赏）；'
                 '行留恰一入引（貞觀元年丁亥六二七「煬帝將幸江都……獨言不可臣親見之」'
                 '——亲历者的声音）；戒嚴恰十处七卷闭域在册零入引（诗只咬否定式'
                 '「不戒嚴」——万乘之防对乘兴之君）；後庭花恰一在册；'
                 '卷539「==[[隋宮]]==」恰二=**同卷同题双块两锚皆裸名（消歧判例反例'
                 '首见——有同名锚仍裸名，辨异靠孤挂 {{*|一云隋堤}} 云注）**；'
                 'ws 层同名两页首句消歧（卷页裸名/诗页消歧分层形态首见）+'
                 '异注简繁两层（一云/一雲隋堤）；ws 页 poem 块**全无句读**'
                 '（与《賈生》页有标点并存——同一选本两种转录形态首见）+title 行'
                 '内嵌异注首见+notes 挂俗名「七绝」首见+无评级页第二见+分类三行'
                 '简繁混排第二见；**再新建 source-ws-t300-022 恰一枚（连续第二首'
                 '开新源 145→146——卷页/诗页两个独立见证面，V066 判例同构；'
                 'audit 断言恰一枚新源 INSERT）**；全唐詩隋宮恰六处四卷闭域+卷540'
                 '《隋宮守歲》锚恰一（第三面）在册零入引；正文第二引上限用满'
                 '第十五例（V018 在先+双针恰一，两引面不重叠）；PERSON 旧传简化段'
                 '再首引二句（弱冠干文+下笔不能自休——干谒门开/谏诤门闭读法声明；'
                 'V066 绹不之省/坎壈终身零重开）；旧传段隋/煬/九重/諫/戒嚴/揚州/江都'
                 '全零；KNOWN 零如实记录（第廿三例，audit 反向断言）；'
                 '判例关键语零入引文。' for k in BG}

NEW_SOURCE_ROW = {
    'id': 'source-ws-t300-022',
    'title': '维基文库《唐詩三百首》页面：隋宮 (乘興南遊不戒嚴)',
    'author': None,
    'edition': '全唐詩',
    'url': 'https://zh.wikisource.org/wiki/隋宮_(乘興南遊不戒嚴)',
    'rights_note': (
        '维基文库录入本，公有领域古籍。本行由 emit_v067.py 对 /tmp/src-dl 快照逐字定位。'
        '本诗 V018 立正文时用的是《全唐詩》卷539 卷页（source-quantangshi-539，'
        'version_code vol-raw），此《唐詩三百首》选本页当时未建源——卷页与诗页是'
        '两个独立见证面（卷页同题双块锚点归属 vs 选本页 header/notes/分类），'
        '本迁移引诗页非新源不能承载（V066 source-ws-t300-031 判例同构）。'
        '页题带首句消歧「隋宮 (乘興南遊不戒嚴)」；title 行内嵌 {{*|一雲隋堤}} 异注；'
        'poem 块四句全无句读（与《賈生》页有标点并存）；notes 挂诗体俗名「七绝」；'
        '无 Textquality 评级。核验状态保持 PENDING。'),
    'verification_status': 'PENDING',
    'source_kind': 'POETRY_COLLECTION',
    'reliability': 'HIGH',
}


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
    A("""-- V067：李商隱《隋宮》(work-t300-022) 四层背景（阶段 D 第 48 首·隋宫与谏书）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V048、V057、V058、V059、V060、V061、
--       V062、V063、V064、V065、V066 已执行
--       （work-t300-022 与其 text-work-t300-022-ws、source-quantangshi-539 是 V018 的行
--       （V018 以卷539 卷页立本诗正文，version_code=vol-raw——ws 选本页当时未建源）；
--       source-ws-t300-022 是本迁移新建的选本页源（恰一枚；audit 断言）；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       source-jiutangshu-wenyuan 是 V016 已立的旧唐书文苑传源（李商隐传在此，简化字录入）；
--       判例在册句（义山/开成二年/岭表/三十六体 V016、绹不之省/坎壈终身 V066、
--       痛哭者一/厝火積薪/狂夫之言 V065/V066）只对照不重开）。
--       **本迁移再新建恰 1 个 source（source-ws-t300-022）——连续第二首开新源（V066 判例
--       同构：卷页/诗页两个独立见证面）；audit 断言恰一枚诗源表新建插入语句且 id 唯一、
--       回滚按 id 删且只删此行。**
--
-- 数据源（可复现）：emit_v067.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/隋宮__乘興南遊不戒嚴_.txt（title 行内嵌异注首见+poem 块全无句读首见+
--   notes 挂俗名七绝首见+无评级页第二见+分类三行简繁混排+Vtext/poem 双转录）、
--   全唐詩卷539（**同卷同题双《隋宮》块**：==[[隋宮]]== 恰二+{{*|一云隋堤}} 恰一
--   +紫泉/乘興诸句各恰一——消歧判例反例；全唐诗「隋宮」恰六处四卷档扫）、
--   全唐詩卷540（《隋宮守歲》锚恰一——「隋宮」第三面档扫零入引）、
--   舊唐書卷190下（李商隐段首引二句+段内隋/煬/九重/諫/戒嚴/揚州/江都全零+段边界断言）、
--   通鑑卷192/193/195/196（行留/亡隋×2/谏书四段+四处年标题窗口）+
--   通鑑 75 卷负证计数扫描（隋宮/南遊/不戒嚴/乘興/宮錦/障泥/紫泉/螢火/垂楊/迷樓/錦帆/
--   隋堤/日角/省諫 全零+亡隋/諫書/行留/幸江都/戒嚴/後庭花 闭域）+
--   既有迁移引文域逐句查重——传区间归属、二引/零重开/首引零域/新源不存在前提全部生成时断言。
--
-- 做：新 poetry_source 行 1（source-ws-t300-022，PENDING）+
--   4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 background_line（四句七绝 **1/1/1/1 第四次**（V056/V061/V066 之后）：scene→1 city→2
--   world→3 person→4，绑 text-work-t300-022-ws 的 4 行）+ 不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「诗题隋宮在史部全零，亡隋只在谏臣嘴里」）：
--   * 诗面词通鉴全零+亡隋恰二双窗口入引+谏书恰一窗口入引+行留恰一入引（一函不省/一函得赏）；
--   * 「戒嚴」通鉴恰十处七卷系闭域档扫——诗只咬其否定式「不戒嚴」系读法（万乘之防对乘兴之君）；
--   * 「谏书两界，人身为证：干谒门开/谏诤门闭」标明读法声明；
--   * 同卷同题双块两锚皆裸名系卷539 恰二闭域上的照登——消歧判例反例首见（有同名锚仍裸名）；
--   * 异注简繁两层（一云/一雲隋堤）照登不判；poem 无句读/notes 俗名「七绝」均照登；
--   * 新源恰一枚如实开例（V066 判例同构，两引面不重叠声明在案），回滚可精确撤销；
--   * 全唐詩隋宮恰六处四卷+《隋宮守歲》在册零入引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第廿三例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * V066「绹不之省/坎壈终身」、V016 诸在册句只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 66，不含 67
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-022-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-022','source-quantangshi-539');  -- 只含 539
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-022-ws';  -- 恰 4
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-022-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-022';                                  -- 4（1/1/1/1）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-022-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-022';   -- 恰 1（本迁移新建）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-022'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-022';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-022-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V067_rollback.sql（按 id 全枚举删除；source 只删本迁移新建的
--   source-ws-t300-022 一行——source-quantangshi-539 系 V018 所立绝不删）
START TRANSACTION;""")

    A('\n-- ---------- 0. 新 source 恰一枚（source-ws-t300-022 选本页；PENDING 照 V066 判例） ----------')
    scols = ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability']
    A(guard('poetry_source', scols, [NEW_SOURCE_ROW], 'x.id = t.id'))

    A('\n-- ---------- 1. BACKGROUND content identities ----------')
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
    brows = [{'id': k, 'work_id': 'work-t300-022',
              'layer': {'bg-022-scene': 'SCENE', 'bg-022-city': 'CITY',
                        'bg-022-world': 'WORLD', 'bg-022-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（四句七绝 1/1/1/1 第四次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-022-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 67, 'Li Shang-yin''s Sui Palace (work-t300-022) background layers (stage-D poem 48, four-line jueju 1/1/1/1 fourth time): dating verdict forty-two, thirtieth shape of the title-evidence series -- the Sui Palace and the remonstrance letter, the fallen dynasty split in two realms: the poem''s title-word Sui-gong scores zero across the Tongjian (machine-asserted, with nan-you, bu-jieyan, chengxing, gongjin, zhangni, zi-quan, yinghuo, chuiyang, milou, jinfan, sui-di, ri-jiao, sheng-jian all zero); yet wang-sui (fallen Sui) appears exactly twice, both as a mirror in the mouths of remonstrators: "your subjecting of the scarred people, following the abuses of the fallen Sui, perhaps surpasses even Emperor Yang" (Zhenguan 4th, gengyin, 630, over rebuilding the Luoyang palace) and "what you do is the corrupt custom of the fallen Sui" (Zhenguan 12th, wuxu, 638) -- the histories'' fallen Sui is a warning-mirror, the poem''s Sui Palace is the scene under silk sails (twelfth same-character split, first fallen-dynasty shape); jian-shu (remonstrance letter) appears exactly once -- after the Prince of Qi''s revolt was quelled the emperor opened the rebel''s papers, found remonstrance letters of his secretary Sun Chuoyue, praised them, and Sun was promoted to Zhongshu Sheren (Zhenguan 17th, guimao, 643): the poem''s letter reaches the nine gates that never glance at it, the histories'' only recorded letter is dug from a traitor''s chest and its author rewarded -- one letter ignored, one letter rewarded; xing-liu (go or stay) exactly once -- Wei Zheng-era Di Huaidao telling Taizong: when Emperor Yang was about to visit Jiang-du he summoned officials to debate go or stay, and only one said no, "your servant saw it himself" (Zhenguan 1st, dinghai, 627) -- the histories keep an eyewitness voice; jie-yan (martial lockdown) appears ten times in seven scroll-volumes, all institutional guard-duty, zero quoted -- the poem bites only its negation bu-jieyan: histories'' lockdown is the ten-thousand-chariot defense, poem''s no-lockdown is a pleasure-bound ruler; juan 539 holds TWO same-titled Sui Palace blocks (closed-domain assert): the zi-quan seven-regulated and this jueju, BOTH anchors bare ==[[隋宮]]== -- the anti-case of the disambiguation precedents (first seen: same-name blocks, still bare anchors; differentiation rests on one orphan variant-note line {{*|一云隋堤}}); at the ws layer the two same-titled anthology pages each disambiguate by first line -- layered disambiguation (bare at scroll level, disambiguated at page level) first seen; the variant note itself logged in two scripts (simplified scroll page vs traditional ws title line {{*|一雲隋堤}} -- a variant note inside a title line, first seen); the ws poem block carries NO punctuation at all (contrast the Jia-sheng page which does -- two transcription styles inside one anthology, first seen) and notes append the colloquial form-name 七绝 (first seen) with no Textquality grade (second time) and three category rows mixing scripts (second time); exactly ONE new poetry_source row (source-ws-t300-022), the second consecutive new source (V066 pattern: scroll page and anthology page are two independent witnesses); body quotes hit their two-use ceiling (fifteenth instance; twin needles; witnesses never overlap); PERSON first-cites two more zero-domain sentences from the simplified JTS biography -- at twenty he visited Linghu Chu with his compositions, and "his brush could not stop itself" -- the same hand, one door open for poems, one door shut for remonstrance (reading declared); V066''s two quoted sentences stay closed (domain exactly V066 asserted); the biography segment holds no Sui/Yang/jiu-chong/jian/jie-yan/Yang-zhou/Jiang-du character (machine-asserted); KNOWN zero honestly recorded (twenty-third instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 67);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V067 精确回滚：只删 V067 插入的行（id 全枚举）。source 只删一行：',
         '-- source-ws-t300-022 是本迁移新建的选本页源（恰一枚，审计断言）——按 id 删除；',
         '-- source-quantangshi-539 是 V018 已立的卷539 卷页源（本迁移复用），绝不删；',
         '-- work-t300-022 本体、其 text_line 4 行都是 V018 的行，绝不删；',
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
    L.append("DELETE FROM poetry_source WHERE id = 'source-ws-t300-022';")
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 67;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_BODY,
              V539_ZQ, V539_CX, TJ_XJD, TJ_WS1, TJ_WS2, TJ_JS, JTS_P1, JTS_P2]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 异注进 title 行 + poem 无句读 + notes 俗名照登硬卡（SCENE/CITY ws 引文）
    scene_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-022-scene' and s == 'source-ws-t300-022')
    if '隋宮{{*|一雲隋堤}}' not in scene_ws:
        bad.append('title 行内嵌异注未逐字入 SCENE 引文（异注进 title 行首见照登硬卡）')
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-022-city' and s == 'source-ws-t300-022')
    if '{{唐詩三百首}}七绝' not in city_ws:
        bad.append('notes 挂俗名「七绝」未逐字入 CITY 引文（首见照登硬卡）')
    if '[[Category:唐诗]]' not in city_ws or '[[Category:唐詩三百首|李]]' not in city_ws:
        bad.append('分类简繁混排未逐字入 CITY 引文（第二见照登硬卡）')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-022-city' and s == 'source-ws-t300-022'):
        bad.append('CITY ws locator 须含「不升格」声明（分类行三重断言失效）')
    # 同卷同题双块照登硬卡
    city_q = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-022-city' and s == 'source-quantangshi-539')
    if '紫泉宮殿鎖煙霞' not in city_q or '{{*|一云隋堤}}' not in city_q:
        bad.append('卷539 双块或简体异注行未逐字入 CITY 引文（消歧反例首见照登硬卡）')
    # SCENE 第二引上限声明硬卡
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-022-scene' and s == 'source-ws-t300-022')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054–V066 同款硬卡）')
    # WORLD：四段史文必须在引文内；诗语零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-022-world')
    for tok in ('煬帝將幸江都', '襲亡隋之弊', '亡隋之弊俗', '孫處約諫書'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（四段必须入引）')
    for tok in ('乘興南遊', '障泥', '宮錦', '九重誰省', '紫泉', '不戒嚴'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文）')
    # PERSON 首引句必须在引文内 + V066 零重开
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-022-person')
    for tok in ('以所业文干之', '下笔不能自休'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺首引要素「{tok}」（简化字段首引照登硬卡）')
    for tok in ('绹不之省', '坎壈终身'):
        if tok in cited:
            bad.append(f'V066 已引「{tok}」零重开——不得入本迁移引文')
    for c, s, _, ex in CITATIONS:
        if not s.startswith('source-ws-t300-') and s != 'source-quantangshi-539':
            for w in ('謫仙', '脫靴', '賜金放還', '宮錦袍', '夜郎', '山東人'):
                if w in ex:
                    bad.append(f'非 ws/卷页引文不得含判例语「{w}」')
    # 判例只引不重开（引文域全扫；含 V064/V065/V066 与 V016）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒',
                '仕宦之疾徑', '茶鐺', '解官以贖', '柴毁骨立', '毀幾不生',
                '車如流水馬如龍', '歴右拾遺', '天寳末，為給事中', '或牒歸故鄉',
                '昆仲宦遊兩都', '輞口', '藍田别墅', '下馬飲君酒', '歸臥南山陲',
                '閉關以拒之', '殺郡王', '雲南王孫', '春草未生', '今宵歸不歸',
                '山中相送罷', '日暮掩柴扉', '一作山中送別', '聚斂為長策',
                '脫巾解帶', '解帶繫頸', '議者不之罪', '晚年唯好靜', '漁歌入浦深',
                '貶晙為梓州刺史', '段子璋反', '參天可汗道', '火炬於樹杪',
                '九歲知屬辭', '別墅在輞川', '華子岡', '版圖墮於避地', '避地江左',
                '龍陽江漲', '仙源公主', '碧玉赴井死', '狂夫之言', '狂夫竊發',
                '不傷良人', '綠珠怨', '贈秘書監', '停筆而化',
                '可為痛哭者一', '厝火積薪', '可憐彼翁', '虛前席', '不問蒼生問鬼神',
                '賈生年少虛垂涕', '宣室求賢訪逐臣',
                '李商隐，字义山，怀州河内人。', '开成二年，方登进士第',
                '商隐随亚在岭表累载', '与太原温庭筠、南郡段成式齐名',
                '府罷，客滎陽，卒'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 四句 1/1/1/1 第四次
    if BG_LINES != {'bg-022-scene': (1,), 'bg-022-city': (2,),
                    'bg-022-world': (3,), 'bg-022-person': (4,)}:
        bad.append('四句 background_line 须 1/1/1/1（第四次）')
    if len(re.findall(r"text-work-t300-022-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    # **新源恰一枚**（连续第二首——断言恰一 INSERT 且 id 正确）
    ins_src = sql.count('INSERT INTO poetry_' + 'source')
    if ins_src != 1:
        bad.append(f'本迁移应恰新建 1 个 source（恰一枚 INSERT），实 {ins_src}')
    src_blk = sql[sql.index('INSERT INTO poetry_' + 'source'):]
    src_blk = src_blk[:src_blk.index(';')]
    if "'source-ws-t300-022'" not in src_blk or "'source-quantangshi-539'" in src_blk:
        bad.append('新源 INSERT 的 id 不对（应恰 source-ws-t300-022，不得含 539）')
    rb = build_rollback()
    if rb.count('DELETE FROM poetry_source') != 1 or 'source-ws-t300-022' not in rb.split('DELETE FROM poetry_source')[1][:60]:
        bad.append('回滚的 source 删除应恰一行且只删 source-ws-t300-022')
    if 'source-quantangshi-539' in rb.split('DELETE FROM poetry_source')[1]:
        bad.append('回滚绝不得删 source-quantangshi-539（V018 所立）')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V067 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V067 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-022' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V067 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-022' AS subject_id" in sql:
        bad.append('V067 的 claim 主语应全部是 bg-022-*，work-t300-022 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V067 不碰 poetry_text_line')
    body_all = ''.join(BG.values())
    if '亡隋只在谏臣嘴里' not in body_all:
        bad.append('BG/WORLD 须含「亡隋只在谏臣嘴里」判决声明')
    if '亡国形态首见' not in body_all:
        bad.append('BG 须含「亡国形态首见」（同字两界第十二形态）声明')
    if '消歧判例反例首见' not in body_all:
        bad.append('BG/CITY 须含「消歧判例反例首见」（同名两锚皆裸名）声明')
    if '全无句读' not in body_all:
        bad.append('BG/SCENE 须含「poem 块全无句读」首见声明')
    if '一云隋堤' not in body_all or '一雲隋堤' not in body_all:
        bad.append('BG/CITY 须含异注简繁两层（一云/一雲隋堤）照登声明')
    if '新源' not in body_all or '恰一' not in body_all:
        bad.append('BG/CITY 须含「再新建恰一枚 source」诚实开例声明')
    if '一函不省' not in body_all or '一函得赏' not in body_all:
        bad.append('BG/WORLD 须含「一函不省/一函得赏」对照声明')
    if '不戒嚴' not in body_all or '万乘之防' not in body_all:
        bad.append('BG/WORLD 须含「不戒嚴对万乘之防」声明')
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
    if len(NEW_SOURCE_ROW['id']) > 64 or len(NEW_SOURCE_ROW['title']) > 200 \
            or len(NEW_SOURCE_ROW['rights_note']) > 1000:
        bad.append('poetry_source 新行宽度超限')
    for m in re.finditer(r'INSERT INTO (poetry_\w+)', sql):
        if m.group(1) == 'poetry_schema_version':
            continue  # 长英文版本描述使通用状态机失步——V064/V065 判例：下面显式断言
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
    # 版本账本显式守卫（V064/V065 判例延续）
    vblk = sql[sql.index('INSERT INTO poetry_schema_version'):]
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 67)' not in vblk:
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 13 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（旧传李商隐段二首引句，段界 ==弟 羲叟==）；'
              f'四处年标题窗口断言（貞觀元年六二七/四年六三〇/十二年六三八/十七年六四三）；'
              f'负证机器复查五层（通鉴隋宮/南遊/不戒嚴/乘興/宮錦/障泥/紫泉/螢火/垂楊/'
              f'迷樓/錦帆/隋堤/日角/省諫全零+亡隋恰二闭域(tj-193/195)+諫書/行留/幸江都'
              f'各恰一闭域(tj-196/192/192)+戒嚴恰十分布七卷+後庭花恰一/'
              f'全唐詩隋宮恰六处四卷闭域+卷539 双锚/异注/诸句闭域+卷540 守歲锚恰一/'
              f'ws 无评级恰零+{{{{*}}}}恰一枚在 title+零另/別/ref+poem 无句读+'
              f'首末句页内各恰二+notes 俗名七绝+分类三行连片简繁混排/'
              f'旧传段隋煬九重諫戒嚴揚州江都全零，快照变动即中止）；'
              f'前提全库查重硬卡五件+九首引句零域断言+新源 id 全库不存在断言+'
              f'539 源恰[V018]域断言+V066 二句恰[V066]域断言；'
              f'异注进 title/poem 无句读/notes 俗名/双块异注照登硬卡；CITY「不升格」硬卡；'
              f'SCENE 第二引/上限硬卡；四段通鉴史文入引+诗语零混入断言；'
              f'PERSON 二首引句入引硬卡+V066 绹不之省/坎壈终身零重开硬卡；'
              f'判例只引不重开断言（含 V064/V065/V066 与 V016 李商隐在册诸语）；'
              f'四句 1/1/1/1 形制断言；零 KNOWN 反向断言；'
              f'**新源恰一枚断言（INSERT 恰一+id 正确+回滚恰删此行且不碰 539）**——'
              f'连续第二首开新源（卷页/诗页两个独立见证面，V066 判例同构）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
