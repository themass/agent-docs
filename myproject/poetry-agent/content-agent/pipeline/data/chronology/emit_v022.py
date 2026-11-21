#!/usr/bin/env python3
"""阶段 D 第 4 首：生成 V022——《聞官軍收河南河北》(work-t300-217, V018 已立) 四层背景。MySQL 5.6.40。

V022 与 V020/V021 同形：纯新增（4 content + 4 claim + 4 background + 8 组逐字引用 +
background_line 绑 text-work-t300-217-ws + 1 条 time.span + 1 条 written_during 安史之乱挂接）。

这首诗是阶段 D 弧线的收口：春望（陷城之春）→ 月夜（贼中之夜）→ 春宿左省（收复后值夜）→
聞官軍收河南河北（战事结束时的一刻）。

证据形状的两个特殊点（都已实测，不是想当然）：
  1) 《全唐詩》卷227 快照里此诗**只有转引用桩** `{{:聞官軍收河南河北}}`，无正文——
     所以引诗本文一律走 ws 诗页快照 source-ws-t300-217（V018 立的行），页面里的
     `[[w:…|…]]` 消歧链接与 `{{*|原注…}}` 标记照登不猜字；
  2) 写作地点（旧注梓州说）本地无注本可核——SCENE 层零注家引用，正文向读者明说。

用法: python3 -I emit_v022.py --out-sql <path> --out-rollback <path> [--dry-run]
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

TJ222 = pathlib.Path('/tmp/src-dl/tongjian/tj-222.txt').read_text(encoding='utf-8')
XTS201 = pathlib.Path('/tmp/src-dl/xts-卷201.txt').read_text(encoding='utf-8')
JTS190X = pathlib.Path('/tmp/src-dl/jts-卷190下.txt').read_text(encoding='utf-8')
WS217 = pathlib.Path('/tmp/src-dl/ws-poems/聞官軍收河南河北.txt').read_text(encoding='utf-8')

# ---------- 切片（唯一锚点，逐字节；锚不唯一即中止） ----------
TJ_TOKU = slice_between(TJ222, '大軍乘之而入', '制釋之。', '通鉴克东京')
TJ_TOKU_SACK = slice_between(TJ222, '回紇入東京', '士民皆衣紙。', '通鉴回纥掠东京')
TJ_GRANT = slice_between(TJ222, '時河北諸州皆已降', '敬冀無事，因而授之。', '通鉴授降将河北')  # 尾锚须带「敬冀無事」——「因而授之。」在卷222另见白孝德事，单用不唯一
WS_LINE1 = slice_between(WS217, '劍]]外忽傳收', '滿衣裳。', 'ws诗页第一行')
WS_NOTE = slice_between(WS217, '{{*|原注', '東京}}', 'ws诗页原注')
XTS_JN = slice_between(XTS201, '流落劍南', '檢校工部員外郎。', '新唐书剑南幕段')
JTS_GW = slice_between(JTS190X, '{{YL|上元二年}}冬，黄門侍郎', '賜緋魚袋。', '旧唐书工部员外郎句')

BG = {
    'bg-wgjs-scene': (
        '捷报是从「剑外」传来的——剑门关之外，也就是他流落寄居的蜀中。诗里写的全是身体的反应：'
        '忽然听到，先哭；回头看妻子，她的愁容不知什么时候没了；随手卷起诗书，高兴得近乎发狂。\n'
        '旧注对「在哪座城听到的」有说法（梓州说），但那出自我们本地核不到的注本——所以这里不写城名。'
        '能核到的只有诗本身：题目叫「闻官军收河南河北」，这首诗记的就是「闻」的那一瞬间。'),
    'bg-wgjs-city': (
        '他要东回去的地方是洛阳——诗里的原注说「余田园在东京」（维基文库页面上的原注，'
        '带 {{*|}} 标记照登）。可《资治通鉴》卷222 记下洛阳光复的同时还有一笔：'
        '「怀恩进克东京及河阳城」之后，「回纥入东京，肆行杀略，死者万计，火累旬不灭」，'
        '连自家朔方、神策军也「所过虏掠，三月乃已，比屋荡尽，士民皆衣纸」。\n'
        '「便下襄阳向洛阳」那条欢欣的路，通向的是这样一座刚收回又被劫空的城。'
        '诗里一个字没有提；这个反差不是我们加的情节，是通鉴的记事自己摆在那里的。'),
    'bg-wgjs-world': (
        '这场战事打到这里收场：起于天宝十四年（乙未，公元七五五年）「禄山发所部兵……反于范阳」，'
        '到广德元年（癸卯，公元七六三年）「朝义穷蹙，缢于林中，怀仙取其首以献」——两端都在《资治通鉴》年标题里。\n'
        '但通鉴紧接着还记了一笔：河北诸州都降了，降将薛嵩、田承嗣、李怀仙「迎仆固怀恩，拜于马首」，'
        '怀恩「恐贼平宠衰」奏请留他们分帅河北「自为党援」，而「朝廷亦厌苦兵革，敬冀无事，因而授之」。\n'
        '诗里是狂喜，通鉴那页上是「平而不安」——同一个天下的两个方向。这个并置读法来自通鉴记事的先后次序，'
        '是我们的读法标注，不是史文的判断。'),
    'bg-wgjs-person': (
        '写这首诗时杜甫在剑南幕府。两《唐书》本传各记一段、互相印证：'
        '《新唐书》：「流落剑南，结庐成都西郭。召补京兆功曹参军，不至。会严武节度剑南东、西川，往依焉。'
        '武再帅剑南，表为参谋，检校工部员外郎。」《旧唐书》：'
        '「严武镇成都，奏为节度参谋检校尚书工部员外郎，赐绯鱼袋。」\n'
        '新唐书里还有单独一笔：朝廷召他补京兆功曹参军（京畿的官），他「不至」，人留在蜀中。'
        '而听到河南河北收复，他在诗里写「便下襄阳向洛阳」——去不去洛阳这件事，传里只记了「不至」两个字，'
        '为什么不去、听到捷报时怎么想，传没有说，我们也不替他补。'),
}
CLAIMS = {
    'claim-bg-wgjs-scene': (
        'INTERPRETATION', 'LIKELY',
        '闻讯场景为诗本文内证（题「聞官軍收河南河北」+八句）；旧注写作地点说本地无注本可核，正文已声明不采。'),
    'claim-bg-wgjs-city': (
        'FACT', 'LIKELY',
        '克东京与回纥/朔方军掠东京有通鉴卷222逐字记载；「余田园在东京」有页面原注逐字。'),
    'claim-bg-wgjs-world': (
        'FACT', 'LIKELY',
        '战事起讫以通鉴年标题为锚（755反于范阳/763史朝义死，与 V019/V021 同一批切片）；'
        '授降将河北有通鉴卷222逐字；「平而不安」并置读法已在正文标明为读法。'),
    'claim-bg-wgjs-person': (
        'FACT', 'KNOWN',
        '严武镇蜀、甫为节度参谋检校工部员外郎——两唐书本传各记一段、互不矛盾、逐字可指，升 KNOWN'
        '（与 V017/V021 同标准）；「召补京兆功曹参军不至」为新唐书单源，正文仅作并置不引申。'),
}
CITATIONS = [
    ('claim-bg-wgjs-scene', 'source-ws-t300-217',
     '页面 聞官軍收河南河北（诗第一行原样含消歧链接标记 [[w:…|…]]，照登不猜字；'
     '八句全文见 V018 claim-t300-217-text 引文）',
     WS_LINE1),
    ('claim-bg-wgjs-city', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十二·唐紀三十八（寶應元年東京之復與回紇之掠；两段以「……」相连）',
     join(TJ_TOKU, TJ_TOKU_SACK)),
    ('claim-bg-wgjs-city', 'source-ws-t300-217',
     '页面 聞官軍收河南河北（诗末原注，{{*|}} 标记照登）',
     WS_NOTE),
    ('claim-bg-wgjs-world', 'source-zizhi-tongjian-events',
     '通鑑卷二百十七（755起）與卷二百二十二（763訖+授降将河北）；五段以「……」相连；'
     '卷217年標題作「天寶十四年」不作「載」，照登',
     join(TJ755Y, TJ755, TJ763Y, TJ763, TJ_GRANT)),
    ('claim-bg-wgjs-person', 'source-dufu-zhuan-candidate',
     '卷二百一·文藝上·杜甫传（流落剑南—召补不至—依严武—检校工部员外郎，连续原文）',
     XTS_JN),
    ('claim-bg-wgjs-person', 'source-jiutangshu-dufu',
     '卷一百九十下·杜甫传（上元二年严武镇成都奏授一段；{{YL|}} 标记照登）',
     JTS_GW),
    ('claim-wgjs-time-763', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十二·廣德元年（癸卯，公元七六三年）年標題+史朝義死（系年下限锚；'
     '「青春作伴」为春字内证——合推非注本系年）',
     join(TJ763Y, TJ763)),
    ('claim-wgjs-in-anshi', 'source-zizhi-tongjian-events',
     '通鑑卷二百二十二·廣德元年（丁…年標題+史朝義死：763在亂期內的紀年錨）',
     join(TJ763Y, TJ763)),
]
BG_LINES = {'bg-wgjs-scene': (1, 2), 'bg-wgjs-person': (3, 4),
            'bg-wgjs-world': (5, 6), 'bg-wgjs-city': (7, 8)}
BG_AUDIENCE = {'bg-wgjs-scene': 'PRIMARY', 'bg-wgjs-person': 'JUNIOR',
               'bg-wgjs-world': 'SENIOR', 'bg-wgjs-city': 'JUNIOR'}
BG_TITLES = {'bg-wgjs-scene': '眼前：剑外忽然传来的捷报',
             'bg-wgjs-city': '这条路：通往刚被劫空的东都',
             'bg-wgjs-world': '这个天下：战事收场的一刻与它埋下的线头',
             'bg-wgjs-person': '这个人：召他回京他不去的蜀中幕客'}
BG_SUMMARY = {k: '四层处境背景（阶段 D 第 4 首·弧线收口）；史实句均有逐字引证；'
                 '注本核不到的（写作地点）与读法（平而不安并置）均如实标明。' for k in BG}


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
    A("""-- V022：《聞官軍收河南河北》(work-t300-217) 四层背景 + 系年 + 安史线挂接（阶段 D 第 4 首）。MySQL 5.6.40 兼容。
-- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。
-- 前置：V004、V010、V015、V018 已执行（background_line 绑 text-work-t300-217-ws，V018 插的行；
--       source-ws-t300-217 亦 V018 所立；event-anshi-rebellion 见 V015；source-jiutangshu-dufu 见 V010）。
--
-- 数据源（可复现）：emit_v022.py 对 /tmp/src-dl 维基文库 wikitext 快照做唯一锚点切片，逐字节一致：
--   資治通鑑卷217/222（755/763 两端与 V019/V021 共用同一切片代码路径）、新唐書卷201、舊唐書卷190下、
--   ws-poems/聞官軍收河南河北.txt（诗页快照）。
--
-- 做：4 BACKGROUND content/claim/background + 8 组逐字引用 +
--   8 行 background_line（scene→1,2｜person→3,4｜world→5,6｜city→7,8，绑 text-work-t300-217-ws）+
--   系年 claim-wgjs-time-763（下限锚+春字内证合推 → LIKELY）+ written_during 安史之乱挂接。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布、不写 review_log。
--
-- 诚实边界：
--   * 《全唐詩》卷227 快照内此诗只有转引用桩 {{:聞官軍收河南河北}} 无正文——引诗本文一律走诗页快照；
--   * 旧注「梓州说」核不到注本，SCENE 层零注家引用并向读者声明；
--   * 系年是下限锚（763 正月史朝义死）+「青春」春字内证合推，不是注本/年谱原文，故 LIKELY；
--   * 「平而不安」并置是读法，正文标明；「召补不至」单源，只并置不引申；
--   * 页面题目异文「一作收兩河」只登记（corpus/tang300-variants.md），不进正文不裁决。
--
-- 执行前只读检查：
--   SELECT version_no FROM poetry_schema_version ORDER BY version_no;   -- 含 21，不含 22
--   SELECT id FROM poetry_content WHERE id LIKE 'bg-wgjs-%';            -- 空
--   SELECT id FROM poetry_text_version WHERE id='text-work-t300-217-ws';  -- 恰 1 行（V018 已执行）
-- 执行后核对：
--   SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'bg-wgjs-%';      -- 4
--   SELECT COUNT(*) FROM poetry_background_line bl JOIN poetry_text_version tv ON bl.version_id=tv.id
--    WHERE tv.work_id='work-t300-217';                                  -- 8
--   SELECT certainty FROM poetry_claim WHERE id='claim-bg-wgjs-person'; -- KNOWN
-- 回滚: recovery/V022_rollback.sql（按 id 全枚举删除；不动 V018 的任何行）
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
    brows = [{'id': k, 'work_id': 'work-t300-217',
              'layer': {'bg-wgjs-scene': 'SCENE', 'bg-wgjs-city': 'CITY',
                        'bg-wgjs-world': 'WORLD', 'bg-wgjs-person': 'PERSON'}[k],
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
        f"SELECT {sql_s(k)} AS background_id, 'text-work-t300-217-ws' AS version_id, {n} AS line_seq FROM DUAL"
        for k, seqs in BG_LINES.items() for n in seqs))
    L.append(') AS t\nWHERE NOT EXISTS (SELECT 1 FROM poetry_background_line x '
             'WHERE x.background_id = t.background_id AND x.version_id = t.version_id '
             'AND x.line_seq = t.line_seq);')

    A('\n-- ---------- 6. 系年（下限锚+春字内证合推 → LIKELY；locator 写明非注本系年） ----------')
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            [{'id': 'claim-wgjs-time-763', 'subject_id': 'work-t300-217', 'property_key': 'time.span',
              'value_text': '763..763 (EXACT) 广德元年春说：题曰收河南河北，河北悉平（史朝义死）在763正月（通鉴卷222）'
                            '为下限；「青春作伴」为春之内证——合推广德元年春，非注本/年谱原文',
              'claim_kind': 'FACT', 'certainty': 'LIKELY'}], 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': 'work-t300-217', 'property_key': 'time.span', 'claim_id': 'claim-wgjs-time-763'}],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))

    A('\n-- ---------- 7. written_during 安史之乱（形状同 V017/V020/V021） ----------')
    A(guard('poetry_claim', ['id', 'subject_id', 'property_key', 'value_text', 'claim_kind', 'certainty'],
            [{'id': 'claim-wgjs-in-anshi', 'subject_id': 'work-t300-217', 'property_key': 'event.name',
              'value_text': '安史之亂（755–763）。係年763在亂期內；「收河南河北」即亂事收場本身',
              'claim_kind': 'FACT', 'certainty': 'LIKELY'}], 'x.id = t.id'))
    A(guard('poetry_claim_selection', ['subject_id', 'property_key', 'claim_id'],
            [{'subject_id': 'work-t300-217', 'property_key': 'event.name', 'claim_id': 'claim-wgjs-in-anshi'}],
            'x.subject_id = t.subject_id AND x.property_key = t.property_key'))
    A(guard('poetry_relation', ['id', 'subject_id', 'predicate', 'object_id', 'claim_id'],
            [{'id': 'rel-work-t300-217-written-during-anshi', 'subject_id': 'work-t300-217',
              'predicate': 'written_during', 'object_id': 'event-anshi-rebellion',
              'claim_id': 'claim-wgjs-in-anshi'}],
            'x.id = t.id OR (x.subject_id = t.subject_id AND x.predicate = t.predicate AND x.object_id = t.object_id)'))

    A("""
-- ---------- 8. 版本账本 ----------
INSERT INTO poetry_schema_version (version_no, description)
SELECT 22, 'wen-guanjun-shou-henan-hebei background layers (inserts-only): tongjian 763 ending + two histories on the Shu sojourn; vol227 is a transclusion stub for this poem so poem-text cites the ws page snapshot; old commentary dating unverified and not used'
FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 22);
COMMIT;""")
    return '\n'.join(L) + '\n'


def build_rollback():
    L = ['-- V022 精确回滚：只删 V022 插入的行（id 全枚举）。work-t300-217 本体是 V018 的行，绝不删。',
         'START TRANSACTION;']
    cids = list(CLAIMS) + ['claim-wgjs-time-763', 'claim-wgjs-in-anshi']

    def dels(table, col, vals, chunk=40):
        for i in range(0, len(vals), chunk):
            L.append(f'DELETE FROM {table} WHERE {col} IN ('
                     + ', '.join(sql_s(v) for v in vals[i:i + chunk]) + ');')
    dels('poetry_claim_selection', 'claim_id', cids)
    dels('poetry_citation', 'claim_id', cids)
    dels('poetry_relation', 'id', ['rel-work-t300-217-written-during-anshi'])
    dels('poetry_background_line', 'background_id', list(BG))
    dels('poetry_background', 'id', list(BG))
    dels('poetry_claim', 'id', cids)
    dels('poetry_content', 'id', list(BG))
    L.append('DELETE FROM poetry_schema_version WHERE version_no = 22;')
    L.append('COMMIT;')
    return '\n'.join(L) + '\n'


def audit(sql):
    bad = []
    if re.search(r"'(?:[^'\\]|'')*\\", sql):
        bad.append('字面量里有反斜杠')
    flat = sql.replace("''", "'")
    for q in (TJ_TOKU, TJ_TOKU_SACK, TJ_GRANT, WS_LINE1, WS_NOTE, XTS_JN, JTS_GW,
              TJ755Y, TJ755, TJ763Y, TJ763):
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
        print(f'dry-run: sql {len(sql)} B, rollback {len(rb)} B — 引文 11 条逐字过审')
        return
    pathlib.Path(args.out_sql).write_text(sql, encoding='utf-8')
    pathlib.Path(args.out_rollback).write_text(rb, encoding='utf-8')
    print(f'wrote {args.out_sql} ({len(sql.encode())} B)')
    print(f'wrote {args.out_rollback} ({len(rb.encode())} B)')


if __name__ == '__main__':
    main()
