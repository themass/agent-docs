# chat 页面整改清单（2026-11-20）

六份并行调查的合并结果，只保留**能落到具体文件和行**的条目。排序按「用户可感知的伤害 ÷ 改动量」，
不按模块。每条都标了证据位置，不要凭印象改。

调查范围：角色不像人、老 Java 依赖、面板缺功能、拍照解题、切换会话慢、页面整体体检。
已修的三条见文末「已修」。

---

## P0 — 用户现在就能感知到，且改动小

### 1. 角色念任务清单（部分已修，还剩一道兜底）

**已修**（`eaa8e8a`）：人设层不再整张塞任务卡、约束移到系统末尾、文案重写。

**还剩**：提示词是概率性的，283 张卡 × 长尾模型一定有漏网。需要一道确定性防线。
建议做首轮 `max_tokens` 上限：`graph_middleware.py:47-67` 的 `awrap_model_call` 里判断
「本会话首条助手回复 + 用户输入是短招呼」，把 `max_tokens` 压到 ~120（现在 `routing.yaml:74` 是 4096）。

- 判定短招呼：`len(text) <= 12` 且命中一个很小的多语问候正则表。
- 只对首轮、只对命中问候的输入生效，避免把正常长回答截断在半句。
- 不做「检测到长回复后截断」——文字通道的 delta 是直接发出的，事后截断用户会看到断句。

**顺带补**：目录角色的 `examples` 恒为空（`from_system_role` 不填），模型手里没有一个
「这个角色怎么说话」的样本。可从卡里的 `## Communication style` 抽带引号的句子合成 1–2 条
`<example_dialogue>`，走现有 `_examples_block`（`roleplay.py`，预算 1500）。

### 2. 冷启动断网显示「空会话」，和「历史被清空」一模一样

`ChatViewModel.kt:83-87` + `:93`：`refresh()` 用
`runCatching { loadHistory() }.getOrElse { HistoryPage(emptyList(), hasMore = false) }`
把异常吞成空页。`syncSessionsFromServer` 也在 `AgentBackedChatRepository.kt:428-429` 静默返回。

加载结束后 `ChatScreen.kt:215-217` 渲染 `EmptyChat`（头像 + 三句开场白）——
用户断网打开 App，看到的是一段全新的、从没聊过的空白会话。

改法：`ChatUiState` 加一个 `loadError` 字段，失败时渲染错误条（复用现成的 `ChatErrorBar`），
不要落到 `EmptyChat`。

### 3. 编辑态下带附件发送：新消息发出去了，编辑态还挂着

`SendActions.kt:41-49`：`onSend()` 只在 `editingId != null && drafts.isEmpty()` 时走 `submitEdit`；
草稿托盘里有一张图就落到普通发送分支，而该分支的 `state.update { it.copy(input = "", drafts = emptyList()) }`
（`:45`）**没清 `editingMessageId`**。

结果：编辑消息 → 加图 → 发送，得到一条新消息，「编辑消息」横幅继续挂着，再点发送又走同一条错路。

改法：`ComposerActions.startEdit` 清空 `drafts`（`ComposerActions.kt:18-22`），
并在普通发送分支里一并把 `editingMessageId` 置空。

### 4. 电话：整套栈已经写好了，只差一条 Gradle 依赖边

`feature-companion` 里有完整的实时通话：麦克风权限申请、`startCall`、全屏通话层
（静音/挂断/通话中发文字）、返回键二次确认挂断（`CompanionRoute.kt:116,162,345`）。
LiveKit SDK 已在 `feature-companion/build.gradle:41`。服务端 `/v1/voice/sessions` 也有。

**唯一的阻塞**：`feature-chat/build.gradle` 没有 `:feature-companion` 这条依赖边，
两个模块在 `app/build.gradle` 里是平级兄弟。

第二个障碍是 ID 体系：chat 用 int 的 `roleId`/`characterId`，companion 用 string 的
`character_id`（默认 `"linche"`）。直接接会串号，需要一次归一化。

现在「电话」有**两个入口、两句不同文案、都是空壳**：`ChatRoute.kt:142-144` 弹
"Voice call is currently unavailable"，`RolePickerSheet.kt:145-146` 弹「语音通话即将上线」。

### 5. 拍题解题从来没有成功过（服务端 bug，一行改动）

服务端是**老 Java** `testserverV` 的 `/api/photosolve/v1/solve.json`，不是 companion-agent。

真凶：`DoubaoPhotoSolveProvider.java:97` `maxTokens(4096)` 把 JSON 截断，
`extractJson`（`:218-263`）要求括号平衡，返回 null，`:159-164` 于是报
`questionFound=false` → 40002「不是题目」。**每一次都失败**，和「一直没有成功过」完全一致。

改法：调大 `maxTokens`，或在 `extractJson` 里支持截断的 JSON 收尾。

边框不准是另一回事：`DocQuadNetCropAssistProvider.kt:136-147` 把模型的 4 个角点
塌缩成轴对齐外接矩形，透视全丢；没有置信度阈值（`:114-140`）；
预览用 `FILL_CENTER` 而拍照是全画幅（`PhotoCaptureScreen.kt:94`）。

### 6. 切换会话慢：不是服务端的问题

三处，按影响排序：

1. **每张图串行拉签名 URL**，就在关键路径上（`AgentBackedChatRepository.kt:351-366`，
   从 `:343` 调），0.4–2s。并发化即可。
2. **没有乐观渲染、没有加载态**（`SessionActions.kt:24-32`、`ChatViewModel.kt:90-118`、
   `ChatScreen.kt:216`）——`loading` 唯一的消费点只是「不显示空状态」。先渲染会话骨架。
3. **Room 全页重写**：30 条消息 = 30 个独立事务，会话表读 3 次
   （`AgentBackedChatRepository.kt:719-761`）。批量 upsert。

服务端地板约 400ms（2 次串行 SQL，库在 180ms 外）。`owned_session` + `list_before`
可合并省约 180ms（`chat.py:226-227`），但那是锦上添花，先做客户端的 1 和 2。

---

## P1 — 数据会丢，或体验明显断裂

### 7. 离线缓存只留 30 条，而且是**全局**不是按会话

`MessageCache.kt:26-30, 168-174` + `ChatLogDao.java:41-48`：`CHAT_LOG_KEEP = 30L`，SQL 是
`DELETE FROM ChatLog WHERE msgType = 0 ... AND id <= (SELECT MAX(id) FROM ChatLog) - :keep`
——跨所有会话只留最近 30 条纯文字行。

后果：断网时回退本地缓存（`AgentBackedChatRepository.kt:332-334`），切到任何一个稍旧的会话，
基本只剩几行。和上层 `HistoryMerge`/`mergePending` 精心做的失败重试体验完全不匹配。

改法：改成按 `sessionId` 分组保留（如每会话 100 条）。

### 8. SSE 断流不重连，回答被静默截断

`AgentBackedChatRepository.kt:240-280`（`collectTurn`）：服务端事件流支持 `Last-Event-ID` 补发
（`AgentChatRemote.kt:242-249` 确实发了这个 header），但 `collectTurn` **从不使用 lastEventId**，
`catch (e: Exception)` 直接 `emit(ChatStreamEvent.Error(...))` 收尾。

一次网络抖动就把回复切成半截。同仓库另一条链路已有 `AgentEventReconnector`
（`app/.../agent/AgentEventReconnector.kt`）——重连能力存在，只是没接在这里。

### 9. 清空上下文是 O(n) 逐条删，而一键接口早就写好了

`MessageRemoval.kt:44-75`、`:88-112`：`deleteMany` 用
`for (id in messageIds) { if (deleteOnServer(id)) ... }` 顺序发请求。500 条 = 500 次往返，
没有进度、不能取消，切走后 `viewModelScope` 里的循环还在跑。

而 `AgentChatRemote.kt:91-92` 定义了 `clearHistory` 一键接口，**全仓库零调用**。

### 10. 远程图片签名 URL 失败 → 永久灰块，无重试

`AgentBackedChatRepository.kt:346-366`（`hydrateImages` 失败时「保持空路径」）
+ `ChatItemMapper.kt:47-49` + `MessageParts.kt:167-182`：`path` 为空串时
`AsyncImage(model = File(""))` 走 placeholder 底色。

签名 URL 只有 300 秒寿命（注释在 `:337-339`），隔天打开历史必然命中，用户看到一排灰方块，
没有任何可操作的出口。改法：失败态画占位图 + 点击重试。

### 11. 发送/编辑失败后草稿和文字都不保留

`SendActions.kt:45`（清 drafts）+ `ResendActions.kt:78-86`（`submitEdit` 失败后 `refresh()`，
`input` 已在上一步清空）。图片气泡可以重试（这条做得对），但草稿托盘已消失，
用户没法「改一下再发」；编辑失败后刚打的文字一并没了。

### 12. 流式期性能：25 次/秒全量拷贝 + O(n²) Markdown 解析

- `ReplyStreamer.kt:93-105, 219-223`：`updateByKey` 是
  `current.messages.map { if (it.key == key) transform(it) else it }`，
  每追加几个字就新建 N 元素 List。2000 条历史时约 5 万次对象比较/秒，全为了给最后一条加几个字符。
- `MarkdownText.kt:48-56`：`update` 里无条件 `setMarkdown(view, 已显示全文 + 新片段)`。
  8k 字回答在流式阶段累计 O(n²)，还要每次 `getSpans` 扫全量判链接。「越到后面越卡」的直接来源。

改法：流式只走「最后一条」单槽通道；Markdown 增量解析或按段缓存。

---

## P2 — 明显该有但没有

### 13. 位置、视频：四层全缺

- **位置**：全仓库所有 manifest 都没有 `ACCESS_FINE_LOCATION`；`Permissions.kt:27` 定义了
  `LOCATION` 但零调用方；`MessageKind` 枚举里没有 LOCATION；没有 LocationManager/FusedLocation
  代码；服务端也没有经纬度字段。
- **视频**：`MessageKind` 无 VIDEO，`/v1/uploads` 只认图片和文件。

这两项是真正的新功能，不是补丁，别混在「修 bug」里。

### 14. 面板文案没本地化

`feature-chat/src/main/res` 只有 `values/`（内容是中文），**没有 `values-zh`**；
而 `chatkit` 是「英文默认 + `values-zh`」的正确做法，`app` 已带 de/es/ru。

结果：中文用户看到的 "Camera"、"Help"、"Phone"、"Photo solve" 全是英文；
德/西/俄系统上是「Deutsch 界面 + 中文按钮 + 英文 chatkit」三语混排。

另外 `feature-chat` 的错误文案整批是中文硬编码字面量（`ReplyStreamer.kt:146,182,183,191`、
`HistoryActions.kt:39`、`SessionActions.kt:39,53,65`、`MessageRemoval.kt:38,61,62,110`、
`CharacterActions.kt:92,123,143,160`、`SendActions.kt:91,119,146,164`、`AttachmentStager.kt:72,84`）。

### 15. 搜索：完全不存在

会话列表和消息列表都没有入口。

### 16. 无障碍：所有消息操作对 TalkBack 不可达

`MessageParts.kt:90`：`combinedClickable(onClick = {}, onLongClick = onLongPress)`。
复制、编辑、删除、重新生成、多选全挂在长按上，而 Compose 的 `combinedClickable`
不会自动暴露 `OnLongClick` 语义动作，`onClick = {}` 又让双击是空操作。
**读屏用户双击只会听到「已激活」，没有任何一条消息能被操作。**

需要 `Modifier.semantics { customActions = ... }` 或一个可聚焦的「更多」按钮。

另有若干 `contentDescription = null`：`ChatMessageList.kt:277-282`（「回到底部」，
唯一可见的滚动恢复入口，无描述等于读屏不可用）、`MessageParts.kt:168-171`、
`ImageViewer.kt:82`、`VoiceDraftEditor.kt:87,92`。

---

## P3 — 技术债，会放大后续改动成本

### 17. `AgentBackedChatRepository.kt` 770 行，职责过载

会话 id 迁移、SSE 折叠、错误码翻译（`:317-324`）、上传直传/中转降级（`:453-505`）、
本地缓存、签名 URL 水合全在一个类里。`ChatRepositoryImpl`（178 行）+ `ChatStreamClient`（272 行）
作为「只用于 TTS/人设」的委托仍完整存在，`ChatRepositoryImpl.kt:47` 还额外构造了一套 OkHttpClient。

两份流式实现并存，`ChatStreamClient` 已经明显落后——它的 `delta`/`done` 帧格式和
`AgentChatRemote` 完全不同。改协议时容易只改一边。

### 18. 常量三处独立维护

`ChatViewModel.kt:35-40` 定义了 `REVEAL_TICK_MS = 40L` 和 `ATTACHMENT_TIMEOUT_MS = 120_000L`，
真值分别在 `ReplyStreamer.kt:35` 和 `AttachmentSender.kt:33` 各定义了一份。改一处不会生效。

### 19. 复制粘贴的 import 块

`ChatMenuTargets.kt:1-56` 开头 56 行是从 `ChatMessageList.kt` 复制来的 import，
实际只用到前 20 行附近几个。同样的痕迹在 `ChatScreen.kt:1-64` 与 `ChatDialogs.kt:1-64`
（两边几乎逐行相同的 64 行 import）。读代码时极易误判依赖关系。

### 20. `AttachmentSender.fail()` 用 `coroutineContext[Job]!!` 判「是否被停止」

`AttachmentSender.kt:113-117`：靠 `!!` 取 Job，再用 `isActive` 推断用户是否点了停止。
当前调用点都在 suspend 上下文不会 NPE，但这是随重构就会炸的写法。
正确做法：捕获 `CancellationException`，或在 `onStopGenerating` 里显式传 stopped 标志。

### 21. `allowMainThreadQueries()` 开着

`AppDatabase.java:61`。`SessionRole.resolve` 在主线程跑就是靠它。

### 22. 拍照解题用字符串硬编码类名

`ChatRoute.kt:131-134` 用 `"com.openapi.feature.photosolve.PhotoSolveActivity"` 启动，
改包名/类名就静默失败（catch 后只 toast）。这是唯一一条字面 TODO。

---

## 老 Java 依赖：还没迁完

不是「已经全迁了」。同一个域名 `api.ok123find.top`，按路径分：`/vvv/api/...` = 老 Java，
`/v1/...` = 新 Python。仍在老服务上的：

| 功能 | 位置 |
|---|---|
| TTS | `AttachmentUploader.kt:48` |
| ASR | `BackendSpeechToText.kt:37` |
| 非图片文件上传 | `AttachmentUploader.kt:26` |
| 自定义人设 CRUD | `CharacterRemote.kt:36-58` |
| 反馈/不喜欢 | `ChatMessageActions.kt:38-39` |

**结构性风险**：登录/鉴权整个在老 Java 上；`/v1` 用 Redis token 校验，而 token 是
老服务写的（`redis_token.py:23-48`）。**老 Java 一挂，所有 `/v1` 返回 401。**

死代码（可以删）：`HomeTab.AgentChat` 不可达、`AgentRoleChat.kt` 无人调用、
`HttpDNSUtil` 的 DNS 回退（`needDnspod` 硬编码 false）。

---

## 已修（本次）

| 提交 | 内容 |
|---|---|
| `6c17b2e` | 补 `_channel_for`——语音回合之前一直按文字通道组装提示词，`VOICE_BREVITY_RULES` 从没生效过 |
| `7c0daef` | cue JSON 只注入语音通道，文字聊天不再产协议文本 |
| `eaa8e8a` | 人设层不再塞任务卡；约束移到系统提示词末尾；文案改为给失败模式命名 |

---

## 别在优化时改坏的部分

- **稳定 key 两层设计**：`ChatItem.key` 与 `ChatMessage.key`（`ChatMessage.kt:68-77`），
  注释解释了为什么不能用 `id`——本地 id 要换成服务端 id。
- **贴底策略**：`following` 只由用户滑动决定（`ChatMessageList.kt:138-145`），
  流式增长不抢滚动，有 `ScrollToBottomChip` 兜底。
- **三个滚动 `LaunchedEffect` 用 `Mutex` 串行化**（`ChatMessageList.kt:130-136`），
  注释记录了真实的首帧 `IndexOutOfBoundsException` 复现路径。
- **`ChatErrorBar`**（`ChatScreen.kt:227-233, 339-359`）把服务端 errno/HTTP 原文渲染出来，
  是之前「不知道自己错在哪」的正解，别退回成「请重试」。
