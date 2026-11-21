#!/usr/bin/env python3
"""阶段 D 第 38 首：生成 V057——王維《青谿》(work-t300-056, V018 已立) 四层背景。

「为什么写」走到「同字两界」的第二形态（V056 怨情之后）：
**题面这条溪，在史部只是一件开路的事**——通鉴「青谿」（此「谿」字）75 卷**全零**，
「青溪」恰一处=tj-249 大中十三年（己卯，八五九）窗口内的追书
「初，韋皋在西川，開青溪道以通群蠻，使由蜀入貢」——史部的青溪是一条贡使走的路
（文件闭域+年标题窗口机器断言；**「初」字追书新边界**：窗口年是入书年非事件年，
韦皋事在德宗朝——年窗口只锁文本位置，不锁事件时间，如实声明）。
**诗的收束两个字「已矣」，通鉴「已矣」恰二处却都不算数**——
tj-192 两处皆「…而已矣」句末语气（机器断言两处前字必「而」）：
「垂釣將已矣」是决志，「而已矣」是语气——撞字两界，在册零入引。
诗语「亂石」「深松」「垂釣」「黃花川」「趣途」通鉴全零；
全唐詩「青谿」恰 2=本篇锚+桩（此异体题族唯本篇）、「過青谿水」异题零命中——
**异题支在快照内无凭，如实在册**。零铸造零 relation。

异文侧一个首见：**「一名」式异名注首见**——页底注第二行
「一名「過青谿水作」」纯文本无标记（V052 署名异说、V055 川一作水之后
纯文本第三式：题之异名整短语挂底注）；CITY 引文含其原样，audit 硬卡
「一名「過青谿水作」」字样，登记不裁决；页 {{另}}/{{别}}/{{*}}/<ref> 四全零
而 75%（V055 零标记×75% 正交再验，机器断言）。

PERSON 层**两传同事异词并置首引**：旧传「居母䘮，柴毁骨立，殆不勝䘮。」
（JTS 恰一，XTS 零）×新传「母喪，毀幾不生。」（XTS 恰一，JTS 零）——
同一件事（为母守丧毁瘠），两部书两种措辞，各自逐字首引、并列不合并
（生成时全库查重既往零入引；「两源合龙」判例的反向操作：**合而不并**——
事同一而词各各，audit 双硬卡）。诗「我心素已閒」的閒与传「柴毁骨立」的毁
并置是读法声明非史实；两传王维段「青谿」「垂釣」全零（机器断言）。

十二句五古 4/2/4/2 形制首用；正文第二引上限用满第五例
（V018 text claim 一引在先，全库查重恰一处；SCENE 取末联子句二引对后来关闭）。

用法: python3 -I emit_v057.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/青谿.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS2 = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
V125 = pathlib.Path('/tmp/src-dl/quantangshi/vol125.txt').read_text(encoding='utf-8')
TJ249 = pathlib.Path('/tmp/src-dl/tongjian/tj-249.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = 青谿', '| title    = 青谿', 'ws header title(题面无标记直录)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '| notes    = {{Textquality|75%}}↑ [[全唐詩/卷125#青谿|全唐詩·卷125]]\n一名「過青谿水作」',
                        '一名「過青谿水作」',
                        'ws 页底注(75%+底本指向+「一名「過青谿水作」」纯文本一名式异名注首见,照登不裁决)')
WS_CAT = slice_between(WS, '[[Category:五言古詩]]', '[[Category:五言古詩]]', 'ws 分类行(五言古詩——整理者分类,非史料;V048 分类行判例)')
WS_L12 = slice_between(WS, '言入黃花川，每逐青谿水。\n隨山將萬轉，趣途無百里。', '趣途無百里。',
                       'ws第1-2联(入川逐水/随山万转——行程起笔)')
WS_L34 = slice_between(WS, '聲喧亂石中，色靜深松裏。\n漾漾泛菱荇，澄澄映葭葦。', '澄澄映葭葦。',
                       'ws第3-4联(声喧色静/漾漾澄澄——喧静对写的中段)')
WS_L56 = slice_between(WS, '我心素已閒，清川澹如此。\n請留盤石上，垂釣將已矣。', '垂釣將已矣。',
                       'ws第5-6联(心閒川澹/垂钓已矣——收在决志语上;「垂釣將已矣」系第二引)')
JTS_S = slice_between(JTS, '居母䘮，柴毁骨立，殆不勝䘮。', '殆不勝䘮。',
                      '旧传居母丧柴毁句(从未入引,PERSON 层首引,生成时全库查重硬卡;新传异词不合并)')
XTS_S = slice_between(XTS2, '母喪，毀幾不生。', '毀幾不生。',
                      '新传母丧毁几不生句(从未入引,PERSON 层与旧传并置首引,全库查重硬卡;两源词异不合并)')
TJ_QX = slice_between(TJ249, '初，韋皋在西川，開青溪道以通群蠻，使由蜀入貢。', '使由蜀入貢。',
                      '通鉴大中十三年窗口内追书韦皋开青溪道句(青溪通鉴唯一一处——贡使之路;「初」字追书:窗口年非事件年)')
Q125 = slice_between(V125, '==[[青谿]]==', '==[[青谿]]==', '卷125 本篇篇题锚点(无消歧直锚+桩,同 V055 结构)')
Q125_S = slice_between(V125, '{{:青谿}}', '{{:青谿}}', '卷125 本篇转引桩')

# ---------- 传区间归属复验（V036 立规） ----------
_ja = JTS.find('=王維=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
_xa = XTS2.find('==王維==')
_seg_x = XTS2[_xa:XTS2.find('==鄭虔==')]
if not (0 <= _ja and '柴毁骨立' in _seg_j and '毀幾不生' in _seg_x):
    raise SystemExit('切片越出王维段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；本处附「初」字追书边界声明） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 80]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ249, TJ_QX, '大中十三年')
if not TJ249[TJ249.find('初，韋皋在西川') - 1] in '\n<':
    pass  # 「初」字领起追书已在引文原样，窗口=入书年非事件年（边界声明入 BG/claim）

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_allq = ''.join(f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt')))
# ① 通鉴：青谿（谿字）全零；青溪恰一闭域 tj-249 开道；已矣恰二皆而已矣（前字必而）
if _alltj.count('青谿') != 0:
    raise SystemExit('通鉴「青谿」不再全零——题面谿字无档论断失效')
_qx = {n: t.count('青溪') for n, t in _tjf.items() if '青溪' in t}
if _qx != {'tj-249.txt': 1} or TJ249.count('開青溪道') != 1:
    raise SystemExit(f'通鉴「青溪」不是恰一处开道（实 {_qx}）——贡使之路论断须重估')
_yy = [(m.start(), _alltj[m.start() - 1]) for m in re.finditer('已矣', _alltj)]
if len(_yy) != 2 or any(p != '而' for _, p in _yy):
    raise SystemExit(f'通鉴「已矣」不是恰二处且前字皆「而」（实 {[_p for _, _p in _yy]}）——撞字两界在册须重做')
for _w in ('亂石', '深松', '垂釣', '黃花川'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗语史部不接的判决失效，须重读')
# ② 全唐詩：青谿恰二=本篇锚桩；异题「過青谿水」零命中；青溪十一处在册
if _allq.count('青谿') != 2 or V125.count('==[[青谿]]==') != 1 or V125.count('{{:青谿}}') != 1:
    raise SystemExit(f'全唐詩「青谿」不是恰二（本篇锚桩）——此体题族论断须重估')
if _allq.count('過青谿水') != 0:
    raise SystemExit('异题「過青谿水」在快照内出现——异题无凭在册论断失效')
if _allq.count('青溪') != 11:
    raise SystemExit(f'全唐詩「青溪」不再是 11 处（实 {_allq.count("青溪")}）——彼体诗题在册册数须重估')
# ③ ws：四标记全零 + 75% 恰一 + 一名注恰一（零标记×75% 正交再验）
if WS.count('{{另') or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页标记不再是全零——零标记页论断失效，须重读快照')
if WS.count('{{Textquality|75%}}') != 1 or WS.count('一名「過青谿水作」') != 1:
    raise SystemExit('ws 页 75%/一名注结构变了——一名式异名注首见断言失效')
# ④ 传区间与首引前提
for _w in ('青谿', '青溪', '垂釣'):
    if _w in _seg_j or _w in _seg_x:
        raise SystemExit(f'「{_w}」落在王维传区间——传不系溪负证失效，须重读原文')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
for _w in ('居母䘮', '毀幾不生'):
    _p = [f.name for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V057')
          for _ln in f.read_text(encoding='utf-8').splitlines()
          if 'evidence_excerpt' in _ln and _w in _ln]
    if _p:
        raise SystemExit(f'「{_w}」已在 {_p} 入引——两传并置首引前提失效，PERSON 层须重设计')
_prev_t = [f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V057')
           for _ln in f.read_text(encoding='utf-8').splitlines()
           if 'evidence_excerpt' in _ln and '垂釣將已矣' in _ln]
if _prev_t != ['V018']:
    raise SystemExit(f'本诗正文既往引文域不是恰一处 V018（实 {_prev_t}）——第二引上限论断须重估')

BG = {
    'bg-056-scene': (
        '十二句是一段顺着水走的行程：说进黄花川，就常常沿着青谿水走'
        '（「言入黃花川，每逐青谿水」）；山随人转将近万道，途程不满百里'
        '（「隨山將萬轉，趣途無百里」）；水声在乱石中喧响，青色在深松里安静'
        '（「聲喧亂石中，色靜深松裏」——喧与静各占半句）；'
        '菱荇漾漾地浮过，葭葦澄澄地映水（「漾漾泛菱荇，澄澄映葭葦」）。'
        '收束把心交出去：「我心素已閒，清川澹如此」——心本來就閒，'
        '正如这条川淡；「請留盤石上，垂釣將已矣」——此末联系**第二引**'
        '（正文 V018 text claim 一引在先，全库查重恰一处），'
        '两度上限至此用满，此诗正文对后来迁移关闭。「已矣」二字收的是决志；'
        '心与川互为譬喻是页上原文的对写，不是史实。'),
    'bg-056-city': (
        '这条城的档案先登记另一个题目：页底注第二行'
        '「一名「過青谿水作」」——「青谿／過青谿水作」两名并挂，'
        '**纯文本无标记**（V052 纯文本署名异说、V055 「川一作水」底注尾巴之后'
        '**「一名」式异名注首见**——整短语挂底注第二行，audit 硬卡字样），'
        '照登不裁决；且异题「過青谿水」在全唐詩快照**零命中**（机器断言）：'
        '这条异题支在存卷里无凭，如实登记而不据以改题。'
        '页 {{另}}/{{别}}/{{*}}/<ref> 四全零而 Textquality 只有 75%——'
        'V055 的零标记×75% 正交横截面在此再验一次（机器断言）。'
        '分类行「五言古詩」为整理者动作：照登+非史料声明+不升格（V048 判例）。'
        '卷125 本篇为「无消歧篇题锚点+转引桩」结构（同 V055，机器断言各恰一）。'
        '谿字题族唯本篇：全唐詩「青谿」恰 2=锚+桩；邻体「青溪」11 处'
        '（谿/溪系字样异写）分布他卷各是各诗，在册不引不牵合。'),
    'bg-056-world': (
        '题面这条溪，史部只记过一件开路的事：通鉴「青谿」（这个「谿」字）'
        '75 卷**全零**；「青溪」恰一处（文件闭域+年标题窗口机器断言）——'
        '大中十三年（己卯，八五九）窗口内：「初，韋皋在西川，開青溪道以通群蠻，'
        '使由蜀入貢」。**史部的青溪是一条贡使走的路**。\n'
        '**「初」字追书新边界（如实声明）**：通鉴以「初」字在八五九年窗口里追记'
        '德宗朝旧事——年窗口锁的是这段文字入书的位置，不是事件发生的年份；'
        'V034 立的窗口断言只证文本位置，本迁移不据以系任何事（audit 声明在册）。\n'
        '诗的收束「垂釣將已矣」；通鉴「已矣」恰二处却都不算数——两处皆'
        '「…而已矣」句末语气（tj-192 论规矩礼乐，机器断言二处前字必「而」）：'
        '「已矣」在诗里是决志、在史部是语气——**撞字两界，在册零入引**'
        '（V056 泪两界之后的第二形态）。诗语「亂石」「深松」「垂釣」「黃花川」'
        '通鉴亦全零。**溪在史部止一開道，已矣在史部只而已矣**；'
        '本层零铸造零 relation。'),
    'bg-056-person': (
        '诗的收束是「我心素已閒」；两部史书写到这个人守母丧时，用的却是'
        '最不吃得消的字。旧传：「**居母䘮，柴毁骨立，殆不勝䘮。**」'
        '（居母丧，毁瘠骨立，几乎撑不过丧期）；新传：「**母喪，毀幾不生。**」'
        '（母丧，毁顿几乎活不成）——**同一件事，两部书两种措辞**'
        '（生成时全库查重：两句既往零入引，本迁移并置首引；'
        '旧传单得、新传单得，各自逐字入引，**并列不合并**——'
        '「V037 两源合龙」的反向操作：事同一而词各各，合而不并，audit 双硬卡）。\n'
        '把閒与毁并置看：诗里的心「素已閒」，传里的人毁到骨立——'
        '同一个人的两种时刻，并置是读法声明非史实。王维传其余已用句'
        '（以詩名盛/凝碧/輞川/茶鐺/奉佛段/尤長五言/事母崔氏以孝聞 V055 首引/'
        '齋中四物 V054 首引）一个不重开；两传王维段「青谿」「青溪」「垂釣」'
        '全零（机器断言）——传写其人，不提这条溪。'),
}
CLAIMS = {
    'claim-bg-056-scene': (
        'FACT', 'LIKELY',
        '十二句全诗本文（ws 页四标记全零、Textquality 75%——零标记与不完备'
        '并存，V055 正交横截面再验）；末联「請留盤石上，垂釣將已矣」系第二引：'
        '正文 V018 text claim 一引在先（生成时全库查重恰一处），两度上限至此'
        '用满、此诗正文对后来迁移关闭（audit 硬卡）；心川对写与决志读法系'
        '本层声明非史料断言。'),
    'claim-bg-056-city': (
        'FACT', 'LIKELY',
        '「一名」式异名注首见：底注第二行「一名「過青谿水作」」纯文本无标记'
        '（V052/V055 纯文本二式之后第三式），逐字入引 audit 照登硬卡，登记不裁决；'
        '异题「過青谿水」快照零命中（机器断言）——异题无凭如实登记不改题；'
        '页四标记全零而 75%（正交再验）；分类行照登+非史料声明+不升格；'
        '卷125 无消歧锚+桩（各恰一）；全唐詩「青谿」恰 2 唯本篇、邻体「青溪」'
        '恰 11 处他卷在册不引（谿/溪字样异写）；题有溪而无时→零铸造零 relation。'),
    'claim-bg-056-world': (
        'FACT', 'LIKELY',
        '溪在史部止一开道：通鉴「青谿」全零+「青溪」恰 1 处=tj-249 大中十三年'
        '（己卯，八五九）窗口追书「開青溪道以通群蠻」（文件闭域+年标题窗口'
        '机器断言）；**「初」字追书边界**：窗口年系入书年非事件年，'
        '本迁移不据以系任何事（audit 声明）；撞字两界第二形态：通鉴「已矣」'
        '恰 2 皆「而已矣」语气（tj-192，机器断言前字必而），诗之决志语在册'
        '零入引；诗语亂石/深松/垂釣/黃花川通鉴全零；两传王维段青谿/青溪/垂釣'
        '全零；certainty 不覆盖任何系年，诗 time.span/event.name/written_during '
        '零铸造零 relation。'),
    'claim-bg-056-person': (
        'FACT', 'LIKELY',
        '两传同事异词句并置首引（V037 两源合龙的反向操作「合而不并」首见）：'
        '旧传「居母䘮，柴毁骨立，殆不勝䘮」旧传单得、新传「母喪，毀幾不生」'
        '新传单得（生成时全库引文域查重：两句既往零命中，audit 双硬卡；'
        '各自逐字入引、词异不合并）；閒与毁并置为读法声明非史实；'
        '王维其余已用判例句零重开；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-056-scene', 'source-ws-t300-056',
     '页面 青谿（header author+六联十二句，四段以「……」相連——'
     '末联「請留盤石上，垂釣將已矣」**第二引**：正文 V018 text claim 一引在先、'
     '本迁移取末联二引，**两度上限至此用满，此诗正文对后来迁移关闭**'
     '（生成时全库查重恰一处=V018）；页四标记全零、75%（正交再验）',
     join(WS_AUTHOR, WS_L12, WS_L34, WS_L56)),
    ('claim-bg-056-city', 'source-ws-t300-056',
     '页面 青谿（header title+页底注+分类行三段并收——底注第二行'
     '「一名「過青谿水作」」系**「一名」式异名注首见**（纯文本第三式，'
     'audit 硬卡字样照登不裁决；异题快照零命中如实登记）；「五言古詩」分类系'
     '整理者动作：非史料声明、不升格；页 {{另}}/{{别}}/{{*}}/<ref> 全零而 75%）',
     join(WS_TITLE, WS_NOTE, WS_CAT)),
    ('claim-bg-056-city', 'source-quantangshi-125',
     '卷一百二十五·王维集《青谿》篇题锚点+转引桩（无消歧直锚——机器断言'
     '锚桩各恰一；全唐詩「青谿」恰 2 即此二处，邻体「青溪」恰 11 处他卷'
     '在册不引——谿/溪字样异写）', join(Q125, Q125_S)),
    ('claim-bg-056-world', 'source-zizhi-tongjian-events',
     '卷二百四十九·大中十三年（己卯，八五九）窗口内「初」字追书韦皋开青溪道段'
     '（**通鉴 75 卷「青溪」唯一一处**：文件闭域+年标题窗口机器断言——'
     '史部的青溪是贡使之路；**窗口年系入书年非事件年**（「初」字追书，'
     '不据以系事）；青谿字全零+已矣恰二皆而已矣（前字必而）在册零入引）', TJ_QX),
    ('claim-bg-056-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传居母丧柴毁句（生成时全库引文域查重：'
     '此句既往零入引，本迁移首引；旧传单得与新传异词句并置不合并；'
     '与诗「我心素已閒」并置是读法声明）', JTS_S),
    ('claim-bg-056-person', 'source-xintangshu-wenyi',
     '卷二百二·文艺中·王维传母丧毁几不生句（生成时全库引文域查重：'
     '此句既往零入引，本迁移与旧传句同日首引——两传同事异词，'
     '各自逐字入引、**合而不并**；与诗心之「閒」并置是读法声明）', XTS_S),
]
BG_LINES = {'bg-056-scene': (1, 2, 3, 4), 'bg-056-city': (5, 6),
            'bg-056-world': (7, 8, 9, 10), 'bg-056-person': (11, 12)}
BG_AUDIENCE = {'bg-056-scene': 'PRIMARY', 'bg-056-city': 'JUNIOR',
               'bg-056-world': 'SENIOR', 'bg-056-person': 'JUNIOR'}
BG_TITLES = {'bg-056-scene': '眼前：随山万转的这条水',
             'bg-056-city': '这座城：底注第二行的另一个名字',
             'bg-056-world': '这个天下：青溪在史部是一条贡道',
             'bg-056-person': '这个人：诗里的心素閒，传里的毁骨立'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 38 首·十二句五古 4/2/4/2 形制首用）；史实句均有逐字引证；'
                 '系年第三十二次判决（题证系列第二十状·贡道与撞字）'
                 '「題有谿名，谿在史部止一開道；詩收已矣，已矣在史部只而已矣」——'
                 '通鉴「青谿」全零、「青溪」恰一处=大中十三年（己卯，八五九）窗口'
                 '追书「開青溪道以通群蠻」（闭域+年窗口断言；「初」字追书边界：'
                 '窗口年系入书年非事件年，如实声明不据以系事）；'
                 '通鉴「已矣」恰二皆「而已矣」语气（前字必而机器断言）——'
                 '诗之决志与史之语气撞字两界，在册零入引（V056 泪两界第二形态）；'
                 '「一名「過青谿水作」」纯文本一名式异名注首见（audit 照登硬卡；'
                 '异题快照零命中如实登记不改题）；零标记×75% 正交再验；'
                 '本诗正文第二引上限用满对后来关闭（V018 在先+全库查重）；'
                 '两传母丧异词句并置首引（合而不并首见，V037 合龙反向操作，'
                 'audit 双硬卡）；KNOWN 零如实记录（第十三例，audit 反向断言）；'
                 '零新 source；判例关键语零入引文。' for k in BG}


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
    A("""-- V057：王維《青谿》(work-t300-056) 四层背景（阶段 D 第 38 首·贡道与撞字）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V037、V056 已执行（work-t300-056 与其
--       text-work-t300-056-ws、source-ws-t300-056 是 V018 的行；source-quantangshi-125 是 V035 的行；
--       source-jiutangshu-wenyuan/source-xintangshu-wenyi 是 V016 的行；
--       source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源）。
--       **本迁移零新 source**（audit 断言 SQL 无任何诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v057.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/青谿.txt（「一名「過青谿水作」」一名式异名注首见+四标记全零×75% 正交再验）、
--   舊唐書卷190下（居母丧柴毁句首引+王维段负证）、新唐書卷202（母丧毁几不生句首引+负证）、
--   通鑑卷249（青溪唯一一处开道+大中十三年窗口+「初」字追书边界）+
--   通鑑 75 卷/全唐詩 118 卷存快照负证计数扫描（青谿/青溪/已矣前字/亂石/深松/垂釣/黃花川）+
--   既有迁移引文域逐句查重——传区间归属、首引前提与第二引前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 6 组逐字引用（(claim,source) 主键每对恰一行）+
--   12 行 background_line（十二句形制：scene→1-4 city→5-6 world→7-10 person→11-12，
--   绑 text-work-t300-056-ws 的 12 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有谿名，谿在史部止一開道；詩收已矣，已矣在史部只而已矣」）：
--   * 青谿通鉴全零+青溪恰一处=贡道（闭域+窗口断言）；「初」字追书：窗口年=入书年非事件年；
--   * 已矣撞字两界：通鉴恰二皆「而已矣」（前字必而机器断言），诗之决志在册零入引；
--   * 本诗正文第二引上限用满：V018 一引在先（全库查重恰一处），对后来迁移关闭；
--   * 「一名「過青谿水作」」照登硬卡+异题快照零命中如实登记不改题；
--   * 两传母丧异词句并置首引（合而不并首见，audit 双硬卡）；
--   * 心川对写/閒毁并置均为读法声明，audit 双声明在 BG 文本内；
--   * KNOWN 零如实记录（第十三例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 不才/凝碧/輞川/藍田/茶鐺/尤長五言/以詩名盛/事母崔氏/齋中四物 判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 56，不含 57
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-056-%';             -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-056-ws';  -- 恰 12
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-056-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-056';                                  -- 12（4/2/4/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-056-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-056'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-056';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-056-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-056';   -- 恰 1（V018 旧行，零新源）
-- 回滚: recovery/V057_rollback.sql（按 id 全枚举删除；不动任何共用来源行、不动 V018 的行）
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
    brows = [{'id': k, 'work_id': 'work-t300-056',
              'layer': {'bg-056-scene': 'SCENE', 'bg-056-city': 'CITY',
                        'bg-056-world': 'WORLD', 'bg-056-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（十二句：4/2/4/2） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-056-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 57, 'Wang Wei The Clear Ravine background layers (stage-D poem 38, twelve-line old-style verse shape 4/2/4/2 first use): dating verdict thirty-two, twentieth shape of the title-evidence series -- a ravine name in the title, and in the histories the ravine is only one opened road: the Tongjian scores zero for the xi-ravine graph of the title and exactly one hit for the other ravine graph -- juan 249 under the Dazhong 13 (859) heading, a retrospective "formerly, Wei Gao in Sichuan opened the Qingxi road to reach the barbarian tribes, so they could bring tribute through Shu" (file-closed, year-heading window asserted); a NEW boundary stated honestly: the "formerly" marks a retrospective insertion -- the window year dates the text''s position, not the event (nothing here is dated by it); the poem ends on "it is over" (yi yi) as resolve, while the Tongjian''s two occurrences of yi-yi are both the sentence-final particle "that is all" (machine-asserted: both preceded by er) -- same two characters, two worlds, the second form after V056''s tear-trace split, logged never quoted; first registration of the "also named" plain-text title-variant (a whole alternate title hanging unmarked on the second line of the footnote, third plain-text form after V052/V055, audit hard-assert; the alternate title scores zero inside the snapshot -- logged honestly, the title is not changed); zero-marker-times-75% orthogonality re-verified; the poem body hits its two-use ceiling (V018 first, machine-swept, closure declared); PERSON first-cites both biographies'' mother-mourning sentences side by side -- same event, different words in the two histories, quoted verbatim each and deliberately NOT merged (the reverse operation of V037''s two-source dragon-splice, twin hard-asserts); KNOWN zero honestly recorded (thirteenth instance, audit reverse-asserts); zero new sources; closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 57);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V057 精确回滚：只删 V057 插入的行（id 全枚举）。',
         '-- work-t300-056 本体、其 text_line 12 行与 source-ws-t300-056 都是 V018 的行，绝不删；',
         '-- 全部五个共用 source 行（ws-056/quantangshi-125/jiutangshu-wenyuan/xintangshu-wenyi/',
         '-- zizhi-tongjian-events）均为他迁移所立，零删除（本迁移零新 source）；V057 零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 57;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_L12, WS_L34, WS_L56,
              JTS_S, XTS_S, TJ_QX, Q125, Q125_S]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 「一名」式异名注照登硬卡
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-056-city' and s == 'source-ws-t300-056')
    if '一名「過青谿水作」' not in city_ws:
        bad.append('「一名「過青谿水作」」未逐字入 CITY 引文（一名式异名注首见照登硬卡）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-056-city' and s == 'source-ws-t300-056'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # SCENE 第二引上限声明硬卡
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-056-scene')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054/V055/V056 同款硬卡）')
    scene_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-056-scene')
    if '請留盤石上，垂釣將已矣' not in scene_ex:
        bad.append('末联第二引未逐字入 SCENE 引文')
    # WORLD「初」字追书边界声明硬卡
    w_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-056-world')
    if '入书年' not in w_loc and '非事件年' not in w_loc:
        bad.append('WORLD locator 须含「窗口年=入书年非事件年」追书边界声明')
    # 撞字假命中零入引文
    if '而已矣' in cited:
        bad.append('撞字假命中（而已矣语气）在册不引，不得入引文')
    # 两传并置双硬卡
    p_exs = [ex for c, _, _, ex in CITATIONS if c == 'claim-bg-056-person']
    if len(p_exs) != 2:
        bad.append('PERSON 层须两传两句并列（各恰一引）')
    if '柴毁骨立' not in p_exs[0] or '毀幾不生' not in p_exs[1]:
        bad.append('两传母丧句须各自逐字入引且不合并不改写')
    for c, s, _, ex in CITATIONS:
        if s == 'source-xintangshu-wenyi' and '柴毁' in ex:
            bad.append('两传词异不得互串——新传引文混入旧传字样')
        if s == 'source-jiutangshu-wenyuan' and '毀幾不生' in ex:
            bad.append('两传词异不得互串——旧传引文混入新传字样')
    # 引要素
    w_tj = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-056-world')
    if '開青溪道' not in w_tj:
        bad.append('通鉴侧引文缺「開青溪道」')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-056':
            for w in ('凝碧', '輞川', '藍田', '長齋', '尤長五言', '以詩名盛', '不才', '放還'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山', '隠鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒', '刻碑鳳林山南',
                '仕宦之疾徑', '放田里', '進止仍有風範', '茶鐺', '事母崔氏'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 十二句形制 4/2/4/2
    want = {'bg-056-scene': 4, 'bg-056-city': 2, 'bg-056-world': 4, 'bg-056-person': 2}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('十二句 background_line 必须 4/2/4/2')
    if len(re.findall(r"text-work-t300-056-ws' AS version_id", sql)) != 12:
        bad.append('bg_line INSERT 的 version 行数应为 12')
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
        bad.append("V057 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V057 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-056' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V057 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-056' AS subject_id" in sql:
        bad.append('V057 的 claim 主语应全部是 bg-056-*，work-t300-056 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V057 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '止一開道' not in body_all:
        bad.append('BG/文件头须含「谿在史部止一開道」判决声明')
    if '而已矣' not in ''.join(BG.values()) or '撞字两界' not in body_all:
        bad.append('BG 须含「已矣撞字两界」判决声明（而已矣在册零入引，只许在 BG 论证中出现）')
    if '入书年' not in body_all and '非事件年' not in body_all:
        bad.append('BG/WORLD 须含「初」字追书（窗口年=入书年非事件年）边界声明')
    if '不合并' not in body_all and '合而不并' not in body_all:
        bad.append('BG/PERSON 须含两传「合而不并」声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 12 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（两传王维段双句各就各位）；年标题窗口断言（大中十三年八五九+'
              f'「初」字追书边界声明硬卡——窗口年=入书年非事件年）；'
              f'负证机器复查四层（通鉴青谿全零+青溪恰一=tj-249 開青溪道闭域+已矣恰二前字必而+'
              f'亂石/深松/垂釣/黃花川全零/全唐詩青谿恰二=本篇锚桩+過青谿水零命中+青溪恰十一在册/'
              f'ws 四标记全零+75% 恰一+一名注恰一/两传王段青谿青溪垂釣全零，快照变动即中止）；'
              f'首引前提全库查重硬卡（居母䘮/毀幾不生 两句既往零引）+第二引前提全库查重硬卡'
              f'（本诗正文既往恰一=V018）；一名式异名注照登硬卡；SCENE locator 第二引/上限硬卡；'
              f'撞字假命中零入引断言（而已矣）；两传并置双硬卡+词异不得互串断言；'
              f'判例只引不重开断言（含 V054/V055 新立判例句）；十二句 4/2/4/2 形制断言；'
              f'零 KNOWN 反向断言；零新 source 反向断言（无诗源表新建插入，回滚零删源行）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
