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
| `screenshots/store-1280x800/*.jpg` | 1280×800 | 商品截图（见 `screenshots/README.md`） |

**文案与清单：**

- [`LISTING_COPY.md`](LISTING_COPY.md) — 名称、简短/详细说明、单一用途
- [`../LAUNCH_CHECKLIST.md`](../LAUNCH_CHECKLIST.md) — 上架步骤勾选
- [`ads/AD_SLOTS.md`](ads/AD_SLOTS.md) — Google AdSense **5 个广告位**
- [`../STORE_COMPLIANCE.md`](../STORE_COMPLIANCE.md) — 合规与权限说明

```bash
python3 naviforge/scripts/generate-extension-icons.py
```

商店还需要 **截图**（≥1 张，推荐 1280×800）。已处理素材见 `screenshots/store-1280x800/`；重新生成：

```bash
python3 scripts/prepare-store-screenshots.py
```

从 BrandMark 重新生成（**必须正方形**，勿用非 1:1 的 AI 图直接缩放）：
