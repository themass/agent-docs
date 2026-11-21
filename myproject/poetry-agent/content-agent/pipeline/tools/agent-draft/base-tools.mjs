#!/usr/bin/env node
/**
 * The read-only tool surface an authoring agent is allowed to touch. Everything here is a SELECT
 * against the base; the guard below refuses anything else, and there is no publish path at all —
 * an agent that cannot publish cannot do damage, which is cheaper than any prompt-level warning.
 */
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const conn = join(here, '..', 'scene-validator', 'db-conn.sh');

export function assertReadOnly(sql) {
  if (/\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT)\b/i.test(sql))
    throw new Error('refused: agent tools are read-only');
  return sql;
}
const q = sql => execFileSync('bash', ['-c', `source '${conn}' && q "${assertReadOnly(sql).replace(/"/g, '\\"')}"`],
  { encoding: 'utf8' }).trim().split('\n').filter(Boolean);

export const tools = {
  content: (id) => q(`SELECT id,entity_type,title,status,time_precision FROM poetry_content WHERE id='${id}'`),
  poemLines: (versionId) => q(`SELECT line_seq,content FROM poetry_text_line WHERE version_id='${versionId}' ORDER BY line_seq`),
  versions: (workId) => q(`SELECT id,version_code,status FROM poetry_text_version WHERE work_id='${workId}'`),
  claims: (subjectId) => q(`SELECT id,claim_kind,certainty,status,
      (SELECT COUNT(*) FROM poetry_citation c WHERE c.claim_id=cl.id) citations,
      (SELECT COUNT(*) FROM poetry_citation c JOIN poetry_source s ON s.id=c.source_id
        WHERE c.claim_id=cl.id AND s.verification_status='VERIFIED') verified_refs
    FROM poetry_claim cl WHERE subject_id='${subjectId}'`),
  backgrounds: (workId) => q(`SELECT id,layer,audience,LEFT(body_text,40) body FROM poetry_background WHERE work_id='${workId}'`),
  bgLineLinks: (workId) => q(`SELECT bl.background_id,bl.line_seq FROM poetry_background_line bl
      JOIN poetry_background b ON b.id=bl.background_id WHERE b.work_id='${workId}'`),
  annotations: (versionId) => q(`SELECT id,line_seq,annotation_kind,LEFT(content,40) body FROM poetry_annotation WHERE version_id='${versionId}'`),
  coverage: () => q(`SELECT id,entity_type,from_year,to_year,coverage_kind,status FROM poetry_coverage`),
};

/** Publish/retract/verify are not tools. Not restricted, not "confirm first" — absent. */
export const FORBIDDEN = ['publish', 'retract', 'verify_source', 'set_verified', 'delete_content'];
export function assertAllowed(toolName) {
  if (FORBIDDEN.some(f => String(toolName).toLowerCase().includes(f)))
    throw new Error(`tool "${toolName}" does not exist for an agent: publishing is a human decision`);
  if (!tools[toolName]) throw new Error(`unknown tool: ${toolName}`);
  return toolName;
}
