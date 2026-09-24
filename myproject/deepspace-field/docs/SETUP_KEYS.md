# DeepSpace Field 服务注册与 Key 配置

本文记录后续增强效果需要注册的服务、用途和配置位置。

## 1. NASA Open APIs

用途：

- NASA Image and Video Library
- APOD / NeoWs 等公开 API
- 太阳系公开媒体和元数据辅助查询

注册地址：

- <https://api.nasa.gov/>

配置：

```env
VITE_NASA_API_KEY=你的 NASA API key
```

位置：

- `deepspace-field/.env`

说明：

- 本地开发可先使用 `DEMO_KEY`。
- 真实批量摄取建议申请 key，避免 rate limit。

### 已归档 API（请勿再使用）

NASA 已归档以下接口，**当前 MVP 也不依赖它们**：

| 旧 API | 替代方案 |
|--------|----------|
| Earth API | [Earthdata GIBS API](https://www.earthdata.nasa.gov/eosdis/science-system-description/eosdis-components/gibs) |
| Mars Rover API | [Mars Exploration Program](https://mars.nasa.gov/) 公开数据 + MAST / PDS 影像目录 |

地球近景影像/纹理后续优先走：

- **Earthdata GIBS**（全球影像瓦片）
- **NASA Visible Earth**（静态纹理）
- **Cesium ion**（v2 近景地形，见下文第 3 节）

## 2. MAST / STScI（Hubble + Webb）

用途：

- 查询 Hubble / JWST 观测元数据
- 下载 FITS、preview、science products
- 构建 5 个深空旗舰 POI 的真实观测来源

入口：

- MAST: <https://archive.stsci.edu/home>
- JWST MAST API 文档: <https://jwst-docs.stsci.edu/accessing-jwst-data/mast-api-access>
- Astroquery: <https://astroquery.readthedocs.io/en/latest/mast/mast.html>

配置：

- 公开数据通常不需要 token。
- 若访问专有期数据，需要 MAST token。建议放在本机 shell 或 `.env.local`，不要提交：

```env
MAST_API_TOKEN=你的 token
```

使用位置：

- `scripts/ingest_mast.py`

## 3. Cesium ion（可付费）

用途：

- 地球、月球、火星近景
- 全球地形、影像、3D Tiles
- 后续“飞到地球/月球/火星后切换近景场景”

注册地址：

- <https://ion.cesium.com/>
- 价格页：<https://cesium.com/platform/cesium-ion/pricing/>

配置：

```env
VITE_CESIUM_ION_TOKEN=你的 Cesium ion token
```

位置：

- `deepspace-field/.env`

建议：

- v1 不强制依赖。
- v2 若要地球/月球/火星近景效果明显提升，优先接 Cesium ion。
- 企业/商用请确认 Cesium ion 授权和用量限制。

## 4. Aladin Lite / CDS

用途：

- 科学星图模式
- HiPS 巡天图层
- 验证深空 POI 的真实天区位置

项目：

- <https://github.com/cds-astro/aladin-lite/>
- 文档：<https://aladin.cds.unistra.fr/AladinLite/doc/>

注意：

- Aladin Lite 是 GPLv3。若未来做闭源商用产品，建议：
  - 用 iframe/独立模块隔离，或
  - 仅作为开发/验证工具，或
  - 咨询授权兼容性。

## 5. WorldWide Telescope

用途：

- 深空浏览参考
- 教育星图模式
- 可选嵌入式科学地图

项目：

- WebGL Engine: <https://github.com/WorldWideTelescope/wwt-webgl-engine/>
- Web client: <https://github.com/WorldWideTelescope/wwt-web-client/>

授权：

- MIT，集成风险低于 GPL 项目。

## 6. Google 开源工具

### Draco

用途：压缩飞船、探测器、地形 GLB。

项目：<https://github.com/google/draco>

### Filament

用途：PBR/glTF 资产参考、材质检查、未来高质量 wasm/WebGPU 分支。

项目：<https://github.com/google/filament>

### model-viewer

用途：资产预览页，快速查看飞船/探测器 GLB。

项目：<https://github.com/google/model-viewer>

## 7. 本地文件放置建议

不要提交真实密钥。建议：

```text
deepspace-field/
  .env              # 本机 key，不提交
  .env.example      # 可提交模板
  scripts/.env      # Python 摄取脚本可选读取
```

## 8. 第一阶段不需要注册什么？

当前 MVP 可先不注册任何付费服务：

- 太阳系数据先用内置静态参数和后续离线烘焙脚本。
- NASA 可用 `DEMO_KEY`。
- MAST 公开数据通常无需 token。
- Cesium ion 等到做地球/月球/火星近景再接入。
