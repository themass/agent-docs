# 商店截图

Chrome 网上应用店要求：

| 类型 | 尺寸 | 说明 |
|------|------|------|
| **截图** | **1280×800**（推荐）或 640×400 | 至少 1 张，最多 5 张 |
| 小图块 | 440×280 | 可选推广图 |
|  marquee | 1400×560 | 可选 |

本目录 **`store-1280x800/`** 为已裁切、可直传的 1280×800 JPEG。

## 生成

原图备份在 `source/`（首次运行脚本时从会话素材复制）。

```bash
cd docs/myproject/naviforge
python3 scripts/prepare-store-screenshots.py
```

裁切策略：居中 **cover** 到 16∶10，再缩放到 1280×800（不拉伸变形）。

## 上传顺序

见 [`../LISTING_COPY.md`](../LISTING_COPY.md) 文末表格。
