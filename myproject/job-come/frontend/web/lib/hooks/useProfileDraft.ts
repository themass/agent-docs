"use client";

import { useCallback, useEffect, useRef, useState, type SetStateAction } from "react";
import { updateProfile, type Profile, type ProfilePayload } from "@/lib/api/profile";
import { userFacingApiError } from "@/lib/api/user-error";
import {
  acknowledgeSave, cleanProfileDraft, createProfileDraft, draftIsDirty, receiveProfile,
  type ProfileDraft,
} from "@/lib/profile-draft";

export function useProfileDraft(profile: Profile | null, onSaved: (profile: Profile) => void) {
  const [draft, setDraftState] = useState<ProfileDraft | null>(() => profile ? createProfileDraft(profile) : null);
  const ref = useRef(draft);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const inFlight = useRef<Promise<boolean> | null>(null);
  const update = useCallback((fn: (current: ProfileDraft | null) => ProfileDraft | null) => {
    ref.current = fn(ref.current);
    setDraftState(ref.current);
  }, []);

  useEffect(() => {
    update((current) => profile ? current ? receiveProfile(current, profile) : createProfileDraft(profile) : null);
  }, [profile, update]);

  const setPayload = useCallback((action: SetStateAction<ProfilePayload>) => {
    update((current) => current ? {
      ...current,
      payload: typeof action === "function" ? action(current.payload) : action,
    } : null);
    setMessage(null);
  }, [update]);

  const save = useCallback((): Promise<boolean> => {
    if (inFlight.current) return inFlight.current;
    const current = ref.current;
    if (!current) return Promise.resolve(false);
    if (current.conflict) {
      setMessage("档案已在其他位置更新。你的编辑仍保留，请先处理版本冲突。");
      return Promise.resolve(false);
    }
    if (!draftIsDirty(current)) return Promise.resolve(true);
    setBusy(true);
    setMessage(null);
    const submitted = current.payload;
    const request = (async () => {
      try {
        const saved = await updateProfile(current.base.id, cleanProfileDraft(submitted), current.base.version);
        if (ref.current?.base.id !== saved.id) return false;
        update((latest) => latest ? acknowledgeSave(latest, submitted, saved) : null);
        onSaved(saved);
        const pending = ref.current && (draftIsDirty(ref.current) || ref.current.conflict);
        setMessage(pending ? "此批修改已保存，仍有新的编辑待处理" : "已保存到档案");
        return !pending;
      } catch (error) {
        setMessage(userFacingApiError(error, "保存失败，编辑内容仍保留，请重试"));
        return false;
      } finally {
        setBusy(false);
        inFlight.current = null;
      }
    })();
    inFlight.current = request;
    return request;
  }, [onSaved, update]);

  const dirty = Boolean(draft && draftIsDirty(draft));
  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!ref.current || !draftIsDirty(ref.current)) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const click = (event: MouseEvent) => {
      if (!ref.current || !draftIsDirty(ref.current) || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
      const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!(link instanceof HTMLAnchorElement) || link.target === "_blank" || link.hasAttribute("download")) return;
      const next = new URL(link.href, window.location.href);
      if (next.pathname === window.location.pathname && next.search === window.location.search) return;
      if (!window.confirm("有未保存的简历修改。离开会丢失这些修改，确定离开？")) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    const keydown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void save();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", click, true);
    window.addEventListener("keydown", keydown);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", click, true);
      window.removeEventListener("keydown", keydown);
    };
  }, [save]);

  const downloadDraft = useCallback(() => {
    if (!ref.current) return;
    // Explicit user-triggered recovery copy, not a local source of business truth.
    const blob = new Blob([JSON.stringify(ref.current.payload, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `resume-unsaved-${ref.current.base.id}.json`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, []);

  const discard = useCallback(() => {
    if (!window.confirm("放弃未保存的修改，并加载最新档案？此操作不会保存当前输入。")) return;
    update((current) => current ? createProfileDraft(current.conflict ?? current.base) : null);
    setMessage(null);
  }, [update]);

  return { draft, dirty, busy, message, setPayload, save, discard, downloadDraft };
}

export type ProfileDraftController = ReturnType<typeof useProfileDraft>;
