"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import {
  captureVideoFrame,
  hasGetUserMedia,
  mediaErrorMessage,
  openCameraStream,
  shouldMirrorPreview,
  stopMediaStream,
  videoInputCount,
  type CameraFacing,
} from "@/lib/camera-capture";

type Phase = "live" | "review" | "blocked";

const PANEL_WIDTH = 280;

export function CameraPage({
  onClose,
  onUse,
}: {
  onClose: () => void;
  onUse: (dataUrl: string) => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [phase, setPhase] = useState<Phase>("live");
  const [facing, setFacing] = useState<CameraFacing>("user");
  const [ready, setReady] = useState(false);
  const [canFlip, setCanFlip] = useState(false);
  const [shot, setShot] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mirrored = shouldMirrorPreview(facing);
  const supported = hasGetUserMedia();

  function release(): void {
    stopMediaStream(streamRef.current);
    streamRef.current = null;
    const video = videoRef.current;
    if (video) video.srcObject = null;
  }

  async function startCamera(nextFacing: CameraFacing): Promise<void> {
    if (!supported) {
      setPhase("blocked");
      setError("当前浏览器不支持摄像头");
      return;
    }
    setBusy(true);
    setError(null);
    release();
    try {
      const stream = await openCameraStream(nextFacing);
      streamRef.current = stream;
      const video = videoRef.current;
      if (video) {
        video.srcObject = stream;
        await video.play();
      }
      setFacing(nextFacing);
      setReady(true);
      setPhase("live");
      const count = await videoInputCount();
      setCanFlip(count > 1);
    } catch (err) {
      setPhase("blocked");
      setError(mediaErrorMessage(err));
      setReady(false);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void startCamera("user");
    return () => release();
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (phase === "review") {
          setShot(null);
          setPhase("live");
          return;
        }
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, phase]);

  function shutter(): void {
    const video = videoRef.current;
    if (!video) return;
    try {
      const dataUrl = captureVideoFrame(video, mirrored);
      setShot(dataUrl);
      setPhase("review");
      release();
    } catch (err) {
      setError(err instanceof Error ? err.message : "截图失败");
    }
  }

  const panel = (
    <div
      className="fixed z-[9998] overflow-hidden rounded-2xl border border-slate-200 bg-slate-900 shadow-2xl"
      style={{ width: PANEL_WIDTH, right: 12, top: 48 }}
    >
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <span className="text-[12px] font-medium text-white">拍照</span>
        <button type="button" className="text-white/70 hover:text-white" onClick={onClose} aria-label="关闭">
          ✕
        </button>
      </div>

      {phase === "blocked" ? (
        <div className="space-y-2 p-4 text-center text-[12px] text-white/80">
          <p>{error ?? "无法打开摄像头"}</p>
          <button
            type="button"
            className="rounded-full bg-white/10 px-3 py-1 text-white hover:bg-white/20"
            onClick={() => void startCamera(facing)}
          >
            重试
          </button>
        </div>
      ) : phase === "review" && shot ? (
        <div className="space-y-2 p-2">
          <img src={shot} alt="预览" className="block w-full rounded-xl" />
          <div className="flex gap-2">
            <button
              type="button"
              className="flex-1 rounded-xl bg-white/10 py-2 text-[12px] text-white hover:bg-white/20"
              onClick={() => {
                setShot(null);
                void startCamera(facing);
              }}
            >
              重拍
            </button>
            <button
              type="button"
              className="flex-1 rounded-xl bg-brand-600 py-2 text-[12px] text-white hover:bg-brand-700"
              onClick={() => onUse(shot)}
            >
              使用这张
            </button>
          </div>
        </div>
      ) : (
        <div className="relative">
          <video
            ref={videoRef}
            playsInline
            muted
            className={`block w-full bg-black ${mirrored ? "-scale-x-100" : ""}`}
          />
          {!ready ? (
            <div className="absolute inset-0 flex items-center justify-center bg-black/60 text-[12px] text-white">
              {busy ? "打开中…" : "准备画面…"}
            </div>
          ) : null}
          <div className="flex items-center justify-between gap-2 p-2">
            {canFlip ? (
              <button
                type="button"
                className="rounded-full bg-white/10 px-2.5 py-1 text-[11px] text-white hover:bg-white/20"
                onClick={() => void startCamera(facing === "user" ? "environment" : "user")}
              >
                翻转
              </button>
            ) : (
              <span />
            )}
            <button
              type="button"
              disabled={!ready}
              className="inline-flex size-12 items-center justify-center rounded-full border-4 border-white bg-white/20 text-white disabled:opacity-40"
              onClick={shutter}
              aria-label="拍照"
            >
              <span className="size-8 rounded-full bg-white" />
            </button>
            <span className="w-12" />
          </div>
        </div>
      )}
    </div>
  );

  if (typeof document === "undefined") return null;
  return createPortal(panel, document.body);
}
