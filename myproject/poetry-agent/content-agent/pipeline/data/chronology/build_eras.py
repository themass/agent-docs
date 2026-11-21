#!/usr/bin/env python3
"""Tang era chain v6: mid-year in NEW section is unknown; anchors dominate."""
import json, re, pathlib
from collections import defaultdict

SRC = pathlib.Path("/tmp/src-dl")
VOLS = [
    "卷1","卷2","卷3","卷4","卷5","卷6","卷7","卷8","卷9","卷10",
    "卷11","卷12","卷13","卷14","卷15","卷16","卷17上","卷17下",
    "卷18上","卷18下","卷19上","卷19下","卷20上","卷20下",
]
vol_rank = {v: i for i, v in enumerate(VOLS)}
texts = {v: (SRC / f"jts-{v}.txt").read_text(encoding="utf-8") for v in VOLS}

CN = {"元":1,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9}
YEAR_NUM = re.compile(
    r"(?P<num>二十[一二三四五六七八九]|二十|十[一二三四五六七八九]|十|[元一二三四五六七八九])(?P<unit>年|載)$"
)
MONTH = {
    "正":1,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,
    "十一":11,"十二":12,"腊":12,"臘":12,
}

def cn_year(num: str) -> int:
    if num in CN:
        return CN[num]
    if num.startswith("二十"):
        return 20 + (CN[num[2:]] if len(num) > 2 else 0)
    if num.startswith("十"):
        return 10 + (CN[num[1:]] if len(num) > 1 else 0)
    raise ValueError(num)

def cn_to_re(n: int) -> str:
    table = {
        1:"元|一",2:"二",3:"三",4:"四",5:"五",6:"六",7:"七",8:"八",9:"九",
        10:"十",11:"十一",12:"十二",13:"十三",14:"十四",15:"十五",16:"十六",
        20:"二十",21:"二十一",22:"二十二",23:"二十三",29:"二十九",
    }
    return table.get(n, "__none__")

def parse_year_body(body: str):
    body = body.strip()
    ym = YEAR_NUM.search(body)
    if not ym or ym.end() != len(body):
        return None
    era = body[: ym.start("num")]
    if not era:
        return None
    return era, cn_year(ym.group("num")), ym.group("unit")

rows = []
for vol in VOLS:
    t = texts[vol]
    for m in re.finditer(r"={2,4}\s*([^\n=]+?)\s*={2,4}", t):
        parsed = parse_year_body(m.group(1))
        if not parsed:
            continue
        era, n, unit = parsed
        rows.append({
            "vol": vol, "raw": m.group(1).strip(), "era": era, "n": n,
            "unit": unit, "pos": m.start(), "kind": "header",
        })

# 贞元 prose in 卷13/14; also scan for more 贞元N年 at line starts
for vol in ("卷13", "卷14"):
    t = texts[vol]
    existing = {(r["era"], r["n"]) for r in rows}
    for m in re.finditer(r"(?:^|\n)\s*(?P<body>貞元[元一二三四五六七八九十]+年)", t):
        parsed = parse_year_body(m.group("body"))
        if not parsed:
            continue
        era, n, unit = parsed
        if (era, n) in existing:
            continue
        after = t[m.end(): m.end() + 16]
        if not re.match(r"\s*(春|夏|秋|冬|正|[一二三四五六七八九十]+月)", after):
            continue
        rows.append({
            "vol": vol, "raw": m.group("body"), "era": era, "n": n,
            "unit": unit, "pos": m.start(), "kind": "prose",
        })
        existing.add((era, n))

def era_key(r):
    if r["era"] == "上元":
        return "上元(高宗)" if vol_rank[r["vol"]] <= vol_rank["卷5"] else "上元(肃宗)"
    return r["era"]

for r in rows:
    r["key"] = era_key(r)
rows.sort(key=lambda r: (vol_rank[r["vol"]], r["pos"]))

ordered, seen = [], set()
for i, r in enumerate(rows):
    pair = (r["key"], r["n"])
    if pair in seen:
        continue
    seen.add(pair)
    next_pos = None
    for j in range(i + 1, len(rows)):
        if rows[j]["vol"] == r["vol"]:
            next_pos = rows[j]["pos"]
            break
        break
    ordered.append({**r, "next_pos": next_pos})

print(f"unique year marks: {len(ordered)}")

def section_bounds(mark):
    t = texts[mark["vol"]]
    return t[mark["pos"]: mark.get("next_pos") or len(t)]

def month_near(local, local_pos):
    ctx = local[max(0, local_pos - 100): local_pos + 5]
    mm = re.search(r"(?P<m>十[一二]|[正一二三四五六七八九]|十|腊|臘)\s*月", ctx)
    return MONTH.get(mm.group("m")) if mm else None

def detect_change(prev, cur):
    """Return (same_year|None, evidence, month, confidence).
    same_year None = do not use this transition for assignment.
    """
    new_era = cur["era"]
    prev_sec = section_bounds(prev)
    prev_tail = prev_sec[-2500:] if len(prev_sec) > 2500 else prev_sec
    new_sec = section_bounds(cur)
    blob = prev_tail + "\n<<<BOUNDARY>>>\n" + new_sec
    boundary_at = len(prev_tail) + len("\n<<<BOUNDARY>>>\n")

    # old-era continued as prev_n+1 then 改元 → NEW 元年 is that calendar year
    # = previous header year + 1
    cont = re.search(
        rf"(?:^|[。\n])\s*({cn_to_re(prev['n']+1)})年[\s\S]{{0,200}}改元(?:為|曰)?\s*{re.escape(new_era)}",
        blob,
    )
    if cont:
        return False, f"old-era year {prev['n']+1} then 改元: {cont.group(0)[:70]}", None, "high"

    patterns = [
        rf"改元為\s*{re.escape(new_era)}",
        rf"改元曰\s*{re.escape(new_era)}",
        rf"改元\s*{re.escape(new_era)}",
        rf"改\s*{re.escape(new_era)}\s*元年",
    ]
    hit = hit_pos = None
    for p in patterns:
        m = re.search(p, blob)
        if m:
            hit, hit_pos = m.group(0), m.start()
            break
    if hit is None:
        m = re.search(r"改元", new_sec[:220])
        if m:
            hit, hit_pos = "改元(unnamed near 元年 start)", boundary_at + m.start()

    if hit is None:
        # no evidence — default next-year, low confidence
        return False, "default next-year (no 改元 phrase)", None, "low"

    in_prev = hit_pos < boundary_at
    local = prev_tail if in_prev else new_sec
    local_pos = hit_pos if in_prev else hit_pos - boundary_at
    month = month_near(local, local_pos)

    if in_prev:
        return True, f"改元 in previous section: {hit}", month, "high"
    if month == 1:
        return False, f"正月改元 in new section: {hit}", month, "high"
    if month is not None and month >= 2:
        # Mid-year rename inside the new 元年 section: does NOT tell us whether
        # this calendar year equals the previous header's year. Leave unknown.
        return None, f"mid-year改元 in new section (ambiguous vs prev): {hit}", month, "n/a"
    return False, f"改元 found, month unclear → next-year: {hit}", month, "medium"

# Dense anchors: only years verified earlier in this project / by dual anchors
ANCHORS = {
    ("武德", 1): 618,
    ("貞觀", 23): 649,
    ("天寶", 1): 742,
    ("天寶", 15): 756,
    ("至德", 1): 756,
    ("天祐", 1): 904,
    ("天祐", 4): 907,
}

year_of = {}
conflicts = []
source_of = {}

def set_year(key, n, y, how, conf="high"):
    k = (key, n)
    if k in year_of and year_of[k] != y:
        conflicts.append({"pair": f"{key}{n}", "have": year_of[k], "want": y, "how": how})
        # anchors win
        if source_of.get(k, "").startswith("anchor"):
            return False
        # higher confidence wins if we tracked it; for now keep first unless how is anchor
        if how.startswith("anchor"):
            year_of[k] = y
            source_of[k] = how
            return True
        return False
    year_of[k] = y
    source_of[k] = how
    return True

for (era, n), y in ANCHORS.items():
    set_year(era, n, y, "anchor")

by_key = defaultdict(list)
for r in ordered:
    by_key[r["key"]].append(r)

def fill_within(key):
    ns = sorted({r["n"] for r in by_key[key]})
    known = [(n, year_of[(key, n)]) for n in ns if (key, n) in year_of]
    if not known:
        return False
    changed = False
    base_n, base_y = known[0]
    for n in ns:
        y = base_y + (n - base_n)
        before = year_of.get((key, n))
        set_year(key, n, y, f"within:{key}")
        if before != year_of.get((key, n)):
            changed = True
    return changed

for key in by_key:
    fill_within(key)

def apply_pass(use_low=False):
    changed = False
    transitions = []
    prev = None
    for r in ordered:
        if prev is None:
            prev = r
            continue
        if r["key"] != prev["key"]:
            same, why, month, conf = detect_change(prev, r)
            entry = {
                "from": f"{prev['key']}{prev['n']}",
                "to": f"{r['key']}{r['n']}",
                "same_year": same,
                "month": month,
                "evidence": why,
                "confidence": conf,
                "vol": r["vol"],
            }
            apply = same is not None and (conf in ("high", "medium") or (use_low and conf == "low"))
            y_prev = year_of.get((prev["key"], prev["n"]))
            y_cur1 = year_of.get((r["key"], 1)) if r["n"] == 1 else year_of.get((r["key"], r["n"]))

            if apply and r["n"] == 1:
                if y_prev is not None:
                    y_new = y_prev if same else y_prev + 1
                    before = year_of.get((r["key"], 1))
                    ok = set_year(r["key"], 1, y_new, f"fwd:{conf}:{why}")
                    fill_within(r["key"])
                    if before != year_of.get((r["key"], 1)):
                        changed = True
                    entry["year"] = year_of.get((r["key"], 1))
                    entry["applied"] = ok
                if y_cur1 is not None and y_prev is None:
                    y_p = y_cur1 if same else y_cur1 - 1
                    before = year_of.get((prev["key"], prev["n"]))
                    ok = set_year(prev["key"], prev["n"], y_p, f"back:{conf}:{why}")
                    fill_within(prev["key"])
                    if before != year_of.get((prev["key"], prev["n"])):
                        changed = True
                    entry["year"] = y_cur1
                    entry["applied_back"] = ok
            elif apply and r["n"] > 1 and y_prev is not None and (r["key"], r["n"]) not in year_of:
                # era first appears at n>1; if transition is next-year for year 1,
                # then year n = y_prev + n (if next) or y_prev + n - 1 (if same for yr1)
                if same is False:
                    y_n = y_prev + r["n"]
                else:
                    y_n = y_prev + r["n"] - 1
                set_year(r["key"], r["n"], y_n, f"gap:{conf}")
                fill_within(r["key"])
                changed = True
                entry["gap"] = True
                entry["year"] = y_n
            transitions.append(entry)
        else:
            yp = year_of.get((prev["key"], prev["n"]))
            yc = year_of.get((r["key"], r["n"]))
            if yp is not None and yc is None:
                set_year(r["key"], r["n"], yp + (r["n"] - prev["n"]), "seq")
                changed = True
            elif yc is not None and yp is None:
                set_year(prev["key"], prev["n"], yc - (r["n"] - prev["n"]), "seq-back")
                fill_within(prev["key"])
                changed = True
        prev = r
    return changed, transitions

transitions = []
for _ in range(8):
    changed, transitions = apply_pass(use_low=False)
    if not changed:
        break
# second phase: allow low-confidence defaults to fill remaining holes
for _ in range(8):
    changed, transitions = apply_pass(use_low=True)
    if not changed:
        break

# re-assert anchors
for (era, n), y in ANCHORS.items():
    set_year(era, n, y, "anchor")
    fill_within(era)

print("\n=== anchors ===")
for (era, n), y in ANCHORS.items():
    got = year_of.get((era, n))
    print(f"  {era}{n}: expect {y} got {got} {'OK' if got == y else 'FAIL'}")

print(f"\n=== conflicts ({len(conflicts)}) ===")
for c in conflicts[:20]:
    print(" ", c)

RULER_BY_VOL = {
    "卷1": "高祖", "卷2": "太宗", "卷3": "太宗", "卷4": "高宗", "卷5": "高宗",
    "卷6": "武后", "卷7": "中宗/睿宗", "卷8": "玄宗", "卷9": "玄宗",
    "卷10": "肃宗", "卷11": "代宗", "卷12": "德宗", "卷13": "德宗", "卷14": "德宗/宪宗",
    "卷15": "宪宗", "卷16": "穆宗", "卷17上": "敬宗/文宗", "卷17下": "文宗",
    "卷18上": "武宗", "卷18下": "宣宗", "卷19上": "懿宗", "卷19下": "僖宗",
    "卷20上": "昭宗", "卷20下": "哀帝",
}

eras = []
for key, rs in by_key.items():
    ns = sorted({r["n"] for r in rs})
    years = {n: year_of[(key, n)] for n in ns if (key, n) in year_of}
    if not years:
        eras.append({"key": key, "name": rs[0]["era"], "status": "unresolved",
                     "vols": sorted({r["vol"] for r in rs}, key=lambda v: vol_rank[v])})
        continue
    vols = sorted({r["vol"] for r in rs}, key=lambda v: vol_rank[v])
    missing = [n for n in range(1, max(ns) + 1) if n not in years]
    holes = [n for n in range(min(years), max(years) + 1) if n not in years]
    eras.append({
        "key": key,
        "name": rs[0]["era"],
        "start": years[min(years)],
        "end": years[max(years)],
        "max_n": max(ns),
        "min_n_seen": min(years),
        "missing_n": missing,
        "holes": holes,
        "vols": vols,
        "ruler_hint": RULER_BY_VOL.get(vols[0]),
        "status": "ok" if min(years.keys()) == 1 and not missing else "partial",
    })
eras_sorted = sorted([e for e in eras if "start" in e], key=lambda e: (e["start"], e["name"]))
unresolved = [e for e in eras if e.get("status") == "unresolved"]

conf_in = {}
for t in transitions:
    m = re.match(r"(.+?)(\d+)$", t["to"])
    if m:
        conf_in[m.group(1)] = t.get("confidence", "low")

print(f"\n=== eras resolved {len(eras_sorted)} / unresolved {len(unresolved)} ===")
for e in eras_sorted:
    extra = ""
    if e["missing_n"]:
        extra += f"  missing_n={e['missing_n']}"
    if e.get("holes"):
        extra += f"  holes={e['holes']}"
    print(f"  {e['start']}-{e['end']}  {e['name']:8s}  n=1..{e['max_n']:<2d}  {e['status']:7s}  in={conf_in.get(e['key'],'?')}  {e['ruler_hint']}{extra}")

print("\n=== ambiguous / skipped transitions ===")
for t in transitions:
    if t.get("same_year") is None:
        print(f"  {t['from']} -> {t['to']}: {t['evidence'][:80]}")

print("\n=== continuity jumps/missing ===")
breaks = []
prev_y = prev_r = None
for r in ordered:
    y = year_of.get((r["key"], r["n"]))
    if y is None:
        breaks.append(("missing", r["key"], r["n"], r["vol"]))
    elif prev_y is not None and y - prev_y > 1:
        breaks.append(("jump", f"{prev_r['key']}{prev_r['n']}={prev_y}", f"{r['key']}{r['n']}={y}", y - prev_y))
    elif prev_y is not None and y < prev_y:
        breaks.append(("back", f"{prev_r['key']}{prev_r['n']}={prev_y}", f"{r['key']}{r['n']}={y}"))
    if y is not None:
        prev_y, prev_r = y, r
for b in breaks:
    print(" ", b)

checks = [
    ("武德1", ("武德",1), 618), ("貞觀1", ("貞觀",1), 627), ("貞觀23", ("貞觀",23), 649),
    ("永徽1", ("永徽",1), 650), ("顯慶1", ("顯慶",1), 656), ("龍朔1", ("龍朔",1), 661),
    ("麟德1", ("麟德",1), 664), ("乾封1", ("乾封",1), 666), ("總章1", ("總章",1), 668),
    ("咸亨1", ("咸亨",1), 670), ("上元高1", ("上元(高宗)",1), 674), ("儀鳳1", ("儀鳳",1), 676),
    ("調露1", ("調露",1), 679), ("永隆1", ("永隆",1), 680), ("開耀1", ("開耀",1), 681),
    ("永淳1", ("永淳",1), 682), ("弘道1", ("弘道",1), 683), ("光宅1", ("光宅",1), 684),
    ("垂拱1", ("垂拱",1), 685), ("永昌1", ("永昌",1), 689), ("天授1", ("天授",1), 690),
    ("長壽1", ("長壽",1), 692), ("延載1", ("延載",1), 694), ("天冊萬歲1", ("天冊萬歲",1), 695),
    ("萬歲通天1", ("萬歲通天",1), 696), ("神功1", ("神功",1), 697), ("聖歷1", ("聖歷",1), 698),
    ("久視1", ("久視",1), 700), ("長安1", ("長安",1), 701), ("神龍1", ("神龍",1), 705),
    ("景龍1", ("景龍",1), 707), ("景雲1", ("景雲",1), 710), ("先天1", ("先天",1), 712),
    ("開元1", ("開元",1), 713), ("開元29", ("開元",29), 741),
    ("天寶1", ("天寶",1), 742), ("天寶15", ("天寶",15), 756), ("至德1", ("至德",1), 756),
    ("乾元1", ("乾元",1), 758), ("上元肃1", ("上元(肃宗)",1), 760), ("寶應1", ("寶應",1), 762),
    ("廣德1", ("廣德",1), 763), ("永泰1", ("永泰",1), 765), ("大歷1", ("大歷",1), 766),
    ("建中1", ("建中",1), 780), ("興元1", ("興元",1), 784), ("貞元1", ("貞元",1), 785),
    ("貞元21", ("貞元",21), 805), ("元和7", ("元和",7), 812), ("元和15", ("元和",15), 820),
    ("長慶1", ("長慶",1), 821), ("寶曆1", ("寶曆",1), 825), ("大和1", ("大和",1), 827),
    ("開成1", ("開成",1), 836), ("會昌1", ("會昌",1), 841), ("大中1", ("大中",1), 847),
    ("咸通1", ("咸通",1), 860), ("乾符1", ("乾符",1), 874), ("廣明1", ("廣明",1), 880),
    ("中和1", ("中和",1), 881), ("光啟1", ("光啟",1), 885), ("文德1", ("文德",1), 888),
    ("龍紀1", ("龍紀",1), 889), ("大順1", ("大順",1), 890), ("景福1", ("景福",1), 892),
    ("乾寧1", ("乾寧",1), 894), ("光化1", ("光化",1), 898), ("天復1", ("天復",1), 901),
    ("天祐1", ("天祐",1), 904), ("天祐4", ("天祐",4), 907),
]
ok = bad = 0
print("\n=== spot checks (failures only) ===")
for label, keyn, expect in checks:
    got = year_of.get(keyn)
    if got == expect:
        ok += 1
    else:
        bad += 1
        print(f"  {label:10s} expect {expect} got {got}")
print(f"spot: {ok} ok, {bad} not (of {len(checks)})")

out = {
    "schema": "chronology-era-chain/1",
    "year_of": {
        f"{k[0]}|{k[1]}": v
        for k, v in sorted(year_of.items(), key=lambda kv: (kv[1], kv[0][0], kv[0][1]))
    },
    "eras": eras_sorted,
    "unresolved": unresolved,
    "transitions": transitions,
    "conflicts": conflicts,
    "breaks": [list(map(str, b)) for b in breaks],
    "spot_checks": [
        {"label": l, "expect": e, "got": year_of.get(k), "ok": year_of.get(k) == e}
        for l, k, e in checks
    ],
}
pathlib.Path("/tmp/aud/era_chain.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("wrote /tmp/aud/era_chain.json")
