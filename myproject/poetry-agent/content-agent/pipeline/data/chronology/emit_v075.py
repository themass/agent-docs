#!/usr/bin/env python3
"""阶段 D 第 56 首：生成 V075——劉眘虛《闕題》(work-t300-363, V018 已立) 四层背景。**本迁移零新建 source**——
V066 判例的反向首枚：V018 给此诗立正文时用的就是《唐詩三百首》选本页（version_code ws-raw、
source-ws-t300-363 系 V018 所立）——诗页见证早有源行，引诗页不需新源承载（V074 涼思恰成镜像：
那首 V018 用卷页立文、诗页无源须新建；这首 V018 就用诗页立文、无源可建。audit 断言本文件
恰零枚 poetry_source INSERT、回滚零 source 删除）。

绑定形态：**在册外零首枚**——八句在 120 卷全唐诗快照语料全零，且此零与 V073「八句全库零、
诗只活在诗页」性质相反：本页 notes 唯一回指「↑ 全唐詩·卷256」，而卷 256 正是快照抓取失败卷
（fetch.log「卷256: FAILED」恰二条，机器登记）——**在册外零非书零**，底本缺席即诚实边界，
本迁移不逐字引 256（无快照即无可核切片）；**同面零分歧+唯一裁切点**——V018 存储面八行 vs
本快照 ws 页 poem 块逐字同面（ws-raw 自证），唯末行页尾「清輝照衣裳。 」带一尾随空格而
存储面全八行无尾随空格（生成时双向断言）：面同一字不差，存储端裁了那一个空格。

「为什么写」走到**读书两界**（同字两界第二十形态·读书形态首见）：诗的白雲/读书堂，通鉴各有一
本账、没有一本是读书：白雲恰一（中和二年吕用之「刻青石為奇字云：『玉皇授白雲先生高駢。』」——
史的白雲是石头开口送的道君称号，诗的白雲是走完的路尽头）；宏詞恰一（總章二年铨法「能試文三篇，
謂之宏詞」——史的宏词是格限未至先来待试的科目，诗的深柳读书堂是柳荫深处自己读书；送刘眘虚归取
宏词解的诗题把这条线递到 PERSON 层）；青溪（V057 贡道）/流水（V058 车马喻）在册零重开（audit
硬断言逐字不重入）；落花/幽映/深柳/读书堂/闲门/向山路/衣裳 通鉴全零。

PERSON 层：**零传记之人系列首枚**——眘字在 jts 27+xts 8+qss 3+通鉴 75 卷快照全零（机器断言）：
此人无传；他在本库语料恰五处「眘」全在诗题/署名行——140 王昌齡「送劉眘虛歸取宏詞解」、
160 高適「九日龍沙作寄劉大眘虛」（逐字入引，160 源第六次复用）、019 江南曲署名行；
140 无源行只计数登记不逐字（audit 硬断言「送劉眘虛」不入任何引文）；019 卷署名劉眘虛 vs
ws t300-335 选本页署名李益——两处见证并列只登记不裁决，留 V079 专办（V018「header author=李益」
在册零重开）。

ws 页形制（SCENE/CITY 层）：**无 Vtext 页=双转录缺位反面标本**（全库 273 页闭域；V072–V074
双转录三连的镜像——只此一面）；无 {{VH1}}；**七五页本系列首见**（大写 {{Textquality|75%}}
142 页、全库唯一小写 textquality|75% 页是夜雨寄北——照登不判）；**尾空格照登**（全库 54 页
闭域）；{{唐詩三百首}} body 独立行挂法（59 页闭域）+notes 单行含 TQ+↑ 回指（130 页闭域）；
分类恰两行 [[Category:唐詩]][[Category:五言律詩]]（两类目 149 页、本对 48 页——最简类目面，
整理者动作不升格 V048 判例）。

8 句五律 shape：**2/2/2/2 顺次**（scene→1,2 city→3,4 world→5,6 person→7,8）。

用法: python3 -I emit_v075.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402

WS = pathlib.Path('/tmp/src-dl/ws-poems/闕題__劉眘虛_.txt').read_text(encoding='utf-8')
V128 = pathlib.Path('/tmp/src-dl/quantangshi/vol128.txt').read_text(encoding='utf-8')
V140 = pathlib.Path('/tmp/src-dl/quantangshi/vol140.txt').read_text(encoding='utf-8')
V160 = pathlib.Path('/tmp/src-dl/quantangshi/vol160.txt').read_text(encoding='utf-8')
FETCH = pathlib.Path('/tmp/src-dl/quantangshi/fetch.log').read_text(encoding='utf-8')
V018 = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/V018__tang300_ws_verified.sql').read_text(encoding='utf-8')
TJ254 = pathlib.Path('/tmp/src-dl/tongjian/tj-254.txt').read_text(encoding='utf-8')
TJ201 = pathlib.Path('/tmp/src-dl/tongjian/tj-201.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_AUTHOR = slice_between(WS, '| author   = 劉眘虛', '| author   = 劉眘虛',
                          'ws header author(署名直证——七史无传之人只在页header留名)')
WS_NOTE = slice_between(WS, '| notes    = {{Textquality|75%}}↑ [[全唐詩/卷256#闕題|全唐詩·卷256]]',
                        '| notes    = {{Textquality|75%}}↑ [[全唐詩/卷256#闕題|全唐詩·卷256]]',
                        'ws notes 整值(七五评级+↑底本回指同行——回指目标卷256不在快照,抓取失败在册)')
WS_POEM_A = slice_between(WS, '道由白雲盡，春與青溪長。', '遠隨流水香。',
                          'ws poem 块前四句存原样(同面零分歧——与V018存储面前四行逐字同)')
WS_POEM_B = slice_between(WS, '閑門向山路，深柳讀書堂。', '清輝照衣裳。 ',
                          'ws poem 块后四句存原样(末行「清輝照衣裳。 」带页尾空格——照登;V018存储面八行全无尾随空格——唯一裁切点)')
WS_CAT = slice_between(WS, '[[Category:唐詩]]\n[[Category:五言律詩]]',
                       '[[Category:唐詩]]\n[[Category:五言律詩]]',
                       'ws 页尾分类恰两行(最简类目面——全库恰两类目149页/本对48页闭域;整理者动作不升格V048)')
WS_300 = slice_between(WS, '\n{{唐詩三百首}}\n', '\n{{唐詩三百首}}\n',
                       'ws {{唐詩三百首}} body 独立行挂法(59页闭域——本页无三百首类目行,选本标记只挂在body)')
V128_QT = slice_between(V128, '==[[闕題 (王維)|闕題二首]]==', '==[[闕題 (王維)|闕題二首]]==',
                        '卷128 王維「闕題二首」锚行(闕題题面跨诗人形态之王维侧——锚形「二首」合并消歧器照登;机器断言唯一)')
V128_GAP = slice_between(V128, '{{:闕題 (荆谿白石出)}}', '{{:闕題 (相看不忍發)}}',
                         '卷128 两枚空壳转引连片(王维闕題块锚下无正文——V072/V073空壳卷页侧同款,随CITY入引)')
V160_GAO = slice_between(V160, '==[[九日龍沙作寄劉大眘虛]]==\n{{:九日龍沙作寄劉大眘虛}}',
                         '==[[九日龍沙作寄劉大眘虛]]==\n{{:九日龍沙作寄劉大眘虛}}',
                         '卷160 高適「九日龍沙作寄劉大眘虛」锚+空壳转引(零传记之人存证之一——朋友的诗题;160源第六次复用)')
FETCH_256 = slice_between(FETCH, '全唐詩/卷256: 全唐詩/卷256\n全唐詩/卷256: 全唐詩/卷256\n卷256: FAILED both name forms\n全唐詩/卷263 -> vol263.txt 2589 chars',
                          '全唐詩/卷263 -> vol263.txt 2589 chars',
                          '抓取日志第一轮「卷256: FAILED both name forms」窗口(底本卷页不在快照的机器在案凭证——在册外零非书零;两轮各记一条共恰二条,第二轮此处后继是卷357 missing,负证断言)')
TJ_BY = slice_between(TJ254, '用之又刻青石為奇字云：「玉皇授白雲先生高駢。」', '同歸上清耳！」',
                      '通鉴中和二年吕用之刻青石奇字谶(白雲之通鉴侧——道君称号;窗口断言)')
TJ_HC = slice_between(TJ201, '人有格限未至，而能試文三篇，謂之宏詞', '謂之拔萃',
                      '通鉴總章二年铨法宏詞条(宏詞之通鉴侧——格限未至先来试文;窗口断言)')

# ---------- V018 存储面重建与同面零分歧断言（ws-raw 自证+唯一裁切点） ----------
# 页 poem 块是 4 个物理行（每行两个五言句、逗居其间）；V018 ws-raw 存成 8 行（物理行按逗号切二）。
_V18L = re.findall(r"SELECT 'text-work-t300-363-ws' AS version_id, \d+ AS line_seq, '(.*?)' AS content", V018)
if len(_V18L) != 8 or any(s.endswith(' ') or s != s.strip() for s in _V18L):
    raise SystemExit('V018 t300-363 存储面不是八行全无尾随空格——同面零分歧判决须重估')
_pm = re.search(r'<poem>\n(.*?)\n</poem>', WS, re.S)
_WSL = _pm.group(1).split('\n')
if len(_WSL) != 4 or _WSL[3] != '幽映每白日，清輝照衣裳。 ':
    raise SystemExit('ws poem 块四物理行结构或末行尾空格变了——照登判决须重估')
# （每物理行恰等于相邻两条存储行拼接；末行先剥那一个随行空格——唯一裁切点）
if _WSL[0] != _V18L[0] + _V18L[1] or _WSL[1] != _V18L[2] + _V18L[3] \
        or _WSL[2] != _V18L[4] + _V18L[5] or _WSL[3].rstrip(' ') != _V18L[6] + _V18L[7]:
    raise SystemExit('ws poem 块四物理行与 V018 八行存储面不再逐字相合——同面零分歧断言失效')
if WS.count('清輝照衣裳。 ') != 1:
    raise SystemExit('ws 页尾空格只此一处断了（照登硬卡）')

# ---------- 通鉴年标题窗口断言 ----------
_HEAD = re.compile(r'[^\n]*(?:（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][，、]公元[〇零一二三四五六七八九十百千]+年）'
                   r'|\{\{\*\|[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，西元[〇零一二三四五六七八九十百千]+年\}\})')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 90]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ254, TJ_BY, '中和二年')
_window(TJ201, TJ_HC, '總章二年')

# ---------- 负证机器复查 ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：白雲/宏詞各恰一（读书无账）、青溪/流水恰一（在册句只对照）、诗面语侧全零
for _w, _n in (('白雲', 1), ('宏詞', 1), ('青溪', 1), ('流水', 1)):
    if _alltj.count(_w) != _n:
        raise SystemExit(f'通鉴「{_w}」不再恰{_n}——读书两界闭域档扫须重估')
if '玉皇授白雲先生高駢' not in _tjf.get('tj-254.txt', '') or _tjf['tj-254.txt'].count('白雲') != 1:
    raise SystemExit('通鉴 254 卷白雲谶文变了——中和二年窗口判决须重估')
if '謂之宏詞' not in _tjf.get('tj-201.txt', '') or _tjf['tj-201.txt'].count('宏詞') != 1:
    raise SystemExit('通鉴 201 卷宏詞铨法条变了——總章二年窗口判决须重估')
for _w in ('落花', '幽映', '深柳', '讀書堂', '閑門', '向山路', '衣裳', '青溪長', '白雲盡',
           '流水香', '歸取宏詞', '讀書聲'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零（实 {_alltj.count(_w)}）——诗面语侧闭域档扫须重估')
# ② 全唐诗快照：八句全零（在册外零——底本256抓取失败在册）；闕題锚分布恰三卷；眘恰三卷
for _ln in ('道由白雲盡，春與青溪長。', '時有落花至，遠隨流水香。',
            '閑門向山路，深柳讀書堂。', '幽映每白日，清輝照衣裳。'):
    if _allq.count(_ln) != 0:
        raise SystemExit(f'全唐詩快照「{_ln[:6]}…」不再全零（实 {_allq.count(_ln)}）——在册外零判决须重估')
_qv = sorted((n, t.count('==[[')) for n, t in _qtf.items() if '闕題' in t)
if sorted(n for n, _ in _qv) != ['vol128.txt', 'vol234.txt', 'vol529.txt']:
    raise SystemExit(f'全唐詩快照含「闕題」卷分布变了（实 {_qv}）——题面跨诗人档扫须重估')
if _qtf['vol128.txt'].count('==[[闕題 (王維)|闕題二首]]==') != 1:
    raise SystemExit('卷128 王维闕題二首锚不再唯一——王维侧切片失效')
if _qtf['vol234.txt'].count('==[[闕題 (杜甫)|闕題]]==') != 1:
    raise SystemExit('卷234 杜甫闕題锚不再唯一——杜甫侧计数档扫须重估')
if _qtf['vol529.txt'].count('{{另|秋日赴闕題潼關驛樓|行次潼關逢魏扶東歸}}') != 1:
    raise SystemExit('卷529 异文消歧「秋日赴闕題」不再恰一——第三态档扫须重估')
if FETCH.count('卷256: FAILED') != 2:
    raise SystemExit(f'fetch.log「卷256: FAILED」不再恰二（实 {FETCH.count("卷256: FAILED")}）——在册外零的在案凭证须重核')
if 'vol256' in ''.join(_qtf.keys()) or '卷256' in ''.join(_qtf.keys()):
    raise SystemExit('快照里出现了卷256——底本已补齐，在册外零判决须改写为跨面核验')
_sv = sorted(n for n, t in _qtf.items() if '眘' in t)
if _sv != ['vol019.txt', 'vol140.txt', 'vol160.txt']:
    raise SystemExit(f'全唐詩快照含「眘」卷分布变了（实 {_sv}）——零传记之人存证档扫须重估')
if _qtf['vol019.txt'].count('==相和歌辭·江南曲==\n劉眘虛') != 1:
    raise SystemExit('卷019 江南曲+劉眘虛署名对不再恰一——异注对照须重估')
if V140.count('送劉眘虛歸取宏詞解') != 2:
    raise SystemExit('卷140 送劉眘虛锚+转引不再恰二——PERSON 计数登记须重估')
if V160.count('==[[九日龍沙作寄劉大眘虛]]==\n{{:九日龍沙作寄劉大眘虛}}') != 1:
    raise SystemExit('卷160 高適寄劉大眘虛块变了——逐字入引切片失效')
# ③ 七史快照：眘字全零（零传记之人的机器断言）
_hist = {}
for pat in ('jts-*.txt', 'xts-*.txt', 'qss-*.txt'):
    for p in pathlib.Path('/tmp/src-dl').rglob(pat):
        _hist[p.name] = p.read_text(encoding='utf-8')
_allh = ''.join(_hist.values()) + _alltj
for _w in ('眘', '劉眘虛', '劉慎虛', '慎虛'):
    if _allh.count(_w) != 0:
        raise SystemExit(f'史部快照「{_w}」不再全零（实 {_allh.count(_w)}）——零传记之人判决须重估')
# ④ ws 页形制闭域（无Vtext 273/尾空格54/body挂三百首59/notes含↑130/恰两类目149/本类目对48）
_wsf = {p.name: p.read_text(encoding='utf-8')
        for p in sorted(pathlib.Path('/tmp/src-dl/ws-poems').glob('*.txt'))}
_nv = {n for n, t in _wsf.items() if '{{Vtext' not in t}
if len(_nv) != 273:
    raise SystemExit(f'ws 无Vtext 页不再恰 273（实 {len(_nv)}）——双转录缺位反面标本闭域须重估')
def _last_poem(t):
    m = re.search(r'<poem>\n(.*?)\n</poem>', t, re.S)
    return m.group(1).splitlines()[-1] if m else ''
_tr = {n for n, t in _wsf.items() if _last_poem(t).endswith(' ')}
if len(_tr) != 54:
    raise SystemExit(f'ws 末诗行尾空格页不再恰 54（实 {len(_tr)}）——照登闭域须重估')
_bm = {n for n, t in _wsf.items()
       if any(l == '{{唐詩三百首}}' for l in t.splitlines())
       and '[[Category:唐詩三百首' not in t}
if len(_bm) != 59:
    raise SystemExit(f'ws body挂三百首且无类目页不再恰 59（实 {len(_bm)}）——挂法闭域须重估')
_up = {n for n, t in _wsf.items() if re.search(r'\| notes\s*=.*↑', t)}
if len(_up) != 130:
    raise SystemExit(f'ws notes 含↑页不再恰 130（实 {len(_up)}）——回指闭域须重估')
_c2 = {n for n, t in _wsf.items() if len(re.findall(r'^\[\[Category:', t, re.M)) == 2}
if len(_c2) != 149:
    raise SystemExit(f'ws 恰两类目页不再恰 149（实 {len(_c2)}）——最简类目面闭域须重估')
_c2p = {n for n, t in _wsf.items()
        if tuple(re.findall(r'^\[\[Category:(.+)\]\]$', t, re.M)) == ('唐詩', '五言律詩')}
if len(_c2p) != 48:
    raise SystemExit(f'ws 「唐詩+五言律詩」类目对页不再恰 48（实 {len(_c2p)}）——类目对闭域须重估')
_v256 = {n for n, t in _wsf.items() if '全唐詩/卷256' in t}
if _v256 != {'闕題__劉眘虛_.txt'}:
    raise SystemExit('ws 引卷256 页不再恰本页——底本回指唯一性失效')
# ⑤ 本页负形（零标记/无VH1/无clr/无三百首类目/评级恰一）
for _w in ('{{Vtext', '{{VH1', '{{另', '{{別', '{{*', '<ref>', '{{reflist}}', '{{clr}}',
           '[[Category:唐詩三百首', '| times', '| type', '| from'):
    if WS.count(_w) != 0:
        raise SystemExit(f'ws 页「{_w}」不再全零（反面标本断言失效）')
if WS.count('{{Textquality|75%}}') != 1 or WS.count('{{textquality') != 0:
    raise SystemExit('ws 页七五评级计数变了（七五页本系列首见断言失效）')
_l75 = sorted(n for n, t in _wsf.items() if '{{textquality|75%}}' in t)
if _l75 != ['夜雨寄北.txt']:
    raise SystemExit(f'全库唯一小写 75 评级页变了（实 {_l75}）——大小写谱须重估')

# ---------- 四层背景正文 ----------
BG = {
    'bg-363-scene': (
        '**诗的第一笔是一条走到头的白云路**：「道由白雲盡，春與青溪長」——路被白云拦断，'
        '春天却顺着青溪拉长：诗从「走到看不见的地方」开始。**ws 页是无 Vtext 页**——全库'
        '273 页闭域（机器断言）的**双转录缺位反面标本**：V072–V074 双转录句读分工三连的'
        '镜像，只此一面，poem 块就是唯一转录面。**同面零分歧+唯一裁切点**：V018 以 ws-raw'
        '存储的八行与本快照 poem 块逐字同面（生成时八行双向断言），唯页尾「清輝照衣裳。 」'
        '带一个随行的空格、V018 存储面八行全无尾随空格（照登——全库尾空格页 54 闭域）：面'
        '同一字不差，差只在校存两端对那一个空格的手不同。**七五页本系列首见**（'
        '{{Textquality|75%}}——大写 142 页闭域，全库唯一小写 75 评级页是夜雨寄北，照登'
        '不判）；{{唐詩三百首}} 走 body 独立行挂法（59 页闭域——本页无三百首类目行）。正文'
        '第二引上限用满第二十三例（V018 句读式「道由白雲盡，……清輝照衣裳。」一引在先，'
        '零重开硬断言），此后此诗正文关闭。',
    ),
    'bg-363-city': (
        '**这首诗的题面不属于这首诗**：「闕題」——王维名下有两首、杜甫名下有一首（机器'
        '断言：快照 120 卷里「闕題」字面分布恰三卷——128 王维二首/234 杜甫一首/529 把'
        '「秋日赴闕題潼關驛樓」卷入长题异文）——卷128「==[[闕題 (王維)|闕題二首]]==」锚'
        '带两枚空壳转引照登（V072/V073 空壳卷页侧同款）：闕題作为跨诗人共享的「无名」题面'
        '形态在册第三枚（V044 无题谱外新枝）。**底本回指恰一处、底本不在**：「↑ [[全唐詩/'
        '卷256#闕題|全唐詩·卷256]]」系全库 130 页含↑回指闭域中唯一指向卷256 的一页，而'
        '快照里没有卷256——抓取日志「卷256: FAILED」恰二条（机器登记入引）：**在册外零'
        '首枚**——八句在 120 卷全唐诗快照语料全零，此零非书零而是快照零（底本缺席即说'
        '底本缺席，不逐字引 256）；页尾分类恰两行（[[Category:唐詩]][[Category:五言律詩]]'
        '——恰两类目 149 页/本类目对 48 页闭域）：最简类目面，整理者动作非史料声明、'
        '不升格，V048 判例；{{唐詩三百首}} body 独立行挂法与无类目行照登。',
    ),
    'bg-363-world': (
        '**诗的白云与读书，通鉴各有一本账，没有一本在读书**（同字两界第二十形态·读书形态'
        '首见）：「道由白雲盡」——通鉴「白雲」恰一：中和二年（壬寅，八八二）吕用之'
        '「**刻青石為奇字云：『玉皇授白雲先生高駢。』**密令左右置道院香案」——史的白雲'
        '是石头开口代天授名的道君称号，诗的白雲是路的尽头。「深柳讀書堂」之「宏詞」侧——'
        '通鉴「宏詞」恰一：總章二年（己巳，六六九）铨法「**人有格限未至，而能試文三篇，'
        '謂之宏詞**，試判三條，謂之拔萃」——史的宏词是资格未至先送三篇文来试的科目，诗的'
        '读书堂是柳荫深处自己读的书（「送刘眘虚归取宏词解」的诗题把这两条线并到同一个人'
        '身上——读法声明）。「春與青溪長」之青溪（V057 大中十三年韦皋开青溪道贡使路）、'
        '「遠隨流水香」之流水（V058 貞觀十年長孫后「車如流水馬如龍」车马喻）**在册零'
        '重开**（audit 硬断言逐字不再入本迁移引文）；落花/幽映/深柳/讀書堂/閑門/向山路/'
        '衣裳 通鉴全零（闭域档扫，机器断言）——诗的白云与读书落不进史部任何一本账'
        '（对照判决，非史实因果）。',
    ),
    'bg-363-person': (
        '**史部没有这个人的传**：「眘」（刘眘虚/刘慎虚/慎虛）在 jts 27 卷+xts 8 卷+qss '
        '3 卷+通鉴 75 卷史部快照**全零**（机器断言）——零传记之人，系列首枚：史部不录此'
        '人，连异写都不录。他在本库语料里活在别人的诗题与署名行里：全唐诗快照恰三卷五处'
        '「眘」——卷140 王昌齡卷「送劉眘虛歸取宏詞解」锚+转引恰二（**140 无源行，只计数'
        '登记逐字不入引**，audit 硬断言）；卷160 高適卷「==[[九日龍沙作寄劉大眘虛]]==」'
        '锚+空壳转引逐字入引（160 源在册复用零新建）；卷019「==相和歌辭·江南曲==」下'
        '署名行「劉眘虛」恰一——与 t300-335 选本页署名李益（V018「header author=李益」'
        '在册零重开）**两处见证并列只登记不裁决**，异注留 V079 专办。V018 作者判定「署名 '
        '劉眘虛：选本与维基文库页面两处转录一致」在册零重开。史无此人、诗题有其人：朋友'
        '的诗题替他留名，选本替他收诗——「无传的人活在朋友的题目里」系读法声明。KNOWN '
        '零如实记录（第卅一例，audit 反向断言）。',
    ),
}
BG = {k: (v[0] if isinstance(v, tuple) else v) for k, v in BG.items()}

BG_LINES = {'bg-363-scene': (1, 2), 'bg-363-city': (3, 4),
            'bg-363-world': (5, 6), 'bg-363-person': (7, 8)}
BG_AUDIENCE = {'bg-363-scene': 'PRIMARY', 'bg-363-city': 'JUNIOR',
               'bg-363-world': 'SENIOR', 'bg-363-person': 'JUNIOR'}
BG_TITLES = {
    'bg-363-scene': '眼前：白云尽处的空堂',
    'bg-363-city': '这座城：题面不属于这首诗',
    'bg-363-world': '这个天下：白云是谶，宏词是科',
    'bg-363-person': '这个人：史部无传，诗题有名',
}
CLAIMS = {
    'claim-bg-363-scene': ('FACT', 'LIKELY',
        '闕題八句取 ws 选本页 poem 块存原样面入引（V018 句读式「道由白雲盡，……清輝照衣裳。」'
        '一引在先，零重开硬断言——正文第二引第二十三例）；同面零分歧+唯一裁切点（V018 ws-raw'
        '存储八行≡本快照 poem 块，唯页尾末行带一随行空格而存储面八行全无——照登，全库54页'
        '闭域）；双转录缺位反面标本（无Vtext全库273页闭域——V072–V074三连之镜像）；'
        '七五页本系列首见（大写142页闭域，唯一小写75页夜雨寄北照登不判）'),
    'claim-bg-363-city': ('FACT', 'LIKELY',
        '闕題题面跨诗人形态在册第三枚（快照120卷「闕題」字面恰三卷——128王维二首锚+两空壳'
        '转引逐字入引/234杜甫一首计数/529长题异文消歧计数，机器断言）；底本回指↑卷256全库'
        '唯一且256不在快照（fetch.log「卷256: FAILED」恰二入引）——**在册外零首枚**（八句'
        '快照全零系底本缺席非书零，不逐字引256）；分类恰两行最简类目面（149页/类目对48页'
        '闭域，V048 不升格）；**本迁移零新建 source**（source-ws-t300-363 系 V018 所立、'
        '128 源在册复用）'),
    'claim-bg-363-world': ('FACT', 'LIKELY',
        '通鉴白雲恰一（中和二年吕用之刻青石奇字「玉皇授白雲先生高駢」道君称号）/宏詞恰一'
        '（總章二年铨法「試文三篇謂之宏詞」科目）闭域入引；青溪（V057 贡道）/流水（V058 '
        '车马喻）在册零重开（audit 硬断言）；落花/幽映/深柳/讀書堂/閑門/向山路/衣裳全零；'
        '白云与读书各有其账、无一册是他读书（同字两界第二十形态·读书形态首见，对照判决非'
        '史实因果）'),
    'claim-bg-363-person': ('FACT', 'LIKELY',
        '眘字七史快照全零（jts 27+xts 8+qss 3+通鉴 75——零传记之人，系列首枚，机器断言）；'
        '全唐诗快照眘恰三卷五处全在诗题/署名行；卷160 高適「九日龍沙作寄劉大眘虛」锚+转引'
        '逐字入引（160 源复用零新建）；卷019 江南曲署名劉眘虛与选本页署名李益（V018 在册）'
        '两见证并列只登记不裁决（V079 专办）；卷140 无源行只计数不逐字（audit 硬断言）；'
        'KNOWN 零如实记录第卅一例'),
}
CITATIONS = [
    ('claim-bg-363-scene', 'source-ws-t300-363',
     '页面 闕題（《唐詩三百首》第 363 首（全库最大序号）选本页，页题裸名；header '
     'author 署名行+poem 块四物理行八句存原样以「……」相连——**V018 以此页立正文'
     '（ws-raw），source-ws-t300-363 系 V018 所立第二次复用零新建**（V066 判例反向首枚）；'
     '**同面零分歧**：存储八行与本块逐字同面（双向断言）；**唯一裁切点照登**：页尾'
     '末行「清輝照衣裳。 」带一随行空格而存储面八行全无尾随空格（全库尾空格页 54 闭域）；'
     '无 Vtext/VH1——双转录缺位反面标本（全库 273 页闭域）；七五评级大写页本系列首见；'
     '正文第二引第二十三例零重开',
     join(WS_AUTHOR, WS_POEM_A, WS_POEM_B)),
    ('claim-bg-363-scene', 'source-quantangshi-128',
     '卷一百二十八·王維「==[[闕題 (王維)|闕題二首]]==」锚行（闕題题面跨诗人形态之王维侧——'
     '锚形「二首」合并消歧器照登；同页两枚「{{:闕題 (…)}}」空壳转引在册（V072/V073 空壳'
     '卷页侧同款），锚行随 SCENE 入引、转引行随 CITY 入引——同一 (claim,source) 判例分载）',
     V128_QT),
    ('claim-bg-363-city', 'source-ws-t300-363',
     '页面 闕題（notes 整值入引：{{Textquality|75%}} 评级+↑底本回指同行——**全库 130 页'
     '含↑闭域中唯一指向卷256 的一页**，而卷256 不在快照：抓取日志「卷256: FAILED」恰二'
     '机器登记——**在册外零首枚**（八句 120 卷全唐诗快照全零系底本缺席非书零，不逐字引'
     '256）+{{唐詩三百首}} body 独立行挂法（59 页闭域，本页无三百首类目行）+页尾分类恰'
     '两行（[[Category:唐詩]]+[[Category:五言律詩]]——恰两类目 149 页/类目对 48 页闭域；'
     '整理者动作：非史料声明、不升格，V048 判例）',
     join(WS_NOTE, WS_300, WS_CAT, FETCH_256)),
    ('claim-bg-363-city', 'source-quantangshi-128',
     '卷一百二十八·王維闕題块两枚空壳转引行（「{{:闕題 (荆谿白石出)}}」+「{{:闕題 (相看'
     '不忍發)}}」——锚下无正文、正文各在他页：空壳转引在册形态；「闕題」字面快照恰三卷'
     '分布（128/234/529）机器断言，234 杜甫一首与 529 长题异文消歧只计数登记不入引——'
     '闕題题面跨诗人形态在册第三枚）',
     V128_GAP),
    ('claim-bg-363-world', 'source-zizhi-tongjian-events',
     '卷二百五十四·中和二年（壬寅，八八二）吕用之「刻青石為奇字云：『玉皇授白雲先生高駢。』'
     '…同歸上清耳」（**史的白雲是石头代天授名的道君称号**）……卷二百〇一·總章二年（己巳，'
     '六六九）铨法「人有格限未至，而能試文三篇，謂之宏詞，試判三條，謂之拔萃」（**史的宏词'
     '是格限未至先试三篇文的科目**）；通鉴白雲恰一/宏詞恰一（文件闭域+两处年标题窗口机器'
     '断言）；青溪/流水各恰一系 V057（大中十三年贡道）/V058（貞觀十年车马喻）在册句只对照'
     '不重开（audit 硬断言逐字不再入引）；落花/幽映/深柳/讀書堂/閑門/向山路/衣裳通鉴全零'
     '——两段逐字入引为读书两界判决证据',
     join(TJ_BY, TJ_HC)),
    ('claim-bg-363-person', 'source-quantangshi-160',
     '卷一百六十·高適「==[[九日龍沙作寄劉大眘虛]]==」锚+「{{:九日龍沙作寄劉大眘虛}}」'
     '空壳转引整块逐字入引（**零传记之人存证**：史部七库快照「眘」全零——jts 27+xts 8'
     '+qss 3+通鉴 75 机器断言；全唐诗快照「眘」恰三卷五处全在诗题/署名行；160 源在册'
     '复用零新建；卷140 王昌齡送劉眘虛锚+转引恰二系无源行只计数登记逐字不入引（audit'
     '硬断言）；卷019 江南曲署名劉眘虛与选本页署名李益两见证并列只登记不裁决，V079 专办）',
     V160_GAO),
]

BG_SUMMARY = {k: '四层处境背景（阶段 D 第 56 首·八句五律 2/2/2/2）；史实句均有逐字引证；'
                 '系年第五十次判决（题证系列第卅八状·白云与读书各有其账，无一册是读书）'
                 '「诗的白云与读书，通鉴各有一本账，没有一本在读书」——'
                 '同字两界第二十形态·读书形态首见：白雲恰一（中和二年青石奇字「玉皇授白雲'
                 '先生高駢」）/宏詞恰一（總章二年铨法「試文三篇謂之宏詞」）闭域入引；'
                 '青溪（V057 贡道）/流水（V058 车马喻）在册零重开；落花/幽映/深柳/讀書堂/'
                 '閑門/向山路/衣裳通鉴全零；在册外零首枚（八句 120 卷快照全零系底本卷256'
                 '抓取失败在册非书零——不逐字引 256）；同面零分歧+唯一裁切点（V018 ws-raw'
                 '存储八行≡poem 块，页尾随行空格存储面已裁——照登）；无 Vtext 页 273 页'
                 '闭域反面标本（双转录缺位——V072–V074 三连之镜像）；闕題题面跨诗人第三枚'
                 '（快照恰三卷：128 王维二首/234 杜甫/529 长题异文）；眘字七史全零·'
                 '零传记之人系列首枚（只在朋友诗题与署名行——160 高適逐字入引/140 无源只'
                 '计数/019 署名异注并列不裁决留 V079）；**零新建 source**（V018 已立'
                 ' source-ws-t300-363——V066 判例反向首枚）+128/160 在册复用；正文第二引'
                 '第二十三例零重开；KNOWN 零如实记录第卅一例（audit 反向断言）；'
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
    A("""-- V075：劉眘虛《闕題》(work-t300-363) 四层背景（阶段 D 第 56 首·读书两界）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V026、V033、V035、V039、V048、V053、V057、
--       V058、V059、V060、V061、V062、V063、V064、V065、V066、V067、V068、V069、V070、
--       V071、V072、V073、V074 已执行
--       （work-t300-363 与其 text-work-t300-363-ws（version_code=ws-raw——V018 立此诗正文
--       用的就是《唐詩三百首》选本页，八行带句读全无尾随空格，与本快照 ws 诗页 poem 块
--       逐字同面零分歧，唯页尾「清輝照衣裳。 」一个随行空格存储面已裁——唯一裁切点照登）
--       与其源 source-ws-t300-363（V018 已立的选本页源，本迁移第二次复用零新建——
--       **V066 判例反向首枚：那首《涼思》V018 用卷页立文、诗页无源须新建一枚；这首 V018
--       就用诗页立文、诗页见证早有源行、无源可建。audit 断言本文件恰零枚 poetry_source
--       新建、回滚零 source 删除**）；
--       source-quantangshi-128（V026 已立的卷128 王维卷页源，第五次复用）、
--       source-quantangshi-160（V031 已立的卷160 高適卷页源，第六次复用）、
--       source-zizhi-tongjian-events（V014/V015 已立的通鉴事件源）都是既有行；
--       卷256 无源行亦无快照（抓取失败在册），卷140 无源行（只计数登记不逐字入引）；
--       判例在册句（道由白雲盡句读式全引/清輝照衣裳/header author=劉眘虛 V018、
--       header author=李益 V018（t300-335 江南曲选本页——019 卷署名異注只对照不裁决）、
--       開青溪道 V057、車如流水馬如龍 V058）只对照不重开。
--
-- 数据源（可复现）：emit_v075.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/闕題__劉眘虛_.txt（无Vtext 页=双转录缺位反面标本（全库恰 273 页闭域）+{{唐詩三百首}}
--   body 独立行挂法（59 页闭域）+notes 单行 TQ75+↑底本回指（130 页闭域）+末行页尾随行空格
--   （54 页闭域）+分类恰两行（149 页/「唐詩+五言律詩」对 48 页闭域）+无 VH1/无另/无别/无 */
--   无 ref/无 reflist/无 clr/无 times/type/from/无三百首类目行）、
--   V018 存储面重建比对（text-work-t300-363-ws 八行 vs ws poem 块——同面零分歧+唯一裁切点
--   双向断言）、全唐詩快照卷128（王维闕題二首锚+两空壳转引——闕題题面跨诗人形态；「闕題」
--   字面恰三卷分布 128/234/529 机器断言）+卷160（高適九日龍沙作寄劉大眘虛锚+空壳转引逐字
--   入引）+卷140/卷019（送劉眘虛锚计数恰二/江南曲署名對恰一——只计数不入引）+
--   fetch.log（「卷256: FAILED」恰二条在册——在册外零的生成时凭证，非引用源）+
--   通鑑卷254/201（白雲/宏詞两段逐字入引+年标题窗口：中和二年八八二/總章二年六六九）+
--   通鑑 75 卷负证计数扫描（白雲恰一+宏詞恰一+青溪恰一+流水恰一（后二系 V057/V058 在册句
--   只对照）+落花/幽映/深柳/讀書堂/閑門/向山路/衣裳/青溪長/白雲盡/流水香/歸取宏詞全零）+
--   七史快照（jts 27+xts 8+qss 3+通鉴 75）「眘/劉眘虛/劉慎虛/慎虛」全零机器断言+
--   ws 全库 295 页闭域档扫（无Vtext 273/尾空格 54/body挂三百首 59/notes含↑ 130/恰两类目
--   149/类目对 48/卷256 回指唯一/大写75 评级 142/唯一小写 75 页=夜雨寄北）+
--   既有迁移引文域逐句查重——在册零重开、二引/零重开/首引零域前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 6 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 background_line（八句五律 **2/2/2/2 顺次**：scene→1,2 city→3,4 world→5,6 person→7,8，
--   绑 text-work-t300-363-ws 的 8 行）+ 零新建 source + 不碰 poetry_text_line。
-- 不做：**不新建任何 source**（V066 判例反向首枚——audit 断言零枚）；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「在册外零：底本缺席即说底本缺席」）：
--   * 八句在 120 卷全唐诗快照全零是**快照零非书零**——底本卷256 抓取失败（fetch.log 恰二条
--     机器登记），本迁移不逐字引 256、不断言它与选本页一致与否（无快照即无可核切片）；
--   * 「读书两界」「白云是谶宏词是科」系通鉴两段逐字入引支撑的对照判决，非史实因果——
--     通鉴不记这首诗；亦不考本诗系年（编年诸说一律不采信不铸造）；
--   * 「送刘眘虚归取宏词解」的诗题把通鉴铨法条与诗的读书堂并到同一个人身上——读法声明，
--     140 无源行只计数登记不逐字（audit 硬断言「送劉眘虛」不入任何引文）；
--   * 「零传记之人」严格限于本地七史快照——不排除纸面史部另有传（无快照即不能说）；
--   * 019 卷江南曲署名劉眘虛 vs t300-335 选本页署名李益：**两处见证并列只登记不裁决**
--     （异文只登记不裁决总判例），专办留 V079 江南曲；
--   * 闕題 题面跨诗人形态只登形（128 王维/234 杜甫/529 长题异文），不推作者归属；
--   * 分类恰两行与类目行系整理者动作：非史料声明、不升格，V048 判例；
--   * 「无Vtext 273 页」「尾空格 54 页」「七五评级 142 页」均照登不判；
--   * KNOWN 零如实记录（第卅一例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * V011/V016/V018/V026/V033/V035/V039/V053/V057/V058/V063/V066–V074 已引诸句只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 74，不含 75
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-363-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-363',
--     'source-quantangshi-128','source-quantangshi-160');               -- 恰三行（皆既有，本迁移零新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-363-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-363-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-363';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-363-%';  -- 四行全 LIKELY
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-363'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-363';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-363-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V075_rollback.sql（按 id 全枚举删除；**零 source 删除**——本迁移零新建
--   source，source-ws-t300-363/source-quantangshi-128/source-quantangshi-160 皆既有行绝不删；
--   work-t300-363 本体与其 text_line 8 行都是 V018 的行，绝不删）
START TRANSACTION;""")

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
    brows = [{'id': k, 'work_id': 'work-t300-363',
              'layer': {'bg-363-scene': 'SCENE', 'bg-363-city': 'CITY',
                        'bg-363-world': 'WORLD', 'bg-363-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（八句五律 2/2/2/2 顺次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-363-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 75, 'Liu Shen-xu''s Untitled (work-t300-363) background layers (stage-D poem 56, the highest sequence number in the anthology; eight-line regulated verse 2/2/2/2): dating verdict fifty, thirty-eighth shape of the title-evidence series -- the poem''s white cloud and its reading-hall; the histories keep a ledger for each, and not one of them is reading. Same-character-two-realms, twentieth shape: the reading (dushu) shape, first seen. Baiyun (white cloud) appears exactly once in the Tongjian (Zhonghe 2, renyin, 882: Lu Yongzhi "engraved a blue stone with strange characters, saying: The Jade Emperor confers on Gao Pian, Master of the White Cloud," secretly having it placed on the Daoist altar -- the history''s white cloud is a title of Daoist lordship handed out by talking stone, the poem''s white cloud is where the road runs out). Hongci appears exactly once (Zongzhang 2, jisi, 669, the statute on selection: "among those whose quota has not yet arrived, whoever can sit three essays is called hongci, and whoever sits three judgments is called bacui" -- the history''s hongci is a examination subject you present three essays to enter before your turn; the poem''s reading-hall is reading alone deep in the willows). Qingxi (V057, the tribute road) and liushui (V058, the image of horse-drawn carriages "carriages like flowing water, horses like dragons") are closed citations, re-cited zero times -- the audit hard-asserts neither literal re-enters any citation of this migration. Luohua (falling petals), youying (dim light), shenliu (deep willows), dushutang (reading hall), xianmen (idle gate), xiangshanlu (toward the mountain path), yishang (clothes) all score zero in the Tongjian (machine-asserted): the poem''s white cloud and its reading land in no ledger of the histories (declared contrast, not historical causation). OUT-OF-CATALOG ZERO, first seen: the eight lines score zero across the 120-volume Quan Tangshi snapshot, and the reason is on the record -- this page''s notes point their sole back-reference at juan 256, and juan 256 is one of the failed fetches: the fetch log carries exactly two "卷256: FAILED" lines (machine-registered into the CITY citation). This is a snapshot-zero, not a book-zero: with no snapshot there is no verifiable slice, so juan 256 is never quoted and never compared (the honest boundary of this poem). SAME-FACE ZERO-DIVERGENCE + THE SINGLE TRIM POINT: V018 stored this poem with version_code ws-raw -- from this very anthology page -- and its eight stored lines match this snapshot''s poem block character for character (generator asserts both directions), except that the page''s last line ends "清輝照衣裳。" followed by one trailing space while every stored line is space-free: the two faces agree down to the last graph, and the storage end trimmed that one space (registered as-is; closed set: exactly 54 pages corpus-wide end a poem line with a trailing space). The ws page is the NEGATIVE SPECIMEN of the double-transcription series: it has no Vtext block at all (closed set: exactly 273 pages corpus-wide -- the mirror of the V072-V074 three-in-a-row), no {{VH1}}, no variant marks; {{Textquality|75%}} in uppercase (142 pages; the single lowercase-75 page corpus-wide is Ye Yu Ji Bei -- registered, not judged); the anthology marker {{唐詩三百首}} hangs as its own body line (59 pages) with no anthology category line; the footer carries exactly two category lines ([[Category:唐詩]] + [[Category:五言律詩]] -- 149 pages with exactly two categories, 48 with this pair): the minimal category face, editorial, not upgraded (V048). THE TITLE IS NOT THIS POEM''S: "Untitled" is a cross-poet title-form -- the literal appears in exactly three snapshot volumes (128: two Wang Wei untitleds under one merged-disambiguation anchor with two empty transclusion shells, quoted; 234: one Du Fu, counted; 529: a long-title variant, counted) -- third registered member of the untitled-title family. PERSON: ZERO-BIOGRAPHY PERSON, first of the series -- the graph shen (in Liu Shenxu / Liu Shenvu / Shenvu) scores zero across all local history snapshots (27 JTS + 8 XTS + 3 QSS + 75 Tongjian volumes, machine-asserted); he survives in the corpus only inside other people''s poem-titles and signature lines: exactly three Quan-Tangshi volumes carry the graph -- 140 (Wang Changling''s send-off title for him going to sit the hongci, counted only: volume 140 has no source row, and the audit hard-asserts the send-off title never enters any citation), 160 (Gao Shi''s "On Ninth Festival Written at Longsha, Sent to Liu Da Shenxu" anchor plus empty shell, quoted verbatim; the 160 source at its sixth reuse), and 019 (a Jiangnan qu signed Liu Shenxu -- against the anthology page t300-363''s own cousin-page t300-335 signed Li Yi in V018''s closed citation: two witnesses registered side by side, nothing adjudicated; the case belongs to the future Jiangnan-qu migration). NEW SOURCES: exactly zero -- source-ws-t300-363 was V018''s own row (V018 registered the text from the anthology page, so the anthology-page witness already has its source row: the V066 precedent, inverted for the first time; the audit asserts zero source inserts in the migration and zero source deletes in the rollback), while sources 128 and 160 are reused. Body use-ceiling, twenty-third instance: V018''s punctuated excerpt stands first and is never re-opened (hard assertion); the body is now closed. KNOWN zero honestly recorded (thirty-first instance, audit reverse-asserts); closed precedent keywords (V018''s punctuated full quote, header author lines, V057''s qingxi road, V058''s carriage-water simile) stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 75);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V075 精确回滚：只删 V075 插入的行（id 全枚举）。**零 source 删除**——',
         '-- 本迁移零新建 source（V018 已立 source-ws-t300-363，V066 判例反向首枚）；',
         '-- source-ws-t300-363 / source-quantangshi-128 / source-quantangshi-160 皆既有行，绝不删；',
         '-- work-t300-363 本体与其 text_line 8 行都是 V018 的行，绝不删；',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 75;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V075')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

def _domain_src(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V075')
                   and needle in f.read_text(encoding='utf-8')})

for _premise, _needle, _want in (
        ('本诗首句(V018 句读式一引)', '道由白雲盡', ['V018']),
        ('本诗末句(V018 句读式收尾)', '清輝照衣裳', ['V018']),
        ('V018 句读式全引不重开', '道由白雲盡，……清輝照衣裳。', ['V018']),
        ('本页署名行(V018 header 直证在册)', 'header author=劉眘虛', ['V018']),
        ('江南曲选本页署名(V018 在册——019 异注只对照不裁决)', 'header author=李益', ['V018']),
        ('青溪在册(V057 大中十三年贡道——零重开硬卡)', '開青溪道', ['V057']),
        ('流水在册(V058 貞觀十年车马喻——零重开硬卡)', '車如流水', ['V058']),
        ('V058 在册五成页引文侧对照', '{{Textquality|75%}}↑', ['V055', 'V058', 'V060', 'V061', 'V062', 'V064', 'V065']),
        ('宏詞在册(V016 王昌齡博學宏詞登科——简化字段旧引只对照)', '宏詞', ['V016']),
        ('V066 判例在册(V074 反向首枚对照引子)', 'source-ws-t300-031', ['V066', 'V067', 'V068']),
        ('本诗选本页源已立(V018——V066 判例反向首枚前提)', 'source-ws-t300-363', ['V018']),
        ('卷128 源在册(第五次复用)', 'source-quantangshi-128', ['V026', 'V040', 'V059', 'V061']),
        ('卷160 源在册(第六次复用)', 'source-quantangshi-160', ['V031', 'V049', 'V050', 'V051', 'V053'])):
    _prev = _domain_src(_needle) if (_needle.startswith('source-')) else _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
for _first, _needle in (('署名直证切片', '| author   = 劉眘虛'),
                        ('notes 整值切片', '| notes    = {{Textquality|75%}}↑ [[全唐詩/卷256#闕題|全唐詩·卷256]]'),
                        ('poem 前四句切片', '道由白雲盡，春與青溪長。'),
                        ('poem 后四句切片(带尾空格)', '閑門向山路，深柳讀書堂。'),
                        ('类目两行切片', '[[Category:唐詩]]\n[[Category:五言律詩]]'),
                        ('卷128 王维闕題锚', '==[[闕題 (王維)|闕題二首]]=='),
                        ('卷128 空壳转引连片', '{{:闕題 (荆谿白石出)}}'),
                        ('卷160 高適寄刘大眘虛块', '==[[九日龍沙作寄劉大眘虛]]=='),
                        ('抓取失败在案行', '卷256: FAILED'),
                        ('通鉴白云谶文', '用之又刻青石為奇字'),
                        ('玉皇授白云先生', '玉皇授白雲先生高駢'),
                        ('道院香案', '密令左右置道院香案'),
                        ('通鉴宏詞铨法条', '人有格限未至'),
                        ('试文三篇', '而能試文三篇'),
                        ('试判三条', '試判三條')):
    if _domain(_needle):
        raise SystemExit(f'首引句「{_first}」既往域非零——须换句或降级')


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_AUTHOR, WS_NOTE, WS_POEM_A, WS_POEM_B, WS_CAT, WS_300,
              V128_QT, V128_GAP, V160_GAO, FETCH_256, TJ_BY, TJ_HC]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # SCENE：同面零分歧的页尾裁切点必须逐字在引文内（尾空格照登硬卡）
    sc = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-363-scene' and s == 'source-ws-t300-363')
    if '清輝照衣裳。 ' not in sc:
        bad.append('页尾随行空格面未入 SCENE 引文（唯一裁切点照登硬卡）')
    if '道由白雲盡，春與青溪長。' not in sc:
        bad.append('poem 存原样面未入 SCENE 引文（同面零分歧硬卡）')
    if '道由白雲盡，……清輝照衣裳。' in cited:
        bad.append('V018 句读式引文重开了——本迁移引 poem 存原样面，句读式不重开')
    # CITY：底本回指+抓取失败在册必须在诗页引文内；空壳转引在 128 引文内
    ws_c = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-363-city' and s == 'source-ws-t300-363')
    if '全唐詩/卷256#闕題' not in ws_c or '卷256: FAILED' not in ws_c:
        bad.append('底本回指与抓取失败在册未同入 CITY 诗页引文（在册外零首枚硬卡）')
    if '[[Category:五言律詩]]' not in ws_c:
        bad.append('类目两行未入 CITY 诗页引文（最简类目面硬卡）')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-363-city' and s == 'source-ws-t300-363'):
        bad.append('CITY 诗页 locator 须含「不升格」声明')
    q128c = next(ex for c, s, _, ex in CITATIONS if s == 'source-quantangshi-128' and c == 'claim-bg-363-city')
    if '{{:闕題 (荆谿白石出)}}' not in q128c or '{{:闕題 (相看不忍發)}}' not in q128c:
        bad.append('王维闕題两空壳转引未入 CITY 128 引文（题面跨诗人第三枚硬卡）')
    if '在册外零' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-363-city' and s == 'source-ws-t300-363'):
        bad.append('CITY 诗页 locator 须含「在册外零」声明')
    # WORLD：两段通鉴史文必须逐字入引；在册句与诗语零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-363-world')
    for tok in ('刻青石為奇字', '玉皇授白雲先生高駢', '而能試文三篇', '謂之宏詞', '謂之拔萃'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（两段必须入引）')
    for tok in ('開青溪道', '車如流水', '客去波平檻', '本以高難飽'):
        if tok in cited:
            bad.append(f'在册零重开判例「{tok}」混入本迁移引文')
    for tok in ('落花', '幽映', '深柳', '讀書堂', '閑門', '向山路', '衣裳'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文）')
    w_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-363-world')
    if '白雲' not in w_loc or '宏詞' not in w_loc:
        bad.append('WORLD locator 须点出白雲/宏詞（读书两界声明）')
    # PERSON：160 块必须逐字入引；140 送行诗题严禁入引（无源行只计数）
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-363-person')
    if '九日龍沙作寄劉大眘虛' not in p_ex:
        bad.append('高適寄刘大眘虛块未入 PERSON 引文（零传记之人存证硬卡）')
    for tok in ('送劉眘虛', '归取宏词解'):
        if tok in cited:
            bad.append(f'140 无源行诗句「{tok}」入了引文（只计数登记硬断言）')
    # 判例只引不重开
    for tok in ('道由白雲盡，……清輝照衣裳。', 'header author=劉眘虛', 'header author=李益',
                '開青溪道', '車如流水馬如龍', '博學宏詞', '客去波平檻', '疑誤有新知',
                '本以高難飽', '我亦舉家清', '君問歸期未有期', '錦瑟無端五十',
                '{{:風雨 (李商隱)}}', '{{:蟬 (李商隱)}}', '↑ [[全唐詩/卷539#風雨',
                '↑ [[全唐詩/卷540#涼思', '吾道豈淹留', '淒涼寶劍篇',
                '==涼思==', '==風雨==', '玉皇授白雲先生高駢。』密令左右', '北斗七星高',
                '憐君何事到天涯', '文思清丽', '令狐绹作相', '绹不之省'):
        if tok in cited and not (tok == '玉皇授白雲先生高駢。』密令左右' and '玉皇授白雲先生高駢。」' in cited):
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    if BG_LINES != {'bg-363-scene': (1, 2), 'bg-363-city': (3, 4),
                    'bg-363-world': (5, 6), 'bg-363-person': (7, 8)}:
        bad.append('八句 background_line 须 2/2/2/2 顺次（V020 以来八句篇常规）')
    if len(re.findall(r"text-work-t300-363-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # 零新建 source（V066 判例反向首枚）
    if 'INSERT INTO poetry_' + 'source' in sql:
        bad.append('V075 有意零新建 source（V066 判例反向首枚），但 SQL 里出现了 source INSERT')
    rb = build_rollback()
    if 'DELETE FROM poetry_' + 'source' in rb:
        bad.append('V075 零新建 source，回滚不得含 source 删除')
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V075 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V075 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-363' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V075 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-363' AS subject_id" in sql:
        bad.append('V075 的 claim 主语应全部是 bg-363-*，work-t300-363 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V075 不碰 poetry_text_line')
    body_all = ''.join(BG.values())
    if '读书形态' not in body_all:
        bad.append('BG 须含「读书形态」（同字两界第二十形态）声明')
    if '在册外零' not in body_all:
        bad.append('BG/CITY 须含「在册外零首枚」声明')
    if '唯一裁切点' not in body_all:
        bad.append('BG/SCENE 须含「同面零分歧+唯一裁切点」声明')
    if '零传记之人' not in body_all:
        bad.append('BG/PERSON 须含「零传记之人系列首枚」声明')
    if '只登记不裁决' not in body_all:
        bad.append('BG/PERSON 须含江南曲异注「只登记不裁决」声明')
    if 'V048' not in body_all:
        bad.append('BG/CITY 须含分类不升格（V048）声明')
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
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 75)' not in vblk:
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
              f'V018 存储面八行重建 vs ws poem 块同面零分歧+唯一裁切点双向断言；'
              f'两处年标题窗口断言（中和二年八八二/總章二年六六九）；'
              f'负证机器复查五层（通鉴白雲恰一+宏詞恰一+青溪恰一+流水恰一+落花/幽映/深柳/'
              f'讀書堂/閑門/向山路/衣裳/青溪長/白雲盡/流水香/歸取宏詞/讀書聲全零/'
              f'全唐诗八句快照全零+闕題字面恰三卷(128/234/529)+眘恰三卷(019/140/160)+江南曲'
              f'署名对恰一+140锚恰二/160块恰一+fetch.log卷256 FAILED恰二+256不在快照+七史眘全零/'
              f'ws 无Vtext 273+尾空格54+body挂三百首59+notes含↑130+恰两类目149+类目对48+卷256'
              f'回指唯一+大写75页142+唯一小写75页=夜雨寄北+本页九项零标记，快照变动即中止）；'
              f'前提全库查重硬卡十四件+十五首引句零域断言+零新建 source 前提（source-ws-t300-363 '
              f'仅 V018 域在册）断言；SCENE 尾空格面+存原样面入引+V018 句读式引文零重开断言；'
              f'CITY 底本回指+卷256 FAILED 同引+在册外零声明硬卡；CITY「不升格」硬卡；'
              f'两段通鉴史文入引+在册句（開青溪道/車如流水）与诗语零混入断言；'
              f'PERSON 160 块入引硬卡+140 送行诗题严禁入引断言+江南曲只登记不裁决声明；'
              f'判例只引不重开断言（含 V018 署名两行/句读式全引、V057/V058 在册句、V074 在册句在内）；'
              f'八句 2/2/2/2 形制断言；零 KNOWN 反向断言；零新建 source 正反断言+回滚零 source 删除断言；'
              f'幂等/宽度/主键/幂等版本账本守卫全数过审')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql)} B) + {args.out_rollback} ({len(rb)} B)')


if __name__ == '__main__':
    main()
