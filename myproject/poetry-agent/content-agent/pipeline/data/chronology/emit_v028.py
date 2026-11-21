#!/usr/bin/env python3
"""阶段 D 第 10 首：生成 V028——陳子昂《登幽州臺歌》(work-t300-002, V018 已立) 四层背景。

三百首开卷第一首。「为什么写」这一问第一次有本传级的材料可说：旧唐书本传把
武攸宜北讨契丹、以子昂为管记、军中文翰皆委之记成他仕途的一段，通鉴把统帅的败怯
逐月记出——诗登的幽州台正是那个战区的城。但边界同样第一次这么硬：
**两唐书与通鉴没有任何一处说此诗作于北征幕中，甚至没有一处提到这首诗**——
「北征感时而作」是后世年谱的说法，本地核不到。所以 time.span/event.name/
written_during 全部缺席（V023/V024/V027 形状断言 + 本文件零 relation 断言守死）；
事件实体挂战事本体（696–697 通鉴年标题直证 KNOWN），不向诗外溢。

PERSON 层是阶段 D 第一个**单传诗人**：新唐书文艺传实测无陈子昂本传
（xts-卷201/202/203 全检，仅卷202 萧颖士传一句提到他）——「两史并列升 KNOWN」
的标准用不上；KNOWN 只给旧传+全唐詩卷首叙**同记且逐字一致**的事实（梓州射洪人、
为武攸宜管记、忧愤而卒）；只见于卷首叙的碎琴段不升，各记一段的（王適之叹只有
旧传有、碎琴只有卷首叙有）并列照登。

WORLD 层是阶段 D 第一个**安史乱之外的战事**：通鉴卷205/206——万岁通天元年
（丙申，696）「營州契丹松漠都督李盡忠、歸誠州刺史孫萬榮舉兵反，攻陷營州」、
神功元年（丁酉，697）「武攸宜軍漁陽…不敢進。契丹乘勝寇幽州」、同年
「甲午，孫萬榮為奴所殺」「制以契丹初平」。新立事件实体
event-tang-khitans-invasion（营州契丹之乱，696–697）。

poetry_citation 主键 (claim_id, source_id)——**同一 claim 对同一来源只有一行**：
同一 claim 的多处引文用 join() 以「……」相连成一行（V027 已有先例），
绝不出现两行同主键（V028 初稿就犯了这个错，重写时修正；audit 加了断言）。

用法: python3 -I emit_v028.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/登幽州臺歌.txt').read_text(encoding='utf-8')
V83 = pathlib.Path('/tmp/src-dl/quantangshi/vol083.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190中.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
TJ5 = pathlib.Path('/tmp/src-dl/tongjian/tj-205.txt').read_text(encoding='utf-8')
TJ6 = pathlib.Path('/tmp/src-dl/tongjian/tj-206.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；锚不唯一即中止） ----------
WS_L12 = slice_between(WS, '前不見古人，後不見來者。', '前不見古人，後不見來者。', 'ws起二句')
WS_L34 = slice_between(WS, '念天地之悠悠，獨愴然而涕下。', '念天地之悠悠，獨愴然而涕下。', 'ws末二句')
WS_HDR = slice_between(WS, '| title    = 登幽州臺歌\n| section  =\n| author   = 陳子昂',
                       '| author   = 陳子昂', 'ws header title+author')
V83_NOTE = slice_between(V83, "'''陳子昂'''", "'''陳子昂'''", 'vol83 卷首作者注')
V83_ANCHOR = slice_between(V83, '==[[登幽州臺歌]]==', '{{:登幽州臺歌}}', 'vol83 锚点+转引用桩')
V83_HEAD = slice_between(V83, '陳子昂，字伯玉，梓州射洪人。少以富家子，尚氣決，好弋博，後遊鄉校，乃感悔修飭。初舉進士入京，不爲人知。',
                         '不爲人知。', '卷首叙前半(蜀人/入京不为人知)')
V83_QIN = slice_between(V83, '有賣胡琴者，價百萬，子昂顧左右，輦千緡市之。', '名滿都下。',
                        '卷首叙碎琴段')
V83_CAREER = slice_between(V83, '擢進士第。武后朝，爲靈臺正字。數上書言事，遷右拾遺。武攸宜北討，表爲管記，軍中文翰，皆委之子昂。父爲縣令段簡所辱，子昂聞之，遽還鄉里，簡乃因事收繫獄中，憂憤而卒。',
                          '憂憤而卒。', '卷首叙仕履段(靈臺正字—右拾遺—管記—忧愤而卒)')
V83_PUSH = slice_between(V83, '唐興，文章承徐庾餘風，駢麗穠縟，子昂橫制頹波，始歸雅正，李杜以下，咸推宗之。集十卷，今編詩二卷。',
                         '今編詩二卷。', '卷首叙推宗语')
JTS_JIA = slice_between(JTS, '陳子昂，梓州射洪人。家世富豪。', '家世富豪。', '旧传籍贯段')
JTS_WEN = slice_between(JTS, '初爲《感遇詩》三十首，京兆司功王適見而驚曰：「此子必爲天下文宗矣！」由是知名。',
                        '由是知名。', '旧传感遇诗/王适叹')
JTS_LIN = slice_between(JTS, '則天召見，奇其對，拜麟臺正字。', '拜麟臺正字。', '旧传召见拜官句')
JTS_CANMOU = slice_between(JTS, '俄授麟臺正字。武攸宜統軍北討契丹，以子昂爲管記，軍中文翰皆委之。',
                          '軍中文翰皆委之。', '旧传管记段')
JTS_SI = slice_between(JTS, '子昂父在鄉，爲縣令段簡所辱，子昂聞之，遽還鄉里。簡乃因事收繫獄中，憂憤而卒，時年四十餘。',
                       '時年四十餘。', '旧传忧愤卒段')
JTS_REP = slice_between(JTS, '子昂褊躁無威儀，然文詞宏麗，甚爲當時所重。有集十卷，友人黃門侍郎盧藏用爲之序，盛行於代。',
                        '盛行於代。', '旧传史臣语(褊躁/文词宏丽/卢藏用序)')
XTS_XY = slice_between(XTS, '所許可當世者，陳子昂、富嘉謨、盧藏用之文辭，董南事、孔述睿之博學而已。',
                       '之博學而已。', '新唐书萧颖士传提及陈子昂(本传不立的旁证)')
TJ5_TITLE = slice_between(TJ5, '則天順聖皇后中之上萬歲通天元年（丙申，公元六九六年）',
                          '公元六九六年）', '通鉴205卷696年标题')
TJ5_START = slice_between(TJ5, '夏，五月，壬子，營州契丹松漠都督李盡忠、歸誠州刺史孫萬榮舉兵反，攻陷營州',
                          '殺都督趙文翽。', '通鉴696起兵陷营州')
TJ5_XJ = slice_between(TJ5, '契丹伏兵於中道邀之，全軍皆沒。', '契丹伏兵於中道邀之，全軍皆沒。',
                       '通鉴696硖石谷唐兵大败全军没')
TJ5_QD = slice_between(TJ5, '以同州刺史建安王武攸宜為右武威衛大將軍，充清邊道行軍大總管，以討契丹。',
                       '以討契丹。', '通鉴696武攸宜出师')
TJ5_CAN = slice_between(TJ5, '右拾遺陳子昂為攸宜府參謀，上疏曰：「恩制免天下罪人及募諸色奴充兵討擊契丹，此乃捷急之計，非天子之兵。',
                        '非天子之兵。', '通鉴陈子昂攸宜府参谋上疏')
TJ6_TITLE = slice_between(TJ6, '則天順聖皇后中之下神功元年（丁酉，公元六九七年）',
                          '公元六九七年）', '通鉴206卷697年标题')
TJ6_XJ = slice_between(TJ6, '春，三月，戊申，清邊道總管王孝傑、蘇宏暉等將兵十七萬與孫萬榮戰於東硤石谷，唐兵大敗，孝傑死之。',
                        '孝傑死之。', '通鉴697东硖石谷王孝傑死')
TJ6_YY = slice_between(TJ6, '武攸宜軍漁陽，聞孝傑等敗沒，軍中震恐，不敢進。契丹乘勝寇幽州，攻陷城邑，剽掠吏民，攸宜遣將擊之，不克。',
                        '攸宜遣將擊之，不克。', '通鉴697攸宜军渔阳不敢进/契丹寇幽州')
# 凯旋条（庚午，武攸宜自幽州凱旋。）不入引文——引它需连上下文，且渔阳段已证统帅败怯全貌；
# 事件 summary 里「旋凯」的说法因此不写（summary 只写引文可指的事）。
TJ6_END1 = slice_between(TJ6, '甲午，孫萬榮為奴所殺。', '甲午，孫萬榮為奴所殺。', '通鉴697孙万荣见杀')
TJ6_END2 = slice_between(TJ6, '制以契丹初平', '制以契丹初平', '通鉴697制以契丹初平')

BG = {
    'bg-yz-scene': (
        '四句、二十五个字，没有题目里的故事：「前不見古人，後不見來者。念天地之悠悠，獨愴然而涕下。」'
        '往前看不见古人，往后看不见来者，天地无穷，一个人站在高处哭了。\n'
        '这首诗「为什么写」，本传里没有一句话直接回答——本传甚至通篇没提这首诗（见第 7、8 句那层）。'
        '能核到的只有一件事：他登的幽州，在通鉴里有一段对得上年月的战事。'),
    'bg-yz-city': (
        '幽州是战区的城。通鉴万岁通天元年（丙申，公元六九六年）记朝廷'
        '「以同州刺史建安王武攸宜為右武威衛大將軍，充清邊道行軍大總管，以討契丹」；'
        '神功元年（丁酉，公元六九七年）记「武攸宜軍漁陽，聞孝傑等敗沒，軍中震恐，不敢進。'
        '契丹乘勝寇幽州，攻陷城邑，剽掠吏民，攸宜遣將擊之，不克」——幽州被契丹攻陷过，'
        '主帅在渔阳按兵不动。\n'
        '台的建制（黄金台、蓟北楼，都是后世说法）本地核不到，不写。核得到的是：'
        '陈子昂就在这支军队里——旧传「武攸宜統軍北討契丹，以子昂爲管記，軍中文翰皆委之」，'
        '通鉴「右拾遺陳子昂為攸宜府參謀，上疏曰」还留了他反对以罪人奴兵凑数的一段原话。'),
    'bg-yz-world': (
        '这是安史之乱六十年前的事，本库的事件线第一次走到乱前：万岁通天元年（丙申，公元六九六年）'
        '「營州契丹松漠都督李盡忠、歸誠州刺史孫萬榮舉兵反，攻陷營州」，当年'
        '「契丹伏兵於中道邀之，全軍皆沒」；神功元年（丁酉，公元六九七年）三月'
        '「清邊道總管王孝傑、蘇宏暉等將兵十七萬與孫萬榮戰於東硤石谷，唐兵大敗，孝傑死之」，'
        '同年「甲午，孫萬榮為奴所殺」，朝廷随即「制以契丹初平」论功行赏——'
        '本迁移把这两年立成事件线锚点 event-tang-khitans-invasion。\n'
        '幽州城在这两年里是前线。但要说清边界：通鉴记的是战场，本传记的是他在那支军队里，'
        '没有任何一条史料说这首诗为这场战事而作——并置是给读者的坐标，不是因果。'),
    'bg-yz-person': (
        '陈子昂，梓州射洪人——旧传与全唐詩卷首叙同记。旧传记他早年：'
        '「初爲《感遇詩》三十首，京兆司功王適見而驚曰：『此子必爲天下文宗矣！』由是知名」；'
        '卷首叙另记一段碎琴扬名的市井传说（「有賣胡琴者…一日之內，名滿都下」），'
        '两源各记一路，不合并。\n'
        '仕履核得而不矛盾的：则天召见拜麟臺正字（旧传），数上书迁右拾遗（卷首叙），'
        '武攸宜北讨表为管记（两源同记），父被县令段簡所辱、闻之还乡、被收繫狱中、'
        '「憂憤而卒，時年四十餘」（两源同记）。\n'
        '边界两条硬杠：新唐书文艺传**没有**陈子昂本传（卷201/202/203 全检，仅萧颖士传一句'
        '「所許可當世者，陳子昂、富嘉謨、盧藏用之文辭」可作他身后的旁证）——所以凡只见于'
        '《全唐詩》卷首叙的说法（如碎琴）一律不升；而本传通篇不提《登幽州臺歌》，'
        '这首诗作于何年、是否作于北征幕中，**两唐书与通鉴无一字**——不铸系年。'),
}
CLAIMS = {
    'claim-bg-yz-scene': (
        'INTERPRETATION', 'LIKELY',
        '四句本文的内证（古今/天地的对举）；写作缘由本传无一字，正文只给坐标不给因果，已声明边界。'),
    'claim-bg-yz-city': (
        'FACT', 'LIKELY',
        '696 武攸宜出师、其在军中参谋上疏、697 幽州陷落诸条通鉴逐字（年标题归属已分记）；'
        '旧传管记句逐字；台之建制核不到零引用。'),
    'claim-bg-yz-world': (
        'FACT', 'LIKELY',
        '起于 696「舉兵反攻陷營州」与全军没、697 东硖石谷王孝傑死、孙万荣见杀、契丹初平，'
        '通鉴卷205/206 逐字（年标题归属已分记）；'
        '诗与战事无逐字因果关联——正文只并置不断言，事件实体挂战事本体不挂诗。'),
    'claim-bg-yz-person': (
        'FACT', 'KNOWN',
        '籍贯（梓州射洪）、管记北讨、忧愤而卒——旧传与全唐詩卷首叙逐字一致处升 KNOWN；'
        'certainty 不覆盖只见于卷首叙的碎琴段、不覆盖任何系年；'
        '新唐书无本传（xts-卷201/202/203 实测）——两史并列标准用不上，单传边界写明。'),
}
# 主键 (claim_id, source_id) 唯一：同 claim 同来源多处引文一律 join() 成一行。
CITATIONS = [
    ('claim-bg-yz-scene', 'source-ws-t300-002',
     '页面 登幽州臺歌（起二句+末二句逐字以「……」相連；页内实测无 {{另|}} 异文标记，'
     '四句与 V018 入库正文全同；全文另见 V018 claim-t300-002-text 引文）',
     join(WS_L12, WS_L34)),
    ('claim-bg-yz-city', 'source-zizhi-tongjian-events',
     '通鑑卷二百零五·万岁通天元年标题+武攸宜出师条+陈子昂参谋上疏句＋卷二百零六·'
     '神功元年标题+渔阳不敢进/幽州陷落条；五段以「……」相連，年標題歸屬已分記',
     join(TJ5_TITLE, TJ5_QD, TJ5_CAN, TJ6_TITLE, TJ6_YY)),
    ('claim-bg-yz-city', 'source-jiutangshu-wenyuan',
     '卷一百九十中·文苑中·陈子昂传（管记段——军中文翰皆委之）',
     JTS_CANMOU),
    ('claim-bg-yz-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百零五·万岁通天元年标题+起兵陷营州条+硖石谷全军没句＋卷二百零六·'
     '神功元年标题+东硖石谷孝傑死条+孙万荣见杀句+制以契丹初平短语；'
     '七段以「……」相連，年標題歸屬已分記（事件线战事本体证据；诗不挂 written_during）',
     join(TJ5_TITLE, TJ5_START, TJ5_XJ, TJ6_TITLE, TJ6_XJ, TJ6_END1, TJ6_END2)),
    ('claim-bg-yz-person', 'source-ws-t300-002',
     '页面 登幽州臺歌（header title+author 字段逐字——署名第三证，V018 T1_TITLE 路数的逐字切片）',
     WS_HDR),
    ('claim-bg-yz-person', 'source-jiutangshu-wenyuan',
     '卷一百九十中·文苑中·陈子昂传（籍贯段＋感遇诗/王适叹＋召见拜官句＋管记段＋忧愤卒段＋史臣语；'
     '六段以「……」相連，出处同卷同传）',
     join(JTS_JIA, JTS_WEN, JTS_LIN, JTS_CANMOU, JTS_SI, JTS_REP)),
    ('claim-bg-yz-person', 'source-quantangshi-083',
     '页面 全唐詩/卷083（卷首作者注＋本诗锚点与转引用桩＋卷首叙前半/碎琴段/仕履段/推宗语；'
     '碎琴只见于此源不升 KNOWN，与旧传同记处作并列第二证；卷页无正文，正文证据在诗页；'
     '六段以「……」相連，出处同卷）',
     join(V83_NOTE, V83_ANCHOR, V83_HEAD, V83_QIN, V83_CAREER, V83_PUSH)),
    ('claim-bg-yz-person', 'source-xintangshu-wenyi',
     '卷二百二·文藝中·萧颖士传（新唐书无陈子昂本传的唯一旁证——身后推重；'
     '本层单传边界的出处，升证反用）',
     XTS_XY),
]
BG_LINES = {'bg-yz-scene': (1, 2), 'bg-yz-city': (3, 4),
            'bg-yz-world': (5, 6), 'bg-yz-person': (7, 8)}
BG_AUDIENCE = {'bg-yz-scene': 'PRIMARY', 'bg-yz-city': 'JUNIOR',
               'bg-yz-world': 'SENIOR', 'bg-yz-person': 'JUNIOR'}
BG_TITLES = {'bg-yz-scene': '眼前：二十五个字的一哭',
             'bg-yz-city': '这座城：契丹攻陷过的幽州',
             'bg-yz-world': '这个天下：安史乱前的六十年',
             'bg-yz-person': '这个人：本传没提这首诗'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 10 首）；史实句均有逐字引证；'
                 '系年全部缺席——两唐书与通鉴无一字提及此诗；新唐书无本传为单传边界。' for k in BG}

EVENT_ROW = {
    'id': 'event-tang-khitans-invasion',
    'entity_type': 'EVENT', 'slug': 'khitans-invasion', 'title': '营州契丹之乱（李尽忠、孙万荣）',
    'summary': '万岁通天元年（696）营州契丹松漠都督李尽忠、归诚州刺史孙万荣举兵反，攻陷营州；'
               '唐军讨之于硖石谷，全军皆没。神功元年（697）王孝傑十七万军覆于东硖石谷，'
               '武攸宜军渔阳不敢进，幽州为契丹所陷；同年孙万荣为奴所杀，制以契丹初平。',
    'start_year': 696, 'end_year': 697, 'time_precision': 'RANGE',
}
EVENT_TIME_VALUE = '696..697 (RANGE) 起：通鉴卷205 万岁通天元年（丙申，公元六九六年）' \
                   '「李盡忠、孫萬榮舉兵反，攻陷營州」；讫：卷206 神功元年（丁酉，公元六九七年）' \
                   '「孫萬榮為奴所殺」「制以契丹初平」——起讫同年标题直证'
EVENT_TIME_CLAIM = 'claim-event-tang-khitans-invasion-time'
EVENT_CIT = ('通鑑卷二百零五·万岁通天元年标题+起兵陷营州条+硖石谷全军没句＋'
             '卷二百零六·神功元年标题+东硖石谷孝傑死条+孙万荣见杀句+制以契丹初平短语；'
             '六段以「……」相連，年標題歸屬已分記',
             join(TJ5_TITLE, TJ5_START, TJ5_XJ, TJ6_TITLE, TJ6_XJ, TJ6_END1, TJ6_END2))


def guard(table, cols, rows, match_expr):
    def lit(v):
        if v is None:
            return 'NULL'
        if isinstance(v, int):   # EVENT 行的 start_year/end_year（V027 无整数列，V028 首遇）
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
    A("""-- V028：陳子昂《登幽州臺歌》(work-t300-002) 四层背景 + 乱前事件线首点（阶段 D 第 10 首）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V018 已执行（work-t300-002 与其 text-work-t300-002-ws、source-ws-t300-002
--       都是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi 是 V016 的行；
--       source-zizhi-tongjian-events 是 V015 的行——本迁移在同一通鉴来源上增引卷205/206，不另开行）。
--
-- 数据源（可复现）：emit_v028.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/登幽州臺歌.txt（页内实测无 {{另|}} 异文——如实写明）、資治通鑑卷205/206、
--   全唐詩卷083（卷首叙+锚点+转引用桩）、舊唐書卷190中、新唐書卷202（仅作无本传的旁证）。
--
-- 做：1 个新 source 登记（全唐詩卷083，PENDING——登记不等于核验）+
--   1 个新 EVENT 实体（营州契丹之乱，V015 同构）+ 其 time.span claim（KNOWN，通鉴年标题直证）
--   及其 1 组逐字引用（主键唯一）+
--   4 BACKGROUND content/claim/background + 8 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（scene→1,2｜city→3,4｜world→5,6｜person→7,8，绑 text-work-t300-002-ws）。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「本传没提这首诗」）：
--   * 两唐书与通鉴**无一字**提及《登幽州臺歌》——北征幕中作诗是后世年谱说，本地核不到：
--     time.span/event.name/written_during 一个都不造（V023/V024/V027 形状断言 + 本文件
--     零 relation 断言守死）；事件实体挂战事本体（696–697 通鉴年标题直证 KNOWN），不向诗外溢；
--   * 新唐书文艺传无陈子昂本传（xts-卷201/202/203 全检索，仅卷202 萧颖士传一句提及）——
--     阶段 D 首个单传诗人：凡只见于全唐詩卷首叙者（碎琴）不升，KNOWN 只给两源同记处；
--   * ws 诗页快照实测无页内异文（无 {{另|}}，四句与 V018 入库正文全同）——没有异文也登记为「核过」，
--     tang300-variants.md 不开「无」行；
--   * 台的建制（黄金台/蓟北楼后世说）零引用不写。
--
-- 干支对账：696=丙申、697=丁酉（audit-migrations.py 检查4 同源复核）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 27，不含 28
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-yz-%' OR id='event-tang-khitans-invasion';  -- 空
--   SELECT id FROM poetry_text_version WHERE id='text-work-t300-002-ws';  -- 恰 1 行（V018 已执行）
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-083';     -- 空
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-yz-%';        -- 4
--   SELECT COUNT(*) FROM poetry_content WHERE id='event-tang-khitans-invasion';  -- 1
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-002';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-yz-person';   -- KNOWN
--   SELECT certainty FROM poetry_claim WHERE id='claim-event-tang-khitans-invasion-time';  -- KNOWN
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-002'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-002';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id IN ('claim-bg-yz-scene','claim-bg-yz-city','claim-bg-yz-world',
--                        'claim-bg-yz-person','claim-event-tang-khitans-invasion-time')
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V028_rollback.sql（按 id 全枚举删除；不动 V018 的任何行，不动共用通鉴/两唐书来源行）
START TRANSACTION;""")

    A('\n-- ---------- 0. 来源登记（一律 PENDING：登记不等于核验） ----------')
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            [{'id': 'source-quantangshi-083',
              'title': '《全唐詩》全唐詩/卷083（维基文库录入本）',
              'author': None,
              'edition': '全唐詩/卷083（维基文库《全唐詩》录入本）',
              'url': 'https://zh.wikisource.org/wiki/全唐詩/卷083',
              'rights_note': '维基文库录入本，公有领域古籍。本卷为陈子昂诗卷，卷首 Collection header '
                             "notes 标作者 '''陳子昂''' 并有整段卷首叙（旧传之外独立的第二传状来源）。"
                             '本诗条目只有锚点+转引用桩，正文在诗页。本行由 emit_v028.py 对快照逐字定位。'
                             '核验状态保持 PENDING。',
              'verification_status': 'PENDING', 'source_kind': 'POETRY_COLLECTION',
              'reliability': 'HIGH'}],
            'x.id = t.id'))

    A('\n-- ---------- 1. 事件实体（阶段 D 首个安史乱前战事；V015 同构，通鉴年标题直证 KNOWN） ----------')
    A(guard('poetry_content',
            ['id', 'entity_type', 'slug', 'title', 'summary',
             'start_year', 'end_year', 'time_precision'],
            [EVENT_ROW], 'x.id = t.id'))
    A(guard('poetry_claim',
            ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            [{'id': EVENT_TIME_CLAIM, 'subject_id': EVENT_ROW['id'],
              'property_key': 'time.span', 'value_text': EVENT_TIME_VALUE,
              'claim_kind': 'FACT', 'certainty': 'KNOWN'}], 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': EVENT_ROW['id'], 'property_key': 'time.span',
              'claim_id': EVENT_TIME_CLAIM}],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))
    A('INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)\nSELECT * FROM (')
    A(f"SELECT {sql_s(EVENT_TIME_CLAIM)} AS claim_id, 'source-zizhi-tongjian-events' AS source_id, "
      f"{sql_s(EVENT_CIT[0])} AS locator, {sql_s(EVENT_CIT[1])} AS evidence_excerpt FROM DUAL")
    A(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_citation x '
      'WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);')

    A('\n-- ---------- 2. BACKGROUND content identities ----------')
    rows = [{'id': k, 'entity_type': 'BACKGROUND', 'slug': k[3:], 'title': BG_TITLES[k],
             'summary': BG_SUMMARY[k], 'time_precision': 'UNKNOWN'} for k in BG]
    A(guard('poetry_content', ['id', 'entity_type', 'slug', 'title', 'summary', 'time_precision'],
            rows, 'x.id = t.id'))

    A('\n-- ---------- 3. claims（主语=BACKGROUND content 行；claim id 带 claim- 前缀，V004 同款） ----------')
    crows = [{'id': k, 'subject_id': k.replace('claim-', '', 1), 'property_key': 'context',
              'value_text': v[2], 'claim_kind': v[0], 'certainty': v[1]} for k, v in CLAIMS.items()]
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            crows, 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': k.replace('claim-', '', 1), 'property_key': 'context', 'claim_id': k}
             for k in CLAIMS],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))

    A('\n-- ---------- 4. background rows ----------')
    brows = [{'id': k, 'work_id': 'work-t300-002',
              'layer': {'bg-yz-scene': 'SCENE', 'bg-yz-city': 'CITY',
                        'bg-yz-world': 'WORLD', 'bg-yz-person': 'PERSON'}[k],
              'body_text': BG[k], 'audience': BG_AUDIENCE[k], 'claim_id': 'claim-' + k} for k in BG]
    A(guard('poetry_background', ['id', 'work_id', 'layer', 'body_text', 'audience', 'claim_id'],
            brows, 'x.id = t.id'))

    A('\n-- ---------- 5. 逐字引文（(claim,source) 主键每对恰一行） ----------')
    L.append('INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(c)} AS claim_id, {sql_s(s)} AS source_id, {sql_s(loc)} AS locator, "
        f"{sql_s(ex)} AS evidence_excerpt FROM DUAL"
        for c, s, loc, ex in CITATIONS))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_citation x '
             'WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);')

    A('\n-- ---------- 6. background_line ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-002-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 7. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 28, 'chen-zi-ang deng-youzhou-tai-ge background layers plus the stage-D first pre-An-Shi event anchor (inserts-only): new EVENT entity for the Yingzhou Khitan revolt 696-697 with KNOWN time.span straight from tongjian ju205/206 year titles (rising and fall of Yingzhou in 696; Wang Xiaojie buried at East Xiashi Valley, Wu Zhuyi stalled at Yuyang, Youzhou fallen, Sun Wanrong killed by his own slave and the edict declaring the Khitans pacified, all in 697); the poem itself deliberately gets NO time.span, NO event.name, NO written_during and zero relation rows -- neither Tang history nor the Zizhi Tongjian mentions this poem anywhere, the camp-composition story is a later chronology claim not locally verifiable; first single-biography poet of stage D (Xin Tang Shu has no biography of Chen Zi-ang -- verified by full scan of ju201-203, one passing mention in the Xiao Yingshi entry only): KNOWN covers only facts recorded word-for-word by both the JTS biography and the Quan Tang Shi volume-headnote (the qin-smashing story appears in the headnote alone and is NOT promoted); ws page verified to carry no inline variants -- recorded as checked-and-clean'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 28);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V028 精确回滚：只删 V028 插入的行（id 全枚举）。work-t300-002 本体是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi/tongjian-events/source-ws-t300-002）都不删；',
         '-- V028 零 poetry_relation 行，故无需删 relation。',
         'START TRANSACTION;']
    cids = list(CLAIMS) + [EVENT_TIME_CLAIM]

    def dels(table, col, vals, chunk=40):
        for i in range(0, len(vals), chunk):
            L.append(f'DELETE FROM {table} WHERE {col} IN ('
                     + ', '.join(sql_s(v) for v in vals[i:i + chunk]) + ');')
    dels('poetry_claim_selection', 'claim_id', cids)
    dels('poetry_citation', 'claim_id', cids)
    dels('poetry_background_line', 'background_id', list(BG))
    dels('poetry_background', 'id', list(BG))
    dels('poetry_claim', 'id', cids)
    dels('poetry_content', 'id', list(BG) + [EVENT_ROW['id']])
    dels('poetry_source', 'id', ['source-quantangshi-083'])
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 28;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (WS_L12, WS_L34, WS_HDR, V83_NOTE, V83_ANCHOR, V83_HEAD, V83_QIN, V83_CAREER, V83_PUSH,
              JTS_JIA, JTS_WEN, JTS_LIN, JTS_CANMOU, JTS_SI, JTS_REP, XTS_XY,
              TJ5_TITLE, TJ5_START, TJ5_XJ, TJ5_QD, TJ5_CAN,
              TJ6_TITLE, TJ6_XJ, TJ6_YY, TJ6_END1, TJ6_END2):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    # poetry_citation 主键 (claim_id, source_id)：本文件内每对恰出现一次
    pairs = [(c, s) for c, s, _, _ in CITATIONS] + [(EVENT_TIME_CLAIM, 'source-zizhi-tongjian-events')]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    # 有意的形状断言（V023/V024/V027 同款 + V028 新增零 relation 断言）：
    # 只查「值 AS 列名」形状，不查裸词；event 本体的 time.span 合法（subject=event），
    # 所以诗的缺席用「主语+property_key 相邻」与 relation 全表双断言。
    if "'written_during' AS predicate" in sql:
        bad.append("V028 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V028 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-002' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V028 有意不给诗铸 {pk}，但该主语组合出现了')
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
    loc, ex = EVENT_CIT
    if len(loc) > 300 or len(ex) > 500:
        bad.append(f'event citation 宽度超限 ({len(loc)}B/{len(ex)}B)')
    if len(EVENT_ROW['summary']) > 500 or len(EVENT_TIME_VALUE) > 500:
        bad.append('event summary/time value 宽度超限')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 26 切片逐字过审；'
              f'(claim,source) 主键 9 对唯一；诗 time.span/event.name/written_during/relation '
              f'缺席已断言；citation 宽度过审')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
