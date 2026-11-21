#!/usr/bin/env python3
"""V016：唐朝诗人小传（阶段 B 第一批 7 位）。从 tang-persons.json 生成迁移 + 回滚。
用法（在 chronology 目录，不要用 python3 -I，需要 import emit_v014）:
  python3 emit_v016.py \
    --out-sql ../../../../../testserverV/vvv-poetry/src/main/resources/db/poetry/V016__tang_person_biographies.sql \
    --out-rollback ../../../../../testserverV/vvv-poetry/src/main/resources/db/poetry/recovery/V016_rollback.sql
约定与 emit_v014/v015 相同：只写文件、不执行；全部 INSERT…WHERE NOT EXISTS 可重放；
回滚只删本迁移新增的行（person-du-fu 的 content/poetry_person 行属 V002，只补出处与新增属性断言）。
"""
import argparse
import json
import pathlib

HERE = pathlib.Path(__file__).parent

SOURCE_ROWS = [
    (
        "source-jiutangshu-wenyuan",
        "《舊唐書》列傳第一百四十 文苑（卷190上、190中、190下）",
        "劉昫等",
        "维基文库录入本，页面标注未校对；{{YL|}}、{{SKchar|}}、-{…}- 等录入标记在引文中原样保留",
        "https://zh.wikisource.org/wiki/舊唐書/卷190下",
        "公有领域古籍。reliability 是编者对正史列传的分级判断，不代表本条已走 verifySource。",
        "OFFICIAL_HISTORY",
        "HIGH",
    ),
    (
        "source-xintangshu-wenyi",
        "《新唐書》列傳第一百二十六至一百二十八 文藝（卷201、202、203）",
        "歐陽修、宋祁等",
        "维基文库录入本；引文逐字摘自 wikitext，-{…}- 为录入本的繁简转换标记",
        "https://zh.wikisource.org/wiki/新唐書/卷202",
        "公有领域古籍。与旧唐书并列使用：一致的记 KNOWN，不同的两说并列。reliability 不代表已核验。",
        "OFFICIAL_HISTORY",
        "HIGH",
    ),
]

SRC_LABEL = {
    "jts190s": "舊唐書文苑上", "jts190m": "舊唐書文苑中", "jts190x": "舊唐書文苑下",
    "xts201": "新唐書文藝上", "xts202": "新唐書文藝中", "xts203": "新唐書文藝下",
}

# V002 给 person-du-fu 写的占位 summary；本迁移只在它仍是这个值时改写，回滚也只在
# 它仍是本迁移写的值时才还原——中间若有人手工改过或已发布，两者都跳过。
V002_DUFU_SUMMARY = "待核查：生平、年谱与相关史料。"


def src_for(src):
    if src.startswith("jts"):
        return "source-jiutangshu-wenyuan"
    if src.startswith("xts"):
        return "source-xintangshu-wenyi"
    raise KeyError(src)


def sql_str(s):
    if s is None:
        return "NULL"
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def union_select(rows):
    return "\nUNION ALL\n".join(rows)


def person_id(per):
    return per.get("id") or f"person-tang-{per['slug']}"


def person_slug(per):
    pid = person_id(per)
    if pid.startswith("person-tang-"):
        return pid[len("person-"):]  # tang-li-bai
    return pid[len("person-"):]      # du-fu（V002 已占用的 slug，不动）


def claim_id(pid, key):
    cid = f"claim-{pid}-{key}"
    if len(cid) > 64:
        raise ValueError(f"claim id 超长: {cid}")
    return cid


def build_sql(doc):
    persons = doc["persons"]
    pids = [person_id(p) for p in persons]
    new_pids = [p for p in persons if not p.get("id")]
    new_pids = [person_id(p) for p in new_pids]
    facts = [(p, pid, f) for p, pid in zip(persons, pids) for f in p["facts"]]
    exps = [(p, pid, ex) for p, pid in zip(persons, pids) for ex in p.get("experiences", [])]

    L = []
    L.append(
        f"""-- V016：唐朝诗人小传（阶段 B 第一批 7 位）。MySQL 5.6.40 兼容。
-- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。前置：V014、V015 已执行。
--
-- 数据源（可复现）：
--   content-agent/pipeline/data/chronology/tang-persons.json
--   （每条引文已对维基文库 wikitext 快照逐字核验，见 validate.py 的 persons 段）
--   生成：python3 emit_v016.py
--
-- 写入：{len(persons)} 个 PERSON 实体（新增 {len(new_pids)} 个；杜甫沿用 V002 的 person-du-fu 行，不删不重建）；
--       生平属性断言 {len(facts)} 条（certainty 记核验结果：两史一致且年份由已核年号表钉到具体年=KNOWN，
--       两史不同或史文只给含糊年代=LIKELY，值里写明「兩說並列」或「單源」）；
--       每条断言引用旧唐书文苑/新唐书文艺的逐字原文；
--       经历 EXPERIENCE {len(exps)} 条（人 × 阶段 A 已录事件，依据是本人本传的逐字原文）。
-- 不做：不核验来源、不改 status、不加没有出处的句子；
--       不写生卒年——本批 7 人无一人两史给出一致的卒年，poetry_content 的年份一律 UNKNOWN/留空；
--       person-du-fu 在 V004 里的 712..770 APPROXIMATE 草稿值本迁移不动（它没有出处支持，也没有被证伪）。
--
-- 执行前: SELECT version_no FROM poetry_schema_version ORDER BY version_no;  -- 含 15，不含 16
-- 执行后: SELECT COUNT(*) FROM poetry_content WHERE entity_type='PERSON' AND (id LIKE 'person-tang-%' OR id='person-du-fu');  -- {len(pids) + 23}
--         SELECT COUNT(*) FROM poetry_claim WHERE subject_id IN ({', '.join(sql_str(p) for p in pids)});  -- {len(facts) + len(exps)}
-- 回滚: recovery/V016_rollback.sql"""
    )
    L.append("START TRANSACTION;")
    L.append("")

    L.append("-- ---------- sources ----------")
    for sid, title, author, edition, url, rights, kind, rel in SOURCE_ROWS:
        L.append(
            f"INSERT INTO poetry_source (id, title, author, edition, url, rights_note, verification_status, source_kind, reliability)\n"
            f"SELECT {sql_str(sid)}, {sql_str(title)}, {sql_str(author)}, {sql_str(edition)}, {sql_str(url)},\n"
            f"       {sql_str(rights)}, 'PENDING', {sql_str(kind)}, {sql_str(rel)}\n"
            f"FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_source WHERE id = {sql_str(sid)});"
        )
    L.append("")

    L.append("-- ---------- persons (PERSON) ----------")
    crows = []
    for per, pid in zip(persons, pids):
        crows.append(
            "SELECT "
            f"{sql_str(pid)} AS id, 'PERSON' AS entity_type, "
            f"{sql_str(person_slug(per))} AS slug, {sql_str(per['name'])} AS title, "
            f"{sql_str(per['summary'])} AS summary, "
            "CAST(NULL AS SIGNED) AS start_year, CAST(NULL AS SIGNED) AS end_year, 'UNKNOWN' AS time_precision"
            " FROM DUAL"
        )
    L.append("INSERT INTO poetry_content (id, entity_type, slug, title, summary, start_year, end_year, time_precision)")
    L.append("SELECT * FROM (")
    L.append(union_select(crows))
    L.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_content c WHERE c.id = t.id);")
    L.append("")
    # person-du-fu 的 summary 是 V002 的「待核查」占位；本迁移已有出处，替换为有出处的说法
    # （值条件保护：只有该行仍是 V002 的占位文字时才改，回滚同理还原）
    for per, pid in zip(persons, pids):
        if per.get("id"):
            L.append(
                f"UPDATE poetry_content SET summary = {sql_str(per['summary'])}\n"
                f" WHERE id = {sql_str(pid)} AND summary = {sql_str(V002_DUFU_SUMMARY)} AND status <> 'PUBLISHED';"
            )
    L.append("")
    prows = []
    for per, pid in zip(persons, pids):
        cn = per.get("courtesy_name")
        prows.append(
            f"SELECT {sql_str(pid)} AS id, 'dynasty-tang' AS dynasty_id, "
            f"{sql_str(cn) if cn else 'CAST(NULL AS CHAR)'} AS courtesy_name FROM DUAL"
        )
    L.append("INSERT INTO poetry_person (id, dynasty_id, courtesy_name)")
    L.append("SELECT * FROM (")
    L.append(union_select(prows))
    L.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_person p WHERE p.id = t.id);")
    L.append("")

    L.append("-- ---------- 生平属性断言（一条属性一条断言） ----------")
    cl = []
    for per, pid, f in facts:
        cl.append(
            f"SELECT {sql_str(claim_id(pid, f['key']))} AS id, {sql_str(pid)} AS subject_id, "
            f"{sql_str(f['key'])} AS property_key, {sql_str(f['value'])} AS value_text, "
            f"'FACT' AS claim_kind, {sql_str(f['certainty'])} AS certainty FROM DUAL"
        )
    L.append("INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)")
    L.append("SELECT * FROM (")
    L.append(union_select(cl))
    L.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim c WHERE c.id = t.id);")
    L.append("")
    L.append("INSERT INTO poetry_claim_selection (subject_id, property_key, claim_id)")
    L.append("SELECT * FROM (")
    L.append(
        union_select(
            f"SELECT {sql_str(pid)} AS subject_id, {sql_str(f['key'])} AS property_key, "
            f"{sql_str(claim_id(pid, f['key']))} AS claim_id FROM DUAL"
            for per, pid, f in facts
        )
    )
    L.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim_selection s "
        "WHERE s.subject_id = t.subject_id AND s.property_key = t.property_key);"
    )
    L.append("")

    L.append("-- ---------- citations：逐字史书原文 ----------")
    # 主键是 (claim_id, source_id)：同一断言引同一来源的多条原文并成一行，以「……」连接
    ci = []
    for per, pid, f in facts:
        cid = claim_id(pid, f["key"])
        by_src = {}
        for e in f["evidence"]:
            by_src.setdefault(src_for(e["src"]), []).append(e)
        for source_id, eg_list in by_src.items():
            locator = "；".join(f"{SRC_LABEL[e['src']]}·{e['locator']}" for e in eg_list)
            quote = "……".join(e["quote"] for e in eg_list)
            ci.append(
                f"SELECT {sql_str(cid)} AS claim_id, {sql_str(source_id)} AS source_id, "
                f"{sql_str(locator)} AS locator, {sql_str(quote)} AS evidence_excerpt FROM DUAL"
            )
    L.append("INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)")
    L.append("SELECT * FROM (")
    L.append(union_select(ci))
    L.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_citation c "
        "WHERE c.claim_id = t.claim_id AND c.source_id = t.source_id);"
    )
    L.append("")

    L.append("-- ---------- 经历：诗人 × 阶段 A 已录事件 ----------")
    L.append(
        "-- 年份留空（UNKNOWN）：本传只记此人经历其事，未记起止年；事件本身的年份在 V015 的 event 行上。"
    )
    erows = []
    for per, pid, ex in exps:
        eid = ex["event_id"]
        exp_id = f"exp-{pid.removeprefix('person-')}-{eid.removeprefix('event-')}"
        ex["id"] = exp_id
        basis_key = ex["fact_key"]
        fact = next(f for f in per["facts"] if f["key"] == basis_key)
        title = f"{per['name']}·{fact['evidence'][0]['quote'][:12]}…"
        erows.append(
            "SELECT "
            f"{sql_str(exp_id)} AS id, 'EXPERIENCE' AS entity_type, "
            f"{sql_str(exp_id.removeprefix('exp-'))} AS slug, {sql_str(title)} AS title, "
            f"{sql_str('依据 ' + per['name'] + ' 本传原文（' + SRC_LABEL[fact['evidence'][0]['src']] + '）；' + '本传未记起止年。')} AS summary, "
            "CAST(NULL AS SIGNED) AS start_year, CAST(NULL AS SIGNED) AS end_year, 'UNKNOWN' AS time_precision"
            " FROM DUAL"
        )
    L.append("INSERT INTO poetry_content (id, entity_type, slug, title, summary, start_year, end_year, time_precision)")
    L.append("SELECT * FROM (")
    L.append(union_select(erows))
    L.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_content c WHERE c.id = t.id);")
    L.append("")
    L.append("INSERT INTO poetry_experience (id, person_id, event_id, place_id)")
    L.append("SELECT * FROM (")
    L.append(
        union_select(
            f"SELECT {sql_str(ex['id'])} AS id, {sql_str(pid)} AS person_id, "
            f"{sql_str(ex['event_id'])} AS event_id, CAST(NULL AS CHAR) AS place_id FROM DUAL"
            for per, pid, ex in exps
        )
    )
    L.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_experience e WHERE e.id = t.id);")
    L.append("")
    # 经历断言：把「此人经历此事」当作从本传读出的结论，标明 INTERPRETATION 并引原文
    ecl, esel, eci = [], [], []
    for per, pid, ex in exps:
        fact = next(f for f in per["facts"] if f["key"] == ex["fact_key"])
        cid = claim_id(ex["id"], "experience.event")
        ecl.append(
            f"SELECT {sql_str(cid)} AS id, {sql_str(ex['id'])} AS subject_id, "
            f"'experience.event' AS property_key, {sql_str(ex['event_id'])} AS value_text, "
            f"'INTERPRETATION' AS claim_kind, 'LIKELY' AS certainty FROM DUAL"
        )
        esel.append(
            f"SELECT {sql_str(ex['id'])} AS subject_id, 'experience.event' AS property_key, "
            f"{sql_str(cid)} AS claim_id FROM DUAL"
        )
        by_src = {}
        for e in fact["evidence"]:
            by_src.setdefault(src_for(e["src"]), []).append(e)
        for source_id, eg_list in by_src.items():
            locator = "；".join(f"{SRC_LABEL[e['src']]}·{e['locator']}（经历由此句读出）" for e in eg_list)
            quote = "……".join(e["quote"] for e in eg_list)
            eci.append(
                f"SELECT {sql_str(cid)} AS claim_id, {sql_str(source_id)} AS source_id, "
                f"{sql_str(locator)} AS locator, {sql_str(quote)} AS evidence_excerpt FROM DUAL"
            )
    L.append("INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)")
    L.append("SELECT * FROM (")
    L.append(union_select(ecl))
    L.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim c WHERE c.id = t.id);")
    L.append("")
    L.append("INSERT INTO poetry_claim_selection (subject_id, property_key, claim_id)")
    L.append("SELECT * FROM (")
    L.append(union_select(esel))
    L.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim_selection s "
        "WHERE s.subject_id = t.subject_id AND s.property_key = t.property_key);"
    )
    L.append("")
    L.append("INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)")
    L.append("SELECT * FROM (")
    L.append(union_select(eci))
    L.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_citation c "
        "WHERE c.claim_id = t.claim_id AND c.source_id = t.source_id);"
    )
    L.append("")

    L.append("-- ---------- coverage ----------")
    L.append(
        "INSERT INTO poetry_coverage (id, entity_type, from_year, to_year, coverage_kind, status, note, updated_by, updated_at)"
    )
    L.append("SELECT * FROM (")
    L.append(
        "SELECT 'cov-person-tang-618-907' AS id, 'PERSON' AS entity_type, "
        "618 AS from_year, 907 AS to_year, 'PARTIAL' AS coverage_kind, "
        "'DRAFT' AS status, "
        f"{sql_str('唐诗三百首头部 7 位诗人已录入（合计 177 首／366 首），每条史实有旧唐书文苑或新唐书文艺的逐字原文；'
                    '其余作者核到出处再补。生卒年两史不一致的一律不写。')} AS note, "
        "'chronology-emit' AS updated_by, NOW() AS updated_at FROM DUAL"
    )
    L.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_coverage c WHERE c.id = t.id);")
    L.append("")
    L.append(
        "INSERT INTO poetry_schema_version (version_no, description)\n"
        f"SELECT 16, 'Tang person biographies: 7 poets, {len(facts)} sourced attributes cited verbatim from Jiu Tangshu Wenyuan and Xin Tangshu Wenyi; birth/death years left UNKNOWN where the two histories disagree'\n"
        "FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 16);"
    )
    L.append("COMMIT;")
    L.append("")
    return "\n".join(L) + "\n"


def build_rollback(doc):
    persons = doc["persons"]
    pids = [person_id(p) for p in persons]
    new_pids = [person_id(p) for p in persons if not p.get("id")]
    all_claims = [claim_id(pid, f["key"]) for p, pid in zip(persons, pids) for f in p["facts"]]
    exp_ids = [f"exp-{pid.removeprefix('person-')}-{ex['event_id'].removeprefix('event-')}"
               for p, pid in zip(persons, pids) for ex in p.get("experiences", [])]
    exp_claims = [claim_id(e, "experience.event") for e in exp_ids]
    exp_subjects = pids + exp_ids

    def in_list(ids):
        return ", ".join(sql_str(i) for i in ids)

    dufu = next(p for p in persons if p.get("id"))
    srcs = "'source-jiutangshu-wenyuan', 'source-xintangshu-wenyi'"
    return (
        """-- V016 回滚：删除本迁移写入的人物实体/属性断言/出处/经历/覆盖。不删除 version_no=16 账本行。
-- person-du-fu 与 person-tang-ruler-* 是 V002/V014 的行：本迁移只补新增属性断言与出处，
-- 并把 person-du-fu 的「待核查」占位 summary 换成本批有出处的 summary——回滚只在该行仍是本迁移写入的值时还原。
-- 来源行仅在仍无引用且仍为 PENDING 时删除。"""
        + "DELETE FROM poetry_citation WHERE claim_id IN ("
        + in_list(all_claims + exp_claims)
        + f") AND source_id IN ({srcs});\n"
        + "DELETE FROM poetry_claim_selection WHERE subject_id IN ("
        + in_list(exp_subjects)
        + ");\n"
        + "DELETE FROM poetry_claim WHERE id IN ("
        + in_list(all_claims + exp_claims)
        + ");\n"
        + "DELETE FROM poetry_experience WHERE id IN ("
        + in_list(exp_ids)
        + ");\n"
        + "DELETE FROM poetry_content WHERE id IN ("
        + in_list(exp_ids + new_pids)
        + ");\n"
        + "DELETE FROM poetry_person WHERE id IN ("
        + in_list(new_pids)
        + ");\n"
        + f"UPDATE poetry_content SET summary = {sql_str(V002_DUFU_SUMMARY)}\n"
        + f" WHERE id = 'person-du-fu' AND summary = {sql_str(dufu['summary'])} AND status <> 'PUBLISHED';\n"
        "DELETE FROM poetry_coverage WHERE id = 'cov-person-tang-618-907';\n"
        + f"DELETE FROM poetry_source WHERE id IN ({srcs})\n"
        "  AND verification_status = 'PENDING'\n"
        "  AND NOT EXISTS (SELECT 1 FROM poetry_citation c WHERE c.source_id = poetry_source.id);\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-sql", required=True)
    ap.add_argument("--out-rollback", required=True)
    args = ap.parse_args()
    doc = json.loads((HERE / "tang-persons.json").read_text(encoding="utf-8"))
    sql = build_sql(doc)
    rb = build_rollback(doc)
    out_sql = pathlib.Path(args.out_sql)
    out_rb = pathlib.Path(args.out_rollback)
    out_sql.write_text(sql, encoding="utf-8")
    out_rb.write_text(rb, encoding="utf-8")
    print(f"wrote {out_sql} bytes {len(sql.encode('utf-8'))}")
    print(f"wrote {out_rb} bytes {len(rb.encode('utf-8'))}")


if __name__ == "__main__":
    main()
