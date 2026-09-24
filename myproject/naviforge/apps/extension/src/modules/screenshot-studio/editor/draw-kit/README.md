# Draw Kit（截图标注库）

截图工作室的标注能力由 **Draw Kit** 提供：图形用注册表（registry），交互用工具处理器（tool handlers），**禁止**在 `ScreenshotEditor` / `render-export` 里堆 `if (type === …)`。

## 模块

| 路径 | 职责 |
|------|------|
| `core/shape-registry.ts` | 图形定义注册、`draw` / `hitTest` / `translate` / `resize` |
| `shapes/register-shapes.ts` | 各图形的具体实现 + `registerAllShapes()` |
| `tools/pointer-handlers.ts` | 指针交互（选择、拖拽创建、移动、缩放） |
| `annotation-types.ts` | `StudioAnnotation` 联合类型、`StudioTool` 列表 |
| `presets.ts` | 颜色、线宽、字号等预设 |

## 新增一种图形（3 步）

### 1. 在 `annotation-types.ts` 增加类型分支

```typescript
| { id: string; type: 'my-shape'; x: number; y: number; ... }
```

并在 `StudioTool` / `STUDIO_TOOLS` 里增加工具 id（若需要新工具）。

### 2. 在 `shapes/register-shapes.ts` 注册定义

```typescript
registerShapeDefinition({
  type: 'my-shape',
  layer: 'vector', // 或 'region'（马赛克/模糊类，需 env.image）
  traits: { stroke: true }, // 侧栏显示哪些调节项
  bounds: (ann) => ({ x: ann.x, y: ann.y, width: ann.w, height: ann.h }),
  draw: (ctx, ann, env) => { /* canvas */ },
  hitTest: (ann, x, y) => boolean,
  translate: (ann, dx, dy) => ({ ...ann, x: ann.x + dx, ... }),
  resize: (ann, handle, x, y, origin) => ({ ...ann, ...resizeBox(handle, x, y, origin) }),
})
```

`registerAllShapes()` 在 `ensureDrawKit()` 时执行一次。

### 3. 在 `tools/pointer-handlers.ts` 接上创建逻辑

- **框选类**（矩形/椭圆/马赛克/模糊）：扩展 `create-box` 的 `shape` 联合类型，在 `handlePointerUp` 里 `addAnnotation`。
- **拖线类**（箭头/直线）：扩展 `create-line`。
- **轨迹类**（画笔/荧光笔）：扩展 `create-path`。
- **点击放置**（文字/序号/表情）：在 `handlePointerDown` 里像 `marker` / `sticker` 一样处理。

侧栏控件：在 `ScreenshotEditor.tsx` 根据 `editor.tool` 与 `shapeTraits` 显示线宽/字号等（已有模式）。

## 设计模式

- **Registry**：图形类型 → `ShapeDefinition`，渲染与命中统一走 `shape-registry.ts`。
- **Strategy**：每种 `StudioTool` 的指针行为集中在 `pointer-handlers.ts`，不按工具拆散到 UI 组件。
- **数据驱动**：标注 JSON 可序列化；导出 PNG 时对 `vector` / `region` 分层绘制。
