#!/usr/bin/env python3
"""V017：把《春望》挂到安史之乱这条线上（阶段 D 第 1 首的骨架挂接）。
从 tang-work-links.json 生成迁移 + 回滚。
用法（在 chronology 目录，不要用 python3 -I，需要 import emit_v014）:
  python3 emit_v017.py \
    --out-sql ../../../../../testserverV/vvv-poetry/src/main/resources/db/poetry/V017__chunwang_anshi_link.sql \
    --out-rollback ../../../../../testserverV/vvv-poetry/src/main/resources/db/poetry/recovery/V017_rollback.sql
约定与 emit_v014/v015/v016 相同：只写文件、不执行；全部 INSERT…WHERE NOT EXISTS 可重放；
UPDATE 一律带值条件（只有仍是前一迁移写入的那个值时才改），回滚同样按值还原。
"""
import argparse
import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent


def sql_str(s):
    """字符串字面量。反斜杠按 MySQL 默认 sql_mode（\\ 是转义符）双写；
    若连接开了 NO_BACKSLASH_ESCAPES，\\ 会被当成字面量、双写就变成两个反斜杠污染数据。
    两种模式不可能同时满足，所以取默认模式，并由 audit() 断言本迁移的字面量里一个反斜杠都没有——
    把「静默污染」变成生成期失败。单引号用 '' （ANSI 写法，两种模式都对）。"""
    if s is None:
        return "NULL"
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def union_select(rows):
    return "\nUNION ALL\n".join(rows)


def joined(doc, keys, sep="……"):
    return sep.join(doc["quotes"][k]["quote"] for k in keys)


def new_claim_row(c):
    return (
        f"SELECT {sql_str(c['id'])} AS id, {sql_str(c['subject_id'])} AS subject_id, "
        f"{sql_str(c['property_key'])} AS property_key, {sql_str(c['value_text'])} AS value_text, "
        f"{sql_str(c['claim_kind'])} AS claim_kind, {sql_str(c['certainty'])} AS certainty FROM DUAL"
    )


def build_sql(doc):
    L = []
    L.append(
        f"""-- V017：把《春望》挂到安史之乱这条线上（阶段 D 第 1 首）。MySQL 5.6.40 兼容。
-- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。前置：V011、V013、V015、V016 已执行。
--
-- 数据源（可复现）：
--   content-agent/pipeline/data/chronology/tang-work-links.json
--   （每条引文由脚本对维基文库 wikitext 快照做唯一锚点切片并逐字复核，见 validate.py 的 work-links 段）
--   生成：python3 emit_v017.py
--
-- 做四件事：
--   1) {len(doc['claims'])} 条挂接断言 + 关系：work-chun-wang --written_during--> event-anshi-rebellion，
--      依据注本系年与本诗内证两条原文；标 LIKELY（系年本身仍是两说并存）。
--   2) {len(doc['updates']['citation_swaps'])} 处占位出处换成真实定位与逐字原文
--      （V004 的「待人工核对：……」——audit C5_citation_locator_placeholder_on_published_claim 挡的就是这种）：
--      《春望》系年 757、杜甫 757 年经历、叛军陷长安 756 ——第三处正是 V015 明说「本轮没有句子」的年份，
--      占位行问的「通鉴纪事年月」和通鉴卷218 给的是同一件事，所以是替换而不是并排新增。
--   3) {len(doc['citation_inserts'])} 条新增引用（断言上本来没有该来源的行）。
--   4) claim-chang-an-capture-time 的 756 年有两个独立来源一致，LIKELY 升 KNOWN。
--
-- 主题线不动：V004 第 7 节已把 work-chun-wang 作为 ordinal 4 的成员挂在 theme-anshi-rebellion 上，
--   本迁移补的是那条线里没有出处的部分——「这首诗写在乱中」这件事本身要有出处。
-- 不做：不核验来源（走 verifySource）、不改 status、不发布任何东西、不动 V004/V011/V013 的迁移文件；
--   不裁决《春望》系年——鹤注支持 757，758 一说至今无来源，两条 claim 仍是 DISPUTED，两说并存。
--   不写 poetry_review_log：那张表 V003 起就规定 append-only，只可追加不可回滚，
--   评审结论走 Studio；本迁移不替人下评审结论。
--
-- 执行前: SELECT version_no FROM poetry_schema_version ORDER BY version_no;  -- 含 16，不含 17
--         SELECT claim_id, source_id, locator FROM poetry_citation
--          WHERE claim_id IN ('claim-chun-wang-time-757','claim-exp-757-time','claim-chang-an-capture-time');
--                                                                        -- {len(doc['updates']['citation_swaps'])} 条 locator 都以「待」开头
--         SHOW VARIABLES LIKE 'character_set_client';                     -- 须为 utf8mb4（与 V001–V016 同规，
--         　　本文件族一律不写 SET NAMES，字符集由连接保证；latin1 连接跑本文件 = 中文全部乱码）
-- 执行后: SELECT locator FROM poetry_citation WHERE claim_id IN
--           ('claim-chun-wang-time-757','claim-exp-757-time','claim-chang-an-capture-time');
--                                                                        -- 都不再以「待」开头
--         SELECT COUNT(*) FROM poetry_citation WHERE locator LIKE '待%';           -- 比执行前少 {len(doc['updates']['citation_swaps'])}
--         SELECT certainty FROM poetry_claim WHERE id='claim-chang-an-capture-time';  -- KNOWN
--         SELECT predicate, object_id FROM poetry_relation WHERE subject_id='work-chun-wang';  -- written_during
-- 回滚: recovery/V017_rollback.sql"""
    )
    L.append("START TRANSACTION;")
    L.append("")

    # ---------- 1. sources ----------
    L.append("-- ---------- 1. 来源登记（一律 PENDING：登记不等于核验） ----------")
    for s in doc["new_sources"]:
        L.append(
            "INSERT INTO poetry_source (id, title, author, edition, url, rights_note, verification_status, source_kind, reliability)\n"
            f"SELECT {sql_str(s['id'])}, {sql_str(s['title'])}, {sql_str(s['author'])}, {sql_str(s['edition'])}, "
            f"{sql_str(s['url'])},\n       {sql_str(s['rights_note'])}, {sql_str(s['verification_status'])}, "
            f"{sql_str(s['source_kind'])}, {sql_str(s['reliability'])}\n"
            f"FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_source WHERE id = {sql_str(s['id'])});"
        )
    u = doc["updates"]["source_title"]
    L.append("")
    L.append(
        f"-- {u['why']}。\n"
        f"UPDATE poetry_source SET title = {sql_str(u['new_title'])}\n"
        f" WHERE id = {sql_str(u['id'])} AND title = {sql_str(u['old_title'])} AND verification_status = 'PENDING';"
    )
    L.append("")

    # ---------- 2. citation swaps ----------
    L.append("-- ---------- 2. 占位出处 → 真实定位与逐字原文 ----------")
    for s in doc["updates"]["citation_swaps"]:
        keys = s.get("quote_keys") or [s["quote_key"]]
        L.append(
            f"-- {s['claim_id']}：{s['why']}\n"
            "UPDATE poetry_citation\n"
            f"   SET source_id = {sql_str(s['new_source'])},\n"
            f"       locator = {sql_str(s['new_locator'])},\n"
            f"       evidence_excerpt = {sql_str(joined(doc, keys))}\n"
            f" WHERE claim_id = {sql_str(s['claim_id'])} AND source_id = {sql_str(s['placeholder_source'])}\n"
            f"   AND locator = {sql_str(s['old_locator'])};"
        )
    L.append("")

    # ---------- 3. citation inserts ----------
    L.append("-- ---------- 3. 新增引用 ----------")
    for ins in doc["citation_inserts"]:
        L.append(
            f"-- {ins['why']}\n"
            "INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)\n"
            f"SELECT {sql_str(ins['claim_id'])}, {sql_str(ins['source_id'])}, {sql_str(ins['locator'])}, "
            f"{sql_str(joined(doc, ins['quote_keys']))}\n"
            "FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_citation WHERE claim_id = "
            f"{sql_str(ins['claim_id'])} AND source_id = {sql_str(ins['source_id'])});"
        )
    L.append("")

    # ---------- 4. certainty upgrade ----------
    L.append("-- ---------- 4. 两个独立来源一致才升级 ----------")
    for up in doc["updates"]["certainty_upgrades"]:
        L.append(
            f"-- {up['claim_id']}：{up['why']}\n"
            f"UPDATE poetry_claim SET certainty = {sql_str(up['to'])}\n"
            f" WHERE id = {sql_str(up['claim_id'])} AND certainty = {sql_str(up['from'])} AND status <> 'PUBLISHED';"
        )
    L.append("")

    # ---------- 5. 挂接断言 + selection + citations + relation ----------
    L.append("-- ---------- 5. 诗 × 事件：挂接断言、其出处、以及关系行 ----------")
    L.append(
        "-- audit C4_claim_subject_mismatch_on_relation 要求关系的 claim 主语与关系主语一致，\n"
        "-- 所以这条断言的主语是 work-chun-wang（「这首诗写于乱中」是诗的属性），关系从它指向事件。"
    )
    claims = doc["claims"]
    L.append("INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)")
    L.append("SELECT * FROM (")
    L.append(union_select(new_claim_row(c) for c in claims))
    L.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim c WHERE c.id = t.id);")
    L.append("")
    sel = [
        f"SELECT {sql_str(c['subject_id'])} AS subject_id, {sql_str(c['property_key'])} AS property_key, "
        f"{sql_str(c['id'])} AS claim_id FROM DUAL"
        for c in claims
        if c.get("selection")
    ]
    L.append("INSERT INTO poetry_claim_selection (subject_id, property_key, claim_id)")
    L.append("SELECT * FROM (")
    L.append(union_select(sel))
    L.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim_selection s "
        "WHERE s.subject_id = t.subject_id AND s.property_key = t.property_key);"
    )
    L.append("")
    ci = []
    for c in claims:
        for cit in c.get("citations", []):
            ci.append(
                f"SELECT {sql_str(c['id'])} AS claim_id, {sql_str(cit['source_id'])} AS source_id, "
                f"{sql_str(cit['locator'])} AS locator, "
                f"{sql_str(joined(doc, cit['quote_keys']))} AS evidence_excerpt FROM DUAL"
            )
    L.append("INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)")
    L.append("SELECT * FROM (")
    L.append(union_select(ci))
    L.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_citation c "
        "WHERE c.claim_id = t.claim_id AND c.source_id = t.source_id);"
    )
    L.append("")
    rel = []
    for c in claims:
        r = c.get("relation")
        if not r:
            continue
        rel.append(
            f"SELECT {sql_str(r['id'])} AS id, {sql_str(c['subject_id'])} AS subject_id, "
            f"{sql_str(r['predicate'])} AS predicate, {sql_str(r['object_id'])} AS object_id, "
            f"{sql_str(c['id'])} AS claim_id FROM DUAL"
        )
    L.append("INSERT INTO poetry_relation (id, subject_id, predicate, object_id, claim_id)")
    L.append("SELECT * FROM (")
    L.append(union_select(rel))
    # 表上除了 PK(id) 还有 UNIQUE(subject_id,predicate,object_id)：只按 id 守不住后者。
    # 若同三元组已存在但 id 不同，按 id 的 NOT EXISTS 会放行、INSERT 就在唯一键上抛错。
    L.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_relation r "
             "WHERE r.id = t.id OR (r.subject_id = t.subject_id "
             "AND r.predicate = t.predicate AND r.object_id = t.object_id));")
    L.append("")

    # ---------- 6. 未裁决的分歧 ----------
    L.append("-- ---------- 6. 没有裁决的：数据库里没有表能表达「两说未裁决」，写在数据文件与文档里 ----------")
    g = doc["gap"]
    L.append("-- " + g["id"] + "（" + g["status"] + "）")
    for f in g["facts"]:
        L.append("--   · " + f)
    L.append("--   待决：" + g["open_question"])
    L.append("")

    # 账本描述必须在 VARCHAR(200) 内：默认 sql_mode 下超长是「warning + 静默截断」，
    # 截掉的正是句尾的语义（(KNOWN)），而迁移照样"成功"——这种失败没有信号，所以在生成期就拦掉。
    desc = (
        "Chun Wang linked to the An Lushan rebellion with a sourced relation; 3 V004 placeholder "
        "citations replaced by verbatim notes/annals text; Chang-an fall 756 re-verified (KNOWN)"
    )
    assert len(desc) <= 200, f"schema_version 描述超长 {len(desc)}"
    L.append(
        "INSERT INTO poetry_schema_version (version_no, description)\n"
        f"SELECT 17, {sql_str(desc)}\n"
        "FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 17);"
    )
    L.append("COMMIT;")
    L.append("")
    return "\n".join(L) + "\n"


def build_rollback(doc):
    L = []
    L.append(
        """-- V017 回滚：撤销本迁移写入的挂接断言/出处/关系，并把三处占位出处与一处 certainty 还原。
-- 不删除 version_no=17 账本行；不碰 poetry_review_log（本迁移没写它，那张表也只可追加）。
-- V004/V011/V013/V015/V016 的行一律不删：claim-chun-wang-time-757、claim-exp-757-time、
-- claim-chang-an-capture-time 及其引用属 V004/V011，回滚只把值条件命中的一处还原成迁移前的那个值。
-- 来源行仅在仍无引用且仍为 PENDING 时删除。"""
    )
    claim_ids = [c["id"] for c in doc["claims"]]
    rel_ids = [c["relation"]["id"] for c in doc["claims"] if c.get("relation")]
    new_srcs = [s["id"] for s in doc["new_sources"]]

    L.append("START TRANSACTION;")
    L.append("")
    L.append("-- 挂接：关系、引用、选择、断言（都是本迁移新增的行）")
    L.append("DELETE FROM poetry_relation WHERE id IN (" + ", ".join(sql_str(i) for i in rel_ids) + ");")
    L.append("DELETE FROM poetry_citation WHERE claim_id IN (" + ", ".join(sql_str(i) for i in claim_ids) + ");")
    L.append(
        "DELETE FROM poetry_claim_selection WHERE claim_id IN ("
        + ", ".join(sql_str(i) for i in claim_ids)
        + ");"
    )
    L.append("DELETE FROM poetry_claim WHERE id IN (" + ", ".join(sql_str(i) for i in claim_ids) + ");")
    L.append("")
    L.append("-- 本迁移新增的引用（按 (claim_id, source_id) 主键精确删）")
    pairs = ", ".join(
        f"('{ins['claim_id']}', {sql_str(ins['source_id'])})" for ins in doc["citation_inserts"]
    )
    L.append(f"DELETE FROM poetry_citation WHERE (claim_id, source_id) IN ({pairs});")
    L.append("")
    L.append("-- certainty 还原（只在本迁移升级过的值上生效）")
    for up in doc["updates"]["certainty_upgrades"]:
        L.append(
            f"UPDATE poetry_claim SET certainty = {sql_str(up['from'])}\n"
            f" WHERE id = {sql_str(up['claim_id'])} AND certainty = {sql_str(up['to'])} AND status <> 'PUBLISHED';"
        )
    L.append("")
    L.append("-- 占位出处还原：只有仍指向本迁移写入的来源与定位时才还原（中间被人工改过就不动）")
    for s in doc["updates"]["citation_swaps"]:
        L.append(
            "UPDATE poetry_citation\n"
            f"   SET source_id = {sql_str(s['placeholder_source'])},\n"
            f"       locator = {sql_str(s['old_locator'])},\n"
            "       evidence_excerpt = NULL\n"
            f" WHERE claim_id = {sql_str(s['claim_id'])} AND source_id = {sql_str(s['new_source'])}\n"
            f"   AND locator = {sql_str(s['new_locator'])};"
        )
    L.append("")
    L.append("-- 通鉴来源标题还原")
    u = doc["updates"]["source_title"]
    L.append(
        f"UPDATE poetry_source SET title = {sql_str(u['old_title'])}\n"
        f" WHERE id = {sql_str(u['id'])} AND title = {sql_str(u['new_title'])} AND verification_status = 'PENDING';"
    )
    L.append("")
    L.append(
        "DELETE FROM poetry_source WHERE id IN ("
        + ", ".join(sql_str(i) for i in new_srcs)
        + ")\n"
        "  AND verification_status = 'PENDING'\n"
        "  AND NOT EXISTS (SELECT 1 FROM poetry_citation c WHERE c.source_id = poetry_source.id);"
    )
    L.append("COMMIT;")
    L.append("")
    return "\n".join(L) + "\n"


def audit(doc, sql):
    """生成后自查：键唯一、id/locator/账本描述长度、可重放（无裸 INSERT…VALUES）。

    这一轮补上的三类盲区（独立复核发现，V017 首版漏掉）：
      1) poetry_schema_version.description VARCHAR(200)——超长在默认 sql_mode 下是
         「warning + 静默截断」，截掉的正是句尾语义，而迁移照样"成功"，没有信号；
      2) claim / selection / relation / source 自身的键去重（原先只查 citation）；
      3) relation 除 id 外还有 UNIQUE(subject,predicate,object)——按 id 守不住它。
    """
    problems = []
    # ---------- citation 主键 (claim_id, source_id) ----------
    keys = []
    for s in doc["updates"]["citation_swaps"]:
        keys.append((s["claim_id"], s["new_source"]))
    for ins in doc["citation_inserts"]:
        keys.append((ins["claim_id"], ins["source_id"]))
    for c in doc["claims"]:
        for cit in c.get("citations", []):
            keys.append((c["id"], cit["source_id"]))
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        problems.append(f"citation PK 重复: {sorted(dup)}")
    # 换源后不许与同一 claim 上已有的另一来源撞（占位来源被换掉，不会残留）
    for s in doc["updates"]["citation_swaps"]:
        if (s["claim_id"], s["placeholder_source"]) in keys:
            problems.append(f"换源后仍保留占位来源行: {s['claim_id']}")

    # ---------- claim / selection / relation / source 的键 ----------
    cids = [c["id"] for c in doc["claims"]]
    if len(set(cids)) != len(cids):
        problems.append(f"claim id 在本迁移内重复: {sorted(c for c in cids if cids.count(c) > 1)}")
    sels = [(c["subject_id"], c["property_key"]) for c in doc["claims"] if c.get("selection")]
    if len(set(sels)) != len(sels):
        problems.append(f"selection PK 在本迁移内重复: {sorted(s for s in sels if sels.count(s) > 1)}")
    rels = [(c["relation"]["id"], c["subject_id"], c["relation"]["predicate"], c["relation"]["object_id"])
            for c in doc["claims"] if c.get("relation")]
    for label, idx in (("relation id", 0), ("relation 三元组", slice(1, 4))):
        vals = [tuple(r[idx]) if not isinstance(idx, slice) else r[idx] for r in rels]
        if len(set(vals)) != len(vals):
            problems.append(f"{label} 在本迁移内重复: {sorted(v for v in vals if vals.count(v) > 1)}")
    sids = [s["id"] for s in doc["new_sources"]]
    if len(set(sids)) != len(sids):
        problems.append(f"source id 在本迁移内重复: {sorted(s for s in sids if sids.count(s) > 1)}")
    # 本迁移新登记的来源不许撞上既有迁移已登记的来源（撞了就是重复定义，而非可重放的幂等）
    for sid in sids:
        if f"INSERT INTO poetry_source" in sql and sql.count(f"SELECT {sql_str(sid)},") > 1:
            problems.append(f"同一来源在本迁移内登记两次: {sid}")

    # ---------- 长度上限（VARCHAR 按字符计） ----------
    for c in doc["claims"]:
        if len(c["id"]) > 64:
            problems.append(f"claim id 超长 {len(c['id'])}: {c['id']}")
        if len(c["subject_id"]) > 64 or len(c["property_key"]) > 64:
            problems.append(f"subject/property 超长: {c['id']}")
        if c.get("value_text") and len(c["value_text"]) > 500:
            problems.append(f"value_text 超长 {len(c['value_text'])}: {c['id']}")
        for cit in c.get("citations", []):
            if len(cit["locator"]) > 300:
                problems.append(f"locator 超长 {len(cit['locator'])}: {c['id']}")
    for ins in doc["citation_inserts"]:
        if len(ins["locator"]) > 300:
            problems.append(f"locator 超长 {len(ins['locator'])}: {ins['claim_id']}")
    for s in doc["updates"]["citation_swaps"]:
        if len(s["new_locator"]) > 300:
            problems.append(f"locator 超长 {len(s['new_locator'])}: {s['claim_id']}")
    for c in doc["claims"]:
        r = c.get("relation")
        if r:
            if len(r["id"]) > 64:
                problems.append(f"relation id 超长 {len(r['id'])}: {r['id']}")
            if len(r["predicate"]) > 40:
                problems.append(f"relation predicate 超长 {len(r['predicate'])}/40: {r['id']}")
            if len(r["object_id"]) > 64:
                problems.append(f"relation object_id 超长 {len(r['object_id'])}: {r['id']}")
    for c in doc["claims"]:
        for v, cap in ((c.get("claim_kind"), 24), (c.get("certainty"), 24)):
            if v and len(v) > cap:
                problems.append(f"claim_kind/certainty 超长 {len(v)}/{cap}: {c['id']}")
    for s in doc["new_sources"]:
        # 上限取自 V001__foundation.sql 的实测 DDL，不是猜的：
        # id VARCHAR(64)、title VARCHAR(300)、author VARCHAR(200)、
        # edition VARCHAR(300)、url VARCHAR(1000)、rights_note TEXT(65535 字节)
        for f, cap in (("id", 64), ("title", 300), ("author", 200),
                       ("edition", 300), ("url", 1000)):
            if s.get(f) and len(s[f]) > cap:
                problems.append(f"source.{f} 超长 {len(s[f])}/{cap}: {s['id']}")
        if s.get("rights_note") and len(s["rights_note"].encode("utf-8")) > 65535:
            problems.append(f"source.rights_note 超 TEXT 字节上限: {s['id']}")
    # 账本行：超长会静默截断（见 docstring），必须生成期拦住
    m = re.search(r"INSERT INTO poetry_schema_version \(version_no, description\)\nSELECT \d+, (.*?)\nFROM DUAL",
                  sql, re.S)
    if not m:
        problems.append("账本 INSERT 结构不符合预期，长度检查跳过")
    else:
        n = len(m.group(1)) - 2  # 去掉两侧引号
        if n > 200:
            problems.append(f"schema_version 描述超长 {n}/200（默认 sql_mode 下静默截断）")

    # ---------- 可重放：任何表都不许出现裸 INSERT…VALUES ----------
    for tbl in ("poetry_source", "poetry_claim", "poetry_claim_selection",
                "poetry_citation", "poetry_relation", "poetry_schema_version"):
        if re.search(rf"INSERT INTO {tbl}\b[^;]*?\bVALUES\b", sql, re.S):
            problems.append(f"{tbl} 出现裸 INSERT…VALUES，不可重放")
    # ---------- 反斜杠：sql_str 的转义只在默认 sql_mode 下正确 ----------
    # 开 NO_BACKSLASH_ESCAPES 的连接会把 \\ 当两个字面反斜杠、污染数据。
    # 当前数据一个反斜杠都没有，所以断言成立；将来 JSON 里出现反斜杠，这里立刻失败，
    # 而不是等到某个运维用某种 sql_mode 执行时静默写坏。
    lits = re.findall(r"'((?:[^'\\]|'')*)'", sql)
    bs = [l for l in lits if "\\" in l]
    if bs:
        problems.append(f"字面量里出现反斜杠 {len(bs)} 处——sql_mode 相关，需人工确认（例：{bs[0][:40]}）")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-sql", required=True)
    ap.add_argument("--out-rollback", required=True)
    args = ap.parse_args()
    doc = json.loads((HERE / "tang-work-links.json").read_text(encoding="utf-8"))
    sql = build_sql(doc)
    rb = build_rollback(doc)
    problems = audit(doc, sql)
    out_sql = pathlib.Path(args.out_sql)
    out_rb = pathlib.Path(args.out_rollback)
    out_sql.write_text(sql, encoding="utf-8")
    out_rb.write_text(rb, encoding="utf-8")
    print(f"wrote {out_sql} bytes {len(sql.encode('utf-8'))}")
    print(f"wrote {out_rb} bytes {len(rb.encode('utf-8'))}")
    n_cit = sql.count("INSERT INTO poetry_citation")
    print(f"citation inserts in file: {n_cit}; citation updates: {sql.count('UPDATE poetry_citation')}")
    if problems:
        for p in problems:
            print("  -", p)
        raise SystemExit(1)
    print("audit OK: keys unique, ids <=64, locators <=300, replayable")


if __name__ == "__main__":
    main()
