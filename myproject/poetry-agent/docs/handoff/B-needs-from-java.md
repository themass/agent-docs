# B 对 `vvv-poetry` 的新增需求

日期:2026-11-06。任务 B 不改 `vvv-poetry`(契约第 3 节)。下面是学生端需要、`vvv-poetry` 目前没有的东西,由用户或任务 A 处理。每一项都写了「现在怎么凑合」,所以都不阻塞本次演示。

## 1. 已发布内容的两个公开读方法(优先级:高)

`PoetryCatalog` 是已发布读取的唯一实现,但缺两样,`vvv-student` 因此自带了 SQL(`StudentSql`、`StudentContentMapper`):

| 需要 | 现在怎么凑合 | 期望 |
|---|---|---|
| 某版本的**已发布注释**(`poetry_annotation`,要求其 claim 是公开 claim、版本已发布且来源已核验) | `StudentContentMapper.annotations`,把 `PoetrySql` 的 `PUBLIC_VERSION`/`PUBLIC_CLAIM` 条件抄了一份(更严) | `PoetryCatalog.annotations(versionId, limit, offset)` |
| **已发布脚本**:`poetry_script` 中 `status='PUBLISHED'` 且 `bundle_hash` 非空,最新一条 | `StudentContentMapper.latestLesson / lessonWorkIds / publishedBundleCount` | `PoetryCatalog.lessonOf(workId)` 与 `isPublishedBundle(hash)` |

落地后删除 `StudentSql` 与这几条查询。`StudentSqlGuardTest` 会在查询丢失 `PUBLISHED` 条件时失败。

## 2. 脚本的发布路径(优先级:高,否则线上没有可分发的课)

`PoetryMediaController` 只能写 DRAFT 脚本,**没有任何端点把脚本置为 `PUBLISHED`、写入 `bundle_hash`/`compiled_at`**。`vvv-student` 只分发 `status='PUBLISHED'` 且 `bundle_hash` 非空的脚本,所以现在真库里一条都不会分发(这是正确的失败方向)。需要:

- 编译器产出 bundle 后回写 `bundle_hash`、`compiled_by`、`compiled_at`;
- 发布闸门:脚本引用的内容、素材都已发布,才允许 `PUBLISHED`;
- 约定 bundle 文件的落点:`vvv-student` 读 `{student.bundle.root}/{hash 前 32 位}/bundle.json` 与 `manifest.json`(与 `content-agent/pipeline/dist/bundles` 的布局一致)。

## 3. 素材登记的公开读(优先级:中)

现有 `GET /api/poetry/v1/assets*` 需要作者令牌。`vvv-student` 为避免向学生端扩散令牌,直接读 `poetry_asset` 的 `PUBLISHED` 行(`StudentContentMapper.assets/asset`)。期望在 `PoetryCatalog` 里提供公开读,同第 1 项。

## 4. 写作时间的属性键(优先级:低,需要确认)

`ContentService.pack` 把 `property_key` 以 `time.` 开头的 claim 当作「写作时间」展示(种子数据里是 `time.span`)。请确认这个约定;如果另有键,告诉我改一处。

## 5. 学段词表(优先级:低,需要内容决定)

Java 词表有 `PRIMARY|JUNIOR|SENIOR`。学生端只有「小学/初中」两档,当前规则:`PRIMARY` 只看 audience 为空或 `PRIMARY` 的注释/背景;`JUNIOR` 看全部。`SENIOR` 内容会被初中看到。若不希望如此,需要内容负责人定。

## 6. 配置项(部署)

`vvv-student` 在 `student.enabled=true` 且 `poetry.enabled=true` 时启用。需要的属性见 `docs/handoff/B.md` 第 4 节;**令牌值不要写进仓库**。
