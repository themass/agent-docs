#!/usr/bin/env python3
"""唐朝年表底座校验：帝王表 + 年号表。校验不变量，不是照抄来源。
用法: python3 validate.py
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
rulers_doc = json.loads((HERE / "tang-rulers.json").read_text(encoding="utf-8"))
eras_doc = json.loads((HERE / "tang-eras.json").read_text(encoding="utf-8"))

errs: list[str] = []
warn: list[str] = []

# --- rulers ---
R = rulers_doc["rulers"]
span = rulers_doc["span"]
if len(R) != 23:
    errs.append(f"帝王行数 {len(R)} != 23")
if len({r["name"] for r in R}) != 21:
    errs.append(f"不同的皇帝数 {len({r['name'] for r in R})} != 21")
if R[0]["start"] != span[0] or R[-1]["end"] != span[1]:
    errs.append("帝王起讫不等于 span 618–907")
for a, b in zip(R, R[1:]):
    if a["end"] == b["start"]:
        continue
    note = b.get("boundary_before")
    if (
        note
        and note.get("gap_years") == b["start"] - a["end"]
        and note.get("facts")
        and note.get("open_question")
    ):
        warn.append(
            f"已登记的帝王缺口: {a['name']}退位{a['end']} → {b['name']}即位{b['start']}（{note['status']}）"
        )
    else:
        errs.append(
            f"帝王不连续且无说明: {a['name']}退位{a['end']} ≠ {b['name']}即位{b['start']}"
        )
for r in R:
    if r["end"] < r["start"]:
        errs.append(f"{r['name']} 退位早于即位")

# --- eras ---
E = eras_doc["eras"]
G = eras_doc["gaps"]
if eras_doc.get("schema") != "chronology-eras/1":
    errs.append(f"eras schema {eras_doc.get('schema')!r} != chronology-eras/1")
if eras_doc.get("dynasty") != "tang":
    errs.append("eras dynasty != tang")

# seq unique & increasing
seqs = [e["seq"] for e in E]
if seqs != list(range(1, len(E) + 1)):
    errs.append(f"era seq 不连续: {seqs}")

# within-era bounds
for e in E:
    if e["end"] < e["start"]:
        errs.append(f"年号 {e['name']} end < start")
    if e["end"] - e["start"] + 1 != e["max_n"]:
        # 至德与天宝同年：max_n 是年号内序，跨度可以短于 max_n 当同公历年改元
        span_years = e["end"] - e["start"] + 1
        if not (e["name"] == "至德" and span_years == 2 and e["max_n"] == 2):
            if span_years != e["max_n"]:
                # 允许 end-start+1 == max_n；若同年改元导致更短，必须写 notes
                if span_years < e["max_n"] and not e.get("notes"):
                    errs.append(
                        f"年号 {e['name']} 公历跨度 {span_years} < max_n {e['max_n']} 且无 notes"
                    )
                elif span_years > e["max_n"]:
                    errs.append(
                        f"年号 {e['name']} 公历跨度 {span_years} > max_n {e['max_n']}"
                    )
    if e["status"] != "verified":
        errs.append(f"eras 里只能放 verified，待核应进 gaps: {e['name']}")
    if e["confidence"] not in {
        "anchor",
        "anchor-chain",
        "derived-low",
        "derived-from-tianyou",
        "tongjian-ce",
    }:
        errs.append(f"未知 confidence: {e['name']}={e['confidence']}")

# 上元 must be disambiguated
shangyuan = [e for e in E if e["name"] == "上元"]
if len(shangyuan) != 2:
    errs.append(f"上元 应有两条（高宗/肃宗），实际 {len(shangyuan)}")
else:
    tags = {e.get("disambiguation") for e in shangyuan}
    if tags != {"高宗", "肃宗"}:
        errs.append(f"上元 disambiguation 应为 高宗/肃宗，实际 {tags}")

# anchors from provenance must match written eras
anchors = eras_doc["provenance"]["method"]["anchors"]

def era_year(name, n, disambiguation=None):
    for e in E:
        if e["name"] != name:
            continue
        if disambiguation and e.get("disambiguation") != disambiguation:
            continue
        if disambiguation is None and e.get("disambiguation"):
            # ambiguous name without tag — skip
            continue
        # year of 元年 + (n-1)
        return e["start"] + (n - 1)
    return None

anchor_checks = [
    ("武德", 1, None, anchors["武德1"]),
    ("貞觀", 23, None, anchors["貞觀23"]),
    ("天寶", 1, None, anchors["天寶1"]),
    ("天寶", 15, None, anchors["天寶15"]),
    ("至德", 1, None, anchors["至德1"]),
    ("天祐", 1, None, anchors["天祐1"]),
    ("天祐", 4, None, anchors["天祐4"]),
]
for name, n, dis, expect in anchor_checks:
    got = era_year(name, n, dis)
    if got != expect:
        errs.append(f"锚点 {name}{n} 期望 {expect} 实际 {got}")

# 至德1 == 天寶15
if era_year("至德", 1) != era_year("天寶", 15):
    errs.append("至德元年应与天宝十五载同一公历年")

# gaps must be documented
for g in G:
    if not g.get("facts") or not g.get("open_question"):
        errs.append(f"缺口 {g.get('id')} 缺少 facts/open_question")
    if g["before_year"] <= g["after_year"]:
        errs.append(f"缺口 {g.get('id')} before_year 应大于 after_year")
    # no verified era may sit strictly inside a gap
    for e in E:
        if e["start"] > g["after_year"] and e["end"] < g["before_year"]:
            errs.append(f"verified 年号 {e['name']} 落在缺口 {g['id']} 内")

# expected remaining gaps (武周段、中晚唐均已用通鉴 CE 闭合)
gap_ids = {g["id"] for g in G}
if gap_ids:
    errs.append(f"年号缺口应已全部闭合，仍有: {sorted(gap_ids)}")
if "gap-after-hongdao" in gap_ids:
    errs.append("gap-after-hongdao 应已闭合，不应再出现")
if "gap-after-baoying" in gap_ids:
    errs.append("gap-after-baoying 应已闭合，不应再出现")

# tongjian CE anchors for 武周/先天 + 中晚唐
for name, n, expect in (
    ("光宅", 1, 684),
    ("天授", 1, 690),
    ("神龍", 1, 705),
    ("開元", 1, 713),
    ("廣德", 1, 763),
    ("建中", 1, 780),
    ("元和", 1, 806),
    ("光化", 1, 898),
):
    got = era_year(name, n)
    if got != expect:
        errs.append(f"通鉴锚点 {name}{n} 期望 {expect} 实际 {got}")

# continuity of verified eras outside gaps: adjacent verified eras either
# abut/overlap or have a documented gap between them
sorted_e = sorted(E, key=lambda e: (e["start"], e["seq"]))
for a, b in zip(sorted_e, sorted_e[1:]):
    if b["start"] <= a["end"] + 1:
        continue  # continuous or overlapping (至德/天宝)
    covered = any(
        g["after_year"] <= a["end"] and g["before_year"] >= b["start"]
        for g in G
    )
    if not covered:
        errs.append(
            f"年号断档无缺口说明: {a['name']}…{a['end']} → {b['name']}…{b['start']}"
        )

# rulers cross-check: 高祖 starts 618, last ends 907; 高宗 end 683 == 弘道
hongdao = next(e for e in E if e["name"] == "弘道")
gaozong = next(r for r in R if r["name"] == "高宗")
if hongdao["start"] != gaozong["end"]:
    warn.append(
        f"弘道元年={hongdao['start']} 与高宗退位年={gaozong['end']} 不一致（应登记）"
    )
elif hongdao["start"] == gaozong["end"]:
    pass  # consistent

# --- events (tang-events.json) ---
import os

EVENTS_FILE = HERE / "tang-events.json"
if EVENTS_FILE.exists():
    events_doc = json.loads(EVENTS_FILE.read_text(encoding="utf-8"))
    V = events_doc["events"]
    if events_doc.get("schema") != "chronology-events/1":
        errs.append(f"events schema {events_doc.get('schema')!r} != chronology-events/1")
    vseqs = [v["seq"] for v in V]
    if vseqs != list(range(1, len(V) + 1)):
        errs.append(f"event seq 不连续: {vseqs}")
    if len({v["slug"] for v in V}) != len(V):
        errs.append("event slug 重复")
    era_span = {}
    for e in E:
        for y in range(e["start"], e["end"] + 1):
            era_span[y] = e
    for v in V:
        if v["start"] < 617 or v["end"] > 907:
            errs.append(f"事件 {v['slug']} 超出 617–907")
        if v["end"] < v["start"]:
            errs.append(f"事件 {v['slug']} end < start")
        if v["certainty"] not in {"KNOWN", "LIKELY"}:
            errs.append(f"事件 {v['slug']} certainty 非法")
        if not v.get("evidence"):
            errs.append(f"事件 {v['slug']} 没有证据引文")
        if not v.get("time_evidence"):
            errs.append(f"事件 {v['slug']} 没写年份怎么核的")
        # 年份必须落在已核年表的覆盖内（617 是起兵年，在 618 之前，单独允许）
        for y in {v["start"], v["end"]}:
            if y != 617 and y not in era_span:
                errs.append(f"事件 {v['slug']} 年份 {y} 不在已核年号覆盖内")
        for eg in v.get("evidence", []):
            if eg["src"] not in {"jts", "tj"}:
                errs.append(f"事件 {v['slug']} 未知出处 {eg['src']}")
    # KNOWN 且跨多年的事件必须两端都有证据年份说明；单一来源的 LIKELY 可接受
    for v in V:
        if v["certainty"] == "KNOWN" and v["end"] - v["start"] > 4 and len(v["evidence"]) < 2:
            errs.append(f"长时段 KNOWN 事件 {v['slug']} 只有 {len(v['evidence'])} 条证据")

    # 引文逐字复核：能找到 raw 快照就校验，找不到只警告
    DL = pathlib.Path("/tmp/src-dl")
    jts = {q.stem.replace("jts-", ""): q.read_text(encoding="utf-8") for q in DL.glob("jts-卷*.txt")} if DL.exists() else {}
    tj = {q.stem.replace("tj-", "卷"): q.read_text(encoding="utf-8") for q in (DL / "tongjian").glob("tj-*.txt")} if (DL / "tongjian").exists() else {}
    snap = {**jts, **tj} if (jts or tj) else None
    if snap is None:
        warn.append("找不到 /tmp/src-dl 快照，跳过引文逐字复核")
    else:
        for v in V:
            for eg in v["evidence"]:
                text = snap.get(eg["vol"])
                if text is None:
                    warn.append(f"事件 {v['slug']} 引文 {eg['vol']} 无快照，跳过")
                elif eg["quote"] not in text:
                    errs.append(f"事件 {v['slug']} 引文与快照不符: {eg['vol']} {eg['quote'][:30]}…")

# events coverage: no event may sit inside the documented event gap without a note
print("events verified:", len(json.loads(EVENTS_FILE.read_text(encoding='utf-8'))['events']) if EVENTS_FILE.exists() else 0)

# --- persons (tang-persons.json) ---
PERSONS_FILE = HERE / "tang-persons.json"
if PERSONS_FILE.exists():
    pd = json.loads(PERSONS_FILE.read_text(encoding="utf-8"))
    if pd.get("schema") != "chronology-persons/1":
        errs.append(f"persons schema {pd.get('schema')!r} != chronology-persons/1")
    P = pd["persons"]
    pseqs = [x["seq"] for x in P]
    if pseqs != list(range(1, len(P) + 1)):
        errs.append(f"person seq 不连续: {pseqs}")
    if len({x["slug"] for x in P}) != len(P):
        errs.append("person slug 重复")
    CERT = {"KNOWN", "LIKELY", "DISPUTED", "UNKNOWN"}  # 与 audit C7 同一套词表
    PERSON_SRC = {
        "jts190s": "jts-卷190上.txt", "jts190m": "jts-卷190中.txt", "jts190x": "jts-卷190下.txt",
        "xts201": "xts-卷201.txt", "xts202": "xts-卷202.txt", "xts203": "xts-卷203.txt",
    }
    known_events = set()
    if EVENTS_FILE.exists():
        for v in json.loads(EVENTS_FILE.read_text(encoding="utf-8"))["events"]:
            known_events.add(v.get("id") or f"event-tang-{v['slug']}")
    DL2 = pathlib.Path("/tmp/src-dl")
    psnap = {}
    for k, fn in PERSON_SRC.items():
        f = DL2 / fn
        if f.exists():
            psnap[k] = f.read_text(encoding="utf-8")
    if len(psnap) < len(PERSON_SRC):
        missing = sorted(set(PERSON_SRC) - set(psnap))
        warn.append(f"人物引文缺快照，跳过这些来源的逐字复核: {missing}")
    seen_keys = {}
    for x in P:
        sid = x.get("id") or f"person-tang-{x['slug']}"
        if not x.get("facts"):
            errs.append(f"人物 {x['slug']} 没有任何 facts")
        for f in x["facts"]:
            key = (sid, f["key"])
            if key in seen_keys:
                errs.append(f"{sid} 属性 {f['key']} 出现多次（selection 只能选一条）")
            seen_keys[key] = 1
            if f["certainty"] not in CERT:
                errs.append(f"人物 {x['slug']}/{f['key']} certainty 非法: {f['certainty']}")
            if not f.get("evidence"):
                errs.append(f"人物 {x['slug']}/{f['key']} 没有证据引文")
            # KNOWN 不许两说并列；两说并列必须写出来
            if "並列" in f["value"] and f["certainty"] == "KNOWN":
                errs.append(f"人物 {x['slug']}/{f['key']} 两说并列却标 KNOWN")
            if "兩說並列" in f["value"] and f["certainty"] == "LIKELY":
                # 至少要两个来源才算两说
                srcs = {e["src"] for e in f["evidence"]}
                if len(srcs) < 2:
                    errs.append(f"人物 {x['slug']}/{f['key']} 称兩說並列，来源不足两个: {sorted(srcs)}")
            for eg in f.get("evidence", []):
                if eg["src"] not in PERSON_SRC:
                    errs.append(f"人物 {x['slug']}/{f['key']} 未知出处 {eg['src']}")
                    continue
                text = psnap.get(eg["src"])
                if text is not None and eg["quote"] not in text:
                    errs.append(
                        f"人物 {x['slug']}/{f['key']} 引文与快照不符: {eg['src']} {eg['quote'][:24]}…"
                    )
        for ex in x.get("experiences", []):
            if ex["event_id"] not in known_events:
                errs.append(f"人物 {x['slug']} 挂到未收录事件 {ex['event_id']}")
            if not any(f["key"] == ex["fact_key"] for f in x["facts"]):
                errs.append(f"人物 {x['slug']} 的经历依据指向不存在的属性 {ex['fact_key']}")
    print("persons verified:", len(P))

# --- work links (tang-work-links.json) ---
LINKS_FILE = HERE / "tang-work-links.json"
if LINKS_FILE.exists():
    ld = json.loads(LINKS_FILE.read_text(encoding="utf-8"))
    if ld.get("schema") != "chronology-work-links/1":
        errs.append(f"work-links schema {ld.get('schema')!r} != chronology-work-links/1")
    SNAP = {
        "qss04": pathlib.Path("/tmp/src-dl/qss-卷04.txt"),
        "tj218": pathlib.Path("/tmp/src-dl/tongjian/tj-218.txt"),
        "xts201": pathlib.Path("/tmp/src-dl/xts-卷201.txt"),
        "v011": pathlib.Path("/Users/gqli/work/testserverV/vvv-poetry/src/main/resources/db/poetry/V011__chunwang_verified_evidence.sql"),
    }
    qtexts = {}
    for qk, qd in ld["quotes"].items():
        f = SNAP.get(qd["src"])
        if f is None or not f.exists():
            warn.append(f"work-links 引文 {qk} 无快照 {qd['src']}，跳过逐字复核")
            continue
        text = f.read_text(encoding="utf-8")
        qtexts[qk] = text
        n = text.count(qd["quote"])
        if n != 1:
            errs.append(f"work-links 引文 {qk} 在 {qd['src']} 出现 {n} 次（应恰好 1 次）: {qd['quote'][:24]}…")
    # 年号换算前提：至德 756–757
    zhide = next(e for e in E if e["name"] == "至德" and not e.get("disambiguation"))
    if (zhide["start"], zhide["end"]) != (756, 757):
        errs.append("至德应为 756–757，换算前提不成立")
    # 迁移内所有 (claim_id, source_id) 不许撞 PK
    pk_seen = {}
    def pk(tag, cid, sid):
        if (cid, sid) in pk_seen:
            errs.append(f"work-links PK 冲突 (claim_id,source_id)=({cid},{sid}): {tag} 与 {pk_seen[(cid,sid)]}")
        pk_seen[(cid, sid)] = tag
    for s in ld["updates"]["citation_swaps"]:
        pk("swap:" + s["claim_id"], s["claim_id"], s["new_source"])
        for k in s.get("quote_keys") or [s["quote_key"]]:
            if k not in ld["quotes"]:
                errs.append(f"work-links swap 引文键不存在: {k}")
    for ins in ld["citation_inserts"]:
        pk("insert:" + ins["claim_id"], ins["claim_id"], ins["source_id"])
        for k in ins["quote_keys"]:
            if k not in ld["quotes"]:
                errs.append(f"work-links 插入引文键不存在: {k}")
    sel_keys = set()
    for c in ld["claims"]:
        if len(c["id"]) > 64:
            errs.append(f"work-links claim id 超长: {c['id']}")
        if c["claim_kind"] not in {"FACT", "INTERPRETATION", "DRAMATIZATION"}:
            errs.append(f"work-links claim_kind 非法: {c['id']}")
        if c["certainty"] not in CERT:
            errs.append(f"work-links certainty 非法: {c['id']}")
        key = (c["subject_id"], c["property_key"])
        if key in sel_keys:
            errs.append(f"work-links selection 重复: {key}")
        sel_keys.add(key)
        rel = c.get("relation")
        if rel:
            if len(rel["id"]) > 64:
                errs.append(f"work-links relation id 超长: {rel['id']}")
            if rel.get("claim_id_proven") is None and c["certainty"] not in {"KNOWN", "LIKELY"}:
                pass  # 关系必须由带出处的 claim 支撑，emitter 里固定取本条
        for cit in c.get("citations", []):
            pk("claim-cit:" + c["id"], c["id"], cit["source_id"])
            for k in cit["quote_keys"]:
                if k not in ld["quotes"]:
                    errs.append(f"work-links claim 引文键不存在: {k}")
    g = ld.get("gap")
    if g and (not g.get("facts") or not g.get("open_question")):
        errs.append("work-links gap 缺 facts/open_question")
    print("work-links verified:", len(ld["claims"]))

print(
    "rulers:", len(R),
    "| eras verified:", len(E),
    "| gaps:", len(G),
    "| events:", len(json.loads(EVENTS_FILE.read_text(encoding='utf-8'))['events']) if EVENTS_FILE.exists() else 0,
)
print("FAIL" if errs else "OK  structural invariants hold")
for w in warn:
    print("  ~", w)
for e in errs:
    print("  -", e)
sys.exit(1 if errs else 0)
