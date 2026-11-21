#!/usr/bin/env node
/**
 * 枚举比对：contracts/vocabulary.json（唯一来源）与各处定义是否逐项一致。
 *   node check-vocabulary.mjs <platform-root> [vvv-poetry-root]
 * 只读，不改文件。任何 DIFFERS 退出码为 1；Java 仓库不可达时该项为 SKIPPED（不算通过，也不拦截）。
 * 由 check-copies.sh 调用。
 */
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const [, , platformRoot, javaRoot] = process.argv;
if (!platformRoot) { console.error('usage: check-vocabulary.mjs <platform-root> [vvv-poetry-root]'); process.exit(2); }
const P = (...p) => join(platformRoot, ...p);

const vocab = JSON.parse(readFileSync(P('content-agent/pipeline/contracts/vocabulary.json'), 'utf8'));
const quoted = s => [...s.matchAll(/'([^']+)'|"([^"]+)"/g)].map(m => m[1] ?? m[2]);
const sameSet = (a, b) => a && b && a.length === b.length && [...a].sort().join('|') === [...b].sort().join('|');

const rows = [];
const check = (label, actual, expected) =>
  rows.push(actual === null ? { label, status: 'DIFFERS', detail: '找不到定义（正则未命中，需要同步检查脚本）' }
    : sameSet(actual, expected) ? { label, status: 'same' }
    : { label, status: 'DIFFERS', detail: `实际 [${actual.join(', ')}]，词表 [${expected.join(', ')}]` });

/* 1. 契约 schema（两份副本由 check-copies.sh 另行保证字节一致） */
const schema = JSON.parse(readFileSync(P('content-agent/pipeline/contracts/bundle.schema.json'), 'utf8'));
const assetProps = schema.properties.assets.additionalProperties.properties;
check('bundle.schema assets.kind', assetProps.kind.enum, vocab.asset_kind);
check('bundle.schema assets.level', assetProps.level.enum, vocab.media_level);

/* 2. scene-runtime TypeScript（2026-11-11 起只有一份：student-app/runtime/scene-runtime） */
const ts = readFileSync(P('student-app/runtime/scene-runtime/src/bundle.ts'), 'utf8');
const tsType = name => { const m = ts.match(new RegExp(`export type ${name} = ([^;]+);`)); return m ? quoted(m[1]) : null; };
check('bundle.ts MediaLevel', tsType('MediaLevel'), vocab.media_level);
check('bundle.ts ClaimKind', tsType('ClaimKind'), vocab.claim_kind);
check('bundle.ts StepId', tsType('StepId'), vocab.step);
check('bundle.ts LayerId', tsType('LayerId'), vocab.layer);
const kindUnion = ts.match(/kind:\s*([^;]*'illustration'[^;]*);/);
check('bundle.ts AssetSpec.kind', kindUnion ? quoted(kindUnion[1]) : null, vocab.asset_kind);
const degrade = readFileSync(P('student-app/runtime/scene-runtime/src/degrade.ts'), 'utf8');
const order = degrade.match(/export const ORDER: MediaLevel\[\] = \[([^\]]*)\]/);
check('degrade.ts ORDER', order ? quoted(order[1]) : null, vocab.media_level);

/* 2b. 学生端 agent 的 Python 枚举（models.py）。它自己声明了一份 Literal，与词表是重复定义；
   今天一致，但没有任何东西防止它漂移——所以在这里比对。 */
const py = readFileSync(P('student-app/agent/src/student_agent/models.py'), 'utf8');
const pyLit = name => {
  const m = py.match(new RegExp(`^${name} = Literal\\[([^\\]]+)\\]`, 'm'));
  return m ? m[1].split(',').map(x => x.trim().replace(/^["']|["']$/g, '')) : null;
};
check('models.py Step', pyLit('Step'), vocab.step);
check('models.py Layer', pyLit('Layer'), vocab.layer);

/* 3. 编译规则（scene-validator） */
const rules = readFileSync(P('content-agent/pipeline/tools/scene-validator/rules.mjs'), 'utf8');
const ruleArr = name => { const m = rules.match(new RegExp(`const ${name} = \\[([^\\]]*)\\]`)); return m ? quoted(m[1]) : null; };
check('rules.mjs KINDS (claim)', ruleArr('KINDS'), vocab.claim_kind);
check('rules.mjs LEVELS', ruleArr('LEVELS'), vocab.media_level);
check('rules.mjs STEPS', ruleArr('STEPS'), vocab.step);
check('rules.mjs LAYERS', ruleArr('LAYERS'), vocab.layer);

/* 4. Java 后端（vvv-poetry）：只读对照 */
const javaFile = javaRoot && join(javaRoot, 'src/main/java/com/timeline/poetry/service/PoetryMediaService.java');
if (javaFile && existsSync(javaFile)) {
  const java = readFileSync(javaFile, 'utf8');
  const jl = name => { const m = java.match(new RegExp(`${name}\\s*=\\s*List\\.of\\(([^)]*)\\)`)); return m ? quoted(m[1]) : null; };
  check('Java PoetryMediaService.KINDS', jl('KINDS'), vocab.asset_kind);
  check('Java PoetryMediaService.LEVELS', jl('LEVELS'), vocab.media_level);
} else {
  rows.push({ label: 'Java PoetryMediaService', status: 'SKIPPED', detail: `未找到 vvv-poetry（${javaRoot || '未指定'}）；设 VVV_POETRY 后重跑` });
}

for (const r of rows) console.log(`${r.status.padEnd(8)} ${r.label}${r.detail ? `\n           ${r.detail}` : ''}`);
process.exit(rows.some(r => r.status === 'DIFFERS') ? 1 : 0);
