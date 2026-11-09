# vendor/

上游源码，整棵目录原样复制，不是包依赖。我们在上游之上迭代，改动只放在 `src/` 的适配器里，尽量不改 vendor 内的文件。

| 目录 | 上游 | 版本 | 提交 | 许可证 |
|---|---|---|---|---|
| `mem0/` | https://github.com/mem0ai/mem0 | mem0ai 2.2.1（tag v2.2.1） | 94c3fe9f238f3dbf29c9ce98643bd71eb13077cd | Apache-2.0（见 `mem0/LICENSE`） |

升级流程：在临时目录 clone 新的 tag，比对差异，再替换本目录并更新本表。不要在 vendor 目录里直接提交功能改动。
