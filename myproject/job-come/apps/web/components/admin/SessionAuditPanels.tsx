"use client";

import { useMemo, useState, type ReactNode } from "react";

import type {
  AdminCheckpointMessage,
  AdminInventory,
  AdminTimelineTurn,
} from "@/lib/api/admin";

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-CN");
  } catch {
    return iso;
  }
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform duration-150 ${open ? "rotate-90" : ""}`}
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden
    >
      <path d="M7.3 4.7a1 1 0 011.4 0l5 5a1 1 0 010 1.4l-5 5a1 1 0 11-1.4-1.4L11.58 10 7.3 5.7a1 1 0 010-1.4z" />
    </svg>
  );
}

function Accordion({
  title,
  meta,
  defaultOpen = false,
  children,
}: {
  title: ReactNode;
  meta?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand-500"
      >
        <Chevron open={open} />
        <span className="min-w-0 flex-1 text-[13px] font-medium text-slate-800">{title}</span>
        {meta ? <span className="shrink-0 text-[11px] text-slate-500">{meta}</span> : null}
      </button>
      {open ? <div className="border-t border-slate-100 px-3 py-2">{children}</div> : null}
    </section>
  );
}

function EventBadge({ type }: { type: string }) {
  const tone =
    type === "skill"
      ? "bg-sky-100 text-sky-800"
      : type === "thinking"
        ? "bg-amber-100 text-amber-900"
        : type.startsWith("tool")
          ? "bg-violet-100 text-violet-800"
          : type.includes("subagent")
            ? "bg-blue-100 text-blue-800"
            : type === "error"
              ? "bg-rose-100 text-rose-800"
              : "bg-slate-100 text-slate-700";
  return <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${tone}`}>{type}</span>;
}

function EventRow({ ev }: { ev: AdminTimelineTurn["events"][number] }) {
  const [open, setOpen] = useState(false);
  const hasBody = Boolean(ev.content) || Boolean(ev.payload && Object.keys(ev.payload).length);
  return (
    <div className="rounded-md border border-slate-100 bg-slate-50/80">
      <button
        type="button"
        disabled={!hasBody}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full cursor-pointer items-center gap-2 px-2 py-1.5 text-left disabled:cursor-default"
      >
        {hasBody ? <Chevron open={open} /> : <span className="w-3.5" />}
        <EventBadge type={ev.event_type} />
        <span className="text-[10px] text-slate-400">{fmtTime(ev.created_at)}</span>
        {ev.payload?.name ? (
          <span className="truncate font-mono text-[10px] text-slate-600">{String(ev.payload.name)}</span>
        ) : null}
      </button>
      {open && hasBody ? (
        <div className="space-y-1 border-t border-slate-100 px-2 py-1.5">
          {ev.content ? (
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-[11px] text-slate-700">{ev.content}</pre>
          ) : null}
          {ev.payload && Object.keys(ev.payload).length > 0 ? (
            <pre className="max-h-40 overflow-auto rounded bg-white p-2 font-mono text-[10px] text-slate-600">
              {JSON.stringify(ev.payload, null, 2)}
            </pre>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function TimelinePanel({ turns }: { turns: AdminTimelineTurn[] }) {
  if (turns.length === 0) {
    return <p className="text-sm text-slate-500">暂无审计记录</p>;
  }
  return (
    <div className="space-y-2">
      {turns.map((turn, idx) => (
        <Accordion
          key={turn.turn_index}
          defaultOpen={idx === turns.length - 1}
          title={`Turn #${turn.turn_index + 1}`}
          meta={`${fmtTime(turn.started_at)} · ${turn.events.length} events`}
        >
          <div className="space-y-2">
            {turn.user_message ? (
              <div>
                <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-400">用户</p>
                <div className="rounded-lg bg-slate-900 px-3 py-2 text-[12px] text-white whitespace-pre-wrap">
                  {turn.user_message}
                </div>
              </div>
            ) : null}
            {turn.events.length > 0 ? (
              <div className="space-y-1">
                <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">事件</p>
                {turn.events.map((ev) => (
                  <EventRow key={ev.id} ev={ev} />
                ))}
              </div>
            ) : null}
            {turn.assistant_message ? (
              <div>
                <p className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-400">助手</p>
                <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-[12px] whitespace-pre-wrap text-slate-800">
                  {turn.assistant_message}
                </div>
              </div>
            ) : null}
          </div>
        </Accordion>
      ))}
    </div>
  );
}

export function CheckpointPanel({
  messages,
  meta,
}: {
  messages: AdminCheckpointMessage[];
  meta: { count: number; thread: string } | null;
}) {
  return (
    <div className="space-y-2">
      {meta ? (
        <p className="text-[11px] text-slate-500">
          {meta.count} checkpoints · thread {meta.thread} · {messages.length} messages
        </p>
      ) : null}
      {messages.map((msg) => {
        const preview =
          typeof msg.content === "string"
            ? msg.content.slice(0, 100)
            : JSON.stringify(msg.content).slice(0, 100);
        const chars = typeof msg.content === "string" ? msg.content.length : preview.length;
        return (
          <Accordion
            key={msg.index}
            defaultOpen={false}
            title={
              <span className="flex items-center gap-2">
                <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] font-normal">{msg.role}</span>
                <span className="truncate font-normal text-slate-600">{preview || "(empty)"}</span>
              </span>
            }
            meta={`${chars} chars${msg.tool_calls.length ? ` · ${msg.tool_calls.length} tools` : ""}`}
          >
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap text-[11px] text-slate-800">
              {typeof msg.content === "string" ? msg.content : JSON.stringify(msg.content, null, 2)}
            </pre>
            {msg.tool_calls.length > 0 ? (
              <pre className="mt-2 max-h-40 overflow-auto rounded bg-violet-50 p-2 font-mono text-[10px]">
                {JSON.stringify(msg.tool_calls, null, 2)}
              </pre>
            ) : null}
            {Object.keys(msg.additional_kwargs).length > 0 ? (
              <pre className="mt-2 max-h-32 overflow-auto rounded bg-slate-50 p-2 font-mono text-[10px] text-slate-600">
                {JSON.stringify(msg.additional_kwargs, null, 2)}
              </pre>
            ) : null}
          </Accordion>
        );
      })}
    </div>
  );
}

function ParamTable({ parameters }: { parameters: Record<string, unknown> }) {
  const props = (parameters.properties as Record<string, { type?: string; description?: string }> | undefined) ?? {};
  const required = new Set((parameters.required as string[] | undefined) ?? []);
  const names = Object.keys(props);
  if (names.length === 0) {
    return <p className="text-[11px] text-slate-400">无参数 schema</p>;
  }
  return (
    <table className="w-full text-left text-[11px]">
      <thead>
        <tr className="text-slate-400">
          <th className="py-1 pr-2 font-medium">参数</th>
          <th className="py-1 pr-2 font-medium">类型</th>
          <th className="py-1 font-medium">说明</th>
        </tr>
      </thead>
      <tbody>
        {names.map((name) => (
          <tr key={name} className="border-t border-slate-100 align-top">
            <td className="py-1 pr-2 font-mono text-slate-800">
              {name}
              {required.has(name) ? <span className="ml-1 text-rose-500">*</span> : null}
            </td>
            <td className="py-1 pr-2 text-slate-500">{props[name]?.type ?? "—"}</td>
            <td className="py-1 text-slate-600">{props[name]?.description ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function InventoryPanel({ inventory }: { inventory: AdminInventory }) {
  const [q, setQ] = useState("");
  const query = q.trim().toLowerCase();
  const toolByName = useMemo(
    () => Object.fromEntries(inventory.tools.map((t) => [t.name, t])),
    [inventory.tools],
  );

  const match = (parts: Array<string | null | undefined>) => {
    if (!query) return true;
    return parts.some((p) => (p ?? "").toLowerCase().includes(query));
  };

  return (
    <div className="space-y-3">
      <label className="block">
        <span className="sr-only">筛选 MCP / Tool / Skill</span>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="筛选 server、tool、skill…"
          className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-[12px] outline-none focus:border-brand-400"
        />
      </label>

      <p className="text-[11px] text-slate-500">
        MCP {inventory.mcp_servers.length} · Tools {inventory.tools.length} · Skills {inventory.skills.length}
      </p>

      {inventory.mcp_servers.map((server, idx) => {
        const tools = (server.tools ?? [])
          .map((name) => toolByName[name])
          .filter(Boolean)
          .filter((t) => match([t.name, t.description, ...(t.skills ?? [])]));
        const extraTools = inventory.tools.filter(
          (t) =>
            !(server.tools ?? []).includes(t.name) &&
            t.registered_on_mcp_server &&
            match([t.name, t.description]),
        );
        const listed = tools.length ? tools : extraTools;
        const resources = (server.resources ?? []).filter((r) => match([r.uri, r.name, r.description]));
        if (query && listed.length === 0 && resources.length === 0 && !match([server.name, server.description])) {
          return null;
        }
        return (
          <Accordion
            key={server.name}
            defaultOpen={idx === 0}
            title={
              <span className="flex items-center gap-2">
                MCP · {server.name}
                <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-normal ${server.enabled ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
                  {server.enabled ? "enabled" : "disabled"}
                </span>
              </span>
            }
            meta={`${listed.length} tools · ${resources.length} resources`}
          >
            <div className="space-y-3 text-[12px]">
              {server.description ? <p className="text-slate-600">{server.description}</p> : null}
              <p className="font-mono text-[10px] text-slate-500">
                {server.command} {(server.args ?? []).join(" ")}
              </p>

              <div>
                <p className="mb-1.5 text-[11px] font-semibold text-slate-700">Tools ({listed.length})</p>
                <div className="space-y-1.5">
                  {listed.map((t) => (
                    <Accordion
                      key={t.name}
                      defaultOpen={false}
                      title={
                        <span className="flex min-w-0 flex-col">
                          <span className="font-mono text-[12px]">{t.name}</span>
                          <span className="truncate font-normal text-[11px] text-slate-500">
                            {t.description || "无说明"}
                          </span>
                        </span>
                      }
                      meta={t.registered_on_mcp_server ? "MCP" : "schema"}
                    >
                      <p className="mb-2 text-[12px] text-slate-700">{t.description || "无说明"}</p>
                      {t.skills.length > 0 ? (
                        <p className="mb-2 text-[11px] text-slate-500">
                          Skills：{t.skills.join(", ")}
                        </p>
                      ) : null}
                      <ParamTable parameters={t.parameters} />
                    </Accordion>
                  ))}
                  {listed.length === 0 ? <p className="text-[11px] text-slate-400">该 server 未挂载 tool</p> : null}
                </div>
              </div>

              <div>
                <p className="mb-1.5 text-[11px] font-semibold text-slate-700">Resources ({resources.length})</p>
                {resources.length === 0 ? (
                  <p className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-500">
                    当前 MCP 未注册 Resource。档案与 JD 通过 Tools 读写，没有独立 resource URI。
                  </p>
                ) : (
                  <ul className="space-y-1">
                    {resources.map((r) => (
                      <li key={r.uri} className="rounded-md border border-slate-100 px-2 py-1.5">
                        <p className="font-mono text-[11px] text-slate-800">{r.uri}</p>
                        <p className="text-[11px] text-slate-600">{r.description || r.name}</p>
                        {r.mime_type ? <p className="text-[10px] text-slate-400">{r.mime_type}</p> : null}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </Accordion>
        );
      })}

      <Accordion title={`Skills (${inventory.skills.length})`} meta="按需展开 SKILL.md" defaultOpen={false}>
        <div className="space-y-1.5">
          {inventory.skills
            .filter((s) => match([s.id, s.description, ...(s.tools ?? [])]))
            .map((s) => (
              <Accordion
                key={s.id}
                defaultOpen={false}
                title={s.id}
                meta={s.enabled ? `${s.tools.length} tools` : "off"}
              >
                {s.description ? <p className="text-[12px] text-slate-600">{s.description}</p> : null}
                <p className="mt-1 text-[11px] text-slate-500">tools: {s.tools.join(", ") || "—"}</p>
                <p className="text-[11px] text-slate-500">hints: {s.scope_for_hints.join(", ") || "—"}</p>
                {s.body_preview ? (
                  <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-[10px]">
                    {s.body_preview}
                  </pre>
                ) : null}
              </Accordion>
            ))}
        </div>
      </Accordion>

      {inventory.product_rules_preview ? (
        <Accordion title="Product Rules" defaultOpen={false} meta="注入 system reminder">
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded bg-amber-50 p-2 text-[10px]">
            {inventory.product_rules_preview}
          </pre>
        </Accordion>
      ) : null}
    </div>
  );
}
