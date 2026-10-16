"use client";

type TodoItem = {
  content?: string;
  status?: string;
  id?: string;
};

function label(item: TodoItem): string {
  return item.content || item.id || "任务";
}

/**
 * Status is encoded twice — marker shape and text treatment — so the list is
 * still readable without colour.
 */
function isDone(status?: string) {
  return status === "completed" || status === "done";
}
function isRunning(status?: string) {
  return status === "in_progress" || status === "running";
}

export function AgentPlanTodos({ todos }: { todos: TodoItem[] }) {
  if (!todos.length) return null;
  const doneCount = todos.filter((t) => isDone(t.status)).length;

  return (
    <div className="rounded-lg bg-brand-50/60 p-2.5 ring-1 ring-inset ring-brand-100">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-micro font-semibold uppercase tracking-wider text-brand-700">计划步骤</p>
        <span className="text-micro tabular-nums text-brand-600">
          {doneCount} / {todos.length}
        </span>
      </div>
      <ol className="space-y-1.5">
        {todos.map((item, idx) => {
          const done = isDone(item.status);
          const running = isRunning(item.status);
          return (
            <li key={item.id ?? idx} className="flex items-start gap-2 text-xs">
              <span
                className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-micro font-semibold ${
                  done
                    ? "bg-success-600 text-white"
                    : running
                      ? "bg-brand-600 text-white"
                      : "bg-surface text-ink-500 ring-1 ring-inset ring-brand-200"
                }`}
              >
                {done ? (
                  <svg
                    className="h-2.5 w-2.5"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={3.5}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden
                  >
                    <path d="m4.5 12.75 6 6 9-13.5" />
                  </svg>
                ) : (
                  idx + 1
                )}
              </span>
              <span
                className={
                  done
                    ? "text-ink-500 line-through"
                    : running
                      ? "font-medium text-brand-800"
                      : "text-ink-700"
                }
              >
                {label(item)}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
