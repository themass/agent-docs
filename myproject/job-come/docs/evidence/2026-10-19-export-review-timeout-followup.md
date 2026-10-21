# 导出质检超时复查（2026-10-19）

## 已读证据

本地 `.data/logs/dev/api.log` 中，同一 draft `rdft_nkklji12bxkae2xy` 在 20:40:51 连续启动两个 request-owned review run：`260208ab7d73`、`c25cf2d93947`。分别于 61.934s 和 63.125s 保存成功。该证据不支持“这两次后端一直没有结果”，但暴露重复发起；不能据此证明用户当前浏览器已正确展示结果。

## 本次补丁

- 导出页自动质检延迟至下一事件循环，effect cleanup 先取消调度，避免开发 StrictMode probe mount 发出重复模型请求。显式重新检查仍立即执行。
- ResumeReviewer 自身增加整体 wall-clock deadline，HTTP SDK 的单次 timeout 不再是唯一保护；独立调用也不能无限等待 fallback/backoff。
- 操作流错误路径的 rollback 最多等待 5 秒，避免失效数据库连接吞掉终止 error 事件。
- 超时结果明确 available=False/reviewer_timeout，不能伪报质检通过。
- 保持 90 秒模型总预算、25 秒单次预算，未用缩短超时伪装成功。

## 验证范围

- 后端 review/reviewer/SSE 聚焦测试：30 passed。
- 前端 Node 聚焦测试：3 passed（含防重复调度源代码守卫，不等同真实浏览器复现）。
- Next production build、类型检查通过。
- git diff --check 通过。
- 未调用真实付费模型，未修改业务数据库，未重启服务。

## 尚待验证

用户当前浏览器端到端返回是否丢失、代理断开是否仍发生；本次测试不能替代带真实网络和模型的验收。不能宣称持续超时已经完全解决。
