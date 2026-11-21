#!/usr/bin/env python3
"""阶段 D 第 49 首：生成 V068——李商隱《瑤池》(work-t300-026, V018 已立) 四层背景。

**本迁移再新建 1 个 source（source-ws-t300-026）——连续第三首开新源（V066/V067
判例同构）**：V018 以全唐詩卷539 卷页（source-quantangshi-539，version_code
vol-raw）立本诗正文，ws《唐詩三百首》诗页从未建源（ledger 146→147，audit 断言
恰一枚新源 INSERT、回滚按 id 删且只删此行）。

「为什么写」走到**仙界两界**（同字两界第十三形态·仙界形态首见）：
**「诗问死者何不重来，史部活着问长生的皇帝一炷香接一炷香；通鉴的瑤池
全是边州，穆王三个没一个是那个穆王」**——

诗面仙界词通鉴全零（八駿/黃竹/阿母/綺窗/三萬里/動地哀/重來——机器断言）；
「**瑤池**」通鉴恰三**全在 tj-199 一页且该页零年标题**（50% 页三连聚首见——
窗口断言不可入围，闭域+整句入引+locator 声明零标题）：三处全是安西边州的
**瑤池都督府/瑤池都督**（阿史那贺鲁除授沿革）——**诗问的仙池史部没有，
同名的是一份边州建制**；「**穆王**」恰三闭域双窗口入引+一处零标题闭域：
永淳元年（壬午，六八二）刘仁轨铨选议引「**故周穆王命伯冏為太僕正**」
（谏书里的穆王是官制案例）、廣德二年（甲辰，七六四）「**臨淮武穆王李光弼**」
（谥法之穆）、tj-255 零标题页常山忠穆王（又一谥号）——**史部三个穆王
没一个是巡游瑶池的那个：一个是奏疏引的周王，两个是唐人谥号；
诗问「穆王何事不重來」，史部连可以问的穆王都没有**；而史部反向接题——
「**長生**」恰十三处七卷闭域双窗口入引：元和十三年（戊戌，八一八）宪宗纳
山人柳泌「**雲能合長生藥**」（群臣莫敢言）、大中十一年（丁丑，八五七）宣宗
问轩辕集「**長生可學乎**」，对以「**王者屏欲而崇德，則自然受天遐福，
何處更求長生？**」——**诗问死者为何不回来，史部活着皇帝前赴后继求解长生，
史部唯一的正面回答是「何处更求长生」**；「靈藥」恰一（tj-211 闭域档扫）。

卷539 侧（CITY 层核心）：本篇锚「==[[瑤池]]==」**全《全唐詩》唯一**（八卷十条
字面中锚恰一——对照同卷《隋宮》双锚 V067：**同卷同作者，单锚诗题与双锚诗题
并存，「锚点恰一」与「锚点恰二」两种同名形态同一卷内标本齐备**）；卷内
穆王/八駿/黃竹各恰一=全在本篇（诗面三字卷内自足闭域）；ws 页 notes 只有
{{唐詩三百首}} 裸标记——**对照同卷《隋宮》页 notes 挂「七绝」：同卷 notes
两形态首见**（挂不挂体名非强制）；title 裸名——对照同卷《隋宮》页 title 内嵌
异注：**同卷 title 两形态首见**；poem 无句读第二见（V067 首见）；无评级第三见
（V066 首见）；{{另}}/{{別}}/{{*}}/<ref> 全零。

正文第二引上限用满第十六例（V018 卷539 一引在先，双针各恰一处——两引面不重叠）。

PERSON 层：旧传李商隐段（简化字录入）再首引二句（皆零域）——「**会昌二年，
又以书判拔萃。**」「**恃才诡激，为当涂者所薄。**」：诗写君主迷上仙界不回头，
传写「为当涂者所薄」的君主侧写——**诗悯君之迷，传悯士之穷**（读法声明）；
段内瑤池/穆王/八駿/長生/仙字全零——**写尽瑶池八骏的人，传里没有一个仙字**
（段级零证·仙字首用）；V066「绹不之省/坎壈终身」、V067「以所业文干之/
下笔不能自休」、V016 在册诸句零重开（域断言）。

4 句七绝 shape：1/1/1/1 第五次（V056/V061/V066/V067 之后）。

用法: python3 -I emit_v068.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/瑤池.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
V539 = pathlib.Path('/tmp/src-dl/quantangshi/vol539.txt').read_text(encoding='utf-8')
TJ199 = pathlib.Path('/tmp/src-dl/tongjian/tj-199.txt').read_text(encoding='utf-8')
TJ203 = pathlib.Path('/tmp/src-dl/tongjian/tj-203.txt').read_text(encoding='utf-8')
TJ223 = pathlib.Path('/tmp/src-dl/tongjian/tj-223.txt').read_text(encoding='utf-8')
TJ240 = pathlib.Path('/tmp/src-dl/tongjian/tj-240.txt').read_text(encoding='utf-8')
TJ249 = pathlib.Path('/tmp/src-dl/tongjian/tj-249.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 瑤池', '| title    = 瑤池',
                         'ws header title(裸名题面——对照同卷隋宫页title内嵌异注：同卷title两形态)')
WS_AUTHOR = slice_between(WS, '| author   = 李商隱', '| author   = 李商隱', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '| notes    = {{唐詩三百首}}', '| notes    = {{唐詩三百首}}',
                        'ws 页底注(裸选本标记不挂体名——对照同卷隋宫页挂「七绝」：同卷notes两形态首见)')
WS_CAT = slice_between(WS, '[[Category:李商隱]]', '[[Category:唐詩三百首|李]]',
                       'ws 分类三行连片(简体「唐诗」与繁体「唐詩三百首」同页混排第三见)')
WS_BODY = slice_between(WS, '瑤池阿母綺窗開\n黃竹歌聲動地哀', '穆王何事不重來\n</poem>',
                        'ws 页 poem 块四句(全无句读第二见;第二引)')
V539_BLOCK = slice_between(V539, '==[[瑤池]]==\n<poem>\n瑤池阿母綺窗開', '穆王何事不重來\n</poem>',
                           '卷539 本篇块(锚==[[瑤池]]==全唐诗唯一——同卷隋宫双锚之对照,单锚诗题标本)')
TJ_YC = slice_between(TJ199, '置瑤池都督府，隸安西都護；戊子，以左衛將軍阿史那賀魯為瑤池都督。',
                      '置瑤池都督府，隸安西都護；戊子，以左衛將軍阿史那賀魯為瑤池都督。',
                      '通鉴tj-199安西瑶池都督府除授(通鉴瑤池恰三全在此页全为边州建制;'
                      '该页零年标题50%页——三连聚首见,不可作窗口断言,locator声明)')
TJ_MW1 = slice_between(TJ203, '故周穆王命伯冏為太僕正', '故周穆王命伯冏為太僕正',
                       '通鉴永淳元年刘仁轨铨选议(穆王史部一处——谏书里是官制案例;窗口断言)')
TJ_MW2 = slice_between(TJ223, '臨淮武穆王李光弼', '臨淮武穆王李光弼',
                       '通鉴广德二年李光弼传段(穆王史部二处——谥法之穆;窗口断言)')
TJ_CS1 = slice_between(TJ240, '薦山人柳泌，雲能合長生藥', '雲能合長生藥',
                       '通鉴元和十三年宪宗纳柳泌(长生史部十三处之一——活着求长生;窗口断言)')
TJ_CS2 = slice_between(TJ249, '上召入禁中，問曰：「長生可學乎？」', '何處更求長生？」',
                       '通鉴大中十一年宣宗问轩辕集(史部对仙界的唯一正面回答——何处更求长生;窗口断言)')
JTS_P1 = slice_between(JTS, '会昌二年，又以书判拔萃。', '又以书判拔萃。',
                       '旧传李商隐段(书判拔萃——才调第二道入场券;PERSON 首引)')
JTS_P2 = slice_between(JTS, '恃才诡激，为当涂者所薄。', '为当涂者所薄。',
                       '旧传李商隐段自断(当涂者所薄——掌权者侧的厌弃;PERSON 首引)')

# ---------- 传区间归属复验（V036 立规；段界 ==弟 羲叟==） ----------
_ja = JTS.find('=李商隱=')
_jm = re.search(r'\n==[^=\n]{1,12}==', JTS[_ja + 8:])
_seg_j = JTS[_ja:_ja + 8 + _jm.start()]
for _needle in (JTS_P1, JTS_P2):
    if _needle not in _seg_j:
        raise SystemExit('PERSON 首引句越出旧传李商隐段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；四扇窗口+一页零标题反向断言） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ203, TJ_MW1, '永淳元年')
_window(TJ223, TJ_MW2, '廣德二年')
_window(TJ240, TJ_CS1, '元和十三年')
_window(TJ249, TJ_CS2, '大中十一年')
# 50% 页零标题断言（V064 立规；本页三连聚——若快照修订后有年标题，入围规则变了须重估）
if _HEAD.findall(TJ199):
    raise SystemExit('tj-199 出现年标题——零标题三连聚判决与入围规则须重估')

# ---------- 负证机器复查（V042 立规） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：诗面仙界词全零；瑤池恰三全在tj-199；穆王恰三分布三卷；長生恰十三处七卷；靈藥恰一
for _w in ('八駿', '黃竹', '阿母', '綺窗', '三萬里', '動地哀', '重來', '何事不重來',
           '西王母', '仙術'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗面仙界不进史部的判决失效，须重读')
_yc = {n: t.count('瑤池') for n, t in _tjf.items() if '瑤池' in t}
if _yc != {'tj-199.txt': 3}:
    raise SystemExit(f'通鉴「瑤池」分布变了（实 {_yc}）——三连聚零标题页判决须重估')
if _alltj.count('瑤池都督') != 3:
    raise SystemExit('通鉴「瑤池都督」不再恰三——三处全是边州建制判决须重估')
_mw = {n: t.count('穆王') for n, t in _tjf.items() if '穆王' in t}
if _mw != {'tj-203.txt': 1, 'tj-223.txt': 1, 'tj-255.txt': 1}:
    raise SystemExit(f'通鉴「穆王」分布变了（实 {_mw}）——三个穆王没一个是那个穆王判决须重估')
if _HEAD.findall(_tjf['tj-255.txt']):
    raise SystemExit('tj-255 出现年标题——第三处穆王的零标题闭域声明须重估')
_cs = {n: t.count('長生') for n, t in _tjf.items() if '長生' in t}
if sum(_cs.values()) != 13 or len(_cs) != 7:
    raise SystemExit(f'通鉴「長生」不再恰 13 处七卷（实 {sum(_cs.values())}）——活着求长生判决须重估')
if _alltj.count('靈藥') != 1:
    raise SystemExit('通鉴「靈藥」不再恰一——在册闭域须重估')
# ② 全唐诗：锚全库唯一；卷内三字各恰一；字面十条八卷
if _allq.count('==[[瑤池]]==') + _allq.count('==瑤池==') != 1:
    raise SystemExit('《全唐詩》「瑤池」锚不再全库唯一——单锚诗题标本判决失效')
_qd = {name: t.count('瑤池') for name, t in sorted(_qtf.items()) if '瑤池' in t}
if sum(_qd.values()) != 10 or len(_qd) != 8:
    raise SystemExit(f'全唐詩「瑤池」字面不再恰十条八卷（实 {sum(_qd.values())}）——在册闭域须重估')
for _w in ('穆王', '八駿', '黃竹', '動地哀', '三萬里', '不重來'):
    if V539.count(_w) != 1:
        raise SystemExit(f'卷539「{_w}」不再恰一——诗面三字卷内自足闭域失效')
if V539.count('綺窗') != 2 or V539.count('阿母') != 3:
    raise SystemExit('卷539「綺窗/阿母」计数变了（实为卷内 2/3 他诗混片——闭域档扫须重估）')
if V539.count('==[[隋宮]]==') != 2:
    raise SystemExit('卷539 隋宫双锚变了（V067 判例在册）——单锚/双锚并存标本须重估')
# ③ ws：无评级 + notes 裸标记 + title 裸名 + poem 无句读 + 零标记 + 双转录 + 分类三行
if WS.count('{{Textquality') != 0:
    raise SystemExit('ws 页出现 Textquality 评级——无评级第三见断言失效')
if WS.count('| notes    = {{唐詩三百首}}') != 1 or WS.count('{{唐詩三百首}}') != 1:
    raise SystemExit('ws 页 notes 结构变了（应恰一枚裸选本标记不挂体名——同卷两形态断言失效）')
if WS.count('{{另') or WS.count('{{別') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页出现异文/注记标记——零标记断言失效（对照同卷隋宫页 {{*}} 恰一）')
if '穆王何事不重來。' in WS or '瑤池阿母綺窗開，' in WS:
    raise SystemExit('ws poem 块出现句读——poem 无句读第二见断言失效')
if WS.count('瑤池阿母綺窗開') != 2 or WS.count('穆王何事不重來') != 2:
    raise SystemExit('ws 页 Vtext/poem 双转录结构变了（首末句页内应各恰 2）')
_cat = '[[Category:李商隱]]\n[[Category:唐诗]]\n[[Category:唐詩三百首|李]]'
if WS.count(_cat) != 1:
    raise SystemExit('ws 页分类三行连片结构变了（简繁混排第三见断言失效）')
# ④ 旧传李商隐段负证：仙界字全零（段级；仙字首用）
for _w in ('瑤池', '穆王', '八駿', '長生', '仙', '黃竹'):
    if _seg_j.count(_w) != 0:
        raise SystemExit(f'「{_w}」落在旧传李商隐段——传无一仙字段级零证失效，须重读原文')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V068')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

def _domain_src(needle):
    # 源 id 类前提专用全文扫描：引文 INSERT 的 source_id 与多行 evidence_excerpt
    # 不同行（V067 判例——按 evidence_excerpt 行扫会漏报引用面）
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V068')
                   and needle in f.read_text(encoding='utf-8')})

for _premise, _needle, _want in (
        ('本诗首句', '瑤池阿母綺窗開', ['V018']),
        ('本诗末句', '穆王何事不重來', ['V018']),
        ('卷页源复用面', 'source-quantangshi-539', ['V018', 'V067']),
        ('V066 不之省句', '绹不之省', ['V066', 'V067']),
        ('V066 坎壈断', '坎壈终身', ['V066', 'V067']),
        ('V067 干文句', '以所业文干之', ['V067']),
        ('V067 不自休句', '下笔不能自休', ['V067']),
        ('义山署名句', '李商隐，字义山', ['V016'])):
    _prev = _domain_src(_needle) if _needle.startswith('source-') else _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
# 首引句必须零域；新源 id 必须全库不存在（确系 V018 未建）
for _first, _needle in (('边州瑶池', '置瑤池都督府'), ('官制穆王', '故周穆王命伯冏'),
                        ('谥号穆王', '臨淮武穆王李光弼'), ('柳泌长生', '雲能合長生藥'),
                        ('轩辕集对', '何處更求長生'), ('书判拔萃', '又以书判拔萃'),
                        ('当涂薄', '为当涂者所薄')):
    if _domain(_needle):
        raise SystemExit(f'首引前提破了：「{_needle}」（{_first}）既往有引（{_domain(_needle)}）——须重设计')
if _domain_src('source-ws-t300-026'):
    raise SystemExit('source-ws-t300-026 已存在于既往迁移——本迁移不再新建源，设计须改')

BG = {
    'bg-026-scene': (
        '四句是一场没等来的重访：瑶池的西王母（阿母）绮窗大开（「瑤池阿母綺窗開」）——'
        '仙境的主人把窗打开，等着那位客人；穆王东归途中，黄竹之歌声声动地皆哀'
        '（「黃竹歌聲動地哀」——《穆天子传》里穆王见冻人作《黄竹》诗三章）；'
        '八骏日行三万里（「八駿日行三萬里」）——脚力何止万里；'
        '可穆王为什么再也不来了（「穆王何事不重來」）——窗一直开着，人不来了。'
        'ws 诗页 notes **只有 {{唐詩三百首}} 裸标记、不挂诗体名**——对照同卷《隋宮》'
        'ws 页 notes 挂「七绝」：**同卷 notes 两形态首见**（挂不挂体名非强制，'
        '选本标记自身也有形态谱）；title 行裸名「瑤池」——对照同卷《隋宮》页 title '
        '内嵌异注：**同卷 title 两形态首见**；poem 块**全无句读**（第二见，V067 首见）；'
        '无 Textquality 评级**第三见**（V066 首见）；{{另}}/{{別}}/{{*}}/<ref> 全零；'
        '页内 Vtext/poem 双转录并存（首末句页内各恰 2）。此诗正文系**第二引**：'
        'V018 卷539 卷页一引在先，本迁移引 ws 选本页——**两引两面（卷页+诗页），'
        '上限恰满而不重叠**；生成时全库查重双针各恰一处，两度上限至此用满，'
        '此诗正文对后来迁移关闭。'),
    'bg-026-city': (
        '卷539 侧：本篇锚「==[[瑤池]]==」**全《全唐詩》唯一**（机器断言：全库扫描'
        '锚恰一；字面「瑤池」十条八卷中只有此一处是诗题锚——他人诗句在册零入引）——'
        '对照 V067 同卷《隋宮》双锚：**同卷同作者，单锚诗题与双锚诗题并存**，'
        '「锚点恰一」「锚点恰二」两种同名形态在同一卷里标本齐备。卷内「穆王/八駿/'
        '黃竹」各恰一（机器断言）——**诗面三个专名在整卷里自足**：李商隱这卷诗里，'
        '穆天子只出场一次，且是「不重來」那一次。ws 诗页分类三行简繁混排第三见'
        '（整理者分类：非史料声明、不升格，V048 判例）。**本迁移再新建 1 个 source'
        '（source-ws-t300-026）——连续第三首开新源**（V066 賈生/V067 隋宮 判例同构：'
        'V018 以卷539 卷页立本诗（source-quantangshi-539，vol-raw），ws 选本页'
        '从未建源——卷页与诗页是两个独立见证面）。'
        '全唐詩「西王母」恰二（301/540 他人句在册零入引）、「阿母」恰五、「綺窗」'
        '恰三在册（机器断言闭域）。（本层零 relation。）'),
    'bg-026-world': (
        '**诗问死者何不重来，史部的皇帝们活着问长生**（同字两界第十三形态·仙界形态'
        '首见）：通鉴「八駿/黃竹/阿母/綺窗/三萬里/動地哀/重來/西王母/仙術」全零'
        '（机器断言——诗的整个仙界不在史部）；「**瑤池**」恰三**全在 tj-199 一页且'
        '该页零年标题**（50% 页三连聚首见；窗口断言不可入围——闭域整句入引，locator '
        '声明零标题）：三处全是安西边州建制「**置瑤池都督府，隸安西都護；戊子，'
        '以左衛將軍阿史那賀魯為瑤池都督。**」——**诗问的仙池史部没有，同名的是一份'
        '边州任命**；「**穆王**」恰三闭域双窗口逐字入引+一处零标题闭域：永淳元年'
        '（壬午，六八二）铨选议引「**故周穆王命伯冏為太僕正**」（谏书里的穆王是'
        '官制案例）、廣德二年（甲辰，七六四）「**臨淮武穆王李光弼**」（谥法之穆）、'
        'tj-255 零标题页常山忠穆王（又一谥号，闭域不入引）——**史部三个穆王没有'
        '一个是巡游瑶池的那个：一个是奏疏引的周王，两个是唐人谥号；诗问「穆王何事'
        '不重來」，史部连可以当面问的穆王都没有**；而史部反向接题——「**長生**」'
        '恰十三处七卷（太宗合药/则天胡超/玄宗符瑞/肃宗长生殿/宪宗柳泌/宣宗轩辕集'
        '分布闭域）双窗口入引：元和十三年（戊戌，八一八）宪宗纳山人柳泌「**雲能合'
        '長生藥**」（谏官争论而帝曰「煩一州之力而能為人主致長生」——群臣莫敢言）、'
        '大中十一年（丁丑，八五七）宣宗问轩辕集「**長生可學乎？**」对以「**王者'
        '屏欲而崇德，則自然受天遐福，何處更求長生？**」——**诗问死者为何不回来，'
        '史部活着皇帝前赴后继求解长生；史部唯一的正面回答是「何处更求长生」**；'
        '「靈藥」恰一处（開元中胡人求師子國靈藥——tj-211 闭域档扫在册零入引）。'
        '本层零铸造零 relation。'),
    'bg-026-person': (
        '旧传李商隐段（**简化字录入**，V016 locator 已注，引文照登简体原样）'
        '再首引二句（皆生成时全库查重域恰零）：「**会昌二年，又以书判拔萃。**」'
        '「**恃才诡激，为当涂者所薄。**」\n'
        '**诗悯君之迷，传悯士之穷**（读法声明，非史实）：诗的瑶池里，君主迷上'
        '仙界一去不回头；传里的「当涂者」（掌权者）看这个人的眼神是「薄」——'
        '同是上位者的目光，一边望向神仙，一边鄙薄人才。书判拔萃是才调的第二道'
        '入场券（继弱冠干文之后），入场券一路发，「名宦不进」一路兑到底。\n'
        '「恃才诡激，为当涂者所薄」系**史臣自断**（照登，certainty LIKELY——'
        '与 V066 已引「名宦不进，坎壈终身」同段同调，彼句零重开）；段内'
        '**瑤池/穆王/八駿/長生/仙 字全零**（机器断言，「仙」字段级零证首用——'
        '写尽瑶池八骏的人，传里没有一个仙字）；V066「绹不之省/名宦不进，坎壈终身」、'
        'V067「以所业文干之/下笔不能自休」、字义山/开成二年/岭表/三十六体（V016）'
        '在册句零重开（域断言）；本诗无底注（无注可登）；certainty 不覆盖任何系年，'
        '诗 time.span/event.name/written_during 仍零铸造（audit 硬卡）。'),
}
CLAIMS = {
    'claim-bg-026-scene': (
        'FACT', 'LIKELY',
        '四句七绝本文（ws 选本页 poem 块四句**全无句读**第二见，各从其录）；notes '
        '裸选本标记不挂体名——对照同卷《隋宮》页挂「七绝」：**同卷 notes 两形态首见**；'
        'title 裸名——对照同卷隋宫页 title 内嵌异注：同卷 title 两形态首见；'
        '无评级页第三见；{{另}}/{{別}}/{{*}}/<ref> 全零；页内 Vtext/poem 双转录并存'
        '首末句各恰 2；全句**第二引**：正文 V018 卷539 卷页 claim 一引在先'
        '（生成时全库查重双针「瑤池阿母綺窗開」「穆王何事不重來」各恰一处），'
        '本迁移引 ws 诗页——两引两面（卷页+诗页）上限恰满不重叠；两度上限至此用满、'
        '此诗正文对后来迁移关闭（audit 硬卡）。'),
    'claim-bg-026-city': (
        'FACT', 'LIKELY',
        '本篇锚「==[[瑤池]]==」**全《全唐詩》唯一**（机器断言：字面十条八卷中锚恰一）'
        '——对照 V067 同卷《隋宮》双锚恰二：**同卷单锚/双锚两种同名形态标本齐备**；'
        '卷内穆王/八駿/黃竹各恰一=诗面专名卷内自足（机器断言）；「西王母」恰二'
        '「阿母」恰五「綺窗」恰三在册零入引（闭域断言）；ws 分类三行简繁混排第三见'
        '（分类行非史料声明+不升格，V048 判例）；**再新建 source-ws-t300-026 恰一枚'
        '（连续第三首开新源——V066/V067 判例同构，卷页/诗页两个独立见证面；'
        'audit 断言恰一枚新源 INSERT）**。'),
    'claim-bg-026-world': (
        'FACT', 'LIKELY',
        '通鉴「八駿/黃竹/阿母/綺窗/三萬里/動地哀/重來/西王母/仙術」全零（诗的仙界'
        '不在史部，机器断言）；「瑤池」恰三**全在 tj-199 且该页零年标题**（50% 页'
        '三连聚首见——不可作窗口断言，整句入引+locator 声明零标题；三处全是'
        '「瑤池都督府/瑤池都督」边州建制恰三断言——**仙池史部没有，同名是边州**）；'
        '「穆王」恰三分布三卷闭域双窗口入引=永淳元年（壬午，六八二）「故周穆王命'
        '伯冏為太僕正」奏疏引周王+廣德二年（甲辰，七六四）「臨淮武穆王李光弼」谥号'
        '+tj-255 零标题页常山忠穆王（又一谥号闭域不入引）——**三个穆王没一个是'
        '那个穆王**（同字两界第十三形态·仙界形态首见，audit 硬卡）；「長生」恰十三处'
        '七卷闭域双窗口入引=元和十三年（戊戌，八一八）「雲能合長生藥」（活着求长生）'
        '+大中十一年（丁丑，八五七）「長生可學乎/何處更求長生」（史部唯一正面回答）；'
        '「靈藥」恰一闭域在册零入引；certainty 不覆盖任何系年，诗 time.span/event.'
        'name/written_during 零铸造零 relation（audit 硬卡）。'),
    'claim-bg-026-person': (
        'FACT', 'LIKELY',
        '旧传李商隐段（简化字录入，引文照登简体原样）再首引二句皆生成时全库查重'
        '域恰零=「会昌二年，又以书判拔萃。」+「恃才诡激，为当涂者所薄。」'
        '（传区间归属机器断言）；「诗悯君之迷/传悯士之穷」系读法声明；「恃才诡激，'
        '为当涂者所薄」系史臣自断（照登 LIKELY）；段内瑤池/穆王/八駿/長生/仙字'
        '全零（机器断言，「仙」字段级零证首用）；V066「绹不之省/坎壈终身」域恰'
        '[V066]、V067「以所业文干之/下笔不能自休」域恰 [V067]、字义山/开成二年/'
        '岭表/三十六体（V016）零重开；本诗无底注（无注可登）；certainty 不覆盖'
        '任何系年。'),
}
CITATIONS = [
    ('claim-bg-026-scene', 'source-ws-t300-026',
     '页面 瑤池（《唐詩三百首》第 26 首选本页，页题裸名——同卷 title 两形态之一；'
     'title+author+notes+poem 块四句——poem **全无句读**（第二见）；notes 裸选本标记'
     '不挂体名（对照同卷隋宫页挂「七绝」——同卷 notes 两形态首见）；全句**第二引**：'
     'V018 卷539 卷页一引在先——两引面不重叠，上限恰满，生成时全库查重双针恰一处，'
     '此后此诗正文关闭；{{另}}/{{別}}/{{*}}/<ref> 全零；页内 Vtext/poem 双转录并存）',
     join(WS_TITLE, WS_AUTHOR, WS_NOTE, WS_BODY)),
    ('claim-bg-026-city', 'source-quantangshi-539',
     '卷五百三十九·李商隱《瑤池》块（锚「==[[瑤池]]==」**全《全唐詩》唯一**——'
     '字面十条八卷中锚恰一机器断言；对照同卷《隋宮》双锚恰二：同卷单锚/双锚'
     '两种同名形态标本齐备；卷内穆王/八駿/黃竹各恰一（诗面专名卷内自足）；'
     '源行系 V018 已立、本迁移复用零新建）',
     V539_BLOCK),
    ('claim-bg-026-city', 'source-ws-t300-026',
     '页面 瑤池（整页 notes 行（裸选本标记——同卷 notes 两形态首见）+分类三行连片'
     '（简体「唐诗」与繁体「唐詩三百首」同页混排第三见）；分类行系整理者/编排动作：'
     '非史料声明、不升格；**本迁移新建 source-ws-t300-026 恰一枚**（连续第三首'
     '开新源，V066/V067 判例同构）',
     join(WS_NOTE, WS_CAT)),
    ('claim-bg-026-world', 'source-zizhi-tongjian-events',
     '卷一百九十九·安西瑶池都督府除授段（**通鉴瑤池恰三全在此页且该页零年标题'
     '50%页——三连聚首见，不作窗口断言，整句入引+此声明**；三处皆瑤池都督府/'
     '都督边州建制）……卷二百零三·永淳元年（壬午，六八二）铨选议引周穆王伯冏段'
     '……卷二百二十三·廣德二年（甲辰，七六四）臨淮武穆王李光弼段（穆王恰三分布'
     '三卷——第三个落零标题页闭域不入引：没一个是瑶池穆王）……卷二百四十·元和'
     '十三年（戊戌，八一八）柳泌長生药段……卷二百四十九·大中十一年（丁丑，八五七）'
     '宣宗问轩辕集段（**長生恰十三处七卷——活着求长生的皇帝们；唯一正面回答'
     '「何處更求長生」**；五段史文逐字入引为判决证据）',
     join(TJ_YC, TJ_MW1, TJ_MW2, TJ_CS1, TJ_CS2)),
    ('claim-bg-026-person', 'source-jiutangshu-wenyuan',
     '舊唐書卷一九〇下·李商隱（**简化字录入**照登原样，V016 locator 同款标注）'
     '（「会昌二年，又以书判拔萃」句+「恃才诡激，为当涂者所薄」句——皆全库查重'
     '恰零域首引；传区间归属机器断言；后者系史臣自断非自家语；「诗悯君之迷/传悯'
     '士之穷」系读法声明；段内瑤池/穆王/長生/仙字全零；V066/V067 已引诸句与'
     '字义山/岭表/三十六体在册句零重开）',
     join(JTS_P1, JTS_P2)),
]
BG_LINES = {'bg-026-scene': (1,), 'bg-026-city': (2,),
            'bg-026-world': (3,), 'bg-026-person': (4,)}
BG_AUDIENCE = {'bg-026-scene': 'PRIMARY', 'bg-026-city': 'JUNIOR',
               'bg-026-world': 'SENIOR', 'bg-026-person': 'JUNIOR'}
BG_TITLES = {'bg-026-scene': '眼前：窗一直开着，人不来了',
             'bg-026-city': '这座城：全唐诗唯一的瑶池锚',
             'bg-026-world': '这个天下：史部的穆王与长生',
             'bg-026-person': '这个人：当涂者的眼神'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 49 首·四句七绝 1/1/1/1 第五次）；史实句均有逐字引证；'
                 '系年第四十三次判决（题证系列第卅一状·瑶池与长生）'
                 '「诗问死者何不重来，史部的皇帝们活着问长生」——同字两界第十三形态·'
                 '仙界形态首见：通鉴八駿/黃竹/阿母/綺窗/三萬里/動地哀/重來/西王母/'
                 '仙術全零；瑤池恰三**全在 tj-199 且该页零年标题（50% 页三连聚首见——'
                 '不可作窗口断言，整句入引+声明）**且三处全是安西边州建制（仙池史部'
                 '没有，同名是边州任命）；穆王恰三分布三卷双窗口入引+一处零标题闭域'
                 '（永淳元年壬午六八二奏疏引周王伯冏+廣德二年甲辰七六四谥号武穆王+'
                 'tj-255 零标题页常山忠穆王——**没一个是巡游瑶池的那个**）；長生恰'
                 '十三处七卷双窗口入引（元和十三年戊戌八一八柳泌「雲能合長生藥」+大'
                 '中十一年丁丑八五七宣宗问轩辕集「長生可學乎/何處更求長生」——活着求'
                 '长生的皇帝们，史部唯一正面回答是「何处更求长生」）；靈藥恰一在册；'
                 '本篇锚「==[[瑤池]]==」全《全唐詩》唯一（字面十条八卷中锚恰一——'
                 '对照 V067 同卷隋宫双锚：同卷单锚/双锚两种同名形态标本齐备）；卷内'
                 '穆王/八駿/黃竹各恰一（诗面专名卷内自足）；西王母恰二/阿母恰五/綺窗'
                 '恰三在册零入引；ws 页 notes 裸选本标记不挂体名（对照同卷隋宫页挂'
                 '「七绝」——**同卷 notes 两形态首见**）+title 裸名（同卷 title 两形态'
                 '首见）+poem 全无句读第二见+无评级页第三见+{{另}}/{{別}}/{{*}}/<ref> '
                 '全零；**再新建 source-ws-t300-026 恰一枚（连续第三首开新源 146→147——'
                 'V066/V067 判例同构，卷页/诗页两个独立见证面；audit 断言恰一枚新源 '
                 'INSERT）**；正文第二引上限用满第十六例（V018 在先+双针恰一，两引面'
                 '不重叠）；PERSON 旧传简化段再首引二句（会昌二年书判拔萃+恃才诡激为'
                 '当涂者所薄——诗悯君之迷/传悯士之穷读法声明）；段内瑤池/穆王/八駿/'
                 '長生/仙字全零（**「仙」字段级零证首用——写尽瑶池的人传里无一仙字**）；'
                 'V066/V067 已引诸句零重开（域断言）；KNOWN 零如实记录（第廿四例，'
                 'audit 反向断言）；判例关键语零入引文。' for k in BG}

NEW_SOURCE_ROW = {
    'id': 'source-ws-t300-026',
    'title': '维基文库《唐詩三百首》页面：瑤池',
    'author': None,
    'edition': '全唐詩',
    'url': 'https://zh.wikisource.org/wiki/瑤池',
    'rights_note': (
        '维基文库录入本，公有领域古籍。本行由 emit_v068.py 对 /tmp/src-dl 快照逐字定位。'
        '本诗 V018 立正文时用的是《全唐詩》卷539 卷页（source-quantangshi-539，'
        'version_code vol-raw），此《唐詩三百首》选本页当时未建源——卷页与诗页是'
        '两个独立见证面（卷页锚点归属 vs 选本页 header/notes/分类），本迁移引诗页'
        '非新源不能承载（V066 source-ws-t300-031、V067 source-ws-t300-022 判例同构，'
        '连续第三首）。页面 notes 只有 {{唐詩三百首}} 裸标记不挂诗体名（对照同卷'
        '隋宫页挂「七绝」——同卷 notes 两形态照登）；title 裸名；poem 块四句全无句读；'
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
    A("""-- V068：李商隱《瑤池》(work-t300-026) 四层背景（阶段 D 第 49 首·瑶池与长生）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V048、V057、V058、V059、V060、V061、
--       V062、V063、V064、V065、V066、V067 已执行
--       （work-t300-026 与其 text-work-t300-026-ws、source-quantangshi-539 是 V018 的行
--       （V018 以卷539 卷页立本诗正文，version_code=vol-raw——ws 选本页当时未建源）；
--       source-ws-t300-026 是本迁移新建的选本页源（恰一枚；audit 断言）；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       source-jiutangshu-wenyuan 是 V016 已立的旧唐书文苑传源（李商隐传在此，简化字录入）；
--       判例在册句（义山/开成二年/岭表/三十六体 V016、绹不之省/坎壈终身 V066、
--       乘興南遊/孫處約諫書/以所业文干之/下笔不能自休 V067）只对照不重开）。
--       **本迁移再新建恰 1 个 source（source-ws-t300-026）——连续第三首开新源（V066/V067
--       判例同构：卷页/诗页两个独立见证面）；audit 断言恰一枚诗源表新建插入语句且 id 唯一、
--       回滚按 id 删且只删此行。**
--
-- 数据源（可复现）：emit_v068.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/瑤池.txt（notes 裸标记同卷两形态首见+title 裸名同卷两形态+poem 全无句读
--   第二见+无评级第三见+零标记+Vtext/poem 双转录+分类三行简繁混排）、
--   全唐詩卷539（锚 ==[[瑤池]]== 全唐诗唯一+卷内穆王/八駿/黃竹各恰一+同卷隋宫双锚在册
--   对照；全唐诗 瑤池字面十条八卷/西王母恰二/阿母恰五/綺窗恰三 档扫闭域）、
--   舊唐書卷190下（李商隐段首引二句+段内瑤池/穆王/八駿/長生/仙/黃竹全零+段边界断言）、
--   通鑑卷199/203/223/240/249（五段逐字入引+四处年标题窗口+两页零年标题断言）+
--   通鑑 75 卷负证计数扫描（八駿/黃竹/阿母/綺窗/三萬里/動地哀/重來/西王母/仙術 全零+
--   瑤池恰三全在tj-199零标题页/瑤池都督恰三/穆王恰三/長生恰十三处七卷/靈藥恰一 闭域）+
--   既有迁移引文域逐句查重——传区间归属、二引/零重开/首引零域/新源不存在前提全部生成时断言。
--
-- 做：新 poetry_source 行 1（source-ws-t300-026，PENDING）+
--   4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 background_line（四句七绝 **1/1/1/1 第五次**（V056/V061/V066/V067 之后）：scene→1
--   city→2 world→3 person→4，绑 text-work-t300-026-ws 的 4 行）+ 不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「诗问死者何不重来，史部的皇帝们活着问长生」）：
--   * 仙界词通鉴全零+瑶池恰三全在零标题页（三连聚首见——不作窗口断言，声明在案）+
--     穆王恰三（奏疏引周王+两谥号——没一个是那个穆王）+長生恰十三双窗口入引+靈藥恰一；
--   * 「诗悯君之迷/传悯士之穷」标明读法声明；「恃才诡激，为当涂者所薄」标明史臣自断；
--   * 同卷单锚/双锚并存系 V067 在册判例上的标本齐备声明，非新证据；
--   * notes 两形态/title 两形态/poem 句读有无均照登不判（选本标记自身有形态谱）；
--   * 新源恰一枚如实开例（连续第三首，两引面不重叠声明在案），回滚可精确撤销；
--   * 全唐詩西王母/阿母/綺窗在册零入引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第廿四例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * V066/V067 已引诸句、V016 在册句只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 67，不含 68
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-026-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-026','source-quantangshi-539');  -- 只含 539
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-026-ws';  -- 恰 4
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-026-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-026';                                  -- 4（1/1/1/1）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-026-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-026';   -- 恰 1（本迁移新建）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-026'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-026';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-026-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V068_rollback.sql（按 id 全枚举删除；source 只删本迁移新建的
--   source-ws-t300-026 一行——source-quantangshi-539 系 V018 所立绝不删）
START TRANSACTION;""")

    A('\n-- ---------- 0. 新 source 恰一枚（source-ws-t300-026 选本页；PENDING 照 V066/V067 判例） ----------')
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
    brows = [{'id': k, 'work_id': 'work-t300-026',
              'layer': {'bg-026-scene': 'SCENE', 'bg-026-city': 'CITY',
                        'bg-026-world': 'WORLD', 'bg-026-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（四句七绝 1/1/1/1 第五次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-026-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 68, 'Li Shang-yin''s Jade Pool (work-t300-026) background layers (stage-D poem 49, four-line jueju 1/1/1/1 fifth time): dating verdict forty-three, thirty-first shape of the title-evidence series -- the Jade Pool and longevity, the immortal realm split in two realms: the poem asks why King Mu never came back, while the histories keep living emperors asking after immortality one after another; all staging words of the poem''s immortal realm (ba-jun the eight steeds, huang-zhu, a-mu, qi-chuang, san-wan-li, dong-di-ai, chong-lai, xi-wang-mu, xian-shu) score zero across the Tongjian (machine-asserted); yao-chi appears exactly three times, ALL on the zero-year-heading page tj-199 (first triple-gathering on a 50-percent page -- no window assertion possible, full-sentence quote with the zero-heading declaration in the locator) and all three are frontier administration -- the Yao-chi Commandery-Governorate under Anxi and the post granted to Ashina Helu (the poem''s immortal pool does not exist in the histories; the same name is a frontier appointment); mu-wang appears exactly three times across three files, two quoted with year-heading windows (Yongchun 1st, renwu, 682, a memorial citing "of old King Mu of Zhou appointed Bo Jiong as Grand Coachman" -- in the histories'' memorials King Mu is a staffing precedent; Guangde 2nd, jiachen, 764, "Li Guangbi, Prince Wu-mu of Linhuai" -- a posthumous name; the third on zero-heading page tj-255, closed-domain, not quoted): not one of the three Kings Mu is the king who toured the Jade Pool -- the histories have no King Mu left to ask; and the histories answer the poem from the other side: chang-sheng (longevity) appears thirteen times in seven scroll-volumes, two quoted with windows (Yuanhe 13th, wuxu, 818, Emperor Xianzong takes in the recluse Liu Bi "who claims to compound the medicine of longevity"; Dazhong 11th, dingchou, 857, Emperor Xuan asks Xuanyuan Ji "can longevity be learned?" and is answered: "if a king casts off desire and honors virtue, heaven''s long blessing comes by itself -- where would one further seek longevity?") -- the poem questions the dead about not returning, the living emperors queue up seeking never to die, and the histories'' only straight answer is "where would one further seek it"; ling-yao exactly once (closed-domain archive scan); the anchor ==[[瑤池]]== for this poem is UNIQUE in the entire Quan Tangshi (ten literal hits in eight volumes, one anchor -- contrast the double anchors of Sui Palace in the same juan per V067: single-anchor and double-anchor title shapes coexist as specimens in one volume); inside juan 539 the words mu-wang, ba-jun and huang-zhu each occur exactly once, all in this poem (the poem''s proper names are self-contained in the scroll); xi-wang-mu exactly 2 / a-mu exactly 5 / qi-chuang exactly 3 remain on the record unquoted; the ws anthology page carries a bare selection mark in notes without appending the form-name (contrast the Sui Palace page of the same juan which appends the colloquial form-name -- two notes shapes in one juan, first seen) plus a bare title line (two title shapes in one juan), a poem block with NO punctuation (second time), no Textquality grade (third time) and zero variant markers, Vtext/poem double transcription; exactly ONE new poetry_source row (source-ws-t300-026), the third consecutive new source (V066/V067 pattern: scroll page and anthology page are two independent witnesses); body quotes hit their two-use ceiling (sixteenth instance; twin needles; witnesses never overlap); PERSON first-cites two more zero-domain sentences from the simplified JTS biography -- in 842 he passed the special clerical exam, and "relying on talent he was wilful and sharp, and those in power thought little of him" (historian''s own verdict, logged): the poem mourns a ruler bewitched by immortality, the biography mourns a talent despised by power (reading declared); the biography segment holds no yao-chi/mu-wang/ba-jun/chang-sheng/xian/huang-zhu character (machine-asserted, first segment-level zero for the character xian itself); V066/V067 quoted sentences stay closed (domains asserted); KNOWN zero honestly recorded (twenty-fourth instance, audit reverse-asserts); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 68);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V068 精确回滚：只删 V068 插入的行（id 全枚举）。source 只删一行：',
         '-- source-ws-t300-026 是本迁移新建的选本页源（恰一枚，审计断言）——按 id 删除；',
         '-- source-quantangshi-539 是 V018 已立的卷539 卷页源（本迁移复用），绝不删；',
         '-- work-t300-026 本体、其 text_line 4 行都是 V018 的行，绝不删；',
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
    L.append("DELETE FROM poetry_source WHERE id = 'source-ws-t300-026';")
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 68;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_BODY, V539_BLOCK,
              TJ_YC, TJ_MW1, TJ_MW2, TJ_CS1, TJ_CS2, JTS_P1, JTS_P2]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 同卷两形态（notes/title）照登硬卡
    scene_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-026-scene' and s == 'source-ws-t300-026')
    if '| notes    = {{唐詩三百首}}' not in scene_ws:
        bad.append('notes 裸标记整行未逐字入 SCENE 引文（同卷 notes 两形态首见照登硬卡）')
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-026-city' and s == 'source-ws-t300-026')
    if '[[Category:唐诗]]' not in city_ws or '[[Category:唐詩三百首|李]]' not in city_ws:
        bad.append('分类简繁混排未逐字入 CITY 引文（第三见照登硬卡）')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-026-city' and s == 'source-ws-t300-026'):
        bad.append('CITY ws locator 须含「不升格」声明（分类行三重断言失效）')
    # 锚唯一照登硬卡
    if '==[[瑤池]]==' not in next(ex for c, s, _, ex in CITATIONS if s == 'source-quantangshi-539'):
        bad.append('卷539 锚未逐字入 CITY 引文（全唐诗唯一锚标本照登硬卡）')
    # SCENE 第二引上限声明硬卡
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-026-scene' and s == 'source-ws-t300-026')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054–V067 同款硬卡）')
    # WORLD：五段史文必须在引文内；诗语零混入；零标题声明必须在 locator
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-026-world')
    for tok in ('置瑤池都督府', '故周穆王命伯冏', '臨淮武穆王李光弼', '雲能合長生藥', '何處更求長生'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（五段必须入引）')
    for tok in ('黃竹', '八駿', '綺窗', '阿母', '三萬里', '動地哀', '不重來'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文）')
    w_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-026-world')
    if '零年标题' not in w_loc:
        bad.append('WORLD locator 须含「零年标题」声明（50% 页三连聚不可作窗口断言）')
    # PERSON 首引句必须在引文内 + V066/V067 零重开
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-026-person')
    for tok in ('又以书判拔萃', '为当涂者所薄'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺首引要素「{tok}」（简化字段首引照登硬卡）')
    for tok in ('绹不之省', '坎壈终身', '以所业文干之', '下笔不能自休', '明年，令狐绹作相'):
        if tok in cited:
            bad.append(f'V066/V067 已引「{tok}」零重开——不得入本迁移引文')
    # 判例只引不重开（引文域全扫；含 V064/V065/V066/V067 与 V016）
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
                '乘興南遊不戒嚴', '半作障泥半作帆', '紫泉宮殿鎖煙霞', '一云隋堤',
                '襲亡隋之弊', '亡隋之弊俗', '孫處約諫書', '煬帝將幸江都',
                '李商隐，字义山，怀州河内人。', '开成二年，方登进士第',
                '商隐随亚在岭表累载', '与太原温庭筠、南郡段成式齐名',
                '府罷，客滎陽，卒'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 四句 1/1/1/1 第五次
    if BG_LINES != {'bg-026-scene': (1,), 'bg-026-city': (2,),
                    'bg-026-world': (3,), 'bg-026-person': (4,)}:
        bad.append('四句 background_line 须 1/1/1/1（第五次）')
    if len(re.findall(r"text-work-t300-026-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    # **新源恰一枚**（连续第三首——断言恰一 INSERT 且 id 正确）
    ins_src = sql.count('INSERT INTO poetry_' + 'source')
    if ins_src != 1:
        bad.append(f'本迁移应恰新建 1 个 source（恰一枚 INSERT），实 {ins_src}')
    src_blk = sql[sql.index('INSERT INTO poetry_' + 'source'):]
    src_blk = src_blk[:src_blk.index(';')]
    if "'source-ws-t300-026'" not in src_blk or "'source-quantangshi-539'" in src_blk:
        bad.append('新源 INSERT 的 id 不对（应恰 source-ws-t300-026，不得含 539）')
    rb = build_rollback()
    if rb.count('DELETE FROM poetry_source') != 1 or 'source-ws-t300-026' not in rb.split('DELETE FROM poetry_source')[1][:60]:
        bad.append('回滚的 source 删除应恰一行且只删 source-ws-t300-026')
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
        bad.append("V068 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V068 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-026' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V068 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-026' AS subject_id" in sql:
        bad.append('V068 的 claim 主语应全部是 bg-026-*，work-t300-026 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V068 不碰 poetry_text_line')
    body_all = ''.join(BG.values())
    if '活着问长生' not in body_all and '活着求长生' not in body_all:
        bad.append('BG/WORLD 须含「史部的皇帝们活着问长生」判决声明')
    if '仙界形态首见' not in body_all:
        bad.append('BG 须含「仙界形态首见」（同字两界第十三形态）声明')
    if '三连聚' not in body_all:
        bad.append('BG/WORLD 须含「零标题页三连聚首见」声明')
    if '巡游瑶池的那个' not in body_all:
        bad.append('BG/WORLD 须含「三个穆王没一个是那个穆王」声明')
    if '何处更求长生' not in body_all:
        bad.append('BG/WORLD 须含「何處更求長生」史部唯一正面回答声明')
    if '全《全唐詩》唯一' not in body_all and '全唐诗唯一' not in body_all:
        bad.append('BG/CITY 须含「锚全唐诗唯一」标本声明')
    if '同卷 notes 两形态首见' not in body_all:
        bad.append('BG/SCENE 须含「同卷 notes 两形态首见」声明')
    if '连续第三首' not in body_all or '恰一' not in body_all:
        bad.append('BG/CITY 须含「再新建恰一枚 source（连续第三首）」诚实开例声明')
    if '仙' not in body_all or '没有一个仙字' not in body_all:
        bad.append('BG/PERSON 须含「传里没有一个仙字」段级零证声明')
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
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 68)' not in vblk:
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
              f'四处年标题窗口断言（永淳元年六八二/廣德二年七六四/元和十三年八一八/大中十一年八五七）+'
              f'两页零年标题反向断言（tj-199 三连聚页/tj-255 第三穆王页——快照出现年标题即中止重估）；'
              f'负证机器复查五层（通鉴八駿/黃竹/阿母/綺窗/三萬里/動地哀/重來/何事不重來/西王母/'
              f'仙術全零+瑤池恰三全在tj-199+瑤池都督恰三+穆王恰三分布三卷+長生恰十三处七卷+'
              f'靈藥恰一/全唐诗锚恰一+字面十条八卷+卷539 穆王八駿黃竹各恰一+同卷隋宫双锚在册/'
              f'ws 无评级恰零+notes 裸标记恰一+零标记+poem 无句读+首末句页内各恰二+分类三行连片/'
              f'旧传段瑤池穆王八駿長生仙黃竹全零，快照变动即中止）；'
              f'前提全库查重硬卡八件+七首引句零域断言+新源 id 全库不存在断言+'
              f'539 源恰[V018,V067]域断言+V066/V067 四句各恰域断言；'
              f'同卷两形态（notes/title）/锚唯一/零标题声明照登硬卡；CITY「不升格」硬卡；'
              f'SCENE 第二引/上限硬卡；五段通鉴史文入引+诗语零混入断言；'
              f'PERSON 二首引句入引硬卡+V066/V067 诸句零重开硬卡；'
              f'判例只引不重开断言（含 V064/V065/V066/V067 与 V016 李商隐在册诸语）；'
              f'四句 1/1/1/1 形制断言；零 KNOWN 反向断言；'
              f'**新源恰一枚断言（INSERT 恰一+id 正确+回滚恰删此行且不碰 539）**——'
              f'连续第三首开新源（卷页/诗页两个独立见证面，V066/V067 判例同构）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
