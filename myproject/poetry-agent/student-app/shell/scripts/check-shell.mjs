#!/usr/bin/env node
/**
 * 壳的静态一致性检查。不构建、不联网、不跑测试套件。
 *   1. package.json 依赖全部是确切版本(没有 ^ ~ * latest)
 *   2. capacitor.config.ts 的 webDir 相对路径能落到前端 student-web 的输出位置(目录是否已构建只提示)
 *   3. native/ 下的权限片段没有申请位置、通讯录、相机、广告标识符(AD_ID 只允许出现在 tools:node="remove" 里)
 *   4. 原生插件桩与适配层用的方法名互相对得上
 */
import { readFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const problems = [];
const notes = [];
const fail = m => problems.push(m);

// 1. 依赖固定
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
for (const sect of ['dependencies', 'devDependencies']) {
  for (const [name, v] of Object.entries(pkg[sect] || {})) {
    if (!/^\d+\.\d+\.\d+$/.test(v)) fail(`${sect}.${name}=${v} 不是确切版本`);
  }
}

// 2. webDir
const cfg = readFileSync(join(root, 'capacitor.config.ts'), 'utf8');
const m = cfg.match(/webDir:\s*'([^']+)'/);
if (!m) fail('capacitor.config.ts 里找不到 webDir');
else {
  const webDir = resolve(root, m[1]);
  if (m[1].startsWith('/')) fail('webDir 必须是相对路径');
  if (!webDir.endsWith(join('student-app', 'frontend', 'dist', 'web'))) fail(`webDir 没有指向 student-app/frontend/dist/web:${webDir}`);
  if (!existsSync(join(webDir, 'index.html'))) notes.push(`webDir 还没构建:${webDir}(先 make student-web)`);
}
if (/appId:\s*'([^']+)'/.exec(cfg)?.[1]?.match(/^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$/) == null) fail('appId 格式不合法');

// 3. 权限片段
const walk = d => readdirSync(d).flatMap(f => { const p = join(d, f); return statSync(p).isDirectory() ? walk(p) : [p]; });
const forbidden = [/ACCESS_(FINE|COARSE|BACKGROUND)_LOCATION/, /READ_CONTACTS|WRITE_CONTACTS|GET_ACCOUNTS/, /android\.permission\.CAMERA/, /NSLocation\w*UsageDescription/, /NSContactsUsageDescription/, /NSCameraUsageDescription/, /NSUserTrackingUsageDescription/, /NSPhotoLibrary\w*UsageDescription/];
for (const f of walk(join(root, 'native')).filter(p => /\.(xml|template)$/.test(p))) {
  const text = readFileSync(f, 'utf8').replace(/<!--[\s\S]*?-->/g, '');   // 注释里的说明不算声明
  for (const re of forbidden) if (re.test(text)) fail(`${f.replace(root + '/', '')} 含未成年人 App 不应申请的项:${re}`);
  for (const line of text.split('\n')) {
    if (line.includes('AD_ID') && !line.includes('tools:node="remove"')) fail(`${f.replace(root + '/', '')} 声明了 AD_ID`);
  }
}

// 4. 插件方法名对齐
const kt = readFileSync(join(root, 'native/android-plugin/XuexiNativePlugin.kt'), 'utf8');
const js = readFileSync(join(root, 'src/native-adapter.js'), 'utf8');
const ktMethods = new Set([...kt.matchAll(/fun (\w+)\(call: PluginCall\)/g)].map(x => x[1]));
for (const [, name] of js.matchAll(/Native\.(\w+)\(/g)) {
  if (name !== 'addListener' && !ktMethods.has(name)) fail(`native-adapter.js 调用了 Native.${name},Kotlin 桩里没有`);
}

// 5. 注入被学生端消费(学生端 platform.js 必须读取 XUEXI_NATIVE 并等待 ready)
const platformJs = resolve(root, '../frontend/src/platform.js');
if (!existsSync(platformJs)) fail('找不到 ../frontend/src/platform.js,无法确认注入被消费');
else {
  const pj = readFileSync(platformJs, 'utf8');
  if (!pj.includes('XUEXI_NATIVE')) fail('frontend/src/platform.js 未引用 XUEXI_NATIVE:壳注入没有被消费');
  if (!pj.includes('native?.ready') && !pj.includes('native.ready')) fail('frontend/src/platform.js 未引用 native?.ready / native.ready:ready 没有被等待');
}

for (const n of notes) console.log('提示:', n);
if (problems.length) { for (const p of problems) console.error('✗', p); process.exit(1); }
console.log('shell 静态检查通过');
