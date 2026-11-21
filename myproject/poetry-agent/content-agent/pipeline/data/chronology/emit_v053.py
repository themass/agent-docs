#!/usr/bin/env python3
"""阶段 D 第 34 首：生成 V053——孟浩然《春曉》(work-t300-121, V018 已立) 四层背景。

「为什么写」走到产品目标最硬的一寸：**异文第一次有可核查的出处**。
「夜來風雨聲」的异文不是笼统的「一本作」——ws 页 <ref> **实链**
《文苑英華 (四庫全書本)/卷0157》，异文「欲知昨夜風」四字可点开、可核到卷次；
「花落**知**多少」的异文「一作**無**」同样挂着这枚实链。
**「每句史实都有可核查出处」在异文层首次落地**（V049 <ref> 无实链 → 本迁移实链首见）。

系年第二十八次判决（题证系列第十六状·四库实链与馆藏谱系）：
「題有節候無年份，詩有三本無一家」——
「春曉」是节气感不是年份（V048 重阳、V051 夏日之后第三枚周期时间）；
而这首诗的版本谱系清楚到可以列出书架：from 三本——
文苑英華 (四庫全書本)/卷0157、唐音 (四庫全書本)/卷06、
四部叢刊本孟浩然集 djvu 第 121 页；底注又見全唐詩卷160；
页内 <ref> 又把异文钉回文苑英華卷0157。**三本各有其字，谁也没吃掉谁**——
异文登记先行于引用、照登不裁决（本页是「登记先行」纪律最完整的一次）。
零铸造零 relation。

**全唐詩快照内 {{另}} 标记首见（机器结构差异断言）**：
卷160 他篇皆是「篇题锚点+转引桩」（V049/V050/V051 三次验证的 2× 结构），
唯独《春曉》是**正文内联**：篇题锚点后直接 <poem>，
且内嵌第三见证「{{另|夜來風雨聲，花落知多少|欲知昨夜風，花落無多少}}」——
集部快照与选本页在同一枚异文上**互相指认**：
ws <ref> 说文苑英華作「欲知昨夜風」，卷160 内联 {{另}} 备作「欲知昨夜風，花落無多少」——
**两支 witness 在两个体系里各自被完整保留，没有一处合并**（audit 双断言硬卡
两处标记字样分别入 CITY/SCENE 引文）。

负证机器复查三层（生成时断言，快照变动即中止）：
① 通鉴：春曉/啼鳥/聞啼鳥 全零——最家喻户晓的二十字在史部一个字符都没有；
② 全唐詩：春曉 恰 5=卷160 消歧锚点「==[[春曉 (孟浩然)|春曉]]==」恰一处
   （**无转引桩**——内联结构断言 {{:春曉 count=0，全卷唯一例外）
   +卷283「奉和武相公春曉聞鶯」锚点×2+卷301 王建「《和門下武相公春曉聞鶯》王建」恰一
   ——**同名题族（春曉聞鶯唱和二家）登记在册、与孟诗无涉，不牵合不引**；
③ ws：Textquality|100% 恰一；<ref> 恰二且都指向卷0157 实链；
   {{另}}/{{别}}/{{*}} 零（异文全在 <ref> 与 from 字段，正文干净）；
   两传孟区间 春曉/啼鳥/風雨/花落/睡覺 全零。

四句绝句 1/1/1/1 形制（scene1/city1/world1/person1）——V018 后第二枚绝句形制；
**零新 source**（ws-121/quantangshi-160/283/301/jiutangshu-wenyuan/xintangshu-wenyi 均已立）。

PERSON 层的诚实（传句用尽）：孟浩然两传所有候选句均已入引
（生成时全库引文域逐句查重：少好節義/喜振人患難/以詩自適/不逹而卒/與之唱和/
署為從事/應進士不第/隱鹿門山/病疽背卒/同知名者/皆位不顯——十一句全在 V016/V031/
V037/V038 用过），**本迁移零传句入引**；PERSON 层只读版本目录：from 三本链
是这首诗在书架上的位置（四库本两部+四部丛刊本影印页码），这是「为什么写」之外
「凭什么传」的最实答案。异文出处断言（PERSON locator 硬卡「版本目录链，非史料断言」）。

用法: python3 -I emit_v053.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/春曉__孟浩然_.txt').read_text(encoding='utf-8')
V160 = pathlib.Path('/tmp/src-dl/quantangshi/vol160.txt').read_text(encoding='utf-8')
V283 = pathlib.Path('/tmp/src-dl/quantangshi/vol283.txt').read_text(encoding='utf-8')
V301 = pathlib.Path('/tmp/src-dl/quantangshi/vol301.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷203.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = [[春曉]]', '| title    = [[春曉]]', 'ws header title(消歧 wiki 链)')
WS_AUTHOR = slice_between(WS, '| author   = 孟浩然', '| author   = 孟浩然', 'ws header author(署名直证)')
WS_FROM = slice_between(WS, '| from     = 文苑英華 (四庫全書本)/卷0157',
                        '| from3    = 页面:Sibu Congkan0646-孟浩然-孟浩然集-1-1.djvu/121{{!}}孟浩然集 (四部叢刊本)',
                        'ws from 三本链(文苑英華卷0157/唐音卷06/四部叢刊孟浩然集 djvu121——版本目录链首用)')
WS_TYPE = slice_between(WS, '| type2    = 五言絕句', '| theme2   = 詠春詩',
                        'ws type2/theme2 两行(五言絕句/詠春詩——整理者分类,非史料;V048 分类行判例)')
WS_NOTE = slice_between(WS, '| notes    ={{Textquality|100%}}{{-|又見[[全唐詩/卷160]]}}', '又見[[全唐詩/卷160]]}}',
                        'ws 页底注(Textquality 100%+**又見卷160**跨卷又見——底注第三形态,照登+非史料声明)')
WS_L1 = slice_between(WS, '春眠不覺曉，處處聞啼鳥。', '處處聞啼鳥。', 'ws第1-2句(春眠不觉晓/处处闻啼鸟——通鉴全库零字符)')
WS_L2 = slice_between(WS, '夜來風雨聲<ref>《[[文苑英華 (四庫全書本)/卷0157|文苑英華]]》作「欲知昨夜風」</ref>，花落知<ref>《[[文苑英華 (四庫全書本)/卷0157|文苑英華]]》：「一作無」</ref>多少。',
                      '多少。', 'ws第3-4句(风雨声/花落知多少——两枚 <ref> 实链四库文苑英華卷0157,异文有出处首见)')
WS_CAT = slice_between(WS, '[[Category:千家詩]]', '[[Category:千家詩]]', 'ws 分类行(千家詩——选本入类,整理者动作,非史料)')
Q160 = slice_between(V160, '==[[春曉 (孟浩然)|春曉]]==', '春曉 (孟浩然)|春曉]]==',
                     '卷160 消歧篇题锚点(本篇全卷唯一正文内联——无转引桩,结构差异断言)')
Q160_INLINE = slice_between(V160, '{{另|夜來風雨聲，花落知多少|欲知昨夜風，花落無多少}}',
                            '欲知昨夜風，花落無多少}}',
                            '卷160 正文内联 {{另}}(全唐詩快照内 {{另}} 标记首见——第三见证与 ws <ref> 互证)')
Q283 = slice_between(V283, '==[[奉和武相公春曉聞鶯]]==', '奉和武相公春曉聞鶯]]==',
                     '卷283 奉和武相公春曉聞鶯篇题锚点(李益卷——同名题族登记)')
Q301 = slice_between(V301, '《和門下武相公春曉聞鶯》王建', '《和門下武相公春曉聞鶯》王建',
                     '卷301 和门下武相公春晓闻莺王建行(唱和两家之第二家——题族在册不牵合)')

# ---------- 传区间归属复验（V036 立规） ----------
_ja, _jb = JTS.find('=孟浩然='), JTS.find('=元德秀=')
_xa, _xb = XTS.find('==孟浩然=='), XTS.find('===附 王昌齡===')
if not (0 <= _ja < _jb and 0 <= _xa < _xb):
    raise SystemExit('孟浩然传区块定位失败——修订后重生成')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_alltj = ''.join(f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt')))
_allq = ''.join(f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt')))
# ① 通鉴：最家喻户晓的二十字在史部零字符
for _w in ('春曉', '啼鳥', '聞啼鳥'):
    if _alltj.count(_w):
        raise SystemExit(f'「{_w}」在通鉴有命中——家喻户晓零档案论断须重估')
# ② 全唐詩：春曉恰 5=卷160 锚点一（无桩，内联唯一例外）+卷283×2+卷301×1
if _allq.count('春曉') != 5:
    raise SystemExit(f'全唐詩「春曉」计数不是 5（实 {_allq.count("春曉")}）——题族论断须重估')
if V160.count('==[[春曉 (孟浩然)|春曉]]==') != 1 or V160.count('{{:春曉') != 0:
    raise SystemExit('卷160 春晓不是唯一正文内联（锚点一且无桩）——结构差异断言失效')
if V160.count('{{另|夜來風雨聲，花落知多少|欲知昨夜風，花落無多少}}') != 1:
    raise SystemExit('卷160 内联 {{另}} 第三见证结构变了——两支 witness 论断须重做')
if V283.count('==[[奉和武相公春曉聞鶯]]==') != 1 or V283.count('{{:奉和武相公春曉聞鶯}}') != 1:
    raise SystemExit('卷283 春曉聞鶯锚点结构破坏——题族册数须重估')
if V301.count('《和門下武相公春曉聞鶯》王建') != 1:
    raise SystemExit('卷301 王建和章行不在场——唱和两家论断须重估')
# ③ ws：100% 恰一、<ref> 恰二全指卷0157、{{另}}/{{别}}/{{*}} 零
if WS.count('{{Textquality|100%}}') != 1 or WS.count('<ref>') != 2:
    raise SystemExit('ws 页 100% 或 <ref> 数变了——互证/实链断言须重估')
if WS.count('文苑英華 (四庫全書本)/卷0157') != 3:
    raise SystemExit(f'卷0157 实链计数不是 3（from 一行+<ref> 两行，实测 {_ws_ref3} 次）——实链断言须重估'.replace('_ws_ref3', str(WS.count('文苑英華 (四庫全書本)/卷0157'))))
if any(m in WS for m in ('{{另', '{{别', '{{*')):
    raise SystemExit('ws 页正文出现 {{另}}/{{别}}/{{*}}——本页异文应全在 <ref> 体系，快照已变')
_seg_j, _seg_x = JTS[_ja:_jb], XTS[_xa:_xb]
for _w in ('春曉', '啼鳥', '風雨', '花落', '睡覺'):
    if _w in _seg_j or _w in _seg_x:
        raise SystemExit(f'「{_w}」落在孟浩然传区间——诗语零档案负证失效，须重读原文')
# ④ 传句用尽复查（PERSON 层零传句入引的反向前提）
for _s in ('少好節義', '喜振人患難', '以詩自適', '不逹而卒', '與之唱和', '署為從事',
           '應進士不第', '隱鹿門山', '隠鹿門山', '病疽背卒', '同知名者', '皆位不顯'):
    _hits = [f.name for f in sorted(pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry').glob('V0*.sql'))
             for _ln in f.read_text(encoding='utf-8').splitlines()
             if 'evidence_excerpt' in _ln and _s in _ln]
    if not _hits:
        raise SystemExit(f'传句「{_s}」未在任何既有迁移入引——「传句用尽」前提失效，PERSON 层须重设计')

BG = {
    'bg-121-scene': (
        '二十个字是一个早晨的完整苏醒：春睡得沉，不知不觉天亮了（「春眠不覺曉」——'
        '醒来的第一个念头是「已经天亮」）；醒来先听见的是鸟，到处都是（「處處聞啼鳥」——'
        '听觉先于视觉）；想起夜里的风雨声（「夜來風雨聲」——页内 <ref> 实链四库本'
        '《文苑英華》卷0157 作「欲知昨夜風」，异文有可核查出处首见，照登不裁决），'
        '那些花被打落了多少呢（「花落知」——同枚 <ref> 注「一作無」）多少——'
        '问题悬在问句上收束。通鉴 75 卷里「春曉」「啼鳥」一个字符都没有'
        '（机器断言）：最家喻户晓的二十字，史部零档案。'
        '醒来惜花的读法是本层声明，史实只有页上四句。'),
    'bg-121-city': (
        '这首诗的「城」是一座书架。底注「又見[[全唐詩/卷160]]」是整理者的跨卷又見注'
        '（底注第三形态：既非底本指向、也非「一作某某詩」——非史料声明、不升格）。'
        '卷160 的全唐詩快照里，本篇是**全卷唯一正文内联**：'
        '他篇皆是「篇题锚点+转引桩」（V049/V050/V051 三验），唯独《春曉》锚点后直接内嵌正文，'
        '且内嵌第三见证「{{另|夜來風雨聲，花落知多少|欲知昨夜風，花落無多少}}」'
        '（全唐詩快照内 {{另}} 标记首见，audit 照登硬卡）——'
        '它与 ws 页 <ref>「《文苑英華》作欲知昨夜風」**互证同支**：'
        '两个体系各自完整保留两支 witness，没有一处合并（异文照登纪律最完整的一页）。'
        '另登记在册、与孟诗无涉：全唐詩「春曉」恰五处，余三处是「春曉聞鶯」唱和题族'
        '（卷283 李益《奉和武相公春曉聞鶯》+卷301 王建《和門下武相公春曉聞鶯》）——'
        '同名题族不牵合（V051 异衔/V052 同名异地之后的**同题族不牵合**）。'),
    'bg-121-world': (
        '「春曉」是节气感不是年份——V048 重阳、V051 夏日之后第三枚周期时间：'
        '每个春天都这样醒一次，所以系不了年（判决在文件头）。'
        '史部侧本层只做负证：通鉴 75 卷「春曉」「啼鳥」「聞啼鳥」计数全零（机器断言）——'
        '这首诗在史部没有一秒的档案，它的全部档案都在诗世界与书架上。'
        '「唱和题族在册不引」是负证的延伸：同名句在史部与诗世界都不构成孟诗的语境'
        '（同卷语境不挪砝码，V049 纪律）。本层零铸造零 relation。'),
    'bg-121-person': (
        '这个人的传，本迁移**一个传字都不引**——生成时全库引文域逐句查重：'
        '孟浩然两传十一句候选（少好節義/喜振人患難/以詩自適/署為從事/與之唱和/'
        '應進士不第/不逹而卒/隱鹿門山/病疽背卒/同知名者/皆位不顯）'
        '全部已在 V016/V031/V037/V038 入引（机器断言在册）——'
        '传已讲完，再引就是重开判例。'
        '那「凭什么传」？版本目录给答案：from 三本——'
        '《文苑英華》四庫全書本卷0157、《唐音》四庫全書本卷06、'
        '《孟浩然集》四部叢刊本影印 djvu 第 121 页（页内链原样入引）；'
        '再加上全唐詩卷160 的又見注。**一首二十字的绝句，被四部书各抄了一遍**——'
        '书架就是它的传记。from 链是版本目录链（非史料断言，audit locator 硬卡），'
        '它说的是流传，不是写作。'),
}
CLAIMS = {
    'claim-bg-121-scene': (
        'FACT', 'LIKELY',
        '四句全诗本文（ws 页 {{Textquality|100%}}+两枚 <ref> 实链原样入引——'
        '异文有可核查出处首见（V049 <ref> 无实链→本迁移实链首见），'
        'audit 照登断言硬卡两枚 <ref> 字样；'
        '同一 (claim,source) 主键一行容全文判例；正文另见 V018 claim-t300-121-text——'
        '本诗正文两度上限至此用满，后来者不得三引）；'
        '通鉴春曉/啼鳥/聞啼鳥全零为负证扫描；苏醒过程与惜花读法为本层声明，非史料断言。'),
    'claim-bg-121-city': (
        'FACT', 'LIKELY',
        '书架档案：底注「又見全唐詩/卷160」照登（底注第三形态）+非史料声明+不升格；'
        '卷160 结构差异机器断言：本篇消歧锚点恰一+转引桩零=全卷唯一正文内联；'
        '内嵌 {{另}} 第三见证逐字入引（全唐詩快照内 {{另}} 首见，audit 双断言硬卡），'
        '与 ws <ref> 互证同支、两支 witness 不合并（异文照登不裁决）；'
        '同题族不牵合：「春曉聞鶯」唱和两家（卷283 李益/卷301 王建）锚点逐字入册，'
        '与孟诗无涉不牵合（V051 异衔/V052 同名异地之后第三形态）；'
        '题有節候無年份→零铸造零 relation。'),
    'claim-bg-121-world': (
        'FACT', 'LIKELY',
        '周期时间第三例（重阳/夏日/春曉——每到不是某年）；'
        '通鉴「春曉」「啼鳥」「聞啼鳥」计数全零（机器负证扫描——家喻户晓零档案）；'
        '诗语与唱和题族均不构成孟诗语境（V049 同卷语境不挪砝码延伸）；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-121-person': (
        'FACT', 'LIKELY',
        '传句用尽（首见）：孟传十一句候选全部已在 V016/V031/V037/V038 入引'
        '（生成时逐句全库引文域查重机器断言）——本迁移零传句入引，再引即重开判例；'
        'PERSON 层只读版本目录：from 三本链逐字入引（四库本文苑英華卷0157/'
        '四库本唐音卷06/四部丛刊孟浩然集 djvu121 页）——版本目录链非史料断言'
        '（audit locator 硬卡），说的是流传不是写作；'
        '「书架就是它的传记」为读法声明；判例零重开。'),
}
CITATIONS = [
    ('claim-bg-121-scene', 'source-ws-t300-121',
     '页面 春曉 (孟浩然)（header author+四句，三行以「……」相連——第3句含两枚 <ref> 实链'
     '《文苑英華 (四庫全書本)/卷0157》原样入引（异文有可核查出处首见：欲知昨夜風/一作無，'
     '照登不裁决，tang300-variants.md 新行）；同一 (claim,source) 主键一行容全文判例；'
     '正文另见 V018 claim-t300-121-text——本诗正文两度上限至此用满，后来者不得三引）',
     join(WS_AUTHOR, WS_L1, WS_L2)),
    ('claim-bg-121-city', 'source-ws-t300-121',
     '页面 春曉 (孟浩然)（notes 又見注+type2/theme2 分类两行+Category 三段并收——'
     '底注「又見全唐詩/卷160」系跨卷又見（底注第三形态：非底本指向、非一作某某詩）；'
     '五言絕句/詠春詩/千家詩均为整理者分类动作：非史料声明、不升格（V048 分类行判例）；'
     'header title 消歧链 [[春曉]] 原样并收——与 V018 作品题一致，不另作异文）',
     join(WS_TITLE, WS_NOTE, WS_TYPE, WS_CAT)),
    ('claim-bg-121-city', 'source-quantangshi-160',
     '卷一百六十·孟浩然集《春曉 (孟浩然)》正文内联段（消歧篇题锚点+内嵌 {{另}} 第三见证'
     '两段并收——全卷唯一正文内联（其余各篇锚点×2 转引桩结构，本篇锚点一+桩零，'
     '生成时机器结构差异断言）；内联 {{另}} 系全唐詩快照内 {{另}} 标记首见，'
     '与 ws 页 <ref> 互证同支——两支 witness 各自完整保留不合并）',
     join(Q160, Q160_INLINE)),
    ('claim-bg-121-city', 'source-quantangshi-283',
     '卷二百八十三·李益《奉和武相公春曉聞鶯》篇题锚点（「春曉聞鶯」唱和题族之一——'
     '同名题族在册不引正文：与孟诗无涉不牵合，V051 异衔/V052 同名异地第三形态；'
     '全唐詩「春曉」恰 5=160×1+283×2+301×1 生成时计数断言）', Q283),
    ('claim-bg-121-city', 'source-quantangshi-301',
     '卷三百零一·王建《和門下武相公春曉聞鶯》目录行（唱和题族之二——'
     '李益奉和、王建再和，武相公为唱和主场而孟浩然不在其中；册数断言见 283 locator）', Q301),
    ('claim-bg-121-person', 'source-ws-t300-121',
     '页面 春曉 (孟浩然)（header from 三本链整段入引——版本目录链，非史料断言：'
     '四庫全書本文苑英華卷0157+四庫全書本唐音卷06+四部叢刊本孟浩然集 djvu 第121页；'
     '「凭什么传」的书架答案；传句用尽：十一句候选全在 V016/V031/V037/V038 入引，'
     '本迁移零传句——audit 生成时逐句查重硬卡）', WS_FROM),
]
BG_LINES = {'bg-121-scene': (1,), 'bg-121-city': (2,), 'bg-121-world': (3,), 'bg-121-person': (4,)}
BG_AUDIENCE = {'bg-121-scene': 'PRIMARY', 'bg-121-city': 'JUNIOR',
               'bg-121-world': 'SENIOR', 'bg-121-person': 'JUNIOR'}
BG_TITLES = {'bg-121-scene': '眼前：一个春天的苏醒',
             'bg-121-city': '这座城：一支诗的两支见证与一个书架',
             'bg-121-world': '这个天下：史部没有的一秒',
             'bg-121-person': '这个人：传句用尽，书架接任'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 34 首·四句绝句 1/1/1/1 形制）；史实句均有逐字引证；'
                 '系年第二十八次判决「題有節候無年份，詩有三本無一家」'
                 '（题证系列第十六状·四库实链与馆藏谱系——「春曉」是节气感不是年份'
                 '（周期时间第三例：重阳/夏日/春曉），而版本谱系可列书架：'
                 'from 三本（文苑英華四库本卷0157/唐音四库本卷06/四部丛刊孟浩然集 djvu121）'
                 '+又見卷160+<ref> 钉回卷0157——三本各有其字谁也没吃掉谁）'
                 '→time.span/event.name/written_during 全缺席、零 relation；'
                 '异文有可核查出处首见：<ref> 实链具体卷次（V049 无实链→本迁移实链首见）；'
                 '全唐詩快照内 {{另}} 首见：卷160 本篇全卷唯一正文内联（锚点一桩零结构断言）'
                 '+内嵌第三见证与 ws <ref> 互证同支、两支 witness 不合并（audit 双断言硬卡）；'
                 '同题族不牵合：春曉聞鶯唱和两家（卷283/301）在册不引；'
                 '通鉴春曉/啼鳥/聞啼鳥全零（家喻户晓零档案，机器负证）；'
                 '传句用尽首见：孟传十一句全在 V016/V031/V037/V038 入引（生成时逐句查重硬卡）'
                 '→PERSON 层零传句、只读版本目录（非史料声明硬卡）；'
                 'KNOWN 零如实记录（audit 反向断言）；零新 source；判例关键语零入引文。' for k in BG}


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
    A("""-- V053：孟浩然《春曉》(work-t300-121) 四层背景（阶段 D 第 34 首·异文有可核查出处首见）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V016、V018、V031、V037、V038、V051、V052 已执行（work-t300-121 与其
--       text-work-t300-121-ws、source-ws-t300-121 是 V018 的行；source-quantangshi-160 是 V031 的行；
--       source-quantangshi-283 是 V018、source-quantangshi-301 是 V027 的行；
--       source-jiutangshu-wenyuan 与 source-xintangshu-wenyi 是 V016 的行）。
--       **本迁移零新 source**（audit 断言 SQL 无任何诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v053.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/春曉__孟浩然_.txt（<ref> 实链×2 指四库本文苑英華卷0157、from 三本链、
--   底注又見卷160、Textquality|100%——异文有出处首见+底注第三形态），
--   全唐詩卷160（全卷唯一正文内联+内嵌 {{另}} 第三见证——快照内 {{另}} 首见）、
--   卷283/301（春曉聞鶯唱和题族册数）、舊唐書卷190下/新唐書卷203（孟段负证零入引）
--   + 通鑑 75 卷/全唐詩 120 卷负证计数扫描+既有迁移引文域逐句查重——
--   传区间归属、春曉/啼鳥全部计数、内联结构差异、传句用尽前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 6 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 行 background_line（四句绝句形制：scene→1 city→2 world→3 person→4，
--   绑 text-work-t300-121-ws 的 4 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下；
--   **零传句入引**（传句用尽，PERSON 层只读版本目录链——见下）。
--
-- 诚实边界（这首的边界是「題有節候無年份，詩有三本無一家」）：
--   * 异文有可核查出处首见：<ref> 不是笼统「一本作」而是实链四库本《文苑英華》卷0157——
--     「每句史实有可核查出处」在异文层首次落地；两支 witness（<ref>/卷160 内联 {{另}}）
--     照登不裁决、各自完整保留不合并（audit 双断言硬卡两处标记字样）；
--   * 卷160 结构差异机器断言：本篇消歧锚点恰一+转引桩零=全卷唯一正文内联；
--   * 同题族不牵合：春曉聞鶯（李益奉和/王建再和）在册入引锚点、正文零引、不牵合孟诗；
--   * 通鉴春曉/啼鳥/聞啼鳥全零：家喻户晓零档案（机器负证，本层零入引只做声明）；
--   * 传句用尽首见：孟传十一句全在 V016/V031/V037/V038 入引（生成时逐句查重硬卡），
--     本迁移零传句——再引即重开判例；from 三本链=版本目录链（非史料声明，locator 硬卡）；
--   * KNOWN 零如实记录（第九例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 苏醒过程/惜花读法/「书架就是它的传记」均为读法声明；
--   * 不才明主弃/放還/韓朝宗/遑恤他/鹿門/孟亭/刻碑鳳林山南/雅稱道之/知音/南亭 判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 52，不含 53
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-121-%';             -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-121-ws';  -- 恰 4（绝句）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-121-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-121';                                  -- 4（1/1/1/1）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-121-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-121'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-121';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-121-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-121';   -- 恰 1（V018 旧行，零新源）
-- 回滚: recovery/V053_rollback.sql（按 id 全枚举删除；不动任何共用来源行、不动 V018 的行）
START TRANSACTION;""")

    A('\n-- ---------- 1. BACKGROUND content identities（零新 source——断言在生成器 audit） ----------')
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
    brows = [{'id': k, 'work_id': 'work-t300-121',
              'layer': {'bg-121-scene': 'SCENE', 'bg-121-city': 'CITY',
                        'bg-121-world': 'WORLD', 'bg-121-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（四句绝句：1/1/1/1） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-121-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 53, 'Meng Haoran Spring Dawn background layers (stage-D poem 34, four-line quatrain 1/1/1/1, first time a variant carries a checkable citation): dating verdict twenty-eight, sixteenth shape of the title-evidence series -- the title keeps a season-feeling not a year (third cyclic time after Double Ninth and summer day) while the poem keeps three books and no single family: the page''s <ref> notes are live links into the Siku Wenyuan Yinghua juan 157 (so the variant "欲知昨夜風" and "一作無" can be opened and checked -- the goal "every historical sentence has a verifiable source" lands on the variant layer for the first time), the from-fields list three shelves (Siku Wenyuan Yinghua 157, Siku Tangyin 6, Sibu Congkan Meng Haoran ji djvu page 121) and the note adds a cross-volume "also seen in Quantangshi juan 160"; in juan 160 this poem is the volume''s only inline text (machine structure assertion: one disambiguated anchor, zero transclusion stubs) embedding a third witness marker {{另}} -- the first {{另}} anywhere in the Quantangshi snapshot -- corroborating the ws <ref> branch, both witnesses preserved whole, never merged (audit double hard-assert); same-title-family no-conflation: the Chunxiao Wenying唱和 pair in juan 283/301 catalogued by anchor only, prose never quoted, never read as Meng''s context; Tongjian counts of 春曉/啼鳥/聞啼鳥 are all zero -- the most memorized twenty characters in China hold zero archive in history (machine negative); precedent exhaustion first appearance: all eleven candidate biography sentences of Meng were already cited in V016/V031/V037/V038 (generated-time per-sentence sweep hard-assert), so this migration quotes zero biography lines and PERSON reads only the bibliographic chain (declared non-historical in locator); KNOWN zero honestly recorded (ninth instance, audit reverse-asserts); zero new sources (six shared source rows pre-exist, audit asserts no source-row insert statement); closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 53);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V053 精确回滚：只删 V053 插入的行（id 全枚举）。',
         '-- work-t300-121 本体、其 text_line 4 行与 source-ws-t300-121 都是 V018 的行，绝不删；',
         '-- 全部六个共用 source 行（ws-121/quantangshi-160/283/301/jiutangshu-wenyuan/',
         '-- xintangshu-wenyi）均为他迁移所立，零删除（本迁移零新 source）；V053 零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 53;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re_search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_FROM, WS_TYPE, WS_NOTE, WS_L1, WS_L2, WS_CAT,
              Q160, Q160_INLINE, Q283, Q301]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 异文实链照登双断言：ws <ref>（SCENE）与卷160 内联 {{另}}（CITY）
    scene_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-121-scene')
    city_q160 = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-121-city' and s == 'source-quantangshi-160')
    _ref1 = '<ref>《[[文苑英華 (四庫全書本)/卷0157|文苑英華]]》作「欲知昨夜風」</ref>'
    _ref2 = '<ref>《[[文苑英華 (四庫全書本)/卷0157|文苑英華]]》：「一作無」</ref>'
    if _ref1 not in scene_ex:
        bad.append('<ref> 实链异文注未逐字入 SCENE 引文（异文有可核查出处首见照登硬卡）')
    if _ref2 not in scene_ex:
        bad.append('第二枚 <ref>「一作無」未逐字入 SCENE 引文（双 <ref> 照登硬卡）')
    if '{{另|夜來風雨聲，花落知多少|欲知昨夜風，花落無多少}}' not in city_q160:
        bad.append('卷160 内联 {{另}} 第三见证未逐字入 CITY 引文（快照内 {{另}} 首见照登硬卡）')
    # 底注/分类三重断言
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-121-city' and s == 'source-ws-t300-121')
    if '又見[[全唐詩/卷160]]' not in city_ws:
        bad.append('底注又見注未照登入 CITY 引文（底注第三形态照登断言）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-121-city' and s == 'source-ws-t300-121'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # PERSON from 链非史料声明硬卡
    p_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-121-person')
    if '版本目录链' not in p_loc or '非史料' not in p_loc:
        bad.append('PERSON locator 须含「版本目录链…非史料断言」（from 链不升格硬卡）')
    # 唱和题族只登锚点、正文零引
    if '春寒囀小' in cited or '侵黑行飛' in cited:
        bad.append('唱和题族正文零引（只登锚点/目录行）')
    # 传句零入引（本迁移引文域硬卡）
    for _s in ('少好節義', '喜振人患難', '以詩自適', '不逹而卒', '與之唱和', '署為從事',
               '應進士不第', '隱鹿門山', '隠鹿門山', '病疽背卒', '同知名者', '皆位不顯',
               '刻碑鳳林山南', '不才', '放還', '韓朝宗', '雅稱道之'):
        if _s in cited:
            bad.append(f'传句用尽/判例零重开：「{_s}」不得入本迁移引文')
    # 形制 1/1/1/1
    want = {'bg-121-scene': 1, 'bg-121-city': 1, 'bg-121-world': 1, 'bg-121-person': 1}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('四句绝句 background_line 必须 1/1/1/1')
    if len(re.findall(r"text-work-t300-121-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    # 零新 source 断言
    if 'INSERT INTO poetry_source' in sql:
        bad.append('本迁移有意零新 source，SQL 出现了诗源表新建插入语句')
    if any('DELETE FROM poetry_source' in l for l in build_rollback().splitlines()):
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
        bad.append("V053 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V053 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-121' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V053 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-121' AS subject_id" in sql:
        bad.append('V053 的 claim 主语应全部是 bg-121-*，work-t300-121 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V053 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '詩有三本無一家' not in body_all:
        bad.append('BG/文件头须含「詩有三本無一家」判决声明')
    if '互证' not in body_all:
        bad.append('BG/CITY 须含两支 witness「互证」声明')
    if '不牵合' not in body_all:
        bad.append('BG 须含「同题族不牵合」（春曉聞鶯在册）')
    if '读法' not in body_all:
        bad.append('BG 须含「读法」声明')
    if '传句用尽' not in body_all:
        bad.append('BG/PERSON 须含「传句用尽」首见声明')
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


import re  # noqa: E402  （audit 用）
re_search = re.search


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
              f'切片传区间归属断言；负证机器复查三层（通鉴春曉/啼鳥/聞啼鳥全零/'
              f'全唐詩春曉恰 5=160×1+283×2+301×1+卷160 内联结构断言（锚点一桩零）/'
              f'卷160 内联 {{另}} 第三见证恰一/ws 100% 恰一+<ref> 恰二+卷0157 恰三次+'
              f'{{另}}/{{别}}/{{*}} 零+孟段诗语全零，快照变动即中止）；'
              f'传句用尽逐句查重硬卡（十一句全在 V016/V031/V037/V038 引文域）；'
              f'<ref> 双注+卷160 {{另}} 三处标记字样照登硬卡；底注又見照登+三重断言；'
              f'PERSON 版本目录链非史料 locator 硬卡；唱和题族正文零引断言；'
              f'判例只引不重开断言；四句 1/1/1/1 形制断言；零 KNOWN 反向断言；'
              f'零新 source 反向断言（无诗源表新建插入，回滚零删源行）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
