#!/usr/bin/env python3
"""阶段 D 第 13 首：生成 V032——李白《登金陵鳳凰臺》(work-t300-326, V018 已立) 四层背景。

「为什么写」第五次成立，形状是 **本传给足整条人生弧，尾联自己点破**：
「總爲浮雲能蔽日，長安不見使人愁」——长安在哪里？他一生三进三出长安的两唐书本传
全给了：天宝初供奉翰林（旧传「與筠俱待詔翰林」）、高力士脱靴「由是斥去」（旧传五字）、
永王璘幕「坐長流夜郎」（两史一致）、晚年再无可还。金陵登台的愁不是无来由的怀古诗式，
是本传那条路走完之后往北看的那一眼。

系年第七次判决：**全缺席，缺席原因是「两传给他三个南行窗口，没有一个落在金陵」**——
供奉翰林被斥后「浪迹江湖」（740s，无年）、永王败后长流夜郎途中遇赦（757–758，流放线
不经金陵而经九江寻阳；但「白浮游四方，嘗乘舟與崔宗之自採石至金陵」——新传明写他
**确实到过金陵**，却不系年）、晚年依李阳冰在当涂（762，当涂距金陵一步）。
三个窗口任何一个都可能写此诗，本传一个都没系年；「李白于永王败后系舟金陵」是年谱推定，
本地核不到不采信。time.span/event.name/written_during 零铸造 + 零 relation（V027–V031 断言）。

本传给的不是年份是**地理**：新传「嘗乘舟與崔宗之自採石至金陵，著宮錦袍坐舟中，旁若無人」
与旧传「自采石達金陵，白衣宮錦袍」逐字并立——两史同记他泛舟到金陵这件事，
这是本地最硬的「他在这座城」证据（虽不系年）。

怀古线全用诗本文内证+本传，不开新史料：吴宫晋代两联是登台所见所忆，不需要史书。
浮雲蔽日的政治指向（或谓指杨国忠/李林甫）——年谱与注家说，本地核不到，**不写**，
正文只到「长安不见」为止，愁给本传解释，不给猜谜。

ws 诗页实测无 {{另}} 异文（「查过、干净」不开 variants 行，同 231/002/234 判例）；
无 vol180 快照——本诗**没有第二证卷页**，来源只有 ws 诗页+两唐书（诚实写明，
不假装全唐詩在场；V025–V031 每首都有卷页桩，此首没有，就少一条 citation）。

用法: python3 -I emit_v032.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/登金陵鳳凰臺.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷202.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；锚不唯一即中止——2026-11-20 实测全部 x1） ----------
WS_L12 = slice_between(WS, '鳳凰臺上鳳凰遊，鳳去臺空江自流。', '鳳去臺空江自流。', 'ws首联(台空江流)')
WS_L34 = slice_between(WS, '吳宮花草埋幽徑，晉代衣冠成古丘。', '晉代衣冠成古丘。', 'ws二联(吴宫晋代)')
WS_L56 = slice_between(WS, '三山半落青天外，二水中分白鷺洲。', '二水中分白鷺洲。', 'ws三联(三山白鹭)')
WS_L78 = slice_between(WS, '總爲浮雲能蔽日，長安不見使人愁。', '長安不見使人愁。', 'ws尾联(长安不见)')
# （ws header author 字段不单独入引文：V018 claim-t300-326-author 已引 'header author=李白'，
#   本迁移不重复 V018 已登记的署名证——与 V029 不同，那首在 PERSON 层做了署名第三证。）
JTS_HEAD = slice_between(JTS, '李白字太白，山東人。少有逸才，志氣宏放，飄然有超世之心，父爲任城尉，因家焉。',
                         '因家焉。', '旧传首段(山东人/任城)')
JTS_ZHU = slice_between(JTS, '少與魯中諸生孔巢父、韓沔、裴政、張叔明、陶沔等隠於徂徠山，酣歌縱酒，時號「竹溪六逸」。',
                        '時號「竹溪六逸」。', '旧传竹溪六逸段')
JTS_HAN = slice_between(JTS, '旣而玄宗詔筠赴京師，筠薦之於朝，遣使召之，與筠俱待詔翰林。',
                        '與筠俱待詔翰林。', '旧传待诏翰林段')
JTS_CAO = slice_between(JTS, '嘗沉醉殿上，引足令高力士脫靴，由是斥去。乃浪迹江湖，終日沉飲。',
                        '終日沉飲。', '旧传脱靴斥去段(出长安)')
JTS_JL = slice_between(JTS, '時侍御史崔宗之謫官金陵，與白詩酒唱和。嘗月夜乘舟，自采石達金陵，白衣宮錦袍，於舟中顧瞻笑傲，傍若無人。',
                       '傍若無人。', '旧传采石至金陵段(两史同记到金陵)')
JTS_YW = slice_between(JTS, '祿山之亂，玄宗幸蜀，在途以永王璘為江淮兵馬都督、揚州節度大使。白在宣州謁見，遂辟爲從事。永王謀亂，兵敗，白坐長流夜郎。後遇赦得還，竟以飲酒過度，醉死於宣城。有文集二十卷，行於時。',
                       '有文集二十卷，行於時。', '旧传永王段+流夜郎+醉死宣城(第三窗口附近)')
XTS_HEAD = slice_between(XTS, '李白，字太白，興聖皇帝九世孫。其先隋末以罪徙西域，神龍初，遁還，客巴西。',
                         '客巴西。', '新传首段(世系/客巴西)')
XTS_HL = slice_between(XTS, '往見賀知章，知章見其文，歎曰：「子，謫仙人也！」言于玄宗，召見金鑾殿，論當世事，奏頌一篇。帝賜食，親為調羹，有詔供奉翰林。',
                        '有詔供奉翰林。', '新传谪仙人+供奉翰林段(入长安)')
XTS_GX = slice_between(XTS, '白嘗侍帝，醉，使高力士脫靴。力士素貴，恥之，擿其詩以激楊貴妃，帝欲官白，妃輒沮止。',
                        '妃輒沮止。', '新传脱靴段(出长安原因两传异写之一)')
XTS_FH = slice_between(XTS, '懇求還山，帝賜金放還。白浮游四方，嘗乘舟與崔宗之自採石至金陵，著宮錦袍坐舟中，旁若無人。',
                       '旁若無人。', '新传赐金放还+採石至金陵段(到金陵第二证)')
XTS_YW = slice_between(XTS, '安祿山反，轉側宿松、匡廬間，永王璘辟為府僚佐。璘起兵，逃還彭澤，璘敗，當誅。',
                        '當誅。', '新传永王幕+当诛段')
XTS_ZL = slice_between(XTS, '至是子儀請解官以贖，有詔長流夜郎。會赦，還尋陽，坐事下獄。',
                        '坐事下獄。', '新传流夜郎+会赦段')
XTS_ZU = slice_between(XTS, '李陽冰為當塗令，白依之。代宗立，以左拾遺召，而白已卒，年六十餘。',
                        '年六十餘。', '新传依李阳冰当涂+卒段(第三窗口)')
XTS_QS = slice_between(XTS, '白晚好黃老，度牛渚磯至姑孰，悅謝家青山，欲終焉。及卒，葬東麓。',
                       '葬東麓。', '新传青山终焉段(葬当涂)')

BG = {
    'bg-jl-scene': (
        '他登的是金陵的凤凰台：「鳳凰臺上鳳凰遊，鳳去臺空江自流。」——传说凤凰来过，'
        '如今凤去台空，只有长江照旧流。眼前是「三山半落青天外，二水中分白鷺洲」——'
        '三山在半空之外若隐若现，白鹭洲把江水分成两支，这是登台实见的金陵 geography。\n'
        '但这首诗真正看的方向在北：「總爲浮雲能蔽日，長安不見使人愁」——登台往北望，'
        '长安看不见，愁。为什么愁长安：他的人生平两唐书本传写全了（见第 5–8 句那几层），'
        '三次到长安边上三次离开。金陵是他到过多次的城——两史同记他「自采石至金陵」——'
        '但这首诗写于哪一年，本地核不到（见 world 层）。'),
    'bg-jl-city': (
        '金陵在这首诗里是三层城叠在一起：眼下的城（三山、白鹭洲、长江），'
        '亡过的城（「吳宮花草埋幽徑，晉代衣冠成古丘」——吴宫的花草埋进荒路，'
        '东晋的名门成了古坟丘），和看不见的城（长安）。\n'
        '他确实在金陵地面上活动过，两史逐字并立：旧唐书「時侍御史崔宗之謫官金陵，'
        '與白詩酒唱和。嘗月夜乘舟，自采石達金陵，白衣宮錦袍，於舟中顧瞻笑傲，傍若無人」'
        '（卷一百九十下），新唐书写同一件事「嘗乘舟與崔宗之自採石至金陵，著宮錦袍坐舟中，'
        '旁若無人」（卷二百零二）——采石到金陵是这条水路的固定一段，锦袍一段两史同记。\n'
        '他最后葬的地方离金陵一步：新传「度牛渚磯至姑孰，悅謝家青山，欲終焉。及卒，葬東麓」——'
        '牛渚矶、姑孰、青山都在金陵上游几十里内。这座城是他人生的终点站。'),
    'bg-jl-world': (
        '长安是这个人的太阳，这首诗的太阳被云遮着：「浮雲能蔽日，長安不見使人愁」。\n'
        '两传给他三次贴着长安又离开的经过。第一次入：天宝初，旧传「與筠俱待詔翰林」，'
        '新传写得更全——贺知章叹他「謫仙人」，「召見金鑾殿……帝賜食，親為調羹，'
        '有詔供奉翰林」。第一次出：旧传五个字「由是斥去」（高力士脱靴一段后），'
        '新传写「帝欲官白，妃輒沮止」——两传对出长安的原因各写各的，并列。\n'
        '第二次贴边在安史乱中：新传「安祿山反，轉側宿松、匡廬間，永王璘辟為府僚佐。'
        '璘起兵，逃還彭澤，璘敗，當誅」，随后「有詔長流夜郎。會赦，還尋陽」——'
        '旧传同段作「白坐長流夜郎。後遇赦得還」。第三次：「代宗立，以左拾遺召，'
        '而白已卒」——诏书到了人没了。\n'
        '**系年的诚实话**：这首诗可能写于三个窗口任何一个（放还后浪迹期 740s、'
        '流夜郎遇赦前后 757–758、晚年依李阳冰期 762——都到过金陵一带），'
        '两史对他到金陵一句都不系年；年谱推定某年，本地核不到不采信。'
        '本诗 time.span、event.name、written_during 全部缺席。'
        '浮雲蔽日指谁（注家说指杨国忠、或李林甫）——本地核不到，正文不猜。'),
    'bg-jl-person': (
        '李白的本传是全库写得最像他诗的两篇。\n'
        '入长安前的他：旧传「少有逸才，志氣宏放，飄然有超世之心」，与孔巢父等'
        '「隠於徂徠山……時號『竹溪六逸』」；新传多一层世系「興聖皇帝九世孫。'
        '其先隋末以罪徙西域，神龍初，遁還，客巴西」——出生地两传不一致（山东人/客巴西），'
        '并列。\n'
        '长安里的他：谪仙人的名号是贺知章给的（新传）；沉香亭醉草、使高力士脱靴两传都有，'
        '细节各写（旧传「由是斥去」一笔带过，新传展开到贵妃沮止）；'
        '出长安的路径也各说——旧传直接「斥去」，新传是他自己「懇求還山，帝賜金放還」。\n'
        '乱中的他：永王璘幕、当诛、郭子儀请解官以赎、长流夜郎、会赦——新传全有，'
        '旧传无郭子儀赎罪一段（单源，照登不升）。结局两传不同：旧传「竟以飲酒過度，'
        '醉死於宣城」，新传「以左拾遺召，而白已卒，年六十餘」——死因两说并列，'
        '葬地新传有（青山东麓），旧传无。\n'
        '「长安不见使人愁」的愁就是这个人的底色：本传说他「飄然有超世之心」，'
        '又处处写他到长安门口进不去、进去又被挤出来。登台的愁不用猜谜，传记替诗作答。'),
}
CLAIMS = {
    'claim-bg-jl-scene': (
        'FACT', 'LIKELY',
        '登台动作+所见由诗本文四联内证支撑；「到金陵」由两史采石至金陵段逐字支撑；'
        '写作年份不采任何窗口（见 world 层），本 claim 不含系年。'),
    'claim-bg-jl-city': (
        'FACT', 'LIKELY',
        '三层城为诗本文；采石至金陵两史逐字并立（同件两录）；青山终焉葬东麓为新传逐字（单源照登）。'),
    'claim-bg-jl-world': (
        'FACT', 'LIKELY',
        '入翰林/出翰林/永王幕/流夜郎/召卒五段两传逐字（各段细节异写处并列）；'
        '三窗口均可到金陵而无一系年→time.span/event.name/written_during 全缺席、零 relation；'
        '浮云所指不猜（本地核不到）。'),
    'claim-bg-jl-person': (
        'FACT', 'KNOWN',
        '两传一致处升 KNOWN：天宝初待诏/供奉翰林、高力士脱靴事、坐永王事长流夜郎、遇赦；'
        '异写处并列不升：出生地（山东人/客巴西）、出京路径（斥去/恳求赐金放还）、'
        '死因（醉酒宣城/召卒年六十餘）、郭子儀赎罪（单源）；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-jl-scene', 'source-ws-t300-326',
     '页面 登金陵鳳凰臺（首联+三联逐字以「……」相連；页内实测无 {{另|}} 异文标记——'
     '「查过、干净」，登记在计划文档不开 variants 行；全文另见 V018 claim-t300-326-text 引文）',
     join(WS_L12, WS_L56)),
    ('claim-bg-jl-scene', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传（賜金放還+採石至金陵段——本传侧「他在金陵」之证）', XTS_FH),
    ('claim-bg-jl-city', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白（崔宗之謫官金陵+月夜乘舟自采石達金陵段）', JTS_JL),
    ('claim-bg-jl-city', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传（青山终焉段+採石至金陵段——两史同件第二录+终点站，两段「……」相連）',
     join(XTS_QS, XTS_FH)),
    ('claim-bg-jl-city', 'source-ws-t300-326',
     '页面 登金陵鳳凰臺（二联逐字——吴宫晋代怀古线纯内证，引此备查）', WS_L34),
    ('claim-bg-jl-world', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白（待诏翰林段＋脱靴斥去浪迹段＋永王流夜郎遇赦段；'
     '三段以「……」相連——三窗口旧传侧）', join(JTS_HAN, JTS_CAO, JTS_YW)),
    ('claim-bg-jl-world', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传（供奉翰林段+贵妃沮止段+永王当诛段+流夜郎会赦段+召卒段；'
     '五段以「……」相連——三窗口新传侧；年谱系年本地核不到不采信，见 claim 与文件头）',
     join(XTS_HL, XTS_GX, XTS_YW, XTS_ZL, XTS_ZU)),
    ('claim-bg-jl-world', 'source-ws-t300-326',
     '页面 登金陵鳳凰臺（尾联逐字——浮雲蔽日/长安不见之愁的政治指向本地核不到，正文不猜）', WS_L78),
    ('claim-bg-jl-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·李白（首段+竹溪六逸段+脱靴段+永王醉死宣城段；四段「……」相連）',
     join(JTS_HEAD, JTS_ZHU, JTS_CAO, JTS_YW)),
    ('claim-bg-jl-person', 'source-xintangshu-wenyi',
     '卷二百零二·文藝中·李白传（世系段+谪仙人翰林段+脱靴展开段+永王段+流夜郎段+召卒段+青山段；'
     '七段以「……」相連，出处同卷同传）',
     join(XTS_HEAD, XTS_HL, XTS_GX, XTS_YW, XTS_ZL, XTS_ZU, XTS_QS)),
]
BG_LINES = {'bg-jl-scene': (1, 2), 'bg-jl-city': (3, 4),
            'bg-jl-world': (5, 6), 'bg-jl-person': (7, 8)}
BG_AUDIENCE = {'bg-jl-scene': 'PRIMARY', 'bg-jl-city': 'JUNIOR',
               'bg-jl-world': 'SENIOR', 'bg-jl-person': 'SENIOR'}
BG_TITLES = {'bg-jl-scene': '眼前：凤去台空，往北望',
             'bg-jl-city': '这座城：三层叠在一起的金陵',
             'bg-jl-world': '这个天下：三次贴着长安又离开',
             'bg-jl-person': '这个人：传记替诗作答'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 13 首）；史实句均有逐字引证；'
                 '三窗口均可到金陵而无一系年→time.span/event.name/written_during 全缺席、零 relation；'
                 '浮云所指不猜；ws 诗页无页内异文（查过、干净）。' for k in BG}


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
    A("""-- V032：李白《登金陵鳳凰臺》(work-t300-326) 四层背景（阶段 D 第 13 首）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-326 与其 text-work-t300-326-ws、
--       source-ws-t300-326 都是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行——引 卷190下/卷202 不另开行）。
--
-- 数据源（可复现）：emit_v032.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/登金陵鳳凰臺.txt（页内实测无 {{另}} 异文——「查过、干净」）、
--   舊唐書卷190下、新唐書卷202。**无全唐詩卷180 本地快照**——本诗没有卷页第二证，
--   诚实缺一条 citation，不假装在场（V025–V031 的卷页桩教训：有则引，无则明说无）。
--
-- 做：4 BACKGROUND content/claim/background + 10 组逐字引用（(claim,source) 主键每对恰一行）+
--   8 行 background_line（scene→1,2｜city→3,4｜world→5,6｜person→7,8，绑 text-work-t300-326-ws）。
--   0 个新 source（ws+两唐书来源行 V018/V016 已登记）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「三个南行窗口都到过金陵一带，一个都没系年」）：
--   * 窗口一 赐金放还后浪迹期（740s）、窗口二 永王败后流夜郎遇赦前后（757–758）、
--     窗口三 晚年依李阳冰期（762，葬当涂青山）——两史记他「自采石至金陵」但不系年；
--     年谱推定某年本地核不到不采信；通鉴通篇无李白（tj-191–265 全检零命中）——
--     time.span/event.name/written_during 一个都不造（V023/V024/V027 形状断言+V028 零 relation 断言）；
--   * 出长安两传异写：旧传「由是斥去」vs 新传「懇求還山，帝賜金放還」——并列不裁决；
--   * 死因两说：旧传「醉死於宣城」vs 新传「以左拾遺召，而白已卒，年六十餘」——并列；
--     出生地（山東人/客巴西）、郭子儀赎罪（只新传）同理；KNOWN 只给两传一致处；
--   * 浮雲蔽日的政治指向（注家谓指杨国忠/李林甫）本地核不到，正文与引文都不写。
--
-- 干支对账：本迁移无通鉴年标题、无干支断言（audit 检查4 无涉）。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 31，不含 32
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-jl-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-326-ws';  -- 恰 8
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-jl-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-326';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-jl-person';   -- KNOWN
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-326'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-326';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-jl-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V032_rollback.sql（按 id 全枚举删除；不动 V018 的行，不动共用来源行）
START TRANSACTION;""")

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
    brows = [{'id': k, 'work_id': 'work-t300-326',
              'layer': {'bg-jl-scene': 'SCENE', 'bg-jl-city': 'CITY',
                        'bg-jl-world': 'WORLD', 'bg-jl-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-326-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 32, 'Li Bai Deng Jinling Fenghuang-tai background layers (stage-D poem 13): the biographies give the whole arc the poem looks back on -- three approaches to Chang-an and three departures (summoned to the Hanlin, expelled after the Gao Lishi boot anecdote per JTS / requesting release per XTS, the Prince Yong affair and long exile to Ye-lang, and the posthumous recall summons that reached only his death); NO time.span, NO event.name, NO written_during, zero relation rows -- all three southbound windows plausibly touch Jinling and the two histories both record his boat trip from Cai-shi to Jinling yet neither ever dates any Jinling stay, the chronology-s year is not adopted, and the Tongjian never mentions Li Bai at all (full scan of ju 191-265); every known conflict kept in parallel (birth place, departure cause, death place and cause, Guo Ziyi-ransom single source); the floating-clouds allegory-target is NOT guessed -- unverifiable locally, so the text stops at chang-an-bu-jian'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 32);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V032 精确回滚：只删 V032 插入的行（id 全枚举）。',
         '-- work-t300-326 本体、其 text_line 8 行与 source-ws-t300-326 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi）不删；V032 零 poetry_relation 行。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 32;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (WS_L12, WS_L34, WS_L56, WS_L78,
              JTS_HEAD, JTS_ZHU, JTS_HAN, JTS_CAO, JTS_JL, JTS_YW,
              XTS_HEAD, XTS_HL, XTS_GX, XTS_FH, XTS_YW, XTS_ZL, XTS_ZU, XTS_QS):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    # 引用来源里出现过的切片必须都真在引文行里（WS_HDR 只在文件头注释提及时不误伤：
    # 它没进 CITATIONS——检查过；断言只覆盖 CITATIONS 用到的切片）
    cited = {ex for _, _, _, ex in CITATIONS}
    joined = '……'.join(sorted(cited))
    for q in (WS_L12, WS_L34, WS_L56, WS_L78, JTS_HEAD, JTS_ZHU, JTS_HAN, JTS_CAO, JTS_JL,
              JTS_YW, XTS_HEAD, XTS_HL, XTS_GX, XTS_FH, XTS_YW, XTS_ZL, XTS_ZU, XTS_QS):
        if q not in joined:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V032 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V032 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-326' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V032 有意不给诗铸 {pk}，但该主语组合出现了')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V032 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V032 零新 source，不该出现 INSERT INTO poetry_source')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 19 切片逐字过审且全部进引文；'
              f'(claim,source) 主键 {len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言；零新 source/text_line 未触碰已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
