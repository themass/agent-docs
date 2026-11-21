# 接口清单与数据模型

- 服务:Java 模块 `vvv-student`,前缀 `/api/student/v1`。统一外壳与 `vvv-poetry` 一致:`{"errno":0,"data":...,"error":null}`。
- 鉴权:公开内容(`config`、`timeline`、`works`、`bundles`、`pack`)无需令牌,只做进程内限流与访问日志;设备相关接口使用 `Authorization: Bearer <deviceKey>`;内部汇总接口使用 `X-Student-Internal-Token`(未配置则 503,与 `vvv-poetry` 做法一致)。
- 所有查询只读已发布内容;任何接口都不返回 `status != 'PUBLISHED'` 的行。

## 1. 内容分发(只读)

| 方法与路径 | 作用 | 来源 |
|---|---|---|
| `GET /config` | `assetBase`(素材 CDN 或开发静态路径)、`minSchemaMajor`、`dataNoticeVersion`、`audiences`、`agentEnabled` | 配置 |
| `GET /timeline?fromYear&toYear&type&limit&offset` | 已发布条目 + 覆盖声明 + `includesUnknownDates` | `PoetryCatalog.timeline`、`coverage` |
| `GET /works/{workId}` | 作品卡片:标题、作者、年代(含采用说)、是否有课程入口 | `PoetryCatalog` + 已发布脚本 |
| `GET /works/{workId}/lesson` | 课程入口:最新已发布脚本的 `scriptId/scriptVersion/bundleHash/coverageNotice` | `poetry_script`(PUBLISHED 且 `bundle_hash` 非空) |
| `GET /works/{workId}/pack?audience=` | 诗文包:逐句原文与拼音、注释、背景、背景↔诗句关联、覆盖声明 | 见 §3 |
| `GET /bundles/{hash}` | scene bundle 的 JSON,内容寻址,`Cache-Control: public, max-age=31536000, immutable`,`ETag: "<hash>"` | 文件存储 + 已发布登记交叉校验 |
| `GET /bundles/{hash}/manifest` | bundle 清单(资产 hash、总字节) | 同上 |
| `GET /claims/{claimId}/citations` | 某条已发布 claim 的出处(标题、作者、版本、位置、摘录);未发布或不存在返回 404 | `PoetryCatalog.claim/citations` |
| `GET /assets?level=` | 已发布素材登记:id、kind、level、uri、hash、bytes、`fallbackId`、权利信息、meaning(`meaning` 是给作者看的,学生界面不显示) | `poetry_asset`(PUBLISHED) |
| `GET /assets/{id}/chain` | 降级链(至 L0 终点) | 同上 |

**bundle 分发的取舍**:bundle 由内容生产项目的编译器写成文件(`dist/bundles/<hash 前 32 位>/bundle.json`);Java 通过 `student.bundle.root` 配置的目录读取。放行条件:`hash` 匹配 `^[a-f0-9]{12,64}$`(杜绝路径穿越),且 `poetry_script` 里存在 `status='PUBLISHED'` 且 `bundle_hash = hash` 的行,且文件存在。三者缺一返回 404,**不会因为目录里有文件就分发**。生产环境推荐把同一份文件放对象存储 + CDN,此接口作为源站回退。

**素材文件本身**不由 `vvv-student` 分发:`uri` 是对象存储键,前端用 `config.assetBase + uri` 取(与 `platform-web` loader 一致);`vvv-student` 只提供登记表。

## 2. 设备与学习记录

### 2.1 接口

| 方法与路径 | 作用 |
|---|---|
| `POST /devices` | 创建匿名设备。请求体空。返回 `{deviceId, deviceKey}`,**密钥只返回这一次**,服务端只存 SHA-256。限流更严(每 IP 每分钟 10 次)。 |
| `GET /devices/me` | 校验凭证、返回创建时间与数据保留说明版本 |
| `DELETE /devices/me` | 删除该设备的全部服务端记录(会话、事件、缺口、设备本身)。家长清除与「重置匿名身份」共用。 |
| `PUT /devices/me/sessions/{workId}` | 写会话进度:`{lastStep, visited[], audience}`。幂等覆盖。 |
| `GET /devices/me/sessions` | 取全部进度(换屏恢复、「继续上次」) |
| `POST /devices/me/events` | 批量事件(≤50 条/次),全部白名单校验,非法条目整条拒绝并返回序号 |
| `POST /devices/me/gaps` | 记录一次复述评估结果:`{workId, scriptHash, covered[], missing[]}`(要点 id 列表) |
| `GET /internal/gaps?workId=` | 缺口看板:按要点与步骤聚合的人次(最少 5 人才显示,否则只返回「不足」) |

### 2.2 事件白名单(`POST /devices/me/events`)

每条:`{workId, step, kind, ms?, ref?, at}`

| `kind` | `step` | 附加字段规则 |
|---|---|---|
| `step_enter` / `step_leave` / `step_skip` | read\|arrive\|meet\|return\|recite | `step_leave` 带 `ms`(0–3,600,000) |
| `layer_open` | arrive | `ref ∈ SCENE\|CITY\|WORLD\|PERSON` |
| `line_tap` | read\|return | `ref` = 句序号 1–64 |
| `ask` | 任意 | `ref ∈ rephrase\|hint\|ask_why\|open_layer\|basis\|recite_prompt\|decline`(只有动作名) |
| `retell_submit` | recite | `ref ∈ len_0_20\|len_21_60\|len_61_plus`(只有长度档) |
| `media_degraded` | 任意 | `ref` = 降级原因枚举 `weak_net\|low_memory\|reduced_motion\|user_off\|asset_failed\|context_lost` |
| `agent_fallback` | 任意 | `ref` = `timeout\|unavailable\|rejected\|budget\|disabled` |

**没有自由文本字段。** `ref` 只能是上表的枚举值或 1–64 的整数;服务端校验后才落库。

### 2.3 隐私红线(实现与评审都按这个查)
- 不收集:姓名、学校、年级以外的个人信息、人脸、声纹、录音、设备指纹(IMEI/IDFA/广告 id)、精确位置、**复述原文**、**学生向 agent 提出的自由文本**、IP 地址(访问日志不入学习表)。
- 设备 id 是服务端随机生成的 128 位值(Base64URL),**可随时重置**;重置 = 丢弃旧凭证并新建,旧记录可被 `DELETE` 清除。
- 年级/学段只有 `PRIMARY|JUNIOR` 两档,由学生自选。
- 保留期:事件 90 天后由定时清理(`student_event.created_at`);会话进度保留到设备被删或 180 天未活跃。清理任务作为 SQL 提供,不自动执行。

### 2.4 表结构(MySQL 5.6.40:无 JSON、无 CHECK、无外键;SQL 只写不执行)

文件:`vvv-student/src/main/resources/db/student/S001__learning_records.sql`。

| 表 | 主要列 | 说明 |
|---|---|---|
| `student_device` | `id`(VARCHAR(32) 主键),`key_sha256`(CHAR(64)),`audience`,`created_at`,`last_seen_at`,`consent_version` | 只存密钥的 SHA-256;`key_sha256` 唯一索引 |
| `student_session` | `device_id`,`work_id`,`last_step`,`visited`(VARCHAR(40),逗号分隔),`audience`,`entered_at`,`updated_at`,主键(`device_id`,`work_id`) | 恢复进度;不含分数 |
| `student_event` | `id`(BIGINT 自增),`device_id`,`work_id`,`step`,`kind`,`ref`(VARCHAR(24)),`ms`(INT),`client_at`,`created_at` | 结构化事件 |
| `student_gap` | `id`,`device_id`,`work_id`,`script_hash`(VARCHAR(64)),`point_id`(VARCHAR(48)),`state`(`COVERED`/`MISSING`),`created_at` | 每要点一行,便于聚合 |

索引长度:MySQL 5.6 InnoDB 的限制是单列前缀 767 字节、整个索引 3072 字节。`utf8mb4` 下 `VARCHAR(64)` = 256 字节,联合主键(`device_id` 32 个字符 + `work_id` 64 个字符)= 384 字节,都在限制内。

## 3. 诗文包(pack)

学生端页面不直接取底座。`GET /works/{workId}/pack` 返回聚合后的只读视图:

```jsonc
{
  "workId": "work-chun-wang",
  "title": "春望",
  "author": { "personId": "person-du-fu", "name": "杜甫" },
  "textVersionId": "text-chun-wang-v1",
  "lines": [{ "seq": 1, "text": "国破山河在,", "pinyin": null }],
  "annotations": [{ "id": "...", "lineSeq": 1, "kind": "WORD", "audience": "PRIMARY", "text": "..." }],
  "backgrounds": [{ "id": "bg-...", "layer": "CITY", "audience": "JUNIOR", "body": "...", "claimId": "claim-...",
                    "claimKind": "FACT|INTERPRETATION|DRAMATIZATION", "certainty": "KNOWN|LIKELY|DISPUTED|UNKNOWN" }],
  "relations": [{ "backgroundId": "bg-...", "lineSeq": 1 }],
  "writtenAt": { "text": "757 年或 758 年(两说并存)", "certainty": "DISPUTED" },
  "coverageNotice": "..."
}
```

- 每一部分都来自已发布数据;任一部分读取失败返回该部分为空数组并在 `warnings[]` 写明,**不会拿草稿补**。
- 若作品没有已发布的课本版原文,返回 404(与 `chun-wang-sample-spec.md` §8.2「样本未全部发布返回 404」一致)。
- 背景句 `audience` 为空表示全学段通用。

## 4. agent 接口(`student-app/agent`,FastAPI)

| 方法与路径 | 作用 |
|---|---|
| `GET /agent/v1/health` | 返回 `{status, mode: 'script'|'llm', primary_configured: bool}`;**不返回任何密钥、地址或模型名** |
| `POST /agent/v1/turn` | 一个回合:见下 |

请求:
```jsonc
{ "bundle_hash": "…", "work_id": "work-chun-wang", "audience": "PRIMARY",
  "step": "arrive", "action": "open_layer",
  "args": { "layer": "WORLD", "line_seq": 1, "text": null, "history": [] } }
```
- `action ∈ rephrase|hint|ask_why|open_layer|basis|recite_prompt|decline|evaluate_retell|free_text`。`free_text` 由路由器归并到上述动作之一或 `decline`。
- `args.text` ≤ 120 字(`evaluate_retell` ≤ 400 字),超出截断;`history` 最多 3 轮,每轮只含 `{role, say}`。

响应:
```jsonc
{ "role": "narrator", "say": "…", "basis": [{"kind":"script","id":"arrive/WORLD/0","claim_id":"claim-bg-world"}],
  "badge": "FACT", "next": "no_action", "source": "script", "degraded_reason": null,
  "evaluation": null }
```
- `basis[].kind ∈ script|annotation`;`id` 是台词 `{step}/{layer}/{index}` 或注释 `ann:{annotation_id}`(编号规则见 agent-design.md 第 5 节)。
- `source ∈ script|llm`;`degraded_reason ∈ null|disabled|unavailable|timeout|rejected|budget`。
- `evaluation`(仅 `evaluate_retell`):`{covered:[pointId], missing:[pointId], supplement:[{say, basis}]}`。无分数字段。
- 响应永远是 200 + 合法 JSON(请求体不合法才 422);模型或网络任何失败都归结为脚本台词。

## 5. 契约文件与夹具

放在 `runtime/contracts/`(与 `bundle.schema.json` 同处;`check-copies` 只比对已登记文件,新增文件不影响):

| 文件 | 内容 |
|---|---|
| `student-pack.schema.json` | 诗文包 |
| `student-events.schema.json` | 事件批量上报 |
| `agent-turn.schema.json` | agent 请求与响应 |
| `demo/` | 演示夹具:`config.json`、`timeline.json`、`works.chun-wang.json`、`lesson.chun-wang.json`、`pack.chun-wang.json`(`bundle` 沿用同目录的 `sample.chun-wang.json`) |

演示夹具里的诗文、注释与背景沿用 `frontend/public/preview.json`(内容底座的草稿导出),因此**整个演示都标注为未发布**,页面横幅与 `X-Student-Source: demo-fixture` 响应头同时出现;学生模式下真实 Java 返回已发布内容时没有这条横幅。
