#!/usr/bin/env python3
"""V015：唐朝大事件骨架（阶段 A）。从 tang-events.json 生成迁移 + 回滚。
用法:
  python3 emit_v015.py --out-sql ../../../../../testserverV/vvv-poetry/src/main/resources/db/poetry/V015__tang_events_foundation.sql \
      --out-rollback ../../../../../testserverV/vvv-poetry/src/main/resources/db/poetry/recovery/V015_rollback.sql
约定与 emit_v014.py 相同：只写文件、不执行；全部 INSERT…WHERE NOT EXISTS 可重放；
回滚只删本迁移新增的行（event-tang-foundation 等 19 个事件；安史之乱沿用 V004 的既有行，只加出处）。
"""
import argparse
import json
import pathlib
import textwrap

from emit_v014 import DISAMB_SLUG, ERA_SLUG  # 同一目录，直接复用 slug 表

HERE = pathlib.Path(__file__).parent


def era_id(e):
    base = ERA_SLUG[e["name"]]
    dis = e.get("disambiguation")
    if dis:
        return f"period-tang-era-{base}-{DISAMB_SLUG[dis]}"
    return f"period-tang-era-{base}"


def era_label(e):
    dis = e.get("disambiguation")
    return f"{e['name']}（{dis}朝）" if dis else e["name"]

SOURCE_ROWS = [
    (
        "source-jiutangshu-benji-events",
        "《舊唐書》本紀（大事件用：卷1、2、3、6、7、8、9、11、12、14、15、17下、20下）",
        "劉昫等",
        "维基文库录入本，页面标注未校对；引文逐字摘自 raw 原文",
        "https://zh.wikisource.org/wiki/舊唐書",
        "公有领域古籍。reliability 是编者对正史本纪的分级判断，不代表本条已走 verifySource。",
        "OFFICIAL_HISTORY",
        "HIGH",
    ),
    (
        "source-zizhi-tongjian-events",
        "《資治通鑑》唐紀（大事件用：卷222、254）",
        "司馬光",
        "维基文库录入本；年标题自带公元",
        "https://zh.wikisource.org/wiki/資治通鑑",
        "公有领域编年史。安史之乱终点、黄巢入京引文取此。reliability 不代表已核验。",
        "OFFICIAL_HISTORY",
        "HIGH",
    ),
]


def sql_str(s):
    if s is None:
        return "NULL"
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def union_select(rows, width_hint=None):
    return "\nUNION ALL\n".join(rows)


def src_for(evidence_src):
    return {
        "jts": "source-jiutangshu-benji-events",
        "tj": "source-zizhi-tongjian-events",
    }[evidence_src]


def build_sql(events_doc):
    events = events_doc["events"]
    eras = json.loads((HERE / "tang-eras.json").read_text(encoding="utf-8"))["eras"]
    lines = []
    ev_ids = [ev.get("id") or f"event-tang-{ev['slug']}" for ev in events]
    new_ids = [i for i, ev in zip(ev_ids, events) if not ev.get("id")]
    claim_ids = [f"claim-{i}-time" for i in ev_ids]
    sel_ids = ev_ids

    lines.append(
        textwrap.dedent(
            f"""\
            -- V015：唐朝大事件骨架（阶段 A 第一批 20 个，617–907）。MySQL 5.6.40 兼容。
            -- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。前置：V014 已执行。
            --
            -- 数据源（可复现）：
            --   content-agent/pipeline/data/chronology/tang-events.json（每条引文已对维基文库 raw 快照逐字核验，见 validate.py）
            --   生成：python3 emit_v015.py
            --
            -- 写入：{len(events)} 个 EVENT 实体（新增 {len(new_ids)} 个；安史之乱沿用 V004 的 event-anshi-rebellion 行）；
            --       time.span 断言 {len(events)} 条（certainty 逐条给：核到起点+终点或单一明确年份=KNOWN，节标题错简=LIKELY）；
            --       每条断言引用逐字史料原文；era_of/主题关系不在此迁移发明。
            -- 更新：event-anshi-rebellion 与「叛军陷长安」是 V004 的待核草稿——
            --       安史终点 763 由通鉴卷222 广德元年条核到，claim-anshi-time 升回 KNOWN；
            --       claim-chang-an-capture-time 不动（本轮没有为「陷长安」单独找句子）。
            -- 不做：不核验来源、不改 status、不加没有出处的句子。
            --
            -- 执行前: SELECT version_no FROM poetry_schema_version ORDER BY version_no;  -- 含 14，不含 15
            -- 执行后: SELECT COUNT(*) FROM poetry_content WHERE id LIKE 'event-tang-%' OR id='event-anshi-rebellion';  -- {len(ev_ids)}
            --         SELECT certainty FROM poetry_claim WHERE id='claim-anshi-time';  -- KNOWN
            -- 回滚: recovery/V015_rollback.sql
            """
        ).rstrip()
    )
    lines.append("START TRANSACTION;")
    lines.append("")

    lines.append("-- ---------- sources ----------")
    for sid, title, author, edition, url, rights, kind, rel in SOURCE_ROWS:
        lines.append(
            textwrap.dedent(
                f"""\
                INSERT INTO poetry_source (id, title, author, edition, url, rights_note, verification_status, source_kind, reliability)
                SELECT {sql_str(sid)}, {sql_str(title)}, {sql_str(author)}, {sql_str(edition)}, {sql_str(url)},
                       {sql_str(rights)}, 'PENDING', {sql_str(kind)}, {sql_str(rel)}
                FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_source WHERE id = {sql_str(sid)});"""
            ).rstrip()
        )
    lines.append("")

    # events: content + child + claim + selection（安史之乱的 content 行已存在，NOT EXISTS 会跳过）
    lines.append("-- ---------- events (EVENT) ----------")
    cunions = []
    for ev in events:
        eid = ev.get("id") or f"event-tang-{ev['slug']}"
        summary = ev["summary"]
        cunions.append(
            "SELECT "
            f"{sql_str(eid)} AS id, 'EVENT' AS entity_type, "
            f"{sql_str(ev['slug'])} AS slug, {sql_str(ev['title'])} AS title, "
            f"{sql_str(summary)} AS summary, "
            f"{ev['start']} AS start_year, {ev['end']} AS end_year, 'RANGE' AS time_precision "
            "FROM DUAL"
        )
    lines.append(
        "INSERT INTO poetry_content (id, entity_type, slug, title, summary, start_year, end_year, time_precision)"
    )
    lines.append("SELECT * FROM (")
    lines.append(union_select(cunions))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_content c WHERE c.id = t.id);")
    lines.append("")

    punions = []
    for ev, eid in zip(events, ev_ids):
        place = ev.get("place")
        if eid == "event-anshi-rebellion":
            continue  # V004 已插入 poetry_event 行，place 保持不动
        punions.append(
            f"SELECT {sql_str(eid)} AS id, {sql_str(place) if place else 'CAST(NULL AS CHAR)'} AS place_id FROM DUAL"
        )
    lines.append("INSERT INTO poetry_event (id, place_id)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(punions))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_event e WHERE e.id = t.id);")
    lines.append("")

    lines.append("-- ---------- time.span claims ----------")
    cl = []
    for ev, eid in zip(events, ev_ids):
        claim_id = f"claim-{eid}-time"
        if claim_id == "claim-anshi-time":
            continue  # V004 已有；值一致，只补出处并升 certainty
        value = f"{ev['start']}..{ev['end']} (RANGE)"
        cl.append(
            f"SELECT {sql_str(claim_id)} AS id, {sql_str(eid)} AS subject_id, "
            f"'time.span' AS property_key, {sql_str(value)} AS value_text, "
            f"'FACT' AS claim_kind, {sql_str(ev['certainty'])} AS certainty FROM DUAL"
        )
    lines.append("INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(cl))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim c WHERE c.id = t.id);")
    lines.append("")

    sel = []
    for ev, eid in zip(events, ev_ids):
        if eid == "event-anshi-rebellion":
            continue  # V004 已选 claim-anshi-time
        sel.append(
            f"SELECT {sql_str(eid)} AS subject_id, 'time.span' AS property_key, "
            f"{sql_str('claim-' + eid + '-time')} AS claim_id FROM DUAL"
        )
    lines.append("INSERT INTO poetry_claim_selection (subject_id, property_key, claim_id)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(sel))
    lines.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim_selection s "
        "WHERE s.subject_id = t.subject_id AND s.property_key = t.property_key);"
    )
    lines.append("")

    lines.append("-- ---------- citations：逐字史料原文 ----------")
    # poetry_citation 主键是 (claim_id, source_id)：同一断言引用同一来源的多条原文
    # 必须并成一行，节与节之间以「……」连接（中国史料传统的省写标法），
    # locator 用「；」并列。JSON 里仍逐条分开保存，validate.py 逐条复核。
    ci = []
    for ev, eid in zip(events, ev_ids):
        claim_id = f"claim-{eid}-time"
        by_src: dict[str, list[dict]] = {}
        for e in ev["evidence"]:
            by_src.setdefault(src_for(e["src"]), []).append(e)
        for source_id, eg_list in by_src.items():
            locator = "；".join(e["locator"] for e in eg_list)
            quote = "……".join(e["quote"] for e in eg_list)
            ci.append(
                f"SELECT {sql_str(claim_id)} AS claim_id, {sql_str(source_id)} AS source_id, "
                f"{sql_str(locator)} AS locator, {sql_str(quote)} AS evidence_excerpt FROM DUAL"
            )
    lines.append("INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(ci))
    lines.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_citation c "
        "WHERE c.claim_id = t.claim_id AND c.source_id = t.source_id);"
    )
    lines.append("")

    lines.append("-- ---------- 安史之乱：起点+终点都核到了，升回 KNOWN（V013 因终点未核降的级） ----------")
    lines.append(
        "UPDATE poetry_claim SET certainty = 'KNOWN'\n"
        " WHERE id = 'claim-anshi-time' AND certainty = 'LIKELY' AND status <> 'PUBLISHED';"
    )
    lines.append("")

    lines.append("-- ---------- in_era 关系：事件落在哪个已核年号里 ----------")
    # 617 晋阳起兵在唐朝年号之前（隋大业），没有关系可写，跳过即可。
    rel_rows = []
    rel_claims = []
    seen_claim = set()
    for ev, eid in zip(events, ev_ids):
        overlapping = [e for e in eras if e["start"] <= ev["end"] and e["end"] >= ev["start"]]
        if not overlapping:
            continue
        names = "、".join(era_label(e) for e in overlapping)
        claim_id = f"claim-{eid}-in-era"
        if claim_id not in seen_claim:
            seen_claim.add(claim_id)
            rel_claims.append(
                f"SELECT {sql_str(claim_id)} AS id, {sql_str(eid)} AS subject_id, "
                f"'era.name' AS property_key, {sql_str(names)} AS value_text, "
                f"'FACT' AS claim_kind, 'KNOWN' AS certainty FROM DUAL"
            )
        for e in overlapping:
            oid = era_id(e)
            rel_id = f"rel-{eid}-in-era-{oid.removeprefix('period-tang-era-')}"
            if len(rel_id) > 64:
                rel_id = rel_id[:64]
            rel_rows.append(
                f"SELECT {sql_str(rel_id)} AS id, {sql_str(eid)} AS subject_id, "
                f"'in_era' AS predicate, {sql_str(oid)} AS object_id, "
                f"{sql_str(claim_id)} AS claim_id FROM DUAL"
            )
    lines.append("INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(rel_claims))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim c WHERE c.id = t.id);")
    lines.append("")
    lines.append("INSERT INTO poetry_claim_selection (subject_id, property_key, claim_id)")
    lines.append("SELECT * FROM (")
    lines.append(
        union_select(
            f"SELECT {sql_str(ev.get('id') or 'event-tang-' + ev['slug'])} AS subject_id, "
            f"'era.name' AS property_key, {sql_str('claim-' + (ev.get('id') or 'event-tang-' + ev['slug']) + '-in-era')} AS claim_id FROM DUAL"
            for ev, eid in zip(events, ev_ids)
            if any(e["start"] <= ev["end"] and e["end"] >= ev["start"] for e in eras)
        )
    )
    lines.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim_selection s "
        "WHERE s.subject_id = t.subject_id AND s.property_key = t.property_key);"
    )
    lines.append("")
    lines.append("INSERT INTO poetry_relation (id, subject_id, predicate, object_id, claim_id)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(rel_rows))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_relation r WHERE r.id = t.id);")
    lines.append("")

    lines.append("-- ---------- coverage ----------")
    cov = [
        (
            "SELECT 'cov-event-tang-617-907' AS id, 'EVENT' AS entity_type, "
            "617 AS from_year, 907 AS to_year, 'PARTIAL' AS coverage_kind, "
            "'DRAFT' AS status, "
            f"{sql_str('大事件骨架第一批 20 条（政治军事转折为主），每条有逐字史料原文；经济文化与地方性事件未录。')} AS note, "
            "'chronology-emit' AS updated_by, NOW() AS updated_at FROM DUAL"
        ),
    ]
    lines.append(
        "INSERT INTO poetry_coverage (id, entity_type, from_year, to_year, coverage_kind, status, note, updated_by, updated_at)"
    )
    lines.append("SELECT * FROM (")
    lines.append(union_select(cov))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_coverage c WHERE c.id = t.id);")
    lines.append("")

    lines.append(
        textwrap.dedent(
            """\
            INSERT INTO poetry_schema_version (version_no, description)
            SELECT 15, 'Tang events foundation: 20 dated events 617-907, every time.span cited with verbatim annals text; anshi end re-verified KNOWN'
            FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 15);
            """
        ).rstrip()
    )
    lines.append("COMMIT;")
    lines.append("")
    return "\n".join(lines) + "\n"


def build_rollback(events_doc):
    events = events_doc["events"]
    ev_ids = [ev.get("id") or f"event-tang-{ev['slug']}" for ev in events]
    new_ids = [i for i, ev in zip(ev_ids, events) if not ev.get("id")]
    # 安史之乱的 content/event/claim/selection 行属 V004：回滚不得删除
    new_claim_ids = [f"claim-{i}-time" for i in new_ids]
    all_claim_ids = [f"claim-{i}-time" for i in ev_ids]
    era_claim_ids = [f"claim-{i}-in-era" for i in ev_ids]  # 含安史之乱：这条关系是本迁移新增的

    def in_list(ids):
        return ", ".join(sql_str(i) for i in ids)

    return (
        textwrap.dedent(
            """\
            -- V015 回滚：删除本迁移写入的事件实体/断言/出处/覆盖。不删除 version_no=15 账本行。
            -- event-anshi-rebellion 及其 claim/selection 是 V004 的行：本迁移只 UPDATE certainty 与新增引用，
            -- 回滚把 certainty 恢复为 V013 后的 LIKELY，不删行。
            -- 来源行仅在仍无引用且仍为 PENDING 时删除。
            """
        )
        + "DELETE FROM poetry_citation WHERE claim_id IN ("
        + in_list(all_claim_ids)
        + ") AND source_id IN ('source-jiutangshu-benji-events', 'source-zizhi-tongjian-events');\n"
        + "UPDATE poetry_claim SET certainty = 'LIKELY' WHERE id = 'claim-anshi-time' AND certainty = 'KNOWN' AND status <> 'PUBLISHED';\n"
        + "DELETE FROM poetry_relation WHERE predicate = 'in_era' AND subject_id IN ("
        + in_list(ev_ids)
        + ");\n"
        + f"DELETE FROM poetry_claim_selection WHERE subject_id IN ({in_list(ev_ids)}) AND property_key = 'era.name';\n"
        + f"DELETE FROM poetry_claim WHERE id IN ({in_list(era_claim_ids)});\n"
        + f"DELETE FROM poetry_claim_selection WHERE subject_id IN ({in_list(new_ids)});\n"
        + f"DELETE FROM poetry_claim WHERE id IN ({in_list(new_claim_ids)});\n"
        + f"DELETE FROM poetry_event WHERE id IN ({in_list(new_ids)});\n"
        + f"DELETE FROM poetry_content WHERE id IN ({in_list(new_ids)});\n"
        + "DELETE FROM poetry_coverage WHERE id = 'cov-event-tang-617-907';\n"
        + "DELETE FROM poetry_source WHERE id IN ('source-jiutangshu-benji-events', 'source-zizhi-tongjian-events')\n"
        "  AND verification_status = 'PENDING'\n"
        "  AND NOT EXISTS (SELECT 1 FROM poetry_citation c WHERE c.source_id = poetry_source.id);\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-sql", required=True)
    ap.add_argument("--out-rollback", required=True)
    args = ap.parse_args()
    doc = json.loads((HERE / "tang-events.json").read_text(encoding="utf-8"))
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
