#!/usr/bin/env python3
"""阶段 D：生成 V019——《春望》四层背景去草稿化（正文带证 + 逐字引证）。MySQL 5.6.40。

规矩（与 V017 同一套）：
  * 每条引文由本脚本对 /tmp/src-dl 的维基文库 wikitext 快照做**唯一锚点切片**，
    锚点在快照中必须恰好出现一次，切片与快照逐字节一致；{{YL|}}、{{SK notes|}}、{{SKchar|}}
    等录入标记原样保留，不修正、不改写。
  * 只写文件，绝不执行；核验走 Studio 的 verifySource，本迁移不核验、不发布、不改 status。
  * V004/V011/V017 的迁移文件不可变：本迁移用 UPDATE/INSERT 在其之上追加，
    并把 V004 剩下的三条「待人工核对」背景占位引证换成真实定位+逐字原文。

V019 做四件事：
  1) 四层 body_text 重写：把「（草稿：…待复核）」换成只陈述引文支撑得起的内容；
     属于注家读法的一律在正文里言明是读法，不冒充史实。
  2) 3 条 V004 背景占位引证（scene/city/world 的「待人工核对」）→ 真实来源+定位+逐字原文。
  3) 2 条新增引用（world×鹤注顾宸之争、person×鹤注陷贼营）；
     person 的两条 V011 引证扩为「……」拼接（同一来源同一 claim 只能一行，PK=(claim_id,source_id)）。
  4) 三条 claim 文本修正（world 层的「音信断绝」史无明文，改为注家分歧的如实转述）+
     certainty DISPUTED→LIKELY（两史+注本三源一致；升 KNOWN 需要的是「两说裁决」，没有）。

V019 不做：
  * 不裁决《春望》系年（757/758 两说并存，758 说至今无来源——gap-chunwang-dating-open 保持 OPEN）；
  * 不核验来源、不发布、不写 poetry_review_log（append-only，评审结论走 Studio）；
  * 不动 background_line（V004 的 8 条绑定仍有效，text-chun-wang-draft 是发布链上的版本）。

用法: python3 -I emit_v019.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re

SNAP = pathlib.Path('/tmp/src-dl')
QSS04 = (SNAP / 'qss-卷04.txt').read_text(encoding='utf-8')
TJ217 = (SNAP / 'tongjian/tj-217.txt').read_text(encoding='utf-8')
TJ218 = (SNAP / 'tongjian/tj-218.txt').read_text(encoding='utf-8')
TJ222 = (SNAP / 'tongjian/tj-222.txt').read_text(encoding='utf-8')
XTS201 = (SNAP / 'xts-卷201.txt').read_text(encoding='utf-8')
JTS190X = (SNAP / 'jts-卷190下.txt').read_text(encoding='utf-8')


def slice_between(src, start_anchor, end_anchor, what):
    """唯一锚点切片：start/end 各自在快照中恰好出现一次，且 end 在 start 之后。
    返回 [start, end] 闭区间原文，逐字节来自快照。任何一步不满足就中止——
    宁可生成失败，不能引错字。"""
    if src.count(start_anchor) != 1:
        raise SystemExit(f'锚点不唯一（{src.count(start_anchor)} 次）：{what} / {start_anchor[:20]}')
    if src.count(end_anchor) != 1:
        raise SystemExit(f'锚点不唯一（{src.count(end_anchor)} 次）：{what} / {end_anchor[:20]}')
    a = src.index(start_anchor)
    b = src.index(end_anchor)
    if b < a:
        raise SystemExit(f'锚点顺序反了：{what}')
    q = src[a:b + len(end_anchor)]
    if src.count(q) != 1:
        raise SystemExit(f'切片不唯一：{what}')
    return q


# ---------- 引文（逐字来自快照；变量名即用途） ----------
# SCENE：司马光读《春望》语（四库全书本《杜詩詳註》卷四，正文内的 {{SK notes|…}} 块）
SGY = slice_between(QSS04, '司馬温公曰', '他皆類此', '司马温公语')
# WORLD：顾宸对「家书抵万金」处境的质疑（同注条内，紧接赵氏语后；止于「當從鶴説為正」之前）
GC = slice_between(QSS04, '顧宸云', '安得云家書抵萬金', '顾宸语')
# PERSON：鹤注系年短句（V017 已核过的 note_short，同一段注）
HE = slice_between(QSS04, '春望{{SK notes|鶴注', '三月䧟賊營時所作', '鹤注短句')
# WORLD 起点：通鉴卷217 年标题 + 反于范阳
TJ755Y = slice_between(TJ217, '玄宗至道大聖大明孝皇帝下之下天寶十四年（乙未', '公元七五五年）', '通鉴755年标题')
TJ755 = slice_between(TJ217, '十一月，甲子，祿山發所部兵', '反於范陽。', '通鉴反于范阳')
# WORLD 终点：通鉴卷222 年标题 + 史朝义死
TJ763Y = slice_between(TJ222, '肅宗文明武德大聖大宣孝皇帝下之下廣德元年（癸卯', '公元七六三年）', '通鉴763年标题')
TJ763 = slice_between(TJ222, '朝義窮蹙', '懷仙取其首以獻。', '通鉴史朝义死')
# CITY：通鉴卷218 城况两句（搜捕/诛戮；同罗突厥逃归后长安大扰）
TJC1 = slice_between(TJ218, '祿山命搜捕百官', '誅及嬰孩。', '通鉴218搜捕')
TJC2 = slice_between(TJ218, '同羅、突厥之逃歸也', '獄囚自出。', '通鉴218大扰')
# PERSON：新唐书本传「困长安」；旧唐书本传「授兵曹参军」
XTS_K = slice_between(XTS201, '舉進士不中第，困長安。', '困長安。', '新唐书困长安')
JTS_OFF = slice_between(JTS190X, '天寳末，獻《三大禮賦》', '授京兆府兵曹叅軍。', '旧唐书授兵曹')

# V011 已写入库的两条 person 层引证（扩接与回滚**共用这两个常量**——手敲第二遍必出错，
# 回滚恢复到一个不存在的旧值等于没有回滚。main 里对 V011 文件逐字断言。）
V011_XTS = '時所在寇奪，甫家寓鄜，彌年艱窶，孺弱至餓死；肅宗立，自鄜州羸服欲奔行在，為賊所得'
V011_JTS = '十五載，禄山䧟京師，肅宗徴兵靈武，甫自京師宵遁赴河西謁肅宗，於彭原郡拜右拾遺'


# 拼接引文用 V017 的既有惯例：同 claim 同来源只允许一行，跨段用「……」连接，locator 里说明。
def join(*parts):
    return '……'.join(parts)


# ---------- 背景正文（读者语言，简体中文；每个史实后面站得住的只有上面那批引文） ----------
BG_TEXT = {
    'bg-chun-wang-scene': (
        '城还在，山和河也还在，可城里已经没有从前那种人气了。春天照常来了，草木没人打理，越长越深。\n'
        '这四句的读法不是我们编的：宋人录司马光的话说——「国破山河在」，明是无余物矣；'
        '「城春草木深」，明无人迹矣；花与鸟本是平时可娱之物，见之而泣、闻之而悲，「则时可知矣」。'
        '注家把这四句叫「春望之景，睹物伤怀」。以景物反衬城破，是历代注家公认的读法——'
        '它是解读的入口，不是史书记载的现场。'),
    'bg-chun-wang-city': (
        '长安是帝国的心脏。756 年秋天叛军入城之后，宫阙、街市、官署还在，但秩序已经不在了。\n'
        '秩序不在是什么样子，《资治通鉴》卷二一八记了两笔：禄山「命搜捕百官、宦者、宫女等，每获数百人，'
        '辄以兵卫送洛阳」，扈从不及、留在长安的王侯将相「诛及婴孩」；同年冬天同罗、突厥叛军逃归时，'
        '「长安大扰，官吏窜匿，狱囚自出」。杜甫此刻就在城里：两《唐书》都记他陷在贼中。'),
    'bg-chun-wang-world': (
        '这场战事的起与止，《资治通鉴》的年标题给出两个锚点：起于天宝十四年（乙未，公元七五五年）'
        '「禄山发所部兵……反于范阳」，终于广德元年（癸卯，公元七六三年）史朝义「穷蹙，缢于林中」。\n'
        '但「烽火连三月、家书抵万金」是不是因为音信断绝，注家自己就在争：仇注引黄鹤认为此诗作于陷贼之时；'
        '同一注条里顾宸反驳说，杜甫移家奉先、入鄜州时「道路未尝隔绝」，质疑「家书抵万金」的处境。'
        '所以史书上并没有「战期音信断绝是常态」的直接记载——它是这首诗的说法，也是注家取舍后的读法，'
        '不是我们替杜甫补的事实。'),
    'bg-chun-wang-person': (
        '写这首诗前后，杜甫困在长安一带，官职低微，家人不在身边。\n'
        '旧《唐书》本传记他天宝末献《三大礼赋》后被召试文章，只授了京兆府兵曹参军这样的小官；'
        '新《唐书》本传记「举进士不中第，困长安」，又说战乱中他家寄在鄜州，他衣衫破旧想去行在，半路被叛军抓住。'
        '至于写诗时他多大年纪——生卒年本身两说（旧传永泰二年卒、年五十九，新传只说大历中卒、年五十九，'
        '都没写生年），所以我们不给他标年龄。'),
}
# claim 文本修正：world 层旧文本断言「音信断绝」，史无明文（顾宸明说道路未尝隔绝），必须改
CLAIM_TEXT = {
    'claim-bg-scene': '「国破山河在」明无余物、「城春草木深」明无人迹（司马光语，见仇注卷四）：以春景反衬城破是注家读法。',
    'claim-bg-world': '战事起于755（通鉴年标题+反于范阳）终于763（通鉴年标题+史朝义死）；「家书抵万金」是否因音信断绝，注家内部有分歧（顾宸质疑鹤注）。',
}
CERTAINTY_UP = {
    # DISPUTED → LIKELY：正文的每一句现在都站在两史+注本的逐字引文上；
    # 不升 KNOWN——系年两说未裁决，处境层建立在系年语境之上。
    'claim-bg-city': 'LIKELY',
    'claim-bg-world': 'LIKELY',
    'claim-bg-person': 'LIKELY',
}


def sql_s(v):
    assert '\\' not in v, f'字面量里不许有反斜杠: {v[:40]}'
    return "'" + v.replace("'", "''") + "'"


# V004 的三条背景占位引证（UPDATE 的 WHERE 要精确匹配旧行，防误伤 V011/V017 之后的状态）
PLACEHOLDERS = {
    'claim-bg-scene': ('source-dufu-nianpu-candidate', '待人工核对：解诗依据（注本/研究）'),
    'claim-bg-city': ('source-anshi-candidate', '待人工核对：城况记载卷次'),
    'claim-bg-world': ('source-anshi-candidate', '待人工核对：战事时长与交通阻断记载'),
}


def build():
    L = []
    A = L.append
    A("""-- V019：《春望》四层背景去草稿化——正文带证 + V004 剩余占位引证换逐字原文（阶段 D）。MySQL 5.6.40 兼容。
-- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。前置：V004、V011、V015、V017 已执行。
--
-- 数据源（可复现）：引文由 emit_v019.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，
--   与快照逐字节一致；{{YL|}}、{{SK notes|}}、{{SKchar|}} 等录入标记原样保留（含 {{SKchar|2593}} 占位字符——
--   那是扫描版缺字的录入标记，照登不猜字）。快照：杜詩詳註(四庫全書本)卷四、資治通鑑卷217/218/222、
--   新唐書卷201、舊唐書卷190下。
--
-- 做：4 段背景正文重写（只说引文支撑得起的话，注家读法言明是读法）；
--   V004 剩的 3 条「待人工核对」背景占位引证换成真实来源+定位+逐字原文（scene/city/world）；
--   2 条新增引用（world×注本顾宸语、person×鹤注陷贼营）；person 两条既有引证「……」扩接新证据句；
--   2 条 claim 文本修正（world 层「音信断绝」史无明文，改为注家分歧的如实转述）；
--   3 条 certainty DISPUTED→LIKELY（两史+注本逐字引文齐备；不升 KNOWN——系年未裁决）。
-- 不做：不核验来源（走 verifySource + scripts/db/verify-sources.sh）、不改 status、不发布；
--   不裁决 757/758 系年（758 说至今无来源，gap-chunwang-dating-open 保持 OPEN）；
--   不写 poetry_review_log（append-only，评审结论走 Studio）；
--   不动 background_line、不动 V004/V011/V017 的迁移文件。
--
-- 诚实边界：
--   * 「家书抵万金≠音信断绝是史实」——顾宸语就录在同一条鹤注注文里，正文如实呈现分歧；
--   * 司马光语见于四库本《杜詩詳註》转引，页面自述需据扫描版校对：正文与引文照登快照，不据记忆改写；
--   * 生卒两说（766/大历中，皆年五十九、无生年）不裁决，正文不给年龄；
--   * 通鉴卷222 的 763 年标题在 V015 已引用于事件起讫，此处引于 world 层是不同 claim 上的独立引用，不冲突。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 18，不含 19
--   SELECT claim_id, source_id, locator FROM poetry_citation
--    WHERE claim_id IN ('claim-bg-scene','claim-bg-city','claim-bg-world') AND locator LIKE '待%';  -- 恰 3 行
--   SELECT COUNT(*) FROM poetry_citation WHERE locator LIKE '待%';      -- 记下来（应为 4：上述3条+claim-exp?若已清则3）
--   SELECT body_text FROM poetry_background WHERE id LIKE 'bg-chun-wang-%';  -- 4 段都含「待」
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_citation WHERE claim_id LIKE 'claim-bg-%' AND locator LIKE '待%';   -- 0
--   SELECT COUNT(*) FROM poetry_background WHERE id LIKE 'bg-chun-wang-%' AND body_text LIKE '%待复核%'; -- 0
--   SELECT certainty FROM poetry_claim WHERE id IN ('claim-bg-city','claim-bg-world','claim-bg-person'); -- LIKELY
--   SELECT COUNT(*) FROM poetry_citation WHERE locator LIKE '待%';      -- 比执行前少 3
-- 回滚: recovery/V019_rollback.sql（恢复 V004 原文/占位引证/原 certainty，删新增行与账本行）
START TRANSACTION;""")

    # ---------- 1. 背景正文 ----------
    A('\n-- ---------- 1. 四层正文重写（只替换仍含「待」的草稿文本，幂等且不误伤已复核文本） ----------')
    for bid in ('bg-chun-wang-scene', 'bg-chun-wang-city', 'bg-chun-wang-world', 'bg-chun-wang-person'):
        A(f"UPDATE poetry_background SET body_text = {sql_s(BG_TEXT[bid])}\n"
          f" WHERE id = {sql_s(bid)} AND body_text LIKE '%待%';")

    # ---------- 2. claim 文本修正 ----------
    A('\n-- ---------- 2. claim 文本修正（旧文本断言了史料没写的东西） ----------')
    for cid, old in (('claim-bg-scene', '以"城在而山河在"反衬物是人非。'),
                     ('claim-bg-world', '长期战事与音信断绝构成天下层。')):
        A(f"UPDATE poetry_claim SET value_text = {sql_s(CLAIM_TEXT[cid])}\n"
          f" WHERE id = {sql_s(cid)} AND value_text = {sql_s(old)};")

    # ---------- 3. 占位引证 → 真实定位 + 逐字原文 ----------
    A('\n-- ---------- 3. V004 占位引证替换（WHERE 精确匹配旧 source+locator，幂等） ----------')
    A(f"""UPDATE poetry_citation
   SET source_id = 'source-dushi-xiangzhu',
       locator = '卷四·春望·司馬溫公語（四庫本仇注转引；页面自述需据扫描版校对，引文照登快照）',
       evidence_excerpt = {sql_s(SGY)}
 WHERE claim_id = 'claim-bg-scene' AND source_id = 'source-dufu-nianpu-candidate'
   AND locator = {sql_s(PLACEHOLDERS['claim-bg-scene'][1])};""")
    A(f"""UPDATE poetry_citation
   SET source_id = 'source-zizhi-tongjian-events',
       locator = '通鑑卷二百十八·唐紀三十四（至德元載=756，由年表換算）；搜捕句與大擾句以「……」相連（同卷两事，同 claim 同来源只允许一行）',
       evidence_excerpt = {sql_s(join(TJC1, TJC2))}
 WHERE claim_id = 'claim-bg-city' AND source_id = 'source-anshi-candidate'
   AND locator = {sql_s(PLACEHOLDERS['claim-bg-city'][1])};""")
    A(f"""UPDATE poetry_citation
   SET source_id = 'source-zizhi-tongjian-events',
       locator = '通鑑卷二百十七·唐紀三十三（天寶十四年標題）起點＋卷二百二十二·唐紀三十八（廣德元年標題）終點；年標題與紀事句以「……」相連；卷217內年標題作「天寶十四年」不作「載」，照登',
       evidence_excerpt = {sql_s(join(TJ755Y, TJ755, TJ763Y, TJ763))}
 WHERE claim_id = 'claim-bg-world' AND source_id = 'source-anshi-candidate'
   AND locator = {sql_s(PLACEHOLDERS['claim-bg-world'][1])};""")

    # ---------- 4. 新增引用（PK=(claim_id,source_id)，只插本 claim 上没有该来源的行） ----------
    A('\n-- ---------- 4. 新增引用 ----------')
    A(f"""INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)
SELECT 'claim-bg-world', 'source-dushi-xiangzhu',
       '卷四·春望·注條（顧宸語：對「家書抵萬金」处境的质疑，紧接趙氏語後；同條內另有仇氏「當從鶴説為正」的取舍，引文止于顧語）',
       {sql_s(GC)}
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_citation
  WHERE claim_id = 'claim-bg-world' AND source_id = 'source-dushi-xiangzhu');""")
    A(f"""INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)
SELECT 'claim-bg-person', 'source-dushi-xiangzhu',
       '卷四·春望·鶴注（「陷賊營時所作」：人在賊佔長安的注本依据；至德二載=757，由年表換算，係年仍 DISPUTED）',
       {sql_s(HE)}
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_citation
  WHERE claim_id = 'claim-bg-person' AND source_id = 'source-dushi-xiangzhu');""")

    # ---------- 5. person 两条既有引证「……」扩接（V011 的行，WHERE 匹配 V011 当时的写法） ----------
    A('\n-- ---------- 5. person 层既有引证扩接（同一 claim 同一来源只能一行，用「……」补证据句） ----------')
    A(f"""UPDATE poetry_citation
   SET locator = '卷二百一·文藝上·杜甫传（V011 定位；困長安句與奔行在被獲句以「……」相連）',
       evidence_excerpt = {sql_s(join(XTS_K, V011_XTS))}
 WHERE claim_id = 'claim-bg-person' AND source_id = 'source-dufu-zhuan-candidate'
   AND evidence_excerpt = {sql_s(V011_XTS)};""")
    A(f"""UPDATE poetry_citation
   SET locator = '卷一百九十下·杜甫传（V011 定位；授兵曹句與陷京師宵遁句以「……」相連，先卑官後陷賊，时序如传文）',
       evidence_excerpt = {sql_s(join(JTS_OFF, V011_JTS))}
 WHERE claim_id = 'claim-bg-person' AND source_id = 'source-jiutangshu-dufu'
   AND evidence_excerpt = {sql_s(V011_JTS)};""")

    # ---------- 6. certainty ----------
    A('\n-- ---------- 6. certainty DISPUTED→LIKELY（逐字引文齐备；系年未裁决所以不升 KNOWN） ----------')
    for cid in ('claim-bg-city', 'claim-bg-world', 'claim-bg-person'):
        A(f"UPDATE poetry_claim SET certainty = 'LIKELY'\n"
          f" WHERE id = {sql_s(cid)} AND certainty = 'DISPUTED' AND status <> 'PUBLISHED';")

    # ---------- 7. 来源行不动说明 + 账本 ----------
    A("""
-- ---------- 7. 说明 ----------
-- source-anshi-candidate / source-dufu-nianpu-candidate 两行保留（PENDING）：
--   它们在别的 claim 上仍可能被引用（如 claim-anshi-time），本迁移只挪走背景层对它们的占位引用；
--   来源行何时退役是核验后的事，不由本迁移裁决。
-- background_line 未动：4 层×2 行绑定（text-chun-wang-draft 1,2/1,2/5,6/7,8）仍然有效。
-- V018 为 work-chun-wang 新立的 text-work-chun-wang-ws（8 行同文）如要接背景，等场景链
--   切到该版本时再补绑定，避免 facts 导出的 background_line_counts 与校验器对不上。

-- ---------- 8. 版本账本 ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 19, 'chun-wang background layers de-drafted: sourced body text, 3 placeholder citations replaced by verbatim tongjian/commentary text, 2 inserts, 2 extends; dating stays unresolved'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 19);
COMMIT;""")
    return '\n'.join(L) + '\n'


# V004 原文（回滚恢复用——从 V004 文件逐字复制，不是重新敲的；见下方校验）
V004_BG = {
    'bg-chun-wang-scene': '城还在，山和河也还在，可它已经不是从前的样子。春天照常来了，草木疯长，长满了没人打理的街巷。（草稿：以景物反衬，措辞待复核）',
    'bg-chun-wang-city': '长安是帝国的心脏。都城被占之后，宫阙、街市、官署还在，但秩序已经不在了。（草稿：城市作为处境，需核对城况史源）',
    'bg-chun-wang-world': '这场战事从755年打到763年（通行纪年，待核），前后多年，音信断绝是常态。"家书抵万金"不是夸张的说法，是当时的实际处境。（草稿）',
    'bg-chun-wang-person': '写这首诗时杜甫正困在长安一带，官职低微、家人离散。（草稿：具体年份与官职待年谱核对，不假设确定故事）',
}
V004_CIT = {  # claim -> (source, locator)
    'claim-bg-scene': ('source-dufu-nianpu-candidate', '待人工核对：解诗依据（注本/研究）'),
    'claim-bg-city': ('source-anshi-candidate', '待人工核对：城况记载卷次'),
    'claim-bg-world': ('source-anshi-candidate', '待人工核对：战事时长与交通阻断记载'),
}


def build_rollback():
    L = ['-- V019 精确回滚：恢复到 V019 执行前的状态（V004 原文/占位引证/V011 引证原样/DISPUTED）。',
         '-- 逐条 UPDATE 都带当前值守卫：只在 V019 的效果确实存在时回滚，幂等。',
         'START TRANSACTION;']
    for bid, old in V004_BG.items():
        L.append(f"UPDATE poetry_background SET body_text = {sql_s(old)}\n"
                 f" WHERE id = {sql_s(bid)} AND body_text <> {sql_s(old)};")
    L.append(f"UPDATE poetry_claim SET value_text = '以\"城在而山河在\"反衬物是人非。'\n"
             " WHERE id = 'claim-bg-scene' AND value_text <> '以\"城在而山河在\"反衬物是人非。';")
    L.append("UPDATE poetry_claim SET value_text = '长期战事与音信断绝构成天下层。'\n"
             " WHERE id = 'claim-bg-world' AND value_text <> '长期战事与音信断绝构成天下层。';")
    for cid, (sid, loc) in V004_CIT.items():
        L.append(f"""UPDATE poetry_citation
   SET source_id = {sql_s(sid)}, locator = {sql_s(loc)}, evidence_excerpt = NULL
 WHERE claim_id = {sql_s(cid)} AND source_id <> {sql_s(sid)};""")
    for cid in ('claim-bg-world', 'claim-bg-person'):
        L.append(f"DELETE FROM poetry_citation WHERE claim_id = {sql_s(cid)} AND source_id = 'source-dushi-xiangzhu';")
    L.append(f"""UPDATE poetry_citation
   SET locator = '卷二百一·文藝上·杜甫传',
       evidence_excerpt = {sql_s(V011_XTS)}
 WHERE claim_id = 'claim-bg-person' AND source_id = 'source-dufu-zhuan-candidate'
   AND evidence_excerpt LIKE '%……%';""")
    L.append(f"""UPDATE poetry_citation
   SET locator = '卷一百九十下·杜甫传',
       evidence_excerpt = {sql_s(V011_JTS)}
 WHERE claim_id = 'claim-bg-person' AND source_id = 'source-jiutangshu-dufu'
   AND evidence_excerpt LIKE '%……%';""")
    for cid in ('claim-bg-city', 'claim-bg-world', 'claim-bg-person'):
        L.append(f"UPDATE poetry_claim SET certainty = 'DISPUTED'\n"
                 f" WHERE id = {sql_s(cid)} AND certainty = 'LIKELY';")
    L.append("DELETE FROM poetry_schema_version WHERE version_no = 19;")
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    # 每条引文必须与快照逐字节一致（防手滑改动；切片本身已保证，这里对最终 SQL 再验一遍）。
    # 只验「原文出现在 SQL 里」——带引号验证会在「……」拼接引文处误报（片段后面跟的不是引号）。
    flat = sql.replace("''", "'")
    for q in (SGY, GC, HE, TJ755Y, TJ755, TJ763Y, TJ763, TJC1, TJC2, XTS_K, JTS_OFF):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
    # 占位文本只允许出现在 WHERE 侧（匹配旧行用），SET 侧出现 = 把占位又写回去了。
    # 不能拿 SET…; 当语句体：第一个分号在语句末尾，WHERE 会被误圈进来。截到 WHERE 为止。
    for _, loc in PLACEHOLDERS.values():
        for m in re.finditer(r'\bSET\b(.*?)\bWHERE\b', sql, re.S):
            if loc in m.group(1):
                bad.append(f'占位定位出现在 SET 侧: {loc}')
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-sql', required=True)
    ap.add_argument('--out-rollback', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    # 回滚里的 V004 原文必须真在 V004 文件里（防止「回滚到一个不存在的旧值」）
    v004 = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/'
                        'V004__chunwang_context_draft.sql').read_text(encoding='utf-8')
    for old in V004_BG.values():
        assert old in v004, f'V004 原文核对失败: {old[:20]}…'
    for _, loc in V004_CIT.values():
        assert loc in v004, f'V004 占位定位核对失败: {loc}'
    # 回滚要把这两条恢复到 V011 写下的原样——字面量必须逐字出现在 V011 文件里
    v011 = pathlib.Path('/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/'
                        'V011__chunwang_verified_evidence.sql').read_text(encoding='utf-8')
    for lit in (V011_XTS, V011_JTS):
        assert lit in v011, f'V011 原文核对失败: {lit[:20]}…'
    sql = build()
    rb = build_rollback()
    bad = audit(sql)
    if bad:
        print('AUDIT FAIL:')
        for b in bad:
            print(' -', b)
        raise SystemExit(1)
    if args.dry_run:
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B, 引文 {11} 条全部逐字过审')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
