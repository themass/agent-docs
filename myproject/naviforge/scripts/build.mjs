#!/usr/bin/env node
/**
 * NaviForge extension build entrypoint (run from repo root).
 *
 *   node scripts/build.mjs dev   — development build → load chrome-mv3-dev
 *   node scripts/build.mjs prod  — production build → load chrome-mv3
 *   node scripts/build.mjs zip   — prod build + store zip (same as release)
 *
 * npm: npm run dev | prod | zip
 */
import { spawnSync } from 'node:child_process'
import { existsSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const extDir = join(root, 'apps/extension')
const distDir = join(extDir, 'dist')

const mode = process.argv[2]
if (!mode) {
  console.error('Usage: node scripts/build.mjs <dev|prod|zip>')
  process.exit(1)
}

function run(label, cmd, args, cwd = root) {
  console.log(`\n→ ${label}: ${cmd} ${args.join(' ')}`)
  const r = spawnSync(cmd, args, { stdio: 'inherit', cwd, shell: false })
  if (r.status !== 0) process.exit(r.status ?? 1)
}

function prepWorkspaceBuilds() {
  run('shared', 'npm', ['run', 'build', '-w', '@naviforge/shared'])
}

function wxtBuild(wxtArgs) {
  run('extension', 'npx', ['wxt', 'build', ...wxtArgs], extDir)
}

function printLoadHint(folder) {
  console.log('\nChrome → 扩展程序 → 开发者模式 → 加载已解压的扩展程序:')
  console.log(`  ${join(distDir, folder)}`)
}

function printZipPaths() {
  if (!existsSync(distDir)) return
  const zips = readdirSync(distDir).filter((f) => f.endsWith('.zip')).sort()
  if (!zips.length) return
  console.log('\nUpload to Chrome Web Store:')
  for (const z of zips) console.log(`  ${join(distDir, z)}`)
}

switch (mode) {
  case 'dev':
    prepWorkspaceBuilds()
    wxtBuild(['-m', 'development'])
    printLoadHint('chrome-mv3-dev')
    break
  case 'prod':
    prepWorkspaceBuilds()
    wxtBuild([])
    printLoadHint('chrome-mv3')
    break
  case 'zip':
    prepWorkspaceBuilds()
    wxtBuild([])
    run('zip', 'npm', ['run', 'zip', '-w', '@naviforge/extension'])
    printZipPaths()
    console.log('\nBefore upload: npm run check && docs/STORE_COMPLIANCE.md')
    break
  default:
    console.error(`Unknown mode "${mode}". Use: dev | prod | zip`)
    process.exit(1)
}
