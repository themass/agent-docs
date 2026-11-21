#!/usr/bin/env python3
"""阶段 D 第 3 首：生成 V021——《春宿左省》(work-t300-209, V018 已立) 四层背景。MySQL 5.6.40。

V021 与 V020 同形：纯新增（4 content + 4 claim + 4 background + 引用逐字原文 + background_line
绑 text-work-t300-209-ws + 1 条 time.span + 1 条 written_during 安史之乱挂接）。

这首诗的证据形状与月夜不同——注本材料本地没有（实测：《杜詩詳註》四庫本卷03/卷04/卷05 快照
均无「春宿左省」与「花隱掖垣」——此诗在卷六，快照未抓到且维基文库当前不可达），
所以 SCENE 层**不引任何注家语**，只引诗本文作内证，
并把「掖垣/金钥的职官制度解释需要注本，未核」写成正文里的诚实边界。
PERSON 层反而最厚：《旧唐书》本传连续一段（救房琯到下辟华州）+《新唐书》拜右拾遗，都是逐字切片。
WORLD/CITY 用通鉴卷220 至德二年收京三段。

用法: python3 -I emit_v021.py --out-sql <path> --out-rollback <path> [--dry-run]
"""
import argparse
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
from emit_v019 import (  # noqa: E402  切片器/SQL字面量/共用引文——单一来源，不抄第二份
    slice_between, sql_s, join, TJ755Y, TJ755, TJ763Y, TJ763,
)

TJ220 = (pathlib.Path('/tmp/src-dl/tongjian/tj-220.txt')).read_text(encoding='utf-8')
XTS201 = (pathlib.Path('/tmp/src-dl/xts-卷201.txt')).read_text(encoding='utf-8')
JTS190X = (pathlib.Path('/tmp/src-dl/jts-卷190下.txt')).read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；锚不唯一即中止） ----------
TJ757Y = slice_between(TJ220, '肅宗文明武德大聖大宣孝皇帝中之下至德二年（丁酉', '公元七五七年）', '通鉴757年标题')
TJ_ENTER = slice_between(TJ220, '遲明，諜至，守忠、歸仁與張通儒、田乾真等皆已遁矣。癸卯', '大軍入西京。', '通鉴大军入西京')
TJ_CHEER = slice_between(TJ220, '俶整眾入城，百姓老幼', '歡呼悲泣。', '通鉴百姓欢呼悲泣')
XTS_SHIYI = slice_between(XTS201, '至德二年，亡走鳳翔上謁', '拜右拾遺。', '新唐书拜右拾遗')
JTS_FANGGUAN = slice_between(
    JTS190X, '房琯布衣時與甫善', '出甫為華州司功叅軍。', '旧唐书救房琯段')

# 诗本文（V018 已入库的 8 句）不作为独立引文重复登记——SCENE 层引它就是把同一正文再抄一遍，
# locator 指向 V018 的 claim-t300-209-text 引文行即可，见 CITATIONS 第一条。

BG = {
    'bg-chunsu-scene': (
        '这个夜晚在宫里。傍晚花影落在宫墙的缺口上，归鸟啾啾地掠过；入夜后锁钥的声音清晰可闻——'
        '值夜的谏官睡不着，一遍遍问夜多深了，因为明天一早要把密封的奏章递进去。\n'
        '「掖垣」「金钥」具体指什么建筑、什么门禁，需要注本来解释——这层注本我们还没有核到，'
        '不敢代注家下定义。能说的是：这一切都是诗里的场景，诗题为「春宿左省」，值夜是这首诗的现场。'),
    'bg-chunsu-city': (
        '这座城刚被收复不久。至德二载（丁酉，公元七五七年）九月癸卯，广平王俶统率的「朔方等军及回纥、'
        '西域之众十五万，号二十万」进入西京，《资治通鉴》写长安百姓：「俶整众入城，百姓老幼'
        '夹道欢呼悲泣。」\n'
        '「星临万户动，月傍九霄多」的万户与九霄，写的正是这座刚收回宫阙的京城——'
        '在刚刚失而复得的人眼里，星空下的宫殿才会那样亮。'),
    'bg-chunsu-world': (
        '战事此时打到了第四年：起于天宝十四年（乙未，公元七五五年）「禄山发所部兵……反于范阳」，'
        '广德元年（癸卯，公元七六三年）史朝义「穷蹙，缢于林中」才收场——两端都在《资治通鉴》年标题里。\n'
        '至德二年是转折之年：年标题下记着「癸卯，大军入西京」——长安回到了唐朝手里。'
        '但仗没打完：诗中「明朝有封事」那份连夜准备的上疏，就是乱世里谏官的日常。'),
    'bg-chunsu-person': (
        '写这首诗时杜甫是右拾遗——《新唐书》本传记他「至德二年，亡走凤翔上谒，拜右拾遗」：'
        '从长安跑去凤翔投奔肃宗，被留了这个从八品的谏官。\n'
        '这个位置他没坐多久，旧《唐书》本传记了完整一段：房琯布衣时与杜甫交好，为宰相后自请率军讨贼，'
        '「琯兵败于陈涛斜」，来年春被罢相，「甫上疏言琯有才，不宜罢免。肃宗怒，贬琯为刺史，'
        '出甫为华州司功参军」——救朋友，触怒皇帝，被赶出京城。'
        '「明朝有封事」不是一个履职动作的抒情化：这个人的奏疏真的会换来贬官。'),
}
CLAIMS = {
    'claim-bg-chunsu-scene': (
        'INTERPRETATION', 'LIKELY',
        '值夜场景为诗本文内证（题「春宿左省」）；掖垣/金钥的制度解释需注本，未核——正文已声明边界。'),
    'claim-bg-chunsu-city': (
        'FACT', 'LIKELY',
        '至德二载九月收西京与百姓欢呼有通鉴卷220逐字记载；宫殿星月意象为诗本文内证。'),
    'claim-bg-chunsu-world': (
        'FACT', 'LIKELY',
        '战事起讫以通鉴年标题为锚（755反于范阳/763史朝义死）；757收京以通鉴卷220年标题+入京句为锚。'),
    'claim-bg-chunsu-person': (
        'FACT', 'KNOWN',
        '拜右拾遗（新唐书本传）与救房琯被出（旧唐书本传连续一段）为两史各自逐字记载，事件链完整；升 KNOWN。'),
}
# 注：person 的 KNOWN 理由与 V017 陷长安 756 同标准——两个独立来源各记一段、互不矛盾、都逐字可指。
CITATIONS = [
    ('claim-bg-chunsu-scene', 'source-quantangshi-225',
     '卷225·杜甫·春宿左省（锚点 ==春宿左省==；诗本文八句为内证，见 V018 claim-t300-209-text 引文）',
     '花隱掖垣暮，……數問夜如何。'),
    ('claim-bg-chunsu-city', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十·唐紀（至德二年丁酉=757，卷內年標題自带公元）；入京句與歡呼句以「……」相連',
     join(TJ_ENTER, TJ_CHEER)),
    ('claim-bg-chunsu-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百十七（天寶十四年標題+反于范陽）與卷二百二十二（廣德元年標題+史朝義死）為起訫；'
     '卷二百二十至德二年標題+入西京句為轉折；四段以「……」相連；卷217年標題作「天寶十四年」不作「載」，照登',
     join(TJ755Y, TJ755, TJ757Y, TJ_ENTER, TJ763Y, TJ763)),
    ('claim-bg-chunsu-person', 'source-dufu-zhuan-candidate',
     '卷二百一·文藝上·杜甫传（拜右拾遗原文）',
     XTS_SHIYI),
    ('claim-bg-chunsu-person', 'source-jiutangshu-dufu',
     '卷一百九十下·杜甫传（救房琯段连续原文：交好—兵败—罢相—上疏—贬琯出甫）',
     JTS_FANGGUAN),
]
BG_LINES = {'bg-chunsu-scene': (1, 2), 'bg-chunsu-city': (3, 4),
            'bg-chunsu-person': (5, 6), 'bg-chunsu-world': (7, 8)}
BG_AUDIENCE = {'bg-chunsu-scene': 'PRIMARY', 'bg-chunsu-city': 'JUNIOR',
               'bg-chunsu-world': 'SENIOR', 'bg-chunsu-person': 'JUNIOR'}
BG_TITLES = {'bg-chunsu-scene': '眼前：宫墙里的值夜',
             'bg-chunsu-city': '这座城：刚刚收回的京城',
             'bg-chunsu-world': '这个天下：打到转折之年的战事',
             'bg-chunsu-person': '这个人：刚上任就会因奏疏获罪的谏官'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 3 首）；史实句均有逐字引证；制度词未核到的已写成正文边界。' for k in BG}


def guard(table, cols, rows, match_expr):
    sel = '\nUNION ALL\n'.join(
        'SELECT ' + ', '.join(f'{sql_s(r[c])} AS {c}' for c in cols) + ' FROM DUAL'
        for r in rows)
    return (f'INSERT INTO {table} ({", ".join(cols)})\n'
            f'SELECT * FROM (\n{sel}\n) AS t\n'
            f'WHERE NOT EXISTS (SELECT 1 FROM {table} x WHERE {match_expr});')


def build():
    L = []
    A = L.append
    A("""-- V021：《春宿左省》(work-t300-209) 四层背景 + 系年 + 安史线挂接（阶段 D 第 3 首）。MySQL 5.6.40 兼容。
-- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V003、V011、V015、V017、V018 已执行（background_line 绑 text-work-t300-209-ws，V018 插的行）。
--
-- 数据源（可复现）：emit_v021.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   資治通鑑卷217/220/222（切片与 V019/V020 共用同一代码路径）、新唐書卷201、舊唐書卷190下。
--
-- 做：4 BACKGROUND content/claim/background（正文全带证或如实声明边界）+ 5 组逐字引用 +
--   8 行 background_line（scene→1,2｜city→3,4｜person→5,6｜world→7,8，绑 text-work-t300-209-ws）+
--   系年断言 claim-chun-su-time-757（两史合证 → LIKELY）+ written_during 安史之乱挂接。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log。
--
-- 诚实边界：
--   * 「掖垣/金钥」的制度解释需要注本（杜诗详注卷五本地快照正文为空、维基文库当前不可达）——
--     SCENE 层因此零注家引用，正文向读者声明这一点；
--   * 系年 757 由「新唐书至德二年拜右拾遗」+「旧唐书明年春救房琯时已为左省官」合证推出，
--     不是注本单源，也不是年谱原文，故 LIKELY；
--   * person 层升 KNOWN 的标准与 V017 陷长安 756 一致：两个独立来源各记一段、互不矛盾、逐字可指。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 20，不含 21
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-chunsu-%';          -- 空
--   SELECT id FROM poetry_text_version WHERE id='text-work-t300-209-ws';  -- 恰 1 行（V018 已执行）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-chunsu-%';    -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-209';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-chunsu-person';  -- KNOWN
-- 回滚: recovery/V021_rollback.sql（按 id 全枚举删除；不动 V018 的任何行）
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
    brows = [{'id': k, 'work_id': 'work-t300-209',
              'layer': {'bg-chunsu-scene': 'SCENE', 'bg-chunsu-city': 'CITY',
                        'bg-chunsu-world': 'WORLD', 'bg-chunsu-person': 'PERSON'}[k],
              'body_text': BG[k], 'audience': BG_AUDIENCE[k], 'claim_id': 'claim-' + k} for k in BG]
    A(guard('poetry_background', ['id', 'work_id', 'layer', 'body_text', 'audience', 'claim_id'],
            brows, 'x.id = t.id'))

    A('\n-- ---------- 4. 逐字引文 ----------')
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-209-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A('\n-- ---------- 6. 系年（两史合证 → LIKELY；locator 写明是合证推出，不是年谱原文） ----------')
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            [{'id': 'claim-chun-su-time-757', 'subject_id': 'work-t300-209', 'property_key': 'time.span',
              'value_text': '757..757 (EXACT) 至德二载春任左省时作：新唐书「至德二年…拜右拾遗」+旧唐书救房琯段'
                            '（罢相在明年春=758，值左省时在757收京后）——两史合证推出，非年谱原文',
              'claim_kind': 'FACT', 'certainty': 'LIKELY'}], 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': 'work-t300-209', 'property_key': 'time.span', 'claim_id': 'claim-chun-su-time-757'}],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))
    A(f"""INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)
SELECT * FROM (
SELECT 'claim-chun-su-time-757' AS claim_id, 'source-dufu-zhuan-candidate' AS source_id,
       '卷二百一·文藝上·杜甫传（至德二年=757，卷标题在传内；拜右拾遗）' AS locator, {sql_s(XTS_SHIYI)} AS evidence_excerpt FROM DUAL
UNION ALL
SELECT 'claim-chun-su-time-757' AS claim_id, 'source-jiutangshu-dufu' AS source_id,
       '卷一百九十下·杜甫传（「其年十月…明年春，琯罢相」：明年春=乾元元年758，上疏时杜甫在左省任内）' AS locator,
       {sql_s(JTS_FANGGUAN)} AS evidence_excerpt FROM DUAL
) AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_citation x WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);""")

    A('\n-- ---------- 7. written_during 安史之乱（形状同 V017/V020） ----------')
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            [{'id': 'claim-chun-su-in-anshi', 'subject_id': 'work-t300-209', 'property_key': 'event.name',
              'value_text': '安史之亂（755–763）。係年757在亂期內；「明朝有封事」與房琯兵敗後朝局為亂中語境依據',
              'claim_kind': 'FACT', 'certainty': 'LIKELY'}], 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': 'work-t300-209', 'property_key': 'event.name', 'claim_id': 'claim-chun-su-in-anshi'}],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))
    A(f"""INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)
SELECT * FROM (
SELECT 'claim-chun-su-in-anshi' AS claim_id, 'source-zizhi-tongjian-events' AS source_id,
       '通鑑卷二百二十·至德二年（丁酉，公元七五七年）年標題+入西京句（757在亂期內的紀年錨）' AS locator,
       {sql_s(join(TJ757Y, TJ_ENTER))} AS evidence_excerpt FROM DUAL
UNION ALL
SELECT 'claim-chun-su-in-anshi' AS claim_id, 'source-jiutangshu-dufu' AS source_id,
       '卷一百九十下·杜甫传（房琯陳濤斜之敗與貶琯出甫：亂中朝局內證）' AS locator,
       {sql_s(JTS_FANGGUAN)} AS evidence_excerpt FROM DUAL
) AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_citation x WHERE x.claim_id = t.claim_id AND x.source_id = t.source_id);""")
    A(guard('poetry_relation', ['id', 'subject_id', 'predicate', 'object_id', 'claim_id'],
            [{'id': 'rel-work-t300-209-written-during-anshi', 'subject_id': 'work-t300-209',
              'predicate': 'written_during', 'object_id': 'event-anshi-rebellion',
              'claim_id': 'claim-chun-su-in-anshi'}],
            'x.id = t.id OR (x.subject_id = t.subject_id AND x.predicate = t.predicate AND x.object_id = t.object_id)'))

    A("""
-- ---------- 8. 版本账本 ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 21, 'chun-su-zuo-sheng background layers (inserts-only): tongjian 757 recovery + two histories on the advisor year; SCENE layer has zero commentary quotes by design (no commentary snapshot locally; boundary stated in text)'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 21);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V021 精确回滚：只删 V021 插入的行（id 全枚举）。work-t300-209 本体是 V018 的行，绝不删。',
         'START TRANSACTION;']
    cids = list(CLAIMS) + ['claim-chun-su-time-757', 'claim-chun-su-in-anshi']

    def dels(table, col, vals, chunk=40):
        for i in range(0, len(vals), chunk):
            L.append(f'DELETE FROM {table} WHERE {col} IN ('
                     + ', '.join(sql_s(v) for v in vals[i:i + chunk]) + ');')
    dels('poetry_claim_selection', 'claim_id', cids)
    dels('poetry_citation', 'claim_id', cids)
    dels('poetry_relation', 'id', ['rel-work-t300-209-written-during-anshi'])
    dels('poetry_background_line', 'background_id', list(BG))
    dels('poetry_background', 'id', list(BG))
    dels('poetry_claim', 'id', cids)
    dels('poetry_content', 'id', list(BG))
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 21;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (TJ757Y, TJ_ENTER, TJ_CHEER, XTS_SHIYI, JTS_FANGGUAN, TJ755Y, TJ755, TJ763Y, TJ763):
        if q not in flat:
            bad.append(f'引文未逐字进入 SQL: {q[:24]}…')
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 9 条逐字过审')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
