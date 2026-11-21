#!/usr/bin/env node
/**
 * 把「壳的运行时配置 + 注入适配层」写进 make student-web 的输出里(只写构建产物,不碰前端源码)。
 *
 *   dist/web/public/runtime-config.js  =  window.STUDENT_APP_CONFIG = {...}  +  native-adapter.js
 *
 * 前端 build.mjs 本来就把 runtime-config.js 定义成「部署时由宿主替换的文件」,这里照做。
 * 接口地址来自环境变量,没有就用占位(并明确告警),不在仓库里写死任何真实域名或密钥:
 *   STUDENT_API_BASE   例 https://api.example.org/api/student/v1
 *   STUDENT_AGENT_BASE 例 https://api.example.org/agent/v1
 *   STUDENT_ASSET_BASE 可空
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const shellRoot = resolve(here, '..');
const webDir = resolve(shellRoot, '../frontend/dist/web');
const target = join(webDir, 'public', 'runtime-config.js');

if (!existsSync(join(webDir, 'index.html'))) {
  console.error(`缺少 ${webDir}/index.html:先在平台根目录执行 make student-web`);
  process.exit(1);
}

const PLACEHOLDER = 'https://api.invalid';
const apiBase = process.env.STUDENT_API_BASE || `${PLACEHOLDER}/api/student/v1`;
const agentBase = process.env.STUDENT_AGENT_BASE || `${PLACEHOLDER}/agent/v1`;
const assetBase = process.env.STUDENT_ASSET_BASE || '';

for (const [name, v] of [['STUDENT_API_BASE', apiBase], ['STUDENT_AGENT_BASE', agentBase]]) {
  if (v.startsWith(PLACEHOLDER)) console.warn(`警告:${name} 未设置,写入占位地址 ${PLACEHOLDER}(App 里所有接口会失败并走离线/文字降级)`);
  if (!v.startsWith('https://')) console.warn(`警告:${name}=${v} 不是 https。商店包不允许明文,仅本地联调可用。`);
}

const adapter = readFileSync(join(shellRoot, 'src', 'native-adapter.js'), 'utf8');
const config = `window.STUDENT_APP_CONFIG = ${JSON.stringify({ apiBase, agentBase, assetBase }, null, 2)};\n`;
writeFileSync(target, `// 由 student-app/shell/scripts/prepare-web.mjs 生成(构建产物,勿手改)。\n${config}\n${adapter}`);
console.log(`已写入 ${target}(apiBase=${apiBase})`);
