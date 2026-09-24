"use client";

type TodoItem = {
  content?: string;
  status?: string;
  id?: string;
};

function label(item: TodoItem): string {
  return item.content || item.id || "任务";
}

function statusStyle(status?: string): string {
  if (status === "completed" || status === "done") return "text-emerald-700 line-through";
  if (status === "in_progress" || status === "running") return "text-brand-700 font-medium";
  return "text-slate-700";
}

export function AgentPlanTodos({ todos }: { todos: TodoItem[] }) {
  if (!todos.length) return null;
  return (
    <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-2.5">
      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-indigo-700">计划步骤</p>
      <ol className="space-y-1.5">
        {todos.map((item, idx) => (
          <li key={item.id ?? idx} className="flex items-start gap-2 text-[11px]">
            <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-white text-[9px] font-semibold text-indigo-700 ring-1 ring-indigo-200">
              {idx + 1}
            </span>
            <span className={statusStyle(item.status)}>{label(item)}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
