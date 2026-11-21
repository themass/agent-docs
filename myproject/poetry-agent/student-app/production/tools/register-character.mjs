#!/usr/bin/env node
// 把 published/characters/<id>/ 下已通过 character-check 的角色登记进 registry.json,生成三级降级链:
//   <prefix>-bust (L3 character) -> <prefix>-still (L1 illustration) -> <prefix>-text (L0 subtitle,文字描述)
// 用法: node register-character.mjs <character-dir> --prefix a-dufu [--meaning "..."] [--step meet]
import { writeFileSync, mkdirSync } from 'node:fs';
import { join, resolve, relative } from 'node:path';
import { checkCharacter } from './character-check.mjs';
import { PUBLISHED, describeFiles, fingerprint, loadRegistry, saveRegistry, upsert, checkRegistry } from './lib/registry.mjs';

const args = process.argv.slice(2);
const dir = args.find((a) => !a.startsWith('--'));
const opt = (k, d) => { const i = args.indexOf(`--${k}`); return i >= 0 ? args[i + 1] : d; };
if (!dir || !opt('prefix')) { console.error('usage: node register-character.mjs <character-dir> --prefix a-dufu [--meaning ..] [--step meet]'); process.exit(2); }

const absDir = resolve(dir);
const r = checkCharacter(join(absDir, 'manifest.json'));
if (r.errors.length) { r.errors.forEach((e) => console.error('✗', e)); process.exit(1); }
const m = r.manifest, prefix = opt('prefix'), step = opt('step', 'meet');
const rel = (p) => relative(PUBLISHED, join(absDir, p)).split('\\').join('/');
const meaning = opt('meaning', `让学生见到此时此地的诗人,而不是一个通用古人像(${m.display_name};演绎形象,非画像)`);

const textFile = 'alt.txt';
writeFileSync(join(absDir, textFile), `${m.display_name}\n${m.degrade.text_alt}\n${m.depiction.notice}\n`);

const rights = { origin: m.rights.origin, license: m.rights.license, workflow: m.rights.workflow, human_fix: !!m.rights.human_fix, author: m.rights.author, notes: m.rights.notes };
const ph = { ...m.placeholder, replace_with_task: m.placeholder.replace_with_task };
const used = [...r.files, 'manifest.json'].filter((f, i, a) => a.indexOf(f) === i);
const common = { status: 'published', placeholder: ph, depiction: 'DRAMATIZATION', used_in: [{ step }] };

const textFiles = describeFiles(absDir, [textFile], { [textFile]: { role: 'entry' } });
const stillFiles = describeFiles(absDir, [m.degrade.still.file], { [m.degrade.still.file]: { role: 'entry' } });
const bustFiles = describeFiles(absDir, used).map((f) => ({ ...f, role: f.path.endsWith('manifest.json') ? 'entry' : f.path.endsWith('still.svg') ? 'poster' : 'layer' }));

const reg = loadRegistry();
upsert(reg, { asset_id: `${prefix}-text`, kind: 'subtitle', level: 'L0', uri: rel(textFile), ...fingerprint(textFiles), files: textFiles,
  render: 'text-card', rights, meaning: `角色动画和图都不可用时,仍用文字告诉学生此处有人在场(${m.display_name})`, fallback_asset_id: null, ...common });
upsert(reg, { asset_id: `${prefix}-still`, kind: 'illustration', level: 'L1', uri: rel(m.degrade.still.file), ...fingerprint(stillFiles), files: stillFiles,
  media: { width: m.degrade.still.width, height: m.degrade.still.height }, render: 'still', rights,
  meaning: `角色动画不可用时仍保留“有人在场”(${m.display_name}静帧;演绎形象)`, fallback_asset_id: `${prefix}-text`, ...common });
upsert(reg, { asset_id: `${prefix}-bust`, kind: 'character', level: 'L3', uri: rel('manifest.json'), ...fingerprint(bustFiles), files: bustFiles,
  media: { width: m.canvas.width, height: m.canvas.height, states: Object.keys(m.states), mouth_mode: m.mouth_mode }, render: 'character-svg-layers', rights,
  meaning, fallback_asset_id: `${prefix}-still`, ...common });

const chk = checkRegistry(reg);
if (chk.errors.length) { chk.errors.forEach((e) => console.error('✗', e)); process.exit(1); }
saveRegistry(reg);
console.log(`registered ${prefix}-bust (L3) -> ${prefix}-still (L1) -> ${prefix}-text (L0); registry has ${reg.assets.length} assets`);
