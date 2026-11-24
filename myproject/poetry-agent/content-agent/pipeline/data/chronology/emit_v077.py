#!/usr/bin/env python3
"""阶段 D 第 58 首：生成 V077——劉方平《春怨》(work-t300-360, V018 已立) 四层背景。

**恰新建 source 一枚：source-quantangshi-768**——卷768 卷页源（V076 首立卷页源之第二枚）：
金昌緒《春怨》的底本卷页携带**编者附记小传**「金昌緒，餘杭人，詩一首。」+题级{{另}}锚
「=={{另|春怨|伊州歌}}===」+**inline 全文转录**（非空壳——与 V076 253 空壳成底本两态：
壳在册/inline 在录），非新源不能逐字承载（audit 断言恰一枚 source INSERT、回滚恰删此一枚；
source-ws-t300-360 / source-ws-t300-043 / source-zizhi-tongjian-events 复用零新建）。

**征引耗尽首枚（通鉴账让渡）**：同字两界二十二形态·让渡形态首见——本诗第二句有淚痕，
通鉴「淚痕」恰一（光啟二年丙午八八六僖宗奔鳳翔宿板下解袍賜王建「以其有淚痕故也」）——
**这一处已被 V056《怨情》逐字引走用讫**（域 ['V056'] 机器断言）：通鉴的泪痕账没有第二笔，
本迁移只登记耗尽事实、**在册句零重开硬断言**（「以其有淚痕故也」不入任何引文）——同字两界
第一次以「这一账前人先记走了」的形态出现。轮到梨花：通鉴「梨花」恰一（延載元年甲午六九四
太后出梨花一枝以示宰相、宰相皆以為瑞、杜景儉獨曰「陰陽不時、咎在臣等」——史的梨花是
反常到教宰相拜谢的灾异，诗的梨花是无人开门来看的满地落白）。

**同题两诗在册首枚**：选本同时收《春怨》两首——t300-360 劉方平（七绝）/t300-043 金昌緒
（五绝，「打起黃鶯兒」）——同题两诗各有 work/text/claim/source 全套在册（机器断言）；
题面「春怨」在全唐诗快照恰两卷：143（王昌齡锚+空壳——只计数）/768（金昌緒 inline 全文
逐字入引）——**同题三诗三命运**：刘底本卷251 抓取失败（在册外零第二枚）、金底本卷768
inline 在录、王锚壳在册。一作伊州歌两处独立见证（768 锚内 {{另|春怨|伊州歌}} + 金选本页
题面 {{*|一作伊州歌}}——题面{{*}}20 页闭域）只登记不裁决；768 与金选本页诗面互异
（{{另|啼時|幾時}} vs {{另|啼時|幾迴}}、却/卻）——异文跨面见证对第二枚。

**存储面即定読面第二枚（折叠族）**：V018 ws-raw 四行净文=本页 poem 块折叠面——{{另|欲|又}}
取头部主读「欲」、两物理行行尾随行空格全裁（生成时拼合双向断言）；notes 行尾**双随行空格
全库恰一页**（机器断言唯此页——照登）；{{唐詩三百首}} 走「}}」同行随尾挂法（145 页闭域，
与 V075 body 独立行挂法 59 页闭域对成挂法两式总账）；类目四行四元组（唐詩/七言絕句/閨怨詩/
詠春詩）**全库恰一页**（金选本页五言四元组亦恰一页——同题两页各占一个唯一类目面）。

PERSON 层：**零传记之人第三、四枚合页首枚**——劉方平/金昌緒在七史快照全零（机器断言）；
金有 verbatim 记在 768 编者附记（与 V076 王之渙附记同款装置：王之渙得「詩六首」、
金昌緒得「詩一首」）；刘无附记、快照「劉方平」恰两处全在锚/署名行（017「====巫山高
劉方平著====」——「著」式锚全书 55 处唯卷017（机器断言），只计数不入引 audit 硬卡；
018 署名行）——刘只留名、金留一首。KNOWN 零第卅三例（两首 V018 KNOWN text claim 在册
零重开不碰）。四句七绝 shape：**1/1/1/1 第九次**。

用法: python3 -I emit_v077.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402

WS = pathlib.Path('/tmp/src-dl/ws-poems/春怨__劉方平_.txt').read_text(encoding='utf-8')
WJ = pathlib.Path('/tmp/src-dl/ws-poems/春怨__金昌緒_.txt').read_text(encoding='utf-8')
V768 = pathlib.Path('/tmp/src-dl/quantangshi/vol768.txt').read_text(encoding='utf-8')
V143 = pathlib.Path('/tmp/src-dl/quantangshi/vol143.txt').read_text(encoding='utf-8')
V17 = pathlib.Path('/tmp/src-dl/quantangshi/vol017.txt').read_text(encoding='utf-8')
FETCH = pathlib.Path('/tmp/src-dl/quantangshi/fetch.log').read_text(encoding='utf-8')
V018 = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/V018__tang300_ws_verified.sql').read_text(encoding='utf-8')
TJ205 = pathlib.Path('/tmp/src-dl/tongjian/tj-205.txt').read_text(encoding='utf-8')
TJ256 = pathlib.Path('/tmp/src-dl/tongjian/tj-256.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_AUTHOR = slice_between(WS, '| author   = 劉方平', '| author   = 劉方平',
                          'ws 刘页 header author(署名直证——七史无传之人只在页header留名)')
WS_POEM_A = slice_between(WS, '紗窗日落漸黃昏，金屋無人見淚痕。 ', '金屋無人見淚痕。 ',
                          'ws 刘页 poem 物理行1存原样(行尾随行空格照登)')
WS_POEM_B = slice_between(WS, '寂寞空庭春{{另|欲|又}}晚，梨花滿地不開門。 ', '梨花滿地不開門。 ',
                          'ws 刘页 poem 物理行2存原样({{另|欲|又}}异读+行尾随行空格照登)')
WS_NOTE = slice_between(WS, '| notes    ={{Textquality|75%}}↑ [[全唐詩/卷251#春怨|全唐詩·卷251]]  ',
                        '全唐詩·卷251]]  ',
                        'ws 刘页 notes 整值(七五评级+↑底本回指同行+行尾双随行空格全库恰一页——回指目标卷251不在快照抓取失败在册)')
WS_300 = slice_between(WS, '}}{{唐詩三百首}}', '}}{{唐詩三百首}}',
                        'ws {{唐詩三百首}}「}}」同行随尾挂法(145页闭域——与V075 body独立行挂法59页闭域对成挂法两式)')
WS_CAT4 = slice_between(WS, '[[Category:唐詩]]\n[[Category:七言絕句]]\n[[Category:閨怨詩]]\n[[Category:詠春詩]]',
                        '[[Category:詠春詩]]',
                        'ws 刘页类目四行四元组(唐詩/七言絕句/閨怨詩/詠春詩——全库恰一页;整理者动作不升格V048)')
FETCH_251 = slice_between(FETCH, '全唐詩/卷251: 全唐詩/卷251\n全唐詩/卷251: 全唐詩/卷251\n卷251: FAILED both name forms\n全唐詩/卷253 -> vol253.txt 2088 chars',
                          '全唐詩/卷253 -> vol253.txt 2088 chars',
                          '抓取日志第一轮「卷251: FAILED both name forms」窗口(底本卷页不在快照的机器在案凭证——在册外零第二枚;两轮各记一条共恰二条,第二轮此处后继是卷256 FAILED,负证断言)')
WJ_TITLE = slice_between(WJ, '| title    = 春怨{{*|一作伊州歌}}', '一作伊州歌}}',
                         'ws 金页 header title(题面内嵌{{*}}一作伊州歌——题面{{*}}20页闭域;选本侧归属异议独立见证)')
WJ_NOTE = slice_between(WJ, '| notes    ={{Textquality|75%}} ↑ [[全唐詩/卷768#|', '全唐詩·卷768]]',
                        'ws 金页 notes 整值(七五评级+↑底本回指同行——回指目标卷768 在本快照在册,与刘页卷251抓取失败成对照)')

WJ_POEM_A = slice_between(WJ, '{{另|打|卻}}起黃鶯兒，莫教枝上啼。 ', '莫教枝上啼。 ',
                          'ws 金页 poem 物理行1存原样({{另|打|卻}}异读+行尾随行空格照登)')
WJ_POEM_B = slice_between(WJ, '{{另|啼時|幾迴}}驚妾夢，不得到遼西。 ', '不得到遼西。 ',
                          'ws 金页 poem 物理行2存原样({{另|啼時|幾迴}}异读——768 面对作{{另|啼時|幾時}}——跨面异文见证对)')
V768_BLOCK = slice_between(V768, '==={{另|春怨|伊州歌}}===', '不得到遼西。',
                           '卷768 金昌緒题锚+inline 全诗(锚级{{另|春怨|伊州歌}}一作见证+「打{{另|起|却}}/{{另|啼時|幾時}}」存面——非空壳:与 V076 卷253 空壳成底本两态;本迁移恰新建此卷页源)')
V768_APP = slice_between(V768, '[[Author:金昌緒|金昌緒]]，餘杭人，詩一首。', '餘杭人，詩一首。',
                         '卷768 金昌緒编者附记整行(与 V076 王之渙附记同款装置:王得「詩六首」金得「詩一首」——餘杭人全快照恰一)')
TJ_LIHUA = slice_between(TJ205, '太后出梨花一枝以示宰相', '卿真宰相也！」',
                         '通鉴延載元年武后出梨花示宰相段(杜景儉「陰陽不時，咎在臣等」拜谢——史的梨花是反常到教宰相认罪的灾异;窗口断言)')

# ---------- V018 存储面重建与折叠断言（存储面即定読面第二枚；同题两诗两页各自折叠） ----------
_V18A = re.findall(r"SELECT 'text-work-t300-360-ws' AS version_id, \d+ AS line_seq, '(.*?)' AS content", V018)
_V18B = re.findall(r"SELECT 'text-work-t300-043-ws' AS version_id, \d+ AS line_seq, '(.*?)' AS content", V018)
if len(_V18A) != 4 or any(s != s.strip() for s in _V18A):
    raise SystemExit('V018 t300-360 存储面不是四行全无尾随空格——折叠断言须重估')
if len(_V18B) != 4 or any(s != s.strip() for s in _V18B):
    raise SystemExit('V018 t300-043 存储面不是四行全无尾随空格——同题另一首断言须重估')
_pmA = re.search(r'<poem>\n(.*?)\n</poem>', WS, re.S)
_pmB = re.search(r'<poem>\n(.*?)\n</poem>', WJ, re.S)
_WSLA = _pmA.group(1).split('\n')
_WSLB = _pmB.group(1).split('\n')
if len(_WSLA) != 2 or len(_WSLB) != 2:
    raise SystemExit('两选本页 poem 块不是各两物理行——照登判决须重估')
# 刘页：行1=存储1+2+随行空格；行2=存储3折{{另|欲|又}}+存储4+随行空格
if _WSLA[0] != _V18A[0] + _V18A[1] + ' ':
    raise SystemExit('ws 刘页物理行1 ≠ 存储行1+行2+随行空格——折叠断言失效')
if _WSLA[1] != _V18A[2].replace('欲', '{{另|欲|又}}', 1) + _V18A[3] + ' ':
    raise SystemExit('ws 刘页物理行2 ≠ 存储行3折{{另|欲|又}}+行4+随行空格——定読判决失效')
# 金页：两处 {{另}} 折叠（打←{{另|打|卻}}；啼時←{{另|啼時|幾迴}}）
if _WSLB[0] != '{{另|打|卻}}' + _V18B[0][1:] + _V18B[1] + ' ':
    raise SystemExit('ws 金页物理行1 ≠ {{另|打|卻}}+存储行2——同题另一首折叠断言失效')
if _WSLB[1] != '{{另|啼時|幾迴}}' + _V18B[2][2:] + _V18B[3] + ' ':
    raise SystemExit('ws 金页物理行2 ≠ {{另|啼時|幾迴}}+存储行4——同题另一首定読断言失效')
_m = re.search(r"'t300-360' AS slug, '([^']*)' AS title", V018)
if not _m or _m.group(1) != '春怨' or WS.splitlines()[1] != '| title    = 春怨':
    raise SystemExit('刘页题面(零标记) ≠ V018 work title——题面折叠断言失效')
_m = re.search(r"'t300-043' AS slug, '([^']*)' AS title", V018)
if not _m or _m.group(1) != '春怨' or '{{*|一作伊州歌}}' not in WJ_TITLE:
    raise SystemExit('金页题面(内嵌{{*}}) ≠ V018 work title「春怨」——同题两作存储一致断言失效')
# 768 inline 面与金选本页诗面互异（跨面见证对只登记不裁决——生成时确认两侧确异）
if '打{{另|起|却}}黃鶯兒' not in V768_BLOCK or '{{另|啼時|幾時}}' not in V768_BLOCK:
    raise SystemExit('卷768 inline 存面变了——跨面异文见证对断言失效')
if WS.count('{{另') != 1 or WJ.count('{{另') != 2 or WJ.count('{{*') != 1:
    raise SystemExit('两页 {{另}}/{{*}} 计数变了（刘恰一/金恰二+恰一）——标记面断言须重估')

# ---------- 通鉴年标题窗口断言 ----------
_HEAD = re.compile(r'[^\n]*(?:（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][，、]公元[〇零一二三四五六七八九十百千]+年）'
                   r'|\{\{\*\|[甲乙丙丁戊己庚辛壬癸]，西元[〇零一二三四五六七八九十百千]+年\}\})')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 90]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ205, TJ_LIHUA, '延載元年')
_window(TJ256, '以其有淚痕故也', '光啟二年')   # 只作耗尽登记断言——此句不入本迁移任何引文

# ---------- 负证机器复查 ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：梨花恰一（延載元年）/淚痕恰一（光啟二年·已被 V056 用讫）；诗面语全零
for _w, _n, _f in (('梨花', 1, 'tj-205.txt'), ('淚痕', 1, 'tj-256.txt')):
    if _alltj.count(_w) != _n or _tjf[_f].count(_w) != 1:
        raise SystemExit(f'通鉴「{_w}」不再恰一恰在 {_f}——同字两界账目闭域须重估')
for _w in ('春怨', '紗窗', '金屋', '空庭', '不開門', '黃鶯', '遼西', '妾夢', '黃昏'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零（实 {_alltj.count(_w)}）——诗面语侧闭域档扫须重估')
# ② 全唐诗快照：同题三诗三命运——刘四句净文全零（底本卷251不在）/金 inline 只在768/王锚壳在143
if sorted(_qtf) and len(_qtf) != 118:
    raise SystemExit(f'全唐詩快照卷数不再是 118（实 {len(_qtf)}）——闭域须重估')
for _ln in ('紗窗日落漸黃昏', '金屋無人見淚痕', '寂寞空庭春欲晚', '梨花滿地不開門',
            '打起黃鶯兒', '啼時驚妾夢'):
    if _allq.count(_ln) != 0:
        raise SystemExit(f'全唐詩快照「{_ln[:6]}…」不再全零——在册两态判决须重估（净文只在选本侧）')
for _ln in ('莫教枝上啼', '不得到遼西', '遼西'):
    if _allq.count(_ln) != 1:
        raise SystemExit(f'全唐詩快照「{_ln}」不再恰一（实 {_allq.count(_ln)}）——inline 唯一在册面判决须重估')
if not any(_ln in V768 for _ln in ('莫教枝上啼', '不得到遼西')):
    raise SystemExit('金诗净文不在 768——inline 在录断言失效')
_cv = sorted(n for n, t in _qtf.items() if '春怨' in t)
if _cv != ['vol143.txt', 'vol768.txt']:
    raise SystemExit(f'全唐詩快照含「春怨」卷分布变了（实 {_cv}）——同题在册谱须重估')
if _qtf['vol143.txt'].count('==[[春怨 (王昌齡)|春怨]]==') != 1 or _qtf['vol143.txt'].count('{{:春怨 (王昌齡)}}') != 1:
    raise SystemExit('卷143 王昌齡春怨锚/壳计数变了——只计数档扫须重估')
if _qtf['vol768.txt'].count('==={{另|春怨|伊州歌}}===') != 1 or V768.count('不得到遼西。') != 1:
    raise SystemExit('卷768 锚或 inline 不再唯一——CITY 切片失效')
_yz = sorted(n for n, t in _qtf.items() if '伊州歌' in t)
if _yz != ['vol128.txt', 'vol768.txt']:
    raise SystemExit(f'全唐詩快照含「伊州歌」卷分布变了（实 {_yz}）——一作见证谱须重估')
if _allq.count('餘杭人') != 1 or V768.count('餘杭人，詩一首。') != 1:
    raise SystemExit('快照「餘杭人」不再恰一恰在768——PERSON 附记切片失效')
if V768.count('==金昌緒==') != 1:
    raise SystemExit('卷768 二级作者锚不再唯一——附记挂锚断言失效')
_lv = sorted(n for n, t in _qtf.items() if '劉方平' in t)
if _lv != ['vol017.txt', 'vol018.txt'] or _qtf['vol017.txt'].count('劉方平') != 1 or _qtf['vol018.txt'].count('劉方平') != 1:
    raise SystemExit(f'快照含「劉方平」分布/计数变了（实 {_lv}）——只留名判决须重估')
if _qtf['vol017.txt'].count('巫山高 劉方平著') != 1:
    raise SystemExit('卷017「巫山高 劉方平著」不再恰一——著锚计数须重估')
_zh = [n for n, t in _qtf.items() if re.search(r'====[^=\n]+著====', t)]
if _zh != ['vol017.txt'] or len(re.findall(r'====[^=\n]+著====', _allq)) != 55:
    raise SystemExit(f'「著」式三级锚分布/计数变了（实 {len(_zh)}卷）——55 处唯卷017 断言须重估')
_kv = sorted(n for n, t in _qtf.items() if '金昌緒' in t)
if _kv != ['vol768.txt'] or V768.count('金昌緒') != 4:
    raise SystemExit(f'快照含「金昌緒」分布/计数变了（实 {_kv}）——一首之人谱须重估')
# ③ 七史快照：劉方平/金昌緒全零（零传记之人第三、四枚合页首枚）
_hist = {}
for pat in ('jts-*.txt', 'xts-*.txt', 'qss-*.txt'):
    for p in pathlib.Path('/tmp/src-dl').rglob(pat):
        _hist[p.name] = p.read_text(encoding='utf-8')
_allh = ''.join(_hist.values()) + _alltj
for _w in ('劉方平', '金昌緒'):
    if _allh.count(_w) != 0:
        raise SystemExit(f'史部快照「{_w}」不再全零（实 {_allh.count(_w)}）——零传记之人合页判决须重估')
# ④ 抓取日志：卷251 FAILED 恰二（两轮各一）；第二轮后继是卷256 FAILED（切片只取第一轮窗口）
if FETCH.count('卷251: FAILED both name forms') != 2:
    raise SystemExit(f'fetch.log「卷251: FAILED」不再恰二（实 {FETCH.count("卷251: FAILED both name forms")}）——在册外零凭证须重估')
if FETCH.count('卷251: FAILED both name forms\n全唐詩/卷256') != 1 or FETCH.count(FETCH_251) != 1:
    raise SystemExit('fetch.log 卷251 两轮窗口结构变了——第一轮窗口锚定失效')
# ⑤ ws 页形制闭域（notes双空格恰一页/四元组两页各唯一/题面{{*}}20/随尾挂145）
_wsf = {p.name: p.read_text(encoding='utf-8')
        for p in sorted(pathlib.Path('/tmp/src-dl/ws-poems').glob('*.txt'))}
if len(_wsf) != 295:
    raise SystemExit(f'ws 诗页语料不再 295 页（实 {len(_wsf)}）——闭域档扫须重估')
def _notes_tail2(t):
    for l in t.splitlines():
        if l.startswith('| notes'):
            return l.endswith('  ') and not l.endswith('   ')
    return False
_nt = {n for n, t in _wsf.items() if _notes_tail2(t)}
if _nt != {'春怨__劉方平_.txt'}:
    raise SystemExit(f'ws notes 行尾双随行空格页不再恰本页（实 {sorted(_nt)}）——全库恰一页断言失效')
_lq = '[[Category:唐詩]]\n[[Category:七言絕句]]\n[[Category:閨怨詩]]\n[[Category:詠春詩]]'
_jq = '[[Category:唐詩]]\n[[Category:五言絕句]]\n[[Category:閨怨詩]]\n[[Category:詠春詩]]'
if {n for n, t in _wsf.items() if _lq in t} != {'春怨__劉方平_.txt'}:
    raise SystemExit('ws 刘页类目四元组不再全库恰一页——唯一类目面断言失效')
if {n for n, t in _wsf.items() if _jq in t} != {'春怨__金昌緒_.txt'}:
    raise SystemExit('ws 金页类目四元组不再全库恰一页——同题两页各占唯一面断言失效')
_ts = {n for n, t in _wsf.items() if any(l.startswith('| title') and '{{*' in l for l in t.splitlines())}
if len(_ts) != 20 or '春怨__金昌緒_.txt' not in _ts:
    raise SystemExit(f'ws 题面内嵌{{{{*}}}}页不再恰 20 或金页跌出（实 {len(_ts)}）——题面异议闭域须重估')
_hg = {n for n, t in _wsf.items() if '}}{{唐詩三百首}}' in t}
if len(_hg) != 145 or '春怨__劉方平_.txt' not in _hg:
    raise SystemExit(f'ws「}}」同行随尾挂法页不再恰 145 或本页跌出（实 {len(_hg)}）——挂法两式总账须重估')

# ---------- 四层背景正文 ----------
BG = {
    'bg-360-scene': (
        '**诗的第一笔是一间正在暗下去的屋子**：「紗窗日落漸黃昏，金屋無人見淚痕」——日落、'
        '黄昏、无人、泪痕，四个状态叠成一个看不见的脸。**ws 页的 poem 块存原样**：两个物理行、'
        '每行两个七言句，行尾各带一个随行空格照登；第二行内嵌 {{另|欲|又}} 异读（「寂寞空庭'
        '春{{另|欲|又}}晚」）。**存储面即定読面第二枚**（V076 首枚）：V018 以 ws-raw 存的'
        '四行净文正是本页折叠面——「欲」取 {{另}} 头部主读、两个行尾随行空格全裁（生成时'
        '拼合断言：页物理行 = 存储行拼合+标记件）：页面存异读、库存储定读。署名 header '
        '「author = 劉方平」逐字入引——七史无传之人只在页 header 留名。**正文第二引上限'
        '用满第二十五例**（V018 句读式「紗窗日落漸黃昏，……梨花滿地不開門。」一引在先，'
        '零重开硬断言），此后此诗正文关闭。',
    ),
    'bg-360-city': (
        '**选本同时收了两首《春怨》**：t300-360 劉方平（七绝）与 t300-043 金昌緒（五绝'
        '「打起黃鶯兒」）——同题两诗各有 work/text/claim/source 全套在册（机器断言），'
        '本页类目四元组（唐詩/七言絕句/閨怨詩/詠春詩）**全库恰一页**、金页五言四元组亦'
        '全库恰一页——**同题两页各占一个唯一类目面**（整理者动作：非史料声明、不升格，'
        'V048 判例）。notes 整值入引：75% 评级+↑底本回指「全唐詩·卷251」同行——**行尾'
        '双随行空格全库恰一页**（照登）；而回指目标卷251 不在快照：抓取日志「卷251: FAILED '
        'both name forms」恰二条（两轮各一，机器登记入引）——**在册外零第二枚**（四句净文'
        '118 卷全零系底本缺席非书零）。对照金页：notes 回指卷768、768 在快照在册——'
        '「春怨」在快照恰两卷：143（王昌齡锚+空壳——只计数）/768（金昌緒 inline 全文逐字'
        '入引）——**同题三诗三命运**：刘底本不在、金 inline 在录、王锚壳在册；与 V076 卷253'
        '空壳成**底本两态**（壳在册/inline 在录）。题面「一作伊州歌」两处独立见证（768 锚内 '
        '{{另|春怨|伊州歌}}+金选本页题面 {{*}}——题面{{*}}20 页闭域）**只登记不裁决**；'
        '768 与金选本页诗面互异（{{另|啼時|幾時}} vs {{另|啼時|幾迴}}、却/卻）——**异文'
        '跨面见证对第二枚**。{{唐詩三百首}} 走「}}」同行随尾挂法（145 页闭域——与 V075 body'
        '独立行挂法 59 页闭域对成挂法两式）。**恰新建卷页源一枚 source-quantangshi-768**。',
    ),
    'bg-360-world': (
        '**诗的梨花，通鉴恰一处，那一处是灾异**（同字两界第二十二形态·让渡形态首见）：'
        '「梨花滿地不開門」——通鉴「梨花」恰一：延載元年（甲午，六九四）武后「**出梨花一枝'
        '以示宰相，宰相皆以為瑞**」，杜景儉獨曰「**今草木黃落，而此更發榮，陰陽不時，咎在'
        '臣等**」因拜谢，太后曰「卿真宰相也！」——史的梨花是反常到教宰相拜谢认罪的灾异，'
        '诗的梨花是无人开门来看的满地落白（对照判决，非史实因果）。**泪的账已被前人记走**：'
        '本诗第二句有淚痕，通鉴「淚痕」也恰一（光啟二年僖宗解御袍賜王建「以其有淚痕故也」）'
        '——但这一处 V056《怨情》已逐字引走用讫（域 [\'V056\'] 机器断言）：通鉴的泪痕账'
        '没有第二笔，本迁移只登记耗尽事实、**在册句零重开硬断言**（audit 硬卡此句不入本'
        '迁移任何引文）——同字两界二十二形态第一次以「这一账前人先记走了」的形态出现；'
        '春怨/紗窗/金屋/空庭/不開門/黃鶯/遼西/妾夢/黃昏 通鉴全零（闭域档扫，机器断言）。',
    ),
    'bg-360-person': (
        '**七史里没有这两个人——总集只留下他们的一首诗和一行附记**：劉方平/金昌緒在 '
        'jts 2 卷+xts 8 卷+qss 3 卷+通鉴 75 卷史部快照**全零**（机器断言）——零传记之人'
        '系列第三、四枚**合页首枚**（同一迁移两个人都无传）。金昌緒有总集编者附记一行：'
        '「金昌緒，餘杭人，詩一首。」（逐字入引，新源承载——与 V076 王之渙附记同款装置：'
        '王得「詩六首」、金得「詩一首」——**餘杭人三字全快照恰一**）。刘方平无附记：'
        '「劉方平」在快照恰两处全在锚/署名行（017「====巫山高 劉方平著====」——'
        '「著」式锚全书 55 处唯卷017，机器断言，只计数不入引；018 署名行）——**刘只留名、'
        '金留一首**。V018 作者判定（署名两页转录一致）在册零重开；两首 V018 text claim 已'
        '持 KNOWN（在册零重开不碰），本迁移自铸 claims 零 KNOWN（如实记录第卅三例，audit '
        '反向断言）。无传的人在总集里一个有一首、一个只剩名字——系读法声明。',
    ),
}
BG = {k: (v[0] if isinstance(v, tuple) else v) for k, v in BG.items()}

BG_LINES = {'bg-360-scene': (1,), 'bg-360-city': (2,),
            'bg-360-world': (3,), 'bg-360-person': (4,)}
BG_AUDIENCE = {'bg-360-scene': 'PRIMARY', 'bg-360-city': 'JUNIOR',
               'bg-360-world': 'SENIOR', 'bg-360-person': 'JUNIOR'}
BG_TITLES = {
    'bg-360-scene': '眼前：日落黄屋与满院空庭',
    'bg-360-city': '这座城：同题两诗与底本两态',
    'bg-360-world': '这个天下：梨花是灾异，泪账已记讫',
    'bg-360-person': '这个人：七史无名，总集留一首',
}
CLAIMS = {
    'claim-bg-360-scene': ('FACT', 'LIKELY',
        '四句取 ws 选本页 poem 块存原样面入引（两物理行各带行尾随行空格照登+第二行内嵌'
        '{{另|欲|又}} 异读；header author 署名直证同入引——七史无传之人只在页 header 留名）；'
        '**存储面即定読面第二枚**（V018 ws-raw 四行净文=本页 poem 块折叠面：欲取头部主读、'
        '两随行空格全裁——生成时拼合断言双向）；正文第二引第二十五例（V018 句读式'
        '「紗窗日落漸黃昏，……梨花滿地不開門。」一引在先零重开硬断言）'),
    'claim-bg-360-city': ('FACT', 'LIKELY',
        '**同题两诗在册首枚**：t300-360/t300-043 各有全套在册（机器断言）；本页类目四元组'
        '与金页五言四元组各全库恰一页（同题两页各占唯一类目面，V048 不升格）；notes 整值'
        '入引（75%+↑回指卷251 同行+**行尾双随行空格全库恰一页**）——卷251 不在快照'
        '（fetch.log「卷251: FAILED」恰二机器登记——**在册外零第二枚**）；对照金页回指'
        '卷768 在册+inline 全文入引；「春怨」快照恰两卷 143（锚壳只计数）/768（inline'
        '入引）——同题三诗三命运+底本两态（与 V076 空壳对照）；一作伊州歌两处见证'
        '（768 锚{{另}}+金页题面{{*}}——题面{{*}}20页闭域）只登记不裁决；768/选本诗面'
        '互异（幾時/幾迴、却/卻）异文跨面见证对第二枚；{{唐詩三百首}} 随尾挂法 145 页'
        '闭域与 V075 独立行 59 页闭域成挂法两式总账；**恰新建卷页源一枚 source-quantangshi-'
        '768**（卷页源第二枚，audit 正反断言）'),
    'claim-bg-360-world': ('FACT', 'LIKELY',
        '通鉴梨花恰一（延載元年甲午六九四武后出梨花一枝示宰相、宰相皆以為瑞、杜景儉'
        '「陰陽不時，咎在臣等」拜谢）闭域+年标题窗口机器断言入引——史的梨花是灾异、诗的'
        '梨花是无人看（对照判决非史实因果）；**同字两界第二十二形态·让渡形态首见**：淚痕'
        '通鉴恰一（光啟二年御袍）已被 V056 逐字引走用讫（域断言）——本迁移零重开硬断言'
        '（audit 硬卡「以其有淚痕故也」不入任何引文）；春怨/紗窗/金屋/空庭/不開門/黃鶯/'
        '遼西/妾夢/黃昏通鉴全零'),
    'claim-bg-360-person': ('FACT', 'LIKELY',
        '劉方平/金昌緒七史快照全零（jts 2+xts 8+qss 3+通鉴 75——零传记之人第三、四枚'
        '合页首枚，机器断言）；金附记「餘杭人，詩一首」逐字入引（新源承载——與 V076 王'
        '附记同款、餘杭人全快照恰一）；「劉方平」快照恰两处全在锚/署名行（017 巫山高'
        '劉方平著——著式锚全书55处唯卷017机器断言只计数不入引/018 署名行）——刘只留名'
        '金留一首；V018 作者判定在册零重开；KNOWN 零如实记录第卅三例'),
}
CITATIONS = [
    ('claim-bg-360-scene', 'source-ws-t300-360',
     '页面 春怨 (劉方平)（《唐詩三百首》第 360 首選本页；header author+poem 块两物理行'
     '存原样以「……」相连——行尾随行空格照登、行2内嵌 {{另|欲|又}}；**存储面即定読面'
     '第二枚**：V018 ws-raw 四行净文=本页折叠面（欲取头部主读+随行空格全裁，生成时拼合'
     '双向断言）；正文第二引第二十五例零重开',
     join(WS_AUTHOR, WS_POEM_A, WS_POEM_B)),
    ('claim-bg-360-city', 'source-ws-t300-360',
     '页面 春怨 (劉方平)（notes 整值（75% 评级+↑底本回指卷251 同行+**行尾双随行空格'
     '全库恰一页**机器断言）+{{唐詩三百首}}「}}」同行随尾挂法（145 页闭域——与 V075 body'
     '独立行 59 页闭域成挂法两式）+页尾类目四元组（唐詩/七言絕句/閨怨詩/詠春詩全库恰'
     '一页——整理者动作：非史料声明、不升格，V048）+抓取日志窗口「卷251: FAILED both '
     'name forms」恰二取第一轮（**在册外零第二枚**：底本不在快照非书零）',
     join(WS_NOTE, WS_300, WS_CAT4, FETCH_251)),
    ('claim-bg-360-city', 'source-ws-t300-043',
     '页面 春怨 (金昌緒)（同题另一首选本页——header title 内嵌 {{*|一作伊州歌}}（题面'
     '{{*}}20 页闭域）+notes 整值（75%+↑回指卷768 在册——与刘页卷251 抓取失败成对照）+poem'
     ' 块两物理行存原样（{{另|打|卻}}/{{另|啼時|幾迴}}+随行空格照登——与卷768 面互成'
     '跨面异文见证对，只登记不裁决）；V018 折叠断言同页双向',
     join(WJ_TITLE, WJ_NOTE, WJ_POEM_A, WJ_POEM_B)),
    ('claim-bg-360-city', 'source-quantangshi-768',
     '卷七百六十八·金昌緒「==={{另|春怨|伊州歌}}===」锚+inline 全诗逐字入引（**底本两态**'
     '之 inline 在录态——与 V076 卷253 空壳成谱；锚级一作伊州歌见证+「打{{另|起|却}}/'
     '{{另|啼時|幾時}}」存面与选本页互异；「春怨」快照恰两卷 143（王锚壳只计数不入引）/'
     '768——**本迁移恰新建此卷页源一枚**）',
     V768_BLOCK),
    ('claim-bg-360-world', 'source-zizhi-tongjian-events',
     '卷二百零五·延載元年（甲午，六九四）武后出梨花一枝以示宰相、宰相皆以為瑞、杜景儉'
     '「今草木黃落，而此更發榮，陰陽不時，咎在臣等」因拜谢、「卿真宰相也！」（**史的梨花'
     '是反常到教宰相认罪的灾异**）——通鉴 75 卷「梨花」唯一一处（文件闭域+年标题窗口机器'
     '断言）；淚痕恰一处（光啟二年御袍）V056 已用讫**零重开**（audit 硬卡不入引）；春怨/'
     '紗窗/金屋/空庭/不開門/黃鶯/遼西/妾夢/黃昏全零——梨花一段逐字入引为让渡形态判决证据',
     TJ_LIHUA),
    ('claim-bg-360-person', 'source-quantangshi-768',
     '卷七百六十八·金昌緒编者附记整行「[[Author:金昌緒|金昌緒]]，餘杭人，詩一首。」逐字'
     '入引（**七史无传、总集编者一行小传**：與 V076 王之渙附记同款装置——王得「詩六首」'
     '金得「詩一首」；「餘杭人」全快照恰一机器断言；「金昌緒」快照唯 768 卷恰四处；'
     '劉方平快照恰两处全在锚/署名行只计数不入引——新源承载）',
     V768_APP),
]

BG_SUMMARY = {k: '四层处境背景（阶段 D 第 58 首·四句七绝 1/1/1/1 第九次）；史实句均有逐字引证；'
                 '系年第五十二次判决（同题两诗与底本两态——三首《春怨》三种在册命运）；'
                 '同字两界第二十二形态·让渡形态首见：「诗的梨花，通鉴恰一处，那一处是灾异；'
                 '泪的账已被 V056 记走」——梨花入引（延載元年宰相声瑞）、淚痕零重开硬断言'
                 '（耗尽登记不重引）；同题两诗在册首枚（t300-360/t300-043 各全套在册——'
                 '类目四元组两页各全库唯一）；存储面即定読面第二枚（V018 ws-raw 净文=两页'
                 '折叠面，生成时拼合断言）；在册外零第二枚（卷251 FAILED 恰二机器登记——'
                 '与 V075 卷256 成对）；一作伊州歌两处见证+768/选本诗面互异只登记不裁决；'
                 '恰新建卷页源一枚 source-quantangshi-768（卷页源第二枚）+ws-360/043/通鉴'
                 '在册复用；正文第二引第二十五例零重开；零传记之人第三、四枚合页首枚'
                 '（七史全零+金附记「詩一首」+刘只留名）；KNOWN 零如实记录第卅三例'
                 '（audit 反向断言）；判例关键语零入引文。' for k in BG}


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
    A("""-- V077：劉方平《春怨》(work-t300-360) 四层背景（阶段 D 第 58 首·同题两诗与让渡形态）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V026、V033、V035、V039、V048、V049、V053、
--       V055、V056、V057、V058、V059、V060、V061、V062、V063、V064、V065、V066、V067、
--       V068、V069、V070、V071、V072、V073、V074、V075、V076 已执行
--       （work-t300-360 与其 text-work-t300-360-ws（version_code=ws-raw——V018 立此诗正文
--       用的就是《唐詩三百首》选本页，四行净文全无尾随空格——是本页 poem 块的**折叠面**：
--       {{另|欲|又}} 取头部主读「欲」、两物理行行尾随行空格全裁——**存储面即定読面第二枚**
--       （V076 首枚）：页面存异读、库存储定读）与其源 source-ws-t300-360（V018 已立的
--       选本页源，本迁移第二次复用零新建）；
--       **同题另一首** work-t300-043（金昌緒《春怨》五绝）及其 text-work-t300-043-ws /
--       source-ws-t300-043（V018 同场所立——同题两诗在册首枚：两首各全套在册机器断言；
--       本页诗面随 CITY 入引——768 与选本两面互异 {{另|啼時|幾時}}/{{另|啼時|幾迴}}、却/卻
--       只登记不裁决）；source-zizhi-tongjian-events（V014/V015 已立的通鉴事件源）是既有行；
--       **本迁移恰新建一枚 source：source-quantangshi-768**——卷768 卷页源（V076 首立
--       卷页源之第二枚），承载金昌緒编者附记小传「餘杭人，詩一首。」+题级{{另}}锚+inline
--       全文（V076 卷253 空壳/本篇 768 inline 成**底本两态**：壳在册/inline 在录）；
--       audit 断言本文件恰一枚 poetry_source INSERT、回滚恰删此一枚；
--       判例在册句（V018 句读式「紗窗日落漸黃昏，……梨花滿地不開門。」「打起黃鶯兒，……
--       不得到遼西。」+两页 'header author=' 署名直证、V056 通鉴泪痕句「以其有淚痕故也」
--       ——**泪痕账 V056 已用讫：零重开硬断言，此句不入任何引文**；V075 fetch.log 卷256
--       在册句只对照不重开）。
--
-- 数据源（可复现）：emit_v077.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/春怨__劉方平_.txt（poem 块两物理行存原样+行尾随行空格照登+{{另|欲|又}}；notes
--   整值 75%+↑回指卷251 同行+**行尾双随行空格全库恰一页**机器断言；{{唐詩三百首}}「}}」同行
--   随尾挂法 145 页闭域；类目四元组全库恰一页）、
--   ws-poems/春怨__金昌緒_.txt（同题另一首：题面 {{*|一作伊州歌}}（20 页闭域）+notes 回指
--   卷768 在册+poem 双 {{另}} 存原样）、
--   V018 存储面重建比对（t300-360 四行 vs ws 折叠面双向断言；t300-043 四行 vs 金页双折叠
--   面双向断言——同题两页各自折叠）、
--   全唐詩快照卷768（锚{{另|春怨|伊州歌}}+inline 全诗+编者附记「餘杭人，詩一首。」——
--   新源逐字承载）+卷143（王昌齡锚+空壳——只计数不入引——**同题三诗三命运**）+卷017/018
--   （劉方平恰两处全在锚/署名行——「巫山高 劉方平著」恰一、「著」式锚全书 55 处唯卷017
--   机器断言——只计数不入引）+卷128（伊州歌只计数）、
--   fetch.log（「卷251: FAILED both name forms」恰二取第一轮窗口入引——**在册外零第二枚**：
--   底本不在快照非书零；第二轮窗口后继是卷256 FAILED——负证断言）、
--   通鑑卷205（梨花段逐字入引+延載元年窗口）、卷256（淚痕窗口——只断言耗尽不入引）+
--   通鑑 75 卷负证计数扫描（梨花恰一在205+淚痕恰一在256（V056 用讫）+春怨/紗窗/金屋/空庭/
--   不開門/黃鶯/遼西/妾夢/黃昏全零）+全唐詩快照负证（六句净文全零/莫教枝上啼+不得到遼西+
--   遼西恰一在768/春怨恰两卷143,768/伊州歌恰两卷128,768/餘杭人恰一/金昌緒唯768恰四/
--   劉方平恰两卷各一）+七史快照（jts 2+xts 8+qss 3+通鉴 75）劉方平/金昌緒全零机器断言+
--   ws 全库 295 页闭域档扫（notes双空格恰1含本页/类目四元组两页各唯一/题面{{*}}20含金页/
--   随尾挂145含本页，快照变动即中止）+既有迁移引文域逐句查重——在册零重开、让渡耗尽/
--   首引零域前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 6 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 background_line（四句七绝 **1/1/1/1 第九次**：scene→1 city→2 world→3 person→4，
--   绑 text-work-t300-360-ws 的 4 行）+ 恰新建 source 一枚（source-quantangshi-768）+
--   不碰 poetry_text_line。
-- 不做：**不新建除 768 外的任何 source**（audit 断言恰一枚、回滚恰删此一枚）；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「泪的账前人先记走了」）：
--   * 「梨花灾异」「泪账耗尽让渡」系通鉴梨花段逐字入引+V056 在册域机器断言支撑的对照判决，
--     非史实因果——通鉴不记这首诗；亦不考本诗系年（编年诸说一律不采信不铸造）；
--   * 「以其有淚痕故也」**不入本迁移任何引文**（V056 已逐字用讫——audit 硬断言）：
--     通鉴泪痕恰一即恰一处已讫，无第二笔可引，只登记耗尽事实；
--   * 一作《伊州歌》：**两处见证（768 题级锚 {{另|春怨|伊州歌}} + 金选本页题面 {{*}}）
--     并列只登记不裁决**（异文只登记不裁决总判例）；欲/又、打/卻、啼時/幾迴取 {{另}}
--     头部主读系 V018 存储事实的登记非本迁移裁决；768 面却/幾時 与选本面卻/幾迴 互异
--     只登跨面见证对不裁决；
--   * 卷143 王昌齡《春怨》锚壳只计数不入引（同题三诗三命运之登记）；「巫山高 劉方平著」
--     与 55 处「著」式锚只计数不入引（署名行≠传记）；
--   * 页尾类目系整理者动作：非史料声明、不升格，V048 判例；
--   * 「七史无传」严格限于本地史部快照——不排除纸面史部另有传（无快照即不能说）；
--   * KNOWN 零如实记录（第卅三例——两首 V018 text claim 的 KNOWN 在册零重开不碰，audit
--     反向断言本迁移 SQL 无 KNOWN 字面量）；
--   * V011/V014/V015/V016/V018/V020/V026/V033/V035/V039/V048/V049/V053/V055/V056/V057/V058/
--     V059–V076 已引诸句只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 76，不含 77
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-360-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-360',
--     'source-ws-t300-043','source-quantangshi-768');                   -- 恰两行（768 本迁移新建前不存在）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-360-ws';  -- 恰 4
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-043-ws';  -- 恰 4
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-360-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-360';                                  -- 4（1/1/1/1）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-360-%';  -- 四行全 LIKELY
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-quantangshi-768';  -- 恰 1（本迁移所立）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-360'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-360';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-360-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V077_rollback.sql（按 id 全枚举删除；**source 只删一行**——
--   source-quantangshi-768 是本迁移新建的卷页源（恰一枚，审计断言）按 id 删除；
--   source-ws-t300-360 与 source-ws-t300-043 都是 V018 所立的选本页源（本迁移复用），绝不删；
--   work-t300-360/work-t300-043 本体与其 text_line 各 4 行都是 V018 的行，绝不删）
START TRANSACTION;""")

    A('\n-- ---------- 0. 新建卷页源一枚（source-quantangshi-768——V076 卷页源第二枚） ----------')
    src = [{'id': 'source-quantangshi-768', 'title': '御定全唐詩 (四庫全書本) 卷七百六十八（錢起 盧綸 … 金昌緒 曾麻幾 等合卷）',
            'author': None, 'edition': '御定全唐詩 (四庫全書本)',
            'url': 'https://zh.wikisource.org/wiki/全唐詩/卷768',
            'rights_note': '维基文库录入本，公有领域古籍。本行由 emit_v077.py 对 /tmp/src-dl 快照逐字定位。本诗（t300-360 劉方平）V018 立正文用的是《唐詩三百首》选本页（source-ws-t300-360，version_code ws-raw），此《御定全唐詩》卷768 是**同题另一首**（t300-043 金昌緒）的底本页：金页 notes ↑回指即指本页，且本页在册形态是 inline 全文转录（「打{{另|起|却}}黃鶯兒……不得到遼西。」）+题级锚 {{另|春怨|伊州歌}}+编者附记小传「金昌緒，餘杭人，詩一首。」——与 V076 卷253 空壳成底本两态（壳在册/inline 在录）。选本页与卷页是两个独立见证面（选本侧 {{*|一作伊州歌}} vs 卷页侧锚级 {{另|春怨|伊州歌}}——两处只登记不裁决），本迁移引卷页非新源不能承载（audit 断言恰一枚 source INSERT、回滚恰删此一枚）。核验状态保持 PENDING。',
            'verification_status': 'PENDING', 'source_kind': 'POETRY_COLLECTION',
            'reliability': 'HIGH'}]
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            src, 'x.id = t.id'))

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
    brows = [{'id': k, 'work_id': 'work-t300-360',
              'layer': {'bg-360-scene': 'SCENE', 'bg-360-city': 'CITY',
                        'bg-360-world': 'WORLD', 'bg-360-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（四句七绝 1/1/1/1 第九次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-360-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 77, 'Liu Fang-ping''s Spring Sorrow (work-t300-360) background layers (stage-D poem 58, one of two poems sharing the title in the anthology; four-line seven-character quatrain 1/1/1/1, ninth time): dating verdict fifty-two, thirty-eighth shape of the title-evidence series -- two Spring Sorrows in one anthology, three fates on the record. THE SAME-TITLE PAIR ON RECORD, first seen: the anthology carries two poems titled 春怨 -- t300-360 Liu Fang-ping (seven-character) and t300-043 Jin Changxu (five-character, "Hit the oriole off the branch") -- each with its own full work/text/claim/source stack (machine-asserted); their anthology pages each own a unique category quadruple in the whole 295-page corpus (seven-character and five-character runs, one page each -- curator action, not upgraded, V048). THREE FATES OF THE TITLE in the 118-volume Quan-Tangshi snapshot: the literal appears in exactly two volumes -- 143 (Wang Changling, anchor plus empty shell: counted only, never quoted) and 768 (Jin Changxu, inline full text quoted verbatim) -- while Liu''s base volume 251 is absent from the snapshot: the fetch log says "卷251: FAILED both name forms" exactly twice (both rounds; first-round window quoted) -- OUT-OF-CATALOG ZERO, second instance (paired with V075''s volume 256): the six clean lines scoring zero across 118 volumes is a snapshot zero, not a book zero. BASE-BOOK TWO STATES: volume 768 holds Jin''s poem INLINE (unlike V076''s volume-253 empty shell): anchor, poem body and an editors'' appendix mini-bio on one page. ALTERNATIVE TITLE, two witnesses, registered not adjudicated: 一作伊州歌 appears independently inside the volume-768 anchor ({{另|春怨|伊州歌}}) and in the anthology page''s title field ({{*}}, a closed set of exactly 20 pages); the 768 face and the anthology face differ line by line ({{另|啼時|幾時}} vs {{另|啼時|幾迴}}, 却 vs 卻) -- cross-face variant witnesses, second pair. THE STORED FACE IS THE READING FACE, second of its series: both poems were stored by V018 as the folded face of their anthology pages (欲 from the head of {{另|欲|又}}, both physical lines'' trailing spaces trimmed; Jin''s page folds twice: 打 from {{另|打|卻}}, 啼時 from {{另|啼時|幾迴}}) -- generator asserts the pair-join both directions for each page. Page form registered: the notes field of this page ends in a DOUBLE trailing space -- exactly one page in the whole corpus (machine-asserted); the {{唐詩三百首}} marker here hangs in the same line right after the header close (}}{{ form, a closed set of 145 pages), paired with V075''s standalone-body hang (59 pages): two hang styles, one ledger. WORLD: same-character-two-realms, twenty-second shape -- the conceded shape, first seen. The poem''s pear blossom: the Tongjian has exactly one (Yanzai 1, jiawu, 694: the empress dowager "sent a branch of pear blossom out to show the chancellors, and all the chancellors took it for an omen of fortune" while Du Jingjian alone said "now grass and trees are yellow and falling, yet this one blooms out of season -- the fault in the balance of yin and yang lies with us ministers", bowed and thanked; the history''s pear blossom is an anomaly so out of season it made a chancellor confess, the poem''s pear blossom is white all over the ground with nobody opening the door to see it). But the tears: the poem''s second line carries tear traces, and the Tongjian''s ledger of 淚痕 has exactly one entry (Guangqi 2, bingwu, 886: Xizong, sleeping under a plank, unfastened his imperial robe for Wang Jian "because it has tear traces on it") -- and that one entry was already quoted verbatim and used up by V056 (domain [''V056''] machine-asserted): for the first time in twenty-two shapes, this ledger was booked by a predecessor -- the migration registers the exhaustion and hard-asserts the closed sentence never re-enters any citation of this migration (audit). 春怨/紗窗/金屋/空庭/不開門/黃鶯/遼西/妾夢/黃昏 all zero in the Tongjian (machine-asserted). PERSON: ZERO-BIOGRAPHY PAIR, third and fourth of the series, first on one page: Liu Fang-ping and Jin Changxu score zero across the local history snapshots (2 JTS + 8 XTS + 3 QSS + 75 Tongjian, machine-asserted). Jin has one editors'' appendix line, quoted verbatim as this migration''s PERSON evidence (the same apparatus as V076''s Wang Zhihuan note: Wang got "six poems", Jin gets "one poem"; 餘杭人 appears exactly once in the whole snapshot). Liu has no note at all: 劉方平 appears in exactly two snapshot places, both anchor/byline lines (017 "====巫山高 劉方平著====" -- the "著"-style heading occurs 55 times corpus-wide, all in volume 017, machine-asserted, counted only, never quoted; 018 a byline): Liu keeps a name, Jin keeps one poem. NEW SOURCES: exactly one -- source-quantangshi-768, the volume page (second volume-page source ever, following V076; the audit asserts exactly one source insert and exactly one source delete in the rollback), while ws-t300-360 (second reuse), ws-t300-043 (second reuse) and the Tongjian events source are existing rows. Body use-ceiling, twenty-fifth instance: V018''s punctuated excerpt on this poem stands first and is never re-opened (hard assertion); likewise V018''s header-author excerpts for both pages and its punctuated excerpt for the sister poem stay closed. KNOWN zero honestly recorded (thirty-third instance -- both V018 text claims keep their KNOWN and stay untouched; audit reverse-asserts no KNOWN literal in this migration); closed precedent keywords (both punctuated full quotes, both header-author lines, V056''s tear-trace sentence, V075''s fetch-log line) stay out of all citations of this migration.'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 77);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V077 精确回滚：只删 V077 插入的行（id 全枚举）。**source 只删一行**——',
         '-- source-quantangshi-768 是本迁移新建的卷页源（恰一枚，审计断言），按 id 删除；',
         '-- source-ws-t300-360 与 source-ws-t300-043 都是 V018 所立的选本页源（本迁移复用），绝不删；',
         '-- work-t300-360 / work-t300-043 本体与其 text_line 各 4 行都是 V018 的行，绝不删；',
         '-- source-zizhi-tongjian-events 为他迁移所立，零删除。',
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
    L.append('DELETE FROM poetry_source WHERE id = ' + sql_s('source-quantangshi-768') + ';')
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 77;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V077')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

def _domain_src(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V077')
                   and needle in f.read_text(encoding='utf-8')})

for _premise, _needle, _want in (
        ('本诗首句面(V018 句读式一引——零重开前提)', '紗窗日落漸黃昏', ['V018']),
        ('本诗末句面(V018 句读式收尾)', '梨花滿地不開門', ['V018']),
        ('V018 本诗句读式全引不重开', '紗窗日落漸黃昏，……梨花滿地不開門。', ['V018']),
        ('同题另一首 V018 句读式全引不重开', '打起黃鶯兒，……不得到遼西。', ['V018']),
        ('本页署名行(V018 header 直证在册)', 'header author=劉方平', ['V018']),
        ('金页署名行(V018 header 直证在册)', 'header author=金昌緒', ['V018']),
        ('淚痕通鉴唯一处(V056 已逐字用讫——让渡前提/零重开硬卡)', '以其有淚痕故也', ['V056']),
        ('本诗选本页源已立(V018——第二次复用前提)', 'source-ws-t300-360', ['V018']),
        ('同题另一首选本页源已立(V018——第二次复用前提)', 'source-ws-t300-043', ['V018']),
        ('新源未立前提(source-quantangshi-768 系本迁移新建)', 'source-quantangshi-768', [])):
    _prev = _domain_src(_needle) if (_needle.startswith('source-')) else _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
for _first, _needle in (('页署名切片(原文面)', '| author   = 劉方平'),
                        ('页物理行1存原样', '紗窗日落漸黃昏，金屋無人見淚痕。 '),
                        ('页物理行2存原样({{另|欲|又}}面)', '寂寞空庭春{{另|欲|又}}晚，梨花滿地不開門。 '),
                        ('notes 双随行空格整值', '| notes    ={{Textquality|75%}}↑ [[全唐詩/卷251#春怨|全唐詩·卷251]]  '),
                        ('类目四元组', '[[Category:七言絕句]]\n[[Category:閨怨詩]]\n[[Category:詠春詩]]'),
                        ('抓取日志卷251窗口', '卷251: FAILED both name forms\n全唐詩/卷253 -> vol253.txt 2088 chars'),
                        ('金页题面{{*}}', '| title    = 春怨{{*|一作伊州歌}}'),
                        ('一作伊州歌', '一作伊州歌'),
                        ('金页 notes 整值', '| notes    ={{Textquality|75%}} ↑ [[全唐詩/卷768#|全唐詩·卷768]]'),
                        ('金页物理行1', '{{另|打|卻}}起黃鶯兒，莫教枝上啼。 '),
                        ('金页物理行2', '{{另|啼時|幾迴}}驚妾夢，不得到遼西。 '),
                        ('卷768 锚级一作', '{{另|春怨|伊州歌}}'),
                        ('卷768 inline 打面', '打{{另|起|却}}'),
                        ('卷768 inline 啼時面', '{{另|啼時|幾時}}'),
                        ('卷768 二级作者锚', '==金昌緒=='),
                        ('金昌緒附记整行', '[[Author:金昌緒|金昌緒]]，餘杭人，詩一首。'),
                        ('通鉴梨花段首', '太后出梨花一枝以示宰相'),
                        ('通鉴梨花段尾', '卿真宰相也！」'),
                        ('陰陽不時', '陰陽不時'),
                        ('杜景儉', '杜景儉')):
    if _domain(_needle):
        raise SystemExit(f'首引句「{_first}」既往域非零——须换句或降级')


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_AUTHOR, WS_POEM_A, WS_POEM_B, WS_NOTE, WS_300, WS_CAT4, FETCH_251,
              WJ_TITLE, WJ_NOTE, WJ_POEM_A, WJ_POEM_B, V768_BLOCK, V768_APP, TJ_LIHUA]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # SCENE：折叠断言的标记件必须逐字在引文内（存储面即定読面第二枚硬卡）
    sc = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-360-scene' and s == 'source-ws-t300-360')
    if '{{另|欲|又}}' not in sc:
        bad.append('{{另|欲|又}} 未入 SCENE 引文（存储面即定読面第二枚硬卡）')
    if WS_POEM_A[-1] != ' ' or WS_POEM_B[-1] != ' ':
        bad.append('poem 两物理行行尾随行空格面未入 SCENE 引文（照登硬卡）')
    if '紗窗日落漸黃昏，……梨花滿地不開門。' in cited:
        bad.append('V018 句读式引文重开了——本迁移引 poem 存原样面，句读式不重开')
    if '打起黃鶯兒，……不得到遼西。' in cited:
        bad.append('V018 同题另一首句读式引文重开了')
    # CITY：底本两态——768 三件必须逐字入引；金页四件必须入引；只计数件不得入引
    q768 = next(ex for c, s, _, ex in CITATIONS if s == 'source-quantangshi-768' and c == 'claim-bg-360-city')
    for tok in ('==={{另|春怨|伊州歌}}===', '打{{另|起|却}}黃鶯兒，莫教枝上啼。', '{{另|啼時|幾時}}驚妾夢，不得到遼西。'):
        if tok not in q768:
            bad.append(f'卷768 inline 在录件「{tok[:12]}…」未入 CITY 引文（底本两态硬卡）')
    wj = next(ex for c, s, _, ex in CITATIONS if s == 'source-ws-t300-043')
    for tok in ('{{*|一作伊州歌}}', '{{另|打|卻}}', '{{另|啼時|幾迴}}'):
        if tok not in wj:
            bad.append(f'金选本页件「{tok}」未入 CITY 引文（同题两诗在册/跨面见证对硬卡）')
    ws_c = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-360-city' and s == 'source-ws-t300-360')
    if '卷251: FAILED both name forms' not in ws_c:
        bad.append('fetch.log 卷251 窗口未入 CITY 诗页引文（在册外零第二枚硬卡）')
    if WS_NOTE not in ws_c or WS_CAT4 not in ws_c:
        bad.append('notes 双随行空格整值/类目四元组未入 CITY 诗页引文（全库恰一页硬卡）')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-360-city' and s == 'source-ws-t300-360'):
        bad.append('CITY 诗页 locator 须含「不升格」声明')
    for tok in ('==[[春怨 (王昌齡)|春怨]]==', '{{:春怨 (王昌齡)}}', '春怨 (王昌齡)',
                '巫山高 劉方平著', '===[[巫山高', 'Category:唐詩三百首'):
        if tok in cited:
            bad.append(f'只计数件「{tok[:12]}…」混入本迁移引文（同题三诗三命运/署名行≠传记硬卡）')
    # WORLD：梨花段必须逐字入引；淚痕耗尽句零入引（让渡形态首枚硬卡）；诗语不得入通鉴引文
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-360-world')
    for tok in ('太后出梨花一枝以示宰相', '宰相皆以為瑞', '陰陽不時，咎在臣等', '卿真宰相也！」'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴梨花段要素「{tok}」（灾异判决硬卡）')
    for tok in ('以其有淚痕故也', '解御袍賜建'):
        if tok in cited:
            bad.append(f'V056 耗尽在册句「{tok[:8]}…」混入本迁移引文——让渡形态首枚，零重开硬断言失效')
    for tok in ('紗窗日落漸黃昏', '金屋無人見淚痕', '寂寞空庭春欲晚', '梨花滿地不開門'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文——SCENE 引诗面系另一事）')
    w_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-360-world')
    if '梨花' not in w_loc or '淚痕' not in w_loc:
        bad.append('WORLD locator 须点出梨花/淚痕（让渡形态声明）')
    # PERSON：附记必须逐字入引；locator 含同款装置声明
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-360-person')
    for tok in ('金昌緒', '餘杭人，詩一首。'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺附记要素「{tok}」（编者一行小传硬卡）')
    if '同款装置' not in next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-360-person'):
        bad.append('PERSON locator 须含「与 V076 附记同款装置」声明')
    # 判例只引不重开
    for tok in ('紗窗日落漸黃昏，……梨花滿地不開門。', '打起黃鶯兒，……不得到遼西。',
                'header author=劉方平', 'header author=金昌緒', '以其有淚痕故也',
                '卷256: FAILED', '白日依山盡', '幽映每白日', '道由白雲盡', '玉皇授白雲先生高駢',
                '而能試文三篇', '開青溪道', '車如流水', '客去波平檻', '本以高難飽',
                '君問歸期未有期', 'theme2   = 詠春詩', '↑ [[全唐詩/卷256', '{{:闕題',
                '時樞等七人已至滑州', '皆並命于白馬驛', '投屍於河。', '如出九泉睹白日',
                '宜投之黃河', '刻青石為奇字'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    if BG_LINES != {'bg-360-scene': (1,), 'bg-360-city': (2,),
                    'bg-360-world': (3,), 'bg-360-person': (4,)}:
        bad.append('四句 background_line 须 1/1/1/1 顺次（四句七绝常规·第九次）')
    if len(re.findall(r"text-work-t300-360-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    # 恰新建 source 一枚（卷页源第二枚）
    if sql.count('INSERT INTO poetry_' + 'source') != 1:
        bad.append('V077 有意恰新建一枚 source（source-quantangshi-768），但 SQL 里 source INSERT 数不是 1')
    if sql_s('source-quantangshi-768') not in sql:
        bad.append('source-quantangshi-768 未入 SQL')
    rb = build_rollback()
    if rb.count('DELETE FROM poetry_' + 'source') != 1:
        bad.append('V077 恰新建一枚 source，回滚须恰含一行 source 删除')
    if 'DELETE FROM poetry_source WHERE id = ' + sql_s('source-quantangshi-768') not in rb:
        bad.append('回滚的 source 删除行不是 source-quantangshi-768')
    for keep in ('source-ws-t300-360', 'source-ws-t300-043'):
        if f'DELETE FROM poetry_source WHERE id = ' + sql_s(keep) in rb:
            bad.append(f'回滚误删既有源 {keep}')
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录第卅三例）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if len(CITATIONS) != 6:
        bad.append('本迁移引文应为 6 组')
    if "'written_during' AS predicate" in sql:
        bad.append("V077 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V077 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-360' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V077 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-360' AS subject_id" in sql or "SELECT 'work-t300-043' AS subject_id" in sql:
        bad.append('V077 的 claim 主语应全部是 bg-360-*，两首 work 都不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V077 不碰 poetry_text_line')
    body_all = ''.join(BG.values())
    if '让渡形态' not in body_all:
        bad.append('BG 须含「让渡形态」（同字两界第二十二形态）声明')
    if '在册外零' not in body_all:
        bad.append('BG/CITY 须含「在册外零第二枚」声明')
    if '存储面即定読面第二枚' not in body_all:
        bad.append('BG/SCENE 须含「存储面即定読面第二枚」声明')
    if '同题两诗' not in body_all:
        bad.append('BG/CITY 须含「同题两诗在册首枚」声明')
    if '同题三诗三命运' not in body_all:
        bad.append('BG/CITY 须含「同题三诗三命运」声明')
    if '零传记之人' not in body_all:
        bad.append('BG/PERSON 须含「零传记之人第三、四枚合页首枚」声明')
    if '只登记不裁决' not in body_all:
        bad.append('BG/CITY 须含一作伊州歌「只登记不裁决」声明')
    if 'V048' not in body_all:
        bad.append('BG/CITY 须含类目不升格（V048）声明')
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
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 77)' not in vblk:
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 14 切片逐字过审且全部进引文；'
              f'V018 存储面两页各自重建 vs ws poem 块折叠面（{{{{另|欲|又}}}}取头部主读+两随行空格全裁；'
              f'金页双折叠 打←{{{{另|打|卻}}}}/啼時←{{{{另|啼時|幾迴}}}}）双向断言+题面断言（刘零标记/金内嵌{{{{*}}}}）；'
              f'两处年标题窗口断言（延載元年六九四/光啟二年八八六——后者只作耗尽登记断言不入引）；'
              f'负证机器复查五层（通鉴梨花恰一在205+淚痕恰一在256+春怨/紗窗/金屋/空庭/不開門/黃鶯/'
              f'遼西/妾夢/黃昏全零/全唐诗六句净文全零+莫教枝上啼/不得到遼西/遼西恰一在768+春怨恰两卷'
              f'143,768+143锚壳各恰一+伊州歌恰两卷128,768+餘杭人恰一+金昌緒唯768恰四+劉方平恰两卷各一+'
              f'巫山高著恰一+55著锚唯017/fetch 卷251 FAILED恰二+第二轮窗口负证+史部劉方平/金昌緒全零/'
              f'ws295 页 notes双空格恰1含本页+四元组两页各唯一+题面{{{{*}}}}20含金页+随尾挂145含本页，'
              f'快照变动即中止）；'
              f'前提全库查重硬卡十件+二十首引句零域断言+新源未立前提（source-quantangshi-768 零域）断言+'
              f'淚痕耗尽前提（域恰 ['"'"'V056'"'"']）断言；'
              f'SCENE {{另|欲|又}}+随行空格入引+两首 V018 句读式引文零重开断言；'
              f'CITY 768 三件套入引（底本两态）+金页三件入引（跨面见证对）+卷251 窗口入引+「不升格」硬卡+'
              f'只计数件（143锚壳/巫山高著）零入引断言；'
              f'通鉴梨花段四要素入引+「以其有淚痕故也/解御袍賜建」零入引硬断言（让渡形态首枚）+诗语零混入断言；'
              f'PERSON 附记要素入引硬卡+「同款装置」声明；'
              f'判例只引不重开断言（含 V018 两页署名/两句读式、V056 淚痕句、V075 fetch 句、V076 诸句在内）；'
              f'四句 1/1/1/1 形制断言；零 KNOWN 反向断言；恰新建 source 一枚正反断言+回滚恰删此一枚断言+'
              f'既有两源零删除断言；幂等/宽度/主键/幂等版本账本守卫全数过审')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql)} B) + {args.out_rollback} ({len(rb)} B)')


if __name__ == '__main__':
    main()
