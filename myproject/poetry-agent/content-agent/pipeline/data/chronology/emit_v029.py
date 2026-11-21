#!/usr/bin/env python3
"""阶段 D 第 11 首：生成 V029——宋之問《題大庾嶺北驛》(work-t300-234, V018 已立) 四层背景。

「为什么写」的形状第三次成立（前两次：V019 春望、V014/V019 系列）：不是注本系年、不是诗会内证，
而是**本传直接把贬途交出来**——旧传「及易之等敗，左遷瀧州參軍」「配徙欽州。先天中，賜死於徙所」，
并且给出本地唯一一条「路上写诗」的直接证据：「之問再被竄謫，經途江、嶺，所有篇詠，傳布遠近」。
詩題「題大庾嶺北驛」= 题在岭北驿站——贬、过岭、北望，因果由不得一点注家插手。

但系年仍旧缺席，形状同 V027（第三次应用）：他**两次**南贬过岭南道（705 泷州、710 钦州），
两次都北起南行过大庾岭，诗在哪一程写的核不到——年谱定 705，本地核不到不采信；
710 程在景云，挂 written_during→神龍政变(705) 是半证据断言。
time.span / event.name / written_during 全部缺席 + 零 relation（V028 断言同款）。

PERSON 层第一次写满三源对质：告发王同皎一事，旧传/新传指**宋之问自己**「令兄子发其事以自赎」，
通鉴指**其弟宋之悌**「密遣其子昙…欲以自赎」——三源两说逐字并列不裁决，此节不升 KNOWN；
KNOWN 只给三源一致的贬岭表/流钦州/赐死。籍贯虢州弘农(旧)vs 汾州(新) 并列。
新传记赐死细节「之問得詔震汗，東西步，不引決…乃飲食洗沐就死」——全库最活的一段。

本迁移顺带修一处 V018 数据缺陷（头注 §0.5）：text-work-t300-234-ws 的 line_seq 3 误把
四句并一行（24 字），8 句只落 5 行；V029 在同一事务里删 5 行插 8 行（逐字对 ws 诗页），
回滚精确恢复 V018 原 5 行。全库扫描此缺陷只有 234/291 两例（291 的修复另迁移处理——
291 有页内异文 {{另|}} 未登记，先登记后修形，顺序不可反）。

用法: python3 -I emit_v029.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/題大庾嶺北驛.txt').read_text(encoding='utf-8')
V52 = pathlib.Path('/tmp/src-dl/quantangshi/vol052.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190中.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')
TJ8 = pathlib.Path('/tmp/src-dl/tongjian/tj-208.txt').read_text(encoding='utf-8')
TJ9 = pathlib.Path('/tmp/src-dl/tongjian/tj-209.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；锚不唯一即中止） ----------
WS_L12 = slice_between(WS, '陽月南飛雁，傳聞至此回。', '陽月南飛雁，傳聞至此回。', 'ws起二句(雁回)')
WS_L34 = slice_between(WS, '我行殊未已，何日復歸來？', '我行殊未已，何日復歸來？', 'ws二联(人行)')
WS_L56 = slice_between(WS, '江靜潮初落，林昏瘴不開。', '江靜潮初落，林昏瘴不開。', 'ws三联(岭南物象)')
WS_L78 = slice_between(WS, '明朝望鄉處，應見隴頭梅。', '明朝望鄉處，應見隴頭梅。', 'ws尾联(北望)')
WS_HDR = slice_between(WS, '| title    = 題大庾嶺北驛\n| section  =\n| author   = 宋之問',
                       '| author   = 宋之問', 'ws header title+author')
V52_NOTE = slice_between(V52, "'''宋之問'''", "'''宋之問'''", 'vol52 卷首作者注')
V52_ANCHOR = slice_between(V52, '==[[題大庾嶺北驛]]==', '{{:題大庾嶺北驛}}', 'vol52 锚点+转引用桩')
JTS_HEAD = slice_between(JTS, '宋之問，虢州弘農人。', '宋之問，虢州弘農人。', '旧传籍贯(虢州弘農)')
JTS_JINPAO = slice_between(JTS, '則天以錦袍賜之。及之問詩成，則天稱其詞愈高，奪虬錦袍以賞之。',
                          '奪虬錦袍以賞之。', '旧传夺锦袍')
JTS_FU = slice_between(JTS, '易之兄弟雅愛其才，之問亦傾附焉。', '易之兄弟雅愛其才，之問亦傾附焉。',
                       '旧传附易之')
JTS_LONG = slice_between(JTS, '及易之等敗，左遷瀧州參軍。未幾，逃還，匿於洛陽人張仲之家。',
                         '匿於洛陽人張仲之家。', '旧传泷州贬+逃还(窗口一 705)')
JTS_GAO = slice_between(JTS, '仲之與駙馬都尉王同皎等謀殺武三思，之問令兄子發其事以自贖。及同皎等獲罪，起之問爲鴻臚主薄，由是深爲義士所譏。',
                        '由是深爲義士所譏。', '旧传告发段(之问令兄子)')
JTS_SI = slice_between(JTS, '睿宗即位，以之問嘗附張易之、武三思，配徙欽州。先天中，賜死於徙所。',
                       '賜死於徙所。', '旧传钦州流+赐死')
JTS_SHI = slice_between(JTS, '之問再被竄謫，經途江、嶺，所有篇詠，傳布遠近。', '傳布遠近。',
                        '旧传路上写诗直证')
XTS_HEAD = slice_between(XTS, '宋之問，字延清，一名少連，汾州人。', '汾州人。', '新传籍贯(汾州)')
XTS_JINPAO = slice_between(XTS, '后賜錦袍，之問俄頃獻，后覽之嗟賞，更奪袍以賜。', '更奪袍以賜。',
                           '新传夺锦袍')
XTS_LONG = slice_between(XTS, '及敗，貶瀧州，朝隱崖州，並參軍事。', '並參軍事。',
                         '新传泷州贬(窗口一 705；与朝隐同句)')
XTS_GAO = slice_between(XTS, '仲之與王同皎謀殺三思安王室，之問得其實，令兄子曇與冉祖雍上急變，因丐贖罪，由是擢鴻臚主簿，天下醜其行。',
                        '天下醜其行。', '新传告发段(之问令兄子昙)')
XTS_LIU = slice_between(XTS, '睿宗立，以獪險盈惡詔流欽州。', '詔流欽州。', '新传钦州流(窗口二 710)')
XTS_SI = slice_between(XTS, '之問得詔震汗，東西步，不引決。', '不引決。', '新传赐死细节一')
XTS_SI2 = slice_between(XTS, '乃飲食洗沐就死。', '乃飲食洗沐就死。', '新传赐死细节二')
XTS_SHENSONG = slice_between(XTS, '及之問、沈佺期，又加靡麗，回忌聲病，約句准篇，如錦繡成文，學者宗之，號為「沈宋」。',
                             '號為「沈宋」。', '新传沈宋定评')
TJ8_TITLE = slice_between(TJ8, '=== 中宗大和大聖大昭孝皇帝中神龍元年（乙巳，公元七零五年）===',
                          '神龍元年（乙巳，公元七零五年）===', '通鉴208卷705年标题(标准形)')
TJ8_FB = slice_between(TJ8, '初，少府監丞弘農宋之問及弟兗州司倉之遜皆坐附會張易之貶嶺南，逃歸東都，匿於友人光祿卿、駙馬都尉王同皎家。',
                       '欲以自贖。', '通鉴705标题下追述(贬岭南+告发系于弟之悌)')
TJ9_TITLE = slice_between(TJ9, '===中宗大和大聖大昭孝皇帝下景雲元年{{*|庚戌，西元七一〇年}}===',
                          '西元七一〇年}}===', '通鉴209卷710年标题(变体形{{*|干支，西元…}})')
TJ9_LIU = slice_between(TJ9, '越州長史宋之問，饒州刺史冉祖雍，坐諂附韋、武，皆流嶺表。',
                        '皆流嶺表。', '通鉴710流岭表条')

# ---------- text_line 修复（V018 数据缺陷：234 的 line_seq 3 误并四句为一行） ----------
LINES_OLD = {1: '陽月南飛雁，', 2: '傳聞至此回。',
             3: '我行殊未已，何日復歸來？江靜潮初落，林昏瘴不開。',
             4: '明朝望鄉處，', 5: '應見隴頭梅。'}
LINES_NEW = {1: '陽月南飛雁，', 2: '傳聞至此回。', 3: '我行殊未已，', 4: '何日復歸來？',
             5: '江靜潮初落，', 6: '林昏瘴不開。', 7: '明朝望鄉處，', 8: '應見隴頭梅。'}
for n, t in LINES_NEW.items():
    src_line = f'{t}'
    if t not in WS and t.replace('，', '').replace('。', '').replace('？', '') not in WS:
        raise SystemExit(f'新行 {n} 不在 ws 快照: {t}')

BG = {
    'bg-dy-scene': (
        '诗的开头是一个对比：「陽月南飛雁，傳聞至此回。」——十月的大雁往南飞，听说到了大庾岭就掉头；'
        '「我行殊未已，何日復歸來？」——雁回，人却还要往南走，归期无人能答。\n'
        '题目就是动作：「題」大庾嶺「北驛」——这首诗是题在岭北驿站墙上的。'
        '他为什么在这里：贬官。哪一程贬的，两程都对得上（见第 5、6 句那层），'
        '但「贬、过岭、北望」这个为什么，本传一个字都不用多给。'),
    'bg-dy-city': (
        '岭就是界线，界线是诗本文立起来的：大雁到这里回头，人过了岭就是另一片天——'
        '「江靜潮初落，林昏瘴不開」，潮水安静落下去，密林的瘴气散不开，这是他亲眼看见的岭南。\n'
        '路线两史各记一笔：旧唐书「及易之等敗，左遷瀧州參軍」（泷州在岭南道），'
        '新唐书「及敗，貶瀧州，朝隱崖州，並參軍事」（与阎朝隐同句受贬）。'
        '北望的那一眼在尾联：「明朝望鄉處，應見隴頭梅」——望乡只能看见岭上的梅，'
        '岭南北之界，梅信之说本库核不到出处，照诗句原文，不补故事。'),
    'bg-dy-world': (
        '通鉴把这条政治线框在两个年标题里。神龙元年（乙巳，公元七零五年）标题下的追述：'
        '「初，少府監丞弘農宋之問及弟兗州司倉之遜皆坐附會張易之貶嶺南，逃歸東都，'
        '匿於友人光祿卿、駙馬都尉王同皎家」——他是张易之集团倒台的余党，这是第一次。\n'
        '景云元年（庚戌，公元七一〇年）：「越州長史宋之問，饒州刺史冉祖雍，坐諂附韋、武，'
        '皆流嶺表」——睿宗即位，他又因为依附韦后、武三思流了一次岭表。两次南贬之间，'
        '还有告发王同皎、靠太平公主起用、又因赃污外放的全套起落。旧传只用九个字收他的结局：'
        '「配徙欽州。先天中，賜死於徙所」。\n'
        '边界：这首诗可以属 705 程，也可以属 710 程——两程都过岭，核不到哪一程。'
        '年谱定 705，本地核不到不采信；两窗口并列，不铸系年。'),
    'bg-dy-person': (
        '这个人的名声和下场，三源对质着看。\n'
        '籍贯两史各说一座：旧传「虢州弘農人」，新传「汾州人」——并列。\n'
        '夺锦袍的快事两传各记一段（旧传「奪虬錦袍以賞之」、新传「更奪袍以賜」）；'
        '新传有全库最活的一笔，记他接到赐死诏的样子：「之問得詔震汗，東西步，不引決」，'
        '冉祖雍请使者宽限时他「荒悸不能處家事」，被祖雍斥了一句「奈何遲回邪」，'
        '「乃飲食洗沐就死」。\n'
        '最要紧的官司在告发：王同皎谋诛武三思，旧传「之問令兄子發其事以自贖…由是深爲義士所譏」，'
        '新传「之問得其實，令兄子曇與冉祖雍上急變，因丐贖罪…天下醜其行」——两传都指他自己告发求赎；'
        '通鉴却把告密记在弟弟头上：「之遜於簾下聞之，密遣其子曇及甥校書郎李悛告三思，欲以自贖」。'
        '三源两说，逐字并列不裁决——此节不升 KNOWN。\n'
        'KNOWN 只给三源一致的：附张易之贬岭南、睿宗立再流岭表、先天中赐死于徙所。\n'
        '诗人的地位新传有定评：「學者宗之，號為『沈宋』」；而旧传那九个字'
        '「之問再被竄謫，經途江、嶺，所有篇詠，傳布遠近」——路上写的诗传遍远近，'
        '这是本地史料里唯一一条说他一路都在写诗的直证。'),
}
CLAIMS = {
    'claim-bg-dy-scene': (
        'FACT', 'LIKELY',
        '题壁动作由题目（题+驿）与起联本文内证支撑；贬途由两史贬泷州逐字支撑；'
        '诗属哪一程贬不裁决（见 world 层）。'),
    'claim-bg-dy-city': (
        'FACT', 'LIKELY',
        '岭南物象为诗本文；贬泷州两史各记一笔；梅信典故核不到零引用，正文照诗句不补。'),
    'claim-bg-dy-world': (
        'FACT', 'LIKELY',
        '705 追述、710 流岭表两条通鉴逐字（年标题归属已分记；710 标题为 {{*|干支，西元…}} 变体形）；'
        '旧传结局九字逐字；两窗口并列不裁决、不铸诗 time.span、不挂 written_during。'),
    'claim-bg-dy-person': (
        'FACT', 'KNOWN',
        '附易之贬岭南、睿宗立流岭表、先天赐死——两史+通鉴一致处升 KNOWN；'
        '告发主谋三源两说（旧/新指之问，通鉴指其弟之悌）并列不裁决不升；'
        '籍贯两史各异并列不升；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-dy-scene', 'source-ws-t300-234',
     '页面 題大庾嶺北驛（起二句+二联逐字以「……」相連；页内实测无 {{另|}} 异文标记，'
     '八句与 V018 入库正文全同——V018 分行缺陷由本迁移 §0.5 修复；全文另见 V018 claim-t300-234-text 引文）',
     join(WS_L12, WS_L34)),
    ('claim-bg-dy-city', 'source-ws-t300-234',
     '页面 題大庾嶺北驛（三联+尾联逐字以「……」相連——瘴/潮为亲见岭南，梅为北望所见）',
     join(WS_L56, WS_L78)),
    ('claim-bg-dy-city', 'source-jiutangshu-wenyuan',
     '卷一百九十中·文苑中·宋之问传（泷州贬+逃还段）', JTS_LONG),
    ('claim-bg-dy-city', 'source-xintangshu-wenyi',
     '卷二百二·文藝中·宋之问传（贬泷州句——与阎朝隐同句，逐字照登）', XTS_LONG),
    ('claim-bg-dy-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百零八·神龍元年（乙巳，公元七零五年）标题+追述条（贬岭南、匿王同皎家、'
     '告发系于弟之悌）＋卷二百零九·景雲元年（庚戌，公元七一〇年）标题+流岭表条；'
     '四段以「……」相連，年標題歸屬已分記；710 年标题在快照中为 {{*|干支，西元…}} 变体形，逐字照登',
     join(TJ8_TITLE, TJ8_FB, TJ9_TITLE, TJ9_LIU)),
    ('claim-bg-dy-world', 'source-jiutangshu-wenyuan',
     '卷一百九十中·文苑中·宋之问传（钦州流+先天赐死段——结局九字）', JTS_SI),
    ('claim-bg-dy-person', 'source-ws-t300-234',
     '页面 題大庾嶺北驛（header title+author 字段逐字——署名第三证，V018 T1_TITLE 路数）', WS_HDR),
    ('claim-bg-dy-person', 'source-jiutangshu-wenyuan',
     '卷一百九十中·文苑中·宋之问传（籍贯段＋夺锦袍＋附易之＋泷州段＋告发段＋赐死段＋'
     '路上写诗句；七段以「……」相連，出处同卷同传）',
     join(JTS_HEAD, JTS_JINPAO, JTS_FU, JTS_LONG, JTS_GAO, JTS_SI, JTS_SHI)),
    ('claim-bg-dy-person', 'source-xintangshu-wenyi',
     '卷二百二·文藝中·宋之问传（籍贯段＋夺锦袍＋泷州句＋告发段＋流钦州＋赐死两细节段＋'
     '沈宋定评；七段以「……」相連，出处同卷同传）',
     join(XTS_HEAD, XTS_JINPAO, XTS_LONG, XTS_GAO, XTS_LIU, XTS_SI, XTS_SI2, XTS_SHENSONG)),
    ('claim-bg-dy-person', 'source-quantangshi-052',
     '页面 全唐詩/卷052（卷首作者注＋本诗锚点与转引用桩 {{:題大庾嶺北驛}}；'
     '卷页无正文，正文证据在诗页；同 V022/V025–V028 桩教训）',
     join(V52_NOTE, V52_ANCHOR)),
    ('claim-bg-dy-person', 'source-zizhi-tongjian-events',
     '通鑑卷二百零八·追述条（告发主谋的第二说：弟之悌遣子——PERSON 层三源两说的通鉴侧出处）',
     TJ8_FB),
]
BG_LINES = {'bg-dy-scene': (1, 2), 'bg-dy-city': (3, 4),
            'bg-dy-world': (5, 6), 'bg-dy-person': (7, 8)}
BG_AUDIENCE = {'bg-dy-scene': 'PRIMARY', 'bg-dy-city': 'JUNIOR',
               'bg-dy-world': 'SENIOR', 'bg-dy-person': 'SENIOR'}
BG_TITLES = {'bg-dy-scene': '眼前：雁回而人南',
             'bg-dy-city': '这道岭：过岭就是另一片天',
             'bg-dy-world': '这个天下：两次贬岭表，一次赐死',
             'bg-dy-person': '这个人：三源对质的名声'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 11 首）；史实句均有逐字引证；'
                 '系年两窗口并列（705 泷州／710 钦州），不铸 time.span 不挂乱事线；'
                 '本迁移并修 V018 对 234 的分行缺陷（5 行并句→8 行，逐字对 ws 诗页）。' for k in BG}


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
    A("""-- V029：宋之問《題大庾嶺北驛》(work-t300-234) 四层背景 + 一处 V018 文本修复（阶段 D 第 11 首）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V018 已执行（work-t300-234 与其 text-work-t300-234-ws、source-ws-t300-234
--       都是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi 是 V016 的行；
--       source-zizhi-tongjian-events 是 V015 的行——本迁移在同一通鉴来源上增引卷208/209，不另开行）。
--
-- 数据源（可复现）：emit_v029.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/題大庾嶺北驛.txt（页内实测无 {{另|}} 异文——如实写明）、資治通鑑卷208/209、
--   全唐詩卷052（卷首注+锚点+转引用桩）、舊唐書卷190中、新唐書卷202。
--
-- §0.5 文本修复（先修文本再挂 bg_line，同事务）：V018 对 234 落 poetry_text_line 时把
--   line_seq 3 误并为四句一行（'我行殊未已，何日復歸來？江靜潮初落，林昏瘴不開。'），8 句只落 5 行。
--   全库扫描此形状仅 234、291 两例（291 另迁移处理——其页有 {{另|}} 异文，先登记后修形）。
--   234 的 version 只被 V018 触过（grep 实测），删 5 插 8 安全；逐字对 ws 诗页 <poem> 块。
--   回滚精确恢复 V018 原 5 行（值原样枚举）。
--
-- 做：1 个新 source 登记（全唐詩卷052，PENDING——登记不等于核验）+
--   poetry_text_line 修复（删 5 行 + 插 8 行，逐字对 ws 快照）+
--   4 BACKGROUND content/claim/background + 11 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（scene→1,2｜city→3,4｜world→5,6｜person→7,8，绑 text-work-t300-234-ws）。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「两次南贬都过岭，诗属哪一程核不到」）：
--   * 窗口一 神龙元年（705）贬泷州（两史+通鉴），窗口二 景云元年（710）流岭表（两史+通鉴）；
--     年谱定 705 本地核不到不采信；710 不在神龙政变(705)时间跨内，挂 written_during 是半证据断言——
--     time.span/event.name/written_during 一个都不造（V023/V024/V027 形状断言 + 零 relation 断言）；
--   * 告发王同皎：旧/新传指之问自为，通鉴指其弟之悌——三源两说逐字并列不裁决，此节不升 KNOWN；
--   * 籍贯虢州弘農(旧) vs 汾州(新) 并列不升；大庾梅信典故零引用不补；
--   * ws 诗页快照实测无页内异文（无 {{另|}}，八句与 V018 正文全同）——「查过、干净」不开 variants 行。
--
-- 干支对账：705=乙巳、710=庚戌（audit-migrations.py 检查4 覆盖标准形；
--   tj-209 的 710 标题为 {{*|庚戌，西元七一〇年}} 变体形，audit 正则不认「西元」——已人工核对无误）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 28，不含 29
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-dy-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-234-ws';  -- 恰 5（V018 缺陷行）
--   SELECT id FROM poetry_source WHERE id='source-quantangshi-052';     -- 空
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-dy-%';        -- 4
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-234-ws';  -- 8
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-234';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-dy-person';   -- KNOWN
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-234'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-234';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-dy-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V029_rollback.sql（按 id 全枚举删除；poetry_text_line 恢复 V018 原 5 行原值；
--   不动 V018 的其他行，不动共用通鉴/两唐书来源行）
START TRANSACTION;""")

    A('\n-- ---------- 0. 来源登记（一律 PENDING：登记不等于核验） ----------')
    A(guard('poetry_source',
            ['id', 'title', 'author', 'edition', 'url', 'rights_note',
             'verification_status', 'source_kind', 'reliability'],
            [{'id': 'source-quantangshi-052',
              'title': '《全唐詩》全唐詩/卷052（维基文库录入本）',
              'author': None,
              'edition': '全唐詩/卷052（维基文库《全唐詩》录入本）',
              'url': 'https://zh.wikisource.org/wiki/全唐詩/卷052',
              'rights_note': '维基文库录入本，公有领域古籍。本卷为宋之问诗卷，卷首 Collection header '
                             "notes 标作者 '''宋之問'''。本诗条目只有锚点+转引用桩，正文在诗页。"
                             '本行由 emit_v029.py 对快照逐字定位。核验状态保持 PENDING。',
              'verification_status': 'PENDING', 'source_kind': 'POETRY_COLLECTION',
              'reliability': 'HIGH'}],
            'x.id = t.id'))

    A("""
-- ---------- 0.5 文本修复：text-work-t300-234-ws 5 行并句 → 8 行（逐字对 ws 诗页） ----------
DELETE FROM poetry_text_line WHERE version_id = 'text-work-t300-234-ws';""")
    L.append('INSERT INTO poetry_text_line (version_id, line_seq, content)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT 'text-work-t300-234-ws' AS version_id, {n} AS line_seq, "
        f"{sql_s(t)} AS content FROM DUAL"
        for n, t in sorted(LINES_NEW.items())))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_text_line x '
             'WHERE x.version_id = t.version_id AND x.line_seq = t.line_seq);')

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
    brows = [{'id': k, 'work_id': 'work-t300-234',
              'layer': {'bg-dy-scene': 'SCENE', 'bg-dy-city': 'CITY',
                        'bg-dy-world': 'WORLD', 'bg-dy-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（挂修复后的 8 行新 line_seq） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-234-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 29, 'song-zhi-wen ti-dayu-ling-bei-yi background layers plus one V018 text-line repair (inserts-after-repair): poetry_text_line rows for text-work-t300-234-ws were mis-merged by V018 (four poem-lines packed into line_seq 3, 5 rows for an eight-line regulated verse; full-corpus scan finds this shape only for 234 and 291) -- this migration deletes the 5 rows and re-inserts 8 rows word-for-word against the ws page, and the rollback restores V018 original 5 rows verbatim; four background layers with why-written anchored by the JTS biography itself (demoted after Zhang Yizhi fell, exiled again under Ruizong, ordered to die at the place of exile; and the unique local witness that his exile-road poems spread far); deliberately NO time.span, NO event.name, NO written_during and zero relation rows -- he crossed the ridge on two separate southbound exiles (705 Longzhou and 710 Qinzhou) and neither source says which journey carried this poem; the denunciation of Wang Tongjiao is left unadjudicated in three sources two voices (JTS and XTS blame Song Zhiwen himself, the Tongjian blames his younger brother Zhi-ti)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 29);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V029 精确回滚：只删 V029 插入的行（id 全枚举）；poetry_text_line 恢复 V018 原 5 行原值。',
         '-- work-t300-234 本体是 V018 的行，绝不删；共用 source 行（jiutangshu-wenyuan/',
         '-- xintangshu-wenyi/tongjian-events/source-ws-t300-234）都不删；V029 零 poetry_relation 行。',
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
    dels('poetry_source', 'id', ['source-quantangshi-052'])
    L.append("")
    L.append("-- text_line 还原：删 V029 的 8 行，重插 V018 原 5 行（值原样枚举，逐字抄自 V018 SQL 3343–3351 行）")
    L.append("DELETE FROM poetry_text_line WHERE version_id = 'text-work-t300-234-ws';")
    L.append('INSERT INTO poetry_text_line (version_id, line_seq, content)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT 'text-work-t300-234-ws' AS version_id, {n} AS line_seq, "
        f"{sql_s(t)} AS content FROM DUAL"
        for n, t in sorted(LINES_OLD.items())))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_text_line x '
             'WHERE x.version_id = t.version_id AND x.line_seq = t.line_seq);')
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 29;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (WS_L12, WS_L34, WS_L56, WS_L78, WS_HDR, V52_NOTE, V52_ANCHOR,
              JTS_HEAD, JTS_JINPAO, JTS_FU, JTS_LONG, JTS_GAO, JTS_SI, JTS_SHI,
              XTS_HEAD, XTS_JINPAO, XTS_LONG, XTS_GAO, XTS_LIU, XTS_SI, XTS_SI2, XTS_SHENSONG,
              TJ8_TITLE, TJ8_FB, TJ9_TITLE, TJ9_LIU):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    for n, t in LINES_NEW.items():
        if sql_s(t) not in sql:
            bad.append(f'修复行 {n} 未逐字进入 SQL: {t[:16]}…')
    for n, t in LINES_OLD.items():
        if sql_s(t) not in build_rollback().replace("''", "'"):
            bad.append(f'回滚旧行 {n} 未逐字进入回滚 SQL: {t[:16]}…')
    # poetry_citation 主键 (claim_id, source_id)：本文件内每对恰出现一次
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    # 缺席断言（V023/V024/V027/V028 同款）
    if "'written_during' AS predicate" in sql:
        bad.append("V029 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V029 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-234' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V029 有意不给诗铸 {pk}，但该主语组合出现了')
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
    # guard() 只查 INSERT；§0.5 与回滚里的裸 DELETE 是修复语义本体，不参与守卫
    guarded = 0
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
        stmt = sql[m.start():end]
        if 'poetry_text_line' not in m.group(1):
            if 'WHERE NOT EXISTS' not in stmt:
                bad.append(f'{m.group(1)} 的 INSERT 没有幂等守卫')
        else:
            if 'WHERE NOT EXISTS' not in stmt:
                bad.append('poetry_text_line 的 INSERT 没有幂等守卫')
            guarded += 1
    if guarded != 1:  # §0.5 修复行的 INSERT（poetry_background_line 是另一张表，不计入）
        bad.append(f'poetry_text_line 相关 INSERT 数应为 1，实际 {guarded}')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 26 切片+修复8行+回滚旧5行逐字过审；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
