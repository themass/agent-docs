# 将内容检查前移到优化阶段

## 原因

此前 `ResumeExportStep` 挂载后才调用完整的事实与表达检查。优化页只有部分确定性的覆盖/篇幅提示，用户直到下载阶段才发现内容问题，往返步骤还会重复启动 reviewer。

## 本次改动

- `useResumeQualityReview` 由 `ResumeStudio` 持有：预览成功、档案版本匹配且有导出权限后自动检查。优化/导出切换不改变检查请求的身份。
- `ResumeQualityPanel` 在优化页侧栏展示真实服务端进度、事实问题、覆盖及篇幅诊断，提供修改档案、重新生成和重试入口。
- 导出页只消费共享结果并提供文件格式下载，不创建 reviewer 请求。保留未确认问题的用户确认选项，模型不可用不伪装成通过。
- 检查按档案 ID/版本、稿件 ID、语言、强度及权限隔离。目标变化取消旧请求并清空旧结果和确认状态；迟到结果不能覆盖新目标。
- 预览完成通知携带实际 draft.profile_version。档案保存后、对应新预览尚未完成时，不检查旧稿。
- StrictMode 延迟自动启动的保护保留；取消时同时清理计时器。

## 边界

- 本次前移的是主动检查，不是自动修改事实或无限重试生成。重新生成仍由用户触发，不宣称每个模型问题都会自动修复。
- 不改模型 prompt、数据库表或导出 API；继续使用现有检查接口和数据库中的 reviewer 状态写入。
- 同一 Studio 生命周期内切换步骤复用完整结果；不承诺刷新浏览器/跨实例后缓存完整检查报告。本次没有新增本地存储。
- 真机浏览器检查未完成：CUA 返回 Mac 锁屏且无法自动解锁。未对用户真实简历发起付费模型验收或写库。

## 验证

在 frontend/web 执行：

- `node --test tests/*.test.cjs`：92 passed / 0 failed。
- `./node_modules/.bin/tsc --noEmit`：通过。
- `git diff --check`：通过。

新增测试覆盖：生成后自动检查、跨步骤复用、取消和迟到响应隔离、目标变化清空确认、不可用与重试、跳过、权限与无稿件、组件输出及档案版本失配保护。

## Follow-up: export review progress regression

- Regression: after moving review ownership to ResumeStudio, ResumeExportStep rendered only a busy sentence, omitting the existing stage progress UI.
- Fix: while the shared review is running and has no verdict, render ExportReviewProgress with the same reviewProgress and reviewStartedAt. No review request, task timer reset, or simulated percentage is introduced. Keep the existing single skip action.
- Regression test renders the real component: 2/4 completed stages, 50% progress, current running model stage, pulse animation and one skip action. Completed, skipped and unavailable settled states do not retain progress animation.
- Verification: frontend test suite 93 passed / 0 failed; TypeScript noEmit passed. Regression test was first run against the old rendering and failed for the missing progressbar.
- No live browser or paid-model verification performed for this follow-up.
