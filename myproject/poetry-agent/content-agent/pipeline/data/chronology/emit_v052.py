#!/usr/bin/env python3
"""阶段 D 第 33 首：生成 V052——王維《過香積寺》(work-t300-133, V018 已立) 四层背景。

「为什么写」走到第一桩**署名之争**，而且是纯文本形态的异说：
**页底注整行「↑ [[全唐詩/卷126#過香積寺|全唐詩·卷126]] 一作王昌齡詩」——
没有 <ref>、没有 {{另}}，「一作某某詩」五个字裸写在 notes 字段里**
（V049 <ref> 署名异说之后第二形态：纯文本底注署名异说，登记先行于引用）。

系年第二十七次判决（题证系列第十五状·署名异说首见·纯文本形态）：
「題有寺名，寺在史部是戰場；詩有兩家，兩家各有一傳」——
题给一座寺：「過」是路过、「不知」是没到过——题面连「到过」都不担保，何谈系年；
寺在史部倒有档案，**四处「香積」全是战场**：通鉴 tj-220 至德二年（丁酉，757）
「庚子，諸軍俱發；壬寅，至長安城西，陳於香積寺北澧水之東」——
收复长安的香积寺之战；tj-233 贞元三年（丁卯，787）三处全是「香積之捷」的余话
（李泌对德宗「今聞泌言香積之事，朕自覺少理」）。
**史部的香積寺是一场胜仗，诗里的香積寺是一座没找到的禅寺**——
同名同字、一事一寺（V050 山无史山族的镜像：寺有史事、但不是那件事）。
零铸造零 relation。

署名异说两侧都有传，且两侧各有一句**从未入引**的活句（生成时全库引文域查重）：
王維侧：旧传「**維尤長五言詩**。」——史部唯一一句给他「最擅长」的判语，
本诗恰是五律（PERSON 层首引，count=1 且必落王维段断言）；
王昌齡侧：新传附录张镐–闾丘晓对话「**王昌齡之親，欲與誰養？**」——
杀他的闾丘晓求饶说家有老亲，张镐反问：王昌龄的爹娘谁养？
（V016 已立「以世亂還鄕里，爲刺史閭丘曉所殺」句——那句不再引，两度上限留给后人；
本迁移首引对话句，count=1 且必落附王昌齡段断言）。
**争夺这首诗署名的两个人，在史部一个是「尤长五言」、一个是「被谁养亲」——
没有一处史书替这首诗说过一个字的署名**。异说登记不裁决（V049 判例），
正文仍从 ws 页「王維」（V018 路线不动）。

三通互证不升（新合龙·诚实边界第八式）：闾丘晓事三源——
新传附录（將戮之→對話→曉默然）、通鉴 tj-220（「曉素傲很，不受鎬命。
比鎬至，睢陽城已陷三日。鎬召曉，杖殺之。」至德二年同卷窗口断言）、
旧传无此（JTS 閭丘曉 计数全零，机器断言）。新史说「将杀」、通鉴说「杖杀之」——
**意愿侧与执行侧并置不合并**，claim 保持 LIKELY，不升 KNOWN。

负证机器复查四层（生成时断言，快照变动即中止）：
① 通鉴：香積 恰 4=tj-220 一处+tj-233 三处（文件闭域）；閭丘曉 恰一处（tj-220）；
   王昌齡/王維 全零；雲峰/危石/毒龍/安禪 全零；两处摘句年标题窗口
   （至德二年→香积寺/杖杀段在前、贞元三年→余话段在前）；
② 全唐詩：香積 恰 5=（卷126 两枚+卷227 两枚）锚点+卷539 断词假命中一处
   （前字必「雞」：「雞香積露文」——机器断言在册，登记不引）；
   卷227 涪城锚点带「涪城縣」前缀——**同名异地**：蜀地涪城的香积寺
   不是长安香积寺，两处同名寺并登记、不合并；
③ ws：{{另}}/{{别}}/{{*}}/<ref> 全零 + Textquality|100% 恰一（零标记与 100% 互证，
   V048 判例·第二张 100% 页）；notes 整行含「一作王昌齡詩」（audit 照登硬卡）；
④ 传区间：两传王维段/新传附王昌齡段「香積」全零；JTS 全卷閭丘曉 零；
   「以世亂還鄕里」（V016 已用句）零入本迁移任何引文。

八句律詩 2/2/2/2 形制（scene2/city2/world2/person2）；
**零新 source**（ws-133/quantangshi-126/quantangshi-227/
jiutangshu-wenyuan/xintangshu-wenyi/zizhi-tongjian-events 六源行均已立）。

用法: python3 -I emit_v052.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/過香積寺.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS2 = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
XTS3 = pathlib.Path('/tmp/src-dl/xts-卷203.txt').read_text(encoding='utf-8')
V126 = pathlib.Path('/tmp/src-dl/quantangshi/vol126.txt').read_text(encoding='utf-8')
V227 = pathlib.Path('/tmp/src-dl/quantangshi/vol227.txt').read_text(encoding='utf-8')
TJ220 = pathlib.Path('/tmp/src-dl/tongjian/tj-220.txt').read_text(encoding='utf-8')
TJ233 = pathlib.Path('/tmp/src-dl/tongjian/tj-233.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证——异说之下仍从本页，登记先行)')
WS_NOTES = slice_between(WS, '| notes    = {{Textquality|100%}}', '一作王昌齡詩',
                         'ws 页底注整行(Textquality 100%+底本指向+**一作王昌齡詩**——纯文本署名异说首见，照登不裁决)')
WS_L1 = slice_between(WS, '不知香積寺，數里入雲峰。', '數里入雲峰。', 'ws第1联(不知/数里入——题面自陈未到)')
WS_L2 = slice_between(WS, '古木無人徑，深山何處鐘？', '深山何處鐘？', 'ws第2联(无人径/何处钟——寺未至声先到)')
WS_L3 = slice_between(WS, '泉聲咽危石，日色冷青松。', '日色冷青松。', 'ws第3联(泉咽/日冷——名句，通鉴全库零)')
WS_L4 = slice_between(WS, '薄暮空潭曲，安禪制毒龍。', '安禪制毒龍。', 'ws第4联(空潭/安禅制毒龙——收束于禅)')
WS_CAT = slice_between(WS, '[[Category:五言律詩]]', '[[Category:五言律詩]]', 'ws 分类行(五律——整理者分类,非史料;V048 分类行判例)')
JTS_YC = slice_between(JTS, '維尤長五言詩。', '尤長五言詩。',
                       '旧传尤长五言句(史部唯一判语——PERSON 层首引,V016 未用)')
XTS_DH = slice_between(XTS3, '張鎬按軍河南，兵大集，曉最-{後}-期，將戮之，辭曰：「有親，乞貸-{餘}-命。」鎬曰：「王昌齡之親，欲與誰養？」曉默然。', '曉默然。',
                       '新传附王昌齡张镐对话句(欲与谁养——署名异说之另一侧的人;V016 用所杀句、此句首引)')
TJ_XJS = slice_between(TJ220, '庚子，諸軍俱發；壬寅，至長安城西，陳於香積寺北澧水之東。', '陳於香積寺北澧水之東。',
                       '通鉴至德二年香积寺布阵段(史部的香积寺是战场——757 窗口断言)')
TJ_ZH = slice_between(TJ220, '曉素傲很，不受鎬命。比鎬至，睢陽城已陷三日。鎬召曉，杖殺之。', '杖殺之。',
                      '通鉴至德二年闾丘晓杖杀句(新传附录对话的执行侧——三通互证不升断言)')
TJ_JY1 = slice_between(TJ233, '且香積之捷，葉護欲引兵入長安，先帝親拜之於馬前以止之，葉護遂不敢入城。', '葉護遂不敢入城。',
                       '通鉴贞元三年香积之捷余话一(李泌语——787 窗口断言)')
TJ_JY2 = slice_between(TJ233, '今聞泌言香積之事，朕自覺少理。', '朕自覺少理。',
                       '通鉴贞元三年香积之捷余话二(德宗语——史部香积四处全归此役)')
Q126 = slice_between(V126, '==[[過香積寺]]==', '過香積寺]]==', '卷126 本篇篇题锚点(王维诗卷)')
Q126_S = slice_between(V126, '{{:過香積寺}}', '{{:過香積寺}}', '卷126 本篇转引桩')
Q227 = slice_between(V227, '==[[涪城縣香積寺官閣]]==', '涪城縣香積寺官閣]]==', '卷227 涪城县香积寺官阁篇题锚点(杜甫卷——同名异地)')
Q227_S = slice_between(V227, '{{:涪城縣香積寺官閣}}', '{{:涪城縣香積寺官閣}}', '卷227 同名异地转引桩')

# ---------- 传区间归属复验（V036 立规） ----------
_ja = JTS.find('=王維=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
_xa = XTS2.find('==王維==')
_seg_x2 = XTS2[_xa:XTS2.find('==鄭虔==')]
_x3a, _x3b = XTS3.find('===附 王昌齡==='), XTS3.find('===附 崔顥===')
_seg_x3 = XTS3[_x3a:_x3b]
if not (0 <= _ja and '尤長五言' in _seg_j and 0 <= _xa and 0 <= XTS3.find(XTS_DH) - _x3a < len(_seg_x3)):
    raise SystemExit('切片越出王维段/附王昌齡段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 60]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ220, TJ_XJS, '至德二年')
_window(TJ220, TJ_ZH, '至德二年')
_window(TJ233, TJ_JY1, '貞元三年')
_window(TJ233, TJ_JY2, '貞元三年')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_allq = ''.join(f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt')))
# ① 通鉴：香積恰 4=tj-220 一处+tj-233 三处；閭丘曉恰一处；诗人姓名与诗语全零
_xj = {n: t.count('香積') for n, t in _tjf.items() if '香積' in t}
if _xj != {'tj-220.txt': 1, 'tj-233.txt': 3}:
    raise SystemExit(f'通鉴「香積」不是 tj-220 恰一+tj-233 恰三（实 {_xj}）——战场寺名论断须重估')
if _alltj.count('閭丘曉') != 1 or TJ220.count('閭丘曉') != 1:
    raise SystemExit('通鉴「閭丘曉」不是恰一处（tj-220）——三通互证论断须重估')
for _w in ('王昌齡', '王昌龄', '王維', '雲峰', '危石', '毒龍', '安禪'):
    if _alltj.count(_w):
        raise SystemExit(f'「{_w}」在通鉴有命中——诗语/诗人零档案论断须重估')
# ② 全唐詩：香積恰 5=两卷锚点×2+卷539 断词假命中；涪城前缀=同名异地
_xq = sum(t.count('香積') for t in (_allq,))
if _xq != 5:
    raise SystemExit(f'全唐詩「香積」计数不是 5（实 {_xq}）——诗世界两锚点+断词一假命中论断须重估')
for _v, _t in ((V126, '過香積寺'), (V227, '涪城縣香積寺官閣')):
    if _v.count(f'==[[{_t}]]==') != 1 or _v.count(f'{{:{_t}}}') != 1:
        raise SystemExit(f'香積篇题锚点结构破坏：{_t}——两锚点×2 结构断言失效')
_v539 = pathlib.Path('/tmp/src-dl/quantangshi/vol539.txt').read_text(encoding='utf-8')
_hits539 = [i for i in range(len(_v539)) if _v539.startswith('香積', i)]
if len(_hits539) != 1 or _v539[_hits539[0] - 1] != '雞':
    raise SystemExit('卷539 断词假命中（雞香積）结构变了——假命中登记须重做')
# ③ ws：四标记体系全零 + Textquality|100% 恰一（互证 V048）+ notes 含异说
if any(m in WS for m in ('{{另', '{{别', '{{*', '<ref')):
    raise SystemExit('ws 页出现标记体系字样——零标记与 100% 互证断言须重估')
if WS.count('{{Textquality|100%}}') != 1 or '一作王昌齡詩' not in WS_NOTES:
    raise SystemExit('ws 页 Textquality|100% 或「一作王昌齡詩」不在场——照登断言须重估')
# ④ 传区间：香積 全零；JTS 全卷无閭丘曉；V016 已用句零入引文
if '香積' in _seg_j or '香積' in _seg_x2 or '香積' in _seg_x3:
    raise SystemExit('「香積」落在不该落的传区间——寺无史事负证失效，须重读原文')
if JTS.count('閭丘曉') or XTS2.count('閭丘曉'):
    raise SystemExit('旧传/新传王维卷出现「閭丘曉」——三通互证域须重估')

BG = {
    'bg-133-scene': (
        '八句是一次「没找到」的完整行程：不知道香积寺在哪，数里路走进了云遮的山峰'
        '（「不知香積寺，數里入雲峰」——题面先自陈未到）；古树夹着无人走的小径，'
        '深山在哪处响着钟声（「古木無人徑，深山何處鐘？」——寺还没到，声先来）；'
        '泉声在险石间咽住，日光在青松上变冷（「泉聲咽危石，日色冷青松」——'
        '通鉴 75 卷里「危石」「青松」这样的诗语一个字都没有）；'
        '薄暮里空潭弯弯，以安禅降伏毒龙（「薄暮空潭曲，安禪制毒龍」——'
        '十四个字走完找寺到入禅）。读法是读法，史实只有页上八句。'),
    'bg-133-city': (
        '这座城的档案先登记一桩公案：页底注整行「↑ [[全唐詩/卷126#過香積寺|全唐詩·卷126]] '
        '一作王昌齡詩」——「一作某某詩」五个字**裸写在 notes 字段里**，'
        '没有 <ref>、没有 {{另}}（V049 <ref> 署名异说之后的纯文本第二形态），'
        '照登不裁决；底本指向与「五言律詩」分类为整理者动作（非史料声明，V048 判例）。'
        '寺名在诗世界有两处锚点：卷126（王维卷）本篇、卷227《涪城縣香積寺官閣》——'
        '**同名异地**：涪城（蜀地）的香积寺不是长安香积寺，两处并登记、不合并'
        '（同姓不同人纪律的跨类延伸——V051 异衔不牵合）。'
        '另登记不引：卷539「雞香積露文」是断词假命中（「雞香」词组撞出「香積」二字，'
        '机器断言前字必「雞」在册）。页 {{另}}/{{别}}/{{*}}/<ref> 全零而 Textquality|100%——'
        '零标记与 100% 互证（V048 首张 100% 页判例，本迁移为第二张）。'),
    'bg-133-world': (
        '史部有这座寺，四处——**全是打仗**：通鉴至德二年（丁酉，757）'
        '「庚子，諸軍俱發；壬寅，至長安城西，陳於香積寺北澧水之東」——'
        '收复长安的香积寺之战，年标题窗口断言（757）。\n'
        '三十年后贞元三年（丁卯，787）三处余话全是这场仗：李泌对德宗'
        '「且香積之捷，葉護欲引兵入長安，先帝親拜之於馬前以止之」，'
        '德宗「今聞泌言香積之事，朕自覺少理」（两处摘句均年标题 787 窗口断言）。'
        '机器断言：通鉴「香積」恰四处=tj-220 一+tj-233 三；「王維」「王昌齡」通鉴全零；'
        '「雲峰」「危石」「毒龍」「安禪」诗语通鉴全零。\n'
        '**史部的香积寺是一场胜仗，诗里的香积寺是一座没找到的禅寺**——'
        '同名同字、一事一寺（V050「山无史山」的镜像：寺有史事、但不是那件事）。'
        '本层不铸时间，零铸造零 relation。'),
    'bg-133-person': (
        '署名之争的两侧各有一句从未入引的活句（生成时全库引文域查重）：'
        '王維侧，旧传「**維尤長五言詩**。」——史部唯一一句给他「最擅长」的判语，'
        '本诗恰是一首五律（旧传单得，首引）。\n'
        '王昌齡侧，新传附录张镐–闾丘晓对话：晓误期将戮，辞以有亲，'
        '镐曰「**王昌齡之親，欲與誰養？**」晓默然——杀他的人求饶说家有老亲，'
        '张镐反问：王昌龄的爹娘谁养？（V016 已立「爲刺史閭丘曉所殺」句——'
        '那句不再引，两度上限留给后来者）。'
        '三通互证不升：晓事三源——新传附录（将戮）、通鉴 tj-220'
        '（「曉素傲很，不受鎬命……鎬召曉，杖殺之」，757 窗口断言）、'
        '旧传无此（JTS 全卷閭丘晓零，机器断言）——新史言意愿、通鉴言执行，'
        '**并置不合并**，claim 保持 LIKELY。\n'
        '「争夺这首诗署名的两个人，一个在史部得了『尤长五言』、'
        '一个得了『被谁养亲』——没有一处史书替这首诗说过一个字的署名」：'
        '此句是读法声明，不是史实。'),
}
CLAIMS = {
    'claim-bg-133-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页四标记体系全零+Textquality|100% 互证，V048 判例；'
        '同一 (claim,source) 主键一行容全文判例；正文另见 V018 claim-t300-133-text——'
        '本诗正文两度上限至此用满，后来者不得三引）；'
        '「没找到」的行程与入禅收束为本层读法声明，非史料断言。'),
    'claim-bg-133-city': (
        'FACT', 'LIKELY',
        '纯文本署名异说首见：底注整行含「一作王昌齡詩」逐字入引'
        '（audit 照登硬卡；V049 <ref> 形态之后的第二形态），登记不裁决、正文仍从 ws 页；'
        '寺名两锚点结构断言（卷126 本篇+卷227 涪城县香积寺官阁各×2）——'
        '同名异地不合并（V051 异衔不牵合跨类延伸）；卷539 断词假命中机器登记不引；'
        '底注+分类行照登+非史料声明+不升格（V048 分类行判例）；'
        '零标记与 Textquality|100% 互证（第二张 100% 页）；'
        '题有寺名而寺不系年→零铸造零 relation。'),
    'claim-bg-133-world': (
        'FACT', 'LIKELY',
        '香积寺在史部只有战场：通鉴「香積」恰四处=tj-220 至德二年布阵一+tj-233 '
        '贞元三年余话三（文件闭域+两处摘句双年标题窗口断言）；'
        '「王維」「王昌齡」「雲峰」「危石」「毒龍」「安禪」通鉴全零（机器扫描）；'
        '两传王维段/附王昌齡段「香積」全零（机器断言）——寺有史事、不是那件事'
        '（V050 山无史山族镜像）；certainty 不覆盖任何系年，'
        '诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-133-person': (
        'FACT', 'LIKELY',
        '署名异说两侧各单得：旧传「尤長五言詩」句史部唯一（首引，段内位置断言）；'
        '新传附录「欲與誰養」对话句首引（段内位置断言；V016 已用「所殺」句零入'
        '本迁移引文——两度上限纪律，audit 硬卡）；三通互证不升：'
        '新传言意愿（將戮）、通鉴言执行（杖殺之，757 窗口）、旧传无此（JTS 全卷零）——'
        '并置不合并，claim 保持 LIKELY（诚实边界第八式）；'
        '「没有一处史书替这首诗说过署名」声明为读法非史实；判例零重开。'),
}
CITATIONS = [
    ('claim-bg-133-scene', 'source-ws-t300-133',
     '页面 過香積寺（header author+四联八句，五段以「……」相連——页 {{另}}/{{别}}/{{*}}/<ref> '
     '全零+Textquality|100% 互证（V048 判例第二张）；同一 (claim,source) 主键一行容全文判例；'
     '正文另见 V018 claim-t300-133-text——本诗正文两度上限至此用满，后来者不得三引）',
     join(WS_AUTHOR, WS_L1, WS_L2, WS_L3, WS_L4)),
    ('claim-bg-133-city', 'source-ws-t300-133',
     '页面 過香積寺（header notes 整行+分类行两段并收——底注含「**一作王昌齡詩**」'
     '系纯文本署名异说首见（无 <ref>/{{另}}，V049 之后第二形态），照登不裁决（V044 反向极性'
     '同族）；底本指向与「五言律詩」分类均为整理者动作：非史料声明、不升格）',
     join(WS_NOTES, WS_CAT)),
    ('claim-bg-133-city', 'source-quantangshi-126',
     '卷一百二十六·王维诗卷本篇篇题锚点+转引桩（香积寺诗世界档案之一；'
     '锚点×2 结构为生成时机器断言；署名异说的集部侧——异说照登不裁决）',
     join(Q126, Q126_S)),
    ('claim-bg-133-city', 'source-quantangshi-227',
     '卷二百二十七·杜甫诗卷《涪城縣香積寺官閣》篇题锚点+转引桩'
     '（同名异地：蜀地涪城的香积寺不是长安香积寺——两处并登记不合并，'
     'V051 异衔不牵合跨类延伸；卷539「雞香積」断词假命中机器登记不引）',
     join(Q227, Q227_S)),
    ('claim-bg-133-world', 'source-zizhi-tongjian-events',
     '卷二百二十·至德二年香积寺布阵段+闾丘晓杖杀段……卷二百三十三·贞元三年'
     '香积之捷两处余话（四段以「……」相連——通鉴「香積」恰四处全归此役：'
     '文件闭域+双年标题窗口机器断言；「王維/王昌齡/雲峰/危石/毒龍/安禪」通鉴全零'
     '为负证扫描；史部香积寺=战场，诗里香积寺=未至之寺）',
     join(TJ_XJS, TJ_ZH, TJ_JY1, TJ_JY2)),
    ('claim-bg-133-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传尤长五言句（史部唯一「最擅长」判语——本迁移首引'
     '（V016/V035/V043/V044 均未用此句，生成时全库引文域查重）；与署名异说并读为读法）',
     JTS_YC),
    ('claim-bg-133-person', 'source-xintangshu-wenyi',
     '卷二百零三·文藝下·附王昌齡张镐–闾丘晓对话段（「王昌齡之親，欲與誰養」——'
     '署名异说另一侧的人；V016 已用「以世亂還鄕里，爲刺史閭丘曉所殺」句，'
     '该句对后来迁移关闭、本迁移零入引——两度上限；此对话句首引）', XTS_DH),
    ('claim-bg-133-person', 'source-zizhi-tongjian-events',
     '卷二百二十·至德二年闾丘晓杖杀段（三通互证执行侧：新传附录言意愿、'
     '通鉴言「杖殺之」、旧传全卷无闾丘晓——并置不合并，不升 KNOWN；'
     '与 WORLD 层引文同段——同 (claim,source) 主键本迁移仅此一行）', TJ_ZH),
]
BG_LINES = {'bg-133-scene': (1, 2), 'bg-133-city': (3, 4),
            'bg-133-world': (5, 6), 'bg-133-person': (7, 8)}
BG_AUDIENCE = {'bg-133-scene': 'PRIMARY', 'bg-133-city': 'JUNIOR',
               'bg-133-world': 'SENIOR', 'bg-133-person': 'JUNIOR'}
BG_TITLES = {'bg-133-scene': '眼前：一次没找到的寻寺',
             'bg-133-city': '这座城：底注里的公案与两处同名寺',
             'bg-133-world': '这个天下：史部的香积寺是一场胜仗',
             'bg-133-person': '这个人：尤长五言与被谁养亲'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 33 首·八句律詩 2/2/2/2）；史实句均有逐字引证；'
                 '系年第二十七次判决「題有寺名，寺在史部是戰場；詩有兩家，兩家各有一傳」'
                 '（题证系列第十五状·署名异说首见纯文本形态——题面「過/不知」连到过都不担保，'
                 '底注「一作王昌齡詩」裸写无标记，照登不裁决；通鉴香積恰四处全归 757 香积寺之战'
                 '（文件闭域+757/787 双年标题窗口断言），寺有史事不是那件事）'
                 '→time.span/event.name/written_during 全缺席、零 relation；'
                 '同名异地：涪城香积寺与长安香积寺并登记不合并（V051 异衔纪律跨类延伸）；'
                 '卷539「雞香積」断词假命中机器登记不引；'
                 '署名两侧各一句首引（尤長五言/欲與誰養——V016 已用句零入引）；'
                 '三通互证不升（意愿侧与执行侧并置不合并，诚实边界第八式）；'
                 'KNOWN 零如实记录（audit 反向断言）；零标记与 Textquality|100% 互证（第二张）；'
                 '零新 source（六共用源行均已立）；判例关键语零入引文。' for k in BG}


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
    A("""-- V052：王維《過香積寺》(work-t300-133) 四层背景（阶段 D 第 33 首·署名异说纯文本首见）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V027、V035、V051 已执行（work-t300-133 与其
--       text-work-t300-133-ws、source-ws-t300-133、source-quantangshi-227 是 V018 的行；
--       source-quantangshi-126 是 V035 的行；source-xintangshu-wenyi 是 V016 的行；
--       source-jiutangshu-wenyuan 是 V016 的行；source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源）。
--       **本迁移零新 source**（audit 断言 SQL 无任何诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v052.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/過香積寺.txt（零标记+Textquality|100% 互证、底注「一作王昌齡詩」）、
--   舊唐書卷190下（尤长五言句首引+王维段负证）、新唐書卷202/203（王维卷负证+附王昌齡对话句首引）、
--   通鑑卷220/233（香积寺战场四段+双年标题窗口）+ 通鑑 75 卷/全唐詩 120 卷负证计数扫描——
--   传区间归属、香積/閭丘曉/诗语全部计数与断词假命中、年标题窗口生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 8 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句形制：scene→1-2 city→3-4 world→5-6 person→7-8，
--   绑 text-work-t300-133-ws 的 8 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有寺名，寺在史部是戰場；詩有兩家，兩家各有一傳」）：
--   * 纯文本署名异说：底注「一作王昌齡詩」逐字入 CITY 引文（audit 照登硬卡），登记不裁决；
--   * 寺有史事、不是那件事：通鉴香積恰四处全归 757 之战（闭域+757/787 窗口断言）；
--   * 同名异地：卷227 涪城香积寺≠长安香积寺，并登记不合并；卷539 断词假命中机器登记不引；
--   * 三通互证不升：意愿侧（新传將戮）与执行侧（通鉴杖殺之）并置不合并，claim 保持 LIKELY；
--   * V016 已用「所殺」句两度上限关闭，本迁移零入引（audit 硬卡「以世亂還鄕里」不在引文）；
--   * 「没有一处史书替这首诗说过署名」为读法声明，audit 双声明在 BG 文本内；
--   * KNOWN 零如实记录（第八例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 寻寺行程/入禅收束均为读法声明；不才/凝碧/輞川/蓝田/奉佛段/代宗诏集 判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 51，不含 52
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-133-%';             -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-133-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-133-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-133';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-133-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-133'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-133';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-133-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id LIKE 'source-quantangshi-1%';  -- 与执行前相同（零新源）
-- 回滚: recovery/V052_rollback.sql（按 id 全枚举删除；不动任何共用来源行、不动 V018 的行）
START TRANSACTION;""")

    A('\n-- ---------- 1. BACKGROUND content identities（零新 source——本迁移断言在生成器 audit） ----------')
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
    brows = [{'id': k, 'work_id': 'work-t300-133',
              'layer': {'bg-133-scene': 'SCENE', 'bg-133-city': 'CITY',
                        'bg-133-world': 'WORLD', 'bg-133-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（八句：2/2/2/2） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-133-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 52, 'Wang Wei Visiting Xiangji Temple background layers (stage-D poem 33, eight-line regulated verse, the authorship dispute first appears as bare prose): dating verdict twenty-seven, fifteenth shape of the title-evidence series -- the title keeps a temple-name while history keeps only a battle at that name: the Tongjian''s four occurrences of Xiangji are machine-proven to sit wholly in juan 220 (the 757 battle array north of the temple by the Li River, locked behind a Zhide-2 year heading) and juan 233 (three echoes of "the victory at Xiangji" in Li Bi''s dialogue with the emperor, locked behind a Zhenyuan-3 heading) -- history''s Xiangji Temple is a victory, the poem''s is a temple never found; the signature dispute sits bare in the notes field (no ref tag, no variant marker): "also attributed to Wang Changling" transcribed verbatim into the CITY citation (audit hard-assert) and registered without adjudication; the two rival names each contribute one sentence never before cited -- the Old History''s sole verdict "he excelled above all in five-character verse" and the New History appendix''s retort "who then will feed Wang Changling''s parents?" (the sentence V016 already used stays closed to this migration, two-use ceiling asserted absent); three sources on the murder of Lu Qiu-xiao by Zhang Hao placed side by side without merging -- intent on one side, execution on the other, so the claim stays LIKELY (no KNOWN, audit reverse-asserts); same-name-different-place: the Fucheng Xiangji temple in the Du Fu volume registered alongside, never merged; a false word-boundary hit in juan 539 machine-logged and never quoted; zero new sources (six shared source rows pre-exist, audit asserts no source-row insert statement at all); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 52);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V052 精确回滚：只删 V052 插入的行（id 全枚举）。',
         '-- work-t300-133 本体、其 text_line 8 行与 source-ws-t300-133 都是 V018 的行，绝不删；',
         '-- 全部六个共用 source 行（ws-133/quantangshi-126/quantangshi-227/jiutangshu-wenyuan/',
         '-- xintangshu-wenyi/zizhi-tongjian-events）均为他迁移所立，零删除（本迁移零新 source）；',
         '-- V052 零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 52;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_AUTHOR, WS_NOTES, WS_L1, WS_L2, WS_L3, WS_L4, WS_CAT,
              JTS_YC, XTS_DH, TJ_XJS, TJ_ZH, TJ_JY1, TJ_JY2,
              Q126, Q126_S, Q227, Q227_S]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 纯文本署名异说照登硬卡
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-133-city' and s == 'source-ws-t300-133')
    if '一作王昌齡詩' not in city_ws:
        bad.append('「一作王昌齡詩」未逐字入 CITY 引文（纯文本署名异说照登硬卡）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-133-city' and s == 'source-ws-t300-133'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # 两卷锚点入 CITY
    for src, toks in (('source-quantangshi-126', ('==[[過香積寺]]==', '{{:過香積寺}}')),
                      ('source-quantangshi-227', ('==[[涪城縣香積寺官閣]]==', '{{:涪城縣香積寺官閣}}'))):
        ex = next(e for c, s, _, e in CITATIONS if c == 'claim-bg-133-city' and s == src)
        for t in toks:
            if t not in ex:
                bad.append(f'香積篇题锚点「{t}」未入 CITY 引文（两卷×2 结构须全入）')
    # 断词假命中与同名异地零入引文
    if '雞香積' in cited:
        bad.append('卷539 断词假命中「雞香積」登记不引，不得入引文')
    # PERSON 层首引句要素
    p_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-133-person' and s == 'source-jiutangshu-wenyuan')
    if '尤長五言' not in p_jts:
        bad.append('「尤長五言」未入 PERSON 旧传引文（首引断言）')
    p_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-133-person' and s == 'source-xintangshu-wenyi')
    if '欲與誰養' not in p_xts:
        bad.append('「欲與誰養」未入 PERSON 新传引文（首引断言）')
    if '以世亂還鄕里' in cited:
        bad.append('V016 已用「以世亂還鄕里」句两度上限关闭，本迁移零入引')
    # 通鉴侧引文要素+禁代拟
    w_tj = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-133-world')
    if '香積寺北澧水之東' not in w_tj or '香積之捷' not in w_tj:
        bad.append('香积寺战场段要素不齐（布阵句/捷后余话须在场）')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-133':
            for w in ('凝碧', '輞川', '藍田', '長齋', '不才', '放還', '韓朝宗', '病疽背卒'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
            for w in ('雲峰', '危石', '毒龍', '安禪'):
                if c != 'claim-bg-133-scene' and w in ex:
                    bad.append(f'非 SCENE 引文出现诗语「{w}」——史部零档案层不得代拟')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山', '隠鹿門山',
                '孟亭', '畫浩然像', '太學賦詩', '開元、天寶間', '詩名冠代'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句形制 2/2/2/2
    want = {'bg-133-scene': 2, 'bg-133-city': 2, 'bg-133-world': 2, 'bg-133-person': 2}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('八句 background_line 必须 2/2/2/2')
    if len(re.findall(r"text-work-t300-133-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    # 零新 source 断言
    if 'INSERT INTO poetry_source' in sql:
        bad.append('本迁移有意零新 source，SQL 出现了诗源表新建插入语句')
    if 'source-quantangshi' in build_rollback().replace('poetry_citation', ''):
        rb_src = [l for l in build_rollback().splitlines() if 'DELETE FROM poetry_source' in l]
        if rb_src:
            bad.append('回滚不得删除任何 source 行（本迁移零新 source）')
    # KNOWN 零如实记录
    if "'KNOWN'" in sql:
        bad.append('本迁移有意零 KNOWN，SQL 出现了 KNOWN 字面量')
    if {v[1] for v in CLAIMS.values()} != {'LIKELY'}:
        bad.append('本迁移 claim 应全 LIKELY（零 KNOWN 如实记录）')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V052 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V052 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-133' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V052 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-133' AS subject_id" in sql:
        bad.append('V052 的 claim 主语应全部是 bg-133-*，work-t300-133 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V052 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '寺在史部是戰場' not in body_all:
        bad.append('BG/文件头须含「寺在史部是戰場」判决声明')
    if '一作王昌齡詩' not in body_all:
        bad.append('BG 须含「一作王昌齡詩」异说照登声明')
    if '同名异地' not in body_all:
        bad.append('BG/CITY 须含「同名异地」（涪城香积寺不合并）')
    if '读法声明' in body_all and '不是史实' not in body_all and '读法' not in body_all:
        bad.append('BG 须含「读法」声明')
    if '不合并' not in body_all:
        bad.append('BG/PERSON 须含「并置不合并」（三通互证不升）')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 17 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（王维段/附王昌齡段）；双年标题窗口断言'
              f'（至德二年→布阵+杖杀、贞元三年→余话两处）；'
              f'负证机器复查四层（通鉴香積恰 4=tj-220 一+tj-233 三/閭丘曉恰一/诗人姓名与'
              f'雲峰危石毒龍安禪全零/全唐詩香積恰 5=两卷锚点×2+卷539 断词假命中前字必雞/'
              f'ws 四标记全零与 Textquality|100% 互证/传区间香積零+JTS 全卷閭丘曉零，'
              f'快照变动即中止）；「一作王昌齡詩」照登硬卡；两卷锚点×2 全入 CITY 断言；'
              f'「尤長五言/欲與誰養」首引断言；「以世亂還鄕里」零入引断言（两度上限）；'
              f'通鉴侧禁代拟断言；断词假命中零入引断言；底注+分类三重断言；'
              f'判例只引不重开断言；八句 2/2/2/2 形制断言；零 KNOWN 反向断言；'
              f'零新 source 反向断言（无 INSERT INTO poetry_source，回滚零删源行）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
