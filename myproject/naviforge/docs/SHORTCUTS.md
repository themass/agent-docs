# NaviForge 快捷键（0.1.2）

权威定义：`apps/extension/src/lib/toolkit-shortcuts.ts`。

在 **普通 http(s) 网页** 上使用，Chrome 窗口在前台。Mac 上必须按住 **Option + Shift**，不要只按 Option：只按 Option 会打出字符（⌥S → ß），Chrome 不会把按键交给扩展。

| 按键 (Mac) | 命令 | 功能 | 安装/更新后默认 |
|------------|------|------|-----------------|
| ⌥⇧N | `nf-open-toolkit` | 网页内工具浮层 | ✅ |
| ⌥⇧A | `nf-capture-visible` | 可见区域截图 | ✅ |
| ⌥⇧S | `nf-capture-full` | 全页截图 | ✅ |
| ⌘⇧S | `nf-screenshot-studio` | 区域截图工作室 | ✅ |
| ⌥⇧T | `nf-translate` | 就地翻译 | 需在 chrome://extensions/shortcuts 绑定 |

0.1.1 的 `⌥N` / `⌥A` / `⌥S` 在 Mac 上经常完全不触发。0.1.2 换了命令 id，更新后 Chrome 会重新登记 `⌥⇧` 默认键。若快捷键页里仍是空的，手动设成 Option+Shift+字母。
