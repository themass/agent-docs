import type { StudioTool } from '../draw-kit/annotation-types.js'

export type ToolGroupId = 'shapes' | 'lines' | 'stickers'

export type ToolGroup = {
  id: ToolGroupId
  label: string
  hint: string
  tools: StudioTool[]
}

export const TOOL_GROUPS: ToolGroup[] = [
  {
    id: 'shapes',
    label: '图形',
    hint: '拖拽画出方框或椭圆 · 单击已有图形可拖动/缩放',
    tools: ['rect', 'ellipse'],
  },
  {
    id: 'lines',
    label: '线条',
    hint: '拖拽画箭头或直线 · 无需切到「选择」即可点选移动',
    tools: ['arrow', 'line'],
  },
]

export const STICKER_GROUP = {
  id: 'stickers' as const,
  label: '表情贴纸',
  hint: '双击画布粘贴 · 单击选中后可拖动和缩放',
}

export const RAIL_TOOLS: StudioTool[] = [
  'select',
  'pen',
  'highlighter',
  'text',
  'marker',
  'mosaic',
  'blur',
]

export const TOOL_HINTS: Record<StudioTool, string> = {
  select: '选择 · 单击选中 · 拖动移动 · 角点缩放',
  rect: '方框 · 拖拽绘制 · 单击已有图形可编辑',
  ellipse: '椭圆 · 拖拽绘制 · 单击已有图形可编辑',
  arrow: '箭头 · 拖拽起点到终点',
  line: '直线 · 拖拽起点到终点',
  pen: '画笔 · 按住拖动自由绘制',
  highlighter: '荧光笔 · 半透明高亮标记',
  text: '文字 · 点画布输入 · 回车换行 · Ctrl+Enter 完成',
  marker: '序号 · 点击放置数字标记',
  sticker: '表情 · 双击粘贴 · 单击选中缩放',
  mosaic: '马赛克 · 框选区域打码',
  blur: '模糊 · 框选区域虚化',
}

export const TOOL_SHORT_LABELS: Record<StudioTool, string> = {
  select: '选择',
  rect: '方框',
  ellipse: '椭圆',
  arrow: '箭头',
  line: '直线',
  pen: '画笔',
  highlighter: '荧光',
  text: '文字',
  marker: '序号',
  sticker: '表情',
  mosaic: '马赛克',
  blur: '模糊',
}
