#!/usr/bin/env python3
"""阶段 D 第 16 首：生成 V035——王维《輞川閑居贈裴秀才迪》(work-t300-062, V018 已立) 四层背景。

「为什么写」第八次成立，这次本传给的是**一整个隐居现场**：两唐书各记一笔王维在辋川
与裴迪的酬唱——旧传「與道友裴廸浮舟往來，彈琴賦詩，嘯詠終日」（**廸**字），
新传「與裴迪遊其中，賦詩相酬為樂」（**迪**字）——同一个人、两个用字、两源独立一致，
KNOWN 就升这一处。诗题里的「裴秀才」正是这个裴迪；这是阶段 D 第一首**赠诗**，
赠的对象本人就活在诗里（「復值接輿醉」以接輀拟裴）。

系年第十次判决：**全缺席，缺席原因「别墅无得第之年，两传次序相反」**。
辋川别业「得宋之問藍田别墅」（旧传）——宋之問卒年 712 只给一个下限常识，
不得第之年；「晚年長齋」不是年份；**新旧两传把辋川段放在安史之乱叙事的两侧**
（旧传在前、新传在后）——传文次序不是编年，不裁决、并列声明。
凝碧池事件年（756）是硬的（tj-218 标准形年标题，通鉴编年直书升 KNOWN），
但它锁的是王维被陷贼的一段，不是辋川闲居——事件年与诗年无关，不外溢。
time.span/event.name/written_during 零铸造 + 零 relation（同款形状断言累积）。

通鉴的「人零命中、事件在卷」判例（新形状）：**通鉴 75 卷（tj-191–265，完整性 2026-11-20
全量验证）王维零命中；裴迪在其世纪零命中，仅晚唐 902/904 两卷有个同名异人（已机器隔离）**——王维其人不入通鉴，但他最著名的传记场景
（凝碧池之宴、雷海清支解）就在 tj-218 至德元年条下。人缺席 ≠ 事件缺席，两行都写明。

同名护栏：旧唐书本纪（卷20下，天祐间）有「刑部尚書裴迪」——异代同名异人，
与这位never出仕的裴秀才绝不同人（诗题称「秀才」即是无官之证），BG 正文明说。

赠诗第一例 + 八行常形制（每层 2 行）；1 个新 source（全唐詩卷126 桩页——header
noauthor 字段为空，卷内无作者标注，如实声明；V031 桩教训同款）。

用法: python3 -I emit_v035.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import glob
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/輞川閑居贈裴秀才迪.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
TJ218 = pathlib.Path('/tmp/src-dl/tongjian/tj-218.txt').read_text(encoding='utf-8')
QT126 = pathlib.Path('/tmp/src-dl/quantangshi/vol126.txt').read_text(encoding='utf-8')

# ---------- 入库前提的机器复验（缺席声明只能基于完整性已验证的快照集——在常） ----------
_tj_files = sorted(glob.glob('/tmp/src-dl/tongjian/tj-*.txt'))
if len(_tj_files) != 75:
    raise SystemExit(f'通鉴快照应为 75 卷（tj-191–265），实得 {len(_tj_files)}——缺席声明不可用')
_hits_wang, _hits_pei, _bad = [], [], []
for _f in _tj_files:
    _t = pathlib.Path(_f).read_text(encoding='utf-8')
    if _t[:30].lstrip().startswith('<!DOCTYPE') or 'MediaWiki' in _t[:300]:
        _bad.append(_f)
    if '王維' in _t:
        _hits_wang.append(_f)
    if '裴迪' in _t:
        _hits_pei.append(_f)
if _bad:
    raise SystemExit(f'通鉴快照含错误页：{_bad}——先重抓再谈缺席')
if _hits_wang:
    raise SystemExit(f'通鉴命中与「王维零命中」断言冲突：{_hits_wang}——修订 claim 措辞后重生成')
# 裴迪断言的形状（2026-11-20 复扫修正）：王维世纪零命中；仅许 tj-263/265 命中——
# 那是 902/904 年（天复/天祐间）朱全忠阵营的晚唐同名裴迪（判官守大梁/刑部尚書送宫告使），
# 与辋川裴秀才异代异人；晚唐隔离用当年标准形年标题机器断言，不靠自觉
if {f.split('/')[-1] for f in _hits_pei} - {'tj-263.txt', 'tj-265.txt'}:
    raise SystemExit(f'裴迪出现在王维世纪之外的非预期卷：{_hits_pei}——缺席断言需修订')
for _n, _yr in ((263, '公元九零二年'), (265, '公元九零四年')):
    _t = pathlib.Path(f'/tmp/src-dl/tongjian/tj-{_n}.txt').read_text(encoding='utf-8')
    if _yr not in _t:
        raise SystemExit(f'tj-{_n} 缺晚唐年标题 {_yr}——同名隔离断言失效，拒绝生成')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
WS_L1 = slice_between(WS, '寒山轉蒼翠，秋水日潺湲。', '寒山轉蒼翠，', 'ws第1句(寒山秋水)')
WS_L2 = slice_between(WS, '寒山轉蒼翠，秋水日潺湲。', '秋水日潺湲。', 'ws第2句(秋水潺湲)')
WS_L3 = slice_between(WS, '倚杖柴門外，臨風聽暮蟬。', '倚杖柴門外，', 'ws第3句(倚杖柴门)')
WS_L4 = slice_between(WS, '倚杖柴門外，臨風聽暮蟬。', '臨風聽暮蟬。', 'ws第4句(临风暮蝉)')
WS_L5 = slice_between(WS, '渡頭餘落日，墟里上孤煙。', '渡頭餘落日，', 'ws第5句(渡头落日)')
WS_L6 = slice_between(WS, '渡頭餘落日，墟里上孤煙。', '墟里上孤煙。', 'ws第6句(墟里孤烟)')
WS_L7 = slice_between(WS, '復值接輿醉，狂歌五柳前。', '復值接輿醉，', 'ws第7句(接舆之醉——拟裴迪)')
WS_L8 = slice_between(WS, '復值接輿醉，狂歌五柳前。', '狂歌五柳前。', 'ws第8句(五柳——王维自拟)')
WS_TITLE = slice_between(WS, '| title    = 輞川閑居贈裴秀才迪', '| title    = 輞川閑居贈裴秀才迪',
                         'ws header title(赠裴秀才——受赠人题内直证)')
WS_AUTHOR = slice_between(WS, '| author   = 王維', 'author   = 王維', 'ws header author(署名直证)')
JTS_WC = slice_between(JTS, '得宋之問藍田别墅，在輞口，輞水周於舍下，别漲竹洲花塢，與道友裴廸浮舟往來，彈琴賦詩，嘯詠終日。甞聚其田園所為詩，號輞川集。',
                       '號輞川集。', '旧传辋川段(得宋之问别墅/裴廸浮舟——廸字逐字，异文连接声明在locator)')
JTS_LU = slice_between(JTS, '禄山䧟兩都，玄宗出幸，維扈從不及，為賊所得。維服藥取痢，偽稱瘖病。禄山素憐之，遣人迎置洛陽，拘於普施寺，迫以偽署。禄山宴其徒於凝碧宫，其樂工皆梨園弟子、教坊工人。維聞之悲惻，潛為詩曰：「萬户傷心生野煙，百官何日再朝天？秋槐花落空宫裏，凝碧池頭奏筦絃。」',
                        '凝碧池頭奏筦絃。」', '旧传凝碧段(服药取痢/伪称瘖/潜为诗全引——禄字从旧传录本)')
JTS_FAME = slice_between(JTS, '維以詩名盛於開元、天寶間，昆仲宦遊兩都，凡諸王駙馬豪右貴勢之門，無不拂席迎之，寧王、薛王待之如師友。',
                         '待之如師友。', '旧传诗名段(开元天宝间名盛——世界层背景)')
XTS_ZJL = slice_between(XTS, '張九齡執政，擢右拾遺。', '擢右拾遺。', '新传张九龄段(知遇一线——王维线起点)')
XTS_WC = slice_between(XTS, '別墅在輞川，地奇勝，有華子岡、欹湖、竹裏館、柳浪、茱萸沜、辛夷塢，與裴迪遊其中，賦詩相酬為樂。',
                       '賦詩相酬為樂。', '新传辋川段(六景点名/裴迪游其中——迪字逐字，与旧传廸字并证)')
XTS_FB = slice_between(XTS, '兄弟皆篤志奉佛，食不葷，衣不文彩。', '衣不文彩。', '新传奉佛段(笃志奉佛——新传单得)')
XTS_LU = slice_between(XTS, '安祿山反，玄宗西狩，維為賊得，以藥下利，陽喑。祿山素知其才，迎置洛陽，迫為給事中。祿山大宴凝碧池，悉召梨園諸工合樂，諸工皆泣，維聞悲甚，賦詩悼痛。賊平，皆下獄。或以詩聞行在，時縉位已顯，請削官贖維罪，肅宗亦自憐之，下遷太子中允。',
                        '下遷太子中允。', '新传凝碧段(阳喑/赋诗悼痛/弟缙请削官赎罪——与新传辋川段次序相反旧传)')
TJ218_TITLE = slice_between(TJ218, '肅宗文明武德大聖大宣孝皇帝上之下至德元年（丙申，公元七五六年）',
                            '至德元年（丙申，公元七五六年）', '通鉴218卷756年标题(全卷唯一纪年标题,audit生成时已断言)')
TJ218_NB = slice_between(TJ218, '祿山宴其群臣於凝碧池，盛奏眾樂；梨園弟子往往歔欷泣下，賊皆露刃睨之。樂工雷海清不勝悲憤，擲樂器於地，西向慟哭。祿山怒，縛於試馬殿前，支解之。',
                         '支解之。', '通鉴756凝碧池条(雷海清支解——事件本体,人零命中标号在locator)')
QT_STUB = slice_between(QT126, '==[[輞川閑居贈裴秀才迪]]==\n{{:輞川閑居贈裴秀才迪}}',
                        '{{:輞川閑居贈裴秀才迪}}', '全唐诗卷126本诗条目(锚点+转引用桩——卷页无正文)')

BG = {
    'bg-wc-scene': (
        '这首诗的前四句是中国诗里最安静的一段：「寒山轉蒼翠，秋水日潺湲。'
        '倚杖柴門外，臨風聽暮蟬」——冬天的山转成苍色，秋天的水整日潺湲，'
        '老人拄着杖站在柴门外，迎风听暮色里的蝉。\n'
        '「閑居」两个字写在诗题里，不用猜。本传能给的最近的一条是旧传的'
        '「彈琴賦詩，嘯詠終日」——辋川的日子就是这种规格。至于这场暮蝉是'
        '哪一年的秋天，两传无一字；「秋水」「暮蟬」是诗内证据，季节在诗里，年份不在。'
        '季节有证、年份没有——这首的诚实边界从这里开始。'),
    'bg-wc-city': (
        '这座城不在诗里——辋川不是城，是长安东边蓝田辋口的一片山谷别墅。'
        '旧传给出产业来源：「得宋之問藍田别墅，在輞口，輞水周於舍下」——'
        '这产业是从宋之問手里来的；新传给出地形景点：「別墅在輞川，地奇勝，'
        '有華子岡、欹湖、竹裏館、柳浪、茱萸沜、辛夷塢」——六个景点名逐一列出。'
        '两源独立一致升 KNOWN 的这一点：王维在蓝田辋口有一处辋水环绕的别业。\n'
        '他实际的城串在两传里排不开：旧传「歴右拾遺、監察御史、左補闕、庫部郎中」'
        '一路到「轉尚書右丞」（后世叫他王右丞即此）；新传却从「調太樂丞，'
        '坐累為濟州司倉參軍」起，又添「張九齡執政，擢右拾遺」——**两传官历清单不同**，'
        '照登不裁决。辋川就悬在这串官职的边上：不是长安，不是边塞，是京城之侧的山。'),
    'bg-wc-world': (
        '「渡頭餘落日，墟里上孤煙」——诗里的天下小到一个渡口一缕炊烟；'
        '这个人真正撞上的天下，是十几年后的一场大乱。\n'
        '先说一个奇事：**王维其人不进通鉴**——通鉴 191–265 全部 75 卷（2026-11-20 '
        '完整性全量验证）零「王維」命中。但他最著名的传记场景在通鉴里：'
        '至德元年（丙申，公元七五六年）条下，「祿山宴其群臣於凝碧池……樂工雷海清'
        '不勝悲憤，擲樂器於地，西向慟哭。祿山怒……支解之」——人缺席，事件在卷，'
        '事件本体（编年体直书）升 KNOWN。两唐书各记下王维被贼所得、服药装哑、'
        '迫受伪职、闻乐潜诗——旧传连他的诗都全文收了：「萬户傷心生野煙，'
        '百官何日再朝天？秋槐花落空宫裏，凝碧池頭奏筦絃。」\n'
        '但 756 锁的是陷贼那一段，锁不到辋川：这首诗是闲居赠人之作，'
        '乱前乱后无年可系——年表式演算不做。'
        'time.span、event.name、written_during 一个都不造。'),
    'bg-wc-person': (
        '「復值接輿醉，狂歌五柳前」——这首诗的最后一联里站着两个人：'
        '接舆（楚狂人）指裴迪，五柳（陶渊明）是王维自拟。赠诗赠到这里，'
        '等于说：你是我那个疯子朋友，我是这个山谷里的陶潜。\n'
        '这个朋友在两唐书里各出现一次，用字还不同——旧传作「與道友**裴廸**'
        '浮舟往來，彈琴賦詩，嘯詠終日」，新传作「與**裴迪**遊其中，賦詩相酬為樂」：'
        '廸/迪两个写法都是逐字原文，同一个人；两源独立一致升 KNOWN 的正是这一点：'
        '王维与裴迪在辋川的隐居酬唱。\n'
        '两传独得处并列照登不升：新传「兄弟皆篤志奉佛，食不葷，衣不文彩」；'
        '旧传「甞聚其田園所為詩，號輞川集」（集名是旧传单得）。裴迪其人官历两传'
        '均无一字——诗题就叫他「裴秀才」，秀才是他能给的全部身份。\n'
        '同名护栏必须立住：旧唐书本纪（卷二十下，天祐年间）有个做到刑部尚書的'
        '「裴迪」——晚唐百余年后的同名异人，与本诗这位 never 出仕的秀才不是一个人，'
        '查史料时千万别串。'),
}
CLAIMS = {
    'claim-bg-wc-scene': (
        'FACT', 'LIKELY',
        '前四句纯景全诗本文；「闲居」为诗题本文；弹琴赋诗/啸咏终日为旧传近证（LIKELY）；'
        '季节（秋水/暮蝉）有诗内证据，写作年份两传无一字——不编。'),
    'claim-bg-wc-city': (
        'FACT', 'KNOWN',
        '辋川别业存在（蓝田辋口/辞水环绕）——旧传「得宋之問藍田别墅」段与'
        '新传「別墅在輞川」段两源独立一致；产业来源（宋之問旧第）与六景点名各为单传'
        '独得（LIKELY）；两传官历清单不同——并列不裁决；到凉州/边地无关此人此诗。'),
    'claim-bg-wc-world': (
        'FACT', 'KNOWN',
        '756 年标题（标准形，丙申对账由 audit 检查4 覆盖）+凝碧池条通鉴逐字——'
        '编年体直书，事件本体升 KNOWN（V028/V033 事件判例）；此 KNOWN **只覆盖事件，'
        '不外溢到诗**：王维陷贼与辋川闲居的先后无年可系（两传次序相反）→'
        '诗 time.span/event.name/written_during 零铸造、零 relation；'
        '王维其人在通鉴 75 卷零命中、裴迪在其世纪零命中（晚唐同名异人两卷除外，见 PERSON 层护栏）'
        '（完整性已验证集上复扫）——人缺席事件在卷，两行都写明。'),
    'claim-bg-wc-person': (
        'FACT', 'KNOWN',
        'KNOWN 一处：王维裴迪辋川酬唱——旧传「裴廸」段与新传「裴迪」段两源独立一致'
        '（廸/迪异写均逐字入证）；两传独得处（奉佛段新传/集名旧传/凝碧诗全文旧传）'
        '均 LIKELY 并列照登；晚唐同名裴迪（天祐间刑部尚書）异代异人已明说隔离；'
        'certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-wc-scene', 'source-ws-t300-062',
     '页面 輞川閑居贈裴秀才迪（header title+author 两字段+第1、2句，四段以「……」相連——'
     '赠诗受赠人题内直证+开场纯景；页内实测无 {{另|}} 异文，「查过、干净」；'
     '全文另见 V018 claim-t300-062-text 引文）',
     join(WS_TITLE, WS_AUTHOR, WS_L1, WS_L2)),
    ('claim-bg-wc-city', 'source-quantangshi-126',
     '页面 全唐詩/卷126（本诗锚点+转引用桩 {{:輞川閑居贈裴秀才迪}}；'
     '卷首 Collection header 的 noauthor 字段为空——卷页无作者标注、无正文，'
     '正文证据在诗页；同 V022/V025–V031 桩教训）',
     QT_STUB),
    ('claim-bg-wc-city', 'source-ws-t300-062',
     '页面 輞川閑居贈裴秀才迪（第3、4句逐字——柴门暮蝉：别业生活的诗内直证，'
     '与两传辋川段对读）',
     join(WS_L3, WS_L4)),
    ('claim-bg-wc-city', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传辋川段（得宋之問藍田别墅/在輞口/與道友裴廸——'
     '**旧传用「廸」字**，与新传「迪」并证同一人；「號輞川集」三字旧传单得）',
     JTS_WC),
    ('claim-bg-wc-world', 'source-ws-t300-062',
     '页面 輞川閑居贈裴秀才迪（第5、6句逐字——渡口炊烟的小天下与下方大乱并读）',
     join(WS_L5, WS_L6)),
    ('claim-bg-wc-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百十八·唐紀三十四·肅宗·至德元年（丙申，公元七五六年）标题+凝碧池条'
     '（两段以「……」相連，年标题归属已分记——该卷快照页头 {{Textquality|50%}} 已声明；'
     '全卷唯一纪年标题，条目归属由生成器位置断言；**王维其人全通鉴 75 卷零命中**——人缺席事件在卷）',
     join(TJ218_TITLE, TJ218_NB)),
    ('claim-bg-wc-person', 'source-ws-t300-062',
     '页面 輞川閑居贈裴秀才迪（第7、8句逐字——接舆拟裴/五柳自拟：'
     '两人并立的诗内直证，与两传裴廸/裴迪段对读）',
     join(WS_L7, WS_L8)),
    ('claim-bg-wc-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·王维传凝碧段（禄山陷两都/服药取痢/伪称瘖/凝碧宫潜为诗——'
     '凝碧诗全文唯旧传收，诗非三百首内作，作人证引用；禄字从旧传录本）',
     join(JTS_LU, JTS_FAME)),
    ('claim-bg-wc-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·王维传（张九龄段+辋川段+奉佛段+凝碧段；'
     '四段以「……」相連，出处同卷同传——**新传辋川段在安史段之后**，'
     '与旧传次序相反，传文次序不作编年用，声明在 BG 正文）',
     join(XTS_ZJL, XTS_WC, XTS_FB, XTS_LU)),
]
BG_LINES = {'bg-wc-scene': (1, 2), 'bg-wc-city': (3, 4),
            'bg-wc-world': (5, 6), 'bg-wc-person': (7, 8)}
BG_AUDIENCE = {'bg-wc-scene': 'PRIMARY', 'bg-wc-city': 'JUNIOR',
               'bg-wc-world': 'SENIOR', 'bg-wc-person': 'SENIOR'}
BG_TITLES = {'bg-wc-scene': '眼前：柴门外的秋天',
             'bg-wc-city': '这块地：京城之侧的山谷',
             'bg-wc-world': '这个天下：人不进通鉴，事在通鉴',
             'bg-wc-person': '这两个人：接舆与五柳'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 16 首·第一首赠诗）；史实句均有逐字引证；'
                 'background_line 八行常形制：每层两行（1-2/3-4/5-6/7-8）；'
                 '别墅无得第之年+两传次序相反→time.span/event.name/written_during '
                 '全缺席、零 relation；756 凝碧池 KNOWN 仅事件本体不外溢；'
                 'KNOWN 三处：辋川别业（两源）+辋川酬唱（两源，廸/迪并证）+756 事件（编年直书）。' for k in BG}


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
    A("""-- V035：王维《輞川閑居贈裴秀才迪》(work-t300-062) 四层背景（阶段 D 第 16 首·第一首赠诗）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-062 与其 text-work-t300-062-ws、
--       source-ws-t300-062 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行；source-zizhi-tongjian-events 是 V015 的行——都不另开行）。
--
-- 数据源（可复现）：emit_v035.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/輞川閑居贈裴秀才迪.txt（页内实测无 {{另}}——「查过、干净」）、
--   舊唐書卷190下（王维传——辋川段「裴廸」+凝碧段诗全文+诗名段）、新唐書卷202（王维传——
--   辋川段「裴迪」+奉佛段+凝碧段，与旧传次序相反）、資治通鑑卷218（756 标准形年标题+
--   凝碧池条；快照页头 {{Textquality|50%}} 如实声明）、全唐詩卷126（锚点+转引用桩，
--   noauthor 空——卷页无作者标注）。
--   通鉴缺席断言基础：tj-191–265 75/75 完整性已验证（2026-11-20 缺口补齐+错误页扫描），
--   王维全量零命中、裴迪仅许晚唐 902/904 两卷同名命中——生成器内置复验，越界即拒绝生成。
--
-- 做：1 个新 source（source-quantangshi-126，PENDING——桩页教训同款）+
--   4 BACKGROUND content/claim/background + 9 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（八行常形制：每层两行 1-2/3-4/5-6/7-8，绑 text-work-t300-062-ws）。
--   本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「别墅无得第之年 + 两传次序相反 + 人零命中而事件在卷」）：
--   * 辋川别业存在=两传各自逐字（得宋之問藍田别墅/別墅在輞川）——两源独立一致升 KNOWN；
--     得第之年无一字（宋之問卒年 712 只是下限常识，不做年表式演算）；
--   * 旧传辋川段在安史乱前叙事侧、新传在乱后侧——**传文次序不是编年**，并列不裁决；
--   * 756 凝碧池=通鉴标准形年标题逐字（事件 KNOWN，V028/V033 判例），锁陷贼段不锁闲居——
--     事件年与诗年无关，不外溢；
--   * 王维其人在通鉴 75 卷零命中、裴迪在其世纪零命中（晚唐 902/904 同名异人两卷机器隔离）
--     ——人缺席≠事件缺席，两行分开写明；
--   * 裴廸（旧）/裴迪（新）同人次异写——两处均逐字入证，KNOWN 升酬唱一处；
--     晚唐同名刑部尚書裴迪（卷20下）异代异人已声明隔离；
--   * KNOWN 共三处（辋川别业/辋川酬唱/756 事件）；独得处（宋之問旧第/六景点名/
--     官历清单/奉佛段/集名/凝碧诗全文）按 LIKELY 照登。
--
-- 干支对账：756=丙申（至德元年，tj-218 标准形年标题，audit 检查4 覆盖）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 34，不含 35
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-wc-%';              -- 空
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-126';     -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-062-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-wc-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-062';                                  -- 8（每层两行）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-wc-city','claim-bg-wc-world','claim-bg-wc-person');
--     -- KNOWN / KNOWN / KNOWN（city=别业存在两源；world=756 事件不外溢；person=酬唱两源）
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-wc-scene';    -- LIKELY
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-062'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-062';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-wc-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V035_rollback.sql（按 id 全枚举删除；不动 V018 的行，不动共用来源行；
--   本迁移自开的 source-quantangshi-126 随回滚删除）
START TRANSACTION;""")

    A('\n-- ---------- 0. 新 source（1 个；桩页如实标注，PENDING 照 V031 判例） ----------')
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            [{'id': 'source-quantangshi-126',
              'title': '《全唐詩》全唐詩/卷126（维基文库录入本）',
              'author': None,
              'edition': '全唐詩/卷126（维基文库《全唐詩》录入本）',
              'url': 'https://zh.wikisource.org/wiki/全唐詩/卷126',
              'rights_note': '维基文库录入本，公有领域古籍。卷首 Collection header 的 noauthor '
                             '字段为空——卷页无作者标注（与卷160 的孟浩然标注不同）。本诗条目只有'
                             '锚点+转引用桩，正文在诗页。本行由 emit_v035.py 对快照逐字定位。'
                             '核验状态保持 PENDING。',
              'verification_status': 'PENDING', 'source_kind': 'POETRY_COLLECTION',
              'reliability': 'HIGH'}],
            'x.id = t.id'))

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
    brows = [{'id': k, 'work_id': 'work-t300-062',
              'layer': {'bg-wc-scene': 'SCENE', 'bg-wc-city': 'CITY',
                        'bg-wc-world': 'WORLD', 'bg-wc-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（八行常形制：每层两行） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-062-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 35, 'Wang Wei Wang-chuan xian-ju zeng Pei Xiu-cai Di background layers (stage-D poem 16, first gift-poem): the two Tang histories each record one Wang Wei -- the JTS supplies the Wang-chuan estate inherited from Tsung Chih-wen (with friend Pei Ti, graph ti with the walk radical, exchanging poems all day, and his full Ning-bi-pool mourning poem), the XTS supplies the six named garden sites, the devout-Buddhism lines and Pei Di with the walking radical -- same man, two graph variants, both quoted verbatim; KNOWN at exactly three points (the Wang-chuan estate, both sources; the Wang-Wei-Pei-Di retreat friendship, two sources; the 756 CE Ning-bi-pool banquet, standard-form year heading Zhi-de 1 (bing-shen) in tong-jian ju 218, annalistic, V028/V033 event precedent -- the event never overflows to the poem); dating absent for the tenth reason: the estate has no acquisition year (Tsung Chih-wen-d-s 712 death is only a lower-bound commonplace, no year-table arithmetic), late years is not a year, and the two histories place the Wang-chuan passage on opposite sides of the An Lushan narrative (biography order is not chronology -- side by side, no ruling); new twist: Wang Wei and Pei Di score ZERO mentions across all 75 integrity-verified tong-jian volumes (tj-191 to 265) -- the man is absent from the annals while his most famous scene stands in them, both facts said separately; a same-name guard: a much later Pei Di who became Vice Minister of Justice under the Tian-you reign (JTS basic annals 20xia) is a different man of a different century and is explicitly separated; one new source: quan-tang-shi juan 126 page (anchor plus transclusion stub; its Collection header carries an empty noauthor field -- no author attribution on the volume page, said honestly; PENDING per V031 precedent); time.span/event.name/written_during absent, zero relations; background_line shape: two lines per layer (1-2/3-4/5-6/7-8)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 35);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V035 精确回滚：只删 V035 插入的行（id 全枚举）。',
         '-- work-t300-062 本体、其 text_line 8 行与 source-ws-t300-062 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi/tongjian-events）不删；',
         '-- V035 自开的 source-quantangshi-126 随回滚删除；零 relation。',
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
    dels('poetry_source', 'id', ['source-quantangshi-126'])
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 35;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_L1, WS_L2, WS_L3, WS_L4, WS_L5, WS_L6, WS_L7, WS_L8, WS_TITLE, WS_AUTHOR,
              JTS_WC, JTS_LU, JTS_FAME, XTS_ZJL, XTS_WC, XTS_FB, XTS_LU,
              TJ218_TITLE, TJ218_NB, QT_STUB]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # tj-218 年标题+条目在 WORLD 引文里的归属断言（相邻性不适用——长卷——用「标题在前」）
    tj_ex = next(ex for c, s, _, ex in CITATIONS
                 if c == 'claim-bg-wc-world' and s == 'source-zizhi-tongjian-events')
    if tj_ex.find(TJ218_TITLE) < 0 or tj_ex.find(TJ218_NB) < 0:
        bad.append('tj-218 标题或条目未进 WORLD 引文')
    elif tj_ex.find(TJ218_TITLE) > tj_ex.find(TJ218_NB):
        bad.append('tj-218 年标题应在凝碧条之前（归属断言失败）')
    for tok in ('至德二', '開元'):
        if tok in tj_ex:
            bad.append(f'WORLD 引文混入 {tok} 系字符——凝碧条归属 756 单一年标题')
    # 廸/迪 异写双入证断言
    if '裴廸' not in cited or '裴迪' not in cited:
        bad.append('裴廸（旧传）与裴迪（新传）须两处逐字并证')
    body_all = ''.join(BG.values())
    if '裴廸' not in body_all:
        bad.append('BG 正文须并写「裴廸」以完成异写连接声明')
    # 八行常形制：每层恰 2 行，合计 8
    if sum(len(v) for v in BG_LINES.values()) != 8 or any(len(v) != 2 for v in BG_LINES.values()):
        bad.append('background_line 必须是每层恰 2 行（4 层共 8 行）')
    if len(re.findall(r"text-work-t300-062-ws' AS version_id", sql)) != 8:
        bad.append('bg_line INSERT 的 version 行数应为 8')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V035 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V035 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-062' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V035 有意不给诗铸 {pk}，但该主语组合出现了')
    ev_claims = re.findall(r"SELECT '([^']+)' AS subject_id, 'event\.name'", sql)
    if ev_claims:
        bad.append(f'V035 不给诗铸 event.name，但出现了主语: {ev_claims}')
    if "SELECT 'work-t300-062' AS subject_id" in sql:
        bad.append('V035 的 claim 主语应全部是 bg-wc-*，work-t300-062 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V035 不碰 poetry_text_line')
    # 恰 1 个新 source（quantangshi-126）+ 回滚同步删除
    if sql.count('INSERT INTO poetry_source') != 1:
        bad.append('V035 应恰有 1 个 poetry_source INSERT（source-quantangshi-126）')
    if "'source-quantangshi-126' AS id" not in sql:
        bad.append('新 source 应为 source-quantangshi-126')
    if "dels('poetry_source'" not in build_rollback() and "DELETE FROM poetry_source WHERE id IN ('source-quantangshi-126')" not in build_rollback():
        bad.append('回滚未删除 V035 自开的 source-quantangshi-126')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 20 切片逐字过审且全部进引文；'
              f'通鉴 75 卷王维零命中+裴迪世纪限复验已生成时执行；tj-218 标题前置于条目断言；'
              f'裴廸/裴迪异写双入证断言；八行每层两行形制断言；(claim,source) 主键 '
              f'{len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；1 新 source+回滚同步断言；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
