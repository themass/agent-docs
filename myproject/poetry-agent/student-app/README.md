# student-app — 学生端项目

学生端**不调用内容生产 agent、不读 DRAFT**,只消费已发布并编译好的 Scene Bundle 和 Java 分发的已发布内容。

```text
student-app/
  frontend/    学生端页面(零依赖 ES 模块;legacy/ 是旧的内部预览页)
  agent/       学生端讲诗 agent(Python/FastAPI;脚本优先,模型只做措辞)
  runtime/     contracts(含诗文包等契约与演示夹具) · scene-runtime · platform-web
  production/  素材任务体系与 2D 角色(任务 C)
  design/      学生端整体设计(先读 architecture.md)
```

Java 侧是 `testserverV/vvv-student`(`/api/student/v1`)。交接说明:`../docs/handoff/B.md`。

## 现在就能跑的

在平台根目录(`poetry-agent-platform/`):

```bash
make student-dev      # 前端 + /api/student/v1 演示夹具 + agent;不连数据库,不连 Java
make student-verify   # 构建与静态检查(不跑测试套件)
make student-web      # 组装静态目录,可托管,也是 Capacitor 的 webDir
```

演示数据来自内容底座的草稿导出,页面顶部会显示「演示数据,还没有发布」。

## `runtime/` 里是跨 Web / 移动壳共用的内核

| 目录 | 内容 |
|---|---|
| `scene-runtime/` | 框架无关内核:五步状态机 + 降级链 + 离线预取预算(唯一实现) |
| `platform-web/` | scene-runtime 能力接口的 Web 实现;App 壳替换的就是这一层 |
| `contracts/` | bundle 契约与样例;`demo/` 是学生端演示夹具 |

内容生产项目(`../content-agent/`)在 `pipeline/` 里带有自己的一份 `scene-runtime` 与契约,用于校验与编译;两份是否一致用 `make check-copies` 检查。

## 内核为什么这样切(移动端就绪的落点)

| 纪律 | 代码位置 | 违反后的代价 |
|---|---|---|
| 运行时框架无关、能力靠注入 | `runtime/scene-runtime/src/capabilities.ts`、`frontend/src/platform.js` | 换壳 = 重写 |
| 包体与设备预算是硬边界 | `src/degrade.ts` `ceiling()` | 中端安卓卡死、iOS 被杀 |
| 离线优先、内容寻址 | `src/offline.ts`、`frontend/src/data/repo.js`、`sw.js` | 地铁里白屏 |
| 五步不是关卡 | `src/machine.ts`、`frontend/src/lesson/session.js`:任意进入、可回看、不判分 | 学习路径被产品强行规定 |
| 文本永远是降级终点 | `degrade.ts` 找不到可用资产时必须落到 L0 | 断网即无内容 |
