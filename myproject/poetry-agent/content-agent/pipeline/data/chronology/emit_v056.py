#!/usr/bin/env python3
"""阶段 D 第 37 首：生成 V056——李白《怨情》(work-t300-331, V018 已立) 四层背景。

「为什么写」走到「同字两界」的一面：
**诗的题面有「怨」，两部书都查无此怨**——通鉴「怨情」75 卷全零、
全唐詩快照（118 卷存）「怨情」也全零（机器断言：题族在册无册可登，如实）；
**诗里的美人落泪，通鉴的「淚痕」恰一处却不沾她**——光启二年（丙午，八八六）
僖宗幸凤翔夜宿板下、枕王建膝而寝，觉来解御袍赐建曰「以其有淚痕故也」
（文件闭域+年标题窗口机器断言）——**史部的泪痕只沾过一件御袍**。
诗泪无名无人知（「不知心恨誰」），御泪有名无人见：
同一两个字，两个世界，互证其有、不相牵合。零铸造零 relation。

标记体系两个首见：
① **底注空锚片段首见**：「↑ [[全唐詩/卷184#|全唐詩·卷184]]」——
   「#」后直接「|」，锚点片段为空（不完整指向），而本页 Textquality|100%；
   CITY 引文含底注整行原样（audit 硬卡「卷184#|」字样），照登不裁决；
② **底本指向不可核新形态首见**：全唐詩快照缺卷184（快照 118 卷，140–199 区间
   李白诸卷多缺）——底本指向在维基文库可点开、在本快照无法逐字对勘：
   **在册、如实声明、零引用**（不伪造对勘，不因此铸第二证）。

异文侧：页内 {{另}} 恰二（「深坐{{另|顰|蹙}}蛾眉」「但{{另|見|覺}}淚痕濕」），
SCENE 引文双标记原样入引（audit 双硬卡），登记不裁决；
异文支「蹙蛾眉」「覺淚痕」全唐詩快照各零命中（两支在快照内皆孤本，在册）。

同句第二引上限用满第四例：正文 V018 text claim 一引在先（全库查重恰一处=V018），
V056 SCENE 全句二引，locator 明文「两度上限至此用满，此诗正文对后来迁移关闭」。

PERSON 层首引新传李白传末段孙女语：「**辭以孤窮失身，命也，不願更嫁**。」
（生成时全库查重既往零入引；范傳正改葬访后裔段 V042 已引「進止仍有風範」句至
而止，本迁移只取其后相邻一句，前句零重开 audit 硬卡）——
**诗里的女人无名恨誰，传里李白自己的血脉开口说话**：两种女子一虚一实，
并置是读法声明非史实。

四句绝句 1/1/1/1 形制第二次（V053 春曉首见，李白绝句首用）；
**零新 source**（ws-331 系 V018 行、xintangshu-wenyi 系 V016 行、
zizhi-tongjian-events 系 V014/V015 行；卷184 无源行亦不新建）。

用法: python3 -I emit_v056.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/怨情__美人捲珠簾_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS2 = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
TJ256 = pathlib.Path('/tmp/src-dl/tongjian/tj-256.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_TITLE = slice_between(WS, '| title    = [[怨情]]', '| title    = [[怨情]]', 'ws header title(题面零消歧——歧解在页名以首句系之)')
WS_AUTHOR = slice_between(WS, '| author   = 李白', '| author   = 李白', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '| notes    = {{Textquality|100%}}↑ [[全唐詩/卷184#|全唐詩·卷184]]',
                        '全唐詩·卷184]]',
                        'ws 页底注(100%+底本指向空锚片段首见:#后直接|——不完整指向照登不裁决)')
WS_CAT = slice_between(WS, '[[Category:閨怨詩]]', '[[Category:閨怨詩]]', 'ws 分类行(閨怨詩——整理者分类,非史料;V048 分类行判例)')
WS_L1 = slice_between(WS, '美人捲珠簾，深坐{{另|顰|蹙}}蛾眉。', '蹙}}蛾眉。',
                      'ws第1联(卷帘深坐——{{另}}顰/蹙)')
WS_L2 = slice_between(WS, '但{{另|見|覺}}淚痕濕，不知心恨誰。', '心恨誰。',
                      'ws第2联(泪痕湿而恨谁不知——{{另}}見/覺;全诗收在无主语无对象的问上)')
XTS_S = slice_between(XTS2, '告二女，將改妻士族，辭以孤窮失身，命也，不願更嫁。', '不願更嫁。',
                      '新传李白传孙女辞改嫁句(从未入引,PERSON 层首引,生成时全库查重硬卡;V042 前句零重开)')
TJ_LH = slice_between(TJ256, '解御袍賜建曰：「以其有淚痕故也。」', '淚痕故也。」',
                      '通鉴光启二年僖宗解袍赐王建句(泪痕通鉴唯一一处——御袍之泪;窗口断言)')

# ---------- 传区间归属复验（V036 立规） ----------
_xa = XTS2.find('==李白==')
_xm = re.search(r'\n==[^=\n]{1,10}==', XTS2[_xa + 8:])
_seg_x = XTS2[_xa:_xa + 8 + _xm.start()]
_ja = JTS.find('=李白=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
if not (0 <= _xa and '辭以孤窮失身' in _seg_x):
    raise SystemExit('切片越出李白段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 60]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ256, TJ_LH, '光啟二年')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_qtf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt'))}
_allq = ''.join(_qtf.values())
# ① 通鉴：怨情全零；泪痕恰一且闭域 tj-256；诗语另三词全零
if _alltj.count('怨情') != 0:
    raise SystemExit('通鉴「怨情」不再全零——题面无档论断失效')
_lh = {n: t.count('淚痕') for n, t in _tjf.items() if '淚痕' in t}
if _lh != {'tj-256.txt': 1}:
    raise SystemExit(f'通鉴「淚痕」不是恰一处（实 {_lh}）——御袍唯一泪论断须重估')
for _w in ('蛾眉', '珠簾', '深坐'):
    if _alltj.count(_w) != 0:
        raise SystemExit(f'通鉴「{_w}」不再全零——诗语史部不接的判决失效，须重读')
# ② 全唐詩快照：怨情/捲珠簾/心恨全零（缺卷如实）；淚痕恰八在册；卷184 不在快照
if _allq.count('怨情') != 0 or _allq.count('捲珠簾') != 0 or _allq.count('心恨') != 0:
    raise SystemExit('全唐詩快照「怨情/捲珠簾/心恨」不再全零——题族与诗语无册论断失效')
if _allq.count('淚痕') != 8:
    raise SystemExit(f'全唐詩「淚痕」不再是 8 处（实 {_allq.count("淚痕")}）——他人泪句在册册数须重估')
if _allq.count('蹙蛾眉') != 0 or _allq.count('覺淚痕') != 0:
    raise SystemExit('异文支「蹙蛾眉/覺淚痕」在快照内不再零命中——孤本在册论断失效')
if 'vol184.txt' in _qtf:
    raise SystemExit('vol184 进了快照——底本指向不可核新形态前提失效，须补对勘重设计')
# ③ ws：{{另}} 恰二、100% 恰一、空锚片段恰一、其余标记全零
if WS.count('{{另') != 2 or WS.count('{{别') or WS.count('{{*') or WS.count('<ref'):
    raise SystemExit('ws 页标记计数变了（{{另}}2 余全零）——双标记照登断言须重估')
if WS.count('{{Textquality|100%}}') != 1 or WS.count('卷184#|') != 1:
    raise SystemExit('ws 页 100%/空锚片段结构变了——底注空锚首见断言失效')
# ④ 传区间与首引前提
for _w in ('怨情', '淚痕', '蛾眉', '珠簾'):
    if _w in _seg_j or _w in _seg_x:
        raise SystemExit(f'「{_w}」落在李白传区间——传不系怨负证失效，须重读原文')
if JTS.count('辭以孤窮失身') != 0:
    raise SystemExit('旧传竟有孙女段——两支结构论断失效，须重读')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
_prev_s = [f.name for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V056')
           for _ln in f.read_text(encoding='utf-8').splitlines()
           if 'evidence_excerpt' in _ln and '辭以孤窮失身' in _ln]
if _prev_s:
    raise SystemExit(f'「辭以孤窮失身」已在 {_prev_s} 入引——首引前提失效，PERSON 层须重设计')
_prev_t = [f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V056')
           for _ln in f.read_text(encoding='utf-8').splitlines()
           if 'evidence_excerpt' in _ln and '不知心恨誰' in _ln]
if _prev_t != ['V018']:
    raise SystemExit(f'本诗正文既往引文域不是恰一处 V018（实 {_prev_t}）——第二引上限论断须重估')

BG = {
    'bg-331-scene': (
        '四句是一间深阁：美人卷起珠帘，深深独坐着蹙起蛾眉'
        '（「美人捲珠簾，深坐{{另|顰|蹙}}蛾眉」——顰/蹙两支照登不裁决）；'
        '只见泪痕湿了面庞，心里恨的是谁却没有人知道'
        '（「但{{另|見|覺}}淚痕濕，不知心恨誰」——見/覺两支照登不裁决）。'
        '全诗无年、无地、无姓名、无对象——连恨都恨在不具名的人身上；'
        '此诗正文系**第二引**：V018 text claim 已一引在先（全库查重恰一处），'
        '两度上限至此用满，此诗正文对后来迁移关闭。恨誰之问是页上原文，'
        '「为谁而恨」的任何答案都是读法，不是史实。'),
    'bg-331-city': (
        '这条城的档案先登记底注本身：「{{Textquality|100%}}↑ '
        '[[全唐詩/卷184#|全唐詩·卷184]]」——「#」后直接「|」，'
        '**底本指向的空锚片段首见**（不完整指向，页面却自评 100%；'
        'audit 硬卡「卷184#|」字样照登不裁决；完备度与完备的指向是两回事，'
        'V054/V055 的正交纪律在「指向」这一维的延伸）。'
        '**底本指向不可核新形态首见**：全唐詩快照缺卷184（140–199 区间的'
        '李白诸卷多缺）——指向在维基文库可点开、在本快照无法逐字对勘：'
        '如实登记、零引用、不伪造对勘、不因此铸第二证。'
        '分类行「閨怨詩」为整理者动作：照登+非史料声明+不升格（V048 判例）。'
        '题族亦无册可登：全唐詩快照「怨情」「捲珠簾」「心恨」全零（机器断言）——'
        '异文两支「蹙蛾眉」「覺淚痕」快照内亦零命中：这支诗在存卷里连旁证都没有，'
        '在册如实；他人「淚痕」全唐詩 8 处（各是各诗，在册不引不牵合）。'),
    'bg-331-world': (
        '诗的题面有「怨」，两部书都查无此怨：通鉴「怨情」75 卷全零、'
        '全唐詩快照「怨情」亦全零（机器断言）。\n'
        '诗里的美人落泪；通鉴「淚痕」75 卷**恰一处**（文件闭域+年标题窗口'
        '机器断言）——光启二年（丙午，八八六）广明之乱后僖宗幸凤翔，'
        '夜宿板下、枕王建膝而寝，觉来「解御袍賜建曰：『以其有淚痕故也。』」——'
        '**史部七十多卷里的泪痕，只沾过一件御袍**（天子的泪）。'
        '同一两个字，两个世界：诗的泪无名无人知（「不知心恨誰」），'
        '御泪有名无人见（君臣夜宿板下）——互证其有、不相牵合。\n'
        '诗语「蛾眉」「珠簾」「深坐」通鉴亦全零（机器断言）——'
        '深阁的语言进不了史部。**怨在两部皆无档，泪在史部只一袍**；'
        '本层零铸造零 relation。'),
    'bg-331-person': (
        '诗里的女人至终没有名字；新传倒让李白家里两个真实的女人开了口：'
        '范傳正改葬青山、访其后裔，只有两个孙女嫁为民妻，官家要把她们改嫁士族，'
        '「**辭以孤窮失身，命也，不願更嫁**。」（生成时全库查重：此句既往'
        '零入引，本迁移首引；改葬访后裔段前句 V042 已引「進止仍有風範」'
        '至而止，本迁移只取其後相邻一句，前句零重开）。\n'
        '把两处并置看：诗的「不知心恨誰」是不具名女子的无主之恨，'
        '传的「不願更嫁」是李白血脉有名有姓的自我主张——**两种女子，'
        '一虚一实，一在诗一在传**（读法声明，非史实；传中女子非诗中人，'
        '绝不牵合）。李白传其余已用句（山東人家世 V016/V032 两度已满零重开/'
        '謫仙人/脱靴/沈香亭/賜金放還/宮錦袍/夜郎/青山）一个不重开；'
        '两传李白段「怨情」「淚痕」「蛾眉」「珠簾」全零（机器断言）——'
        '传写其人，不提这四字里的任何一个。'),
}
CLAIMS = {
    'claim-bg-331-scene': (
        'FACT', 'LIKELY',
        '四句全诗本文（ws 页 {{另}} 恰二、余标记全零、Textquality 100%；'
        '顰/蹙、見/覺两支照登不裁决，双标记字样入 SCENE 引文 audit 双硬卡）；'
        '全句第二引：正文 V018 text claim 一引在先（生成时全库查重恰一处），'
        '两度上限至此用满、此诗正文对后来迁移关闭（audit 硬卡）；'
        '「为谁而恨」的任何回答系读法非史实。'),
    'claim-bg-331-city': (
        'FACT', 'LIKELY',
        '底注空锚片段首见：底本指向「[[全唐詩/卷184#|全唐詩·卷184]]」#后直接|'
        '（不完整指向而页面自评 100%——指向完备度与录入完备度两回事，'
        'V054/V055 正交纪律的延伸，audit 硬卡「卷184#|」照登）；'
        '底本指向不可核新形态：全唐詩快照缺卷184（机器断言 vol184 不在册）——'
        '如实登记零引用不伪造对勘；分类行照登+非史料声明+不升格；'
        '快照「怨情/捲珠簾/心恨」全零（题族无册如实）、异文两支快照零命中'
        '（孤本在册）、他人淚痕 8 处不引；题无档而诗无时→零铸造零 relation。'),
    'claim-bg-331-world': (
        'FACT', 'LIKELY',
        '怨在两部皆无档：通鉴「怨情」全零+全唐詩快照「怨情」全零（机器断言）；'
        '泪在史部只一袍：通鉴「淚痕」恰 1 处=tj-256 光启二年（丙午，八八六）'
        '僖宗「解御袍賜建曰：『以其有淚痕故也』」（文件闭域+年标题窗口断言）——'
        '诗的泪与史的泪同字两界，互证其有不相牵合；诗语蛾眉/珠簾/深坐'
        '通鉴全零；certainty 不覆盖任何系年，诗 time.span/event.name/'
        'written_during 零铸造零 relation。'),
    'claim-bg-331-person': (
        'FACT', 'LIKELY',
        '新传孙女辞改嫁句首引（生成时全库引文域查重：辭以孤窮失身既往零命中，'
        'audit 硬卡；旧传无此段=新传单得，机器断言）；V042 已引前句'
        '「進止仍有風範」零重开（audit 硬卡前句字样不入引文）；'
        '两种女子一虚一实并置为读法声明非史实（传中女子非诗中人）；'
        '李白其余已用判例句零重开（山東人两度已满在册）；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-331-scene', 'source-ws-t300-331',
     '页面 怨情 (美人捲珠簾)（header author+两联四句，三段以「……」相連——'
     '{{另}}×2（顰/蹙、見/覺）原样入引 audit 双硬卡；全句**第二引**：'
     '正文 V018 text claim 一引在先（生成时全库查重恰一处），'
     '**两度上限至此用满，此诗正文对后来迁移关闭**；页 {{别}}/{{*}}/<ref> 全零）',
     join(WS_AUTHOR, WS_L1, WS_L2)),
    ('claim-bg-331-city', 'source-ws-t300-331',
     '页面 怨情 (美人捲珠簾)（header title+页底注+分类行三段并收——'
     '底本指向「全唐詩/卷184#」系**空锚片段首见**（audit 硬卡「卷184#|」字样；'
     '快照缺卷184 不可对勘：如实零引用）；「閨怨詩」分类系整理者动作：'
     '非史料声明、不升格；题面零消歧、歧解在页名以首句系之）',
     join(WS_TITLE, WS_NOTE, WS_CAT)),
    ('claim-bg-331-world', 'source-zizhi-tongjian-events',
     '卷二百五十六·光启二年（丙午，八八六）僖宗幸凤翔宿板下解袍赐王建段'
     '（**通鉴 75 卷「淚痕」唯一一处**：文件闭域+年标题窗口机器断言——'
     '史部之泪只沾御袍；怨情/蛾眉/珠簾/深坐通鉴全零在册）', TJ_LH),
    ('claim-bg-331-person', 'source-xintangshu-wenyi',
     '卷二百二·文艺中·李白传范傳正访后裔段孙女辞改嫁句（生成时全库引文域查重：'
     '此句既往零入引，本迁移首引；旧传无此段新传单得；前句「進止仍有風範」'
     'V042 已引零重开；与诗中无名恨誰女子并置是读法声明——传中女子非诗中人）',
     XTS_S),
]
BG_LINES = {'bg-331-scene': (1,), 'bg-331-city': (2,),
            'bg-331-world': (3,), 'bg-331-person': (4,)}
BG_AUDIENCE = {'bg-331-scene': 'PRIMARY', 'bg-331-city': 'JUNIOR',
               'bg-331-world': 'SENIOR', 'bg-331-person': 'JUNIOR'}
BG_TITLES = {'bg-331-scene': '眼前：恨在不具名的人身上',
             'bg-331-city': '这座城：底注里一个空的锚',
             'bg-331-world': '这个天下：史部的泪只沾过一件御袍',
             'bg-331-person': '这个人：诗里的无名女子与传里的孙女'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 37 首·四句绝句 1/1/1/1 第二次）；史实句均有逐字引证；'
                 '系年第三十一次判决（题证系列第十九状·同字两界）'
                 '「題有怨名，怨在兩部皆無檔；詩有淚字，淚在通鑑只一袍」——'
                 '通鉴「怨情」全零+全唐詩快照「怨情」全零（机器断言）；'
                 '通鉴「淚痕」恰一处=光启二年（丙午，八八六）僖宗解御袍赐王建'
                 '「以其有淚痕故也」（闭域+年窗口断言）——诗的泪与史的泪同字两界'
                 '互证其有不相牵合→time.span/event.name/written_during 全缺席、零 relation；'
                 '底注空锚片段首见（卷184# 后直接|，不完整指向而页自评 100%，audit 硬卡）；'
                 '底本指向不可核新形态首见（快照缺卷184：如实登记零引用不伪造对勘）；'
                 '此诗正文第二引上限用满对后来关闭（V018 在先+全库查重）；'
                 '双 {{另}}（顰/蹙、見/覺）照登双硬卡；异文两支快照零命中在册；'
                 '新传孙女辞改嫁句首引（全库查重既往零引；V042 前句零重开）；'
                 'KNOWN 零如实记录（第十二例，audit 反向断言）；零新 source；'
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
    A("""-- V056：李白《怨情》(work-t300-331) 四层背景（阶段 D 第 37 首·同字两界）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V042、V055 已执行（work-t300-331 与其
--       text-work-t300-331-ws、source-ws-t300-331 是 V018 的行；
--       source-xintangshu-wenyi 是 V016 的行；source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源）。
--       **本迁移零新 source**（audit 断言 SQL 无任何诗源表新建插入语句；卷184 无源行亦不新建）。
--
-- 数据源（可复现）：emit_v056.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/怨情__美人捲珠簾_.txt（底注空锚片段首见+{{另}}×2 照登+页名首句消歧）、
--   新唐書卷202（孙女辞改嫁句首引+李白段负证）、舊唐書卷190下（李白段负证+无此段断言）、
--   通鑑卷256（淚痕唯一一处+光啟二年窗口）+ 通鑑 75 卷/全唐詩 118 卷存快照负证计数扫描+
--   既有迁移引文域逐句查重——传区间归属、怨情/淚痕/蛾眉/珠簾/深坐全部计数、
--   年标题窗口、vol184 不在快照、首引前提与第二引前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 4 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 行 background_line（四句形制 1/1/1/1：scene→1 city→2 world→3 person→4，
--   绑 text-work-t300-331-ws 的 4 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有怨名，怨在兩部皆無檔；詩有淚字，淚在通鑑只一袍」）：
--   * 怨情通鉴全零+全唐詩快照全零（题面无档，机器断言）；淚痕通鉴恰一=御袍之泪（闭域+窗口断言）；
--   * 此诗正文第二引上限用满：V018 一引在先（全库查重恰一处），对后来迁移关闭；
--   * 底注空锚片段首见+底本指向不可核新形态：快照缺卷184——如实登记、零引用、不伪造对勘；
--   * 异文两支（蹙蛾眉/覺淚痕）快照内零命中（孤本在册）；他人淚痕 8 处不引；
--   * 新传孙女句首引（全库查重既往零引）；V042「進止仍有風範」前句零重开（audit 硬卡）；
--   * 两种女子一虚一实、泪两界均为读法声明，audit 双声明在 BG 文本内；
--   * KNOWN 零如实记录（第十二例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 山東人（V016/V032 两度已满）/謫仙人/脫靴/沈香亭/賜金放還/宮錦袍/夜郎/青山 判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 55，不含 56
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-331-%';             -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-331-ws';  -- 恰 4
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-331-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-331';                                  -- 4（1/1/1/1）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-331-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-331'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-331';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-331-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-331';   -- 恰 1（V018 旧行，零新源）
-- 回滚: recovery/V056_rollback.sql（按 id 全枚举删除；不动任何共用来源行、不动 V018 的行）
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
    brows = [{'id': k, 'work_id': 'work-t300-331',
              'layer': {'bg-331-scene': 'SCENE', 'bg-331-city': 'CITY',
                        'bg-331-world': 'WORLD', 'bg-331-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（四句：1/1/1/1） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-331-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 56, 'Li Bai Grief background layers (stage-D poem 37, four-line jueju shape 1/1/1/1 second use after V053, first for Li Bai): dating verdict thirty-one, nineteenth shape of the title-evidence series -- the same words, two worlds: the title''s word "grief" scores zero in the Tongjian and zero across the surviving 118 juan of the Quan Tangshi snapshot (machine-asserted: no dossier for the title, registered honestly), while the poem''s word for tear-trace appears exactly once in 75 Tongjian juan -- Guangqi 2 (886), Emperor Xizong fleeing to Fengxiang, sleeping with his head on Wang Jian''s lap and giving away his robe "because it bears tear-traces" (file-closed, year-heading window asserted): the histories'' single tear-trace stains only an imperial robe; the poem''s tear is nameless and unknown to whom -- same two characters, two worlds, mutually attested yet never conflated; zero forging, zero relation; first appearance of an empty-anchor fragment in a base-pointer (Quan Tangshi juan 184 followed by bare hash then pipe: an incomplete pointer on a page self-rated 100% -- pointer completeness is a third orthogonal dimension, audit hard-assert); first "pointer unverifiable" form: the snapshot lacks juan 184, so the pointer is neither faked into a second witness nor silently dropped -- logged, zero-cited; the poem body hits its two-use ceiling (V018 first, machine-swept) and closes for future migrations; both {{另}} pairs (pin/cu, jian/jue) transcribed verbatim with twin hard-asserts; both variant branches score zero inside the snapshot (register: orphan witnesses); PERSON first-cites the New History''s granddaughters refusing remarriage ("pleading poverty... fate; we decline another marriage", sweep proves zero prior hits; V042''s adjacent sentence stays closed); KNOWN zero honestly recorded (twelfth instance, audit reverse-asserts); zero new sources; closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 56);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V056 精确回滚：只删 V056 插入的行（id 全枚举）。',
         '-- work-t300-331 本体、其 text_line 4 行与 source-ws-t300-331 都是 V018 的行，绝不删；',
         '-- 全部三个共用 source 行（ws-331/xintangshu-wenyuan/',
         '-- zizhi-tongjian-events）均为他迁移所立，零删除（本迁移零新 source；卷184 无源行）；V056 零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 56;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_TITLE, WS_AUTHOR, WS_NOTE, WS_CAT, WS_L1, WS_L2, XTS_S, TJ_LH]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 空锚片段照登硬卡
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-331-city' and s == 'source-ws-t300-331')
    if '全唐詩/卷184#|' not in city_ws:
        bad.append('空锚片段「卷184#|」未逐字入 CITY 引文（底注空锚首见照登硬卡）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-331-city' and s == 'source-ws-t300-331'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # SCENE 双标记照登双硬卡 + 第二引上限声明
    scene_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-331-scene')
    if '{{另|顰|蹙}}' not in scene_ex or '{{另|見|覺}}' not in scene_ex:
        bad.append('双 {{另}} 未逐字入 SCENE 引文（顰/蹙+見/覺 双硬卡）')
    s_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-331-scene')
    if '第二引' not in s_loc or '上限' not in s_loc:
        bad.append('SCENE locator 须含「第二引/上限」声明（V050/V054/V055 同款硬卡）')
    # V042 前句零重开
    if '進止仍有風範' in cited:
        bad.append('V042 已引前句「進止仍有風範」零重开——不得入本迁移引文')
    # 泪两界要素
    w_tj = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-331-world')
    if '以其有淚痕故也' not in w_tj:
        bad.append('通鉴侧引文缺「以其有淚痕故也」')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-331':
            for w in ('謫仙', '脫靴', '沈香亭', '賜金放還', '宮錦袍', '夜郎', '青山', '山東人'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山', '隠鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒', '刻碑鳳林山南',
                '仕宦之疾徑', '放田里', '進止仍有風範'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 四句形制 1/1/1/1
    want = {'bg-331-scene': 1, 'bg-331-city': 1, 'bg-331-world': 1, 'bg-331-person': 1}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('四句 background_line 必须 1/1/1/1')
    if len(re.findall(r"text-work-t300-331-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    # 零新 source 断言
    if 'INSERT INTO poetry_source' in sql:
        bad.append('本迁移有意零新 source，SQL 出现了诗源表新建插入语句')
    if 'source-quantangshi-184' in sql:
        bad.append('卷184 在册不引也不建源行——SQL 出现了卷184 源 id')
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
        bad.append("V056 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V056 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-331' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V056 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-331' AS subject_id" in sql:
        bad.append('V056 的 claim 主语应全部是 bg-331-*，work-t300-331 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V056 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '只一袍' not in body_all and '只沾' not in body_all:
        bad.append('BG/文件头须含「淚在史部只一袍」判决声明')
    if '两界' not in body_all:
        bad.append('BG/文件头须含「同字两界」判决声明')
    if '不可核' not in body_all:
        bad.append('BG/CITY 须含底本指向「不可核」新形态声明')
    if '空锚' not in body_all:
        bad.append('BG/CITY 须含「空锚片段」首见声明')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 8 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（李白段，新传单得旧传无此段）；年标题窗口断言（光啟二年八八六）；'
              f'负证机器复查四层（通鉴怨情/蛾眉/珠簾/深坐全零+淚痕恰一=tj-256 闭域/'
              f'全唐詩快照怨情/捲珠簾/心恨全零+淚痕恰八在册+异文两支零命中+vol184 不在快照/'
              f'ws {{另}}2 余零+100% 恰一+卷184#| 恰一/两传李段怨情淚痕蛾眉珠簾全零，快照变动即中止）；'
              f'首引前提全库查重硬卡（辭以孤窮失身既往零引）+第二引前提全库查重硬卡'
              f'（本诗正文既往恰一=V018）；空锚片段照登硬卡；双 {{另}} 照登双硬卡；'
              f'SCENE locator 第二引/上限硬卡；V042 前句零重开硬卡；卷184 零建源断言；'
              f'判例只引不重开断言（含山東人两度已满）；四句 1/1/1/1 形制断言；'
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
