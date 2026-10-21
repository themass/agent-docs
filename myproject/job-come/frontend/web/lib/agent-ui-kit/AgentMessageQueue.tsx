"use client";

import { useEffect, useRef, useState, type DragEvent } from "react";

import { cn } from "./cn";
import { defaultAgentUiKitClassNames } from "./defaultClassNames";
import { IconCheck, IconGrip, IconPencil, IconQueueSubmit, IconTrash } from "./icons";
import type { AgentMessageQueueProps, AgentQueueItem } from "./types";

/**
 * Codex/Cursor-style follow-up message queue: reorder, run now, edit, remove.
 * All copy via `labels`; styling via `classNames` overrides.
 */
export function AgentMessageQueue({
  items,
  busy,
  priorityCount = 0,
  labels,
  onRemove,
  onReorder,
  onRunNow,
  onEdit,
  onClearPriority,
  classNames,
  defaultOpen = true,
}: AgentMessageQueueProps) {
  const styles = { ...defaultAgentUiKitClassNames, ...classNames };
  const [open, setOpen] = useState(defaultOpen);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const editRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (editingId) editRef.current?.focus();
  }, [editingId]);

  if (!busy && items.length === 0 && priorityCount === 0) return null;

  function handleDragStart(event: DragEvent<HTMLLIElement>, id: string): void {
    if (editingId) return;
    setDraggingId(id);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", id);
  }

  function handleDragOver(event: DragEvent<HTMLLIElement>, index: number): void {
    event.preventDefault();
    setOverIndex(index);
  }

  function handleDrop(event: DragEvent<HTMLLIElement>, index: number): void {
    event.preventDefault();
    const id = draggingId ?? event.dataTransfer.getData("text/plain");
    if (id) onReorder(id, index);
    setDraggingId(null);
    setOverIndex(null);
  }

  function handleDragEnd(): void {
    setDraggingId(null);
    setOverIndex(null);
  }

  function startEdit(task: AgentQueueItem): void {
    setEditingId(task.id);
    setDraft(task.content);
  }

  function commitEdit(id: string): void {
    const text = draft.trim();
    if (text) onEdit(id, text);
    setEditingId(null);
    setDraft("");
  }

  function cancelEdit(): void {
    setEditingId(null);
    setDraft("");
  }

  const actionBar =
    "flex shrink-0 items-center gap-0.5 opacity-100 sm:opacity-0 sm:transition sm:group-hover:opacity-100 sm:group-focus-within:opacity-100";

  return (
    <div className={styles.queueRoot}>
      <button type="button" className={styles.queueHeaderButton} onClick={() => setOpen((v) => !v)}>
        <span className={styles.queueTitle}>{labels.title}</span>
        <span className={styles.queueBadge}>{items.length + priorityCount}</span>
        <span className={styles.queueHint}>{busy ? labels.hintBusy : labels.hintIdle}</span>
        <span className={styles.queueChevron}>{open ? "▾" : "▸"}</span>
      </button>

      {open ? (
        <div className="mt-2 space-y-2">
          {priorityCount > 0 && onClearPriority ? (
            <div className={styles.queuePriorityBanner}>
              <div className="flex items-center justify-between gap-2">
                <span className={styles.queuePriorityTitle}>{labels.priorityTitle(priorityCount)}</span>
                <button type="button" className={styles.queuePriorityClear} onClick={onClearPriority}>
                  {labels.priorityClear}
                </button>
              </div>
              <p className={styles.queuePriorityHint}>{labels.priorityHint}</p>
            </div>
          ) : null}

          {items.length > 0 ? (
            <ul className="space-y-1.5">
              {items.map((task, idx) => {
                const editing = editingId === task.id;
                return (
                  <li
                    key={task.id}
                    draggable={!editing}
                    onDragStart={(e) => handleDragStart(e, task.id)}
                    onDragOver={(e) => handleDragOver(e, idx)}
                    onDrop={(e) => handleDrop(e, idx)}
                    onDragEnd={handleDragEnd}
                    className={cn(
                      styles.queueRow,
                      draggingId === task.id && styles.queueRowDragging,
                      overIndex === idx && draggingId && draggingId !== task.id && styles.queueRowDropTarget,
                    )}
                  >
                    <span
                      className={cn(styles.queueGrip, editing && "opacity-30 cursor-default")}
                      title={labels.dragHandleTitle}
                      aria-hidden
                    >
                      <IconGrip />
                    </span>
                    <span className={styles.queueIndex}>{idx + 1}</span>
                    {editing ? (
                      <textarea
                        ref={editRef}
                        value={draft}
                        rows={3}
                        className={styles.queueEditArea}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Escape") {
                            e.preventDefault();
                            cancelEdit();
                          }
                          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                            e.preventDefault();
                            commitEdit(task.id);
                          }
                        }}
                      />
                    ) : (
                      <span className={styles.queueBody}>{task.content}</span>
                    )}
                    <div className={actionBar}>
                      {editing ? (
                        <>
                          <button
                            type="button"
                            className={cn(styles.queueIconButton, styles.queueIconButtonAccent)}
                            onClick={() => commitEdit(task.id)}
                            title={labels.saveEditTitle}
                            aria-label={labels.saveEditAria}
                          >
                            <IconCheck />
                          </button>
                          <button
                            type="button"
                            className={styles.queueIconButton}
                            onClick={cancelEdit}
                            title={labels.cancelEditTitle}
                            aria-label={labels.cancelEditAria}
                          >
                            ×
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            className={styles.queueIconButton}
                            onClick={() => onRunNow(task.id)}
                            title={labels.runNowTitle(busy)}
                            aria-label={labels.runNowAria(busy)}
                          >
                            <IconQueueSubmit />
                          </button>
                          <button
                            type="button"
                            className={styles.queueIconButton}
                            onClick={() => startEdit(task)}
                            title={labels.editTitle}
                            aria-label={labels.editAria}
                          >
                            <IconPencil />
                          </button>
                          <button
                            type="button"
                            className={cn(styles.queueIconButton, styles.queueIconButtonDanger)}
                            onClick={() => onRemove(task.id)}
                            title={labels.removeTitle}
                            aria-label={labels.removeAria}
                          >
                            <IconTrash />
                          </button>
                        </>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
