# agentkit 的版本与发布

## 为什么要这套东西

agentkit 没有 registry（不发 PyPI / 私有索引），产品通过**入库的 wheel** 安装。
那么"这份 wheel 到底是哪份源码"就只能靠纪律保证，而纪律会松。

真实踩过的坑（job-come 的 `build-release.sh` 里记着）：`agentkit/observability/` 加进去了
但版本号没动，检查脚本比对**版本号**报 "ok 0.1.0"，部署机装了旧 wheel，uvicorn 起来
`ModuleNotFoundError` —— 后端一直停着，直到有人手动重建。

结论：**版本号不能用来判断是不是同一份代码。** 要比对内容。

## 三条规则

1. **源码只有一份**：`libs/agentkit/`（本仓库）。不要在产品目录里改 agentkit 的副本。
2. **版本号必须随内容变**：格式 `0.1.0+YYYYMMDD.<内容哈希前8位>`。
   本地版本段（`+` 之后）在 PEP 440 里不参与比较，所以不会影响解析；
   但它会写进 wheel 文件名和 `RECORD`，一眼就能看出两份是不是同一个东西。
3. **CI / 提交前跑 `--check`**：比对的是**源码内容**与**已提交 wheel** 的内容摘要，
   不是版本号。不一致就红，不允许提交。

## 用法

```bash
# 改完 agentkit 之后：重建 wheel 并分发到各产品
libs/agentkit/scripts/build.sh

# 只检查（CI / pre-commit）：源码与已提交 wheel 是否一致
libs/agentkit/scripts/build.sh --check
```

`build.sh` 做的事：

1. 算源码内容摘要 → 写进版本号 → 构建 wheel；
2. 把同一份 wheel 复制到每个使用它的产品（`myproject/*/…/wheels/`）；
3. `--check` 模式下不构建，只比对。

## 为什么不回到 path 依赖

`docs/standards/公共组件包.md` 早期写的是 `agentkit = { path = "../../libs/agentkit", editable = true }`。
实测它让**部署机装不上**：部署机只有产品目录，没有 monorepo，`uv sync` 直接报
`Distribution not found at: file:///.../libs/agentkit`。

一个构建期输入被当成了运行时依赖。wheel 是同一份代码在"和别的依赖一样"的形态下的样子，
所以保留 wheel；要修的是"多份副本"和"没有校验"，不是退回 path。
