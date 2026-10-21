# TECH-DESIGN-SYSTEM：前端设计系统

- **状态**：已确认的 V1 实现约定
- **最后更新**：2026-10-16

本文档是前端视觉层的唯一规范。令牌定义在 `frontend/web/tailwind.config.ts`，组件类定义在
`frontend/web/app/globals.css`。本文解释**为什么这样定**和**什么情况下用哪个**；具体数值以代码为准，
不在此处复制易过期的表格。

## 1. 为什么需要这份规范

重构前的统计结果说明问题不在个别页面，而在缺少约定：

| 现象 | 数量 | 后果 |
|---|---|---|
| 混用的 Tailwind 颜色族 | 18 个 | 同一种语义在不同页面是不同颜色 |
| arbitrary px 字号（`text-[11px]` 等） | 198 处 | 正文落到 10–11px，密集且显旧 |
| `focus-visible` 样式 | 全库 1 处 | 键盘导航几乎不可见 |
| 圆角规格 | 5 种混用 | 卡片与控件没有层级关系 |

结论：**密度、颜色语义、层级必须在令牌层决定，不能在每个文件里各自决定。**

## 2. 字号

标尺带显式 line-height，针对中英混排调过：同字号下中文需要比拉丁更大的行距。

- `micro` — 徽章、计数、字段路径。**不用于正文。**
- `xs` — 元信息、辅助说明、表格单元格。
- `sm` — 次级正文、控件标签。密集界面的主力。
- `base` — 主要正文。凡是用户需要读懂的内容都用它。
- `lg` / `xl` / `2xl` — 卡片标题 / 区块标题 / 页面标题（`PageHeader`）。
- `3xl` / `4xl` — 仅用于单个关键数字（如匹配度大字）。

**禁止** `text-[13px]` 这类 arbitrary 值。需要新尺寸就改标尺，让所有页面一起变。

## 3. 颜色

颜色按**角色**命名，不按色板命名。这样换色只改一处，且代码能表达意图。

| 角色 | 用途 |
|---|---|
| `brand` | 强调色、主操作、当前选中、Agent 身份 |
| `ink` | 文字与中性灰。**`ink-500` 是最浅的可读文字色**；`ink-400` 及更浅只做装饰 |
| `surface` | 容器背景与描边：`DEFAULT` / `sunken` / `muted` / `border` / `border-strong` |
| `success` / `warn` / `danger` | 状态。**只有 50/100/200/600/700/900 六档** |

规则：

1. **不得新增颜色族。** 需要新语义时先问它是不是已有角色之一。
2. 状态色只用于传达状态，不用于装饰。
3. 正文级别的危险文字用 `danger-700` 而非 `600`（对比度）。
4. `ink-900` 实色块只保留给深色浮层（`TokenMeter`）。主操作一律 `brand-600`——
   深色按钮和品牌按钮混用会让人以为是两个产品。
5. **`ink-400` 及更浅的灰不得承载需要阅读的文字。** 它在白底只有 2.83:1、在 `ink-100` 上
   2.48:1，达不到 4.5:1。它的合法用途只有三类：`placeholder:`、`disabled:`、纯装饰图标与分隔线。
   需要阅读的弱化文字（meta 行、辅助说明、计数）一律 `ink-500`（白底 5.52:1，`ink-100` 上 4.84:1）。

## 4. 圆角与层级

圆角是四级阶梯，表达嵌套关系：

- 控件（按钮、输入框、徽章）→ `rounded-md`
- 卡片、气泡 → `rounded-xl`
- 面板、分栏容器、拖拽区 → `rounded-2xl`

层级靠阴影而非描边。`shadow-xs` → `sm` → `card` → `raised` → `panel` → `pop` 是递进关系，
`shadow-brand` 只给主操作。

**不要给所有元素都画 1px 实线边框**——这是旧界面「像后台管理系统」的主要来源。需要分隔时优先
`ring-1 ring-inset`，它不占布局空间，也不会在嵌套时叠成双线。

## 5. 组件类

定义在 `globals.css` 的 `@layer components`。**优先复用，不要手写等价的 class 串。**

| 类 | 何时用 |
|---|---|
| `.card` / `.card-pad` | 默认容器。`card-pad` 是配套内边距 |
| `.card-sunken` | 卡片**内部**的次级分区，比 `.card` 低一层 |
| `.btn` + `.btn-sm\|md\|lg` + `.btn-primary\|primary-emphasis\|secondary\|ghost\|success` | 所有按钮。尺寸与风格必须分别指定 |
| `.field` | 所有 input / textarea / select |
| `.segment` + `.segment-item` + `.segment-item-active` | 少量互斥选项（语言轨、模式、视图切换） |
| `.badge` + 5 个变体 | 静态标签、计数、状态点 |
| `.notice` + `info\|success\|warn\|danger` | 行内状态块，承载一句话解释 |
| `.label-meta` | 成组控件上方的小标题 |
| `.skeleton` | 加载占位 |
| `.scroll-area` | 任何内部滚动容器（细滚动条，不吃布局宽度） |
| `.studio-columns` + `.studio-columns-inner` + `.studio-doc` + `.studio-rail` | 简历第 3 步的文档/控件两列（见 5.1） |
| `.agent-rail-collapsed` + `.agent-rail-label` | 舟卡侧栏收起后的 44px 竖条与竖排标签（见 5.3） |

### 5.1 `.studio-*`：为什么是容器查询，不是 `xl:` 断点

简历第 3 步要同时放一份 A4 文档和一组建议面板。把面板堆在文档上方会**把简历挤出首屏**
（实测距顶 1082px，用户打开这一步看不到自己的简历）。所以文档要有自己一列。

列规则写在 `@container` 而不是 `xl:`，原因是 **studio 与 agent 侧栏之间的分隔条用户可以拖**——
viewport 宽度无法描述这个面板实际有多少空间。实测 1280px viewport 下 `xl:` 方案给出
**402px 的文档列**，比它要展示的简历还窄。

- `.studio-columns` 带 `container-type: inline-size`，阈值 `@container (min-width: 60rem)`
  = 20rem 左栏 + ≈36rem 文档，是 A4 预览仍可读的下限。
- DOM 顺序把控件放在前面（**键盘与读屏顺序以 DOM 为准**），`.studio-doc` 用 `order` 调视觉顺序：
  堆叠时 `-1`（文档在前），两列时 `2`。
- 跨面板联动用**计数器 prop**（`openTick`）而不是受控 `expanded`，这样面板仍然拥有自己的状态，
  外部只能请求它打开，不能持续支配它。

#### 两列各自滚动，不用 `sticky`

最初文档列写的是 `position: sticky; top: 0`，放在第 3 步**唯一**的滚动容器里。实测这是坏的：

| 元素 | 高度 |
|---|---|
| `.studio-doc` | 818px |
| `.studio-rail` | 2724px |
| 唯一真实 scroller | clientHeight **860** / scrollHeight **2756** |

一个 860px 的滚动容器同时装着 818px 的文档和 2724px 的面板栏，于是**一个滚动条推着两列一起走**；
滚到面板栏底部时，简历已经被完全推出自己的那一列。`sticky` 救不了这个场景——sticky 只在
**包含块**仍处于视口内时生效，而这里的包含块是整个 2724px 的 grid。

现在的写法：第 3 步的外层 shell **自己不滚**（`ResumeStudio` 的 `stepOwnsScroll`），
把高度交给 `.studio-columns-inner`；两列模式下它是
`grid-template-rows: minmax(0, 1fr)` + `align-items: stretch` + `overflow: hidden`，
`.studio-doc` / `.studio-rail` 各自 `min-height: 0; overflow-y: auto; overscroll-behavior: contain`。
`minmax(0, 1fr)` 是关键：`auto` 会把行撑到最高那列的高度，滚动条就跑回祖先了。

堆叠模式下**只能有一个滚动条**（`.studio-columns-inner` 自己滚）。两个竖直堆叠的滚动区是陷阱：
用户滚上面那个到底之后，手势不会自动接到下面那个。

#### 两列不做「对齐」

左右两列内容不同、高度不同，实测首卡顶边差 47px。强行对齐只能靠填充假的空白，
所以这里**不做对齐**，改做**点击/聚焦联动**：`EvidencePanel` 的每条问题在 `onFocus` /
`onMouseEnter` 上报 `gap.field_path`，右侧预览把对应 `[data-path]` 滚进视野。
用 `focus` 而不是 `click`，键盘 Tab 的用户同样覆盖。

便利之处：`gap.field_path` 与预览的 `data-path` 本来就是同一套路径
（`experiences[0].highlights[2]`），不需要映射层。选择器要 `CSS.escape`（路径含方括号）。
这个指针是**单步内的瞬态状态**，刻意不放进 `uiContext`——它不是 agent 该推理的会话事实。

这块版面由 `scripts/verify_resume_steps.py` 量化断言，两种模式分别判定。断言是**结构性**的
（每列是否拥有自己的滚动条、祖先是否在滚），不是距离——距离指标对坏版面同样能过，
这是它上一轮没被发现的原因。1440×900 下 studio 面板只有 930px，**只会走堆叠分支**，
所以脚本会主动把窗口加宽到 1760px 再测一次：阈值在**容器**上，只能靠加宽触达。详见
[`TECH-RESUME-WRITING.md`](TECH-RESUME-WRITING.md) 第 13.3 与 13.4 节。

### 5.2 左栏字号：绝对值，且**不要在选择器里写 `@apply` 过的类名**

左栏在 22rem 宽的一列里放三组控件和说明文字，右边的文档是全尺寸阅读材料。
两者共用一个字号时，左栏的辅助文案和简历正文一样大，显得过大、也让这一列看起来装得很少。

规则只有一条，写**绝对值**：

```css
.studio-rail
  :where(p, li, span, label, button):not([class~="badge"], [class~="label-meta"],
    [class~="btn"], [class~="segment-item"], [class~="text-micro"]) {
  font-size: 0.78125rem !important;
  line-height: 1.6;
}
```

走过三条死路，不要重走：

1. **在 `.studio-rail` 上设 `font-size` 让子元素继承** —— 无效。Tailwind 的 `text-xs`
   是直接作用在子元素上的类，继承比不过它。
2. **用 `0.92em`** —— `em` 会沿 DOM 层级**逐级复合**，缩放量取决于嵌套深度而不是设计决策。
3. **给例外项单独写一条 `.studio-rail .text-micro { font-size: inherit }`** ——
   这是个真 bug，而且**在源码里完全看不出来**。见下。

`!important` 是必要的：它要和特异性相同的 Tailwind 工具类竞争，而工具类在产出样式表里的顺序
不受这个文件控制。

#### 陷阱：`@apply` 会克隆提到该类的**每一条**规则

`.badge` 和 `.label-meta` 是用 `@apply text-micro` 定义的。Tailwind 处理 `@apply` 的方式是
把**所有选择器里提到被 apply 类的规则**复制一份、改写上下文。于是一条写成

```css
.studio-rail .text-micro { font-size: inherit !important; }
```

的规则，被编译器额外产出了两条**源码里根本不存在**的规则：

```css
.studio-rail .label-meta { font-size: inherit }
.studio-rail .badge      { font-size: inherit }
```

后果：左栏的 badge 字号取决于**谁包着它**——包在 `div` 里是 16px，包在 `li` 里是 12.5px。
同一个组件两个字号，而样式表源码读起来完全正确。

**把类名移进 `:not()` 也不行**：克隆是文本级的，编译器会再产出一份把 `:not()` 里的
`.text-micro` 换成 `.label-meta` 的副本，于是 `text-micro` 实际上不再被豁免。

正确做法是用属性选择器 `[class~="text-micro"]`：匹配同一批元素，但不是改写器认得的类名 token，
规则**只会按原样产出一次**。

**这个文件的铁律：选择器里永远不要点名一个被 `@apply` 过的组件类。**

同理，`:where(h1,h2,h3,h4) :where(span)` 那条 `inherit` 规则也要排除这些类——
标题里的普通 span 属于标题，但标题里的 badge 只是恰好同行的 chip，它自带字号
（实测 `h3` 里的 `2/3 达标` 是 13.5px，别处同样的 badge 是 11px）。

左栏最终只有三档：**11px**（badge / 计数 / micro）、**12.5px**（说明文字）、
**13.5px**（用户输入的文字，要能校对）。

`verify_resume_steps.py` 的 `_assert_rail_type` 在两种版面模式下各测一次：
左栏不得出现 13.6px 以上的文字、同一组件类不得出现两种字号、总档数不超过 3。
`tsc` 不看 CSS，源码也读不出问题，**唯一能看见它的地方是浏览器里的 computed style**，
所以这里用测量而不是评审。变异测试已验证：把 CSS 退回克隆写法，断言如期失败并点名具体元素。

### 5.3 舟卡侧栏收起条：隐藏，不是卸载

第 3/4 步的主角是文档，侧栏 440px 在用户只读不聊时是净损失。所以侧栏可收起成
一条 44px 的竖条（`.agent-rail-collapsed` + `.agent-rail-label`），文档实测
**1122px → 1522px（+400px）**。

四个决定，都不是偏好问题：

1. **收起时侧栏用 `hidden`，不卸载。**
   `useAgentSession` 在 unmount 时会 `abortRef.current?.abort()`，而 agent 面板
   持有 SSE 流。卸载会把用户**已经启动的运行**静默掐掉、把流式回复丢掉——界面上
   完全看不出坏，答案只是永远不来。此外 `AgentStreamPanel` 在新消息时自动滚底，
   重新挂载会从顶部开始、滚动位置丢失，输入框草稿也没了。
   对一个**正在做事**的面板，"收起"只能是隐藏。

2. **竖排标签用 `writing-mode: vertical-rl`，不用 `rotate(90deg)`。**
   旋转只改变绘制，元素仍保留**水平的布局盒**，父容器照样按文字的水平宽度占位，
   44px 这个宽度根本做不到。代价是 CJK 在竖排下默认直立，所以这条标签的文案
   **只能是中文**。

3. **收起时不渲染 `role="separator"`。** 44px 的条上没有可调的东西，
   在它边缘给一个 col-resize 光标是假 affordance。

4. **空闲提示用 `nudge-x`（3.2s infinite，72% 之前静止）。**
   短促一次 + 长停顿：它紧贴用户正在读的文档，连续动效会和阅读抢注意力。
   有真实消息时（busy 或未读 > 0）提示动画让位——运行中本身就是回去看的理由，
   两个动效并排只会互相削弱。`prefers-reduced-motion: reduce` 由 `globals.css`
   既有的全局 media query 接管。

三态文案（`AgentRailHandle.tsx`）：`正在处理…` / `有新回复`（带计数徽标）/
`点这里让舟卡帮你改`。未读用「当前总数减去收起时的基线」算，不是自增计数器，
所以不会漂移；且只数**已完成**的 assistant 轮次，否则徽标会跟着 token 跳。
收起状态存 localStorage（`jc-agent-collapsed-{pageKey}`），**初始值固定 `false`
再用 effect 读**——render 期读 localStorage 会 hydration 不匹配。

`AgentHeader` 收起按钮的完整文案写在 `sr-only` 的 span 里而不是只放 `title`：
文本内容在 accessible-name 计算里优先于 `title`，只写短文案会把 `title` 挡掉，
按 name 定位的测试也会失败。

验收见 `scripts/verify_agent_rail.py`（[`../operations/QA-TESTING.md`](../operations/QA-TESTING.md) 第 1 节脚本清单）。

### card vs notice vs badge

- **card**：承载内容。用户来这里读东西或操作。
- **notice**：解释一个**当前状态**，通常是临时的（质检没过、邮箱未验证、岗位真实性存疑）。
- **badge**：给某个对象贴一个**不可操作的标签**（匹配分、题型、`已归档`）。

判断方法：如果它会随数据变化出现和消失，是 notice；如果它是对象的固有属性，是 badge。

## 6. 共享布局组件

| 组件 | 作用 |
|---|---|
| `components/layout/PageHeader.tsx` | 页面入口统一节奏（eyebrow / 标题 / 说明 / 操作区）|
| `components/ui/EmptyState.tsx` | 空状态。**必须给下一步动作**，不能只写一句灰字 |
| `components/ui/StatTile.tsx` | 指标卡。`tone` 只改数值颜色，不改背景 |
| `components/ui/Icon.tsx` | 共享图标集（24px 网格、单条描边路径）|

每个顶层页面都应以 `PageHeader` 开头，`eyebrow` 填导航分组名（`准备` / `行动` / `复盘`），
让用户知道自己在流程的哪一段。

## 7. 可访问性约定

1. 全局 `:focus-visible` 已在 `globals.css` 定义。**不要在组件里移除 outline。**
2. **状态不能只靠颜色。** 流程步骤、计划清单、质检结果都用「填充 + 图标 + 文案」冗余编码。
3. 浮层必须支持 outside-click 和 `Escape` 关闭，并带 `aria-expanded` / `aria-haspopup`。
4. 错误信息加 `role="alert"`，异步结果加 `role="status"`。
5. `prefers-reduced-motion` 已全局处理，自定义动画无需单独适配。
6. **正文对比度不低于 4.5:1**（大字号/粗体 3:1）。禁用态控件按 WCAG 1.4.3 豁免，不必强拉。
   这一条是可机械验证的，不要靠肉眼判断——见第 9 节的审计脚本。

## 8. 已知陷阱

- **`.5` 间距只有 Tailwind 默认的 `0.5` / `1.5` / `2.5` / `3.5` 四档可用**（`tailwind.config.ts` 的
  `spacing` 只加了 `gutter` / `section` 两个命名档，没有动数字档）。`px-2.5`、`mt-1.5` 这类**是生效的**；
  但 `h-4.5` / `w-4.5` 不存在，会静默失败，要用 `h-4` 或 `h-5`。判断方法见第 9 节。
- **颜色透明度后缀必须落在 Tailwind 的标准档位**（5/10/20/25/…/90）。`ring-brand-500/12`
  这类非标准值 `tsc` 查不出来，只在 `npm run build` 时报错。
- **`npx tsc --noEmit` 不校验 CSS。** 改过 `globals.css` 或 `tailwind.config.ts` 后必须跑一次
  `npm run build`。
- **`@container` 在 `tsc` 和 `npm run build` 里都是「看起来没问题」。** 容器查询只能在真实浏览器里
  按多档宽度实测，否则无法发现它在某个宽度下给出一个过窄的列。
- `components/agent/media/` 下的组件运行在深色/overlay 背景上，其中的 `bg-white/10` 类蒙版是
  故意的，机械替换会改坏它们。

## 9. 修改流程

1. 只在一两个地方需要的样式 → 直接写 Tailwind 工具类。
2. 第三次出现同一个 class 串 → 提成 `globals.css` 的组件类。
3. 需要新的尺寸、颜色角色或层级 → 改 `tailwind.config.ts`，并更新本文第 2–4 节。
4. 提交前：`npx tsc --noEmit` **和** `npm run build` 都要过。

## 10. 机械审计

`tsc` 不看 CSS，`npm run build` 不看计算样式。对比度、失效 class、横向溢出这三类问题只能在真实浏览器里测：

```bash
cd frontend/web && npm run build && npx next start -p 3100 &
python scripts/audit_visual.py --base http://127.0.0.1:3100
```

脚本检查并在发现问题时以非 0 退出：

| 检查 | 判据 |
|---|---|
| 对比度 | 正文 < 4.5:1、大字/粗体 < 3:1 即失败。禁用态控件按 WCAG 1.4.3 豁免并单独列出 |
| 失效 class | `.5` 间距只认 `0.5/1.5/2.5/3.5`，其余静默失效 |
| 横向溢出 | 文档级横向滚动，以及元素 `scrollWidth > clientWidth`（`sr-only` 已排除） |
| 极小字号 | 叶子文本 < 11px |
| 字号/颜色清单 | 不判失败，用于审查标尺是否在扩散 |

新增颜色或组件类后跑一次。它比肉眼可靠，也是第 7 节那条对比度要求的执行方式。
