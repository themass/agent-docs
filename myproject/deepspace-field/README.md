# DeepSpace Field

真实太阳系优先的深空探索 Web MVP。

## 当前 MVP

- 独立 Vite + React + React Three Fiber 应用
- 太阳、经典九大行星（八大行星 + 冥王星/矮行星标注）
- 主要卫星：月球、火卫一/二、伽利略卫星、Titan、Enceladus、Triton、Charon 等
- 三种尺度模式：教学压缩 / 电影飞行 / 真实比例
- 5 个 Hubble/Webb 深空旗舰 POI 元数据
- 科学信息面板：真实参数、数据来源、可视化增强说明

## 快速开始

`.env` 已填写后，直接启动：

```bash
cd hermes-dev/deepspace-field
npm install          # 首次运行需要
npm run dev
```

打开 <http://127.0.0.1:5173>。

生产预览（可选）：

```bash
npm run build
npm run preview      # http://127.0.0.1:4173
```

> **说明**：当前 MVP 使用内置太阳系/深空数据，**不依赖** NASA Earth API 或 Mars Rover API（二者已归档）。`.env` 里的 key 主要供后续数据摄取脚本和 v2 增强使用；即使 key 为空也能正常浏览。

## 环境变量

复制 `.env.example`：

```bash
cp .env.example .env
```

当前 MVP 不强依赖外部 key；后续数据摄取/付费增强会用到：

| 变量 | 用途 |
|------|------|
| `VITE_NASA_API_KEY` | NASA Open APIs。开发可先用 `DEMO_KEY` |
| `VITE_CESIUM_ION_TOKEN` | Cesium ion 地球/月球/火星近景 |
| `VITE_HERMES_API_URL` | 后续嵌入 Hermes 时使用 |
| `VITE_HERMES_API_TOKEN` | 后续 Hermes API 鉴权 |

详细注册与 key 配置见 `docs/SETUP_KEYS.md`。

## 目录

```text
src/
  data/              太阳系与深空 POI 数据
  solar/             R3F 太阳系场景、尺度换算
  state/             Zustand 状态
  ui/                目录、科学面板、HUD
scripts/             数据摄取脚本占位
docs/                设计文档、服务接入说明
```

## 设计原则

1. 真实太阳系是 v1 主场。
2. 真实/压缩/电影模式必须明确区分，避免误导。
3. 深空 POI 先做 5 个高质量目标，不铺大而空的目录。
4. Hubble/Webb/Gaia/NASA 数据用离线脚本烘焙，前端加载标准化资产。
5. 付费服务只用于增强效果，不作为 MVP 必要依赖。
