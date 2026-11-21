#!/usr/bin/env python3
"""阶段 D 第 57 首：生成 V076——王之渙《登鸛雀樓》(work-t300-361, V018 已立) 四层背景。

**本迁移恰新建一枚 source：source-quantangshi-253**——V066 判例的**镜像首枚**：V066 是
V018 用卷页立正文、选本页无源须新建；本篇 V018 用选本页立正文（ws-raw、source-ws-t300-363
同族）、**卷页见证面反而无源**——卷253 携带编者小传与「一作《登鸛鵲樓》。一作朱斌詩。」双重
题注，本迁移引卷页非新源不能承载（audit 断言恰一枚 source INSERT、回滚恰删此一枚；
source-ws-t300-361 第二次复用、source-quantangshi-283 第三次复用）。

**存儲面即定読面首枚**：本页是全库标记最密的诗页——题面内嵌 {{另|雀|鵲}}、第二句行内嵌
<ref>「入」：《文苑英華》注「一作『徹』」孤注（无 {{reflist}}）、第四句 {{另|層|重}}、notes
「一作朱斌詩，參見《國秀集》」——一页四个异文/归属载体。V018 存储四行全是净文：雀/層取
头部主读、鵲/重/徹与整个 <ref> 片段全裁——**唯一裁切点从 V075 的一个空格扩展为整段标记
片段**（生成时拼合断言：页物理行=存储行拼合+标记件）。同面零分歧在此不成立，成**异文定読
分工面**：页面存异读、存储存定读（V072 跨迁移异体分工的页-库内版）。

**在册零首枚的反面：底本在场**——全唐诗快照里有卷253（V075 缺的是卷256）：八句以壳形态
在册（{{:登鸛雀樓 (王之渙)}} 空壳——全唐诗 120 卷语料八句净文全零、恰与在册外零对照成谱：
那首底本不在、这首底本在而挂壳）。**卷页层级首见**：卷253 系多诗人合卷（王之渙 閻防 薛據
姚係 令狐峘 滕珦），诗锚为三级「===[[…]]===」（全库 120 卷唯此卷含「===[[」，机器断言）——
作者作二级、诗作三级；锚下题注以粗斜体双注「一作《登鸛鵲樓》。一作朱斌詩。」——**编者题注
直书归属异议**（与 V073 「整理者作者注挂题锚」同族升级：异议进题注）。

「为什么写」走到**看景两界**（同字两界第二十一形态·看景形态首见）：诗的白日/黃河是纯风景，
通鉴各恰一、没有一处在看景：白日恰一（中和二年阡能之乱平，蜀中百姓见高仁厚「如出九泉睹
白日，已死而復生矣」——史的白日是解围的军队，诗的白日是依山沉下去的太阳）；黃河恰一
（天祐二年白馬驛，李振疾搢紳「此輩常自謂清流，宜投之黃河，使為濁流」——史的黄河是拟沉
清流的浊水，诗的黄河是入海的活水）；千里目/層樓/鸛/鹳 通鉴全零。V015 白馬驛在册句只对照
不重开（本迁移引通鉴侧李振语，非旧唐书本纪句）。

PERSON 层：**零传记之人系列第二枚**（V075 眘字首枚）——王之渙/朱斌/崔國輔/鄭昈在七史快照
全零（机器断言）；但与眘不同，**他有传，在《全唐詩》编者的两行附记里**：「王之渙，幷州人，
兄之咸、之賁皆有文名。天寶間，與王昌齡、崔國輔、鄭昈聯唱迭和，名動一時。詩六首。」——
正史无此人、总集编者给他立了本库唯一传（逐字入引，新源承载）；「名動一時」四字是史部不给、
编者给的。**朱斌恰一恰在这一行题注里**（全唐诗 120 卷语料机器断言）：归属异议的对方名字
只活在编者注里——与选本页 notes 同说「一作朱斌」两处独立成对，**只登记不裁决**（V079
江南曲同款规则）。

ws 页形制（SCENE/CITY 层）：**选本标记缺席首枚**（本页无 {{唐詩三百首}} 亦无三百首类目
——48 页闭域机器断言；选本对这首诗的归属不靠页面自我声明，三百首序号来自编辑账）；
**有声页全库恰三页**（{{Spoken Wikisource}} 登鹳雀楼(王之涣).ogg 2020年普通话录音——页面带
现代层，简体字混排照登，非史料）；类目三连 [[Category:代表作品]]+[[Category:千家詩]]+
[[Category:有声文献]] 全库唯一（千家詩=另一部选本的类目行——本页身兼两选本）；from 三连
文苑英華/御定全唐詩/國秀集（16 页闭域）+edition=yes（20 页闭域）+楷體 templatestyles+
孤儿 </sub> 闭合标签（全库唯本页，照登不判）；{{Textquality|100%}} 满级+notes 尾置评级
（V069 首置的反面第二态）。

4 句五绝 shape：**1/1/1/1 第八次**（scene→1 city→2 world→3 person→4）。

用法: python3 -I emit_v076.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402

WS = pathlib.Path('/tmp/src-dl/ws-poems/登鸛雀樓__王之渙_.txt').read_text(encoding='utf-8')
V253 = pathlib.Path('/tmp/src-dl/quantangshi/vol253.txt').read_text(encoding='utf-8')
V283 = pathlib.Path('/tmp/src-dl/quantangshi/vol283.txt').read_text(encoding='utf-8')
V018 = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/V018__tang300_ws_verified.sql').read_text(encoding='utf-8')
TJ255 = pathlib.Path('/tmp/src-dl/tongjian/tj-255.txt').read_text(encoding='utf-8')
TJ265 = pathlib.Path('/tmp/src-dl/tongjian/tj-265.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_AUTHOR = slice_between(WS, '| author   = 王之渙', '| author   = 王之渙',
                          'ws header author(署名直证——正史无传之人只在页header留名)')
WS_TITLE = slice_between(WS, '| title    = 登鸛{{另|雀|鵲}}樓', '| title    = 登鸛{{另|雀|鵲}}樓',
                         'ws header title(题面内嵌{{另|雀|鵲}}异读——全库题面{{另}}5页闭域)')
_REF = "<small><small><ref>「入」：《文苑英華》注「一作'''徹'''」</ref></small></small> "
WS_POEM_A = slice_between(WS, '白日依山盡，黃河入海流。<small>', _REF,
                          'ws poem 块物理行1存原样(行内嵌<ref>孤注——无reflist孤注无处安放照登;末随行空格照登)')
WS_POEM_B = slice_between(WS, '欲窮千里目，更上一{{另|層|重}}樓。', '欲窮千里目，更上一{{另|層|重}}樓。',
                          'ws poem 块物理行2存原样(第四句{{另|層|重}}异读——页存异读/存储存定读=异文定読分工面)')
WS_FROM = slice_between(WS, '| from     = 文苑英華 (四庫全書本)/卷0312',
                        '| from3    = 國秀集 (四庫全書本)/卷下',
                        'ws from 三行底本链(文苑英華/御定全唐詩/國秀集——from2+from3全库15页闭域)')
WS_NOTES = slice_between(WS, '| notes    = 一作[[Author:朱斌|朱斌]]詩，參見《國秀集》<br/>{{Textquality|100%}}',
                         '| notes    = 一作[[Author:朱斌|朱斌]]詩，參見《國秀集》<br/>{{Textquality|100%}}',
                         'ws notes 整值(一作朱斌+參見國秀集+满级评级尾置——选本侧归属异议独立见证)')
WS_ED = slice_between(WS, '| edition= yes', '| edition= yes',
                      'ws edition= yes(定本标记全库17页闭域)')
WS_CAT3 = slice_between(WS, '[[Category:代表作品]]', '[[Category:有声文献]]',
                        'ws 页尾类目三连含空行(代表作品/千家詩/有声文献——全库唯一;千家詩系另一选本类目行,本页身兼两选本)')
V253_ANCH = slice_between(V253, '===[[登鸛雀樓 (王之渙)|登鸛雀樓]]===', '===[[登鸛雀樓 (王之渙)|登鸛雀樓]]===',
                          '卷253 三级诗锚(本卷37/37通例——卷页层级首见,多诗人合卷作者作二级)')
V253_NOTE = slice_between(V253, "'''{{*|一作《登鸛鵲樓》。一作朱斌詩。}}", "'''{{*|一作《登鸛鵲樓》。一作朱斌詩。}}",
                          "卷253 粗斜体双题注(编者题注直书归属异议——题面异写《登鸛鵲樓》+一作朱斌;朱斌全快照恰一在此)")
V253_TITLEBLOCK = slice_between(V253, '===[[登鸛雀樓 (王之渙)|登鸛雀樓]]===', '{{:登鸛雀樓 (王之渙)}}',
                                '卷253 锚+双题注+空壳转引整块(诗以壳形态在册——锚下无正文,四句快照全零)')
V253_BIO = slice_between(V253, '王之渙，幷州人，兄之咸、之賁皆有文名。天寶間，與王昌齡、崔國輔、鄭昈聯唱迭和，名動一時。詩六首。',
                         '王之渙，幷州人，兄之咸、之賁皆有文名。天寶間，與王昌齡、崔國輔、鄭昈聯唱迭和，名動一時。詩六首。',
                         '卷253 王之渙小传整段(正史无传、总集编者给的本库唯一传——名動一時四字是编者给的)')
TJ_BAI = slice_between(TJ255, '如出九泉睹白日，已死而復生矣！」', '如出九泉睹白日，已死而復生矣！」',
                       '通鉴中和二年阡能案百姓见高仁厚语(白日之通鉴侧——出九泉之喻;窗口断言)')
TJ_HH = slice_between(TJ265, '此輩常自謂清流，宜投之黃河，使為濁流！」', '此輩常自謂清流，宜投之黃河，使為濁流！」',
                      '通鉴天祐二年白馬驛李振语(黃河之通鉴侧——拟沉清流的浊水;V015旧唐書在册句只对照,白馬驛四字不入引;窗口断言)')

# ---------- V018 存储面重建与折叠断言（存储面即定読面首枚） ----------
# 页 poem 块是 2 个物理行（每行两个五言句）；V018 ws-raw 存成 4 行净文（{{另}} 折叠取头部主读、<ref> 片段全裁）。
_V18L = re.findall(r"SELECT 'text-work-t300-361-ws' AS version_id, \d+ AS line_seq, '(.*?)' AS content", V018)
if len(_V18L) != 4 or any(s.endswith(' ') or s != s.strip() for s in _V18L):
    raise SystemExit('V018 t300-361 存储面不是四行全无尾随空格——折叠断言须重估')
_pm = re.search(r'<poem>\n(.*?)\n</poem>', WS, re.S)
_WSL = _pm.group(1).split('\n')
if len(_WSL) != 2:
    raise SystemExit('ws poem 块不是两物理行——照登判决须重估')
if _WSL[0] != _V18L[0] + _V18L[1] + _REF:
    raise SystemExit('ws 物理行1 ≠ 存储行1+行2+<ref>标记件——折叠断言失效')
if _WSL[1] != _V18L[2] + '更上一{{另|層|重}}樓。' or _V18L[3] != '更上一層樓。':
    raise SystemExit('ws 物理行2 ≠ 存储行3+{{另|層|重}}折叠面——定読判决失效')
_m = re.search(r"'t300-361' AS slug, '(登鸛雀樓)' AS title", V018)
if not _m or WS_TITLE.replace('{{另|雀|鵲}}', '雀').split('= ')[1] != _m.group(1):
    raise SystemExit('页题折叠面 ≠ V018 work title——题面折叠断言失效')
if WS_POEM_A[-1] != ' ' or WS.count(WS_POEM_A) != 1:
    raise SystemExit('ws 行1尾随行空格只此一处断了（照登硬卡）')
if WS.count('{{另') != 2 or WS.count('<ref>') != 1 or WS.count('{{Textquality|100%}}') != 1:
    raise SystemExit('ws 页 {{另}}×2/<ref>×1/满级评级×1 变了——最华页面断言须重估')

# ---------- 通鉴年标题窗口断言 ----------
_HEAD = re.compile(r'[^\n]*(?:（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][，、]公元[〇零一二三四五六七八九十百千]+年）'
                   r'|\{\{\*\|[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，西元[〇零一二三四五六七八九十百千]+年\}\})')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 90]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ255, TJ_BAI, '中和二年')
_window(TJ265, TJ_HH, '天祐二年')

# ---------- 负证机器复查 ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：白日/黃河各恰一（看景无账）、千里目/層樓/鸛/鹳/朱斌/王之渙/國秀集/文苑英華全零
for _w, _n in (('白日', 1), ('黃河', 1)):
    if _alltj.count(_w) != _n:
        raise SystemExit(f'通鉴「{_w}」不再恰{_n}——看景两界闭域档扫须重估')
if '如出九泉睹白日' not in _tjf.get('tj-255.txt', '') or _tjf['tj-255.txt'].count('白日') != 1:
    raise SystemExit('通鉴 255 卷白日句变了——中和二年窗口判决须重估')
if '宜投之黃河' not in _tjf.get('tj-265.txt', '') or _tjf['tj-265.txt'].count('黃河') != 1:
    raise SystemExit('通鉴 265 卷黃河句变了——天祐二年窗口判决须重估')
for _w in ('千里目', '層樓', '鸛', '鹳', '王之渙', '朱斌', '國秀集', '文苑英華', '依山海',
           '黃河入海', '白日依山', '欲窮千里', '千里眼'):
    # 注：「更上」不入零清单——通鉴有「更上表稱珂非王氏子」常语（副词+动词，非诗面）
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零（实 {_alltj.count(_w)}）——诗面语侧闭域档扫须重估')
# ② 全唐诗快照：四句净文全零（壳在册）；登鸛雀樓恰两卷（253/283）；朱斌恰一在253题注
for _ln in ('白日依山盡，黃河入海流。', '欲窮千里目，更上一層樓。', '白日依山盡', '千里目'):
    if _allq.count(_ln) != (1 if _ln == '千里目' else 0):
        raise SystemExit(f'全唐詩快照「{_ln[:6]}…」计数变了（实 {_allq.count(_ln)}）——壳在册判决须重估')
if _allq.count('朱斌') != 1 or V253.count('朱斌') != 1:
    raise SystemExit(f'全唐詩快照「朱斌」不再恰一（实 {_allq.count("朱斌")}）——归属异议只活在题注判决须重估')
if V283.count('同崔邠登鸛雀樓') != 2:
    raise SystemExit(f'卷283「同崔邠登鸛雀樓」不再恰二（实 {V283.count("同崔邠登鸛雀樓")}）——题面跨诗人只计数档扫须重估')
_dv = sorted(n for n, t in _qtf.items() if '登鸛雀樓' in t)
if _dv != ['vol253.txt', 'vol283.txt']:
    raise SystemExit(f'全唐詩快照含「登鸛雀樓」卷分布变了（实 {_dv}）——题面跨诗人档扫须重估')
if V253.count('===[[登鸛雀樓 (王之渙)|登鸛雀樓]]===') != 1:
    raise SystemExit('卷253 三级诗锚不再唯一——CITY 切片失效')
if V253.count('{{:登鸛雀樓 (王之渙)}}') != 1:
    raise SystemExit('卷253 空壳转引不再唯一——壳在册硬卡失效')
# 三级锚「===[[」形制谱：20 卷含之，本卷 37/37 通例（锚总数==三级锚数）
_av3 = sorted(n for n, t in _qtf.items() if '===[[' in t)
if 'vol253.txt' not in _av3 or len(_av3) != 20:
    raise SystemExit(f'全唐詩快照含「===[[」卷分布变了（实 {len(_av3)} 卷）——卷页层级谱须重估')
if V253.count('===') != V253.count('===[[') * 2:
    raise SystemExit('卷253 锚形不再是三级通例（=== 对数 ≠ 2×三级锚数）——37/37 通例判决须重估')
_wv = sorted(n for n, t in _qtf.items() if '王之渙' in t)
if _wv != ['vol018.txt', 'vol140.txt', 'vol253.txt'] or V253.count('王之渙') != 8:
    raise SystemExit(f'全唐詩快照含「王之渙」卷分布/本卷计数变了（实 {_wv}/{V253.count("王之渙")}）——PERSON 计数须重估')
if V253.count('王之渙，幷州人') != 1:
    raise SystemExit('卷253 小传不再唯一——PERSON 逐字入引切片失效')
# ③ 七史快照：王之渙/朱斌/崔國輔/鄭昈/之賁全零（零传记之人第二枚；之咸在册系另一人不断言）
_hist = {}
for pat in ('jts-*.txt', 'xts-*.txt', 'qss-*.txt'):
    for p in pathlib.Path('/tmp/src-dl').rglob(pat):
        _hist[p.name] = p.read_text(encoding='utf-8')
_allh = ''.join(_hist.values()) + _alltj
for _w in ('王之渙', '朱斌', '崔國輔', '鄭昈', '之賁'):
    if _allh.count(_w) != 0:
        raise SystemExit(f'史部快照「{_w}」不再全零（实 {_allh.count(_w)}）——零传记之人第二枚判决须重估')
# ④ ws 页形制闭域（题面另5/notes一作13/无三百首48/Spoken3/三连1/孤儿sub1/from二三15/edition17/满级26）
_wsf = {p.name: p.read_text(encoding='utf-8')
        for p in sorted(pathlib.Path('/tmp/src-dl/ws-poems').glob('*.txt'))}
def _title_alt(t):
    for l in t.splitlines():
        if l.startswith('| title'):
            return '{{另' in l
    return False
def _notes_yi(t):
    for l in t.splitlines():
        if l.startswith('| notes'):
            return '一作' in l
    return False
_ta = {n for n, t in _wsf.items() if _title_alt(t)}
if len(_ta) != 5:
    raise SystemExit(f'ws 题面内嵌{{{{另}}}}页不再恰 5（实 {len(_ta)}）——题面异读闭域须重估')
_ny = {n for n, t in _wsf.items() if _notes_yi(t)}
if len(_ny) != 13:
    raise SystemExit(f'ws notes 含「一作」页不再恰 13（实 {len(_ny)}）——选本归属异议闭域须重估')
_n300 = {n for n, t in _wsf.items()
         if '{{唐詩三百首}}' not in t and '[[Category:唐詩三百首' not in t}
if len(_n300) != 48:
    raise SystemExit(f'ws 无三百首标记页不再恰 48（实 {len(_n300)}）——选本标记缺席闭域须重估')
if '登鸛雀樓__王之渙_.txt' not in _n300:
    raise SystemExit('本页跌出无三百首标记闭域——选本标记缺席首枚断言失效')
_sp = {n for n, t in _wsf.items() if '{{Spoken Wikisource' in t}
if len(_sp) != 3 or '登鸛雀樓__王之渙_.txt' not in _sp:
    raise SystemExit(f'ws 有声页不再恰 3 或本页不在其内（实 {sorted(_sp)}）——有声文献谱须重估')
_tri = {n for n, t in _wsf.items()
        if '[[Category:代表作品]]\n\n[[Category:千家詩]]\n\n[[Category:有声文献]]' in t}
if _tri != {'登鸛雀樓__王之渙_.txt'}:
    raise SystemExit(f'ws 类目三连页不再恰本页（实 {sorted(_tri)}）——全库唯一断言失效')
_orph = {n for n, t in _wsf.items() if '</sub></center>' in t}
if _orph != {'登鸛雀樓__王之渙_.txt'}:
    raise SystemExit(f'ws 孤儿</sub>页不再恰本页（实 {sorted(_orph)}）——照登不判唯一性失效')
_f23 = {n for n, t in _wsf.items() if '| from2' in t and '| from3' in t}
if len(_f23) != 15:
    raise SystemExit(f'ws from2+from3 页不再恰 15（实 {len(_f23)}）——三行底本链闭域须重估')
_ed = {n for n, t in _wsf.items() if '| edition= yes' in t}
if len(_ed) != 17:
    raise SystemExit(f'ws edition= yes 页不再恰 17（实 {len(_ed)}）——定本标记闭域须重估')
_tq100 = {n for n, t in _wsf.items() if '{{Textquality|100%}}' in t}
if len(_tq100) != 26:
    raise SystemExit(f'ws 满级评级页不再恰 26（实 {len(_tq100)}）——满级页闭域须重估')
# ⑤ 本页负形（无Vtext/无VH1/无reflist/无clr/无三百首标记/评级恰一满级）
for _w in ('{{Vtext', '{{VH1', '{{reflist}}', '{{clr}}', '{{*}}', '[[Category:唐詩三百首',
           '{{唐詩三百首}}', '别集', '全唐詩/卷25'):
    if WS.count(_w) != 0:
        raise SystemExit(f'ws 页「{_w}」不再全零（反面标本断言失效）')
if WS.count('{{Textquality') != 1:
    raise SystemExit('ws 页评级标记不再恰一（满级尾置断言失效）')


# ---------- 补充切片（随引文入册） ----------
WS_ORPH = slice_between(WS, '</sub></center>', '</sub></center>',
                        'ws 孤儿</sub>闭合标签(无配对<sub>——全库唯本页,照登不判)')
V283_ANCH = slice_between(V283, '==[[同崔邠登鸛雀樓]]==', '{{:同崔邠登鸛雀樓}} ',
                          '卷283 司马都「同崔邠登鸛雀樓」锚+空壳转引(题面跨诗人之283侧——同题另人,283源在册第三次复用逐字入引)')

# ---------- 四层背景正文 ----------
BG = {
    'bg-361-scene': (
        '**诗的第一笔是一轮沉下去的白日与一条停不下来的河**：「白日依山盡，黃河入海流」——'
        '二十个字写尽落日与大河，没有一个字在说登楼的人。**ws 页是全库标记最密的诗页**：'
        '题面内嵌 {{另|雀|鵲}}（全库题面{{另}}恰 5 页闭域）、第二句行内嵌《文苑英華》「一作徹」'
        '<ref> 孤注（全页无 {{reflist}}，孤注无处安放照登）、第四句 {{另|層|重}}——一页四个'
        '异文/归属载体。**存储面即定読面首枚**：V018 以 ws-raw 存的四行全是净文——雀/層取'
        '{{另}}头部主读、<ref> 片段整段裁去（生成时拼合断言：页物理行=存储行拼合+标记件）：'
        '同面零分歧在此不成立，成**异文定読分工面**——页面存异读、库存储定读（V072 跨迁移'
        '异体分工的页-库内版）。满级页 {{Textquality|100%}}（26 页闭域）。正文第二引上限'
        '用满第二十四例（V018 句读式「白日依山盡，……更上一層樓。」一引在先，零重开硬断言），'
        '此后此诗正文关闭。',
    ),
    'bg-361-city': (
        '**这首诗在《全唐詩》里以一只空壳在册**：卷253 锚行下「{{:登鸛雀樓 (王之渙)}}」'
        '转引无正文、四句净文在 118 卷快照全零（机器断言——与 V075 在册外零成谱：那首底本'
        '不在、这首底本在而挂壳）。**卷页层级首见**：卷253 是多诗人合卷（王之渙 閻防 薛據'
        '…），诗锚为三级「===[[…]]===」且本卷 37/37 通例（机器断言）——作者作二级、诗作'
        '三级；锚下粗斜体双注「一作《登鸛鵲樓》。一作朱斌詩。」——**编者题注直书归属异议**'
        '（V073「整理者作者注挂题锚」同族升级：异议进题注）；题面异写登鸛雀樓/登鸛鵲樓'
        '照登。同题另人：卷283 司马都「==[[同崔邠登鸛雀樓]]==」锚+空壳逐字入引（283 源在册'
        '第三次复用）——题面跨诗人形态在册。**选本标记缺席首枚**：选本页无 {{唐詩三百首}} '
        '亦无三百首类目（48 页闭域机器断言）——选本对这首诗的归属不靠页面自我声明；notes'
        '「一作朱斌詩，參見《國秀集》」与 from 三行底本链（文苑英華/御定全唐詩/國秀集，15 页'
        '闭域）+类目三连（代表作品/千家詩/有声文献全库唯一——**千家詩系另一部选本的类目行，'
        '本页身兼两选本**）照登；孤儿 </sub> 闭合标签全库唯本页照登不判；页尾类目系整理者'
        '动作，非史料声明、不升格（V048 判例）。',
    ),
    'bg-361-world': (
        '**诗的白日与黄河，通鉴各恰一处，没有一处在看景**（同字两界第二十一形态·看景形态'
        '首见）：「白日依山盡」——通鉴「白日」恰一：中和二年（壬寅，八八二）阡能之乱平，'
        '蜀中百姓见高仁厚「**如出九泉睹白日，已死而復生矣**」——史的白日是解围的军队出'
        '九泉之喻，诗的白日是依山沉下去的太阳。「黃河入海流」——通鉴「黃河」恰一：天祐二年'
        '（乙丑，九〇五）白馬驛案，李振疾搢紳「**此輩常自謂清流，宜投之黃河，使為濁流**」'
        '——史的黄河是拟沉清流的浊水，诗的黄河是入海的活水（V015 旧唐書「投屍於河」在册句'
        '只对照不重开，audit 硬断言「白馬驛」不入本迁移引文）；千里目/層樓/鸛/鹳/王之渙/'
        '朱斌通鉴全零（闭域档扫，机器断言）——诗的两件大景落不进史部任何一本账（对照判决，'
        '非史实因果）。',
    ),
    'bg-361-person': (
        '**正史没有这个人的传，总集编者给他立了本库唯一传**：王之渙/朱斌/崔國輔/鄭昈在 '
        'jts 27 卷+xts 8 卷+qss 3 卷+通鉴 75 卷史部快照**全零**（机器断言）——零传记之人'
        '系列第二枚（V075 眘字首枚）；与眘不同，他有传，在《全唐詩》编者的两行附记里：'
        '「王之渙，幷州人，兄之咸、之賁皆有文名。天寶間，與王昌齡、崔國輔、鄭昈聯唱迭和，'
        '**名動一時**。詩六首。」（逐字入引，新源承载——「名動一時」四字是史部不给、编者'
        '给的；之咸两条在册系另一人，不攀附）。**归属异议的对方名字只活在编者注里**：'
        '「朱斌」在 118 卷全唐诗快照恰一、恰在卷253 这行题注（机器断言）——与选本页 notes'
        '「一作朱斌詩」两处独立成对，**只登记不裁决**（V079 江南曲同款规则）。V018 作者'
        '判定「署名 王之渙：选本与维基文库页面两处转录一致」在册零重开；V018 text claim 已'
        '持 KNOWN（在册零重开），本迁移自铸 claims 零 KNOWN（如实记录第卅二例，audit 反向'
        '断言）。无传的人活在总集编者的附记里——系读法声明。',
    ),
}
BG = {k: (v[0] if isinstance(v, tuple) else v) for k, v in BG.items()}

BG_LINES = {'bg-361-scene': (1,), 'bg-361-city': (2,),
            'bg-361-world': (3,), 'bg-361-person': (4,)}
BG_AUDIENCE = {'bg-361-scene': 'PRIMARY', 'bg-361-city': 'JUNIOR',
               'bg-361-world': 'SENIOR', 'bg-361-person': 'JUNIOR'}
BG_TITLES = {
    'bg-361-scene': '眼前：白日与大河的净面',
    'bg-361-city': '这座城：全唐诗里的一只空壳',
    'bg-361-world': '这个天下：白日救乱，黄河沉人',
    'bg-361-person': '这个人：正史无传，编者有记',
}
CLAIMS = {
    'claim-bg-361-scene': ('FACT', 'LIKELY',
        '四句取 ws 选本页 poem 块存原样面入引（题面{{另|雀|鵲}}+行内<ref>「入」一作徹孤注'
        '（无reflist照登）+{{另|層|重}}+行尾随空格——全页四个异文/归属载体；V018 句读式'
        '「白日依山盡，……更上一層樓。」一引在先零重开硬断言——正文第二引第二十四例）；'
        '**存储面即定読面首枚**（V018 ws-raw 四行净文=页物理行折叠面：雀/層取头部主读、'
        '<ref>整段裁——异文定読分工面：页面存异读/库存储定读，生成时拼合断言）；满级页'
        '{{Textquality|100%}}（26页闭域）'),
    'claim-bg-361-city': ('FACT', 'LIKELY',
        '《全唐詩》卷253 三级诗锚「===[[登鸛雀樓 (王之渙)|登鸛雀樓]]===」+粗斜体双题注'
        '「一作《登鸛鵲樓》。一作朱斌詩。」+空壳转引整块逐字入引（**卷页层级首见**：本卷'
        '37/37 通例机器断言；**编者题注直书归属异议**；四句净文118卷快照全零——**壳在册**，'
        '与 V075 在册外零成谱）；卷283 司马都「同崔邠登鸛雀樓」锚+壳逐字入引（283 源第三次'
        '复用——题面跨诗人）；**选本标记缺席首枚**（无三百首标记48页闭域）+千家詩类目行'
        '（另一选本，本页身兼两选本）+孤儿</sub>全库唯本页照登；**恰新建卷页源一枚**'
        '（source-quantangshi-253——V066 以来立源全为选本页源，本篇首立卷页源）'),
    'claim-bg-361-world': ('FACT', 'LIKELY',
        '通鉴白日恰一（中和二年阡能案百姓见高仁厚「如出九泉睹白日，已死而復生矣」出九泉之喻）'
        '/黃河恰一（天祐二年李振疾搢紳「此輩常自謂清流，宜投之黃河，使為濁流」拟沉清流之'
        '浊水）闭域入引；千里目/層樓/鸛/鹳/王之渙/朱斌通鉴全零；V015 白馬驛旧唐書在册句只'
        '对照不重开（audit 硬断言白馬驛不入引文）——白日与黄河各有其账、无一册在看景'
        '（同字两界第二十一形态·看景形态首见，对照判决非史实因果）'),
    'claim-bg-361-person': ('FACT', 'LIKELY',
        '王之渙/朱斌/崔國輔/鄭昈/之賁七史快照全零（jts 27+xts 8+qss 3+通鉴 75——零传记之人'
        '系列第二枚，机器断言）；本库唯一传系卷253 编者附记「幷州人…聯唱迭和，名動一時。'
        '詩六首」逐字入引（新源承载）；朱斌118卷恰一恰在此题注+选本页notes两处独立成对，'
        '只登记不裁决（V079 同款规则）；V018 作者判定在册零重开；KNOWN 零如实记录第卅二例'),
}
CITATIONS = [
    ('claim-bg-361-scene', 'source-ws-t300-361',
     '页面 登鸛雀樓 (王之渙)（《唐詩三百首》第 361 首選本页；header title+author+poem 块'
     '两物理行存原样以「……」相连——题面内嵌 {{另|雀|鵲}}（全库题面{{另}}恰 5 页闭域）、'
     '行1内嵌《文苑英華》「一作徹」<ref> 孤注（全页无 reflist，孤注照登）+行尾随空格照登、'
     '行4 {{另|層|重}}——一页四个异文/归属载体；**存储面即定読面首枚**：V018 ws-raw 四行'
     '净文=本页折叠面（雀/層取头部主读、<ref>整段裁，生成时拼合双向断言）；正文第二引'
     '第二十四例零重开',
     join(WS_TITLE, WS_AUTHOR, WS_POEM_A, WS_POEM_B)),
    ('claim-bg-361-city', 'source-ws-t300-361',
     '页面 登鸛雀樓 (王之渙)（from 三行底本链（文苑英華/御定全唐詩/國秀集——from2+from3'
     '全库 15 页闭域）+notes 整值（一作朱斌+參見國秀集+满级评级尾置）+edition= yes（17 页'
     '闭域）+页尾类目三连含空行（代表作品/千家詩/有声文献**全库唯一**——千家詩系另一选本'
     '类目行，本页身兼两选本）+孤儿</sub>（全库唯本页，照登不判）——**选本标记缺席首枚**'
     '（无三百首标记 48 页闭域机器断言）；类目系整理者动作：非史料声明、不升格（V048）',
     join(WS_FROM, WS_NOTES, WS_ED, WS_CAT3, WS_ORPH)),
    ('claim-bg-361-city', 'source-quantangshi-253',
     '卷二百五十三（多诗人合卷）「===[[登鸛雀樓 (王之渙)|登鸛雀樓]]===」三级锚+粗斜体双题注'
     '「一作《登鸛鵲樓》。一作朱斌詩。」+「{{:登鸛雀樓 (王之渙)}}」空壳整块逐字入引'
     '（**卷页层级首见**：三级锚系本卷 37/37 通例机器断言；**编者题注直书归属异议**；'
     '四句净文 118 卷快照全零——壳在册与 V075 在册外零成谱；**本迁移恰新建此卷页源一枚**）',
     V253_TITLEBLOCK),
    ('claim-bg-361-city', 'source-quantangshi-283',
     '卷二百八十三·司马都「==[[同崔邠登鸛雀樓]]==」锚+空壳转引逐字入引（同题另人——题面'
     '跨诗人形态之 283 侧；283 源在册第三次复用零新建；「登鸛雀樓」字面快照恰两卷 253/283'
     '机器断言）',
     V283_ANCH),
    ('claim-bg-361-world', 'source-zizhi-tongjian-events',
     '卷二百五十五·中和二年（壬寅，八八二）阡能之乱平，蜀中百姓见高仁厚「如出九泉睹白日，'
     '已死而復生矣」（**史的白日是解围军队出九泉之喻**）……卷二百六十五·天祐二年（乙丑，'
     '九〇五）李振疾搢紳「此輩常自謂清流，宜投之黃河，使為濁流！」（**史的黄河是拟沉清流'
     '的浊水**）；通鉴白日恰一/黃河恰一（文件闭域+两处年标题窗口机器断言）；千里目/層樓/'
     '鸛/鹳/王之渙/朱斌全零；V015 白馬驛旧唐書在册句只对照不重开——两段逐字入引为看景'
     '两界判决证据',
     join(TJ_BAI, TJ_HH)),
    ('claim-bg-361-person', 'source-quantangshi-253',
     '卷二百五十三·王之渙小传整段逐字入引（**正史无传、总集编者给的本库唯一传**：王之渙/'
     '朱斌/崔國輔/鄭昈/之賁史部快照全零——jts 27+xts 8+qss 3+通鉴 75 机器断言；「朱斌」'
     '118 卷恰一恰在本卷题注——归属异议对方名字只活在编者注里；与选本页 notes 两处独立'
     '成对只登记不裁决，V079 同款规则；之咸在册两条系另一人不攀附；新源承载）',
     V253_BIO),
]

BG_SUMMARY = {k: '四层处境背景（阶段 D 第 57 首·四句五绝 1/1/1/1 第八次）；史实句均有逐字引证；'
                 '系年第五十一次判决（题证系列第卅九状·白日与黄河各有其账，无一册在看景）'
                 '「诗的白日与黄河，通鉴各恰一处，没有一处在看景」——'
                 '同字两界第二十一形态·看景形态首见：白日恰一（中和二年阡能案「如出九泉睹'
                 '白日」）/黃河恰一（天祐二年李振「宜投之黃河，使為濁流」）闭域入引；'
                 '千里目/層樓/鸛/鹳/王之渙/朱斌通鉴全零；V015 白馬驛在册句只对照零重开；'
                 '壳在册（四句净文 118 卷全零、卷253 锚下挂空壳——与 V075 在册外零成谱）；'
                 '卷页层级首见（三级锚本卷 37/37 通例+编者题注直书归属异议）；'
                 '存储面即定読面首枚（V018 ws-raw 净文=页折叠面——异文定読分工面：页面存'
                 '异读/库存储定读）；选本标记缺席首枚（48 页闭域）+有声页全库恰三页+类目'
                 '三连全库唯一；同题另人卷283 司马都逐字入引（283 源第三次复用）；'
                 '王之渙/朱斌七史全零·零传记之人第二枚（正史无传、本库唯一传系卷253 编者'
                 '附记——「名動一時」是编者给的）；朱斌 118 卷恰一在题注+选本 notes 两处'
                 '成对只登记不裁决（V079 同款规则）；**恰新建卷页源一枚 source-quantangshi-'
                 '253**（V066 以来立源全为选本页源，本篇首立卷页源——audit 断言恰一枚）+283/'
                 'ws-361 在册复用；正文第二引第二十四例零重开；KNOWN 零如实记录第卅二例'
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
    A("""-- V076：王之渙《登鸛雀樓》(work-t300-361) 四层背景（阶段 D 第 57 首·看景两界）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V026、V033、V035、V039、V048、V049、V053、
--       V055、V057、V058、V059、V060、V061、V062、V063、V064、V065、V066、V067、V068、
--       V069、V070、V071、V072、V073、V074、V075 已执行
--       （work-t300-361 与其 text-work-t300-361-ws（version_code=ws-raw——V018 立此诗正文
--       用的就是《唐詩三百首》选本页，四行净文全无尾随空格——是本页 poem 块的**折叠面**：
--       题面/句4 {{另}} 取头部主读雀/層、行1内嵌《文苑英華》「一作徹」<ref> 整段裁去；
--       **存储面即定読面首枚**：页面存异读、库存储定读——异文定読分工面）
--       与其源 source-ws-t300-361（V018 已立的选本页源，本迁移第二次复用零新建）；
--       source-quantangshi-283（V033 已立的卷283 卷页源，第三次复用）、
--       source-zizhi-tongjian-events（V014/V015 已立的通鉴事件源）是既有行；
--       **本迁移恰新建一枚 source：source-quantangshi-253**——卷253 多诗人合卷卷页源，
--       承载王之渙小传+双题注+空壳（朱斌系全快照恰一唯一载体）：V018 用选本页立正文，
--       卷页见证面反而无源（V066 判例镜像首枚：那首选本页无源立选本页源，本篇卷页无源
--       立卷页源——V066 以来所立 source 全为选本页源，本篇首立卷页源；audit 断言本文件
--       恰一枚 poetry_source INSERT、回滚恰删此一枚）；
--       判例在册句（白日依山盡句读式全引/header author=王之渙 V018、
--       白馬驛投屍旧唐書句 V015——只对照不重开，audit 硬断言「白馬驛」三字不入引文）。
--
-- 数据源（可复现）：emit_v076.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/登鸛雀樓__王之渙_.txt（全库标记最密诗页：题面 {{另|雀|鵲}}（题面{{另}}5页闭域）+
--   行内 <ref> 孤注无 reflist+{{另|層|重}}+行尾随空格+notes 一作朱斌+满级评级尾置+from 三行
--   （from2+from3 15页闭域）+edition=yes（17页闭域）+类目三连全库唯一+孤儿</sub>全库唯本页+
--   {{Spoken Wikisource}} 有声页恰3页+无三百首标记48页闭域首枚）、
--   V018 存储面重建比对（text-work-t300-361-ws 四行 vs ws poem 块折叠面双向断言）、
--   全唐詩快照卷253（三级锚37/37通例+双题注+空壳+小传——壳在册+卷页层级首见+零传记之人
--   本库唯一传）+卷283（司马都同崔邠登鸛雀樓锚+壳逐字入引）+卷018/140（王之渙字面恰三卷
--   8/1/1 计数只档扫不入引）+
--   通鑑卷255/265（白日/黃河两段逐字入引+年标题窗口：中和二年八八二/天祐二年九〇五）+
--   通鑑 75 卷负证计数扫描（白日恰一+黃河恰一+千里目/層樓/鸛/鹳/王之渙/朱斌/國秀集/
--   文苑英華全零）+全唐詩快照负证（四句净文全零+朱斌恰一在253题注+登鸛雀樓恰两卷253/283+
--   千里目恰一在018只计数）+七史快照（jts 27+xts 8+qss 3+通鉴 75）王之渙/朱斌/崔國輔/
--   鄭昈/之賁全零机器断言（之咸在册系另一人不攀附）+
--   ws 全库 295 页闭域档扫（题面另5/notes一作13/无三百首48/有声3/三连1/孤儿sub1/from二三15/
--   edition17/满级26）+既有迁移引文域逐句查重——在册零重开、二引/零重开/首引零域前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 6 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 background_line（四句五绝 **1/1/1/1 第八次**：scene→1 city→2 world→3 person→4，
--   绑 text-work-t300-361-ws 的 4 行）+ 恰新建 source 一枚（source-quantangshi-253）+
--   不碰 poetry_text_line。
-- 不做：**不新建除 253 外的任何 source**（audit 断言恰一枚、回滚恰删此一枚）；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「壳在册：底本在场但正文挂在他页」）：
--   * 四句在 118 卷全唐诗快照全零、在册形态是卷253 锚下空壳转引——**壳在册非正文在册**，
--     本迁移不逐字引壳的目标页（那在他书/他卷，快照里没有即无可核切片）；
--   * 「看景两界」「白日救乱黄河沉人」系通鉴两段逐字入引支撑的对照判决，非史实因果——
--     通鉴不记这首诗；亦不考本诗系年（编年诸说一律不采信不铸造）；
--   * 「名動一時」是总集编者语不是史部语——入引标明承载源；「正史无传」严格限于本地
--     七史快照——不排除纸面史部另有传（无快照即不能说）；
--   * 一作《登鸛鵲樓》/一作朱斌詩：**两处见证（卷253 题注+选本页 notes）并列只登记不裁决**
--     （异文只登记不裁决总判例）；雀/層取 {{另}} 头部主读系 V018 存储事实的登记非本迁移裁决；
--   * 卷283 同崔邠登鸛雀樓系同题另人只登形不推归属；千家詩类目行/有声文献类目系整理者
--     动作：非史料声明、不升格，V048 判例；
--   * 满级 100% 页 26、有声页 3、三连 1 页、孤儿</sub> 1 页均照登不判；
--   * KNOWN 零如实记录（第卅二例——V018 text claim 的 KNOWN 在册零重开不碰，audit
--     反向断言本迁移 SQL 无 KNOWN 字面量）；
--   * V011/V014/V015/V016/V018/V026/V033/V035/V039/V048/V049/V053/V055/V057/V058/V059–V075
--     已引诸句只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 75，不含 76
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-361-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-361',
--     'source-quantangshi-283','source-quantangshi-253');               -- 恰两行（253 本迁移新建前不存在）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-361-ws';  -- 恰 4
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-361-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-361';                                  -- 4（1/1/1/1）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-361-%';  -- 四行全 LIKELY
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-quantangshi-253';  -- 恰 1（本迁移所立）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-361'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-361';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-361-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V076_rollback.sql（按 id 全枚举删除；**source 只删一行**——
--   source-quantangshi-253 是本迁移新建的卷页源（恰一枚，审计断言）按 id 删除；
--   source-ws-t300-361 是 V018 所立的选本页源、source-quantangshi-283 是 V033 所立的
--   卷283 源（本迁移复用），绝不删；work-t300-361 本体与其 text_line 4 行都是 V018 的行，绝不删）
START TRANSACTION;""")

    A('\n-- ---------- 0. 新建卷页源一枚（source-quantangshi-253——V066 判例镜像首枚） ----------')
    src = [{'id': 'source-quantangshi-253', 'title': '御定全唐詩 (四庫全書本) 卷二百五十三（王之渙 閻防 薛據 姚係 令狐峘 滕珦合卷）',
            'author': None, 'edition': '御定全唐詩 (四庫全書本)',
            'url': 'https://zh.wikisource.org/wiki/全唐詩/卷253',
            'rights_note': '维基文库录入本，公有领域古籍。本行由 emit_v076.py 对 /tmp/src-dl 快照逐字定位。本诗 V018 立正文时用的是《唐詩三百首》选本页（source-ws-t300-361，version_code ws-raw），此《御定全唐詩》卷253 卷页当时未建源——选本页与卷页是两个独立见证面（选本页 header 署名/notes 一作朱斌 vs 卷页编者可入引载体——王之渙小传+粗斜体双题注「一作《登鸛鵲樓》。一作朱斌詩。」+空壳转引），本迁移引卷页非新源不能承载（V066 判例镜像首枚：V066 以来所立 source 全为选本页源，本篇首立卷页源）。页面 {{Textquality|75%}} 七五评级（照登）；三级诗锚 37/37 通例（卷页层级）。核验状态保持 PENDING。',
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
    brows = [{'id': k, 'work_id': 'work-t300-361',
              'layer': {'bg-361-scene': 'SCENE', 'bg-361-city': 'CITY',
                        'bg-361-world': 'WORLD', 'bg-361-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（四句五绝 1/1/1/1 第八次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-361-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 76, 'Wang Zhihuan''s Climbing the Stork Tower (work-t300-361) background layers (stage-D poem 57, the most-marked poem page in the whole corpus; four-line quatrain 1/1/1/1, eighth time): dating verdict fifty-one, thirty-ninth shape of the title-evidence series -- the poem''s white sun and yellow river; the Tongjian has exactly one entry for each, and not one of them is watching the view. Same-character-two-realms, twenty-first shape: the scenic (kanjing) shape, first seen. Baiyun (white sun) appears exactly once in the Tongjian (Zhonghe 2, renyin, 882: after the Qian Neng revolt was crushed, the people of Shu greeted Gao Renhou "as if raised from the nine springs to see the white sun, dead and born again" -- the history''s white sun is the metaphor for a relieving army, the poem''s white sun is the sun setting behind the mountains). Huanghe appears exactly once (Tianyou 2, yichou, 905: at Baima station Li Zhen, hating the gentry, told Zhu Quanzhong "these fellows always called themselves the pure stream -- better throw them into the Yellow River and let them become the muddy flow" -- the history''s Yellow River is the ditch proposed for drowning the pure stream, the poem''s Yellow River is living water running to the sea; V015''s closed Old Tangshu sentence on the same massacre is juxtaposed only, and the audit hard-asserts the three characters for the station name never re-enter any citation of this migration). Qianlimu (thousand-li gaze), cenglou (upper storey), the heron characters in both graphforms, Wang Zhihuan and Zhu Bin all score zero in the Tongjian (machine-asserted): the poem''s two great landscapes land in no ledger of the histories (declared contrast, not historical causation). SHELL-ON-RECORD: unlike V075''s out-of-catalog zero, the base book here is present in the snapshot -- Quan Tangshi juan 253 carries the poem as an empty transclusion shell {{:登鸛雀樓 (王之渙)}}, and the four clean lines score zero across the 118 snapshot volumes (machine-asserted): on record as a shell, not as text; the shell''s target page is never quoted (if it is not in the snapshot there is no verifiable slice -- the honest boundary of this poem). VOLUME-HIERARCHY, first seen: juan 253 is a multi-poet volume and anchors poems at heading level three, "===[[...]]===" -- 37 of 37 anchors in this volume (machine-asserted); under the anchor sits the editors'' bold-italic double note "variant title: Climbing the Stork-and-Magpie Tower; alternatively by Zhu Bin" -- the editors'' title-note stating an attribution dispute outright (an upgrade of V073''s curator author-note at the anchor; registered, never adjudicated). THE STORED FACE IS THE READING FACE, first seen: the page is the most heavily marked poem page of the corpus -- title carries {{另|雀|鵲}}, line 1 carries an inline {{文苑英華}} "variant: 徹" <ref> with no reflist anywhere on the page (an orphan note, registered as-is), line 4 carries {{另|層|重}}, and the notes field says "alternatively by Zhu Bin, see Guoxiuji": four variant/attribution carriers on one page. V018 stored the poem with version_code ws-raw as four clean lines -- the folded face of this page: 雀/層 taken from the head of {{另}}, the whole <ref> fragment trimmed (generator asserts the pair-join both directions). Same-face-zero-divergence does not hold here; what holds is DIVISION OF LABOR BETWEEN VARIANTS AND READING: the page keeps the readings, the store keeps the decision. THE ANTHOLOGY MARKER IS ABSENT, first of its closed set: the page carries neither {{唐詩三百首}} nor its category (closed set: exactly 48 pages corpus-wide, machine-asserted) -- the anthology''s claim on this poem rests on the editorial ledger, not on the page''s self-declaration; the footer categories include the 千家詩 line (a different anthology''s category: this page serves two anthologies) in a triple-category run unique in the corpus (代表作品/千家詩/有声文献), with {{Spoken Wikisource}} putting this page in the corpus-wide set of exactly three voiced pages (a 2020 Mandarin recording -- a modern layer, registered, not a historical source), plus an orphan </sub> closer unique corpus-wide (registered, not judged); the category lines are curator actions: not source claims, not upgraded (V048). Same-title-different-poet: juan 283 anchors "同崔邠登鸛雀樓" (Tong Cbin climbing the tower, under Sima Du) with its own shell, quoted verbatim (the 283 source at its third reuse; the literal 登鸛雀樓 appears in exactly two snapshot volumes, machine-asserted). PERSON: ZERO-BIOGRAPHY PERSON, second of the series -- Wang Zhihuan, Zhu Bin, Cui Guofu and Zheng Hu all score zero across the local history snapshots (27 JTS + 8 XTS + 3 QSS + 75 Tongjian volumes, machine-asserted; the two Zhi Xian hits belong to a different man and are not claimed). But unlike the man of V075, he has a biography -- two lines in the Quan-Tangshi editors'' appendix, quoted verbatim as this migration''s PERSON evidence: "Wang Zhihuan, a man of Bingzhou; his brothers Zhixian and Zhibi were all known for letters. In the Tianbao era he traded verses in turn with Wang Changling, Cui Guofu and Zheng Hu, and his name moved the age in one breath. Six poems." -- "his name moved the age" is a sentence the histories never gave him and the anthology editors did. The rival name lives only in an editor''s note: 朱斌 appears exactly once in all 118 Quan-Tangshi snapshot volumes -- inside this very note (machine-asserted) -- and once more, independently, in the anthology page''s notes: two witnesses registered side by side, nothing adjudicated (the V079 Jiangnan-qu rule). NEW SOURCES: exactly one -- source-quantangshi-253, the volume page (first volume-page source ever created: every source created since V066 was an anthology-page source; here it is the volume page that lacks a row while the anthology page already has V018''s -- the V066 precedent, mirrored for the first time; the audit asserts exactly one source insert and exactly one source delete in the rollback), while sources ws-t300-361 (second reuse) and quantangshi-283 (third reuse) are existing rows. Body use-ceiling, twenty-fourth instance: V018''s punctuated excerpt stands first and is never re-opened (hard assertion); the body is now closed. KNOWN zero honestly recorded (thirty-second instance -- V018''s own KNOWN text claim stays closed and untouched; audit reverse-asserts no KNOWN literal in this migration); closed precedent keywords (V018''s punctuated full quote and header-author line, V015''s Baima-station sentence) stay out of all citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 76);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V076 精确回滚：只删 V076 插入的行（id 全枚举）。**source 只删一行**——',
         '-- source-quantangshi-253 是本迁移新建的卷页源（恰一枚，审计断言），按 id 删除；',
         '-- source-ws-t300-361 是 V018 所立的选本页源、source-quantangshi-283 是 V033 所立的卷283 源（本迁移复用），绝不删；',
         '-- work-t300-361 本体与其 text_line 4 行都是 V018 的行，绝不删；',
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
    L.append('DELETE FROM poetry_source WHERE id = ' + sql_s('source-quantangshi-253') + ';')
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 76;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V076')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

def _domain_src(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V076')
                   and needle in f.read_text(encoding='utf-8')})

for _premise, _needle, _want in (
        ('本诗首句(V018 句读式一引)', '白日依山盡', ['V018']),
        ('本诗末句(V018 句读式收尾)', '更上一層樓', ['V018']),
        ('V018 句读式全引不重开', '白日依山盡，……更上一層樓。', ['V018']),
        ('本页署名行(V018 header 直证在册)', 'header author=王之渙', ['V018']),
        ('白馬驛在册(V015 旧唐書投屍句——零重开硬卡)', '白馬驛', ['V015']),
        ('千家詩类目行在册(V053 春曉页对照——本页另页异证非重开)', '千家詩', ['V053']),
        ('文苑英華在册(V049/V053 <ref>体系对照——本页孤注另证)', '文苑英華', ['V049', 'V053']),
        ('本诗选本页源已立(V018——第二次复用前提)', 'source-ws-t300-361', ['V018']),
        ('卷283 源在册(第三次复用)', 'source-quantangshi-283', ['V033', 'V053']),
        ('V066 选本页源判例在册(本篇卷页源镜像对照)', 'source-ws-t300-031', ['V066', 'V067', 'V068']),
        ('新源未立前提(source-quantangshi-253 系本迁移新建)', 'source-quantangshi-253', [])):
    _prev = _domain_src(_needle) if (_needle.startswith('source-')) else _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
for _first, _needle in (('题面折叠前切片', '| title    = 登鸛{{另|雀|鵲}}樓'),
                        ('页物理行1(带<ref>孤注)', '白日依山盡，黃河入海流。<small>'),
                        ('页物理行2({{另|層|重}}面)', '欲窮千里目，更上一{{另|層|重}}樓。'),
                        ('notes 一作朱斌整值', '| notes    = 一作[[Author:朱斌|朱斌]]詩'),
                        ('edition 定本标记', '| edition= yes'),
                        ('from 三行链首行', '| from     = 文苑英華 (四庫全書本)/卷0312'),
                        ('类目三连有声行', '[[Category:有声文献]]'),
                        ('孤儿</sub>', '</sub></center>'),
                        ('卷253 三级锚', '===[[登鸛雀樓 (王之渙)|登鸛雀樓]]==='),
                        ('卷253 双题注', '一作《登鸛鵲樓》。一作朱斌詩。'),
                        ('卷253 空壳', '{{:登鸛雀樓 (王之渙)}}'),
                        ('卷253 小传', '王之渙，幷州人'),
                        ('名動一時', '名動一時'),
                        ('卷283 同题锚', '同崔邠登鸛雀樓'),
                        ('通鉴白日喻', '如出九泉睹白日'),
                        ('通鉴黄河语', '宜投之黃河'),
                        ('使為濁流', '使為濁流')):
    if _domain(_needle):
        raise SystemExit(f'首引句「{_first}」既往域非零——须换句或降级')


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_POEM_A, WS_POEM_B, WS_FROM, WS_NOTES, WS_ED,
              WS_CAT3, WS_ORPH, V253_TITLEBLOCK, V283_ANCH, TJ_BAI, TJ_HH, V253_BIO]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # SCENE：折叠断言的三标记件必须逐字在引文内（异文定読分工面硬卡）
    sc = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-361-scene' and s == 'source-ws-t300-361')
    if '{{另|雀|鵲}}' not in sc or '{{另|層|重}}' not in sc:
        bad.append('{{另}} 双件未全入 SCENE 引文（异文定読分工面硬卡）')
    if "<ref>「入」：《文苑英華》注「一作'''徹'''」</ref>" not in sc:
        bad.append('行内<ref>孤注件未入 SCENE 引文（孤注照登硬卡）')
    if '</small></small> ' not in sc:
        bad.append('<ref>孤注尾随行空格面未入 SCENE 引文（照登硬卡）')
    if '白日依山盡，……更上一層樓。' in cited:
        bad.append('V018 句读式引文重开了——本迁移引 poem 存原样面，句读式不重开')
    # CITY：壳在册三件套+双题注必须逐字入 253 引文；283 侧必须入引
    q253 = next(ex for c, s, _, ex in CITATIONS if s == 'source-quantangshi-253' and c == 'claim-bg-361-city')
    for tok in ('===[[登鸛雀樓 (王之渙)|登鸛雀樓]]===', '一作《登鸛鵲樓》。一作朱斌詩。', '{{:登鸛雀樓 (王之渙)}}'):
        if tok not in q253:
            bad.append(f'卷253 壳在册件「{tok[:12]}…」未入 CITY 引文（卷页层级首枚硬卡）')
    ws_c = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-361-city' and s == 'source-ws-t300-361')
    if '[[Category:有声文献]]' not in ws_c or '</sub></center>' not in ws_c:
        bad.append('类目三连/孤儿</sub> 未入 CITY 诗页引文（全库唯一断言硬卡）')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-361-city' and s == 'source-ws-t300-361'):
        bad.append('CITY 诗页 locator 须含「不升格」声明')
    q283 = next(ex for c, s, _, ex in CITATIONS if s == 'source-quantangshi-283')
    if '同崔邠登鸛雀樓' not in q283:
        bad.append('卷283 同题锚未入 CITY 引文（题面跨诗人硬卡）')
    # WORLD：两段通鉴史文必须逐字入引；在册句与诗语零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-361-world')
    for tok in ('如出九泉睹白日', '已死而復生矣', '此輩常自謂清流', '宜投之黃河', '使為濁流'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（两段必须入引）')
    for tok in ('白馬驛', '時樞等七人已至滑州'):
        if tok in cited:
            bad.append(f'在册零重开判例「{tok}」混入本迁移引文')
    for tok in ('白日依山盡', '黃河入海流', '欲窮千里目', '更上一層樓'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文——SCENE 引诗面系另一事）')
    w_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-361-world')
    if '白日' not in w_loc or '黃河' not in w_loc:
        bad.append('WORLD locator 须点出白日/黃河（看景两界声明）')
    # PERSON：小传必须逐字入引；之咸另一人不攀附断言在 locator
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-361-person')
    for tok in ('王之渙，幷州人', '聯唱迭和', '名動一時', '詩六首'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺小传要素「{tok}」（编者唯一传硬卡）')
    if '之咸在册两条系另一人不攀附' not in next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-361-person'):
        bad.append('PERSON locator 须含「之咸系另一人不攀附」声明')
    # 判例只引不重开
    for tok in ('白日依山盡，……更上一層樓。', 'header author=王之渙', 'header author=劉眘虛',
                'header author=李益', '幽映每白日', '清輝照衣裳', '刻青石為奇字',
                '玉皇授白雲先生高駢', '而能試文三篇', '謂之宏詞', '開青溪道', '車如流水',
                '客去波平檻', '本以高難飽', '君問歸期未有期', 'theme2   = 詠春詩',
                '↑ [[全唐詩/卷256', '卷256: FAILED', '{{:闕題', '時樞等七人已至滑州',
                '皆並命于白馬驛', '投屍於河。'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    if BG_LINES != {'bg-361-scene': (1,), 'bg-361-city': (2,),
                    'bg-361-world': (3,), 'bg-361-person': (4,)}:
        bad.append('四句 background_line 须 1/1/1/1 顺次（四句绝句常规·第八次）')
    if len(re.findall(r"text-work-t300-361-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    # 恰新建 source 一枚（V066 判例镜像首枚·首立卷页源）
    if sql.count('INSERT INTO poetry_' + 'source') != 1:
        bad.append('V076 有意恰新建一枚 source（source-quantangshi-253），但 SQL 里 source INSERT 数不是 1')
    if sql_s('source-quantangshi-253') not in sql:
        bad.append('source-quantangshi-253 未入 SQL')
    rb = build_rollback()
    if rb.count('DELETE FROM poetry_' + 'source') != 1:
        bad.append('V076 恰新建一枚 source，回滚须恰含一行 source 删除')
    if 'DELETE FROM poetry_source WHERE id = ' + sql_s('source-quantangshi-253') not in rb:
        bad.append('回滚的 source 删除行不是 source-quantangshi-253')
    for keep in ('source-ws-t300-361', 'source-quantangshi-283'):
        if f'DELETE FROM poetry_source WHERE id = ' + sql_s(keep) in rb:
            bad.append(f'回滚误删既有源 {keep}')
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if len(CITATIONS) != 6:
        bad.append('本迁移引文应为 6 组')
    if "'written_during' AS predicate" in sql:
        bad.append("V076 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V076 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-361' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V076 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-361' AS subject_id" in sql:
        bad.append('V076 的 claim 主语应全部是 bg-361-*，work-t300-361 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V076 不碰 poetry_text_line')
    body_all = ''.join(BG.values())
    if '看景形态' not in body_all:
        bad.append('BG 须含「看景形态」（同字两界第二十一形态）声明')
    if '壳在册' not in body_all:
        bad.append('BG/CITY 须含「壳在册」声明')
    if '存储面即定読面' not in body_all:
        bad.append('BG/SCENE 须含「存储面即定読面首枚」声明')
    if '卷页层级首见' not in body_all:
        bad.append('BG/CITY 须含「卷页层级首见」声明')
    if '零传记之人' not in body_all:
        bad.append('BG/PERSON 须含「零传记之人系列第二枚」声明')
    if '只登记不裁决' not in body_all:
        bad.append('BG/PERSON 须含一作朱斌「只登记不裁决」声明')
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
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 76)' not in vblk:
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
              f'V018 存储面四行重建 vs ws poem 块折叠面（{{{{另}}}}取头部主读+<ref>整段裁）双向断言+题面折叠断言；'
              f'两处年标题窗口断言（中和二年八八二/天祐二年九〇五）；'
              f'负证机器复查五层（通鉴白日恰一+黃河恰一+千里目/層樓/鸛/鹳/王之渙/朱斌/國秀集/'
              f'文苑英華/依山海/黃河入海/白日依山/欲窮千里/更上/千里眼全零/'
              f'全唐诗四句净文全零+朱斌恰一在253题注+登鸛雀樓恰两卷253/283+千里目恰一+三级锚谱'
              f'20卷+253锚形37/37通例+王之渙恰三卷8/1/1+小传唯一/七史王之渙朱斌崔國輔鄭昈之賁全零/'
              f'ws 题面另5+notes一作13+无三百首48含本页+有声3含本页+三连唯一含本页+孤儿sub唯一含本页+'
              f'from二三15+edition17+满级26+本页负形九项零标记，快照变动即中止）；'
              f'前提全库查重硬卡十一件+十七首引句零域断言+新源未立前提（source-quantangshi-253 零域）断言；'
              f'SCENE {{另}}双件+<ref>孤注件+尾空格入引+V018 句读式引文零重开断言；'
              f'CITY 253 壳三件套入引+283 同题锚入引+「不升格」硬卡；'
              f'两段通鉴史文入引+在册句（白馬驛/時樞等句）与诗语零混入断言；'
              f'PERSON 小传四要素入引硬卡+之咸另一人不攀附声明；'
              f'判例只引不重开断言（含 V018 署名/句读式、V015 白馬驛句、V053 春曉类目行、V075 诸句在内）；'
              f'四句 1/1/1/1 形制断言；零 KNOWN 反向断言；恰新建 source 一枚正反断言+回滚恰删此一枚断言；'
              f'幂等/宽度/主键/幂等版本账本守卫全数过审')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql)} B) + {args.out_rollback} ({len(rb)} B)')


if __name__ == '__main__':
    main()
