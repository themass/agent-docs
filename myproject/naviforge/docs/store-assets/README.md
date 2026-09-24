# Chrome Web Store 素材

扩展内图标（随 zip 打包）：

| 文件 | 用途 |
|------|------|
| `apps/extension/public/icon-16.png` … `icon-128.png` | Manifest / 工具栏 / 侧栏 |
| `apps/extension/public/icon.svg` | 矢量源（与 UI `BrandMark` 一致） |

**开发者后台单独上传**（本目录）：

| 文件 | 尺寸 | 用途 |
|------|------|------|
| `icon-128-store.png` | 128×128 | 商店列表图标（必填） |
| `icon-512-store.png` | 512×512 | 高清商店图标 / 营销（建议） |

从 BrandMark 重新生成（**必须正方形**，勿用非 1:1 的 AI 图直接缩放）：

```bash
python3 naviforge/scripts/generate-extension-icons.py
```

商店还需要 **截图**（≥1 张，推荐 1280×800），本目录未包含——需自行截侧栏、截图工作室等界面。
