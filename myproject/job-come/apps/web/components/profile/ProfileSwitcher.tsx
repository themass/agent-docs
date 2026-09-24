"use client";

import { useEffect, useState } from "react";

import { activateProfile, createProfile, listProfiles, type ProfileListItem } from "@/lib/api/profile";
import { useAuth } from "@/lib/auth/AuthProvider";

type Props = {
  onSwitched?: () => void;
};

export function ProfileSwitcher({ onSwitched }: Props) {
  const { context, refresh } = useAuth();
  const [items, setItems] = useState<ProfileListItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (context?.actor !== "user") return;
    void listProfiles()
      .then((res) => {
        setItems(res.profiles);
        setActiveId(res.active_profile_id);
      })
      .catch(() => undefined);
  }, [context?.actor, context?.active_profile_id]);

  if (context?.actor !== "user") return null;

  async function onActivate(id: string) {
    if (id === activeId || busy) return;
    setBusy(true);
    try {
      await activateProfile(id);
      await refresh();
      onSwitched?.();
      const res = await listProfiles();
      setItems(res.profiles);
      setActiveId(res.active_profile_id);
    } finally {
      setBusy(false);
    }
  }

  async function onCreate() {
    if (busy) return;
    setBusy(true);
    try {
      await createProfile();
      await refresh();
      onSwitched?.();
      const res = await listProfiles();
      setItems(res.profiles);
      setActiveId(res.active_profile_id);
    } finally {
      setBusy(false);
    }
  }

  if (items.length <= 1) {
    return (
      <button
        type="button"
        disabled={busy}
        onClick={() => void onCreate()}
        className="shrink-0 rounded-md border border-slate-200 px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-50"
      >
        + 档案
      </button>
    );
  }

  return (
    <div className="flex shrink-0 items-center gap-1">
      <label className="sr-only" htmlFor="profile-switcher">
        当前档案
      </label>
      <select
        id="profile-switcher"
        disabled={busy}
        value={activeId ?? ""}
        onChange={(e) => void onActivate(e.target.value)}
        className="max-w-[9.5rem] truncate rounded-md border border-slate-200 bg-white py-1 pl-2 pr-6 text-[11px] text-slate-700"
      >
        {items.map((p) => (
          <option key={p.id} value={p.id}>
            {p.contact_name ?? `档案 ${p.id.slice(-4)}`}
          </option>
        ))}
      </select>
      <button
        type="button"
        disabled={busy}
        onClick={() => void onCreate()}
        className="rounded-md border border-dashed border-slate-300 px-1.5 py-1 text-[11px] text-slate-500 hover:bg-slate-50"
        title="新建档案"
      >
        +
      </button>
    </div>
  );
}
