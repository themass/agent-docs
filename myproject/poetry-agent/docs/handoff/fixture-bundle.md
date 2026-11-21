# 测试夹具包（《春望》）：用法与替换方式

**这是测试数据，不是内容。** 目的：在真实史料核查完成之前，让「编译 → 分发 → 学生端」整条链路能真实跑通，跑通后再替换。

## 它是什么

| 项 | 内容 |
|---|---|
| 编译命令 | `python3 scripts/maintenance/build_fixture_bundle.py`（加 `--check` 只验证、不写任何文件） |
| 产物 | `content-agent/pipeline/dist/bundles/a1a919c215d656000910a72ef2d01f8a/{bundle,manifest}.json` |
| 剧本 | 样本剧本 `content-agent/pipeline/contracts/sample.chun-wang.json`，但**素材表换成** `student-app/production/published/bundles/chun-wang.assets.json`（26 项，来自素材登记簿） |
| 事实 | 夹具事实，**不是**数据库。manifest 里 `facts_source` = `FIXTURE — not from the database; the scholarship is still PENDING` |
| 素材 | 26 项全部是代码生成的占位（`not_for_release`），有真实文件和真实 SHA-256 |
| 降级预案 | L0 需 12 项素材，L1 15，L2 25，L3 26，L4 26 |

相比 `dist/` 里原有的包（`60279d33…`）：原包素材表里是 8 项假哈希（`0f0f0f…`、`1111…`）且引用了登记簿里不存在的 `a-changan-dusk-mini`；新包的每个素材都对应磁盘上真实存在的文件。原包未被改动。

## 为什么它不会混进生产

1. 编译用的事实带 `FIXTURE` 标签，脚本在标签缺失时拒绝编译，编译后还会再检查 manifest。
2. 脚本拒绝使用任何**没有**标 `placeholder` 的素材：一旦素材表里混进了真素材，它就不再是测试数据，脚本会停下来。
3. 生产通道闸门拒绝全部 26 项：
   `node student-app/production/tools/prod.mjs bundle-refs chun-wang --channel production` → 退出码 1，列出 26 个占位素材。闸门不改动素材表文件（运行前后哈希一致）。
4. 真数据库的校验仍是 **BLOCKED（26 条，全在内容和核查侧）**，没有被这套数据掩盖：
   `node content-agent/pipeline/tools/scene-validator/validate.mjs <剧本> --facts content-agent/pipeline/contracts/facts.chun-wang.json`

## 谁需要接上

学生端当前的演示包 `student-app/runtime/contracts/demo/pack.chun-wang.json` 是**纯文字**内容，其中没有任何素材引用，所以这 26 个素材目前没有前端在用。要在浏览器里真正看到角色、场景图和降级，需要学生端会话把前端接到这个 bundle（或登记簿）上。这属于 `student-app/` 的所有者，本说明不替它做。

## 如何替换成真实内容

按顺序，每一步都有现成的闸门：

1. 出处核查完成、相关 claim 发布 → 用 `facts.chun-wang.json`（真库导出）重新跑校验，目标 `verdict: COMPILES`，此时不再需要夹具事实。
2. 每个占位任务有真素材交付 → `prod.mjs check` → 人工验收 → `prod.mjs publish`；登记簿里对应项的 `placeholder` 标记消失。
3. 全部占位替换后，`bundle-refs --channel production` 退出码为 0，再用真事实编译，`manifest.facts_source` 不再带 `FIXTURE`。
4. 删除夹具包目录和 `build_fixture_bundle.py` 即可，没有别的地方依赖它。

## 已验证与未验证

- **已实际运行**：`--check` 与正式编译（12 条规则通过，新增 2 个文件，既有文件内容未变，`index.json` 仅新增一条记录）；生产闸门退出码 1；`registry-check` 26 项 0 错误；ruff 通过。
- **没有验证**：前端是否能加载这个包；占位 SVG 与音频在真机上的表现；包体大小与弱网预算；`make test-all` 里新增的这一步（见下）。
