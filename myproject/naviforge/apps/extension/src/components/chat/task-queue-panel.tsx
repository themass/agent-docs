import { ChevronDown, ChevronUp, GripVertical, ListTodo, Pause, Play, Trash2 } from 'lucide-react'
import { useState, type DragEvent, type ReactNode } from 'react'

import type { QueuedTask } from '@naviforge/runtime'

import { Button } from '../ui/button'
import { cn } from '../../lib/cn'

function QueueFold({
  title,
  count,
  hint,
  open,
  onOpenChange,
  children,
}: {
  title: string
  count: number
  hint: string
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}) {
  return (
    <details
      open={open}
      onToggle={(event) => onOpenChange(event.currentTarget.open)}
      className="border-t border-border/40"
    >
      <summary className="flex cursor-pointer list-none items-center gap-2 px-2 py-1 text-xs [&::-webkit-details-marker]:hidden">
        <span className="font-semibold">{title}</span>
        <span className="rounded-full bg-primary/10 px-1.5 text-[11px] font-medium text-primary">{count}</span>
        <span className="min-w-0 flex-1 truncate text-muted-foreground">{hint}</span>
      </summary>
      <div className="px-2 pb-2">{children}</div>
    </details>
  )
}

export function TaskQueuePanel({
  currentTask,
  pendingTasks,
  steeringCount,
  running,
  onChangePending,
  onSteer,
  onFollowUp,
  queueDisabled,
  onPause,
  paused,
}: {
  currentTask: QueuedTask | null
  pendingTasks: QueuedTask[]
  steeringCount: number
  running: boolean
  onChangePending: (tasks: QueuedTask[]) => void
  onSteer: () => void
  onFollowUp: () => void
  queueDisabled: boolean
  onPause: () => void
  paused: boolean
}) {
  const total = (currentTask ? 1 : 0) + pendingTasks.length
  const [steerOpen, setSteerOpen] = useState(false)
  const [followOpen, setFollowOpen] = useState(false)
  const [dragId, setDragId] = useState<string | null>(null)

  // Keep queue chrome while running (steer/follow-up) or when follow-ups are queued.
  if (!running && pendingTasks.length === 0 && steeringCount === 0 && !currentTask) return null

  function updatePending(id: string, text: string) {
    onChangePending(
      pendingTasks.map((task) => (task.id === id ? { ...task, text } : task)).filter((task) => task.text.trim())
    )
  }

  function removePending(id: string) {
    onChangePending(pendingTasks.filter((task) => task.id !== id))
  }

  function movePending(index: number, delta: number) {
    const target = index + delta
    if (target < 0 || target >= pendingTasks.length) return
    const next = [...pendingTasks]
    const [item] = next.splice(index, 1)
    next.splice(target, 0, item)
    onChangePending(next)
  }

  function onDragStart(event: DragEvent<HTMLDivElement>, id: string) {
    setDragId(id)
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', id)
  }

  function onDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }

  function onDrop(event: DragEvent<HTMLDivElement>, targetId: string) {
    event.preventDefault()
    const sourceId = dragId ?? event.dataTransfer.getData('text/plain')
    setDragId(null)
    if (!sourceId || sourceId === targetId) return
    const from = pendingTasks.findIndex((task) => task.id === sourceId)
    const to = pendingTasks.findIndex((task) => task.id === targetId)
    if (from < 0 || to < 0) return
    const next = [...pendingTasks]
    const [item] = next.splice(from, 1)
    next.splice(to, 0, item)
    onChangePending(next)
  }

  const currentLabel = currentTask?.text ?? (running ? '准备中…' : '')

  return (
    <div data-testid="task-queue" className="shrink-0 border-t border-border/60 bg-muted/30">
      <div className="flex items-center gap-2 px-2 py-1 text-xs">
        <ListTodo className="size-3.5 shrink-0 text-primary" />
        {currentLabel ? (
          <span className="min-w-0 flex-1 truncate text-foreground" title={currentLabel}>
            <span className="font-medium text-primary">{running ? '执行中' : '当前'}</span>
            <span className="text-muted-foreground"> · </span>
            {currentLabel}
          </span>
        ) : (
          <span className="flex-1 text-muted-foreground">任务队列</span>
        )}
        {running ? (
          <button
            type="button"
            className="shrink-0 text-muted-foreground hover:text-foreground"
            onClick={onPause}
            title={paused ? '继续' : '暂停'}
          >
            {paused ? <Play className="size-3.5" /> : <Pause className="size-3.5" />}
          </button>
        ) : null}
      </div>

      {running || steeringCount > 0 || pendingTasks.length > 0 ? (
        <QueueFold
          title="纠偏"
          count={steeringCount}
          hint="Ctrl+Enter"
          open={steerOpen}
          onOpenChange={setSteerOpen}
        >
          <p className="text-[11px] text-muted-foreground">
            {steeringCount ? `${steeringCount} 条将注入下一轮` : '改当前方向，本轮下一步生效'}
          </p>
          {running ? (
            <button
              type="button"
              className="mt-1 text-xs text-primary hover:underline disabled:opacity-40"
              onClick={onSteer}
              disabled={queueDisabled}
            >
              入队纠偏
            </button>
          ) : null}
        </QueueFold>
      ) : null}

      {running || pendingTasks.length > 0 ? (
        <QueueFold
          title="下一问"
          count={pendingTasks.length}
          hint="Enter"
          open={followOpen}
          onOpenChange={setFollowOpen}
        >
          {pendingTasks.length ? (
            <div className="max-h-[min(40vh,20rem)] space-y-1.5 overflow-y-auto">
              {pendingTasks.map((task, index) => (
                <div
                  key={task.id}
                  draggable
                  onDragStart={(event) => onDragStart(event, task.id)}
                  onDragOver={onDragOver}
                  onDrop={(event) => onDrop(event, task.id)}
                  onDragEnd={() => setDragId(null)}
                  className={cn(
                    'flex items-center gap-1 rounded-md border bg-background px-1.5 py-1',
                    dragId === task.id && 'opacity-60 ring-2 ring-primary/30'
                  )}
                >
                  <span
                    className="inline-flex cursor-grab touch-none text-muted-foreground active:cursor-grabbing"
                    title="拖动排序"
                    aria-hidden
                  >
                    <GripVertical className="size-3.5 shrink-0" />
                  </span>
                  <span className="w-4 shrink-0 text-center text-[10px] text-muted-foreground">{index + 1}</span>
                  <input
                    className="min-w-0 flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
                    value={task.text}
                    onChange={(e) => updatePending(task.id, e.target.value)}
                    title={task.text}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    disabled={index === 0}
                    onClick={() => movePending(index, -1)}
                    title="上移"
                  >
                    <ChevronUp className="size-3" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-6"
                    disabled={index === pendingTasks.length - 1}
                    onClick={() => movePending(index, 1)}
                    title="下移"
                  >
                    <ChevronDown className="size-3" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className={cn('size-6 text-destructive')}
                    onClick={() => removePending(task.id)}
                    title="删除"
                  >
                    <Trash2 className="size-3" />
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-muted-foreground">排队下一题，本轮结束后执行</p>
          )}
          {running ? (
            <button
              type="button"
              className="mt-1 text-xs text-primary hover:underline disabled:opacity-40"
              onClick={onFollowUp}
              disabled={queueDisabled}
            >
              入队下一问
            </button>
          ) : null}
        </QueueFold>
      ) : null}
    </div>
  )
}
