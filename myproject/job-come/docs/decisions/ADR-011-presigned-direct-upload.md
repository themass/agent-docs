# ADR-011：媒体上传改为预签名直传（sign → PUT → 绑定）

- **状态**：Accepted（方向与作者确认于 2026-11-17。已实施：A 桶 CORS（2026-11-18 产线配置并 `curl -X OPTIONS` 双 origin 验证）、B `media_upload` 迁移 027 + sign 路由 + 绑定校验 + GC、C `chat-image`/`chat-audio` 直传切换、D `profile-source` JSON 提交形态（含前端重建部署）。E 步观察中：产线 2 日 22 个附件直传 1 / 中继 21（唯一直传发生在 CORS 生效后），直传占比过低，暂不收 `data_url` 拒收门）
- **日期**：2026-11-17
- **参考**：`myandroidTest` 仓库 `docs/design/shared-media-upload-and-storage.md`（v2，下称"参考设计"）。本 ADR 采纳它的时序骨架，改掉它的鉴权与信任假设，差别全部在 §Decision 写明。

## Context

字节现在穿过应用服务器两次，各有一处实测痛点：

| 链路 | 现状 | 代价 |
|---|---|---|
| 聊天附件（照片/语音条） | 浏览器编成 `data:` URL（base64 膨胀 4/3），单附件 ≤8 MB、单消息 ≤24 MB（`agent_attachment_service.py`） | 消息请求体膨胀；慢网络上大字节上传撞请求超时，重试要整批重传 |
| 简历原件 `/profiles/upload` | multipart ≤15 MB 经应用进程读进内存（`profile_router.read_limited_upload`） | 解析型大请求占用 worker；扫描件大图最伤 |

头像链路（`profile_photo_service`）**不在本方案范围内**。分界线不是"图片/非图片"，而是**服务端要不要打开字节**：头像是唯一一条服务端必须打开并改写字节的链路——字节打印进 PDF，EXIF 方向校正、剥 GPS、解码炸弹防护、重编码是硬要求，上传的字节不是最终字节。直传若承载头像，时序必然变成「暂存 → 服务端下载 → 规范化 → 转正式 key」，即本 ADR 在 Alternatives 里拒绝的隔离区+转正式区，只有它一个用户。而收益端：前端裁剪器（`lib/image-crop.ts`）产物 canvas JPEG 1024px/q0.92、约 100–300 KB（6 MB 只是绕过裁剪器的上限），直传省下的字节约等于零，服务端的重编码防线作为纵深防御也一道不能少。维持 multipart。

参考设计是为 4 个 Android 应用共享 `sspacee` 桶写的。它的环境对我们是已知事实而非风险：桶私有（读全部走 CDN 签名 / presigned GET），我们的对象全在 `jc/` 前缀下；它担心的"ACL 未知"和"前缀归属"已验证。它的 `media/` 前缀与我们的 `jc/` 前缀共存，互不干扰。

## 边界先说死：直传解决什么、不解决什么

- 直传省的是**客户端 → 应用服务器**这一跳的字节与 base64。它是带宽和可靠性改造，不是正确性改造——字节早已落对象存储，不在消息行里。
- **服务端 → 模型的 base64 那一跳省不掉**（模型 API 的入参形态，`ImageRef.from_bytes` 就是干这个的）。这一跳的大小由图片本身决定，所以控制它的手段是上传端压缩（§压缩），不是直传。
- 客户端压缩是**性能优化，不是安全边界**。浏览器永远可被绕过（DevTools），所以服务端的大小校验一个都不能少：sign 按声明值限上限 + 绑定时 HEAD 拿实际字节数复核。服务端**从不**替上传方下采样或规范化——超限就是拒绝，不是"帮你改小"。这条契约让"传进来的就是最终字节"成为可依赖的性质。

## Decision

### 1. 时序

```text
浏览器（canvas 压缩到 scene 参数，见 §压缩）
 │  POST /api/v1/media/sign        ← 现有登录态鉴权（user 或 guest session）
 │  {scene, contentType, sizeBytes}
 │  ← {objectKey, upload{method,url,headers,expiresAt}, limits}
 │  PUT upload.url                 ← 原始字节直达 TOS，不过应用服务器
 │  业务接口带 objectKey 提交：
 │    · 聊天消息 attachments[].objectKey（新字段，与 data_url 互斥）
 │    · 档案上传 JSON {objectKey, fileName}（multipart 保留为降级通道）
 服务端绑定校验（归属校验，不是内容校验）：
   key 在签发记录 ∧ actor 相同 ∧ scene 相同 ∧ 未绑定 ∧ 未过期
   → HEAD 一次：对象存在、实际大小 ≤ 该 scene 上限
   → 标 BOUND、记 actual_size、写业务引用
```

**没有 complete。** key 在签发时确定，PUT 200 即对象就位；绑定即校验即消费。与参考设计一致。HEAD 这步参考设计标为可选——我们**做**：一次 TOS 请求换"图不存在 / 超大"两个问题在绑定时当场报错，而不是延迟到模型读图时才炸，值得。

### 2. 鉴权：用登录态，不用 appSecret HMAC

参考设计的 B 路（appId + appSecret 进 APK）是"接入方没有统一登录"的妥协，**不适用且不能适用**：web 端没有 APK 可藏密钥，JS 里的 appSecret 等于明文公开。我们所有路由已有 `require_user` / `get_actor_with_guest`，sign 直接挂同样的依赖；`appId` 应用注册表、`X-Media-Signature`、nonce 表整个不引入。`identityRealm/subjectId` 同理不需要——actor 就是身份。

防线相应从"应用级配额"落到"用户级配额"：Redis 按 actor 限签发速率与日次数（现有 Redis，不建配额表）。guest 的 scene 上限从严（简历试用一直是这个口径）。

### 3. key 与表

```text
jc/<env>/uploads/<actor_id>/<scene>/<yyyy>/<mm>/<dd>/<keyId>.<ext>
keyId = 服务端生成的 22 位 URL-safe 随机串；ext 由 contentType 白名单推导
```

- 必须按 **actor** 分区，不能按 profile/session：sign 发生在档案或会话还不存在的时候（新档案的第一份上传、新会话的第一条带图消息）。
- key 不含文件名、姓名、邮箱。`storage_key()` 的 `jc/<env>/` 前缀纪律与段合法性检查不变。

**`media_upload` 表**（迁移新增）：`object_key`(PK)、`actor_id`、`actor_kind`、`scene`、`content_type`、`declared_size`、`actual_size`、`state`、`issued_at`、`expires_at`、`bound_ref`、`bound_at`。`state`：`ISSUED → BOUND | EXPIRED`。

GC 任务（沿用 `jc/` 前缀纪律，硬编码只扫 `jc/<env>/uploads/`，不遍历桶）：

| 情况 | 处理 |
|---|---|
| `EXPIRED` 且签发超 7 天 | 删对象 |
| `BOUND` | 跟业务共存亡；引用释放后延迟 24 小时删 |
| 桶里有、表里没有 | 对账任务，超 7 天无记录即删；dry-run + 单批上限 |

### 4. scene 白名单与上限

| scene | 内容 | 上限 | 压缩责任 |
|---|---|---|---|
| `chat-image` | 聊天照片 | 2 MB | 客户端（§压缩） |
| `chat-audio` | 语音条 | 8 MB（现值） | 无（浏览器 MediaRecorder 产物已是有损编码；时长上限沿用 `duration_ms ≤ 6h`） |
| `profile-source` | 简历原件：PDF / DOCX / TXT / 照片简历 | 15 MB（现值） | 文档**不压缩**（原件归档 + 可重复解析）；照片简历按 OCR 档压缩后再签（§压缩） |

`chat-image` 从 8 MB 降到 2 MB 是压缩目标的直接后果（目标 ≤800 KB，×安全边际）。**本期不立刻降**：新链路稳定后按观测的体积分布再降，避免同时改两个变量。`contentType` 白名单与 `ALLOWED_INLINE_PREFIXES` 现行范围一致，不放宽。

### 5. 压缩：客户端压缩，服务端只验不修

**决策：聊天图片在浏览器压缩后再直传。** 三条独立理由：

1. **vision 输入 token 按像素面积线性计费**（Anthropic 按 ~1.15 MP 分片、Qwen-VL 按 28×28 patch、豆包同理）。长边 1568 的图约 1.1 MP，4096×3072 原片 12.6 MP——同一张图的 vision token 成本差约 10 倍。压缩点选 1568 是因为主流视觉模型都在这个量级封顶：超过之后再多的像素被分片计费、基本不换成识别质量。**实施时验证**：切换前后各记 `usage` 的图片 token 实测值，本段结论若不成立按实测修正。
2. 上传 payload 小一个数量级：直传的可靠性收益（慢网络重试成本）随字节数走。
3. canvas 输出天然不带 EXIF——方向由 `createImageBitmap` 默认 `imageOrientation: "from-image"` 应用（实现注意：不要显式传 `"none"`，会把躺倒问题带回来），GPS 也不存在。压缩过的图没有元数据剥离负担；规范化需求只存在于头像链路，那里维持服务端处理不变。

**参数**（前端 `compressImage(file, profile)`：一个实现、两个档位）：聊天图档长边 1568、JPEG q0.82，产物 >800 KB 则迭代降到 q0.7 / 长边 1280。与相机链路现参数（`lib/agent-ui-kit/camera-capture.ts` 720p q0.92 ≈ 300 KB）同量级，相册原图是受益方。

**分档**：

- **文档不压缩**（PDF / DOCX / TXT）：原件要归档、要可重复解析，它们的字节不是"图片"，浏览器端重编码只会损坏归档。喂视觉模型前的降采样本来就在服务端做（`profile_vision` 渲染 PDF 页时定标）。
- **照片简历按 OCR 档压缩**（`profile-source` 的 image 类）：长边 2048、q0.85、目标 ≤1.5 MB——整页小字的可读性是这条链路的真问题，参考设计对 solve-image 单独放宽上限是同一个判断，不套用聊天图的 1568 档。这也修掉一处现存浪费：`profile_vision.extract` 目前把原图**全尺寸**字节直接发给视觉模型，没有任何降采样。
- **音频无可压空间**（`chat-audio`）：浏览器 MediaRecorder 产物已是有损编码。且它的字节上传后不再进入服务端处理——模型读 transcript（浏览器 STT），回放是浏览器拿签名 URL 直接从存储播。

服务端**没有任何**"收到大图帮你缩小"的路径：绑定 HEAD 发现超该 scene 上限就是拒收 + 进 GC。

### 6. 实施顺序（对应参考设计 §11，按我们的环境改写）

- **A** 桶 CORS：`AllowedOrigin` = 前端各 origin（生产 + `localhost:3000`）、`AllowedMethod: PUT`、`AllowedHeader: Content-Type`（presigned PUT 把 Content-Type 算进签名，CORS 不放行则浏览器发不出）。现桶从未配过 CORS（今天所有写入是服务端 SDK 发的），这是上线前必配且只有我们会遇到的项。agentkit `ObjectStore` 加 `presigned_put_url`（boto3 `generate_presigned_url("put_object", …)`，与 `presigned_get_url` 对称）→ `./scripts/build-release.sh --update` 重建 wheel。dev（`storage_remote_enabled=false`，写本地盘）下 sign 返回 503，前端捕获后回退 multipart——旧通道同时是生产的降级通道。
- **B** `media_upload` 迁移 + sign 路由 + 绑定校验 + GC 任务 + 测试（含归属：A 的 key 绑到 B 必须 403；过期 410；重复绑定 409；HEAD 超大拒收）。
- **C** `chat-image` / `chat-audio` 切换：`AgentAttachment` 加 `object_key` 字段（与 `data_url` 互斥），前端附件统一走 `sign → PUT → objectKey`，`compressImage` 在 sign 前。旧 `data_url` 路径**保留一个观察期**：存量账本行里有裸 `data:` URL 的消息要一直读得出，新消息优先新路径。
- **D** `profile-source` 切换：新增 JSON 提交形态，multipart 保留。
- **E** 观察期后新消息拒收 `data_url`（读路径永久兼容存量）。降 `chat-image` 上限到观测值。

### 7. 风险与边界（参考设计 §9 全部继承，逐条给答案）

1. **无内容校验**：拿到凭证可塞任意字节。防线 = 单文件上限 + 10 分钟 TTL + actor 级签发配额 + 绑定 HEAD（挡住"根本没传"和超大）。接受：桶私有，最坏是被塞垃圾，不是被读走东西；封 actor + 清前缀可处置。
2. **PUT 可重放**：TTL 内同 key 可覆盖 → **每次上传申请新 key**，绑定后绝不复用凭证（写进前端封装的契约）。
3. **长度不强制**：presigned PUT 约束不了 Content-Length → 声明值上限 + 绑定 HEAD 实际值拒收 + 漏网的进 GC。要入口硬拦得上 POST policy，本期不做，留作升级候选。
4. **签名 URL 是 bearer secret**：不进日志、不进埋点、不进错误详情（前端与后端同等对待）。
5. **guest 滥用**：guest 无账号锚点，签发速率与 scene 上限从严；简历试用本来就是配额制，口径统一。

## Alternatives Considered

- **维持 multipart 代理**（现状）：改动最小，但 4/3 膨胀、请求超时面和 worker 内存占用原样保留；相册原图场景只会更糟。拒绝。
- **原样采纳参考设计（含 B 路 HMAC、`media/` 前缀、消息不跨设备）**：鉴权对 web 不成立；`media/` 前缀破坏我们 `jc/` 前缀纪律与既有 GC；"聊天图不跨设备"与账本回放模型（`agent_attachment_service` 模块注释：回放的一轮要能证明那个数字真被念出来过）相反。骨架采纳，血肉全部替换。
- **隔离区 + 服务端校验转正式区**（参考设计 v1）：多一次往返、一套状态机；聊天图不是打印物，规范化收益低，风险清单已覆盖主要威胁。若未来出现滥用实拍，再叠加不迟——`media_upload` 这张表预留了位置，升级不推翻本决策。
- **服务端异步压缩替代客户端压缩**：省不掉上传跳的原始字节（压缩收益的 1、2 条全丢），只保第 3 条，还引入转码队列。拒绝；服务端压缩只保留在头像链路（有规范化刚需）。

## Consequences

- agentkit 需要一个 1 行能力的公开方法（`presigned_put_url`），走 wheel 重建流程（ADR-002 同款纪律）。
- `sspacee` 桶要加 CORS 规则并验证——这是运维步骤，代码测试覆盖不了，写进上线清单。
- 消息 schema 多一个可选字段；少掉 `data_url` 的时间由观察期决定，账本读路径永久兼容它。
- 头像链路、`storage_router` 本地盘读路径、CDN 签名读路径全部不动——本决策只换"字节如何到达桶"。
