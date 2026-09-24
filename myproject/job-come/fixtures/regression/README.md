# 回归样本集

匿名化素材，供 `scripts/regression_smoke.sh` 与人工验收使用。

```text
fixtures/regression/
  resumes/   3 份纯文本简历（无真实 PII）
  jds/       6 个 JD：2 匹配 / 2 边缘 / 2 不匹配
  expected/  配对说明
```

## 简历

| 文件 | 画像 |
|------|------|
| `01_backend_zh.txt` | 中文后端 |
| `02_fullstack_en.txt` | 英文全栈 |
| `03_pm_zh.txt` | 中文产品 |

## JD 配对

| 文件 | 相对后端简历 | 相对全栈 | 相对产品 |
|------|--------------|----------|----------|
| `01_match_backend_bytedance.txt` | 匹配 | 边缘 | 不匹配 |
| `02_match_fullstack_saas_en.txt` | 边缘 | 匹配 | 不匹配 |
| `03_edge_devops_startup.txt` | 边缘 | 边缘 | 不匹配 |
| `04_edge_frontend_meituan.txt` | 不匹配 | 边缘 | 不匹配 |
| `05_mismatch_ios_startup.txt` | 不匹配 | 不匹配 | 不匹配 |
| `06_mismatch_data_scientist_en.txt` | 不匹配 | 不匹配 | 不匹配 |

```bash
./scripts/regression_smoke.sh
```
