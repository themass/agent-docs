import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { DEFAULT_COLLAPSE_CHARS, shouldCollapseText } from '../components/chat/collapsible-text.js'
import { extractWorkspacePaths, workspacePathFromBody } from '../components/chat/workspace-path-link.js'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

const css = readFileSync(resolve(root, 'entrypoints/options/styles.css'), 'utf8')
assert.match(css, /\.session-role\s*\{[^}]*font:\s*700 17px/, 'audit role titles stay large')
assert.match(css, /\.file-row\s*\{[^}]*padding:\s*7px 12px/, 'file rows stay compact')
assert.match(css, /\.file-name\s*\{[^}]*white-space:\s*nowrap/, 'filenames do not wrap and inflate rows')
assert.match(css, /\.data-list-head,\s*\.data-list-row\s*\{[^}]*padding:\s*8px 12px/, 'toolkit rows stay compact')
assert.doesNotMatch(css, /\.file-row\s*\{[^}]*padding:\s*20px/, 'old tall file cards must not return')

assert.match(css, /\.file-list-scroll\s*\{[^}]*overflow-y:\s*auto/, 'shot/log lists scroll instead of growing the page')
assert.match(css, /\.tabs\s*\{[^}]*flex-wrap:\s*wrap/, 'six workspace tabs can wrap')

const workspace = readFileSync(resolve(root, 'entrypoints/options/workspace-panel.tsx'), 'utf8')
assert.ok(workspace.includes("from './tabs'"), 'workspace reuses the automation Tabs')
assert.ok(workspace.includes('options.workspace.tabs.logs'), 'disk JSONL tab uses i18n logs label')
assert.ok(workspace.includes('const LATEST_SHOTS = 50'), 'shots tab caps at latest 50')
assert.ok(workspace.includes('file-list'), 'disk files stay on compact file-list')
assert.ok(workspace.includes('file-list-scroll'), 'long shot/log lists are scrollable')
assert.ok(workspace.includes('formatWorkspaceMtime'), 'file lists show mtime')
assert.ok(workspace.includes('fileMetaLabel'), 'audio rows share the same time+size meta')

const app = readFileSync(resolve(root, 'entrypoints/options/App.tsx'), 'utf8')
assert.ok(app.includes('options.automation.tabs.sessions'), 'automation storage chats tab uses i18n key')
assert.ok(app.includes("from './tabs'"), 'automation uses the shared Tabs')
assert.doesNotMatch(app, /function Tabs/, 'Tabs is not duplicated in App')
assert.match(app, /function refreshAutomation/, 'automation page can reload lists')
assert.match(app, /options\.common\.buttons\.refresh/, 'automation page uses refresh i18n key')

const plane = readFileSync(resolve(root, 'lib/chrome-dom-plane.ts'), 'utf8')
assert.ok(plane.includes("send<{ success: boolean }>(tabId, 'hide_capture_chrome')"), 'screenshot hides chrome')
assert.ok(plane.includes("send(tabId, 'restore_capture_chrome')"), 'screenshot restores chrome')
assert.ok(
  /async screenshot\([\s\S]*tabs\.update\(tabId, \{ active: true \}\)[\s\S]*captureVisibleTabPng/.test(plane),
  'visible capture focuses the target tab before captureVisibleTab'
)
assert.ok(plane.includes('MIN_CAPTURE_GAP_MS'), 'visible captures are spaced to stay under Chrome quota')
assert.ok(plane.includes('friendlyCaptureError'), 'quota errors are rewritten for humans')
assert.ok(plane.includes('screenshotFullPage'), 'full-page uses the same plane')
assert.ok(
  /async screenshotFullPage[\s\S]*hide_capture_chrome[\s\S]*captureFullPageTab/.test(plane),
  'full-page capture also hides chrome'
)

const translate = readFileSync(resolve(root, 'lib/page-translate.ts'), 'utf8')
assert.ok(translate.includes('naviforge-translate-hud'), 'translate HUD is injected on the target tab')

const ocr = readFileSync(resolve(root, 'lib/vision-ocr.ts'), 'utf8')
assert.ok(ocr.includes('sendOcrHud'), 'OCR posts HUD to the target tab')
assert.ok(ocr.includes("action: 'ocr_hud'"), 'OCR HUD uses PAGE_CONTROL ocr_hud')

const background = readFileSync(resolve(root, 'entrypoints/background.ts'), 'utf8')
assert.ok(background.includes('openWorkspaceNotice'), 'screenshot writes a workspace banner')
const captureFn = background.slice(
  background.indexOf('async function handleToolkitCapture'),
  background.indexOf('export default defineBackground')
)
assert.doesNotMatch(
  captureFn,
  /openOptionsPage/,
  'popup/shortcut capture stays on the page instead of opening the control center'
)
assert.match(
  background,
  /type === 'TOOLKIT_CAPTURE'[\s\S]{0,200}sendResponse\(\{ ok: true, started: true \}\)/,
  'popup capture acks immediately so the menu can close'
)
assert.match(background, /WORKSPACE_REVEAL/, 'toast can open the saved file in Finder')
assert.match(background, /describeSavedShot/, 'capture toast includes the save location')
assert.match(captureFn, /正在截图/, 'capture tells the user it started before Chrome APIs run')
assert.match(background, /captureInFlight/, 'a second click does not fire another captureVisibleTab')

const popup = readFileSync(resolve(root, 'entrypoints/popup/PopupApp.tsx'), 'utf8')
assert.doesNotMatch(popup, /完成后打开工作区/, 'popup no longer claims capture waits to open workspace')
assert.match(popup, /popup\.footerHost/, 'popup footer is catalogued, not hardcoded')
assert.match(popup, /TOOLKIT_CATALOG/, 'popup lists the full toolkit catalog')
assert.match(popup, /runPopupTool/, 'popup runs tools via shared runner')
assert.match(popup, /snapshotCurrentWebTab/, 'popup reads the page under the menu')

const popupActions = readFileSync(resolve(root, 'lib/toolkit-popup-actions.ts'), 'utf8')
assert.match(popupActions, /tabId/, 'popup runner passes the current page tab id with tools')

const popupCopy = readFileSync(resolve(root, 'i18n/catalogs/en.ts'), 'utf8')
assert.match(popupCopy, /toast appears at the top-right/, 'English popup tells the user to watch the page toast')
const popupZh = readFileSync(resolve(root, 'i18n/catalogs/zh-CN.ts'), 'utf8')
assert.match(popupZh, /页面右上角会提示/, 'Chinese popup tells the user to watch the page toast')

const toolkitActions = readFileSync(resolve(root, 'lib/toolkit-actions.ts'), 'utf8')
assert.ok(toolkitActions.includes('export async function snapshotCurrentWebTab'), 'current-page snapshot exists')
assert.match(
  toolkitActions,
  /export async function resolveToolkitTab\(explicitTabId\?/,
  'resolveToolkitTab honors the popup tab id'
)
const captureFns = toolkitActions.slice(toolkitActions.indexOf('export async function toolkitCaptureVisible'))
assert.doesNotMatch(
  captureFns,
  /downloadFallback\([^)]+true\)/,
  'popup capture must not block on a Save As dialog'
)

const launch = readFileSync(resolve(root, 'lib/surface-launch.ts'), 'utf8')
assert.match(launch, /pinCurrentWebTab/, 'opening toolkit from the menu pins the current page')
assert.match(
  launch,
  /export async function openWorkspaceTab[\s\S]{0,200}pinCurrentWebTab/,
  'opening the workspace pins the page under the menu'
)

const toolkitPanel = readFileSync(resolve(root, 'entrypoints/options/toolkit-panel.tsx'), 'utf8')
assert.doesNotMatch(
  toolkitPanel,
  /chrome\.tabs\.onActivated/,
  'toolkit bound tab must not follow every tab you click'
)
assert.match(background, /command === 'open-toolkit'[\s\S]{0,120}openPageToolList/, 'open-toolkit opens page tool list overlay')
assert.match(
  background,
  /command === 'toolkit-translate'[\s\S]{0,120}lastFocusedWindow/,
  '⌥T translates the last focused page, not a service-worker window'
)

const agentBind = readFileSync(resolve(root, 'chat/workspace-tab-control.ts'), 'utf8')
assert.match(
  agentBind.slice(agentBind.indexOf('async function bindActiveTab')),
  /resolveToolkitTab/,
  'Agent falls back to the pinned current page, not a random recent tab'
)

const localWorkspace = readFileSync(resolve(root, 'lib/local-workspace.ts'), 'utf8')
assert.match(localWorkspace, /ENOENT\|no such file or directory/, 'missing dirs list as empty')
assert.ok(localWorkspace.includes('loadWorkspaceFileLists'), 'workspace tabs isolate list failures')
assert.ok(
  localWorkspace.includes('本机助手未连接，无法列出磁盘上的文件'),
  'offline empty copy is not “还没有截图”'
)
assert.match(localWorkspace, /AbortSignal\.timeout/, 'Host fetch cannot hang the capture path')

const content = readFileSync(resolve(root, 'entrypoints/content.ts'), 'utf8')
const pageControlRegistry = readFileSync(resolve(root, 'content/page-control-registry.ts'), 'utf8')
const pageControlDispatch = `${content}\n${pageControlRegistry}`
assert.ok(pageControlDispatch.includes("case 'ocr_hud'"), 'content script paints OCR HUD')
assert.ok(pageControlDispatch.includes("case 'hide_capture_chrome'"), 'content script implements hide')
assert.ok(content.includes('playwright-highlight-container'), 'hides numbered highlights')
assert.ok(content.includes('naviforge-mark-layer'), 'hides TOP marks')
assert.ok(content.includes('naviforge-lock-hint'), 'hides lock hint')
assert.ok(content.includes("behavior: 'auto'"), 'agent scroll is instant, not smooth')
assert.ok(content.includes('largestScrollableElement'), 'falls back to inner overflow containers')

const collapse = readFileSync(resolve(root, 'components/chat/collapsible-text.tsx'), 'utf8')
const block = collapse.slice(collapse.indexOf('export function CollapsibleBlock'))
const toggleAt = block.indexOf('<CollapseToggle')
const childrenAt = block.indexOf('{children(visible)}')
assert.ok(toggleAt >= 0 && toggleAt < childrenAt, 'fold/expand control sits above the message body')

assert.equal(shouldCollapseText('x'.repeat(DEFAULT_COLLAPSE_CHARS + 1)), true)
assert.deepEqual(extractWorkspacePaths('截图已保存 shots/a.png（相对工作区）'), ['shots/a.png'])
assert.deepEqual(
  extractWorkspacePaths('截图文件：shots/20260814T114916Z-visible-a6be33.png'),
  ['shots/20260814T114916Z-visible-a6be33.png']
)
assert.deepEqual(extractWorkspacePaths('{"path":"shots/foo.png"}'), ['shots/foo.png'])
assert.equal(workspacePathFromBody('shots/20260814.png（相对工作区）'), 'shots/20260814.png')
assert.equal(workspacePathFromBody('hello'), null)
const stepCard = readFileSync(resolve(root, 'components/chat/step-card.tsx'), 'utf8')
assert.ok(stepCard.includes('WorkspacePathActions'), 'result card offers open buttons for workspace files')

const composer = readFileSync(resolve(root, 'components/chat/composer.tsx'), 'utf8')
assert.ok(composer.includes('Enter 发送'), 'composer hint says Enter sends')
assert.doesNotMatch(composer, /Enter 换行 · Alt\+Enter/, 'old Alt+Enter send hint is gone')

const wxtConfig = readFileSync(resolve(root, '../wxt.config.ts'), 'utf8')
const permissionBlock = wxtConfig.match(/permissions:\s*\[([\s\S]*?)\],/)?.[1] ?? ''
assert.doesNotMatch(permissionBlock, /['"]audioCapture['"]|['"]videoCapture['"]/, 'manifest permissions must not declare packaged-app-only capture')
const shortcutCount = (wxtConfig.match(/suggested_key:/g) ?? []).length
assert.ok(shortcutCount <= 4, `manifest commands allow at most 4 suggested_key (got ${shortcutCount})`)

console.log('regression self-check ok')
