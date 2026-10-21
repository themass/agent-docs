"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  clampTransform,
  coverScale,
  encodeCrop,
  HEADSHOT_ASPECT,
  IDENTITY_TRANSFORM,
  loadImageFile,
  MAX_ZOOM,
  MIN_ZOOM,
  selectionSourceRect,
  moveCrop,
  resizeCrop,
  type CropRect,
  type CropCorner,
  zoomAround,
  type CropTransform,
  type Size,
} from "@/lib/image-crop";

/** Gesture handling only; selection geometry and JPEG encoding live in image-crop. */
const VIEWPORT_HEIGHT = 320;
const VIEWPORT_WIDTH = Math.round(VIEWPORT_HEIGHT * HEADSHOT_ASPECT);

const INITIAL_CROP: CropRect = { x: 24, y: 30, width: 208, height: 260 };

type Props = {
  file: File;
  /** Whether "show on resume" starts ticked — reflects the profile's current state. */
  initialEnabled: boolean;
  busy?: boolean;
  error?: string | null;
  onCancel: () => void;
  onConfirm: (blob: Blob, enabled: boolean) => void;
};

export function PhotoCropDialog({
  file,
  initialEnabled,
  busy = false,
  error = null,
  onCancel,
  onConfirm,
}: Props) {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [transform, setTransform] = useState<CropTransform>(IDENTITY_TRANSFORM);
  const [crop, setCrop] = useState<CropRect>(INITIAL_CROP);
  const [enabled, setEnabled] = useState(initialEnabled);
  const [encoding, setEncoding] = useState(false);
  const locked = busy || encoding;

  const viewport: Size = useMemo(
    () => ({ width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT }),
    [],
  );
  const natural: Size = useMemo(
    () => ({ width: image?.naturalWidth ?? 0, height: image?.naturalHeight ?? 0 }),
    [image],
  );

  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    origin: CropTransform;
    crop: CropRect;
    mode: "image" | "move" | CropCorner;
  } | null>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // The blob URL behind the preview is owned here, not by the loader: the `<img>`
  // below renders from `image.src`, so the URL has to stay alive for as long as this
  // dialog shows that file. Revoking it at decode time is what made the frame grey.
  useEffect(() => {
    let cancelled = false;
    let release: (() => void) | null = null;
    setImage(null);
    setLoadError(null);
    setTransform(IDENTITY_TRANSFORM);
    setCrop(INITIAL_CROP);
    loadImageFile(file)
      .then(({ image: img, revoke }) => {
        // Unmounted or switched files while decoding: drop it immediately rather
        // than leaking the URL until navigation.
        if (cancelled) {
          revoke();
          return;
        }
        release = revoke;
        setImage(img);
      })
      .catch((err: unknown) => {
        if (!cancelled) setLoadError(err instanceof Error ? err.message : "图片读取失败");
      });
    return () => {
      cancelled = true;
      release?.();
    };
  }, [file]);

  // Focus the dialog on open so Escape works without a click first, and so a
  // keyboard user is not left behind on the page underneath.
  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !locked) onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [locked, onCancel]);

  /**
   * Wheel zoom is bound natively with `passive: false` rather than through React's
   * `onWheel`. React attaches wheel listeners passively at the root, where
   * `preventDefault()` is a no-op, so the page would scroll behind the dialog on
   * every zoom.
   */
  useEffect(() => {
    const node = frameRef.current;
    if (!node || !image || locked) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = node.getBoundingClientRect();
      const focus = {
        x: event.clientX - (rect.left + rect.width / 2),
        y: event.clientY - (rect.top + rect.height / 2),
      };
      setTransform((prev) =>
        zoomAround(prev, prev.zoom * (event.deltaY < 0 ? 1.12 : 1 / 1.12), focus, natural, viewport),
      );
    };
    node.addEventListener("wheel", onWheel, { passive: false });
    return () => node.removeEventListener("wheel", onWheel);
  }, [image, natural, viewport, locked]);

  const onPointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (!image || locked) return;
      event.preventDefault();
      dragRef.current = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        origin: transform,
        crop,
        mode: (event.target as HTMLElement).closest<HTMLElement>("[data-crop-action]")?.dataset.cropAction as "move" | CropCorner || "image",
      };
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    [locked, image, transform, crop],
  );

  const onPointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current;
      if (!drag || drag.pointerId !== event.pointerId) return;
      if (locked) return;
      const dx = event.clientX - drag.startX;
      const dy = event.clientY - drag.startY;
      if (drag.mode !== "image") {
        setCrop(drag.mode === "move" ? moveCrop(drag.crop, dx, dy, viewport)
          : resizeCrop(drag.crop, drag.mode, dx, dy, viewport));
        return;
      }
      setTransform(
        clampTransform(
          {
            zoom: drag.origin.zoom,
            x: drag.origin.x + (event.clientX - drag.startX),
            y: drag.origin.y + (event.clientY - drag.startY),
          },
          natural,
          viewport,
        ),
      );
    },
    [natural, viewport, locked],
  );

  const endDrag = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }, []);

  // Arrow keys nudge the frame: the mouse gesture is the primary path, but a crop
  // that can only be set by dragging is unusable without a pointing device.
  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      if (!image || locked) return;
      const step = event.shiftKey ? 24 : 8;
      const deltas: Record<string, { x: number; y: number }> = {
        ArrowLeft: { x: -step, y: 0 },
        ArrowRight: { x: step, y: 0 },
        ArrowUp: { x: 0, y: -step },
        ArrowDown: { x: 0, y: step },
      };
      const delta = deltas[event.key];
      if (delta) {
        event.preventDefault();
        const action = (event.target as HTMLElement).dataset.cropAction;
        const corner = action && action !== "move" ? action as CropCorner : undefined;
        setCrop((prev) => corner
          ? resizeCrop(prev, corner, delta.x, delta.y, viewport)
          : moveCrop(prev, delta.x, delta.y, viewport));
        return;
      }
      if (event.key === "+" || event.key === "=") {
        event.preventDefault();
        setTransform((prev) => zoomAround(prev, prev.zoom * 1.15, { x: 0, y: 0 }, natural, viewport));
      } else if (event.key === "-" || event.key === "_") {
        event.preventDefault();
        setTransform((prev) => zoomAround(prev, prev.zoom / 1.15, { x: 0, y: 0 }, natural, viewport));
      }
    },
    [image, natural, viewport, locked],
  );

  async function confirm() {
    if (!image || busy || encoding) return;
    setEncoding(true);
    try {
      const blob = await encodeCrop(image, selectionSourceRect(transform, natural, viewport, crop));
      onConfirm(blob, enabled);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "图片导出失败");
    } finally {
      setEncoding(false);
    }
  }

  const scale = image ? coverScale(natural, viewport) * transform.zoom : 1;
  const shownError = error ?? loadError;

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-ink-900/55 p-4"
      role="presentation"
      onClick={() => {
        if (!locked) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="裁剪简历照片"
        tabIndex={-1}
        className="card w-full max-w-md max-h-[calc(100dvh-2rem)] overflow-y-auto outline-none"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="border-b border-surface-border px-5 py-3.5">
          <h2 className="text-sm font-semibold text-ink-900">裁剪照片</h2>
          <p className="mt-0.5 text-xs text-ink-500">
            拖动白框选择位置，拖动四角调整裁剪范围（固定 4:5）。框外可拖动图片，滚轮或滑块等比缩放。
          </p>
        </div>

        <div className="flex flex-col items-center gap-4 bg-surface-sunken px-3 sm:px-5 py-5">
          <div
            ref={frameRef}
            role="application"
            aria-label="照片裁剪区域，可拖动与缩放"
            tabIndex={0}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
            onKeyDown={onKeyDown}
            style={{ width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT }}
            className={`relative overflow-hidden rounded-lg ring-1 ring-surface-border-strong bg-ink-100 touch-none select-none ${
              image ? "cursor-grab active:cursor-grabbing" : ""
            } focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-500/25`}
          >
            {image ? (
              <>
                <img
                  src={image.src}
                  alt=""
                  draggable={false}
                  style={{
                    position: "absolute",
                    left: "50%",
                    top: "50%",
                    width: natural.width * scale,
                    height: natural.height * scale,
                    maxWidth: "none",
                    maxHeight: "none",
                    // Order matters: translate to centre first, then apply pan, so the
                    // pan offsets stay in plain viewport pixels and the clamp maths in
                    // `image-crop.ts` needs no scale correction.
                    transform: `translate(-50%, -50%) translate(${transform.x}px, ${transform.y}px)`,
                    willChange: "transform",
                  }}
                />
                <div
                  data-crop-action="move"
                  data-crop-selection
                  role="group"
                  aria-label="裁剪选区，方向键移动位置"
                  tabIndex={0}
                  className="absolute cursor-move border-2 border-white focus:outline-none focus-visible:border-brand-500"
                  style={{ left: crop.x, top: crop.y, width: crop.width, height: crop.height,
                    boxShadow: "0 0 0 999px rgba(0,0,0,.5)", boxSizing: "border-box" }}
                >
                  {(["nw", "ne", "sw", "se"] as CropCorner[]).map((corner, i) => (
                    <button key={corner} type="button" data-crop-action={corner}
                      aria-label={`调整裁剪框${["左上", "右上", "左下", "右下"][i]}角，方向键调整大小`}
                      disabled={locked}
                      className="absolute h-6 w-6 rounded-sm border-2 border-white bg-ink-900/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
                      style={{ left: corner.endsWith("w") ? -12 : undefined,
                        right: corner.endsWith("e") ? -12 : undefined,
                        top: corner.startsWith("n") ? -12 : undefined,
                        bottom: corner.startsWith("s") ? -12 : undefined,
                        cursor: corner === "nw" || corner === "se" ? "nwse-resize" : "nesw-resize" }}
                    />
                  ))}
                </div>
              </>
            ) : shownError ? null : (
              <div className="flex h-full items-center justify-center text-xs text-ink-500">
                正在读取照片…
              </div>
            )}
          </div>

          <label className="flex w-full items-center gap-3 text-xs text-ink-600">
            <span className="shrink-0">缩放</span>
            <input
              type="range"
              min={MIN_ZOOM}
              max={MAX_ZOOM}
              step={0.01}
              value={transform.zoom}
              disabled={!image || locked}
              aria-label="缩放"
              onChange={(event) =>
                setTransform((prev) =>
                  zoomAround(prev, Number(event.target.value), { x: 0, y: 0 }, natural, viewport),
                )
              }
              className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-ink-200 accent-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
            />
            <span className="w-10 shrink-0 text-right tabular-nums">
              {transform.zoom.toFixed(1)}×
            </span>
          </label>
        </div>

        {shownError ? (
          <p className="notice notice-danger mx-5 mt-4 text-xs" role="alert">
            {shownError}
          </p>
        ) : null}

        <div className="flex flex-col gap-3 px-5 py-4">
          <label className="flex items-start gap-2.5 text-sm text-ink-700">
            <input
              type="checkbox"
              checked={enabled}
              disabled={locked}
              onChange={(event) => setEnabled(event.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-brand-600"
            />
            <span>
              保存后在简历上显示
              <span className="mt-0.5 block text-xs text-ink-500">
                不勾选也会保留照片，之后可以随时打开。
              </span>
            </span>
          </label>
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              disabled={locked}
              className="btn btn-md btn-secondary"
            >
              取消
            </button>
            <button
              type="button"
              onClick={confirm}
              disabled={!image || busy || encoding}
              className="btn btn-md btn-primary"
            >
              {busy || encoding ? "保存中…" : "保存照片"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
