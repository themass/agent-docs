"""Mock 的种子数据。

内容逐字取自 testserverV/vvv-poetry 的 V002__draft_seed.sql 与 V004__chunwang_context_draft.sql,
没有任何自编史实。所有来源都是 PENDING,所有 locator 都保持 V002/V004 里的占位词（"待…")。

与契约 §9 的差异（详见 README 与 docs/handoff/A-parts/S2.md):
- 真实文本版本 id 是 ``text-chun-wang-draft``,不是契约示例里的 ``text-chun-wang-v1``。
- V004 实际带有 2 条注释（ann-chun-wang-shanhe / ann-chun-wang-fenghuo)。按任务要求默认 0 条，
  设置环境变量 ``MOCK_SEED_V004_ANNOTATIONS=1`` 可载入这两条真实种子注释。
"""
from __future__ import annotations

from typing import Any

WORK_ID = "work-chun-wang"
VERSION_ID = "text-chun-wang-draft"
EMPTY_WORK_ID = "work-demo-empty"

LINES = [
    "国破山河在，",
    "城春草木深。",
    "感时花溅泪，",
    "恨别鸟惊心。",
    "烽火连三月，",
    "家书抵万金。",
    "白头搔更短，",
    "浑欲不胜簪。",
]


def _content(cid: str, etype: str, slug: str, title: str, summary: str,
             start: int | None = None, end: int | None = None,
             precision: str = "UNKNOWN") -> dict[str, Any]:
    return {
        "id": cid, "entity_type": etype, "slug": slug, "title": title, "summary": summary,
        "start_year": start, "end_year": end, "time_precision": precision,
        "status": "DRAFT", "revision": 1, "reviewed_by": None,
    }


def _claim(cid: str, subject: str, key: str, value: str, kind: str, certainty: str) -> dict[str, Any]:
    return {"id": cid, "subject_id": subject, "property_key": key, "value_text": value,
            "claim_kind": kind, "certainty": certainty, "status": "DRAFT"}


def _source(sid: str, title: str, author: str | None, edition: str | None, url: str | None,
            rights: str, kind: str | None, reliability: str | None) -> dict[str, Any]:
    return {"id": sid, "title": title, "author": author, "edition": edition, "url": url,
            "rights_note": rights, "source_kind": kind, "reliability": reliability,
            "verification_status": "PENDING", "verified_by": None}


def build_seed(include_v004_annotations: bool = False) -> dict[str, Any]:
    contents: dict[str, dict[str, Any]] = {}
    for row in [
        _content("dynasty-tang", "DYNASTY", "tang", "唐", "待核查：朝代时间范围与背景。", 618, 907, "RANGE"),
        _content("person-du-fu", "PERSON", "du-fu", "杜甫", "待核查：生平、年谱与相关史料。", 712, 770, "APPROXIMATE"),
        _content(WORK_ID, "WORK", "chun-wang", "春望",
                 "待核查：作者归属、文本版本、写作时地与解释依据。", 757, 757, "EXACT"),
        _content("place-chang-an", "PLACE", "chang-an", "长安", "今西安一带：唐长安城不等于今西安城，不冒充等价。"),
        _content("event-anshi-rebellion", "EVENT", "anshi-rebellion", "安史之乱",
                 "待核查：起讫年份采用通行说，需史源定位。", 755, 763, "RANGE"),
        _content("event-chang-an-capture", "EVENT", "chang-an-capture", "叛军陷长安",
                 "待核查：具体月份与史料表述需核对。", 756, 756, "EXACT"),
        _content("exp-du-fu-chang-an-757", "EXPERIENCE", "du-fu-chang-an-757", "杜甫困居长安一带（安史乱中）",
                 "待核查：年谱依据与时间需核对，可能与他说并存。", 757, 757, "EXACT"),
        _content("theme-anshi-rebellion", "THEME", "anshi-rebellion-line", "安史之乱这条线",
                 "主题线草稿：把战乱中的事件、行程与作品串成可停留的一条线。", 755, 763, "RANGE"),
        _content("bg-chun-wang-scene", "BACKGROUND", "chun-wang-scene", "眼前：春天的长安城", "编写草稿，措辞待复核。"),
        _content("bg-chun-wang-city", "BACKGROUND", "chun-wang-city", "这座城：沦陷后的京城", "编写草稿，措辞与史实依据待复核。"),
        _content("bg-chun-wang-world", "BACKGROUND", "chun-wang-world", "这个天下：战火不停", "编写草稿，措辞与史实依据待复核。"),
        _content("bg-chun-wang-person", "BACKGROUND", "chun-wang-person", "这个人：被困在长安的杜甫", "编写草稿，生平依据待复核。"),
        # 空作品：只有标题，没有任何版本/行/背景/注释，用于"从空白起草"演示。这是 Mock 自有的演示数据，
        # 不是真实库里的行。
        _content(EMPTY_WORK_ID, "WORK", "demo-empty", "空白作品（演示）",
                 "Mock 演示用：仅有标题，没有文本版本、诗句、背景或注释。"),
    ]:
        contents[row["id"]] = row

    works = {
        WORK_ID: {"id": WORK_ID, "genre": None, "dynasty_id": "dynasty-tang", "creation_place_id": None},
        EMPTY_WORK_ID: {"id": EMPTY_WORK_ID, "genre": None, "dynasty_id": None, "creation_place_id": None},
    }

    versions = {
        VERSION_ID: {
            "id": VERSION_ID, "work_id": WORK_ID, "version_code": "draft-simplified-001",
            "label": "简体录入草稿（非教材核定版）", "script": "SIMPLIFIED",
            "source_id": "source-chun-wang-candidate", "source_locator": "全诗；待逐字核对",
            "status": "DRAFT",
        }
    }
    lines = {(VERSION_ID, i + 1): {"version_id": VERSION_ID, "line_seq": i + 1, "content": text, "pinyin": None}
             for i, text in enumerate(LINES)}

    sources = {}
    for row in [
        _source("source-chun-wang-candidate", "《春望》公开文本核查入口（待核对版本）", None, None,
                "https://zh.wikisource.org/wiki/春望", "仅作待核查入口；需另行核对底本、版本及使用条件。", None, None),
        _source("source-anshi-candidate", "《资治通鉴》唐纪（安史之乱相关段落）", "司马光", "版本待定：需指定通行本与卷次", None,
                "正史类候选来源。reliability 是编者分级判断，不代表本条已核对。", "OFFICIAL_HISTORY", "HIGH"),
        _source("source-dufu-zhuan-candidate", "《新唐书·杜甫传》", "欧阳修 等", "版本待定", None,
                "正史类候选来源；用于生平与官职，需逐条核对原文。", "OFFICIAL_HISTORY", "HIGH"),
        _source("source-dufu-nianpu-candidate", "杜甫年谱类来源（待指定具体年谱与版本）", "待指定", "待指定", None,
                "年谱类候选来源；《春望》写作年份的分歧要靠这类来源判定。", "YEAR_BOOK", "MEDIUM"),
    ]:
        sources[row["id"]] = row

    claims = {}
    for row in [
        _claim("claim-chun-wang-author", WORK_ID, "authorship", "杜甫", "FACT", "UNKNOWN"),
        _claim("claim-tang-time", "dynasty-tang", "time.span", "618..907 (RANGE)", "FACT", "KNOWN"),
        _claim("claim-dufu-time", "person-du-fu", "time.span", "712..770 (APPROXIMATE)", "FACT", "LIKELY"),
        _claim("claim-anshi-time", "event-anshi-rebellion", "time.span", "755..763 (RANGE)", "FACT", "KNOWN"),
        _claim("claim-chang-an-capture-time", "event-chang-an-capture", "time.span", "756..756 (EXACT)", "FACT", "LIKELY"),
        _claim("claim-exp-757-time", "exp-du-fu-chang-an-757", "time.span", "757..757 (EXACT)", "FACT", "DISPUTED"),
        _claim("claim-theme-anshi-time", "theme-anshi-rebellion", "time.span", "755..763 (RANGE)", "FACT", "KNOWN"),
        _claim("claim-chun-wang-time-757", WORK_ID, "time.span",
               "757..757 (EXACT) 说一：至德二载春困居长安时作", "FACT", "DISPUTED"),
        _claim("claim-chun-wang-time-758", WORK_ID, "time.span",
               "758..758 (EXACT) 说二：至德元载说，另有年谱系于此年", "FACT", "DISPUTED"),
        _claim("claim-bg-scene", "bg-chun-wang-scene", "reading", "以\"城在而山河在\"反衬物是人非。", "INTERPRETATION", "LIKELY"),
        _claim("claim-bg-city", "bg-chun-wang-city", "context", "沦陷中的京城作为处境层。", "INTERPRETATION", "DISPUTED"),
        _claim("claim-bg-world", "bg-chun-wang-world", "context", "长期战事与音信断绝构成天下层。", "INTERPRETATION", "DISPUTED"),
        _claim("claim-bg-person", "bg-chun-wang-person", "context", "困居长安、家人离散构成个人处境层。", "INTERPRETATION", "DISPUTED"),
    ]:
        claims[row["id"]] = row

    # (claim_id, source_id) -> citation。locator 保持 V002/V004 的占位词原文。
    citations = {}
    for claim_id, source_id, locator in [
        ("claim-chun-wang-author", "source-chun-wang-candidate", "待人工核对标题与作者署名"),
        ("claim-anshi-time", "source-anshi-candidate", "待人工核对：通鉴卷次与起止表述"),
        ("claim-dufu-time", "source-dufu-zhuan-candidate", "待人工核对：杜甫传本传原文"),
        ("claim-chang-an-capture-time", "source-anshi-candidate", "待人工核对：通鉴纪事年月"),
        ("claim-exp-757-time", "source-dufu-nianpu-candidate", "待人工核对：年谱系年"),
        ("claim-chun-wang-time-757", "source-dufu-nianpu-candidate", "待人工核对：系年于至德二载的年谱与页码"),
        ("claim-chun-wang-time-758", "source-dufu-nianpu-candidate", "待人工核对：系年于至德元载的年谱与页码"),
        ("claim-bg-scene", "source-dufu-nianpu-candidate", "待人工核对：解诗依据（注本/研究）"),
        ("claim-bg-city", "source-anshi-candidate", "待人工核对：城况记载卷次"),
        ("claim-bg-world", "source-anshi-candidate", "待人工核对：战事时长与交通阻断记载"),
        ("claim-bg-person", "source-dufu-zhuan-candidate", "待人工核对：本传相关原文"),
    ]:
        citations[(claim_id, source_id)] = {"claim_id": claim_id, "source_id": source_id,
                                            "locator": locator, "evidence_excerpt": None}

    backgrounds = {}
    for bid, layer, body, audience, claim in [
        ("bg-chun-wang-scene", "SCENE",
         "山河还在，城里的草木在春天长得很深。",
         "PRIMARY", "claim-bg-scene"),
        ("bg-chun-wang-city", "CITY",
         "叛军攻下长安之后，杜甫被困在这座城里。",
         "JUNIOR", "claim-bg-city"),
        ("bg-chun-wang-world", "WORLD",
         "诗里说“烽火连三月，家书抵万金”：战火不停，一封家信比万金还难得。",
         "SENIOR", "claim-bg-world"),
        ("bg-chun-wang-person", "PERSON",
         "他被困在长安，家人留在鄜州。",
         "JUNIOR", "claim-bg-person"),
    ]:
        backgrounds[bid] = {"id": bid, "work_id": WORK_ID, "layer": layer, "audience": audience,
                            "body_text": body, "claim_id": claim}

    background_lines = [
        ("bg-chun-wang-scene", 1), ("bg-chun-wang-scene", 2),
        ("bg-chun-wang-city", 1), ("bg-chun-wang-city", 2),
        ("bg-chun-wang-world", 5), ("bg-chun-wang-world", 6),
        ("bg-chun-wang-person", 7), ("bg-chun-wang-person", 8),
    ]
    background_line_rows = [{"background_id": b, "version_id": VERSION_ID, "line_seq": s} for b, s in background_lines]

    annotations: dict[str, dict[str, Any]] = {}
    if include_v004_annotations:
        for ann_id, seq, aud, text, claim_id, claim_key, claim_text in [
            ("ann-chun-wang-shanhe", 1, "PRIMARY", "山河：山和河，指大地山川。",
             "claim-ann-shanhe", "note.word.1", "山河：山和河，指大地山川。"),
            ("ann-chun-wang-fenghuo", 5, "JUNIOR", "烽火：战火，这里指战事。",
             "claim-ann-fenghuo", "note.word.5", "烽火：战火，借指战事。"),
        ]:
            claims[claim_id] = _claim(claim_id, WORK_ID, claim_key, claim_text, "INTERPRETATION", "LIKELY")
            citations[(claim_id, "source-dufu-nianpu-candidate")] = {
                "claim_id": claim_id, "source_id": "source-dufu-nianpu-candidate",
                "locator": "待指定注本与页码", "evidence_excerpt": None}
            annotations[ann_id] = {"id": ann_id, "version_id": VERSION_ID, "line_seq": seq,
                                   "annotation_kind": "WORD", "audience": aud, "content": text,
                                   "claim_id": claim_id}

    coverage_rows = [
        {"id": "cov-work-755-760", "entity_type": "WORK", "from_year": 755, "to_year": 760,
         "coverage_kind": "PARTIAL", "status": "PUBLISHED",
         "note": "当前只录入极小样本；空白只代表尚未覆盖，不代表这段时间没有作品。"},
        {"id": "cov-person-700-780", "entity_type": "PERSON", "from_year": 700, "to_year": 780,
         "coverage_kind": "PARTIAL", "status": "PUBLISHED", "note": "唐代诗人只录入个位数。"},
        {"id": "cov-event-750-770", "entity_type": "EVENT", "from_year": 750, "to_year": 770,
         "coverage_kind": "PLANNED", "status": "DRAFT", "note": "事件层待补：战事、灾异、迁转、科举等。"},
    ]

    return {
        "contents": contents, "works": works, "versions": versions, "lines": lines,
        "sources": sources, "claims": claims, "citations": citations,
        "backgrounds": backgrounds, "background_lines": background_line_rows,
        "annotations": annotations, "coverage_rows": coverage_rows,
    }
