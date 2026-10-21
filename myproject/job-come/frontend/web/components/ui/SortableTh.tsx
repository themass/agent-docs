"use client";

import type { ReactNode } from "react";

/** Which column a list is ordered by, and in which direction. */
export type SortState = { sortBy: string; sortDir: "asc" | "desc" };

/**
 * One clickable column header.
 *
 * Only the active column shows an arrow: an arrow on every header reads as
 * "sorted by all of these", which is meaningless. The indicator is driven by
 * the *server-echoed* sort state rather than local intent, so a rejected or
 * coerced sort never leaves the header pointing at the wrong column.
 *
 * `aria-sort` on the `<th>` is what a screen reader announces; the visual
 * caret is decorative and hidden from the accessibility tree.
 */
export function SortableTh({
  columnKey,
  label,
  sort,
  onSort,
  align = "left",
  sortable = true,
  className = "",
  title,
}: {
  columnKey: string;
  label: ReactNode;
  sort: SortState;
  onSort: (columnKey: string) => void;
  align?: "left" | "right" | "center";
  /** Computed-per-page columns have no SQL column to order by. */
  sortable?: boolean;
  className?: string;
  title?: string;
}) {
  const active = sortable && sort.sortBy === columnKey;
  const ariaSort = active ? (sort.sortDir === "asc" ? "ascending" : "descending") : "none";
  const alignClass = { left: "text-left", right: "text-right", center: "text-center" }[align];
  const justify = { left: "justify-start", right: "justify-end", center: "justify-center" }[align];

  if (!sortable) {
    return (
      <th className={`px-3 py-2 font-medium ${alignClass} ${className}`} title={title}>
        {label}
      </th>
    );
  }

  return (
    <th
      className={`px-3 py-2 font-medium ${alignClass} ${className}`}
      aria-sort={ariaSort}
      title={title}
    >
      <button
        type="button"
        onClick={() => onSort(columnKey)}
        className={`inline-flex w-full items-center gap-1 ${justify} rounded px-1 py-0.5 transition hover:text-ink-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand-500 ${
          active ? "text-ink-900" : "text-ink-500"
        }`}
      >
        <span>{label}</span>
        <span aria-hidden="true" className={`text-[10px] leading-none ${active ? "" : "opacity-0"}`}>
          {sort.sortDir === "asc" ? "▲" : "▼"}
        </span>
      </button>
    </th>
  );
}

/**
 * Click handling shared by every sortable list: clicking the active column
 * flips direction, clicking a new one starts at the direction that is useful
 * first for that kind of value (newest time, largest number, A→Z text).
 */
export function nextSortState(
  current: SortState,
  columnKey: string,
  firstDirection: "asc" | "desc" = "desc",
): SortState {
  if (current.sortBy === columnKey) {
    return { sortBy: columnKey, sortDir: current.sortDir === "asc" ? "desc" : "asc" };
  }
  return { sortBy: columnKey, sortDir: firstDirection };
}
