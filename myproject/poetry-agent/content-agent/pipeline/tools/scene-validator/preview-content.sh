#!/usr/bin/env bash
# READ-ONLY preview feed for the local web preview. DRAFT content is exported for INTERNAL preview
# only; the page must label it as draft, because the student path is fail-closed on PUBLISHED.
#   usage: ./preview-content.sh > preview.tsv && node tools/scene-validator/export-preview.mjs preview.tsv apps/web/public/preview.json
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/db-conn.sh"
q "SELECT 'line', CONCAT(line_seq,'#',content) FROM poetry_text_line WHERE version_id='text-chun-wang-draft'
   UNION ALL SELECT 'annotation', CONCAT(line_seq,'#',annotation_kind,'#',audience,'#',id,'#',content) FROM poetry_annotation WHERE version_id='text-chun-wang-draft'
   UNION ALL SELECT 'background', CONCAT(layer,'#',id,'#',COALESCE(body_text,'')) FROM poetry_background WHERE work_id='work-chun-wang'
   UNION ALL SELECT 'status', CONCAT('content:', id, '#', status) FROM poetry_content WHERE id IN ('work-chun-wang','person-du-fu','place-chang-an','event-anshi-rebellion','event-chang-an-capture','exp-du-fu-chang-an-757','theme-anshi-rebellion')
   UNION ALL SELECT 'status', CONCAT('text_version:', id, '#', status) FROM poetry_text_version WHERE id='text-chun-wang-draft'
   UNION ALL SELECT 'coverage', CONCAT(id,'#',entity_type,'#',from_year,'#',to_year,'#',coverage_kind,'#',status) FROM poetry_coverage
   UNION ALL SELECT 'relation', CONCAT(background_id,'#',version_id,'#',line_seq) FROM poetry_background_line"
