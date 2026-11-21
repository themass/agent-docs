#!/usr/bin/env node
/**
 * Zero-dependency build. Node's own type stripper turns the shared TypeScript kernel and the Web
 * platform layer into browser ESM (this also proves they use erasable syntax only, so a WebView shell
 * can run them without a bundler).
 *
 *   node build.mjs          runtime -> dist/runtime, dist/platform-web        (what `make student-dev` needs)
 *   node build.mjs --web    also assemble dist/web/ : a self-contained static folder for any host,
 *                           and the folder a Capacitor shell points `webDir` at.
 *
 * Upgrade trigger to Vite (see design/architecture.md 4.1): a dependency that needs bundling (Live2D, pixi),
 * or ~15+ views. Until then there is no node_modules to audit.
 */
import { stripTypeScriptTypes } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync, readdirSync, cpSync, rmSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = fileURLToPath(new URL('.', import.meta.url));
const runtimeRoot = join(here, '..', 'runtime');

function strip(srcDir, outDir) {
  mkdirSync(outDir, { recursive: true });
  let n = 0;
  for (const file of readdirSync(srcDir).filter(f => f.endsWith('.ts'))) {
    const js = stripTypeScriptTypes(readFileSync(join(srcDir, file), 'utf8'), { mode: 'strip' })
      .replace(/(from\s+['"])(\.\.?\/[^'"]+)\.ts(['"])/g, '$1$2.js$3')
      .replace(/(import\(['"])(\.\.?\/[^'"]+)\.ts(['"]\))/g, '$1$2.js$3');
    writeFileSync(join(outDir, file.replace(/\.ts$/, '.js')), js);
    n++;
  }
  return n;
}

const out = join(here, 'dist');
const a = strip(join(runtimeRoot, 'scene-runtime', 'src'), join(out, 'runtime'));
const b = strip(join(runtimeRoot, 'platform-web', 'src'), join(out, 'platform-web'));

// src/kernel/ is generated from the same source as dist/runtime, for one reason only: source files must
// never import a build output (architecture rule A1). Importing ../dist/... meant "you cannot read or edit
// src/ until you have run a build", and it made the IDE unable to resolve anything. Both copies come from
// runtime/scene-runtime/src, so they cannot disagree. Generated, never edited, not committed.
const kernel = join(here, 'src', 'kernel');
rmSync(kernel, { recursive: true, force: true });
const c = strip(join(runtimeRoot, 'scene-runtime', 'src'), kernel);
const webPlatform = join(here, 'src', 'platform-web');
rmSync(webPlatform, { recursive: true, force: true });
strip(join(runtimeRoot, 'platform-web', 'src'), webPlatform);
console.log(`refreshed src/kernel + src/platform-web from runtime/ (${c} files; generated, do not edit)`);
// platform-web imports its types from the kernel package name; those are type-only and already erased.
console.log(`built ${a} kernel + ${b} platform-web modules -> dist/ (no bundler, no deps)`);

if (process.argv.includes('--web')) {
  const web = join(out, 'web');
  rmSync(web, { recursive: true, force: true });
  mkdirSync(web, { recursive: true });
  for (const f of ['index.html', 'sw.js']) if (existsSync(join(here, f))) cpSync(join(here, f), join(web, f));
  for (const d of ['src', 'public']) cpSync(join(here, d), join(web, d), { recursive: true });
  mkdirSync(join(web, 'dist'), { recursive: true });
  cpSync(join(out, 'runtime'), join(web, 'dist', 'runtime'), { recursive: true });
  cpSync(join(out, 'platform-web'), join(web, 'dist', 'platform-web'), { recursive: true });
  console.log('assembled dist/web (point Capacitor webDir here; set public/runtime-config.js for the shell)');
}
