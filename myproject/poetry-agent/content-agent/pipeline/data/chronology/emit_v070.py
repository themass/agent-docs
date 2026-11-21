#!/usr/bin/env python3
"""阶段 D 第 51 首：生成 V070——李商隱《夜雨寄北》(work-t300-013, V018 已立) 四层背景。

**本迁移零新建 source——连续第二首**（V069 开零新源侧，本篇续之）。
本诗底本面与 V066–V068 同向（底本=选本 ws 页，V018 已立 source-ws-t300-013、
version_code 'ws-xbook-fold'），但《全唐詩》卷539 的见证面**不是正文块而是空壳转引**
（==[[夜雨寄北]]== 下只有 {{:夜雨寄北}} 一行）——**卷页无正文一字**（机器断言：
539 全卷 歸期/秋池/西窗/剪/巴山 全零），第三形态。

「为什么写」走到**夜雨家书两界**（同字两界第十五形态·家书形态首见）：
**诗里一夜的雨，通鉴全库没有；史部唯一的家书是斩封的——「天子何在，敢言家乎」；
史部两滴秋霖都是政务（报灾与阿附）；史部唯一的行旅是贞观之治；
诗的老板郑亚，大中二年贬循州——史部有他的官，没有他的雨**——

四层判决：
① 通鉴「夜雨/歸期/秋池/西窗/剪燭/巴山/寄北/寄内」全零（机器断言）——
   诗题连「寄北」二字史部都不识；
② 「秋霖」恰二全在大曆十二年（丁巳，七七七）：「**京兆尹黎幹奏秋霖損稼**，韓滉奏
   幹不實……『**所損凡三萬餘頃。**』」+「**先是，秋霖，河中府池鹽多敗**……奏雨雖多，
   不害鹽，**仍有瑞鹽生。**」——**史部的雨是公文：一场雨两条奏状，一条报灾被驳、
   一条报平安造假；诗里同一场雨只写给一个人**；
③ 「家書」恰一在興元元年（甲子，七八四）李晟困长安：「**軍中有言及家者**，晟泣曰：
   『**天子何在，敢言家乎！**』」**朱泚使以家書遺晟曰「公家無恙」，晟怒立斬之**——
   **史部的家书是斩封的；诗的家书是想象共剪的**（「君問歸期未有期」对「立斬之」）；
④ 「行旅」恰一在貞觀四年（庚寅，六三〇）「**東至於海，南及五嶺，皆外戶不閉，
   行旅不繼糧，取給於道路焉**」——**史部唯一的行旅是贞观之治的路不拾遗；
   诗的行旅是巴山一夜，回不去**；又「**桂管觀察使鄭亞坐前不能直吳湘冤……亞貶循州刺史**」
   （大中二年戊辰八四八）——诗的老板在通鉴只有贬官一行。

ws 页形制（SCENE/CITY 层）：**小写 {{textquality|75%}} 评级形态全库首见**
（此前 ws 库评级只有大写 {{Textquality|75%}}/100% 或无评级——本页独一份；
机器断言本页大写全零）；**notes 行空壳**（| notes 空值+三百首标记在 header 外——
V069 「↑底本回指」的反面：本页 notes 空，回指方向反由卷页 {{:}} 转引承担）；
**异文三件套 {{另|當|時}}+<ref>注+{{reflist}} 且无大写评级——全 ws 库仅此一页**
（机器断言）；from 三行版本目录：底本 李義山詩集 (四部叢刊本)/卷第六+
**第三书 墨莊漫録 (四庫全書本)/卷05 恰是异文注的出处**（from 链第三书=异文旁证）；
分类四行含「詠懷詩」类目首见（照登不升格）。**正文第二引上限用满第十八例**：
V018 一引带句读（'君問歸期未有期，……却話巴山夜雨時。'），本迁移二引 ws 页
poem 块**存原样含 <ref> 异文注**（各从其录；V018 句读式引文零重开，生成时硬断言）。

PERSON 层：旧传（**简化字**）首引二段（皆零域）——「**俄而茂元卒，来游京师，久之不调。**」
「**会给事中郑亚廉察桂州……检校水部员外郎。**」：诗的「未有期」对上史传的「久之不调」
——**史部没有这场雨，但把「未有期」四个字写成了官历**；段内**雨/夜/窗/燭/池全零**
（机器断言：诗题有雨，传段无一雨字）；V016「商隐随亚在岭表累载」等在册句零重开。

4 句七绝 shape：1/1/1/1 第七次（V056/V061/V066/V067/V068/V069 之后）。

用法: python3 -I emit_v070.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402

WS = pathlib.Path('/tmp/src-dl/ws-poems/夜雨寄北.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
V539 = pathlib.Path('/tmp/src-dl/quantangshi/vol539.txt').read_text(encoding='utf-8')
TJ193 = pathlib.Path('/tmp/src-dl/tongjian/tj-193.txt').read_text(encoding='utf-8')
TJ225 = pathlib.Path('/tmp/src-dl/tongjian/tj-225.txt').read_text(encoding='utf-8')
TJ230 = pathlib.Path('/tmp/src-dl/tongjian/tj-230.txt').read_text(encoding='utf-8')
TJ248 = pathlib.Path('/tmp/src-dl/tongjian/tj-248.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-21 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 夜雨寄北', '| title    = 夜雨寄北',
                         'ws header title(裸名题面——寄北二字通鉴全零)')
WS_AUTHOR = slice_between(WS, '| author   = 李商隱', '| author   = 李商隱', 'ws header author(署名直证)')
WS_TQ = slice_between(WS, '{{textquality|75%}}', '{{textquality|75%}}',
                      'ws 小写评级全库首见(本页大写 Textquality 全零——评级书写形态第三态)')
WS_LING = slice_between(WS, '何{{另|當|時}}共剪西窗燭', '何{{另|當|時}}共剪西窗燭',
                        'ws Vtext 行折叠形态(异文页内双写：Vtext 用{{另}}、poem 用<ref>注)')
WS_POEM = slice_between(WS, '君問歸期未有期\n巴山夜雨漲秋池\n何當共剪西窗燭<ref>', '卻話巴山夜雨時\n</poem>',
                        'ws poem 块存原样含<ref>异文注(正文第二引——只登记不裁决)')
WS_FROM3 = slice_between(WS,
                         '| from     = 李義山詩集 (四部叢刊本)/卷第六',
                         '| from3    = 墨莊漫録 (四庫全書本)/卷05\n',
                         'ws from 三行版本目录(底本四部叢刊+第三书墨莊漫録恰是异文注出处)')
WS_NOTE3 = slice_between(WS, '| notes    = \n}}\n{{唐詩三百首}}\n', '| notes    = \n}}\n{{唐詩三百首}}\n',
                         'ws notes 空壳(空值+三百首标记在 header 外——V069 ↑回指的反面)')
WS_CAT4 = slice_between(WS, '[[Category:李商隱]]', '[[Category:詠懷詩]]',
                        'ws 分类四行连片(简繁混排第五见+詠懷詩类目首见照登)')
V539_SHELL = slice_between(V539, '==[[夜雨寄北]]==\n{{:夜雨寄北}}', '==[[夜雨寄北]]==\n{{:夜雨寄北}}',
                           '卷539 空壳转引(卷页无正文一字——第三形态;双向绑定集齐之卷页侧)')
TJ_QL1 = slice_between(TJ225, '京兆尹黎幹奏秋霖損稼', '所損凡三萬餘頃。」',
                       '通鉴大曆十二年黎幹奏秋霖損稼韩滉驳不实(史部的雨是公文报灾;窗口断言)')
TJ_QL2 = slice_between(TJ225, '先是，秋霖，河中府池鹽多敗', '仍有瑞鹽生。',
                       '通鉴大曆十二年韩滉奏瑞盐(史部的雨是阿附造假;窗口断言)')
TJ_JS = slice_between(TJ230, '軍中有言及家者', '立斬之。',
                      '通鉴兴元元年李晟家书斩封案(史部唯一家书是斩的;窗口断言)')
TJ_XL = slice_between(TJ193, '東至於海，南及五嶺，皆外戶不閉，行旅不繼糧，取給於道路焉。',
                      '東至於海，南及五嶺，皆外戶不閉，行旅不繼糧，取給於道路焉。',
                      '通鉴贞观四年行旅不继粮(史部唯一行旅是贞观之治;窗口断言)')
TJ_YA = slice_between(TJ248, '桂管觀察使鄭亞坐前不能直吳湘冤', '亞貶循州刺史，',
                      '通鉴大中二年郑亚贬循州(诗的老板史部只有官没有雨;窗口断言)')
JTS_M1 = slice_between(JTS, '俄而茂元卒，来游京师', '久之不调。',
                       '旧传李商隐段(茂元卒后京师久之不调——诗的未有期对上史传官历;PERSON 首引)')
JTS_M2 = slice_between(JTS, '会给事中郑亚廉察桂州', '检校水部员外郎。',
                       '旧传李商隐段(郑亚廉察桂州带商隐入幕——老板之实;PERSON 首引)')

# ---------- 传区间归属复验（段界 ==弟 羲叟==） ----------
_ja = JTS.find('=李商隱=')
_jm = re.search(r'\n==[^=\n]{1,12}==', JTS[_ja + 8:])
_seg_j = JTS[_ja:_ja + 8 + _jm.start()]
for _needle in (JTS_M1, JTS_M2):
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

_window(TJ225, TJ_QL1, '大曆十二年')
_window(TJ225, TJ_QL2, '大曆十二年')
_window(TJ230, TJ_JS, '興元元年')
_window(TJ193, TJ_XL, '貞觀四年')
_window(TJ248, TJ_YA, '大中二年')

# ---------- 负证机器复查 ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {p.name: p.read_text(encoding='utf-8') for p in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：诗面语全零；秋霖恰二全在 tj-225；家書恰一在 tj-230；行旅恰一在 tj-193；郑亚恰三；在册档
for _w in ('夜雨', '歸期', '秋池', '西窗', '剪燭', '巴山', '寄北', '寄内'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗面不进史部的判决失效，须重读')
_qld = {n: t.count('秋霖') for n, t in _tjf.items() if '秋霖' in t}
if sum(_qld.values()) != 2 or _qld != {'tj-225.txt': 2}:
    raise SystemExit(f'通鉴「秋霖」不再恰二全在 tj-225（实 {_qld}）——两滴雨都是政务判决须重估')
if _alltj.count('家書') != 1 or _tjf['tj-230.txt'].count('家書') != 1:
    raise SystemExit('通鉴「家書」不再恰一（tj-230 李晟案）——斩封家书判决须重估')
if _alltj.count('行旅') != 1 or _tjf['tj-193.txt'].count('行旅') != 1:
    raise SystemExit('通鉴「行旅」不再恰一（tj-193 贞观四年）——唯一行旅是贞观之治判决须重估')
if _alltj.count('天子何在') != 1:
    raise SystemExit('通鉴「天子何在」不再恰一——李晟语在册须重估')
if _alltj.count('公家無恙') != 1:
    raise SystemExit('通鉴「公家無恙」不再恰一——朱泚遗书语在册须重估')
_yd = {n: t.count('鄭亞') for n, t in _tjf.items() if '鄭亞' in t}
if sum(_yd.values()) != 3 or _yd.get('tj-248.txt') != 2:
    raise SystemExit(f'通鉴「鄭亞」不再恰三（248 卷恰二）——老板有官无雨判决须重估')
for _w, _n in (('漲', 8), ('霖雨', 9), ('久雨', 10)):
    if _alltj.count(_w) != _n:
        raise SystemExit(f'通鉴「{_w}」不再恰{_n}——雨字侧闭域档扫须重估')
# ② 全唐诗：锚全库唯一；字面恰二全在 539 壳内；539 全卷零正文
if _allq.count('==[[夜雨寄北]]==') != 1:
    raise SystemExit('《全唐詩》「==[[夜雨寄北]]==」锚不再全库唯一——壳标本判决失效')
if _allq.count('夜雨寄北') != 2 or V539.count('夜雨寄北') != 2:
    raise SystemExit('全唐詩「夜雨寄北」字面不再恰二（539 壳内两处）——无同名判决须重估')
if V539.count(V539_SHELL) != 1 or V539.count('{{:夜雨寄北}}') != 1:
    raise SystemExit('卷539 空壳转引结构变了（卷页无正文第三形态断言失效）')
for _w in ('歸期', '秋池', '西窗', '剪', '巴山'):
    if V539.count(_w) != 0:
        raise SystemExit(f'卷539「{_w}」不再全零——**卷页无正文一字**机器断言失效，第三形态须重估')
if V539.count('夜雨') != 3 or V539.count('燭') != 2:
    raise SystemExit('卷539「夜雨/燭」他诗混片计数变了（3=壳二+异文标记一/燭 2）——闭域档扫须重估')
# ③ ws：小写评级独份；大写全零；三件套且无大写评级全库独页；from/notes/分类结构；poem 存原样
if WS.count('{{textquality|75%}}') != 1 or WS.count('{{Textquality') != 0:
    raise SystemExit('ws 小写 {{textquality|75%}} 独份×大写全零形态变了（评级书写形态第三态断言失效）')
if WS.count('{{另|當|時}}') != 1 or WS.count('<ref>') != 1 or WS.count('{{reflist}}') != 1:
    raise SystemExit('ws 异文三件套结构变了（{{另}}+<ref>+{{reflist}} 照登硬卡失效）')
if WS.count('「何當」：《墨莊漫録》及《浄徳集》均作「何時」') != 1:
    raise SystemExit('ws 异文注全文不再恰一——只登记不裁决的出处链须重估')
_wsf = {p.name: p.read_text(encoding='utf-8')
        for p in sorted(pathlib.Path('/tmp/src-dl/ws-poems').glob('*.txt'))}
_trio = {n for n, t in _wsf.items() if '{{reflist}}' in t and '{{Textquality' not in t}
if _trio != {'夜雨寄北.txt'}:
    raise SystemExit(f'「有 {{reflist}} 且无大写评级」不再本页独份（实 {sorted(_trio)}）——三件套独页判决须重估')
if WS.count('君問歸期未有期') != 2 or WS.count('卻話巴山夜雨時') != 2:
    raise SystemExit('ws 页 Vtext/poem 双转录结构变了（首末句页内应各恰 2）')
if '君問歸期未有期，' in WS or '卻話巴山夜雨時。' in WS:
    raise SystemExit('ws poem 块出现句读式转录——「存原样」与 V018 句读式引文并存断言失效')
if WS.count(WS_FROM3) != 1 or WS.count(WS_NOTE3) != 1 or WS.count(WS_CAT4) != 1:
    raise SystemExit('ws from 三行/notes 空壳/分类四行连片结构变了')
if WS.count('[[Category:詠懷詩]]') != 1:
    raise SystemExit('ws 分类「詠懷詩」类目计数变了（类目首见照登断言失效）')
# ④ 旧传李商隐段负证（段内雨夜窗燭池全零——诗题有雨，传段无一雨字）
for _w in ('雨', '夜', '窗', '燭', '池'):
    if _seg_j.count(_w) != 0:
        raise SystemExit(f'「{_w}」落在旧传李商隐段——段级零雨字判决失效，须重读原文')

POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')

def _domain(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V070')
                   for _ln in f.read_text(encoding='utf-8').splitlines()
                   if 'evidence_excerpt' in _ln and needle in _ln})

def _domain_src(needle):
    return sorted({f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql'))
                   if not f.name.startswith('V070')
                   and needle in f.read_text(encoding='utf-8')})

for _premise, _needle, _want in (
        ('本诗首句(V018 句读式一引)', '君問歸期未有期', ['V018']),
        ('本诗末句(V018 简体却字)', '却話巴山夜雨時', ['V018']),
        ('V018 句读式全引不重开', '君問歸期未有期，……却話巴山夜雨時。', ['V018']),
        ('ws 诗页源在先', 'source-ws-t300-013', ['V018']),
        ('卷页源四次在册(本迁移第五次复用)', 'source-quantangshi-539',
         ['V018', 'V067', 'V068', 'V069']),
        ('V069 底本回指链接在册', '↑ [[全唐詩/卷539#寄令狐郎中', ['V069']),
        ('V016 岭表句在册', '商隐随亚在岭表累载', ['V016']),
        ('V011 家书抵万金在册', '家書抵萬金', ['V011', 'V017'])):
    _prev = _domain_src(_needle) if _needle.startswith('source-') else _domain(_needle)
    if _prev != _want:
        raise SystemExit(f'前提「{_premise}」既往引文域 {_prev} ≠ {_want}——须重设计')
for _first, _needle in (('壳转引', '{{:夜雨寄北}}'), ('小写评级', '{{textquality'),
                        ('底本链', '李義山詩集 (四部叢刊本)/卷第六'), ('异文书', '墨莊漫録'),
                        ('咏怀类目', '詠懷'), ('秋霖一', '京兆尹黎幹奏秋霖損稼'),
                        ('秋霖二', '先是，秋霖'), ('李晟家书', '軍中有言及家者'),
                        ('贞观行旅', '東至於海，南及五嶺'), ('郑亚贬循州', '亞貶循州刺史'),
                        ('茂元卒京师', '俄而茂元卒'), ('水部员外郎', '检校水部员外郎'),
                        ('诗原样块', '君問歸期未有期\n巴山夜雨漲秋池')):
    if _domain(_needle):
        raise SystemExit(f'首引前提破了：「{_needle}」（{_first}）既往有引（{_domain(_needle)}）——须重设计')

BG = {
    'bg-013-scene': (
        '四句是一封回信：你问我归期，我没有归期（「君問歸期未有期」）；'
        '巴山连夜雨，涨满秋池（「巴山夜雨漲秋池」）；何时能共剪西窗之烛'
        '（「何當共剪西窗燭」）——再细说今夜巴山这场雨（「卻話巴山夜雨時」）。'
        '**寄给谁不裁决**——「寄北」「寄内」两种读法旧说都有，本迁移引文一字不能裁决'
        '（通鉴「寄北/寄内」二字全零，机器断言）；系年同样零铸造。'
        'ws 诗页：**小写 {{textquality|75%}} 评级形态全库首见**（此前 ws 库只有大写'
        '{{Textquality|75%}}/100% 或无评级三态——本页大写全零，机器断言；'
        '评级书写形态的分岔只照登不判）；**异文三件套 {{另|當|時}}+<ref>注+{{reflist}}'
        '且无大写评级——全 ws 库仅此一页**（机器断言）；异文只登记不裁决：'
        '「何當」，《墨莊漫録》及《浄徳集》均作「何時」；'
        '**notes 行空壳**（| notes 空值+{{唐詩三百首}}标记在 header 外——'
        'V069「↑底本回指链接」的反面：这页 notes 是空的，绑定方向反由卷页 {{:}} 转引承担）。'
        '**此诗正文系第二引（上限用满第十八例）**：V018 已引句读式'
        '（「君問歸期未有期，……却話巴山夜雨時。」——却，简体），本迁移改引 ws 页 poem 块'
        '**存原样**：四句裸行+第三行行尾 <ref> 异文注（各从其录；生成时断言 V018 句读式'
        '引文不重开）；此后此诗正文对后来迁移关闭。'),
    'bg-013-city': (
        '卷539 侧是本迁移最特殊的一块：本篇在《全唐詩》卷539 的见证面是**空壳转引**——'
        '「==[[夜雨寄北]]==」下一行「{{:夜雨寄北}}」，**全卷无正文一字**'
        '（机器断言：539 全卷 歸期/秋池/西窗/剪/巴山 全零；「夜雨」三处=壳内两处+他诗'
        '异文标记一处，「燭」二处皆他诗——闭域档扫）。这是卷页/诗页绑定形态的**第三种**：'
        'V066–V068 卷页载正文（底本=卷页）、V069 诗页底本+↑回指链接（底本=诗页）、'
        '本篇**底本=选本《李義山詩集》（ws version_code ws-xbook-fold、from 行自述），'
        '卷页只挂壳**——**双向绑定至此集齐**：V069 是诗页 notes「↑」向上回指卷页，'
        '本篇是卷页「{{:}}」向下转引诗页，两个方向各见过一次（机器断言锚「==[[夜雨寄北]]==」'
        '全唐诗恰一、「夜雨寄北」字面恰二全在壳内——无同名诗，两端裸名，消歧链裸侧第五见，'
        'V061/V062/V063/V069 判例）。（本层零 relation。）'
        '**本迁移零新建 source（连续第二首）**：source-ws-t300-013 是 V018 所立诗页源'
        '（edition 字段即底本「李義山詩集 (四部叢刊本)/卷第六」），'
        'source-quantangshi-539 第五次复用（V018/V067/V068/V069 在册）——'
        '引卷页这一次，引到的正是一个空壳：**壳本身就是证据**，它证明编诗者视此诗'
        '归属已定、不必重抄。ws 侧 from 三行版本目录：底本四部叢刊本《李義山詩集》卷六'
        '+萬首唐人絶句四庫全書本+**第三书墨莊漫録四庫全書本卷05——恰是本页异文注的出处**'
        '（from 链不止底本目录，还挂着异文旁证的书单）；分类四行连片简繁混排第五见，'
        '「詠懷詩」类目首见（整理者归类：非史料声明、不升格，V048 判例）。'),
    'bg-013-world': (
        '**诗里一夜的雨，通鉴全库没有；史部唯一的家书是斩封的**'
        '（同字两界第十五形态·家书形态首见）：'
        '通鉴「**夜雨/歸期/秋池/西窗/剪燭/巴山/寄北/寄内**」全零（机器断言）——'
        '诗题连「寄北」二字史部都不识。可通鉴不是没有雨：'
        '① 「**秋霖**」恰二，全在大曆十二年（丁巳，七七七）：「**京兆尹黎幹奏秋霖損稼，'
        '韓滉奏幹不實；上命御史按視，丁未，還奏，『所損凡三萬餘頃。』**」'
        '——报灾的挨了驳；又「**先是，秋霖，河中府池鹽多敗。戶部侍郎判度支韓滉恐鹽戶減稅，'
        '丁亥，奏雨雖多，不害鹽，仍有瑞鹽生。**」——报平安的造了假。'
        '**史部的雨是公文：一场雨两条奏状；诗里同一场雨只写给一个人**；'
        '② 「**家書**」通鉴恰一，在興元元年（甲子，七八四）李晟困长安：'
        '「**軍中有言及家者，晟泣曰：『天子何在，敢言家乎！』」**朱泚使以家書遺晟'
        '曰「**公家無恙**」，晟怒曰「爾敢為賊為間！」**立斬之**」——'
        '**史部的家书是斩封的；诗的家书是想象共剪的**。'
        '「君問歸期未有期」对「天子何在，敢言家乎」：一个是回不了的归期，'
        '一个是不许问的家（对照判决，非史实因果——通鉴不记这首诗本身）；'
        '③ 「**行旅**」恰一，在貞觀四年（庚寅，六三〇）：「**東至於海，南及五嶺，'
        '皆外戶不閉，行旅不繼糧，取給於道路焉**」——**史部唯一的行旅是贞观之治的路不拾遗；'
        '诗的行旅是巴山一夜，回不去**；'
        '④ 「**鄭亞**」恰三（247/248 卷），大中二年（戊辰，八四八）'
        '「**桂管觀察使鄭亞坐前不能直吳湘冤……亞貶循州刺史**」——'
        '**诗的老板在通鉴只有贬官一行：史部有他的官，没有他的雨**。'
        '「漲」恰八他事、「霖雨」恰九/「久雨」恰十在册零入引（闭域档扫）。'
        '本层零铸造零 relation。'),
    'bg-013-person': (
        '旧传李商隐段（**简化字录入**，V016 locator 同款标注，引文照登简体原样）'
        '首引二段（皆零域）：「**俄而茂元卒，来游京师，久之不调。**」'
        '「**会给事中郑亚廉察桂州……检校水部员外郎。**」\n'
        '史部没有这场雨（段级零证：段内**雨/夜/窗/燭/池五字全零**，机器断言——'
        '**诗题有雨，传段无一雨字**），却把诗的「未有期」四个字写成了官历：'
        '王茂元死了，李商隐到京师游了多年，「久之不调」——**回不了的归期，'
        '在史部那一栏叫作候补**；下一段给出老板之实：给事中郑亚出镇桂州，'
        '带他入幕带检校衔——而这位郑亚，通鉴大中二年「亞貶循州刺史」（WORLD 层）：'
        '老板和幕客各自飘零，一个贬循州，一个困巴山（读法声明，非史实因果）。\n'
        '本诗 ws 页 **notes 行空壳**（无注可登——V069 有↑回指注、V055/V057 等有底注，'
        '本篇空：注的有无本身也是形态）；certainty 不覆盖任何系年，'
        '诗 time.span/event.name/written_during 仍零铸造（audit 硬卡）；'
        'V016「商隐随亚在岭表累载/字义山/开成二年/三十六体」等在册句零重开（域断言）。'),
}
CLAIMS = {
    'claim-bg-013-scene': (
        'FACT', 'LIKELY',
        '四句七绝本文**第二引上限用满第十八例**：V018 句读式一引在先'
        '（「君問歸期未有期，……却話巴山夜雨時。」），本迁移二引 ws 页 poem 块'
        '**存原样**（四句裸行+第三行行尾 <ref> 异文注，各从其录；生成时断言 V018 '
        '句读式引文不重开），此后正文对后来迁移关闭；异文只登记不裁决：「何當」，'
        '《墨莊漫録》及《浄徳集》均作「何時」；**小写 {{textquality|75%}} 评级形态'
        '全库首见**（本页大写 Textquality 全零，机器断言）；**异文三件套'
        '{{另|當|時}}+<ref>+{{reflist}} 且无大写评级——全 ws 库仅此一页**（机器断言）；'
        'notes 行空壳（三百首标记在 header 外）；「寄北/寄内」两种读法并记不裁决；'
        '系年零铸造。'),
    'claim-bg-013-city': (
        'FACT', 'LIKELY',
        '本篇在《全唐詩》卷539 的见证面系**空壳转引**：「==[[夜雨寄北]]==」+'
        '「{{:夜雨寄北}}」，**全卷无正文一字**（机器断言：539 歸期/秋池/西窗/剪/巴山'
        '全零；夜雨3=壳二+他诗异文标记一/燭2 皆他诗闭域）——卷页/诗页绑定**第三形态**'
        '（V066–V068 卷页载正文、V069 诗页底本+↑回指、本篇底本=选本+卷页挂壳）；'
        '**双向绑定至此集齐**（V069 ↑向上 vs 本篇 {{:}} 向下）；锚全唐诗唯一+字面恰二'
        '全在壳内——无同名诗两端裸名，消歧链裸侧第五见（V061/V062/V063/V069 判例）；'
        '**零新建 source 连续第二首**（source-ws-t300-013 系 V018 所立、edition 即底本'
        '李義山詩集四部叢刊本；source-quantangshi-539 第五次复用）；ws from 三行版本目录'
        '入引——**第三书墨莊漫録四庫全書本恰是异文注出处**（from 链挂异文旁证书单）；'
        '分类四行简繁混排第五见+「詠懷詩」类目首见照登（非史料声明不升格，V048 判例）。'),
    'claim-bg-013-world': (
        'FACT', 'LIKELY',
        '通鉴「夜雨/歸期/秋池/西窗/剪燭/巴山/寄北/寄内」全零（机器断言）而雨在他字：'
        '「秋霖」恰二全在大曆十二年丁巳七七七（黎幹奏秋霖損稼韩滉驳不实「所損凡三萬餘頃」+'
        '韩滉奏「雨雖多不害鹽仍有瑞鹽生」——**史部的雨是公文，一场雨两条奏状**）；'
        '「家書」恰一在興元元年甲子七八四李晟困长安（「軍中有言及家者…天子何在敢言家乎」+'
        '朱泚家書「公家無恙」晟立斬之——**史部的家书是斩封的，诗的家书是想象共剪的**）；'
        '「行旅」恰一在貞觀四年庚寅六三〇（「外戶不閉行旅不繼糧取給於道路」——'
        '**史部唯一行旅是贞观之治，诗的行旅是巴山一夜回不去**）；「鄭亞」恰三，大中二年'
        '戊辰八四八「桂管觀察使鄭亞坐前不能直吳湘冤…亞貶循州刺史」——**诗的老板史部'
        '只有官没有雨**（同字两界第十五形态·家书形态首见，audit 硬卡）；'
        '漲恰八/霖雨恰九/久雨恰十在册零入引；certainty 不覆盖任何系年，'
        'time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-013-person': (
        'FACT', 'LIKELY',
        '旧传李商隐段（简化字录入照登原样）首引二段皆生成时全库查重域恰零='
        '「俄而茂元卒，来游京师，久之不调。」+「会给事中郑亚廉察桂州…检校水部员外郎。」'
        '（传区间归属机器断言）；**段级零雨字**：段内雨/夜/窗/燭/池五字全零（机器断言）'
        '——诗题有雨，传段无一雨字；「回不了的归期在史部那一栏叫作候补」「老板贬循州'
        '幕客困巴山」系读法声明非史实因果；本诗 notes 行空壳（无注可登）；'
        'V016 在册句（字义山/开成二年/岭表/三十六体/商隐随亚在岭表累载）零重开（域断言）；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-013-scene', 'source-ws-t300-013',
     '页面 夜雨寄北（《唐詩三百首》第 13 首选本页，页题裸名；title+author+小写评级+Vtext 折叠行'
     '+poem 块以「……」相连——**小写 {{textquality|75%}} 全库首见（大写全零）**；'
     '页内异文双写形态：Vtext 行用 {{另|當|時}} 折叠、poem 行尾用 <ref> 注'
     '（「何當」：《墨莊漫録》及《浄徳集》均作「何時」——只登记不裁决）；poem 块**存原样**：'
     '正文第二引上限用满第十八例（V018 句读式一引在先，本迁移引原样面，各从其录，'
     '生成时断言 V018 句读式引文不重开）；{{reflist}} 在页尾）',
     join(WS_TITLE, WS_AUTHOR, WS_TQ, WS_LING, WS_POEM)),
    ('claim-bg-013-city', 'source-quantangshi-539',
     '卷五百三十九·李商隱《夜雨寄北》**空壳转引块**（「==[[夜雨寄北]]==」+「{{:夜雨寄北}}」'
     '——**卷页无正文一字**：539 全卷歸期/秋池/西窗/剪/巴山 全零机器断言；夜雨3/燭2 他片闭域；'
     '绑定第三形态：底本=选本《李義山詩集》、卷页只挂壳，与 V069 ↑回指合成双向绑定；'
     '锚全唐诗唯一+字面恰二全在壳内——两端裸名消歧链裸侧第五见；'
     '源行系 V018 已立、本迁移第五次复用零新建）',
     V539_SHELL),
    ('claim-bg-013-city', 'source-ws-t300-013',
     '页面 夜雨寄北（from 三行版本目录整段入引（底本四部叢刊本《李義山詩集》卷六+萬首唐人絶句'
     '四庫全書本+**第三书墨莊漫録四庫全書本卷05恰是异文注出处**——版本目录链非史料断言，'
     'V053 判例只引不重开他书 from 链）+notes 空壳块（| notes 空值+三百首标记在 header 外）'
     '+分类四行连片（简繁混排第五见+「詠懷詩」类目首见照登；分类行系整理者分类动作：'
     '非史料声明、不升格，V048 判例）；本迁移零新建源连续第二首）',
     join(WS_FROM3, WS_NOTE3, WS_CAT4)),
    ('claim-bg-013-world', 'source-zizhi-tongjian-events',
     '卷二百二十五·大曆十二年（丁巳，七七七）秋霖双案（黎幹奏秋霖損稼被驳「所損凡三萬餘頃」'
     '+韩滉奏「仍有瑞鹽生」——史部的雨是公文）……卷二百三十·興元元年（甲子，七八四）'
     '李晟家书斩封案（「天子何在，敢言家乎」+「公家無恙」立斬之——史部唯一家书是斩的）……'
     '卷一百九十三·貞觀四年（庚寅，六三〇）「外戶不閉行旅不繼糧」段（唯一行旅=贞观之治）……'
     '卷二百四十八·大中二年（戊辰，八四八）鄭亞貶循州刺史段（老板有官无雨）；'
     '通鉴诗面夜雨/寄北等八字全零，秋霖恰二/家書恰一/行旅恰一/鄭亞恰三（六段逐字入引为判决证据）',
     join(TJ_QL1, TJ_QL2, TJ_JS, TJ_XL, TJ_YA)),
    ('claim-bg-013-person', 'source-jiutangshu-wenyuan',
     '舊唐書卷一九〇下·李商隱（**简化字录入**照登原样，V016 locator 同款标注）'
     '（「俄而茂元卒，来游京师，久之不调」段（诗的未有期对上史传官历）+「会给事中郑亚廉察'
     '桂州…检校水部员外郎」段（老板之实，对 WORLD 层亚贬循州）——皆全库查重恰零域首引；'
     '传区间归属机器断言；段内雨/夜/窗/燭/池五字全零（段级零雨字——诗题有雨传段无雨字）；'
     '「候补」「各自飘零」系读法声明；V016 在册句零重开）',
     join(JTS_M1, JTS_M2)),
]
BG_LINES = {'bg-013-scene': (1,), 'bg-013-city': (2,),
            'bg-013-world': (3,), 'bg-013-person': (4,)}
BG_AUDIENCE = {'bg-013-scene': 'PRIMARY', 'bg-013-city': 'JUNIOR',
               'bg-013-world': 'SENIOR', 'bg-013-person': 'JUNIOR'}
BG_TITLES = {'bg-013-scene': '眼前：回不了期的一夜雨',
             'bg-013-city': '这座城：只挂壳的卷页',
             'bg-013-world': '这个天下：斩封的家书',
             'bg-013-person': '这个人：久之不调'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 51 首·四句七绝 1/1/1/1 第七次）；史实句均有逐字引证；'
                 '系年第四十五次判决（题证系列第卅三状·夜雨寄北与天子何在）'
                 '「诗里一夜的雨通鉴全库没有；史部唯一的家书是斩封的」——'
                 '同字两界第十五形态·家书形态首见：通鉴夜雨/歸期/秋池/西窗/剪燭/巴山/'
                 '寄北/寄内全零（机器断言）；「秋霖」恰二全在大曆十二年丁巳七七七'
                 '（黎幹奏秋霖損稼被驳「所損凡三萬餘頃」+韩滉奏「仍有瑞鹽生」造假——'
                 '**史部的雨是公文，一场雨两条奏状；诗里同一场雨只写给一个人**）；'
                 '「家書」恰一在興元元年甲子七八四李晟困长安（「天子何在，敢言家乎」+'
                 '朱泚遗家書「公家無恙」晟立斬之——**史部的家书是斩封的，诗的家书是'
                 '想象共剪的**）；「行旅」恰一在貞觀四年庚寅六三〇（外戶不閉行旅不繼糧——'
                 '**史部唯一行旅是贞观之治，诗的行旅是巴山一夜回不去**）；「鄭亞」恰三，'
                 '大中二年戊辰八四八亞貶循州刺史——**诗的老板史部只有官没有雨**；'
                 '涨8/霖雨9/久雨10 在册闭域；**卷539 见证面系空壳转引「{{:夜雨寄北}}」——'
                 '全卷无正文一字**（539 歸期/秋池/西窗/剪/巴山 全零机器断言）：绑定第三形态'
                 '（底本=选本《李義山詩集》四部叢刊本、卷页挂壳），与 V069 ↑回指合成'
                 '**双向绑定集齐**（↑向上/{{:}}向下各见一次）；锚全唐诗唯一+字面恰二全在'
                 '壳内（两端裸名消歧链裸侧第五见 V061/V062/V063/V069）；**零新建 source'
                 '连续第二首**（source-ws-t300-013 系 V018 所立、source-quantangshi-539'
                 '第五次复用——壳本身就是证据）；正文第二引上限用满第十八例（V018 句读式'
                 '在先+本迁移 ws 原样面含<ref>异文注，各从其录，V018 句读式引文不重开断言）；'
                 '异文只登记不裁决（何當/何時，《墨莊漫録》《浄徳集》；from 三行版本目录'
                 '入引——第三书墨莊漫録四庫全書本恰是异文注出处）；**小写 {{textquality|75%}}'
                 '全库首见（大写全零）+异文三件套 {{另}}+<ref>+{{reflist}} 且无大写评级'
                 '全 ws 库仅此一页**（机器断言）+notes 行空壳（无注可登，V069 ↑回指的反面）'
                 '+分类四行简繁混排第五见+「詠懷詩」类目首见照登（非史料声明不升格 V048）；'
                 '「寄北/寄内」两读并记不裁决；PERSON 旧传简化段首引二段（俄而茂元卒来游'
                 '京师久之不调+郑亚廉察桂州检校水部员外郎——**回不了的归期在史部叫作候补**；'
                 '**段内雨/夜/窗/燭/池五字全零：诗题有雨传段无一雨字**——段级零证机器断言）；'
                 'V016 在册句零重开（域断言）；KNOWN 零如实记录（第廿六例，audit 反向断言）；'
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
    A("""-- V070：李商隱《夜雨寄北》(work-t300-013) 四层背景（阶段 D 第 51 首·夜雨家书）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V048、V053、V057、V058、V059、V060、
--       V061、V062、V063、V064、V065、V066、V067、V068、V069 已执行
--       （work-t300-013 与其 text-work-t300-013-ws（version_code=ws-xbook-fold，四行带句读、
--       第四行简体「却」）与其源 source-ws-t300-013（edition 字段即底本
--       「李義山詩集 (四部叢刊本)/卷第六」）都是 V018 的行；
--       source-quantangshi-539 是 V018 已立的卷539 卷页源（V018/V067/V068/V069 已引，
--       本迁移第五次复用——**这次引到的是空壳转引 {{:夜雨寄北}}，全卷无正文一字**）；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源；
--       source-jiutangshu-wenyuan 是 V016 已立的旧唐书文苑传源（李商隐传在此，简化字录入）；
--       判例在册句（义山/开成二年/岭表/三十六体 V016、家書抵萬金 V011/V017、
--       四部叢刊/四庫全書 from 链与春晓诸句 V053、乘興南遊/孫處約諫書 V067、
--       穆王何事不重來/雲能合長生藥 V068、嵩雲秦樹久離居/茂陵秋雨病相如/↑底本回指 V069）
--       只对照不重开。
--       **本迁移零新建 source（连续第二首）——
--       audit 断言本文件零 poetry_source INSERT、回滚零 source 删除。**
--
-- 数据源（可复现）：emit_v070.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/夜雨寄北.txt（小写 {{textquality|75%}} 全库首见+异文三件套且无大写评级全库独页+
--   from 三行+notes 空壳+poem 存原样含 <ref> 异文注+双转录首末句各恰 2+分类四行詠懷詩首见）、
--   全唐詩卷539（锚 ==[[夜雨寄北]]== 全唐诗唯一+字面恰二全在壳内+
--   **539 全卷歸期/秋池/西窗/剪/巴山 全零（卷页无正文一字）**+夜雨3/燭2 他片闭域）、
--   舊唐書卷190下（李商隐段首引二段+**段内雨/夜/窗/燭/池五字全零**+段边界断言）、
--   通鑑卷193/225/230/248（六段逐字入引+五处年标题窗口断言：大曆十二年七七七×2/
--   興元元年七八四/貞觀四年六三〇/大中二年八四八）+
--   通鑑 75 卷负证计数扫描（夜雨/歸期/秋池/西窗/剪燭/巴山/寄北/寄内 全零+
--   秋霖恰二全在 225/家書恰一在 230/行旅恰一在 193/鄭亞恰三(248 卷二)/天子何在恰一/
--   公家無恙恰一/漲8/霖雨9/久雨10 闭域）+
--   既有迁移引文域逐句查重——传区间归属、二引/零重开/首引零域前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 background_line（四句七绝 **1/1/1/1 第七次**（V056/V061/V066/V067/V068/V069 之后）：
--   scene→1 city→2 world→3 person→4，绑 text-work-t300-013-ws 的 4 行）+ 不碰 poetry_text_line。
-- 不做：**不新建任何 source（连续第二首）**；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「诗里一夜的雨通鉴全库没有；史部唯一的家书是斩封的」）：
--   * 「夜雨家书两界」系通鉴六段逐字入引支撑的对照判决，非史实因果——通鉴不记这首诗本身；
--   * 「寄给谁」不裁决——「寄北」「寄内」旧说都有，本迁移引文一字不能裁决；系年零铸造；
--   * 「史部的雨是公文」「候补」「各自飘零」标明读法声明；异文何當/何時只登记不裁决；
--   * 通鉴秋霖恰二都是奏报政务（报灾被驳/报盐造假）、家書恰一是李晟军中案（兴元元年）——
--     与诗题之雨/寄只共享字面，绝不当同一事件；
--   * 正文第二引上限用满：V018 句读式一引在先，本迁移引 ws 页 poem 块存原样面——
--     各从其录，V018 句读式引文不重开（生成时硬断言），此后此诗正文关闭；
--   * 「空壳第三形态」「双向绑定集齐」「小写评级首见」「三件套独页」「詠懷詩类目」均照登不判；
--   * 通鉴漲8/霖雨9/久雨10 在册零入引（audit 硬卡零混入）；
--   * KNOWN 零如实记录（第廿六例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * V011/V016/V053/V066–V069 已引诸句只对照不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 69，不含 70
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-013-%';             -- 空
--   SELECT id FROM poetry_source WHERE id IN ('source-ws-t300-013','source-quantangshi-539');
--    -- 两行（均 V018 所立，本迁移不新建）
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-013-ws';  -- 恰 4
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-013-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-013';                                  -- 4（1/1/1/1）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-013-%';  -- 四行全 LIKELY
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-013';   -- 恰 1（V018 所立）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-013'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-013';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-013-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V070_rollback.sql（按 id 全枚举删除；**零 source 删除**——
--   source-ws-t300-013 与 source-quantangshi-539 皆 V018 所立，绝不删）
START TRANSACTION;""")

    A('\n-- ---------- 0. 零新建 source（连续第二首；两源皆 V018 所立复用） ----------')

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
    brows = [{'id': k, 'work_id': 'work-t300-013',
              'layer': {'bg-013-scene': 'SCENE', 'bg-013-city': 'CITY',
                        'bg-013-world': 'WORLD', 'bg-013-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（四句七绝 1/1/1/1 第七次） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-013-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 70, 'Li Shang-yin''s Night Rain, Sent North (work-t300-013) background layers (stage-D poem 51, four-line jueju 1/1/1/1 seventh time): dating verdict forty-five, thirty-third shape of the title-evidence series -- a single night of rain in the poem, nowhere in the whole Zizhi Tongjian; the histories'' one and only family letter is a beheaded one. Same-character-two-realms, fifteenth shape: the home-letter shape, first seen. The Tongjian scores zero on every word of the poem''s night -- yeyu (night rain), guiqi (date of return), qiuchi (autumn pool), xichuang (west window), cutting the candle, Bashan, "sent north", "sent to my wife" (machine-asserted) -- the histories do not even recognise the two words of the title. Yet the histories do have rain: "autumn rain (qiulin)" appears exactly twice, both in Dali 12, dingsi, 777: "Jingzhao Yin Li Gan memorialised that autumn rain damaged the crops; Han Huang memorialised that Gan''s report was not truthful... the damage came to over thirty thousand qing" -- the reporter of disaster was impeached; and "before this, autumn rain had spoiled the pond-salt at Hezhong; Huang, fearing a cut in the salt households'' tax, memorialised that though the rain was much it did not harm the salt, and that auspicious salt had even grown" -- the reporter of good weather faked it. The histories'' rain is an official dispatch: one rain, two memorials; the poem''s same rain is written to exactly one person. "Family letter (jiashu)" appears exactly once in the Tongjian, in Xingyuan 1, jiazi, 784, with Li Cheng penned inside Chang''an: "when any man in the army spoke of home, Cheng wept and said: where is the Son of Heaven, that you dare speak of home!" Zhu Ci had a family letter sent him saying "your household is unharmed"; Cheng flew into a rage and had the bearer beheaded at once" -- the histories'' home letter is a letter cut open and its bearer killed; the poem''s home letter is an imagined shared trimming of the west-window candle. "Travelers (xinglu)" appears exactly once, in Zhenguan 4, gengyin, 630: "from the sea in the east to the five ridges in the south, outer gates stood unbarred and travelers carried no grain, sourcing it along the roads" -- the histories'' one journey is the peace of Zhenguan; the poem''s journey is one night in Bashan, with no way back. Zheng Ya appears exactly three times, and in Dazhong 2, wuchen, 848: "Zheng Ya,观察者 of Guiguan, was demoted to Prefect of Xunzhou for failing earlier to redress the Wu Xiang injustice" -- the poem''s own patron exists in the histories only as one demotion line: the histories have his office, not his rain. The juan-539 witness face of this poem in the Quan Tangshi is a transclusion stub: heading plus {{:夜雨寄北}} and nothing else -- **not one character of the poem text anywhere in juan 539** (machine-asserted: guiqi/qiuchi/xichuang/cut/Bashan all score zero across the juan) -- the third binding form: base text = the anthology Li Yishan shiji (Sibu Congkan edition), the scroll page merely hangs the shell; with V069''s up-arrow back-reference the two binding directions now come complete (poem page pointing up at the scroll page, scroll page transcluding down from the poem page, one sighting each). ZERO new sources, second poem running (audit asserts zero poetry_source INSERT and zero source deletion); the shell itself is the evidence: the compilers treated the attribution as settled. Body use-ceiling reached, eighteenth instance: V018 quoted the punctuated text (with the simplified qi character); this migration quotes the ws page''s raw poem block, its third line carrying the apparatus <ref> registering the variant (hedaing vs. heshi, sourced to the Mozhuang manlu and the Jingde ji) -- registering only, never adjudicating (generator asserts V018''s punctuated excerpt is never re-used); the body is now closed. The ws page shows, first anywhere in the corpus, the lowercase rating form {{textquality|75%}} (this page''s uppercase Textquality count is zero, machine-asserted), and is the only page in the whole ws corpus that carries {{reflist}} with no uppercase rating (machine-asserted); its notes field is an empty shell (no annotation to log -- the mirror of V069''s back-reference arrow); its from-chain names the declared base plus, as its third book, precisely the Mozhuang manlu cited by the variant note (the chain lists not only bases but witnesses); the category quadruple''s 詠懷詩 tag, first seen, logged (editorial, not a source claim, not upgraded, V048 precedent); the title''s addressee (north? my wife?) is left undecided -- neither reading can be adjudicated from these citations. PERSON first-cites two zero-domain simplified JTS passages -- "when Mao-yuan soon after died, [Shang-yin] came to roam the capital and for a long while was not assigned" (the poem''s "no date of return" rendered, in the histories'' column, as years of waiting), and "it happened that Zhen Ya, as supervising censore, proceeded to Guizhou... [he followed him as] supernumerary Vice Director of the Bureau of Waterways" -- with the biography segment holding not a single character of rain/night/window/candle/pool (machine-asserted: the poem''s title carries rain, the biography segment not one rain-graph); "the histories'' column for the unreachable return date is called waiting-for-post" and "patron demoted to Xunzhou, clerk stranded in Bashan" are readings declared, not facts. KNOWN zero honestly recorded (twenty-sixth instance, audit reverse-asserts); closed precedent keywords (including V011''s family-letters-worth-ten-thousand-gold and V053''s from-chains) stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 70);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V070 精确回滚：只删 V070 插入的行（id 全枚举）。',
         '-- **零 source 删除**：source-ws-t300-013（V018 所立的 ws 选本页源）与',
         '-- source-quantangshi-539（V018 所立的卷539 卷页源）本迁移皆复用，绝不删；',
         '-- work-t300-013 本体、其 text_line 4 行都是 V018 的行，绝不删；',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 70;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_TQ, WS_LING, WS_POEM, WS_FROM3, WS_NOTE3, WS_CAT4, V539_SHELL,
              TJ_QL1, TJ_QL2, TJ_JS, TJ_XL, TJ_YA, JTS_M1, JTS_M2]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # SCENE：小写评级/异文注必须逐字入引 + V018 句读式引文零重开
    scene_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-013-scene')
    if '{{textquality|75%}}' not in scene_ws:
        bad.append('小写评级未逐字入 SCENE 引文（评级书写形态第三态照登硬卡）')
    if '{{另|當|時}}' not in scene_ws:
        bad.append('{{另|當|時}} 未逐字入 SCENE 引文（异文三件套照登硬卡）')
    if '《墨莊漫録》及《浄徳集》均作「何時」' not in scene_ws:
        bad.append('异文注全文未逐字入 SCENE 引文（只登记不裁决硬卡）')
    if '君問歸期未有期\n' not in scene_ws:
        bad.append('正文原样块未入 SCENE 引文（第二引第十八例硬卡）')
    if '君問歸期未有期，……却話巴山夜雨時。' in cited:
        bad.append('V018 句读式引文重开了——本迁移引原样面，句读式不重开')
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-013-city' and s == 'source-ws-t300-013')
    if '墨莊漫録 (四庫全書本)/卷05' not in city_ws:
        bad.append('from 第三书未逐字入 CITY 引文（from 链挂异文旁证书单硬卡）')
    if '[[Category:詠懷詩]]' not in city_ws:
        bad.append('「詠懷詩」类目未逐字入 CITY 引文（类目首见照登硬卡）')
    if '不升格' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-013-city' and s == 'source-ws-t300-013'):
        bad.append('CITY ws locator 须含「不升格」声明（分类行三重断言失效）')
    city_q = next(ex for c, s, _, ex in CITATIONS if s == 'source-quantangshi-539')
    if '{{:夜雨寄北}}' not in city_q:
        bad.append('空壳转引未逐字入 CITY 引文（卷页无正文第三形态照登硬卡）')
    if '君問' in city_q or '巴山' in city_q or '秋池' in city_q:
        bad.append('CITY 卷页引文混入正文语——壳内无正文一字正是本迁移的标本')
    c_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-013-city' and s == 'source-quantangshi-539')
    if '无正文' not in c_loc or '第三形态' not in c_loc:
        bad.append('CITY 卷页 locator 须含「无正文/第三形态」声明（壳即证据硬卡）')
    # WORLD：六段史文必须在引文内；诗语零混入
    w_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-013-world')
    for tok in ('京兆尹黎幹奏秋霖損稼', '所損凡三萬餘頃', '先是，秋霖，河中府池鹽多敗',
                '仍有瑞鹽生', '天子何在，敢言家乎', '公家無恙', '立斬之',
                '行旅不繼糧', '亞貶循州刺史'):
        if tok not in w_ex:
            bad.append(f'WORLD 引文缺通鉴判决证据要素「{tok}」（六段必须入引）')
    for tok in ('夜雨', '歸期', '秋池', '西窗', '剪', '巴山'):
        if tok in w_ex:
            bad.append(f'WORLD 引文混入诗语项「{tok}」（诗句不得入通鉴引文）')
    w_loc = next(loc for c, _, loc, _ in CITATIONS if c == 'claim-bg-013-world')
    if '秋霖' not in w_loc or '家書' not in w_loc:
        bad.append('WORLD locator 须点出秋霖/家書（两界柄词声明）')
    # PERSON 首引句必须在引文内 + 在册句零重开
    p_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-013-person')
    for tok in ('俄而茂元卒', '久之不调', '郑亚廉察桂州', '检校水部员外郎'):
        if tok not in p_ex:
            bad.append(f'PERSON 引文缺首引要素「{tok}」（简化字段首引照登硬卡）')
    for tok in ('绹不之省', '坎壈终身', '以所业文干之', '下笔不能自休', '为当涂者所薄',
                '恃才诡激', '置瑤池都督府', '商隐随亚在岭表累载', '令狐绹在内署',
                '尤恶其无行', '以子妻之', '嵩雲秦樹久離居', '茂陵秋雨病相如',
                '一紙書', '雙鯉迢迢', '背恩德而助叛臣', '未嘗不汗沾衣也', '終文園令',
                '穆王何事不重來', '雲能合長生藥', '何處更求長生',
                '↑ [[全唐詩/卷539#寄令狐郎中', '家書抵萬金', '感時花濺淚',
                '春眠不覺曉', '欲知昨夜風', '文苑英華', '孟浩然集 (四部叢刊本)',
                '乘興南遊不戒嚴', '孫處約諫書', '李商隐，字义山，怀州河内人。',
                '开成二年，方登进士第'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    if BG_LINES != {'bg-013-scene': (1,), 'bg-013-city': (2,),
                    'bg-013-world': (3,), 'bg-013-person': (4,)}:
        bad.append('四句 background_line 须 1/1/1/1（第七次）')
    if len(re.findall(r"text-work-t300-013-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    # **零新建 source**（连续第二首）
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
        bad.append("V070 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V070 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-013' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V070 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-013' AS subject_id" in sql:
        bad.append('V070 的 claim 主语应全部是 bg-013-*，work-t300-013 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in rb:
        bad.append('V070 不碰 poetry_text_line')
    body_all = ''.join(BG.values())
    if '家书形态首见' not in body_all:
        bad.append('BG 须含「家书形态首见」（同字两界第十五形态）声明')
    if '斩封' not in body_all:
        bad.append('BG/WORLD 须含「史部的家书是斩封的」判决')
    if '空壳' not in body_all:
        bad.append('BG/CITY 须含「空壳转引（卷页无正文一字）」声明')
    if '双向绑定' not in body_all:
        bad.append('BG/CITY 须含「双向绑定集齐（V069 ↑ vs 本篇 {{:}}）」声明')
    if '只登记不裁决' not in body_all:
        bad.append('BG/SCENE 须含「异文只登记不裁决」声明')
    if '小写' not in body_all:
        bad.append('BG/SCENE 须含「小写 {{textquality|75%}} 全库首见」声明')
    if '无一雨字' not in body_all:
        bad.append('BG/PERSON 须含「诗题有雨，传段无一雨字」段级零证声明')
    if '零新建' not in body_all:
        bad.append('BG/CITY 须含「零新建 source（连续第二首）」声明')
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
    if 'WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 70)' not in vblk:
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 16 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（旧传李商隐段二首引句，段界 ==弟 羲叟==）；'
              f'五处年标题窗口断言（大曆十二年七七七×2/興元元年七八四/貞觀四年六三〇/'
              f'大中二年八四八）；'
              f'负证机器复查五层（通鉴夜雨/歸期/秋池/西窗/剪燭/巴山/寄北/寄内全零+'
              f'秋霖恰二全在225+家書恰一在230+行旅恰一在193+鄭亞恰三(248卷二)+天子何在恰一+'
              f'公家無恙恰一+漲8/霖雨9/久雨10 闭域/全唐诗锚恰一+字面恰二全在壳内+'
              f'539 歸期秋池西窗剪巴山全零（卷页无正文一字）+夜雨3/燭2 闭域/'
              f'ws 小写评级恰一×大写全零+异文三件套且无大写评级全库独页+异文注恰一+'
              f'双转录首末句各恰二+无句读式转录+from三行/notes空壳/分类四行连片+詠懷詩恰一/'
              f'旧传段雨/夜/窗/燭/池五字全零，快照变动即中止）；'
              f'前提全库查重硬卡八件+十三首引句零域断言；小写评级/异文注/壳转引照登硬卡；'
              f'SCENE 正文原样面入引+V018 句读式引文零重开断言；CITY 无正文/第三形态硬卡；'
              f'CITY「不升格」硬卡；六段通鉴史文入引+诗语零混入断言；'
              f'PERSON 四首引要素入引硬卡+V016/V066–V069 诸句零重开硬卡；'
              f'判例只引不重开断言（含 V011 家書抵萬金/V053 from 链与春晓诸句在内）；'
              f'四句 1/1/1/1 形制断言；零 KNOWN 反向断言；'
              f'**零新建 source 断言（INSERT 恰零+回滚零 source 删除）**——连续第二首；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
