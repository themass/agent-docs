-- READ-ONLY. "What still stands between 《春望》 and a publishable scene bundle?"
-- Everything is SELECT. Run: mysql -h ... -D vpn --default-character-set=utf8mb4 -t < gap-report.sql
-- 1. every base id the 春望 script references, with its real publication state
SELECT x.ref_id, COALESCE(c.entity_type,'(not a content row)') AS entity_type,
       COALESCE(c.title,'—') AS title, COALESCE(c.status,'MISSING') AS status
FROM (
  SELECT 'work-chun-wang' AS ref_id UNION ALL SELECT 'text-chun-wang-v1'
  UNION ALL SELECT 'person-du-fu' UNION ALL SELECT 'place-chang-an'
  UNION ALL SELECT 'bg-chun-wang-scene' UNION ALL SELECT 'bg-chun-wang-city'
  UNION ALL SELECT 'bg-chun-wang-world' UNION ALL SELECT 'bg-chun-wang-person'
  UNION ALL SELECT 'event-anshi-rebellion' UNION ALL SELECT 'event-chang-an-capture'
  UNION ALL SELECT 'exp-du-fu-chang-an-757' UNION ALL SELECT 'theme-anshi-rebellion'
) x LEFT JOIN poetry_content c ON c.id = x.ref_id ORDER BY status, ref_id;

-- 2. text: which version actually exists, and how many lines it has
SELECT v.id AS version_id, v.version_code, v.status, v.source_id,
       (SELECT COUNT(*) FROM poetry_text_line l WHERE l.version_id = v.id) AS line_count
FROM poetry_text_version v WHERE v.work_id = 'work-chun-wang';

-- 3. annotations: the base has none yet for 春望 (script needs them for 字词/意象)
SELECT a.id, a.version_id, a.line_seq, a.annotation_kind, a.audience, a.claim_id
FROM poetry_annotation a JOIN poetry_text_version v ON v.id = a.version_id
WHERE v.work_id = 'work-chun-wang';

-- 4. the real blocker: every claim behind 春望, is it checkable at all?
SELECT cl.id AS claim_id, cl.subject_id, cl.claim_kind, cl.certainty, cl.status,
       (SELECT COUNT(*) FROM poetry_citation ci WHERE ci.claim_id = cl.id) AS citations,
       (SELECT COUNT(*) FROM poetry_citation ci JOIN poetry_source s ON s.id = ci.source_id
         WHERE ci.claim_id = cl.id AND s.verification_status = 'VERIFIED'
           AND TRIM(ci.locator) NOT IN ('','待核查','待人工','未核对','TBD')) AS checkable_citations
FROM poetry_claim cl
WHERE cl.id LIKE 'claim-%' ORDER BY checkable_citations, cl.id;

-- 5. sources: how many are actually verified (this gates every claim above)
SELECT verification_status, COUNT(*) AS n FROM poetry_source GROUP BY verification_status;

-- 6. background -> line links (rule R11: background that explains no line is pile-up)
SELECT b.id AS background_id, b.layer,
       (SELECT COUNT(*) FROM poetry_background_line bl WHERE bl.background_id = b.id) AS linked_lines,
       c.status
FROM poetry_background b LEFT JOIN poetry_content c ON c.id = b.id
WHERE b.work_id = 'work-chun-wang' ORDER BY b.layer;

-- 7. coverage declared as data (rule R5 needs this to exist, not a string in code)
SELECT id, entity_type, from_year, to_year, coverage_kind, status FROM poetry_coverage;
