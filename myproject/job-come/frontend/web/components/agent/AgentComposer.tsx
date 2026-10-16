"use client";

import { useLayoutEffect, useRef, useState, useCallback, useEffect } from "react";

import { CameraPage } from "@/components/agent/media/CameraPage";
import { VoiceCaptureBar } from "@/components/agent/media/VoiceCaptureBar";
import { VoiceCaptureOrb } from "@/components/agent/media/VoiceCaptureOrb";
import { VoiceCard } from "@/components/agent/media/VoiceCard";
import { ZoomableImage } from "@/components/agent/media/ZoomableImage";
import { composerEnterIntent } from "@/lib/composer-key";
import { TokenMeter } from "@/components/agent/TokenMeter";
import { createVoiceRecorder, type VoiceClip } from "@/lib/audio-record";
import {
  appendDictation,
  createDictation,
  ensureMicrophoneAccess,
  getSpeechRecognitionCtor,
  speechErrorMessage,
} from "@/lib/speech-dictation";
import type { AgentAttachment, AgentContextUsage } from "@/lib/types/agent";

async function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).slice(0, 8000));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

const iconBtn =
  "inline-flex size-8 shrink-0 items-center justify-center rounded-full text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-900 disabled:pointer-events-none disabled:opacity-40";

type Props = {
  disabled?: boolean;
  busy?: boolean;
  context: AgentContextUsage;
  placeholder?: string;
  variant?: "default" | "sidebar";
  onSend: (content: string, attachments: AgentAttachment[], mode?: "send" | "follow_up" | "steer") => void | Promise<void>;
  onStop?: () => void;
};

export function AgentComposer({
  disabled = false,
  busy = false,
  context,
  placeholder = "描述你的需求，或粘贴 JD…",
  variant = "default",
  onSend,
  onStop,
}: Props) {
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<AgentAttachment[]>([]);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [attachOpen, setAttachOpen] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [voiceUi, setVoiceUi] = useState<"bar" | "orb">("orb");
  const fileRef = useRef<HTMLInputElement>(null);
  const imageRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dictationRef = useRef<ReturnType<typeof createDictation> | null>(null);
  const recorderRef = useRef<ReturnType<typeof createVoiceRecorder> | null>(null);

  const attachMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!attachOpen) return;
    function onDocClick(e: MouseEvent) {
      if (!attachMenuRef.current?.contains(e.target as Node)) {
        setAttachOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [attachOpen]);

  const addFiles = useCallback(async (files: FileList | File[]) => {
    const list = Array.from(files);
    const next: AgentAttachment[] = [];
    for (const file of list) {
      if (file.type.startsWith("image/")) {
        next.push({
          kind: "image",
          name: file.name,
          label: file.name,
          mime_type: file.type,
          data_url: await readFileAsDataUrl(file),
        });
      } else {
        let text_preview: string | undefined;
        try {
          text_preview = await readFileAsText(file);
        } catch {
          text_preview = undefined;
        }
        next.push({
          kind: "file",
          name: file.name,
          label: file.name,
          mime_type: file.type || undefined,
          text_preview,
        });
      }
    }
    setAttachments((prev) => [...prev, ...next]);
    setAttachOpen(false);
  }, []);

  const displayValue = listening && interim ? `${input}${input ? " " : ""}${interim}` : input;

  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, window.innerHeight * 0.28)}px`;
  }, [displayValue]);

  async function cancelListen(): Promise<void> {
    dictationRef.current?.stop();
    dictationRef.current = null;
    await recorderRef.current?.stop();
    recorderRef.current = null;
    setListening(false);
    setInterim("");
  }

  async function finishListen(): Promise<void> {
    dictationRef.current?.stop();
    dictationRef.current = null;
    const clip = await recorderRef.current?.stop();
    recorderRef.current = null;
    setListening(false);
    setInterim("");
    if (clip) {
      setAttachments((prev) => [
        ...prev,
        {
          kind: "audio",
          name: `voice${clip.ext}`,
          label: "语音",
          mime_type: clip.mime,
          data_url: clip.dataUrl,
        },
      ]);
    }
  }

  async function handleSubmit(mode: "send" | "follow_up" | "steer" = "send") {
    if (listening) {
      await finishListen();
    }
    const text = input.trim();
    if ((!text && attachments.length === 0) || disabled) return;
    if (!busy && mode !== "send") {
      // queue modes handled when busy only
    }
    if (!busy && (mode === "follow_up" || mode === "steer")) {
      mode = "send";
    }
    const sendText = text;
    const sendAttachments = attachments;
    setInput("");
    setAttachments([]);
    setAttachOpen(false);
    await onSend(sendText, sendAttachments, mode);
  }

  async function toggleVoice() {
    if (disabled || busy) return;
    if (listening) {
      await finishListen();
      return;
    }

    setSpeechError(null);
    const mic = await ensureMicrophoneAccess();
    if (!mic.ok) {
      setSpeechError(mic.reason === "missing" ? "没有找到麦克风" : "没有麦克风权限");
      return;
    }

    const dictation = createDictation({
      onFinal: (chunk) => {
        setInput((prev) => appendDictation(prev, chunk));
      },
      onInterim: (chunk) => setInterim(chunk),
      onError: (code) => {
        const msg = speechErrorMessage(code);
        if (msg) setSpeechError(msg);
        if (code !== "no-speech" && code !== "aborted") {
          void finishListen();
        }
      },
      onEnd: () => {
        if (!dictationRef.current) {
          setListening(false);
          setInterim("");
        }
      },
    });
    if (!dictation) {
      setSpeechError("当前浏览器不支持语音识别");
      return;
    }

    const recorder = createVoiceRecorder();
    if (recorder) {
      const ok = await recorder.start();
      if (ok) recorderRef.current = recorder;
    }

    dictationRef.current = dictation;
    const started = dictation.start();
    if (!started) {
      setSpeechError("无法启动语音识别");
      await finishListen();
      return;
    }
    setListening(true);
  }

  function onCameraUse(dataUrl: string) {
    setAttachments((prev) => [
      ...prev,
      {
        kind: "image",
        name: "camera.jpg",
        label: "摄像头",
        mime_type: "image/jpeg",
        data_url: dataUrl,
      },
    ]);
    setCameraOpen(false);
  }

  function onPaste(event: React.ClipboardEvent<HTMLTextAreaElement>) {
    if (disabled || busy) return;
    const items = [...event.clipboardData.items];
    const imageItem = items.find((item) => item.type.startsWith("image/"));
    const file = imageItem?.getAsFile();
    if (!file) return;
    event.preventDefault();
    void addFiles([file]);
  }

  const canSend =
    !disabled && (input.trim().length > 0 || attachments.length > 0 || listening);
  const hasVoice = getSpeechRecognitionCtor() !== null;
  const isSidebar = variant === "sidebar";

  return (
    <div
      className={`relative shrink-0 ${
        isSidebar
          ? "border-t border-surface-border bg-surface-sunken px-2.5 pb-2.5 pt-2"
          : "border-t border-surface-border bg-surface px-3 pb-3 pt-2"
      } ${dragOver ? "ring-2 ring-inset ring-brand-200" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDragEnd={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        if (e.dataTransfer.files.length) void addFiles(e.dataTransfer.files);
      }}
    >
      {dragOver ? (
        <div className="pointer-events-none absolute inset-2 z-10 flex items-center justify-center rounded-xl border border-dashed border-brand-400 bg-brand-50/90 text-sm font-medium text-brand-800">
          松开以添加图片或文件
        </div>
      ) : null}

      {listening && voiceUi === "bar" ? (
        <VoiceCaptureBar
          interim={interim}
          transcript={input}
          onCancel={() => void cancelListen()}
          onFinish={() => void finishListen()}
        />
      ) : null}
      {listening && voiceUi === "orb" ? (
        <VoiceCaptureOrb
          interim={interim}
          transcript={input}
          getAudioLevel={() => recorderRef.current?.getLevel() ?? 0}
          onCancel={() => void cancelListen()}
          onFinish={() => void finishListen()}
        />
      ) : null}

      <div
        className={`overflow-visible rounded-2xl border border-surface-border bg-surface transition focus-within:border-brand-300 focus-within:ring-4 focus-within:ring-brand-500/10 ${
          isSidebar ? "shadow-card" : "shadow-raised"
        }`}
      >
        {attachments.length > 0 ? (
          <div className="flex flex-wrap gap-2 border-b border-surface-border px-3 py-2">
            {attachments.map((att, i) => (
              <div key={`${att.kind}-${att.name}-${i}`} className="relative">
                {att.kind === "image" && att.data_url ? (
                  <ZoomableImage
                    src={att.data_url}
                    label={att.label ?? att.name}
                    imgClassName="size-14 rounded-lg object-cover ring-1 ring-inset ring-surface-border"
                  />
                ) : att.kind === "audio" && att.data_url ? (
                  <VoiceCard src={att.data_url} compact onClear={() => setAttachments((a) => a.filter((_, j) => j !== i))} />
                ) : (
                  <span className="inline-flex max-w-[180px] items-center rounded-lg bg-surface-sunken px-2.5 py-2 text-xs text-ink-700 ring-1 ring-inset ring-surface-border">
                    <span className="truncate">{att.label ?? att.name}</span>
                  </span>
                )}
                {att.kind !== "audio" ? (
                  <button
                    type="button"
                    className="absolute -right-1.5 -top-1.5 inline-flex size-5 items-center justify-center rounded-full bg-ink-700 text-micro text-white shadow-xs transition hover:bg-danger-600"
                    aria-label="移除附件"
                    onClick={() => setAttachments((a) => a.filter((_, j) => j !== i))}
                  >
                    ✕
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}

        {speechError ? (
          <p className="px-3 pt-2 text-xs text-danger-700">{speechError}</p>
        ) : null}

        <div className="px-3 pt-2.5">
          <textarea
            ref={textareaRef}
            value={displayValue}
            onChange={(e) => {
              if (!listening) setInput(e.target.value);
            }}
            onPaste={onPaste}
            onKeyDown={(e) => {
              const intent = composerEnterIntent({
                key: e.key,
                shiftKey: e.shiftKey,
                altKey: e.altKey,
                ctrlKey: e.ctrlKey,
                isComposing: e.nativeEvent.isComposing,
                keyCode: e.keyCode,
              });
              if (intent === "send" || intent === "steer") {
                e.preventDefault();
                void handleSubmit(intent);
              }
            }}
            rows={1}
            readOnly={listening}
            disabled={disabled}
            placeholder={
              busy
                ? "Enter 排队 · Ctrl+Enter 插队纠偏"
                : listening
                  ? "正在聆听…"
                  : placeholder
            }
            className="scroll-area max-h-[28vh] w-full resize-none bg-transparent py-0.5 text-base leading-relaxed text-ink-900 outline-none placeholder:text-ink-400"
          />
        </div>

        <div className="flex items-center justify-between gap-2 px-2 pb-2 pt-1">
          <div className="relative flex items-center gap-0.5" ref={attachMenuRef}>
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.length) void addFiles(e.target.files);
                e.target.value = "";
              }}
            />
            <input
              ref={imageRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.length) void addFiles(e.target.files);
                e.target.value = "";
              }}
            />
            <button
              type="button"
              className={iconBtn}
              title="附加文件或图片"
              disabled={disabled || busy}
              onClick={() => setAttachOpen((v) => !v)}
            >
              <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeWidth={2} d="M12 5v14M5 12h14" />
              </svg>
            </button>
            {attachOpen ? (
              <div className="absolute bottom-full left-0 z-20 mb-2 w-56 rounded-xl border border-surface-border bg-surface p-1.5 shadow-pop">
                <button
                  type="button"
                  className="flex w-full rounded-md px-2.5 py-2 text-left text-xs text-ink-700 transition hover:bg-ink-100"
                  onClick={() => imageRef.current?.click()}
                >
                  图片
                </button>
                <button
                  type="button"
                  className="flex w-full rounded-md px-2.5 py-2 text-left text-xs text-ink-700 transition hover:bg-ink-100"
                  onClick={() => fileRef.current?.click()}
                >
                  文件
                </button>
                <p className="px-3 pb-1 pt-1 text-micro text-ink-500">
                  支持 Ctrl+V / Cmd+V 粘贴截图
                </p>
              </div>
            ) : null}
            <button
              type="button"
              className={iconBtn}
              title="摄像头拍照"
              disabled={disabled || busy}
              onClick={() => setCameraOpen(true)}
            >
              <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
            {hasVoice ? (
              <>
                {!listening ? (
                  <button
                    type="button"
                    className={`${iconBtn} size-7`}
                    title={voiceUi === "orb" ? "切换为条形录音" : "切换为浮动声纹"}
                    onClick={() => setVoiceUi(voiceUi === "orb" ? "bar" : "orb")}
                  >
                    {voiceUi === "orb" ? (
                      <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeWidth={2} d="M4 6h16M4 12h16M4 18h10" />
                      </svg>
                    ) : (
                      <svg className="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="12" cy="12" r="4" strokeWidth={2} />
                      </svg>
                    )}
                  </button>
                ) : null}
                <button
                type="button"
                className={`${iconBtn} ${
                  listening
                    ? "bg-danger-600 text-white ring-4 ring-danger-600/20 hover:bg-danger-600 hover:text-white"
                    : ""
                }`}
                title={listening ? "停止语音" : "语音输入"}
                disabled={disabled || busy}
                onClick={toggleVoice}
              >
                <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 14a3 3 0 003-3V7a3 3 0 10-6 0v4a3 3 0 003 3zm7-1v1a7 7 0 01-14 0v-1M12 19v3"
                  />
                </svg>
              </button>
              </>
            ) : null}
          </div>

          <div className="flex shrink-0 items-center gap-0.5">
            {isSidebar ? <TokenMeter context={context} busy={busy} /> : null}
            <button
            type="button"
            disabled={busy ? false : !canSend}
            onClick={() => {
              if (busy) {
                onStop?.();
                return;
              }
              void handleSubmit("send");
            }}
            className={`inline-flex size-9 shrink-0 items-center justify-center rounded-full text-white transition disabled:pointer-events-none disabled:opacity-30 ${
              busy
                ? "bg-danger-600 shadow-xs hover:bg-danger-700"
                : "bg-brand-600 shadow-brand hover:bg-brand-700 active:bg-brand-800"
            }`}
            title={busy ? "停止" : "发送 (Enter)"}
            aria-label={busy ? "停止" : "发送"}
          >
            {busy ? (
              <svg className="size-3.5" viewBox="0 0 24 24" fill="currentColor">
                <rect x="7" y="7" width="10" height="10" rx="1" />
              </svg>
            ) : (
              <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.5}
                  d="M12 19V5m0 0l-6 6m6-6l6 6"
                />
              </svg>
            )}
          </button>
          </div>
        </div>
      </div>

      {!isSidebar ? (
      <p className="mt-2 px-1 text-micro text-ink-500">
        Enter 发送 · Ctrl+Enter 插队 · Shift+Enter 换行 · Context {context.percent}%
      </p>
      ) : null}

      {cameraOpen ? (
        <CameraPage onClose={() => setCameraOpen(false)} onUse={onCameraUse} />
      ) : null}
    </div>
  );
}
