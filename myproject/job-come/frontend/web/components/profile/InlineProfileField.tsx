"use client";

import { useLayoutEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";

type Props = {
  label: string;
  value?: string | null;
  placeholder?: string;
  multiline?: boolean;
  className?: string;
  onChange: (value: string) => void;
  onFocus?: () => void;
};

/** Controlled draft on every keystroke; blur only changes presentation, never saves. */
export function InlineProfileField({ label, value, placeholder = "点击补充", multiline = false, className = "", onChange, onFocus }: Props) {
  const [editing, setEditing] = useState(false);
  const initial = useRef("");
  const input = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);
  useLayoutEffect(() => {
    if (!editing || !input.current) return;
    input.current.focus();
    input.current.setSelectionRange(input.current.value.length, input.current.value.length);
  }, [editing]);
  useLayoutEffect(() => {
    if (!editing || !(input.current instanceof HTMLTextAreaElement)) return;
    input.current.style.height = "auto";
    input.current.style.height = `${input.current.scrollHeight}px`;
  }, [editing, value]);

  if (!editing) {
    return (
      <button type="button" aria-label={`编辑${label}${value ? `：${value}` : ""}`} title={`点击编辑${label}`} onClick={() => {
        initial.current = value ?? "";
        onFocus?.();
        setEditing(true);
      }} className={`group/inline -mx-1 inline-flex min-h-9 max-w-full items-start gap-1 rounded-md px-1 py-1 text-left transition hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 ${className}`}>
        <span className={`min-w-0 whitespace-pre-wrap break-words ${value ? "" : "font-normal text-ink-400"}`}>{value || placeholder}</span>
        <svg aria-hidden="true" className="mt-1 h-3 w-3 shrink-0 text-ink-400 opacity-50 group-hover/inline:opacity-100" viewBox="0 0 16 16" fill="none" stroke="currentColor"><path d="m10 3 3 3M3 10l7-7 3 3-7 7-4 1z" /></svg>
      </button>
    );
  }
  const common = {
    "aria-label": label,
    value: value ?? "",
    placeholder,
    className: `field w-full min-w-0 text-inherit ${className}`,
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange(event.target.value),
    onBlur: () => setEditing(false),
    onKeyDown: (event: KeyboardEvent) => {
      if (event.nativeEvent.isComposing) return;
      if (event.key === "Escape") {
        event.preventDefault();
        onChange(initial.current);
        setEditing(false);
      } else if (event.key === "Enter" && (!multiline || event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        setEditing(false);
      }
    },
  };
  return multiline
    ? <textarea {...common} rows={2} ref={(node) => { input.current = node; }} />
    : <input {...common} ref={(node) => { input.current = node; }} />;
}
