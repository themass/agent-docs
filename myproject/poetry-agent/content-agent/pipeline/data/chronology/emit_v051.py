#!/usr/bin/env python3
"""阶段 D 第 32 首：生成 V051——孟浩然《夏日南亭懷辛大》(work-t300-108, V018 已立) 四层背景。

「为什么写」走到一个只剩行第的朋友：
**诗题里的「辛大」在两传零见、在全唐詩只有四枚自己的篇题（恰八处=四锚点×2，机器断言）；
而「恨無知音賞」押的知音典——「伯牙」通鉴+全唐詩计数全零，
通鉴里的「子期」有六处，处处都是田承嗣叛将盧子期（776 年破擒斩之）**——

系年第二十六次判决（题证系列第十四状·周期季与行第友）：
「題有季有友，季是節非年、友有第無名」——
V048 周期时间不系年（重陽是「每到」）、这首的「夏日」同样是季节不是年份；
V047 人无传名（斛斯山人）、这首的朋友更彻底：**连名都不传，只传行第**——
唐人称辛大，如同称张七；两传孟区间「辛大/辛遊」计数全零（机器断言），
全唐詩的「辛大」（除「辛大夫」六处另册）恰八处=四枚篇题锚点×2（卷159：本篇+《送辛大之鄂渚不及》；
卷160：《都下送辛大之鄂》+《張七及辛大見尋南亭醉作》——V050 卷160 峴山 8×2 同款结构断言）：
**辛大只活在诗世界，而且活得热闹——送他、怀他、等他醉闯南亭**。
零铸造零 relation。

同姓不同人防线第三例（V047 斛斯正、V050 军功杜預）+典名零见：
知音典的「伯牙」通鉴 75 卷+全唐詩 120 卷计数全零、「鍾子期/絕弦」亦全零；
「鍾期」全库恰一处且在他卷他人挽诗（机器闭域断言，登记不引）——典在诗世界不在史部；
「子期」通鉴恰六处，机器断言处处前字必落 {盧,破,擒}（全是盧子期，tj-225/226），
且断言 tj-225 摘句落大曆十年（乙卯，775）→大曆十一年（丙辰，776）窗口——
**孟浩然開元末已卒（740），史部唯一的「子期」登场时诗人已死三十多年**：
连典的名字在史部都被另一个人占了。异姓同名不牵合、史部子期与诗中子期并置为读法声明。

题内 {{另}} 标记首见：题目字段本身就是「夏{{另|日|夕}}南亭懷辛大」——
异文在题面（日/夕），页内另有「山光忽西{{另|落|發}}」一处；
异文照登断言（V044 反向极性）双卡：两处标记字样必分别入 CITY/SCENE 引文；
ws 页 {{另}} 恰两处、{{别}}/{{*}} 零（生成时机器断言）。

读碑者亦有碑的后手——**亭与人在它诗俱在**（CITY 层）：
《張七及辛大見尋南亭醉作》篇题入引：同一座南亭、同一个辛大，
在孟集里是另一首诗的门口——本集的篇题就是这个小世界的档案。

KNOWN 零（如实记录第七例，audit 反向断言 SQL 无 KNOWN 字面量）：
新传「張九齡、王維雅稱道之」单得（旧传孟段无此 praise 语，机器断言零「稱道」）；
通鉴盧子期两段各单得——claim 四行全 LIKELY。

负证机器复查三层（生成时断言，快照变动即中止）：
① 通鉴：伯牙/鍾期/鍾子期/絕弦/辛大 全零；子期恰六处且前字全落 {盧,破,擒}；
   tj-225 摘句大曆十年→十一年窗口断言；
② 全唐詩：辛大（除辛大夫六处另册）恰 8=四锚点×2 结构、伯牙零；
   伯牙/鍾子期/絕弦全零、鍾期恰一处文件闭域 vol286（他人挽句登记不引）；
   刘长卿卷「辛大夫」锚点在场仅登记为它称不引（异衔不牵合）；
③ ws：{{另}} 恰二（题内+山光）、{{别}}/{{*}} 零；两传孟区间「稱道」零。

十句五排 4/2/2/2 形制首用（scene 4/city 2/world 2/person 2）；
本迁移立 1 个新 source（source-quantangshi-159——V018 从未立、V031 只立了 160）：
audit 断言 INSERT INTO poetry_source 恰一处且 id 必为该源。

用法: python3 -I emit_v051.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/夏日南亭懷辛大.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷203.txt').read_text(encoding='utf-8')
V159 = pathlib.Path('/tmp/src-dl/quantangshi/vol159.txt').read_text(encoding='utf-8')
V160 = pathlib.Path('/tmp/src-dl/quantangshi/vol160.txt').read_text(encoding='utf-8')
TJ225 = pathlib.Path('/tmp/src-dl/tongjian/tj-225.txt').read_text(encoding='utf-8')
TJ226 = pathlib.Path('/tmp/src-dl/tongjian/tj-226.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 夏{{另|日|夕}}南亭懷辛大', '夏{{另|日|夕}}南亭懷辛大',
                         'ws header title(题内{{另|日|夕}}——首见题面自带异文标记,照登不裁决)')
WS_AUTHOR = slice_between(WS, '| author   = 孟浩然', '| author   = 孟浩然', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '↑ [[全唐詩/卷159#夏日南亭懷辛大|全唐詩·卷159]]', '全唐詩·卷159]]',
                        'ws 页底注(底本指向——整理者动作,非史料)')
WS_CAT = slice_between(WS, '[[Category:仄韻五排]]', '[[Category:仄韻五排]]',
                       'ws 分类行(仄韻五排——整理者分类,非史料;V048 分类行判例)')
WS_L12 = slice_between(WS, '山光忽西{{另|落|發}}，池月漸東上。散髮乘夕涼，開軒臥閑敞。', '開軒臥閑敞。',
                       'ws第1段(山光西落{{另}}/池月东上/散发/开轩——夏夕四拍)')
WS_L34 = slice_between(WS, '荷風送香氣，竹露滴清響。欲取鳴琴彈，恨無知音賞。', '恨無知音賞。',
                       'ws第2段(荷风/竹露/取琴/恨无知音——由景入琴入怀)')
WS_L56 = slice_between(WS, '感此懷故人，中宵勞夢想。', '中宵勞夢想。', 'ws第3段(感此怀故人/中宵梦想——十句收束于想念)')
XTS_ZC = slice_between(XTS, '張九齡、王維雅稱道之。', '雅稱道之。',
                       '新传雅称道句(张九龄王维雅称道之——新传单得,旧传孟段无称道语;PERSON 层本体)')
TJ_ZQ1 = slice_between(TJ225, '李寶臣與昭義留後李承昭共救之，大破子期於清水，擒子期至京師；斬之。', '擒子期至京師；斬之。',
                       '通鉴775-776卢子期破擒斩段(史部唯一的子期是叛将——大曆十年→十一年窗口断言)')
TJ_ZQ2 = slice_between(TJ226, '及盧子期就擒，吳希光歸國', '吳希光歸國',
                       '通鉴776卢子期就擒余波摘句(同一叛将名字在他卷复现——通鉴六处子期全归此人)')
Q159_SELF = slice_between(V159, '==[[夏日南亭懷辛大]]==', '夏日南亭懷辛大]]==', '卷159 本篇篇题锚点')
Q159_SONG = slice_between(V159, '==[[送辛大之鄂渚不及]]==', '送辛大之鄂渚不及]]==', '卷159 送辛大之鄂渚不及篇题锚点')
Q160_DUSH = slice_between(V160, '==[[都下送辛大之鄂]]==', '都下送辛大之鄂]]==', '卷160 都下送辛大之鄂篇题锚点')
Q160_XUN = slice_between(V160, '==[[張七及辛大見尋南亭醉作]]==', '張七及辛大見尋南亭醉作]]==',
                         '卷160 张七及辛大见寻南亭醉作篇题锚点(同一南亭同一个辛大在另一首诗的门口)')

# ---------- 传区间归属复验（V036 立规） ----------
_ja, _jb = JTS.find('=孟浩然='), JTS.find('=元德秀=')
_xa, _xb = XTS.find('==孟浩然=='), XTS.find('===附 王昌齡===')
if not (0 <= _ja < _jb and 0 <= _xa <= XTS.find(XTS_ZC) <= _xb):
    raise SystemExit('切片越出孟浩然传区块——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；大曆十年→十一年） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')
_i = TJ225.find(TJ_ZQ1)
_heads = [m.start() for m in _HEAD.finditer(TJ225)]
_prev = [h for h in _heads if h < _i]
if not _prev or '大曆十年' not in TJ225[_prev[-1]:_prev[-1] + 60]:
    raise SystemExit('卢子期破擒段前的年标题不是大曆十年（775）——窗口断言失效，判决须重估')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_seg_j, _seg_x = JTS[_ja:_jb], XTS[_xa:_xb]
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_alltj = ''.join(f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt')))
_allq = ''.join(f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt')))
# ① 典名与人名在通鉴：伯牙/鍾期/鍾子期/辛大 全零；子期恰六处且前字全落 {盧,破,擒}
for _w in ('伯牙', '鍾期', '鍾子期', '辛大'):
    if _alltj.count(_w):
        raise SystemExit(f'「{_w}」在通鉴有命中——典名零见/行第无档论断须重估')
_zq = []
for _f in sorted(_tj.glob('tj-*.txt')):
    _t = _f.read_text(encoding='utf-8')
    for _m in re.finditer('子期', _t):
        _zq.append((_f.name, _t[_m.start() - 1]))
if len(_zq) != 6 or any(p not in '盧破擒' for _, p in _zq):
    raise SystemExit(f'通鉴「子期」不是恰六处全归盧子期（实 {len(_zq)} 处）——同姓同名防线须重估')
if not all(f in ('tj-225.txt', 'tj-226.txt') for f, _ in _zq):
    raise SystemExit('通鉴「子期」溢出 tj-225/226——叛将卢子期论断须重估')
# ② 全唐詩：辛大恰 4=四锚点×2 结构；伯牙全零；刘长卿卷辛大夫锚点仅登记在场（不引）
if _allq.count('伯牙') or _allq.count('鍾子期') or _allq.count('絕弦'):
    raise SystemExit('伯牙/鍾子期/絕弦在全唐詩有命中——典名零见论断须重估')
_zq_qts = [f.name for f in sorted(_qts.glob('vol*.txt')) if '鍾期' in f.read_text(encoding='utf-8')]
if _alltj.count('鍾期') or _zq_qts != ['vol286.txt']:
    raise SystemExit(f'「鍾期」不在诗世界恰一处（实 通鉴{_alltj.count("鍾期")}/全唐詩{_zq_qts}）——典在诗世界不在史部论断须重估')
_sd = sum(1 for m in re.finditer('辛大', _allq) if _allq[m.end():m.end() + 1] != '夫')
if _sd != 8:
    raise SystemExit(f'全唐詩「辛大」（除辛大夫）计数不是 8（实 {_sd}）——诗世界四档×2 论断须重估')
if _allq.count('辛大夫') != 6:
    raise SystemExit(f'全唐詩「辛大夫」计数不是 6（实 {_allq.count("辛大夫")}，卷148 四处+卷151 二处）——异衔六处册数须重估')
for _v, _t in ((V159, '夏日南亭懷辛大'), (V159, '送辛大之鄂渚不及'),
               (V160, '都下送辛大之鄂'), (V160, '張七及辛大見尋南亭醉作')):
    if _v.count(f'==[[{_t}]]==') != 1 or _v.count(f'{{:{_t}}}') != 1:
        raise SystemExit(f'辛大篇题锚点结构破坏：{_t}——4×2 结构断言失效')
_liu = pathlib.Path('/tmp/src-dl/quantangshi/vol148.txt').read_text(encoding='utf-8')
if '晦日陪辛大夫宴南亭' not in _liu:
    raise SystemExit('刘长卿卷「辛大夫」锚点不在场——异衔登记断言须重估')
# ③ ws：{{另}} 恰二（题内+山光）；{{别}}/{{*}} 零；两传孟区间「稱道」零
if WS.count('{{另') != 2 or '{{另|日|夕}}' not in WS or '{{另|落|發}}' not in WS:
    raise SystemExit('ws 页 {{另}} 不是恰二（题内+山光）——照登断言须重估')
if '{{别' in WS or '{{*' in WS:
    raise SystemExit('ws 页出现 {{别}}/{{*}}——快照已变，异文登记须重做')
if '稱道' in _seg_j or '辛大' in _seg_j or '辛大' in _seg_x:
    raise SystemExit('「稱道/辛大」落在不该落的传区间——负证失效，须重读原文')

BG = {
    'bg-108-scene': (
        '十句是一个夏夜独自凉下来的完整过程：山的光亮忽然往西沉'
        '（「山光忽西{{另|落|發}}」——此句页内挂 {{另}} 异文：落/發，照登不裁决），'
        '池上的月亮慢慢往东爬；披散着头发乘这傍晚的凉，打开窗卧看宽敞的夜'
        '（「散髮乘夕涼，開軒臥閑敞」——一天里最松弛的姿势）；'
        '风把荷香送来，竹上的露滴成清响（「荷風送香氣，竹露滴清響」——'
        '鼻子和耳朵先于心里）；想取琴弹一曲，恨没有知音来赏'
        '（「欲取鳴琴彈，恨無知音賞」——琴拿起来了，听众缺席）；'
        '有此感触便想起故人，半夜里神魂都为想念所劳'
        '（「感此懷故人，中宵勞夢想」——十句收在一个人的想念上）。'),
    'bg-108-city': (
        '这座「城」是一座南亭——它的档案全在诗里。题面本身就带异文：'
        '「夏{{另|日|夕}}南亭懷辛大」——日/夕两支在题目字段里并挂（题内 {{另}} 首见），'
        '照登不裁决。诗里的朋友「辛大」在两传孟区间计数全零（机器断言）——'
        '唐人呼行第不呼名，传不替他登记；但在全唐詩，「辛大」（异衔「辛大夫」六处另册）'
        '恰八处=四枚篇题锚点×2（V050 卷160 同款结构）：'
        '卷159《夏日南亭懷辛大》本篇与《送辛大之鄂渚不及》、'
        '卷160《都下送辛大之鄂》与《張七及辛大見尋南亭醉作》'
        '（四枚篇题锚点逐字入引，机器 8=4×2 结构断言）——'
        '**辛大只活在诗世界，而且活得热闹**：送他、怀他、等他醉闯南亭。'
        '同一座南亭、同一个辛大，就在本集另一首诗的门口。\n'
        '另登记不引：全唐詩刘长卿卷有「辛大夫」诸篇——衔称不同无从指认同人，'
        '异衔不牵合（V047 同姓不同人纪律）。页底注与分类行（仄韻五排）'
        '为整理者动作：照登+非史料声明+不升格（V048 分类行判例）。'),
    'bg-108-world': (
        '「恨無知音賞」押的是伯牙子期的知音典——但快照史部里这个典**连名字都没有**：'
        '「伯牙」通鉴 75 卷+全唐詩 120 卷计数全零，「鍾子期」「絕弦」亦全零'
        '（V046 典无史源、V050 山无史山的第三族）；「鍾期」全库恰一处且在诗不在史——'
        '卷286 他人挽友「向秀初聞笛，鍾期久罷琴」（机器文件闭域断言，登记不引：'
        '它卷他人句不属本诗档案，V050 同卷语境不挪砝码纪律）——'
        '**典活在诗世界，死在史部**。\n'
        '史部里倒是有「子期」，恰六处（机器断言处处前字必落「盧/破/擒」，'
        '全部集中在 tj-225/226）：田承嗣大将**盧子期**——'
        '大曆十年（乙卯，775）李宝臣等「大破子期於清水，擒子期至京師；斬之」'
        '（年标题窗口断言：775→776 之间），次年余波「及盧子期就擒，吳希光歸國」。\n'
        '孟浩然開元末已卒（新传「開元末，病疽背卒」判例句不引，只作时距参照）——'
        '史部唯一的子期登场时，写这首诗的人已死三十多年。'
        '**被斩的叛将子期与诗里被想念的子期**并置是本层读法声明，不是史实。'
        '季节「夏日」如 V048 的重阳一样是「每到」不是「某年」。本层不铸时间。'),
    'bg-108-person': (
        '传里给这个人一句体面：新传「**張九齡、王維雅稱道之**」——'
        '当朝两位大人物齐声称扬他（新传单得：旧传孟段无「稱道」语，'
        '生成时机器断言；不合龙不升）。\n'
        '把这句和诗对读：传里称扬他的张九龄、王维都是庙堂中人，'
        '诗里他半夜想念的却是一个连名都没传下来的辛大——'
        '**庙堂称扬与草堂想念**，同一位处士的两份清单。'
        '这是读法声明，不是史实；史实只有新传一句。'
        '判例零重开（audit 硬卡）：不才明主弃、放还、韩朝宗遑恤他、鹿门、'
        '孟亭、画浩然像、病疽背卒、樊泽刻碑，本层一个不引。'),
}
CLAIMS = {
    'claim-bg-108-scene': (
        'FACT', 'LIKELY',
        '十句全诗本文（ws 页 {{另}} 恰二处——题内+山光句，异文照登反向极性'
        '双卡：两处标记字样分别入 CITY/SCENE 引文，V044 判例；'
        'Textquality 75% 如实记）；夏夜四拍/琴拿起来听众缺席为本层读法声明，非史料断言。'),
    'claim-bg-108-city': (
        'FACT', 'LIKELY',
        '友有第无名：辛大两传孟区间计数全零（机器断言）；诗世界四档：'
        '全唐詩「辛大」（除辛大夫六处另册）恰 8=（卷159 两枚+卷160 两枚）篇题锚点×2 结构断言，'
        '四枚全数逐字入引；异衔登记不引：辛大夫六处（卷148 四处+卷151 二处）无从指认同人（V047 纪律）；'
        '题内 {{另|日|夕}} 首见照登不裁决；底注+分类行照登+非史料声明+不升格；'
        '季是節非年、友有第無名→零铸造零 relation。'),
    'claim-bg-108-world': (
        'FACT', 'LIKELY',
        '典名零见：伯牙/鍾子期/絕弦通鉴+全唐詩计数全零、鍾期全库恰一处且在他卷他人挽诗'
        '（机器闭域断言，登记不引）——典在诗世界不在史部（V046/V050 同族第三例）；'
        '子期恰六处全归叛将盧子期（前字 {盧,破,擒} 机器断言+tj-225/226 文件闭域断言'
        '+大曆十年→十一年年标题窗口断言）——同名不同人防线；'
        '时距声明（诗人開元末已卒，775 年登场者为另一子期）为读法声明；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-108-person': (
        'FACT', 'LIKELY',
        '新传雅称道句单得（旧传孟段无稱道语，生成时机器断言）→不升；'
        '庙堂称扬与草堂想念并置为读法声明；判例零重开'
        '（不才/放還/韓朝宗/遑恤他/鹿門/孟亭/畫浩然像/病疽背卒/刻碑——'
        'audit 关键语硬卡）；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-108-scene', 'source-ws-t300-108',
     '页面 夏日南亭懷辛大（header author+三段十句，四段以「……」相連——'
     '「山光忽西{{另|落|發}}」标记原样入引（页内异文照登，落/發不裁决，'
     'tang300-variants.md 新行）；同一 (claim,source) 主键一行容全文判例；'
     '正文另见 V018 claim-t300-108-text——本诗正文两度上限至此用满，后来者不得三引）',
     join(WS_AUTHOR, WS_L12, WS_L34, WS_L56)),
    ('claim-bg-108-city', 'source-ws-t300-108',
     '页面 夏日南亭懷辛大（header title 题内{{另|日|夕}}原样+页底注+分类行三段并收——'
     '题内异文（日/夕）系首见题面自带标记，照登不裁决（V044 反向极性）；'
     '底本指向与「仄韻五排」分类均为整理者动作：非史料声明、不升格（V048 分类行判例））',
     join(WS_TITLE, WS_NOTE, WS_CAT)),
    ('claim-bg-108-city', 'source-quantangshi-159',
     '卷一百五十九·孟浩然集两枚篇题锚点（本篇+《送辛大之鄂渚不及》——'
     '辛大四档之二；卷159 本迁移新立 source 行（V018 未立、V031 只立 160），'
     '辛大计数 8=4 锚点×2 结构为生成时机器断言）',
     join(Q159_SELF, Q159_SONG)),
    ('claim-bg-108-city', 'source-quantangshi-160',
     '卷一百六十·孟浩然集两枚篇题锚点（《都下送辛大之鄂》+《張七及辛大見尋南亭醉作》——'
     '辛大四档之二；同一座南亭同一个辛大在本集另一首诗的门口；'
     '异衔的「辛大夫」六处（刘长卿唱和卷148 四处+卷151 二处）只登记在册不引——异衔不牵合）',
     join(Q160_DUSH, Q160_XUN)),
    ('claim-bg-108-world', 'source-zizhi-tongjian-events',
     '卷二百二十五·大曆十年条内卢子期破擒斩段……卷二百二十六复现摘句'
     '（通鉴「子期」恰六处全归此人——前字 {盧,破,擒}+文件闭域+年标题窗口三重机器断言；'
     '伯牙/鍾期通鉴全零为负证扫描；同名不同人不牵合；各单得不升）',
     join(TJ_ZQ1, TJ_ZQ2)),
    ('claim-bg-108-person', 'source-xintangshu-wenyi',
     '卷二百零三·文藝下·孟浩然传雅称道句（张九龄王维齐声称扬——新传单得'
     '（旧传孟段无稱道语，生成时机器断言）；与诗中草堂想念的并置是读法声明）', XTS_ZC),
]
BG_LINES = {'bg-108-scene': (1, 2, 3, 4), 'bg-108-city': (5, 6),
            'bg-108-world': (7, 8), 'bg-108-person': (9, 10)}
BG_AUDIENCE = {'bg-108-scene': 'PRIMARY', 'bg-108-city': 'JUNIOR',
               'bg-108-world': 'SENIOR', 'bg-108-person': 'JUNIOR'}
BG_TITLES = {'bg-108-scene': '眼前：一个夏夜独自凉下来',
             'bg-108-city': '这座城：诗世界里的南亭与辛大',
             'bg-108-world': '这个天下：被叛将占用的名字',
             'bg-108-person': '这个人：庙堂称扬与草堂想念'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 32 首·十句五排 4/2/2/2 形制首用）；史实句均有逐字引证；'
                 '系年第二十六次判决「題有季有友，季是節非年、友有第無名」'
                 '（题证系列第十四状·周期季与行第友——夏日如重阳是每到不是某年，'
                 '辛大只传行第：两传零见、全唐詩恰四档篇题×2 结构机器断言）'
                 '→time.span/event.name/written_during 全缺席、零 relation；'
                 '典名零见+同名不同人防线：伯牙全库零、子期恰六处全归叛将盧子期'
                 '（前字断言+文件闭域+大曆十年→十一年窗口）；'
                 '题内 {{另|日|夕}} 标记首见——照登双卡（题面+山光句）；'
                 'KNOWN 零如实记录（雅称道句单得、卢子期段各单得——都不升）；'
                 '异衔不牵合（刘长卿卷辛大夫登记不引）；新立 source 恰一个'
                 '（source-quantangshi-159，audit 断言）；判例关键语零入引文。' for k in BG}


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
    A("""-- V051：孟浩然《夏日南亭懷辛大》(work-t300-108) 四层背景（阶段 D 第 32 首·十句五排）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V031、V048、V049、V050 已执行（work-t300-108 与其
--       text-work-t300-108-ws、source-ws-t300-108 是 V018 的行；source-xintangshu-wenyi 是 V016 的行；
--       source-quantangshi-160 是 V031 的行；source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源）。
--       本迁移新立 source 恰一个：source-quantangshi-159（断言）——V018 从未立 159、V031 只立了 160。
--
-- 数据源（可复现）：emit_v051.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/夏日南亭懷辛大.txt（题内 {{另}} 首见，{{另}} 恰二处断言）、
--   舊唐書卷190下 / 新唐書卷203（孟段负证+雅称道句）、全唐詩卷159/160（辛大四锚点×2 结构）、
--   通鑑卷225/226（盧子期两段）+ 通鑑 75 卷/全唐詩 120 卷负证计数扫描——
--   传区间归属、大曆十年→十一年窗口、伯牙/鍾期/子期/辛大 全部计数与结构生成时断言。
--
-- 做：1 个新 source（source-quantangshi-159，恰一处 INSERT，断言）+
--   4 BACKGROUND content/claim/background + 6 组逐字引用（(claim,source) 主键每对恰一行）+
--   10 行 background_line（十句形制：scene→1-4 city→5-6 world→7-8 person→9-10，
--   绑 text-work-t300-108-ws 的 10 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有季有友，季是節非年、友有第無名」）：
--   * 夏日=每到不是某年（V048 周期时间判例）；辛大只传行第：两传零见、
--     全唐詩恰八处=四档篇题×2、辛大夫六处另册（机器结构断言）——人只活在诗世界；
--   * 知音典：伯牙/鍾期通鉴+全唐詩计数全零；子期恰六处全归叛将盧子期
--     （前字 {盧,破,擒}+文件闭域+775→776 窗口三重断言）——同名不同人不牵合；
--   * 异衔不牵合：刘长卿卷辛大夫诸篇登记在场、零入引（V047 纪律）；
--   * 题内 {{另|日|夕}} 首见：题面标记逐字入 CITY 引文（照登双卡之一）；
--   * KNOWN 零如实记录（audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 夏夜四拍/庙堂称扬与草堂想念/两个子期并置均为读法声明，audit 双声明在 BG 文本内；
--   * 不才/放還/韓朝宗/遑恤他/鹿門/孟亭/畫浩然像/病疽背卒/刻碑 判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 50，不含 51
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-108-%';             -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-108-ws';  -- 恰 10（五排）
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-159';     -- 空（本迁移新立）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-108-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-108';                                  -- 10（4/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-108-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-108'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-108';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-108-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-quantangshi-159';  -- 恰 1（本迁移新立）
-- 回滚: recovery/V051_rollback.sql（按 id 全枚举删除，含新立的 source 行；
--   不动 V014/V015/V016/V018/V031 的行，不动其余共用来源行）
START TRANSACTION;""")

    A('\n-- ---------- 0. 新立 source：全唐詩卷159（恰一个，断言在生成器 audit） ----------')
    A("""INSERT INTO poetry_source (id, title, author, edition, url, rights_note, verification_status, source_kind, reliability)
SELECT * FROM (
SELECT 'source-quantangshi-159' AS id, '《全唐詩》全唐詩/卷159（维基文库录入本）' AS title, NULL AS author, '全唐詩/卷159（维基文库《全唐詩》录入本）' AS edition, 'https://zh.wikisource.org/wiki/全唐詩/卷159' AS url, '维基文库录入本，公有领域古籍。本卷为孟浩然诗卷，卷首 Collection header notes 标作者 ''''''孟浩然''''''。本卷条目只有锚点+转引用桩，正文在诗页。本行由 emit_v051.py 对快照逐字定位。核验状态保持 PENDING。' AS rights_note, 'PENDING' AS verification_status, 'POETRY_COLLECTION' AS source_kind, 'HIGH' AS reliability FROM DUAL
) AS t
WHERE NOT EXISTS (SELECT 1 FROM poetry_source x WHERE x.id = t.id);""")

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
    brows = [{'id': k, 'work_id': 'work-t300-108',
              'layer': {'bg-108-scene': 'SCENE', 'bg-108-city': 'CITY',
                        'bg-108-world': 'WORLD', 'bg-108-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（十句：4/2/2/2） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-108-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 51, 'Meng Haoran Thinking of Brother Xin on a Summer Evening at the South Pavilion background layers (stage-D poem 32, ten-line five-character regulated sequence, first use of the 4/2/2/2 shape): dating verdict twenty-six, fourteenth shape of the title-evidence series -- the title keeps a season and a friend, yet the season is a recurring festival not a year (summer like the Double Ninth means every-autumn grammar) and the friend survives only as a family-ranking: Xin the Eldest is zero-count in both biographies of Meng while the Quantangshi keeps exactly four traces of the name, two title-anchors in juan 159 and two in juan 160 each counted twice by structure (machine 4x2 assertion, all four quoted verbatim) -- the man lives only in the poetry world, and lives busily there: seen off, missed, expected to stumble drunk at the same south pavilion; the zhiyin allusion has no archive even in names: Boya zero across both corpora, while the Tongjian''s six occurrences of Ziqi are machine-proven to belong wholly to the rebel general Lu Ziqi (prefix closure on the surname and capture verbs plus file closure on juan 225/226 plus a locked Dali-10 to 11 year-heading window) -- when history''s only Ziqi takes the stage the poet has been dead thirty years; titles of another poet''s Xin-the-Marshal poems are registered as same-surname-different-title and never cited (no weight moved); a first: the variant marker sits inside the title field itself (sun/evening), transcribed verbatim with its sibling marker on line one (double verbatim assertion); the new-history praise sentence (Zhang Jiuling and Wang Wei praised him highly) is single-source, the old history carrying no praise verb (machine-asserted) -- no agreement, no promotion; KNOWN zero honestly recorded (audit reverse-asserts); readings declared as readings; twelve closed precedent keywords stay out of citations; exactly one new source opened: the Quantangshi juan 159 (audit asserts the single INSERT)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 51);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V051 精确回滚：只删 V051 插入的行（id 全枚举），含本迁移新立的 source-quantangshi-159。',
         '-- work-t300-108 本体、其 text_line 10 行与 source-ws-t300-108 都是 V018 的行，绝不删；',
         '-- 其余共用 source 行（xintangshu-wenyi/quantangshi-160/zizhi-tongjian-events）与既往迁移的行不删；',
         '-- V051 零 relation。',
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
    dels('poetry_source', 'id', ['source-quantangshi-159'])
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 51;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_L12, WS_L34, WS_L56,
              XTS_ZC, TJ_ZQ1, TJ_ZQ2, Q159_SELF, Q159_SONG, Q160_DUSH, Q160_XUN]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 题内 {{另}} 首见 + 山光句标记：照登双卡
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-108-city' and s == 'source-ws-t300-108')
    scene_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-108-scene')
    if '{{另|日|夕}}' not in city_ws:
        bad.append('题内标记 {{另|日|夕}} 未逐字入 CITY 引文（题内 {{另}} 首见照登断言）')
    if '{{另|落|發}}' not in scene_ex:
        bad.append('山光句标记 {{另|落|發}} 未逐字入 SCENE 引文（照登断言）')
    # 底注+分类三重断言
    if '全唐詩·卷159' not in city_ws or 'Category:仄韻五排' not in city_ws:
        bad.append('底注/分类行未照登入 CITY 引文（三重断言第一项失效）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-108-city' and s == 'source-ws-t300-108'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # 四枚辛大锚点全入 CITY（两卷 source 侧）
    for src, pairs in (('source-quantangshi-159', ('夏日南亭懷辛大', '送辛大之鄂渚不及')),
                       ('source-quantangshi-160', ('都下送辛大之鄂', '張七及辛大見尋南亭醉作'))):
        ex = next(e for c, s, _, e in CITATIONS if c == 'claim-bg-108-city' and s == src)
        for t in pairs:
            if f'==[[{t}]]==' not in ex:
                bad.append(f'辛大篇题锚点「{t}」未入 CITY 引文（4 枚须全入）')
    # 通鉴侧引文要素+禁代拟
    w_tj = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-108-world')
    if '盧子期' not in w_tj and '破子期' not in w_tj:
        bad.append('卢子期段要素不齐（盧子期/破子期须在场）')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-108':
            for w in ('不才', '放還', '韓朝宗', '遑恤他', '鹿門', '孟亭', '畫浩然像',
                      '病疽背卒', '刻碑鳳林山南', '年四十'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
            for w in ('伯牙', '鍾期'):
                if c == 'claim-bg-108-world' and w in ex:
                    bad.append(f'通鉴侧引文出现「{w}」——典名零见层不得代拟')
    # 异衔不牵合：辛大夫零入引文
    if '辛大夫' in cited:
        bad.append('异衔不牵合：「辛大夫」（刘长卿卷）登记不引，不得入引文')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '卒不赴',
                '隱鹿門山', '隠鹿門山', '孟亭', '畫浩然像', '太學賦詩',
                '皆位不顯', '開元、天寶間'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 十句形制 4/2/2/2
    want = {'bg-108-scene': 4, 'bg-108-city': 2, 'bg-108-world': 2, 'bg-108-person': 2}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('十句 background_line 必须 4/2/2/2（scene4 city2 world2 person2）')
    if len(re.findall(r"text-work-t300-108-ws' AS version_id", sql)) != 10:
        bad.append('bg_line INSERT 的 version 行数应为 10')
    # 新 source 恰一个且必为 159
    n_src = len(re.findall(r'INSERT INTO poetry_source', sql))
    if n_src != 1 or 'source-quantangshi-159' not in next(
            sql[m.end():m.end() + 200] for m in re.finditer(r'INSERT INTO poetry_source', sql)):
        bad.append('本迁移新立 source 必须恰一个且为 source-quantangshi-159')
    if "'source-quantangshi-159'" not in build_rollback():
        bad.append('回滚必须删除本迁移新立的 source-quantangshi-159')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V051 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V051 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-108' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V051 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-108' AS subject_id" in sql:
        bad.append('V051 的 claim 主语应全部是 bg-108-*，work-t300-108 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V051 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '友有第無名' not in body_all:
        bad.append('BG/文件头须含「友有第無名」判决声明')
    if '同名不同人' not in body_all:
        bad.append('BG/文件头须含「同名不同人」防线声明（盧子期断言）')
    if '读法声明' not in body_all:
        bad.append('BG 须含两处「读法声明」（两个子期/庙堂与草堂）')
    if '异衔不牵合' not in body_all:
        bad.append('BG/CITY 须含「异衔不牵合」（辛大夫登记不引）')
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
              f'切片传区间归属断言；通鉴年标题窗口断言（大曆十年→十一年）；'
              f'负证机器复查三层（伯牙/鍾期/鍾子期/絕弦/辛大通鉴全零+鍾期全库恰一处闭域 vol286+子期恰六处'
              f'前字闭域 {{盧,破,擒}}+文件闭域 tj-225/226/全唐詩辛大恰 8=4 锚点×2+辛大夫六处另册+'
              f'ws {{另}} 恰二/稱道两传区间零，快照变动即中止）；'
              f'题内 {{{{另|日|夕}}}} 首见照登双卡；四枚辛大锚点全入 CITY 断言；'
              f'异衔不牵合断言（辛大夫零入引文）；通鉴侧禁代拟断言；底注+分类三重断言；'
              f'判例只引不重开断言；十句 4/2/2/2 形制断言；零 KNOWN 反向断言；'
              f'新 source 恰一个断言（source-quantangshi-159，回滚含删除）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
