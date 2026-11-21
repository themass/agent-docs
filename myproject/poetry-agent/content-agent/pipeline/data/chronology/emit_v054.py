#!/usr/bin/env python3
"""阶段 D 第 35 首：生成 V054——王維《終南山》(work-t300-137, V018 已立) 四层背景。

「为什么写」走到与 V050 恰好相反的一面：
**V050 的山在史部零档案（山无史山）；这座山在史部档案多到满出来——
通鉴「終南山」恰五处，处处是皇家的事**：武德八年（乙酉，625）高祖
「營太和宮於終南山」、武德九年（丙戌，626）玄武门余波「萬徹與數十騎亡入終南山」、
贞观二十一年（丁未，647）太宗「命修終南山太和廢宮為翠微宮」、
景龙元年（丁未，七零七年）太子重俊兵败「以百騎走終南山……為左右所殺」、
景云二年（辛亥，711）卢藏用指此山「此乃仕宦之疾徑耳」——
五处五个年标题窗口（机器断言），从 625 排到 711，全是皇帝、太子、隐宦。
**而这首诗里没有一个字带时间**：太乙、天都、海隅、白云、青霭、分野、阴晴——
全山全景、无一时一事。山有史，史是皇家事；诗无时，无时亦无年——
**山的全部档案没有一条属于这首诗**（V050 山无史山的镜像：山有史史非诗史）。
零铸造零 relation。

标记体系两个首见（异文照登纪律最密的一页）：
① **{{*}} 题异注首见 section 字段**：「{{*|題下一有「行」字，一作「終山行」}}」——
   题面三个名字（終南山/終南山行/終山行）并挂不裁决，照登硬卡；
② **同行相邻双 {{另}} 首见**：「連{{另|山|天}}{{另|接|到}}海隅」——
   两处异文彼此相邻，**组合起来是两种整句读法**：連山接/連山到/連天接/連天到，
   四种组合照登不裁决（audit 硬卡双标记字样连续入 SCENE 引文）。
   页内 {{另}} 恰四处（+众/聚、水/浦）、{{*}} 恰一处，全页共五枚标记。

**诚实边界修正（V048 判例的边界澄清）**：本页 {{Textquality|100%}} 却带五枚标记——
完备度与异文数**正交**：V048 的「100% 与零标记互证」只适用于零标记页，
「100%」说的是底本录入完备、不是「没有异文」。本迁移如实登记这条修正（CITY 层）。

同句第二引上限用满第二例（V050 刻碑凤林山南之后）：
「此乃仕宦之疾徑耳」全句 V047 已随卢藏用故事一引，本迁移取子句二引——
locator 明文「两度上限至此用满，此句对后来迁移关闭」，audit 硬卡
locator 含「第二引/上限」+生成时全库引文域查重（既往恰一处=V047）。

断词假命中登记第二例（V053 雞香積之后）：通鉴「疾徑」两处——
tj-210 是典（仕宦之疾徑），tj-251 是断词（濠州贼将王弘立「引兵數萬疾徑奄至」：
疾=疾速、徑=取道，撞出「疾徑」二字）；机器断言第二处必在 tj-251 且后字必「奄」，
**假命中在册、零入引文**。
全唐詩侧「終南山」恰 25 处分布 13 卷=诗世界的山名题族（他人各是各诗，在册不引）；
**卷784 两处命中后字必「翁」**——「終南山翁」是作者名不是诗题（机器断言在册）。

负证机器复查四层（生成时断言，快照变动即中止）：
① 通鉴：終南山 恰 5={191:2, 198:1, 208:1, 210:1} 文件闭域+五年标题窗口；
   疾徑 恰二且第二处必落 tj-251 后字「奄」（断词假命中）；
② 全唐詩：終南山 恰 25、卷126 恰 3（锚点含两次+桩一次）、卷784 两处后字必「翁」；
③ ws：{{另}} 恰四、{{*}} 恰一、相邻双标记恰一、100% 恰一（五标记与 100% 正交在册）；
④ 传区间：两传王维段「終南山」「疾徑」全零；旧传全卷疾徑零；
   「茶鐺」句既往引文域零命中（首引前提，生成时全库查重硬卡）。

八句律詩 2/2/2/2 形制；**零新 source**（ws-137/quantangshi-126/
jiutangshu-wenyuan/zizhi-tongjian-events 四源行均已立）。

用法: python3 -I emit_v054.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/終南山__王維_.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS2 = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
V126 = pathlib.Path('/tmp/src-dl/quantangshi/vol126.txt').read_text(encoding='utf-8')
V784 = pathlib.Path('/tmp/src-dl/quantangshi/vol784.txt').read_text(encoding='utf-8')
TJ191 = pathlib.Path('/tmp/src-dl/tongjian/tj-191.txt').read_text(encoding='utf-8')
TJ198 = pathlib.Path('/tmp/src-dl/tongjian/tj-198.txt').read_text(encoding='utf-8')
TJ208 = pathlib.Path('/tmp/src-dl/tongjian/tj-208.txt').read_text(encoding='utf-8')
TJ210 = pathlib.Path('/tmp/src-dl/tongjian/tj-210.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_SECTION = slice_between(WS, '| section  ={{*|題下一有「行」字，一作「終山行」}}', '一作「終山行」}}',
                           'ws section 字段 {{*}} 题异注(题下有一行字/一作終山行——{{*}} 题异注首见 section 字段,三题面并挂不裁决)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', '| author   = 王維', 'ws header author(署名直证)')
WS_NOTE = slice_between(WS, '| notes    = {{Textquality|100%}}↑ [[全唐詩/卷126#終南山|全唐詩·卷126]]', '全唐詩·卷126]]',
                        'ws 页底注(100%+底本指向——100% 与五枚标记正交:完备度非异文数,本页如实修正 V048 判例边界)')
WS_CAT = slice_between(WS, '[[Category:五言律詩]]', '[[Category:五言律詩]]', 'ws 分类行(五律——整理者分类,非史料;V048 分类行判例)')
WS_L1 = slice_between(WS, '太乙近天都，連{{另|山|天}}{{另|接|到}}海隅。', '海隅。',
                      'ws第1联(太乙/天都/海隅——{{另}}×2 相邻:連山接/連天到四种组合两种整读,照登不裁决)')
WS_L2 = slice_between(WS, '白雲迴望合，青靄入看無。', '入看無。', 'ws第2联(白云回望合/青霭入看无——全山无时)')
WS_L3 = slice_between(WS, '分野中峰變，陰晴{{另|眾|聚}}壑殊。', '壑殊。', 'ws第3联(分野/阴晴——{{另}}众/聚)')
WS_L4 = slice_between(WS, '欲投人處宿，隔{{另|水|浦}}問樵夫。', '問樵夫。',
                      'ws第4联(投宿问樵夫收束——全山全景里唯一的小动作;{{另}}水/浦)')
JTS_C = slice_between(JTS, '齋中無所有，唯茶鐺、藥臼、經案、繩牀而已。', '繩牀而已。',
                      '旧传斋中四物句(茶铛/药臼/经案/绳床——从未入引,PERSON 层首引,生成时全库查重硬卡)')
TJ_TAIHE = slice_between(TJ191, '甲申，上幸鄠縣，校獵於甘谷，營太和宮於終南山；丙戌，還宮。', '丙戌，還宮。',
                         '通鉴武德八年高祖营太和宫句(皇家事一——625 窗口断言)')
TJ_WANCHE = slice_between(TJ191, '萬徹與數十騎亡入終南山。', '亡入終南山。',
                          '通鉴武德九年冯万彻亡入山句(皇家事二·玄武门余波——626 窗口断言)')
TJ_CUIWEI = slice_between(TJ198, '命修終南山太和廢宮為翠微宮', '為翠微宮',
                          '通鉴贞观二十一年修翠微宫句(皇家事三——647 窗口断言)')
TJ_TAIZI = slice_between(TJ208, '太子以百騎走終南山，至鄠西，能屬者才數人，憩於林下，為左右所殺。', '為左右所殺。',
                         '通鉴景龙元年太子重俊走山被杀句(皇家事四——七零七年「零」字年号窗口断言)')
TJ_JIJING = slice_between(TJ210, '承禎曰：「以愚觀之，此乃仕宦之疾徑耳！」', '疾徑耳！」',
                          '通鉴景云二年司马承祯疾径句(皇家事五——711 窗口;V047 全句一引、本迁移子句二引上限用满)')
Q126 = slice_between(V126, '==[[終南山 (王維)|終南山]]==', '終南山 (王維)|終南山]]==', '卷126 本篇消歧篇题锚点(王维集标准锚点+桩结构,对照春晓内联)')
Q126_S = slice_between(V126, '{{:終南山 (王維)}}', '{{:終南山 (王維)}}', '卷126 本篇转引桩')

# ---------- 传区间归属复验（V036 立规） ----------
_ja = JTS.find('=王維=')
_jm = re.search(r'\n=[^=\n]{1,10}=', JTS[_ja + 6:])
_seg_j = JTS[_ja:_ja + 6 + _jm.start()]
_xa = XTS2.find('==王維==')
_seg_x = XTS2[_xa:XTS2.find('==鄭虔==')]
if not (0 <= _ja and '茶鐺' in _seg_j):
    raise SystemExit('切片越出王维段——修订后重生成')

# ---------- 通鉴年标题窗口断言（V034 立规；五扇窗口） ----------
_HEAD = re.compile(r'[^\n]*（[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]，公元[〇零一二三四五六七八九十百千]+年）[=\n]')

def _window(txt, needle, want):
    i = txt.find(needle)
    hs = [m.start() for m in _HEAD.finditer(txt)]
    prev = [h for h in hs if h < i]
    if not prev or want not in txt[prev[-1]:prev[-1] + 60]:
        raise SystemExit(f'摘句前的年标题不是{want}——窗口断言失效，判决须重估')

_window(TJ191, TJ_TAIHE, '武德八年')
_window(TJ191, TJ_WANCHE, '武德九年')
_window(TJ198, TJ_CUIWEI, '貞觀二十一年')
_window(TJ208, TJ_TAIZI, '景龍元年')
_window(TJ210, TJ_JIJING, '景雲二年')

# ---------- 负证机器复查（V042 立规：负证自身也要被机器检验） ----------
_tj = pathlib.Path('/tmp/src-dl/tongjian')
_qts = pathlib.Path('/tmp/src-dl/quantangshi')
_tjf = {f.name: f.read_text(encoding='utf-8') for f in sorted(_tj.glob('tj-*.txt'))}
_alltj = ''.join(_tjf.values())
_allq = ''.join(f.read_text(encoding='utf-8') for f in sorted(_qts.glob('vol*.txt')))
# ① 通鉴：终南山恰 5=四卷闭域；疾径恰二且第二处=断词假命中
_xn = {n: t.count('終南山') for n, t in _tjf.items() if '終南山' in t}
if _xn != {'tj-191.txt': 2, 'tj-198.txt': 1, 'tj-208.txt': 1, 'tj-210.txt': 1}:
    raise SystemExit(f'通鉴「終南山」不是四卷恰 5 处（实 {_xn}）——皇家山档案论断须重估')
_jj = {n: t.count('疾徑') for n, t in _tjf.items() if '疾徑' in t}
if _jj != {'tj-210.txt': 1, 'tj-251.txt': 1}:
    raise SystemExit(f'通鉴「疾徑」不是恰二处（实 {_jj}）——断词假命中论断须重估')
_t251 = _tjf['tj-251.txt']
_i251 = _t251.find('疾徑')
if _t251[_i251 + 2] != '奄':
    raise SystemExit('tj-251「疾徑」后字不是「奄」——断词假命中（疾速取道）结构变了')
# ② 全唐詩：恰 25；卷126 恰三（锚点含二+桩一）；卷784 两处后字必「翁」
if _allq.count('終南山') != 25:
    raise SystemExit(f'全唐詩「終南山」计数不是 25（实 {_allq.count("終南山")}）——题族册数论断须重估')
if V126.count('終南山') != 3:
    raise SystemExit(f'卷126「終南山」不是恰 3（实 {V126.count("終南山")}）——本篇锚点+桩结构断言失效')
if V126.count('==[[終南山 (王維)|終南山]]==') != 1 or V126.count('{{:終南山 (王維)}}') != 1:
    raise SystemExit('本篇篇题锚点结构破坏：終南山 (王維)')
_h784 = [i for i in range(len(V784)) if V784.startswith('終南山', i)]
if len(_h784) != 2 or any(V784[i + 3] != '翁' for i in _h784):
    raise SystemExit('卷784「終南山」两处后字不是「翁」——作者名假命中登记须重做')
# ③ ws：{{另}} 恰四、{{*}} 恰一、相邻双标记恰一、100% 恰一
if WS.count('{{另') != 4 or WS.count('{{*') != 1 or WS.count('{{别') != 0:
    raise SystemExit('ws 页标记计数变了（{{另}}4/{{*}}1/{{别}}0）——五标记照登断言须重估')
if WS.count('連{{另|山|天}}{{另|接|到}}海隅') != 1:
    raise SystemExit('相邻双标记结构破坏——同行双 {{另}} 首见断言失效')
if WS.count('{{Textquality|100%}}') != 1:
    raise SystemExit('ws 页 100% 不在场——正交修正断言须重估')
# ④ 传区间与首引前提
for _w in ('終南山', '疾徑'):
    if _w in _seg_j or _w in _seg_x:
        raise SystemExit(f'「{_w}」落在王维传区间——山史非诗史负证失效，须重读原文')
POETRY = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry')
_prev_c = [f.name for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V054')
           for _ln in f.read_text(encoding='utf-8').splitlines()
           if 'evidence_excerpt' in _ln and '茶鐺' in _ln]
if _prev_c:
    raise SystemExit(f'「茶鐺」句已在 {_prev_c} 入引——首引前提失效，PERSON 层须重设计')
_prev_j = [f.name.split('__')[0] for f in sorted(POETRY.glob('V0*.sql')) if not f.name.startswith('V054')
           for _ln in f.read_text(encoding='utf-8').splitlines()
           if 'evidence_excerpt' in _ln and '仕宦之疾徑' in _ln]
if _prev_j != ['V047']:
    raise SystemExit(f'「仕宦之疾徑」既往引文域不是恰一处 V047（实 {_prev_j}）——第二引上限论断须重估')

BG = {
    'bg-137-scene': (
        '八句是一整座山的全景，没有一个字带时间：远望太乙峰逼近天帝之都，'
        '山势连绵接向海隅（「太乙近天都，連{{另|山|天}}{{另|接|到}}海隅」——'
        '此联两处 {{另}} 彼此相邻：山/天、接/到，两两组合是四种整句读法'
        '——連山接、連山到、連天接、連天到，照登不裁决，同行双标记首见）；'
        '回头看白云合拢，走进青雾反而什么都看不见（「白雲迴望合，青靄入看無」——'
        '远近两试都是雾）；中峰一变便是分野，阴晴使千壑各异'
        '（「分野中峰變，陰晴{{另|眾|聚}}壑殊」——山把天空切开）；'
        '想找个有人处投宿，隔着水向樵夫问路（「欲投人處宿，隔{{另|水|浦}}問樵夫」——'
        '全景里唯一的小动作收束全诗）。全诗无一时一事，读法是读法，史实只有页上八句。'),
    'bg-137-city': (
        '这座城的档案先登记题目本身的三个名字：section 字段挂着'
        '「{{*|題下一有「行」字，一作「終山行」}}」——終南山/終南山行/終山行'
        '并挂不裁决（{{*}} 题异注首见 section 字段，audit 照登硬卡）。'
        '页底注与分类行（五言律詩）为整理者动作：照登+非史料声明+不升格（V048 判例）。'
        '**诚实边界修正**：本页 {{Textquality|100%}} 却带五枚标记（{{另}}×4+{{*}}×1）——'
        '完备度与异文数**正交**：100% 说的是底本录入完备、不是没有异文；'
        'V048「100% 与零标记互证」仅适用于零标记页，本迁移如实登记此边界。'
        '卷126 本篇是标准「消歧锚点+转引桩」结构（对照 V053《春曉》的全卷唯一内联）。'
        '诗世界的山名题族：全唐詩「終南山」恰 25 处分布 13 卷——'
        '他人的终南山各是各诗，在册不引不牵合；机器断言卷784 两处命中后字必「翁」：'
        '「終南山翁」是**作者名**不是诗题（假命中在册第二例，V053 雞香積之后）。'),
    'bg-137-world': (
        'V050 的峴山在史部零档案；这座山正相反——通鉴「終南山」恰五处，'
        '处处是皇家的事（五年标题窗口机器断言）：'
        '武德八年（乙酉，625）高祖「營太和宮於終南山」；武德九年（丙戌，626）'
        '玄武门余波「萬徹與數十騎亡入終南山」；贞观二十一年（丁未，647）'
        '太宗「命修終南山太和廢宮為翠微宮」；景龙元年（丁未，七零七年）'
        '太子重俊兵败「以百騎走終南山……憩於林下，為左右所殺」'
        '（此年号写「零」字——V050 立的异体年号机器防线在岗）；'
        '景云二年（辛亥，711）卢藏用指此山，司马承祯答'
        '「以愚觀之，此乃仕宦之疾徑耳」——隐士的捷径。\n'
        '「仕宦之疾徑耳」子句系**第二引**：全句 V047 已随卢藏用故事一引，'
        '两度上限至此用满，此句对后来迁移关闭（locator 声明+生成时全库查重）。\n'
        '「疾徑」通鉴恰两处，第二处是断词假命中：tj-251 濠州贼将王弘立'
        '「引兵數萬疾徑奄至」——疾=疾速、徑=取道，撞出二字（机器断言后字必「奄」，'
        '在册零入引）。**山从 625 排到 711 全是皇帝、太子、隐宦——'
        '山的全部档案没有一条属于这首诗**（V050 山无史山的镜像：山有史、史非诗史）。'
        '本层不铸时间，零铸造零 relation。'),
    'bg-137-person': (
        '旧传给这个人一间斋房：「**齋中無所有，唯茶鐺、藥臼、經案、繩牀而已**。」——'
        '茶铛、药臼、经案、绳床，四件物之外一无所有（生成时全库查重：'
        '此句从未入任何迁移引文，本迁移首引；旧传单得，新传无此句不合并）。\n'
        '把斋房和山对读：诗里的终南山大到处处分野变、阴晴殊，'
        '传里的斋房小到四件物——**最大的山与最小的房**，同一个人'
        '（读法声明，不是史实）。这是本迁移唯一判例外的旧传句：'
        '王维传其余已用句（以诗名盛/凝碧/辋川/奉佛段/茶铛以外的奉佛句/代宗诏集/尤长五言）'
        '一个不重开；两传王维段「終南山」「疾徑」全零（机器断言）——'
        '传里写这个人时，根本没提这座山。'),
}
CLAIMS = {
    'claim-bg-137-scene': (
        'FACT', 'LIKELY',
        '八句全诗本文（ws 页 {{另}} 恰四/{{*}} 恰一，{{Textquality|100%}}——'
        '相邻双 {{另}} 组合四种整读照登不裁决，audit 硬卡双标记字样连续入引；'
        '同一 (claim,source) 主键一行容全文判例；正文另见 V018 claim-t300-137-text——'
        '本诗正文两度上限至此用满，后来者不得三引）；'
        '全景无时与投宿读法为本层声明，非史料断言。'),
    'claim-bg-137-city': (
        'FACT', 'LIKELY',
        '{{*}} 题异注首见 section 字段：終南山/終南山行/終山行三题面并挂逐字入引'
        '（audit 照登硬卡），登记不裁决；底注+分类行照登+非史料声明+不升格；'
        '诚实边界修正在册：100% 与五枚标记正交（V048 判例仅适用零标记页，如实登记）；'
        '卷126 标准锚点+桩结构（机器断言）；诗世界题族恰 25 处 13 卷在册不引；'
        '卷784「終南山翁」作者名假命中机器断言后字必翁、零入引；'
        '题有山而无时→零铸造零 relation。'),
    'claim-bg-137-world': (
        'FACT', 'LIKELY',
        '山有史、史非诗史（V050 镜像）：通鉴「終南山」恰 5 处=四卷闭域'
        '（武德八年营太和宫/武德九年亡入/贞观二十一年修翠微宫/景龙元年太子走山被杀'
        '/景云二年疾径句——**五年标题窗口机器断言**，含七零七年「零」字年号防线）；'
        '「仕宦之疾徑」子句第二引上限用满（V047 一引在先，locator 声明+全库查重）；'
        '「疾徑」第二处=tj-251 断词假命中（后字必「奄」机器断言），在册零入引；'
        '两传王维段終南山/疾徑全零（传不系山，机器断言）；'
        'certainty 不覆盖任何系年，诗 time.span/event.name/written_during 零铸造零 relation。'),
    'claim-bg-137-person': (
        'FACT', 'LIKELY',
        '旧传斋中四物句首引（生成时全库引文域查重：茶鐺既往零命中，audit 硬卡'
        '——与 V053「传句用尽」相反的镜像：这是王维传里最后一句未用活句）；'
        '旧传单得（新传无此句，不合并）；最大的山与最小的房并置为读法声明非史实；'
        '王维其余已用判例句零重开；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-137-scene', 'source-ws-t300-137',
     '页面 終南山 (王維)（header author+四联八句，五段以「……」相連——'
     '「連{{另|山|天}}{{另|接|到}}海隅」相邻双 {{另}} 原样入引（四种整读不裁决，'
     '同行双标记首见，tang300-variants.md 新行）；同一 (claim,source) 主键一行容全文判例；'
     '正文另见 V018 claim-t300-137-text——本诗正文两度上限至此用满，后来者不得三引）',
     join(WS_AUTHOR, WS_L1, WS_L2, WS_L3, WS_L4)),
    ('claim-bg-137-city', 'source-ws-t300-137',
     '页面 終南山 (王維)（section 字段 {{*}} 题异注+页底注+分类行三段并收——'
     '「題下一有「行」字，一作「終山行」」系 {{*}} 题异注首见 section 字段'
     '（三题面并挂照登不裁决，audit 照登硬卡）；底本指向与「五言律詩」分类均为'
     '整理者动作：非史料声明、不升格；本页 100% 带五枚标记=完备度与异文数正交（V048 边界修正））',
     join(WS_SECTION, WS_NOTE, WS_CAT)),
    ('claim-bg-137-city', 'source-quantangshi-126',
     '卷一百二十六·王维集《終南山 (王維)》篇题锚点+转引桩（标准 2× 结构——'
     '对照 V053《春曉》全卷唯一正文内联；诗世界题族恰 25 处 13 卷在册不引；'
     '卷784「終南山翁」作者名假命中机器在册零入引）',
     join(Q126, Q126_S)),
    ('claim-bg-137-world', 'source-zizhi-tongjian-events',
     '卷一百九十一·武德八年营太和宫段……卷一百九十八·贞观二十一年修翠微宫段……'
     '卷二百零八·景龙元年太子走山段……卷二百一十·景云二年疾径句'
     '（皇家事五处取四段+疾径**第二引**：全句 V047 一引在先、本迁移子句二引，'
     '**两度上限至此用满，此句对后来迁移关闭**；五年标题窗口+文件闭域机器断言；'
     'tj-251 断词假命中「疾徑奄至」在册零入引）',
     join(TJ_TAIHE, TJ_WANCHE, TJ_CUIWEI, TJ_TAIZI, TJ_JIJING)),
    ('claim-bg-137-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传斋中四物句（茶铛/药臼/经案/绳床——'
     '生成时全库引文域查重：此句既往零入引，本迁移首引；旧传单得不合并；'
     '与诗中大山并置是读法声明）', JTS_C),
]
BG_LINES = {'bg-137-scene': (1, 2), 'bg-137-city': (3, 4),
            'bg-137-world': (5, 6), 'bg-137-person': (7, 8)}
BG_AUDIENCE = {'bg-137-scene': 'PRIMARY', 'bg-137-city': 'JUNIOR',
               'bg-137-world': 'SENIOR', 'bg-137-person': 'JUNIOR'}
BG_TITLES = {'bg-137-scene': '眼前：一座没有时间的全景山',
             'bg-137-city': '这座城：三个题目与四件物外的斋',
             'bg-137-world': '这个天下：山从 625 排到 711 都是皇家的事',
             'bg-137-person': '这个人：最大的山与最小的房'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 35 首·八句律詩 2/2/2/2）；史实句均有逐字引证；'
                 '系年第二十九次判决（题证系列第十七状·皇家山与无时诗）'
                 '「題有山有史，史是皇家事；詩有山無時，無時亦無年」——'
                 '通鉴「終南山」恰 5 处五年标题窗口全归营宫/亡入/修宫/杀太子/隐宦捷径'
                 '（V050 山无史山的镜像：山有史、史非诗史）'
                 '→time.span/event.name/written_during 全缺席、零 relation；'
                 '{{*}} 题异注首见 section 字段（終南山/終南山行/終山行并挂照登不裁决）；'
                 '同行相邻双 {{另}} 首见（連山接/連天到四种组合——audit 硬卡连续标记）；'
                 '诚实边界修正：100% 与五枚标记正交（V048 判例仅适用零标记页）；'
                 '「仕宦之疾徑」第二引上限用满对后来关闭（V047 在先+全库查重）；'
                 '断词假命中第二例在册（tj-251 疾徑奄至后字必奄）；'
                 '作者名假命中在册（卷784 終南山翁后字必翁）；'
                 '旧传斋中四物句首引（全库查重既往零引——与 V053 传句用尽互为镜像）；'
                 'KNOWN 零如实记录（第十例，audit 反向断言）；零新 source；判例关键语零入引文。' for k in BG}


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
    A("""-- V054：王維《終南山》(work-t300-137) 四层背景（阶段 D 第 35 首·皇家山与无时诗）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V014、V015、V016、V018、V035、V047、V053 已执行（work-t300-137 与其
--       text-work-t300-137-ws、source-ws-t300-137 是 V018 的行；source-quantangshi-126 是 V035 的行；
--       source-jiutangshu-wenyuan 是 V016 的行；source-zizhi-tongjian-events 是 V014/V015 已立的通鉴事件源）。
--       **本迁移零新 source**（audit 断言 SQL 无任何诗源表新建插入语句）。
--
-- 数据源（可复现）：emit_v054.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/終南山__王維_.txt（{{*}} 题异注在 section 字段首见+相邻双 {{另}} 首见+
--   100% 与五枚标记正交修正）、舊唐書卷190下（斋中四物句首引+王维段负证）、
--   新唐書卷202（王维段负证）、通鑑卷191/198/208/210（皇家事五处+五年标题窗口）
--   + 通鑑 75 卷/全唐詩 120 卷负证计数扫描+既有迁移引文域逐句查重——
--   传区间归属、終南山/疾徑全部计数、断词与作者名两类假命中、年标题窗口、
--   首引前提与第二引前提全部生成时断言。
--
-- 做：4 BACKGROUND content/claim/background + 5 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八句形制：scene→1-2 city→3-4 world→5-6 person→7-8，
--   绑 text-work-t300-137-ws 的 8 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「題有山有史，史是皇家事；詩有山無時，無時亦無年」）：
--   * 山有史、史非诗史：通鉴恰 5 处全归皇家事（闭域+五年窗口断言，含七零七年「零」字防线）；
--   * 「仕宦之疾徑」第二引上限用满：V047 一引在先（全库查重恰一处），此句对后来迁移关闭；
--   * 两类假命中在册零入引：tj-251 断词「疾徑奄至」（后字必奄）+卷784 作者名「終南山翁」（后字必翁）；
--   * 100% 与异文数正交（V048 判例边界修正——只适用零标记页，本页 100% 带五枚标记）；
--   * {{*}} 题异注首见 section 字段+同行相邻双 {{另}} 首见（audit 双照登硬卡）；
--   * 旧传斋中四物句首引（全库查重既往零引）——与 V053「传句用尽」互为镜像；
--   * 全景无时/大山小房并置均为读法声明，audit 双声明在 BG 文本内；
--   * KNOWN 零如实记录（第十例，audit 反向断言 SQL 无 KNOWN 字面量）；
--   * 不才/凝碧/輞川/藍田/長齋/茶鐺以外的奉佛句/尤長五言/以詩名盛/代宗诏集 判例只引不重开。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 53，不含 54
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-137-%';             -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-137-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-137-%';       -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-137';                                  -- 8（2/2/2/2）
--   SELECT certainty FROM poetry_claim WHERE id LIKE 'claim-bg-137-%';  -- 四行全 LIKELY（有意全 LIKELY）
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-137'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-137';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-137-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
--   SELECT COUNT(*) FROM poetry_source WHERE id='source-ws-t300-137';   -- 恰 1（V018 旧行，零新源）
-- 回滚: recovery/V054_rollback.sql（按 id 全枚举删除；不动任何共用来源行、不动 V018 的行）
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
    brows = [{'id': k, 'work_id': 'work-t300-137',
              'layer': {'bg-137-scene': 'SCENE', 'bg-137-city': 'CITY',
                        'bg-137-world': 'WORLD', 'bg-137-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-137-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 54, 'Wang Wei On Zhongnan Mountain background layers (stage-D poem 35, eight-line regulated verse 2/2/2/2, the mirror image of the mountain without history): dating verdict twenty-nine, seventeenth shape of the title-evidence series -- the title keeps a mountain with a full archive and a poem without a single time-word: the Tongjian''s five occurrences of Zhongnan Mountain are machine-proven to be wholly imperial (Wude 8 founding the Taihe palace, Wude 9 a fleeing prince, Zhenguan 21 rebuilding it as Cuiwei, Jinglong 1 a defeated crown prince killed in the grove -- the year written with the zero glyph, the V050 defense line on duty -- and Jingyun 2''s "the shortcut of careers"), five year-heading windows locked; the mountain''s entire archive belongs to no poem (the inversion of V050''s history-less mountain: here history is plentiful and none of it is the poem''s); the title itself carries three names registered in the section field via {{*}} for the first time (zhongnan shan / shan xing / zhong shan xing, side by side unadjudicated, audit hard-assert) and the poem''s first couplet carries the first adjacent double {{另}} pair on one line (four combinations = two whole readings, transcription verbatim); honest-boundary correction registered: Textquality 100% coexists with five markers -- completeness is orthogonal to variant count, V048''s zero-marker corollary applies only to marker-free pages; the career-shortcut sentence is cited for the second time (full sentence used in V047, machine-swept single prior hit) so the two-use ceiling closes it for all future migrations (locator declares it, audit asserts); second false hit on record: the 251st juan''s cut-word "疾徑奄至" (fast + take-road, machine-asserted next char) and juan 784''s author-name "終南山翁" (next char must be weng) -- both logged, never quoted; the Old History''s four-objects room sentence is first-cited (sweep proves zero prior citations -- the mirror of V053''s exhausted biographies); KNOWN zero honestly recorded (tenth instance, audit reverse-asserts); zero new sources; closed precedent keywords stay out of citations'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 54);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V054 精确回滚：只删 V054 插入的行（id 全枚举）。',
         '-- work-t300-137 本体、其 text_line 8 行与 source-ws-t300-137 都是 V018 的行，绝不删；',
         '-- 全部四个共用 source 行（ws-137/quantangshi-126/jiutangshu-wenyuan/',
         '-- zizhi-tongjian-events）均为他迁移所立，零删除（本迁移零新 source）；V054 零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 54;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_SECTION, WS_AUTHOR, WS_NOTE, WS_CAT, WS_L1, WS_L2, WS_L3, WS_L4,
              JTS_C, TJ_TAIHE, TJ_WANCHE, TJ_CUIWEI, TJ_TAIZI, TJ_JIJING, Q126, Q126_S]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 相邻双标记照登硬卡
    scene_ex = next(ex for c, _, _, ex in CITATIONS if c == 'claim-bg-137-scene')
    if '連{{另|山|天}}{{另|接|到}}海隅' not in scene_ex:
        bad.append('相邻双 {{另}} 未逐字连续入 SCENE 引文（同行双标记首见照登硬卡）')
    # {{*}} 题异注照登硬卡
    city_ws = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-137-city' and s == 'source-ws-t300-137')
    if '{{*|題下一有「行」字，一作「終山行」}}' not in city_ws:
        bad.append('{{*}} 题异注未逐字入 CITY 引文（section 字段首见照登硬卡）')
    if '非史料' not in next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-137-city' and s == 'source-ws-t300-137'):
        bad.append('CITY ws locator 须含「非史料」声明（三重断言第二项失效）')
    # WORLD 第二引上限声明硬卡
    w_loc = next(loc for c, s, loc, _ in CITATIONS if c == 'claim-bg-137-world')
    if '第二引' not in w_loc or '上限' not in w_loc:
        bad.append('WORLD locator 须含「第二引/上限」声明（V050 同款硬卡）')
    # 假命中零入引文
    if '疾徑奄至' in cited or '終南山翁' in cited:
        bad.append('假命中（断词疾徑/作者名終南山翁）在册不引，不得入引文')
    # 引要素
    w_tj = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-137-world')
    for tok in ('營太和宮於終南山', '亡入終南山', '為翠微宮', '太子以百騎走終南山', '仕宦之疾徑'):
        if tok not in w_tj:
            bad.append(f'通鉴侧引文缺皇家事要素「{tok}」')
    for c, s, _, ex in CITATIONS:
        if s != 'source-ws-t300-137':
            for w in ('凝碧', '輞川', '藍田', '長齋', '尤長五言', '以詩名盛', '不才', '放還'):
                if w in ex:
                    bad.append(f'非 ws 引文不得含判例语「{w}」')
    # 判例只引不重开（引文域全扫）
    for tok in ('不才明主棄', '奈何誣我', '因放還', '遑恤他', '隱鹿門山', '隠鹿門山',
                '孟亭', '畫浩然像', '開元、天寶間', '詩名冠代', '病疽背卒', '刻碑鳳林山南'):
        if tok in cited:
            bad.append(f'判例只引不重开：{tok} 不得入本迁移引文')
    # 八句形制 2/2/2/2
    want = {'bg-137-scene': 2, 'bg-137-city': 2, 'bg-137-world': 2, 'bg-137-person': 2}
    if {k: len(v) for k, v in BG_LINES.items()} != want:
        bad.append('八句 background_line 必须 2/2/2/2')
    if len(re.findall(r"text-work-t300-137-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
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
        bad.append("V054 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V054 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-137' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V054 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-137' AS subject_id" in sql:
        bad.append('V054 的 claim 主语应全部是 bg-137-*，work-t300-137 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V054 不碰 poetry_text_line')
    body_all = ''.join(BG.values()) + sql
    if '史是皇家事' not in body_all:
        bad.append('BG/文件头须含「史是皇家事」判决声明')
    if '無時亦無年' not in body_all:
        bad.append('BG/文件头须含「無時亦無年」判决声明')
    if '正交' not in body_all:
        bad.append('BG/CITY 须含 100%「正交」边界修正声明')
    if '假命中' not in body_all:
        bad.append('BG 须含「假命中」在册声明（断词+作者名两例）')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 16 切片逐字过审且全部进引文；'
              f'切片传区间归属断言（王维段）；五年标题窗口断言'
              f'（武德八年/武德九年/贞观二十一年/景龙元年七零七年/景云二年）；'
              f'负证机器复查四层（通鉴終南山恰 5=四卷闭域+疾徑恰二第二处断词后字必奄/'
              f'全唐詩終南山恰 25+卷126 恰三+卷784 后字必翁/ws {{另}}4/{{*}}1/相邻双标记恰一/'
              f'100% 恰一/两传王段終南山疾徑全零，快照变动即中止）；'
              f'首引前提全库查重硬卡（茶鐺既往零引）+第二引前提全库查重硬卡（疾徑既往恰一=V047）；'
              f'相邻双 {{另}} 与 {{*}} 题异注两处照登硬卡；WORLD locator 第二引/上限硬卡；'
              f'假命中零入引断言；底注+分类三重断言；判例只引不重开断言；'
              f'八句 2/2/2/2 形制断言；零 KNOWN 反向断言；零新 source 反向断言'
              f'（无诗源表新建插入，回滚零删源行）；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
