"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  dismissNotifications,
  fetchNotifications,
  markNotificationsRead,
  type NotificationItem,
} from "@/lib/api/notifications";
import { useAuth } from "@/lib/auth/AuthProvider";

type MergeConflict = {
  guest_profile: { id: string; contact_name: string | null };
  account_profile: { id: string; contact_name: string | null };
};

type NotificationContextValue = {
  items: NotificationItem[];
  unreadCount: number;
  loading: boolean;
  refresh: () => Promise<void>;
  markRead: (ids: string[]) => Promise<void>;
  dismiss: (ids: string[]) => Promise<void>;
};

const NotificationContext = createContext<NotificationContextValue | null>(null);

function mergeConflictItem(conflict: MergeConflict): NotificationItem {
  return {
    id: "merge_conflict",
    type: "merge_conflict",
    priority: "critical",
    title: "访客档案合并冲突",
    body: `访客「${conflict.guest_profile.contact_name ?? "未命名"}」与账号档案「${conflict.account_profile.contact_name ?? "未命名"}」冲突，请选择保留哪一份。`,
    created_at: new Date().toISOString(),
    read: false,
    dismissed: false,
    dismiss_policy: "on_action",
    action: { label: "处理冲突", href: "/resume-agent" },
    metadata: { tone: "red" },
  };
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { context } = useAuth();
  const [serverItems, setServerItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [localRead, setLocalRead] = useState<Record<string, true>>({});

  const refresh = useCallback(async () => {
    if (context?.actor !== "user") {
      setServerItems([]);
      setUnreadCount(0);
      return;
    }
    setLoading(true);
    try {
      const res = await fetchNotifications();
      setServerItems(res.items);
      setUnreadCount(res.unread_count);
    } catch {
      setServerItems([]);
      setUnreadCount(0);
    } finally {
      setLoading(false);
    }
  }, [context?.actor]);

  useEffect(() => {
    void refresh();
  }, [refresh, context?.active_profile_id, context?.user?.email_verified]);

  const items = useMemo(() => {
    const merged = [...serverItems];
    const conflict = context?.merge_conflict as MergeConflict | null | undefined;
    if (conflict && !merged.some((i) => i.id === "merge_conflict")) {
      merged.unshift(mergeConflictItem(conflict));
    }
    return merged.map((item) => ({
      ...item,
      read: item.read || Boolean(localRead[item.id]),
    }));
  }, [serverItems, context?.merge_conflict, localRead]);

  const effectiveUnread = useMemo(
    () => items.filter((i) => !i.read).length,
    [items],
  );

  const markRead = useCallback(
    async (ids: string[]) => {
      setLocalRead((prev) => {
        const next = { ...prev };
        for (const id of ids) next[id] = true;
        return next;
      });
      const serverIds = ids.filter((id) => id !== "merge_conflict");
      if (serverIds.length && context?.actor === "user") {
        try {
          const res = await markNotificationsRead(serverIds);
          setServerItems(res.items);
          setUnreadCount(res.unread_count);
        } catch {
          /* keep optimistic read */
        }
      }
    },
    [context?.actor],
  );

  const dismiss = useCallback(
    async (ids: string[]) => {
      const serverIds = ids.filter((id) => id !== "merge_conflict");
      if (serverIds.length && context?.actor === "user") {
        const res = await dismissNotifications(serverIds);
        setServerItems(res.items);
        setUnreadCount(res.unread_count);
      }
    },
    [context?.actor],
  );

  const value = useMemo(
    () => ({
      items,
      unreadCount: effectiveUnread,
      loading,
      refresh,
      markRead,
      dismiss,
    }),
    [items, effectiveUnread, loading, refresh, markRead, dismiss],
  );

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}

export function useNotifications() {
  const ctx = useContext(NotificationContext);
  if (!ctx) {
    throw new Error("useNotifications must be used within NotificationProvider");
  }
  return ctx;
}
