"use client";

import { useEffect, useState } from "react";

import { Select } from "@/components/ui/Select";
import { activateProfile, createProfile, listProfiles, type ProfileListItem } from "@/lib/api/profile";
import { useAuth } from "@/lib/auth/AuthProvider";

type Props = {
  disabled?: boolean;
  onSwitched?: () => void;
};

export function ProfileSwitcher({ onSwitched, disabled = false }: Props) {
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
        disabled={busy || disabled}
        onClick={() => void onCreate()}
        className="btn btn-sm btn-secondary shrink-0"
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
      <Select
        id="profile-switcher"
        disabled={busy || disabled}
        value={activeId ?? ""}
        onChange={(e) => void onActivate(e.target.value)}
        className="max-w-[10rem]"
        selectClassName="h-7 truncate py-0 pl-2 text-xs"
      >
        {items.map((p) => (
          <option key={p.id} value={p.id}>
            {p.contact_name ?? `档案 ${p.id.slice(-4)}`}
          </option>
        ))}
      </Select>
      <button
        type="button"
        disabled={busy || disabled}
        onClick={() => void onCreate()}
        className="btn btn-sm btn-secondary px-2"
        title="新建档案"
      >
        +
      </button>
    </div>
  );
}
