/** Annotation union — add a branch here when registering a new shape. */
export type StudioAnnotation =
  | {
      id: string
      type: 'rect'
      x: number
      y: number
      width: number
      height: number
      color: string
      stroke: number
      rotation?: number
    }
  | {
      id: string
      type: 'ellipse'
      x: number
      y: number
      width: number
      height: number
      color: string
      stroke: number
      rotation?: number
    }
  | {
      id: string
      type: 'arrow'
      x1: number
      y1: number
      x2: number
      y2: number
      color: string
      stroke: number
      rotation?: number
    }
  | {
      id: string
      type: 'line'
      x1: number
      y1: number
      x2: number
      y2: number
      color: string
      stroke: number
      rotation?: number
    }
  | {
      id: string
      type: 'pen'
      points: Array<{ x: number; y: number }>
      color: string
      stroke: number
      rotation?: number
    }
  | {
      id: string
      type: 'highlighter'
      points: Array<{ x: number; y: number }>
      color: string
      stroke: number
      rotation?: number
    }
  | {
      id: string
      type: 'text'
      x: number
      y: number
      text: string
      color: string
      fontSize: number
      rotation?: number
    }
  | {
      id: string
      type: 'marker'
      x: number
      y: number
      n: number
      color: string
      size: number
      rotation?: number
    }
  | {
      id: string
      type: 'sticker'
      x: number
      y: number
      emoji: string
      size: number
      rotation?: number
    }
  | {
      id: string
      type: 'mosaic'
      x: number
      y: number
      width: number
      height: number
      block: number
    }
  | {
      id: string
      type: 'blur'
      x: number
      y: number
      width: number
      height: number
      radius: number
    }

export type StudioTool =
  | 'select'
  | 'rect'
  | 'ellipse'
  | 'arrow'
  | 'line'
  | 'pen'
  | 'highlighter'
  | 'text'
  | 'marker'
  | 'sticker'
  | 'mosaic'
  | 'blur'

export type StudioToolMeta = {
  id: StudioTool
  label: string
  /** lucide icon key resolved in UI shell */
  icon: string
}

export const STUDIO_TOOLS: StudioToolMeta[] = [
  { id: 'select', label: '选择 · 拖动移动', icon: 'select' },
  { id: 'rect', label: '方框', icon: 'rect' },
  { id: 'ellipse', label: '椭圆', icon: 'ellipse' },
  { id: 'arrow', label: '箭头', icon: 'arrow' },
  { id: 'line', label: '直线', icon: 'line' },
  { id: 'pen', label: '画笔', icon: 'pen' },
  { id: 'highlighter', label: '荧光笔', icon: 'highlighter' },
  { id: 'text', label: '文字', icon: 'text' },
  { id: 'marker', label: '序号', icon: 'marker' },
  { id: 'sticker', label: '表情', icon: 'sticker' },
  { id: 'mosaic', label: '马赛克', icon: 'mosaic' },
  { id: 'blur', label: '模糊', icon: 'blur' },
]
