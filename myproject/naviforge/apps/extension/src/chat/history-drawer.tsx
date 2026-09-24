import { useEffect, useState } from 'react'
import { ArrowLeft, RotateCcw, Trash2 } from 'lucide-react'

import type { AgentSession } from '../lib/session-model'
import { deleteSession, listSessions } from '../lib/session-store'
import { Button } from '../components/ui/button'
import { STORAGE, type ResumeSessionPayload } from '../lib/settings'
import { sessionToChatEvents } from './chat-events'
import { CollapsibleText } from '../components/chat/collapsible-text'

export function HistoryDrawer({
  open,
  onClose,
  onResume,
}: {
  open: boolean
  onClose: () => void
  onResume: (payload: ResumeSessionPayload) => void
}) {
  const [sessions, setSessions] = useState<AgentSession[]>([])
  const [selectedId, setSelectedId] = useState<string>('')

  useEffect(() => {
    if (!open) return
    void listSessions().then((items) => {
      setSessions(items)
      setSelectedId(items[0]?.id ?? '')
    })
  }, [open])

  if (!open) return null

  const selected = sessions.find((s) => s.id === selectedId) ?? sessions[0]

  async function resume(session: AgentSession): Promise<void> {
    onResume({
      sessionId: session.id,
      threadId: session.threadId,
      task: session.task,
      page: session.page,
    })
    onClose()
  }

  return (
    <div className="absolute inset-0 z-20 flex flex-col bg-background">
      <header className="flex items-center gap-2 border-b px-3 py-2">
        <Button variant="ghost" size="icon" onClick={onClose}>
          <ArrowLeft className="size-3.5" />
        </Button>
        <span className="text-sm font-medium">历史会话</span>
      </header>
      <div className="flex flex-1 min-h-0">
        <div className="w-2/5 border-r overflow-y-auto">
          {sessions.length === 0 ? (
            <p className="p-4 text-xs text-muted-foreground text-center">暂无历史</p>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                className={`w-full text-left px-3 py-2 border-b text-xs hover:bg-muted/50 ${
                  selected?.id === session.id ? 'bg-muted' : ''
                }`}
                onClick={() => setSelectedId(session.id)}
              >
                <strong className="block truncate">{session.task}</strong>
                <small className="text-muted-foreground">
                  {session.records.length} 条 · {new Date(session.updatedAt).toLocaleString()}
                </small>
              </button>
            ))
          )}
        </div>
        {selected ? (
          <div className="flex-1 flex flex-col min-w-0">
            <div className="border-b px-3 py-2 bg-muted/20">
              <p className="text-[10px] uppercase text-muted-foreground">Task</p>
              <p className="text-xs font-medium break-all">{selected.task}</p>
              <div className="mt-2 flex gap-2">
                <Button size="sm" variant="outline" onClick={() => void resume(selected)}>
                  <RotateCcw className="size-3" />
                  继续此会话
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    void deleteSession(selected.id).then(() =>
                      listSessions().then(setSessions)
                    )
                  }}
                >
                  <Trash2 className="size-3" />
                  删除
                </Button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-2 text-xs">
              {sessionToChatEvents(selected.records).map((event) => (
                <div key={event.id} className="rounded border px-2 py-1.5">
                  <span className="text-muted-foreground">
                    {event.turn === undefined ? event.variant : `第 ${event.turn + 1} 步 · ${event.variant}`}
                  </span>
                  <CollapsibleText
                    text={event.body || event.title}
                    maxChars={320}
                    className="mt-0.5 text-xs"
                  />
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
