# Hindsight 安全、隔离与信任边界

## 1. 安全模型

Hindsight 的安全边界不是单一的 `bank_id` WHERE 条件，而是多层组合：

```text
Transport auth
  → RequestContext
  → TenantExtension / schema selection
  → Bank authorization
  → tag read/write scope
  → operation validator
  → store query / write
  → audit / webhook / export policy
```

任何新 API 或新后台任务都必须沿用这条链；直接在路由或后台 SQL 中绕过 MemoryEngine，会产生租户越权、scope 泄漏或不可审计写入。

## 2. RequestContext

`hindsight_api.models.RequestContext` 承载：

- api key / api key id；
- tenant id；
- internal / MCP already authenticated 标记；
- allowed bank IDs；
- retry count；
- cooperative cancellation；
- allowlisted passthrough headers；
- 已认证的 tenant schema。

它不是普通业务参数，而是每次操作的身份和策略上下文。不要把整个 HTTP request、Authorization header 或未筛选的用户 headers 直接传给 LLM 或扩展。

## 3. Tenant Extension 与 schema 隔离

`extensions/tenant.py`、`extensions/loader.py` 和可选的 `hindsight-extensions` 实现可以把认证身份映射到 tenant/schema。部署可能使用：

- 静态 API key → tenant；
- Supabase/JWT 等外部身份 → tenant；
- 每租户 schema；
- 共享 schema + Bank ID 过滤；
- 组合策略。

`engine/schema.py` 对 memories store 所有表做了访问保护：一般模块不应直接拼接 `memory_units`、`documents` 等存储表名，而应通过 memories store。这是防止跨 schema/tenant SQL 绕过的工程护栏。

## 4. Bank 与 tag scope

Bank 是默认的逻辑读写边界；tag scope 可以在 Bank 内进一步限制：

- 可见的事实、documents、mental models、directives 和 knowledge nodes；
- retain 的写入 tags；
- bank-wide 管理操作是否被拒绝；
- export、delete、refresh 是否允许跨 scope。

使用 compound tag groups 时，应明确 AND/OR/NOT 语义，避免把“可见集合”误当成“用户拥有整个 Bank”。任何带 scope 的请求都应同时测试读、写、删除、异步和后台回调。

## 5. Memory Defense

`extensions/memory_defense.py` 位于 retain 入口附近，可在写入前检测恶意、敏感或不应进入长期记忆的内容，执行 block 或 redact。它的安全目标与 prompt injection 防御不同：

- prompt injection 防止记忆内容操纵 Agent；
- memory defense 防止不可信输入污染或外泄长期记忆。

防御动作应进入操作结果和审计，不能静默丢弃所有输入而让调用者误以为完整写入。

## 6. Reflect 的证据边界

Reflect 必须遵循：

1. 只引用实际检索到的 memory/source IDs；
2. tool error 时失败或显式降级，不把错误文本当成证据；
3. observation/mental model 是派生知识，应能追溯到 raw facts；
4. directives 是行为规则，不应伪装成用户事实；
5. 外部 context 与 Bank memory 要在提示中区分来源和可信度。

这能降低幻觉引用、陈旧 observation 和用户输入注入造成的错误回答。

## 7. 敏感数据与日志

- 原文、附件、memory text 可能包含个人信息和密钥，不应默认写入 debug log；
- LLM trace、prompt preview、LLM request 记录应有开关、访问控制和 retention；
- metrics 不要使用高基数、可识别的原文作为 label；
- webhook payload 只发送必要的 operation/source 信息，并验证签名/重放策略；
- export、audit-log、knowledge-base 导出是高敏感操作，应单独鉴权和审计。

## 8. 数据生命周期

建议为以下对象设置不同保留策略：

| 对象 | 风险 | 策略方向 |
|---|---|---|
| raw documents/chunks | 含原始 PII/附件 | 最短必要保留或加密 |
| memory_units | 长期画像与推断 | 可删除、可修订、可审计 |
| observations | 可能放大错误/敏感推断 | 保留 source、支持失效与重建 |
| mental models | 策展内容、可能公开给 Agent | 权限和版本管理 |
| LLM requests/traces | prompt、response、token | 严格访问、短保留 |
| audit logs | 身份、操作、结果 | 防篡改和合规保留 |
| async operation errors | 可能包含 provider 返回内容 | 脱敏和限长 |

## 9. 安全测试清单

- Bank A 的 recall/reflect 不得看到 Bank B；
- tenant A 不得通过 alias、document ID、memory ID、operation ID 或 attachment ID 访问 tenant B；
- tag scoped key 不得读/写 scope 外数据；
- 取消和重试不得越权执行原请求之外的 Bank；
- export/import 不得绕过 scope；
- webhook 重试不得重复造成不可幂等写入；
- malformed tool call、structured output、provider 错误不应把内部堆栈返回客户端；
- prompt/trace/log 中不应泄漏 API key、数据库 URL、附件原文。
