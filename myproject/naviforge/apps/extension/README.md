# `@naviforge/extension`

Phase 0：WXT + React MV3 Side Panel。薄壳：消息路由、UI、权限请求。

上架准备见 [`../../docs/STORE_COMPLIANCE.md`](../../docs/STORE_COMPLIANCE.md) 与
[`../../docs/PRIVACY_POLICY.md`](../../docs/PRIVACY_POLICY.md)。发布前设置
`src/lib/compliance.ts` 中的 `PRIVACY_POLICY_URL`。

Agent 逻辑进 `@naviforge/runtime`；DOM 进 `@naviforge/dom-plane`。

脚手架参考：`../../page-agent/packages/extension`（勿直接改那份）。
