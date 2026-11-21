#!/usr/bin/env python3
"""阶段 D 第 19 首：生成 V038——孟浩然《宿建德江》(work-t300-122, V018 已立) 四层背景。

「为什么写」第十一次成立，这次本传给的是**整个失意群体的共同浓度**：
「日暮客愁新」五个字的愁，两唐书各给了一句群像鉴定——
旧传卷末总评「開元、天寳間，文士知名者，汴州崔顥，京兆王昌齡、高適，㐮陽孟浩然，
皆名位不振」（此句不在孟传段内，在陆据传末——旧书文苑类总评体例，locator 声明）；
新传孟传段末「開元、天寶間，同知名者王昌齡、崔顥，皆位不顯」——
两源独立一致升 KNOWN：孟、王、崔这一批名士「位不顯」是两唐书共同的鉴定结论。

系年第十三次判决：**「题自带地名，传不纪其游」**——比前十次多一个新对偶：
《宿建德江》的题把**地点**钉死了（建德在桐江上，今浙江），全诗「野曠天低樹，
江清月近人」也确是江行实感；但两传的行迹只有鹿门山—京师—荆州三条线，
**无一字记吴越之游**——地方有、年月无。题证地方不证时间，
不借「诗人漫游吴越」的常识把年月补出来。time.span/event.name/written_during 零铸造。

KNOWN 三处：①隐鹿门山（旧传「隠鹿門山」+新传「隱鹿門山」两源合龙）；
②位不顯群像鉴定（两源，见上）；③孟亭/浩然亭身后纪念（新传单源——**不升**，LIKELY）。
鳏居对照 V037 王维：那是两源合龙，这里新传「病疽背卒」旧传「不达而卒」两条死状线
V031 已并列——本首不重复裁决，引 V031 处理并声明。

复用切片刻意标注：JTS_NAME 在 V031 已入证（同一句），本迁移再引为群像主证——
locator 声明「V031 已立，此处群像侧再证」，跨迁移同句再证合规（citation 主键是
claim+source 对，不跨迁移冲突）。{{另|煙|幽}} 页内异文已先登记 variants.md。

绝句第三例：background_line 每层一行（1/2/3/4），audit 形制断言。

用法: python3 -I emit_v038.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import slice_between, sql_s, join  # noqa: E402  切片器/SQL字面量/共用引文——单一来源

WS = pathlib.Path('/tmp/src-dl/ws-poems/宿建德江.txt').read_text(encoding='utf-8')
JTS = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
XTS = pathlib.Path('/tmp/src-dl/xts-卷203.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；2026-11-20 实测全部唯一） ----------
# L1 含 {{另|煙|幽}} 标记原样（V024/V031 判例；variants.md 已先登记）
WS_L1 = slice_between(WS, '移舟泊{{另|煙|幽}}渚，日暮客愁新。', '移舟泊{{另|煙|幽}}渚，', 'ws第1句(含异文标记)')
WS_L2 = slice_between(WS, '移舟泊{{另|煙|幽}}渚，日暮客愁新。', '日暮客愁新。', 'ws第2句(日暮客愁新)')
WS_L3 = slice_between(WS, '野曠天低樹，江清月近人。', '野曠天低樹，', 'ws第3句(野旷天低树)')
WS_L4 = slice_between(WS, '野曠天低樹，江清月近人。', '江清月近人。', 'ws第4句(江清月近人)')
WS_TITLE = slice_between(WS, '| title    = 宿建德江', '| title    = 宿建德江', 'ws header title(题内地名)')
WS_AUTHOR = slice_between(WS, '| author   = 孟浩然', 'author   = 孟浩然', 'ws header author(署名直证)')
JTS_LM = slice_between(JTS, '孟浩然，隠鹿門山，以詩自適。', '以詩自適。',
                       '旧传孟传首句(隐鹿门以诗自适——两源合龙第一源;V037 JTS_MH 同段未含此句)')
JTS_NAME = slice_between(JTS, '開元、天寳間，文士知名者，汴州崔顥，京兆王昌齡、高適，㐮陽孟浩然，皆名位不振，唯高適官逹，自有傳。',
                         '開元、天寳間，文士知名者，汴州崔顥，京兆王昌齡、高適，㐮陽孟浩然，皆名位不振，唯高適官逹，自有傳。',
                         '旧传文苑类总评(皆名位不振——群像鉴定旧传侧;V031 已立此句,此处群像侧再证;不在孟传段内,卷末类序体例已声明)')
XTS_LU = slice_between(XTS, '少好節義，喜振人患難，隱鹿門山。', '隱鹿門山。', '新传鹿门段(两源合龙第二源)')
XTS_HANQ = slice_between(XTS, '採訪使韓朝宗約浩然偕至京師，欲-{薦}-諸朝。', '欲-{薦}-諸朝。',
                         '新传韩朝宗段前部(约荐入京——V031 只用剧饮爽约段,此为事件起点段,零重叠)')
XTS_WX = slice_between(XTS, '開元、天寶間，同知名者王昌齡、崔顥，皆位不顯。', '皆位不顯。',
                       '新传孟传段末总评(皆位不顯——群像鉴定新传侧,天宝二字用新传原字)')
XTS_MT = slice_between(XTS, '初，王維過郢州，畫浩然像-{于}-刺史亭，因曰浩然亭。-{咸}-通中，刺史鄭諴謂賢者名不可斥，更署曰孟亭。',
                       '更署曰孟亭。', '新传孟亭段(身后纪念——新传单源不升 KNOWN)')

# 传区间归属复验（V036 立规）
_ja, _jb = JTS.find('=孟浩然='), JTS.find('=元德秀=')
_xa = XTS.find('　　孟浩然，字浩然')
_xe = XTS.find('===附 王昌齡===')
if not (_ja <= JTS.find('孟浩然，隠鹿門山') <= _jb):
    raise SystemExit('JTS_LM 越出孟传区间')
if JTS.find('開元、天寳間，文士知名者') >= _ja:
    raise SystemExit('JTS_NAME 已落入孟传段——locator 的「不在孟传段内」声明失效，修订后重生成')
for _s, _tag in [(XTS_LU, 'XTS_LU'), (XTS_HANQ, 'XTS_HANQ'), (XTS_WX, 'XTS_WX'), (XTS_MT, 'XTS_MT')]:
    if not (_xa <= XTS.find(_s) <= _xe):
        raise SystemExit(f'切片越出孟传区块：{_tag}——修订后重生成')

BG = {
    'bg-jd-scene': (
        '这一晚的船泊在渚边：「移舟泊{{另|煙|幽}}渚，日暮客愁新」——'
        '把船挪开水流靠住小洲，天黑了，客愁是新的（V018 正文取首读「煙渚」；'
        '页内「幽渚」异读照登不裁决）。夜里的景只有两组：'
        '「野曠天低樹」——原野太空，天压到树顶；「江清月近人」——江水太清，'
        '月亮凑到船边来。天地挤到一条船上，只剩月亮站在客人这一边。\n'
        '愁什么，两传给不了这场夜：新传给过一打具体的愁（太学赋诗四座叹伏之后'
        '是放还、爽约、府罢），但没有一条拴住这一晚。愁有浓度，没有名目。'),
    'bg-jd-city': (
        '这是阶段 D 十九首里**地名最硬的一首**：题目直接落在建德——'
        '桐江上的县，严子陵钓台所在地，唐属睦州。诗里「江清」「野曠」与桐江'
        '江行实景相合（读法，非史料断言）。\n'
        '但传里的地图到此为止：旧传三行行迹——鹿门山、京师、荆州；'
        '新传添上太学、内署、韩朝宗相约的京师。两传**无一字记吴越之游**。'
        '题证地方，不证时间：这首诗确实在建德（题），却不在任何一条史料行迹线上，'
        '也没有年月。漫游吴越是后世常识，常识不补史料——'
        'time.span/event.name/written_during 一个都不造。'),
    'bg-jd-world': (
        '「客愁」的愁，两唐书各给了一份群像鉴定，两源的结论惊人一致：\n'
        '旧唐书文苑类卷末总评：「開元、天寳間，文士知名者，汴州崔顥，京兆王昌齡、'
        '高適，㐮陽孟浩然，**皆名位不振**，唯高適官逹，自有傳」——注意这句不在'
        '孟传里，在邻传传末，是类序式的总评（旧书体例如此，逐字照录）；'
        '新唐书孟传段末：「開元、天寶間，同知名者王昌齡、崔顥，**皆位不顯**」。\n'
        '两源独立一致：孟浩然—王昌龄—崔颢这一批「知名而位不显」是两唐书共同的'
        '鉴定结论——升 KNOWN。「日暮客愁新」于是有了社会学的浓度：'
        '不是一个人怀才不遇，是一代人；月近人因为没有人。'),
    'bg-jd-person': (
        '孟浩然的身份底片两源合龙：旧传「孟浩然，隠鹿門山，以詩自適」，'
        '新传「少好節義，喜振人患難，隱鹿門山」——**隐鹿门山**三个字的'
        '两个独立写法，升 KNOWN；以诗自适（旧）与侠气好施（新）各为单传色彩，照登。\n'
        '新传留了两段旧传没有的：其一，采访使韩朝宗约他同入京师「欲薦諸朝」'
        '（本迁移取事件起点句；剧饮爽约的后续 V031 已引，不重复）——'
        '推荐人自己先辞了行，是另一重「位不顯」的制度形状；其二，身后纪念：'
        '「王維過郢州，畫浩然像于刺史亭，因曰浩然亭」，咸通中刺史郑諴嫌直呼'
        '贤者名讳不敬，改名**孟亭**——新传单源，不升 KNOWN，但王维画像素'
        '（V035/V037 王维线）与这条孟亭记载在同一传里互证：'
        '两人相识这件事本身，新传「張九齡、王維雅稱道之」句另有直证。\n'
        '死状两条线（旧「不达而卒」/新「病疽背卒」）V031 已并列不裁决，本首不重复。'),
}
CLAIMS = {
    'claim-bg-jd-scene': (
        'FACT', 'LIKELY',
        '移舟/泊渚/日暮/野旷/江清/月近全诗本文（{{另|煙|幽}} 页内异文首读煙照登，'
        'variants.md 先登记）；愁有名目与否——两传无一字拴住此夜，愁只有浓度没有名目。'),
    'claim-bg-jd-city': (
        'FACT', 'LIKELY',
        '地点=题内直载（建德，桐江上——行政归属为常识注，非本证）；'
        '江行实景与桐江相合为读法声明；两传行迹零吴越记载——题证地方不证时间；'
        '漫游吴越常识不补史料。'),
    'claim-bg-jd-world': (
        'FACT', 'KNOWN',
        '「知名而位不显」群像鉴定两源独立一致：旧传类序总评「皆名位不振」'
        '（含孟/王/崔/高四人名，唯高适达）与新传孟传段末「皆位不顯」（王/崔同知名者）'
        '各自逐字——鉴定结论本身升 KNOWN；不外溢到诗：客愁≠鉴定文书，'
        '诗 time.span/event.name/written_during 零铸造、零 relation。'),
    'claim-bg-jd-person': (
        'FACT', 'KNOWN',
        'KNOWN 一处：隐鹿门山——旧传「隠鹿門山」与新传「隱鹿門山」两源合龙'
        '（以诗自适/侠气各单传色彩 LIKELY）；身后孟亭/浩然亭纪念新传单源不升；'
        '韩朝宗荐举起点段新传单得 LIKELY（爽约后续 V031 已立）；'
        '死状两传分歧 V031 已并列，本处不重复裁决；certainty 不覆盖任何系年。'),
}
CITATIONS = [
    ('claim-bg-jd-scene', 'source-ws-t300-122',
     '页面 宿建德江（header title+author 两字段+第1、2句，四段以「……」相連——'
     '第1句含页内异文标记 {{另|煙|幽}} 原样入证（V018 正文取首读煙渚，'
     'variants.md 已先登记）；全文另见 V018 claim-t300-122-text 引文）',
     join(WS_TITLE, WS_AUTHOR, WS_L1, WS_L2)),
    ('claim-bg-jd-city', 'source-ws-t300-122',
     '页面 宿建德江（第3、4句逐字——野旷江清：题外地名的唯一诗内实景）',
     join(WS_L3, WS_L4)),
    ('claim-bg-jd-city', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·孟浩然传（旧传行迹全部三行：鹿門山—京師—荊州——'
     '零吴越记载之负证在本段；与 V037 所引 JTS_MH/JTS_MH2 相接不重叠）',
     JTS_LM),
    ('claim-bg-jd-world', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·类序总评（陆据传末「皆名位不振」句——**不在孟传段内**，'
     '旧书文苑类序体例；V031 已引此句为孟氏交游证，此处群像侧再证——'
     '跨迁移同句再证，claim 不同故主键不冲突）', JTS_NAME),
    ('claim-bg-jd-world', 'source-xintangshu-wenyi',
     '卷二百零三·文藝中·孟浩然传段末（「同知名者王昌齡、崔顥，皆位不顯」——'
     '群像鉴定新传侧；与旧传总评两源独立一致）', XTS_WX),
    ('claim-bg-jd-person', 'source-jiutangshu-wenyuan',
     '卷一百九十下·文苑下·孟浩然传首句（隠鹿門山/以詩自適——两源合龙旧传侧；'
     '与 CITY 层同句异claim各立一行）', JTS_LM),
    ('claim-bg-jd-person', 'source-xintangshu-wenyi',
     '卷二百零三·文藝中·孟浩然传（鹿门段+韩朝宗约荐段+孟亭段；三段以「……」相連，'
     '同卷同传——鹿门两源合龙新传侧/荐举起点单得/身后纪念单源不升）',
     join(XTS_LU, XTS_HANQ, XTS_MT)),
]
BG_LINES = {'bg-jd-scene': (1,), 'bg-jd-city': (2,), 'bg-jd-world': (3,), 'bg-jd-person': (4,)}
BG_AUDIENCE = {'bg-jd-scene': 'PRIMARY', 'bg-jd-city': 'JUNIOR',
               'bg-jd-world': 'SENIOR', 'bg-jd-person': 'SENIOR'}
BG_TITLES = {'bg-jd-scene': '眼前：一条船的夜',
             'bg-jd-city': '这座城：题里有地名，传里没有路',
             'bg-jd-world': '这个天下：一代人的位不显',
             'bg-jd-person': '这个人：鹿门的两个写法'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 19 首·绝句第三例）；史实句均有逐字引证；'
                 'background_line 绝句形制：每层一行（1/2/3/4）；'
                 '系年第十三次判决「题自带地名，传不纪其游」→time.span/event.name/'
                 'written_during 全缺席、零 relation；KNOWN 三处之两处（隐鹿门两源+'
                 '位不显群像两源），孟亭单源不升；{{另|煙|幽}} 先登记后照登。' for k in BG}


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
    A("""-- V038：孟浩然《宿建德江》(work-t300-122) 四层背景（阶段 D 第 19 首·绝句第三例）。
-- MySQL 5.6.40 兼容。只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V010、V011、V015、V016、V018 已执行（work-t300-122 与其 text-work-t300-122-ws、
--       source-ws-t300-122 是 V018 的行；source-jiutangshu-wenyuan / source-xintangshu-wenyi
--       是 V016 的行——不另开行）。本迁移零新 source（全唐詩卷160 已由 V031 开立——
--       孟集本身已是已立来源，宿建德江即在其中，不重复引卷页桩，正文在诗页）。
--
-- 数据源（可复现）：emit_v038.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   ws-poems/宿建德江.txt（第1句含 {{另|煙|幽}} 标记原样——variants.md 先登记后照登）、
--   舊唐書卷190下（孟传首句+文苑类序总评「皆名位不振」句——后者不在孟传段内，
--   生成器断言其位置在孟传段之前，类序体例已在 locator 声明）、
--   新唐書卷203（孟传鹿门段+韩朝宗约荐段+段末「皆位不顯」+孟亭段；
--   切片传区间归属生成时断言；V031 已用切片零重叠）。
--
-- 做：0 个新 source（断言）+ 4 BACKGROUND content/claim/background +
--   7 组逐字引用（(claim,source) 主键每对恰一行）+
--   4 行 background_line（**绝句形制：每层一行** scene→1 city→2 world→3 person→4，
--   绑 text-work-t300-122-ws 的 4 行）。本迁移不碰 poetry_text_line。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log；
--   **不给诗铸 time.span、不写 event.name、不挂 written_during、零 poetry_relation 行**——见下。
--
-- 诚实边界（这首的边界是「题证地方不证时间」）：
--   * 建德=题内直载；两传行迹零吴越记载（负证逐字立出）——漫游吴越常识不补史料；
--   * 系年第十三次判决：地方有、年月无→零铸造零 relation；
--   * KNOWN 两处：隐鹿门山（旧「隠鹿門山」+新「隱鹿門山」两源合龙）、
--     位不显群像鉴定（旧类序总评+新传段末，两源独立一致）；均不外溢到诗；
--   * 孟亭/浩然亭身后纪念新传单源不升；韩朝宗荐举起点单得 LIKELY（爽约后续 V031 已立）；
--   * 死状两传分歧（不达而卒/病疽背卒）V031 已并列——本迁移不重复裁决并声明；
--   * JTS_NAME 句 V031 已立（交游侧），此处群像侧再证——跨迁移同句再证合规声明。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 37，不含 38
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-jd-%';              -- 空
--   SELECT COUNT(*) FROM poetry_text_line WHERE version_id='text-work-t300-122-ws';  -- 恰 4（绝句）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-jd-%';        -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-122';                                  -- 4（绝句每层一行）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-jd-world','claim-bg-jd-person');
--     -- KNOWN / KNOWN（world=位不显两源；person=隐鹿门两源）
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-jd-scene','claim-bg-jd-city');
--     -- LIKELY / LIKELY
--   SELECT COUNT(*) FROM poetry_claim WHERE subject_id='work-t300-122'
--     AND property_key IN ('time.span','event.name');                   -- 0（有意为0）
--   SELECT COUNT(*) FROM poetry_relation WHERE subject_id='work-t300-122';  -- 0（有意为0）
--   SELECT claim_id, source_id, COUNT(*) c FROM poetry_citation
--    WHERE claim_id LIKE 'claim-bg-jd-%'
--    GROUP BY claim_id, source_id HAVING c > 1;                         -- 空（主键唯一）
-- 回滚: recovery/V038_rollback.sql（按 id 全枚举删除；不动 V018/V031 的行，不动共用来源行）
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
    brows = [{'id': k, 'work_id': 'work-t300-122',
              'layer': {'bg-jd-scene': 'SCENE', 'bg-jd-city': 'CITY',
                        'bg-jd-world': 'WORLD', 'bg-jd-person': 'PERSON'}[k],
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

    A('\n-- ---------- 5. background_line（绝句：每层一行） ----------')
    L.append('INSERT INTO poetry_background_line (background_id, version_id, line_seq)\nSELECT * FROM (')
    L.append('\nUNION ALL\n'.join(
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-122-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A("""
-- ---------- 6. 版本账本（不给诗铸 time.span / event.name / written_during，零 relation，理由在文件头） ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 38, 'Meng Haoran Su Jian-de-jiang background layers (stage-D poem 19, third quatrain): dating verdict thirteen in a new pairing -- the title nails the PLACE (Jian-de on the Tong river, directly stated in the title) while both histories record no Wu-Yue journey at all (negative evidence quoted line by line: JTS itineraries are Lu-men mountain / the capital / Jing-zhou only) -- title proves where, never when; wandering south of the Yangtze is later common knowledge and common knowledge does not backfill sources, so time.span/event.name/written_during remain absent with zero relations; the new-sad-of-the-traveler (ri-ri mu ke-chou xin) gets a sociological dose from two independent group verdicts: the JTS class-序 remark (placed at the end of a neighbouring biography, a class-order convention, generator-asserted outside the Meng bio block, already cited by V031 on the friendship side and re-cited here on the cohort side -- cross-migration re-citation of one sentence under different claims is lawful) listing Cui Hao, Wang Chang-ling, Gao Shi, Meng Haoran as all holding low positions, and the XTS closing line of Meng-s biography saying the same of Wang and Cui -- KNOWN for the cohort verdict, never overflowing to the poem; second KNOWN: the Lu-men mountain reclusion, JTS yin Lu-men shan plus XTS yin Lu-men shan in two independent wordings; a Meng-ting commemoration note (Wang Wei painted his portrait; the pavilion renamed under Xian-tong) is XTS-only and stays LIKELY; the two death accounts divergence already registered by V031 stays un-ruled and is declared as such here; zero new sources (quan-tang-shi juan 160 opened by V031 -- Meng-s collected poems are already a sourced shelf, poem text lives on the ws page); the page-internal variant yan/you registered in variants.md before quoting'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 38);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V038 精确回滚：只删 V038 插入的行（id 全枚举）。',
         '-- work-t300-122 本体、其 text_line 4 行与 source-ws-t300-122 都是 V018 的行，绝不删；',
         '-- 共用 source 行（jiutangshu-wenyuan/xintangshu-wenyi）与 V031 的行不删；',
         '-- V038 零新 source、零 relation。',
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
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 38;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    slices = [WS_L1, WS_L2, WS_L3, WS_L4, WS_TITLE, WS_AUTHOR,
              JTS_LM, JTS_NAME, XTS_LU, XTS_HANQ, XTS_WX, XTS_MT]
    for q in slices:
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    cited = '……'.join(sorted(ex for _, _, _, ex in CITATIONS))
    for q in slices:
        if q not in cited:
            bad.append(f'切片未进入任何引文: {q[:24]}…')
    # 异文标记照录断言：{{另|煙|幽}} 原样在场
    if '{{另|煙|幽}}' not in flat:
        bad.append('{{另|煙|幽}} 标记须原样在场（先登记后照登判例）')
    # 群像两源断言：两侧关键词各在其引文
    w_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-jd-world' and s == 'source-jiutangshu-wenyuan')
    w_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-jd-world' and s == 'source-xintangshu-wenyi')
    if '皆名位不振' not in w_jts or '皆位不顯' not in w_xts:
        bad.append('位不显群像两源关键词不齐')
    # 隐鹿门两源断言
    p_jts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-jd-person' and s == 'source-jiutangshu-wenyuan')
    p_xts = next(ex for c, s, _, ex in CITATIONS if c == 'claim-bg-jd-person' and s == 'source-xintangshu-wenyi')
    if '隠鹿門山' not in p_jts or '隱鹿門山' not in p_xts:
        bad.append('隐鹿门两源（隠/隱 各自逐字）不齐')
    # 绝句形制：每层恰 1 行，合计 4
    if sum(len(v) for v in BG_LINES.values()) != 4 or any(len(v) != 1 for v in BG_LINES.values()):
        bad.append('绝句 background_line 必须是每层恰 1 行（4 层共 4 行）')
    if len(re.findall(r"text-work-t300-122-ws' AS version_id", sql)) != 4:
        bad.append('bg_line INSERT 的 version 行数应为 4')
    pairs = [(c, s) for c, s, _, _ in CITATIONS]
    if len(pairs) != len(set(pairs)):
        bad.append('poetry_citation (claim_id,source_id) 主键在本文件内重复')
    if "'written_during' AS predicate" in sql:
        bad.append("V038 有意不造 'written_during' AS predicate，但 SQL 里出现了")
    if 'INSERT INTO poetry_relation' in sql:
        bad.append('V038 有意零 poetry_relation 行，但 SQL 里出现了 INSERT')
    for pk in ('time.span', 'event.name'):
        if f"'work-t300-122' AS subject_id, '{pk}' AS property_key" in sql:
            bad.append(f'V038 有意不给诗铸 {pk}，但该主语组合出现了')
    if "SELECT 'work-t300-122' AS subject_id" in sql:
        bad.append('V038 的 claim 主语应全部是 bg-jd-*，work-t300-122 不该做主语')
    if 'DELETE FROM poetry_text_line' in sql or 'DELETE FROM poetry_text_line' in build_rollback():
        bad.append('V038 不碰 poetry_text_line')
    if 'INSERT INTO poetry_source' in sql:
        bad.append('V038 零新 source（卷160 已 V031 开立），不该出现 INSERT INTO poetry_source')
    # 「题证地方不证时间」声明必须在 BG 与文件头双处
    body_all = ''.join(BG.values()) + sql
    if '题证地方' not in body_all:
        bad.append('BG/文件头须含「题证地方不证时间」判决声明')
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
              f'切片传区间/类序位置断言；位不显群像两源断言；隐鹿门两源断言；'
              f'{{{{另|煙|幽}}}} 标记照录断言；绝句每层一行形制断言；(claim,source) 主键 '
              f'{len(set((c, s) for c, s, _, _ in CITATIONS))} 对唯一；零新 source 已断言；'
              f'诗 time.span/event.name/written_during/relation 缺席已断言')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
