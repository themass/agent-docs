#!/usr/bin/env bash
# Read-only export of the base's facts as TSV, for the bundle validator.
#   usage: ./facts-from-db.sh > facts.tsv   then:  node export-facts.mjs facts.tsv facts.json
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/db-conn.sh"

# Everything below is SELECT-only; this script never writes to the base.
q "SELECT 'published', id FROM poetry_content WHERE status='PUBLISHED'
   UNION ALL SELECT 'published', id FROM poetry_text_version WHERE status='PUBLISHED'
   UNION ALL SELECT 'published', id FROM poetry_claim WHERE status='PUBLISHED'
   UNION ALL SELECT 'published', id FROM poetry_coverage WHERE status='PUBLISHED'
   UNION ALL SELECT 'published', a.id FROM poetry_annotation a
     JOIN poetry_text_version v ON v.id=a.version_id WHERE v.status='PUBLISHED'
   UNION ALL SELECT 'draft', id FROM poetry_content WHERE status<>'PUBLISHED'
   UNION ALL SELECT 'draft', id FROM poetry_text_version WHERE status<>'PUBLISHED'
   UNION ALL SELECT 'draft', id FROM poetry_claim WHERE status<>'PUBLISHED'
   UNION ALL SELECT 'draft', a.id FROM poetry_annotation a
     JOIN poetry_text_version v ON v.id=a.version_id WHERE v.status<>'PUBLISHED'
   UNION ALL SELECT 'line', CONCAT(version_id,'#',line_seq) FROM poetry_text_line
   UNION ALL SELECT 'cited_claim', ci.claim_id FROM poetry_citation ci
     JOIN poetry_source s ON s.id=ci.source_id
     WHERE s.verification_status='VERIFIED'
       AND TRIM(ci.locator) NOT IN ('','待核查','待人工','未核对','TBD')
   UNION ALL SELECT 'unknown_date', c.id FROM poetry_content c
     JOIN poetry_claim cl ON cl.subject_id=c.id AND cl.property_key='time.span'
     WHERE cl.certainty IN ('DISPUTED','UNKNOWN') OR c.time_precision='UNKNOWN'
   UNION ALL SELECT 'bg_lines', CONCAT(background_id,'#',COUNT(*)) FROM poetry_background_line
     GROUP BY background_id"
