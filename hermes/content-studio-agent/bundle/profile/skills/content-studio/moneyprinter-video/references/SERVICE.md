# MoneyPrinterTurbo 服务部署

本 Skill 依赖本地或内网运行的 MoneyPrinterTurbo HTTP 服务。

## 快速检查

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8082/docs
curl -s -X POST http://127.0.0.1:8082/api/v1/videos \
  -H "Content-Type: application/json" \
  -d '{"video_subject":"ping","video_script":"测试。","video_language":"zh-CN"}' \
  | python3 -m json.tool
```

期望：docs 返回 200；videos 返回 `data.task_id`。

## 本地启动

```bash
cd /path/to/MoneyPrinterTurbo
cp config.example.toml config.toml   # 首次
# 编辑 config.toml：素材源 API key、LLM、TTS 等
python3 main.py
```

默认监听 `http://127.0.0.1:8082`（8080 留给 OpenInspector LLM Proxy）。

## Docker

```bash
cd /path/to/MoneyPrinterTurbo
docker compose up -d
```

## Content Studio 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `MONEYPRINTER_BASE_URL` | `http://127.0.0.1:8082` | API 根地址 |
| `MONEYPRINTER_VOICE_NAME` | `zh-CN-XiaoxiaoNeural-Female` | edge TTS 音色 |
| `MONEYPRINTER_TIMEOUT` | `600` | 任务最长等待秒数 |
| `MONEYPRINTER_POLL_SECONDS` | `10` | 状态轮询间隔 |

## API 契约（本 Skill 使用）

| 操作 | 方法 | 路径 |
|------|------|------|
| 提交任务 | POST | `/api/v1/videos` |
| 查询状态 | GET | `/api/v1/tasks/{task_id}` |
| 下载成片 | GET | `/api/v1/download/{task_id}/combined-1.mp4` |

任务状态：`state=4` 处理中，`state=1` 完成，`state=-1` 失败。
