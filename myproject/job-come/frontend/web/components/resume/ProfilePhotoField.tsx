"use client";

import { useRef, useState } from "react";

import {
  deleteProfilePhoto,
  setProfilePhoto,
  toggleProfilePhoto,
  type Profile,
} from "@/lib/api/profile";
import { userFacingApiError } from "@/lib/api/user-error";
import { PHOTO_FILE_ACCEPT, photoFileError } from "@/lib/image-crop";

import { PhotoCropDialog } from "./PhotoCropDialog";

/**
 * The headshot control in the profile editor: upload, show/hide, remove.
 *
 * Every action goes straight to the server and hands the returned `Profile` back up
 * through `onSaved`, rather than staging a change in local form state. The photo is
 * a binary upload with its own endpoints and its own version bump, so routing it
 * through the surrounding form's save button would mean either holding file bytes in
 * React state until save, or having a "Save" button that silently already saved part
 * of the form. The surrounding form's `expected_version` stays correct because the
 * fresh profile replaces it.
 *
 * The switch is separate from the upload on purpose: most Chinese-market resumes
 * carry a photo and most English-market ones do not, and the same person often
 * submits both. Deleting and re-cropping for each is a tax; the switch is one click.
 */

type Props = {
  profile: Profile;
  onSaved: (profile: Profile) => void;
};

export function ProfilePhotoField({ profile, onSaved }: Props) {
  const photo = profile.payload.contact.photo;
  const hasPhoto = Boolean(photo?.storage_key);
  const enabled = Boolean(photo?.enabled);
  const showInBilingual = Boolean(photo?.show_in_bilingual);

  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmingRemove, setConfirmingRemove] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function pickFile() {
    setError(null);
    inputRef.current?.click();
  }

  function onFileChosen(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    // Reset first: picking the same file twice in a row fires no change event
    // otherwise, so a user who cancels the crop cannot reopen it on that file.
    event.target.value = "";
    if (!file) return;
    const rejection = photoFileError(file);
    if (rejection) {
      setError(rejection);
      return;
    }
    setError(null);
    setPendingFile(file);
  }

  async function upload(blob: Blob, showOnResume: boolean) {
    setBusy(true);
    setError(null);
    try {
      const next = await setProfilePhoto(profile.id, blob, showOnResume);
      onSaved(next);
      setPendingFile(null);
    } catch (err) {
      setError(userFacingApiError(err, "照片上传失败"));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(nextEnabled: boolean) {
    setBusy(true);
    setError(null);
    try {
      onSaved(await toggleProfilePhoto(profile.id, nextEnabled));
    } catch (err) {
      setError(userFacingApiError(err, "切换失败"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleBilingual(next: boolean) {
    setBusy(true);
    setError(null);
    try {
      onSaved(await toggleProfilePhoto(profile.id, enabled, next));
    } catch (err) {
      setError(userFacingApiError(err, "切换失败"));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      onSaved(await deleteProfilePhoto(profile.id));
      setConfirmingRemove(false);
    } catch (err) {
      setError(userFacingApiError(err, "移除失败"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-start gap-4">
      <input
        ref={inputRef}
        type="file"
        accept={PHOTO_FILE_ACCEPT}
        className="hidden"
        onChange={onFileChosen}
      />

      {/* 4:5 thumbnail, the same aspect as the print box, so this preview is an
          honest preview rather than a differently-shaped crop of the same file. */}
      <div className="h-[100px] w-20 shrink-0 overflow-hidden rounded-lg border border-surface-border bg-surface-sunken">
        {hasPhoto && photo?.download_url ? (
          <img
            src={photo.download_url}
            alt="简历照片"
            className={`h-full w-full object-cover object-top ${enabled ? "" : "opacity-45 grayscale"}`}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <svg
              className="h-7 w-7 text-ink-300"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.6}
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <path d="M15.75 9.75a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
              <path d="M4.5 19.5a7.5 7.5 0 0 1 15 0M3.75 20.25h16.5a.75.75 0 0 0 .75-.75V4.5a.75.75 0 0 0-.75-.75H3.75A.75.75 0 0 0 3 4.5v15c0 .414.336.75.75.75Z" />
            </svg>
          </div>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={pickFile}
            disabled={busy}
            className="btn btn-sm btn-secondary"
          >
            {hasPhoto ? "更换照片" : "上传照片"}
          </button>
          {hasPhoto ? (
            confirmingRemove ? (
              <>
                <button
                  type="button"
                  onClick={remove}
                  disabled={busy}
                  className="btn btn-sm btn-secondary text-danger-700"
                >
                  确认移除
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmingRemove(false)}
                  disabled={busy}
                  className="btn btn-sm btn-ghost"
                >
                  取消
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmingRemove(true)}
                disabled={busy}
                className="btn btn-sm btn-ghost text-ink-500"
              >
                移除
              </button>
            )
          ) : null}
        </div>

        {hasPhoto ? (
          <div className="mt-2.5 space-y-2">
            <label className="flex items-center gap-2 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={enabled}
                disabled={busy}
                onChange={(event) => toggle(event.target.checked)}
                className="h-4 w-4 shrink-0 accent-brand-600"
              />
              <span>在中文简历上显示</span>
            </label>
            {/* Nested under the main switch because it only widens where an
                already-shown photo appears; it is not a second way to turn it on.
                Off by default: a 中英双语 document is usually read by the
                English-market side of a process. */}
            <label
              className={`flex items-center gap-2 pl-6 text-sm ${
                enabled ? "text-ink-700" : "text-ink-400"
              }`}
            >
              <input
                type="checkbox"
                checked={showInBilingual}
                disabled={busy || !enabled}
                onChange={(event) => toggleBilingual(event.target.checked)}
                className="h-4 w-4 shrink-0 accent-brand-600"
              />
              <span>中英双语版本也显示</span>
            </label>
            <p className="text-xs leading-relaxed text-ink-500">
              英文版简历不会显示照片：欧美招聘流程普遍要求筛掉或遮盖带照片的简历，以降低偏见风险。
            </p>
          </div>
        ) : (
          <p className="mt-2.5 text-xs leading-relaxed text-ink-500">
            默认不显示在简历上。上传后可以随时用开关控制，导出的 PDF / Word / HTML 都会跟着变。英文版简历按欧美惯例始终不显示照片。
          </p>
        )}

        {error ? (
          <p className="mt-2 text-xs text-danger-700" role="alert">
            {error}
          </p>
        ) : null}
      </div>

      {pendingFile ? (
        <PhotoCropDialog
          file={pendingFile}
          // A first upload defaults to showing it: the user went looking for this
          // control, so the intent is visible. Replacing a photo keeps whatever the
          // switch is currently set to.
          initialEnabled={hasPhoto ? enabled : true}
          busy={busy}
          error={error}
          onCancel={() => {
            if (busy) return;
            setPendingFile(null);
            setError(null);
          }}
          onConfirm={upload}
        />
      ) : null}
    </div>
  );
}
