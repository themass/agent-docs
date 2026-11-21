#!/usr/bin/env python3
"""从 tang-rulers.json / tang-eras.json 生成 V014 迁移与回滚（只写文件，不执行）。

用法:
  python3 emit_v014.py \
    --out-sql .../V014__tang_chronology_foundation.sql \
    --out-rollback .../recovery/V014_rollback.sql
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import textwrap

HERE = pathlib.Path(__file__).parent

RULER_SLUG = {
    "高祖": "gaozu",
    "太宗": "taizong",
    "高宗": "gaozong",
    "中宗": "zhongzong",
    "睿宗": "ruizong",
    "武后": "wuhou",
    "玄宗": "xuanzong",
    "肅宗": "suzong",
    "肃宗": "suzong",
    "代宗": "daizong",
    "德宗": "dezong",
    "順宗": "shunzong",
    "憲宗": "xianzong",
    "穆宗": "muzong",
    "敬宗": "jingzong",
    "文宗": "wenzong",
    "武宗": "wuzong",
    "宣宗": "xuanzong-xuan",
    "懿宗": "yizong",
    "僖宗": "xizong",
    "昭宗": "zhaozong",
    "哀帝": "aidi",
}

ERA_SLUG = {
    "武德": "wude",
    "貞觀": "zhenguan",
    "永徽": "yonghui",
    "顯慶": "xianqing",
    "龍朔": "longshuo",
    "麟德": "linde",
    "乾封": "qianfeng",
    "總章": "zongzhang",
    "咸亨": "xianheng",
    "上元": "shangyuan",
    "儀鳳": "yifeng",
    "調露": "tiaolu",
    "永隆": "yonglong",
    "開耀": "kaiyao",
    "永淳": "yongchun",
    "弘道": "hongdao",
    "嗣聖": "sisheng",
    "文明": "wenming",
    "光宅": "guangzhai",
    "垂拱": "chuigong",
    "永昌": "yongchang",
    "載初": "zaichu",
    "天授": "tianshou",
    "如意": "ruyi",
    "長壽": "changshou",
    "延載": "yanzai",
    "證聖": "zhengsheng",
    "天冊萬歲": "tiancewansui",
    "萬歲登封": "wansuidengfeng",
    "萬歲通天": "wansuitongtian",
    "神功": "shengong",
    "聖歷": "shengli",
    "久視": "jiushi",
    "大足": "dazu",
    "長安": "changan",
    "神龍": "shenlong",
    "景龍": "jinglong",
    "唐隆": "tanglong",
    "景雲": "jingyun",
    "太極": "taiji",
    "延和": "yanhe",
    "先天": "xiantian",
    "開元": "kaiyuan",
    "天寶": "tianbao",
    "至德": "zhide",
    "乾元": "qianyuan",
    "寶應": "baoying",
    "廣德": "guangde",
    "永泰": "yongtai",
    "大歷": "dali",
    "建中": "jianzhong",
    "興元": "xingyuan",
    "貞元": "zhenyuan",
    "永貞": "yongzhen",
    "元和": "yuanhe",
    "長慶": "changqing",
    "寶曆": "baoli",
    "大和": "daihe",
    "開成": "kaicheng",
    "會昌": "huichang",
    "大中": "dazhong",
    "咸通": "xiantong",
    "乾符": "qianfu",
    "廣明": "guangming",
    "中和": "zhonghe",
    "光啟": "guangqi",
    "文德": "wende",
    "龍紀": "longji",
    "大順": "dashun",
    "景福": "jingfu",
    "乾寧": "qianning",
    "光化": "guanghua",
    "天復": "tianfu",
    "天祐": "tianyou",
}

DISAMB_SLUG = {"高宗": "gaozong", "肃宗": "suzong", "肅宗": "suzong"}


def sql_str(s: str | None) -> str:
    if s is None:
        return "NULL"
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def normalize_ruler_name(name: str) -> str:
    return name.replace("肃", "肅")


def certainty_for_era(confidence: str) -> str:
    if confidence in {"anchor", "anchor-chain", "derived-from-tianyou", "tongjian-ce"}:
        return "KNOWN"
    if confidence == "derived-low":
        return "LIKELY"
    return "UNKNOWN"


def ruler_ids(rulers: list[dict]) -> dict[tuple[str, int], str]:
    counts = {r["name"]: sum(1 for x in rulers if x["name"] == r["name"]) for r in rulers}
    seen: dict[str, int] = {}
    out: dict[tuple[str, int], str] = {}
    for r in rulers:
        name = r["name"]
        base = RULER_SLUG[name]
        seen[name] = seen.get(name, 0) + 1
        slug = f"{base}-{seen[name]}" if counts[name] > 1 else base
        out[(name, r["seq"])] = f"person-tang-ruler-{slug}"
    return out


def era_id(e: dict) -> str:
    base = ERA_SLUG[e["name"]]
    dis = e.get("disambiguation")
    if dis:
        return f"period-tang-era-{base}-{DISAMB_SLUG[dis]}"
    return f"period-tang-era-{base}"


def era_slug(e: dict) -> str:
    base = ERA_SLUG[e["name"]]
    dis = e.get("disambiguation")
    if dis:
        return f"era-{base}-{DISAMB_SLUG[dis]}"
    return f"era-{base}"


def era_title(e: dict) -> str:
    if e.get("disambiguation"):
        return f"{e['name']}（{e['disambiguation']}）"
    return e["name"]


def ruler_summary(r: dict) -> str:
    parts = [f"唐朝帝王；本纪 {r['annals_volume']}。"]
    if r.get("note"):
        note = r["note"].rstrip("。") + "。"
        parts.append(note)
    if r.get("moe_name"):
        parts.append(f"教育部表写作「{r['moe_name']}」。")
    if r.get("boundary_before"):
        parts.append("与前一位的年份边界见 claim 与 JSON boundary_before（未决）。")
    return "".join(parts)


def union_select(rows: list[str]) -> str:
    return "\nUNION ALL\n".join(rows)


def build_sql(rulers_doc: dict, eras_doc: dict) -> str:
    rulers = rulers_doc["rulers"]
    eras = eras_doc["eras"]
    gaps = eras_doc["gaps"]
    id_map = ruler_ids(rulers)

    lines: list[str] = []
    lines.append(
        textwrap.dedent(
            """\
            -- V014：唐朝年表底座（帝王 + 已核年号）。MySQL 5.6.40 兼容。
            -- 只写文件，由用户在已备份的目标库上手工执行；不要用 `mysql --force`。前置：V013 已执行。
            --
            -- 数据源（可复现）：
            --   content-agent/pipeline/data/chronology/tang-rulers.json
            --   content-agent/pipeline/data/chronology/tang-eras.json
            --   生成：python3 emit_v014.py
            --
            -- 已写入：23 位帝王（教育部年表 + 本纪卷次）；已核年号覆盖武德–天祐全段（含武周–先天与中晚唐；公历取通鉴年标题）。
            -- 不做：不核验来源、不改 status。
            --
            -- 执行前: SELECT version_no FROM poetry_schema_version ORDER BY version_no;  -- 含 13，不含 14
            -- 执行后: SELECT COUNT(*) FROM poetry_period WHERE id LIKE 'period-tang-era-%';  -- 75
            --         SELECT COUNT(*) FROM poetry_person WHERE id LIKE 'person-tang-ruler-%'; -- 23
            -- 回滚: recovery/V014_rollback.sql
            """
        ).rstrip()
    )
    lines.append("START TRANSACTION;")
    lines.append("")

    moe_url = rulers_doc["provenance"]["primary"]["url"]
    lines.append("-- ---------- sources ----------")
    lines.append(
        textwrap.dedent(
            f"""\
            INSERT INTO poetry_source (id, title, author, edition, url, rights_note, verification_status, source_kind, reliability)
            SELECT 'source-moe-rulers-table',
                   '教育部《重編國語辭典修訂本》附錄·歷代帝王在位年表',
                   '中華民國教育部',
                   '修訂本附錄；只有帝王与公元年，没有年号列',
                   {sql_str(moe_url)},
                   '政府公开辞书附录。reliability 是编者分级，不代表本条已走 verifySource。表内文帝/武帝/宣帝在此按《旧唐书》本纪写作文宗/武宗/宣宗。',
                   'PENDING', 'ONLINE_ENTRY', 'MEDIUM'
            FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_source WHERE id = 'source-moe-rulers-table');

            INSERT INTO poetry_source (id, title, author, edition, url, rights_note, verification_status, source_kind, reliability)
            SELECT 'source-jiutangshu-benji-chronology',
                   '《舊唐書》本紀（年表用：卷1–20）',
                   '劉昫等',
                   '维基文库录入本，页面标注未校对；年号取 ==/=== 节题与贞元岁首句',
                   'https://zh.wikisource.org/wiki/舊唐書',
                   '公有领域古籍。与 source-jiutangshu-benji（V013）同源，覆盖年表所用全卷；reliability 不代表已核验。',
                   'PENDING', 'OFFICIAL_HISTORY', 'HIGH'
            FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_source WHERE id = 'source-jiutangshu-benji-chronology');

            INSERT INTO poetry_source (id, title, author, edition, url, rights_note, verification_status, source_kind, reliability)
            SELECT 'source-zizhi-tongjian-tangji',
                   '《資治通鑑》唐紀（卷203–210，武周–先天公历）',
                   '司馬光',
                   '维基文库录入本；年标题自带公元/西元',
                   'https://zh.wikisource.org/wiki/資治通鑑',
                   '公有领域编年史。武周至先天段公历年取年标题；改元同异年关系仍按旧唐书。reliability 不代表已走 verifySource。',
                   'PENDING', 'OFFICIAL_HISTORY', 'HIGH'
            FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_source WHERE id = 'source-zizhi-tongjian-tangji');
            """
        ).rstrip()
    )
    lines.append("")

    # rulers content
    lines.append("-- ---------- rulers (PERSON) ----------")
    unions = []
    for r in rulers:
        cid = id_map[(r["name"], r["seq"])]
        slug_tail = cid.removeprefix("person-tang-ruler-")
        unions.append(
            "SELECT "
            f"{sql_str(cid)} AS id, 'PERSON' AS entity_type, "
            f"{sql_str('tang-ruler-' + slug_tail)} AS slug, "
            f"{sql_str(r['name'])} AS title, {sql_str(ruler_summary(r))} AS summary, "
            f"{r['start']} AS start_year, {r['end']} AS end_year, 'RANGE' AS time_precision "
            "FROM DUAL"
        )
    lines.append(
        "INSERT INTO poetry_content (id, entity_type, slug, title, summary, start_year, end_year, time_precision)"
    )
    lines.append("SELECT * FROM (")
    lines.append(union_select(unions))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_content c WHERE c.id = t.id);")
    lines.append("")

    punions = []
    for r in rulers:
        cid = id_map[(r["name"], r["seq"])]
        punions.append(
            f"SELECT {sql_str(cid)} AS id, 'dynasty-tang' AS dynasty_id, "
            f"CAST(NULL AS CHAR) AS courtesy_name FROM DUAL"
        )
    lines.append("INSERT INTO poetry_person (id, dynasty_id, courtesy_name)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(punions))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_person p WHERE p.id = t.id);")
    lines.append("")

    cunions = []
    for r in rulers:
        cid = id_map[(r["name"], r["seq"])]
        claim_id = f"claim-{cid}-time"
        value = f"{r['start']}..{r['end']} (RANGE)"
        cunions.append(
            f"SELECT {sql_str(claim_id)} AS id, {sql_str(cid)} AS subject_id, "
            f"'time.span' AS property_key, {sql_str(value)} AS value_text, "
            f"'FACT' AS claim_kind, 'KNOWN' AS certainty FROM DUAL"
        )
    lines.append("INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(cunions))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim c WHERE c.id = t.id);")
    lines.append("")

    sunions = []
    for r in rulers:
        cid = id_map[(r["name"], r["seq"])]
        sunions.append(
            f"SELECT {sql_str(cid)} AS subject_id, 'time.span' AS property_key, "
            f"{sql_str('claim-' + cid + '-time')} AS claim_id FROM DUAL"
        )
    lines.append("INSERT INTO poetry_claim_selection (subject_id, property_key, claim_id)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(sunions))
    lines.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim_selection s "
        "WHERE s.subject_id = t.subject_id AND s.property_key = t.property_key);"
    )
    lines.append("")

    ciunions = []
    for r in rulers:
        cid = id_map[(r["name"], r["seq"])]
        claim_id = f"claim-{cid}-time"
        excerpt = f"{r['name']} 即位元年 {r['start']}，退位末年 {r['end']}"
        if r.get("moe_name"):
            excerpt += f"（表内名 {r['moe_name']}）"
        locator = f"歷代帝王在位年表·唐·{r['name']}；本纪定位 {r['annals_volume']}"
        ciunions.append(
            f"SELECT {sql_str(claim_id)} AS claim_id, 'source-moe-rulers-table' AS source_id, "
            f"{sql_str(locator)} AS locator, {sql_str(excerpt)} AS evidence_excerpt FROM DUAL"
        )
    lines.append("INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(ciunions))
    lines.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_citation c "
        "WHERE c.claim_id = t.claim_id AND c.source_id = t.source_id);"
    )
    lines.append("")

    # eras
    lines.append("-- ---------- eras (PERIOD) ----------")
    eunions = []
    for e in eras:
        eid = era_id(e)
        vols = "、".join(e["vols"])
        summary = f"唐朝年号；本纪 {vols}；置信 {e['confidence']}。"
        if e.get("notes"):
            summary += e["notes"]
        eunions.append(
            f"SELECT {sql_str(eid)} AS id, 'PERIOD' AS entity_type, "
            f"{sql_str(era_slug(e))} AS slug, {sql_str(era_title(e))} AS title, "
            f"{sql_str(summary)} AS summary, {e['start']} AS start_year, "
            f"{e['end']} AS end_year, 'RANGE' AS time_precision FROM DUAL"
        )
    lines.append(
        "INSERT INTO poetry_content (id, entity_type, slug, title, summary, start_year, end_year, time_precision)"
    )
    lines.append("SELECT * FROM (")
    lines.append(union_select(eunions))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_content c WHERE c.id = t.id);")
    lines.append("")

    punions = [
        f"SELECT {sql_str(era_id(e))} AS id, 'dynasty-tang' AS dynasty_id, "
        f"CAST(NULL AS CHAR) AS parent_id FROM DUAL"
        for e in eras
    ]
    lines.append("INSERT INTO poetry_period (id, dynasty_id, parent_id)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(punions))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_period p WHERE p.id = t.id);")
    lines.append("")

    cunions = []
    for e in eras:
        eid = era_id(e)
        claim_id = f"claim-{eid}-time"
        cert = certainty_for_era(e["confidence"])
        value = f"{e['start']}..{e['end']} (RANGE) max_n={e['max_n']}"
        cunions.append(
            f"SELECT {sql_str(claim_id)} AS id, {sql_str(eid)} AS subject_id, "
            f"'time.span' AS property_key, {sql_str(value)} AS value_text, "
            f"'FACT' AS claim_kind, {sql_str(cert)} AS certainty FROM DUAL"
        )
    lines.append("INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(cunions))
    lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim c WHERE c.id = t.id);")
    lines.append("")

    sunions = [
        f"SELECT {sql_str(era_id(e))} AS subject_id, 'time.span' AS property_key, "
        f"{sql_str('claim-' + era_id(e) + '-time')} AS claim_id FROM DUAL"
        for e in eras
    ]
    lines.append("INSERT INTO poetry_claim_selection (subject_id, property_key, claim_id)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(sunions))
    lines.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim_selection s "
        "WHERE s.subject_id = t.subject_id AND s.property_key = t.property_key);"
    )
    lines.append("")

    ciunions = []
    for e in eras:
        eid = era_id(e)
        claim_id = f"claim-{eid}-time"
        vols = "、".join(e["vols"])
        locator = f"{vols}·{era_title(e)}"
        tr = e.get("transition_from_prev") or {}
        excerpt = tr.get("evidence") or e.get("notes")
        ciunions.append(
            f"SELECT {sql_str(claim_id)} AS claim_id, "
            f"'source-jiutangshu-benji-chronology' AS source_id, "
            f"{sql_str(locator)} AS locator, {sql_str(excerpt)} AS evidence_excerpt FROM DUAL"
        )
    lines.append("INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)")
    lines.append("SELECT * FROM (")
    lines.append(union_select(ciunions))
    lines.append(
        ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_citation c "
        "WHERE c.claim_id = t.claim_id AND c.source_id = t.source_id);"
    )
    lines.append("")

    # era_of relations
    # second citation for eras whose CE comes from 通鉴 titles
    tj_unions = []
    for e in eras:
        if e.get("confidence") != "tongjian-ce":
            continue
        eid = era_id(e)
        claim_id = f"claim-{eid}-time"
        locator = f"唐紀·{era_title(e)}（公元{e['start']}年）"
        excerpt = f"通鉴年标题给定公历；与旧唐书改元句交叉。start={e['start']} end={e['end']}"
        tj_unions.append(
            f"SELECT {sql_str(claim_id)} AS claim_id, "
            f"'source-zizhi-tongjian-tangji' AS source_id, "
            f"{sql_str(locator)} AS locator, {sql_str(excerpt)} AS evidence_excerpt FROM DUAL"
        )
    if tj_unions:
        lines.append("INSERT INTO poetry_citation (claim_id, source_id, locator, evidence_excerpt)")
        lines.append("SELECT * FROM (")
        lines.append(union_select(tj_unions))
        lines.append(
            ") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_citation c "
            "WHERE c.claim_id = t.claim_id AND c.source_id = t.source_id);"
        )
        lines.append("")

    lines.append("-- ---------- era_of relations ----------")
    runions: list[tuple[str, str, str, str, str]] = []
    for e in eras:
        eid = era_id(e)
        raw = e.get("ruler") or ""
        names = [normalize_ruler_name(x.strip()) for x in re.split(r"[/、]", raw) if x.strip()]
        for name in names:
            chosen = None
            for r in rulers:
                if r["name"] != name:
                    continue
                if r["end"] < e["start"] or r["start"] > e["end"]:
                    continue
                chosen = id_map[(r["name"], r["seq"])]
                break
            if chosen is None:
                for r in rulers:
                    if r["name"] == name:
                        chosen = id_map[(r["name"], r["seq"])]
                        break
            if chosen is None:
                continue
            tail = chosen.removeprefix("person-tang-ruler-")
            rel_id = f"rel-{eid}-era-of-{tail}"
            if len(rel_id) > 64:
                rel_id = rel_id[:64]
            claim_id = f"claim-{eid}-era-of"
            runions.append((rel_id, eid, chosen, claim_id, name))

    seen_claim: set[str] = set()
    cunions = []
    for _rel_id, eid, _chosen, claim_id, name in runions:
        if claim_id in seen_claim:
            continue
        seen_claim.add(claim_id)
        # value_text may list multiple rulers if multiple relations share claim
        names_for_era = sorted({n for _, e2, _, c2, n in runions if c2 == claim_id})
        value = "/".join(names_for_era)
        cunions.append(
            f"SELECT {sql_str(claim_id)} AS id, {sql_str(eid)} AS subject_id, "
            f"'era.ruler' AS property_key, {sql_str(value)} AS value_text, "
            f"'FACT' AS claim_kind, 'KNOWN' AS certainty FROM DUAL"
        )
    if cunions:
        lines.append("INSERT INTO poetry_claim (id, subject_id, property_key, value_text, claim_kind, certainty)")
        lines.append("SELECT * FROM (")
        lines.append(union_select(cunions))
        lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_claim c WHERE c.id = t.id);")
        lines.append("")

    rel_sql = [
        f"SELECT {sql_str(rel_id)} AS id, {sql_str(eid)} AS subject_id, "
        f"'era_of' AS predicate, {sql_str(chosen)} AS object_id, "
        f"{sql_str(claim_id)} AS claim_id FROM DUAL"
        for rel_id, eid, chosen, claim_id, _name in runions
    ]
    if rel_sql:
        lines.append("INSERT INTO poetry_relation (id, subject_id, predicate, object_id, claim_id)")
        lines.append("SELECT * FROM (")
        lines.append(union_select(rel_sql))
        lines.append(") AS t WHERE NOT EXISTS (SELECT 1 FROM poetry_relation r WHERE r.id = t.id);")
        lines.append("")

    # coverage
    lines.append("-- ---------- coverage (verified span) ----------")
    cov = [
        (
            "SELECT 'cov-period-tang-era-618-907' AS id, 'PERIOD' AS entity_type, "
            "618 AS from_year, 907 AS to_year, 'PARTIAL' AS coverage_kind, "
            "'DRAFT' AS status, "
            f"{sql_str('已核年号：武德–天祐全段（含武周–先天与中晚唐；公历取通鉴年标题，缺题年份按相邻年序补）。')} AS note, "
            "'chronology-emit' AS updated_by, NOW() AS updated_at FROM DUAL"
        ),
        (
            "SELECT 'cov-person-tang-rulers-618-907' AS id, 'PERSON' AS entity_type, "
            "618 AS from_year, 907 AS to_year, 'PARTIAL' AS coverage_kind, "
            "'DRAFT' AS status, "
            f"{sql_str('唐朝帝王 23 行已录入（含中宗/睿宗两次在位）；高宗→中宗 683/684 边界未决。')} AS note, "
            "'chronology-emit' AS updated_by, NOW() AS updated_at FROM DUAL"
        ),
    ]
    for g in gaps:
        gid = f"cov-period-tang-{g['id']}"
        a = g["after_year"] + 1
        b = g["before_year"] - 1
        note = f"未收录年号段：{g['after_era']}后–{g['before_era']}前。{g['open_question']}"
        cov.append(
            f"SELECT {sql_str(gid)} AS id, 'PERIOD' AS entity_type, "
            f"{a} AS from_year, {b} AS to_year, 'PLANNED' AS coverage_kind, "
            f"'DRAFT' AS status, {sql_str(note)} AS note, "
            f"'chronology-emit' AS updated_by, NOW() AS updated_at FROM DUAL"
        )
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
            SELECT 14, 'Tang chronology foundation: 23 rulers + 75 verified eras (Wude–Tianyou; Zhou/Xiantian and mid/late via Tongjian CE)'
            FROM DUAL WHERE NOT EXISTS (SELECT 1 FROM poetry_schema_version WHERE version_no = 14);
            """
        ).rstrip()
    )
    lines.append("COMMIT;")
    lines.append("")
    return "\n".join(lines) + "\n"


def build_rollback(rulers_doc: dict, eras_doc: dict) -> str:
    rulers = rulers_doc["rulers"]
    eras = eras_doc["eras"]
    gaps = eras_doc["gaps"]
    id_map = ruler_ids(rulers)
    ruler_id_list = [id_map[(r["name"], r["seq"])] for r in rulers]
    era_id_list = [era_id(e) for e in eras]
    claim_ids = [f"claim-{cid}-time" for cid in ruler_id_list]
    claim_ids += [f"claim-{eid}-time" for eid in era_id_list]
    claim_ids += [f"claim-{eid}-era-of" for eid in era_id_list]
    cov_ids = [
        "cov-period-tang-era-618-907",
        "cov-person-tang-rulers-618-907",
    ] + [f"cov-period-tang-{g['id']}" for g in gaps]

    def in_list(ids: list[str]) -> str:
        return ", ".join(sql_str(i) for i in ids)

    return (
        textwrap.dedent(
            """\
            -- V014 回滚：删除本迁移写入的年表实体/断言/覆盖。不删除 version_no=14 账本行。
            -- 来源行仅在仍无引用且仍为 PENDING 时删除。
            """
        )
        + f"DELETE FROM poetry_relation WHERE subject_id IN ({in_list(era_id_list)});\n"
        + f"DELETE FROM poetry_citation WHERE claim_id IN ({in_list(claim_ids)});\n"
        + f"DELETE FROM poetry_claim_selection WHERE subject_id IN ({in_list(ruler_id_list + era_id_list)});\n"
        + f"DELETE FROM poetry_claim WHERE id IN ({in_list(claim_ids)});\n"
        + f"DELETE FROM poetry_coverage WHERE id IN ({in_list(cov_ids)});\n"
        + f"DELETE FROM poetry_period WHERE id IN ({in_list(era_id_list)});\n"
        + f"DELETE FROM poetry_person WHERE id IN ({in_list(ruler_id_list)});\n"
        + f"DELETE FROM poetry_content WHERE id IN ({in_list(ruler_id_list + era_id_list)});\n"
        + textwrap.dedent(
            """\
            DELETE FROM poetry_source WHERE id IN ('source-moe-rulers-table', 'source-jiutangshu-benji-chronology', 'source-zizhi-tongjian-tangji')
              AND verification_status = 'PENDING'
              AND NOT EXISTS (SELECT 1 FROM poetry_citation c WHERE c.source_id = poetry_source.id);
            """
        )
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-sql", type=pathlib.Path, required=True)
    ap.add_argument("--out-rollback", type=pathlib.Path, required=True)
    args = ap.parse_args()
    rulers_doc = json.loads((HERE / "tang-rulers.json").read_text(encoding="utf-8"))
    eras_doc = json.loads((HERE / "tang-eras.json").read_text(encoding="utf-8"))
    args.out_sql.write_text(build_sql(rulers_doc, eras_doc), encoding="utf-8")
    args.out_rollback.write_text(build_rollback(rulers_doc, eras_doc), encoding="utf-8")
    print("wrote", args.out_sql, "bytes", args.out_sql.stat().st_size)
    print("wrote", args.out_rollback, "bytes", args.out_rollback.stat().st_size)


if __name__ == "__main__":
    main()
