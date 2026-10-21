"use client";

import { useLayoutEffect, useRef, useState, useCallback, useEffect } from "react";

import { attachmentSizeError, dataUrlBytes } from "../attachment";
import { composerEnterIntent } from "../composer-key";
import { createVoiceRecorder, type VoiceClip } from "../audio-record";
import {
  appendDictation,
  createDictation,
  ensureMicrophoneAccess,
  getSpeechRecognitionCtor,
  speechErrorMessage,
} from "../speech-dictation";
import { TokenMeter } from "../TokenMeter";
import type { AgentComposerAttachment, AgentComposerLabels, AgentContextUsage } from "../types";
import { CameraPage } from "../media/CameraPage";
import { VoiceCaptureBar } from "../media/VoiceCaptureBar";
import { VoiceCaptureOrb } from "../media/VoiceCaptureOrb";
import { VoiceCard } from "../media/VoiceCard";
import { ZoomableImage } from "../media/ZoomableImage";

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
  labels: AgentComposerLabels;
  placeholder?: string;
  variant?: "default" | "sidebar";
  onSend: (
    content: string,
    attachments: AgentComposerAttachment[],
    mode?: "send" | "follow_up" | "steer",
  ) => void | Promise<void>;
  onStop?: () => void;
};

// No speech activity (no dictation result, no mic level above the noise floor) for
// this long auto-ends the recording, matching what most voice-note UIs do so a user
// never has to remember to tap "完成".
const VOICE_SILENCE_MS = 2600;
// Below this normalized level (0-1, see `attachLevelMonitor` in audio-record.ts) a
// reading is treated as background noise rather than the user still talking.
const VOICE_NOISE_FLOOR = 0.08;

export function AgentComposer({
  disabled = false,
  busy = false,
  context,
  labels,
  placeholder,
  variant = "default",
  onSend,
  onStop,
}: Props) {
  const resolvedPlaceholder = placeholder ?? labels.placeholderDefault;
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<AgentComposerAttachment[]>([]);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [speechError, setSpeechError] = useState<string | null>(null);
  const [attachError, setAttachError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [attachOpen, setAttachOpen] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [voiceUi, setVoiceUi] = useState<"bar" | "orb">("orb");
  const fileRef = useRef<HTMLInputElement>(null);
  const imageRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dictationRef = useRef<ReturnType<typeof createDictation> | null>(null);
  const recorderRef = useRef<ReturnType<typeof createVoiceRecorder> | null>(null);
  // Only the words dictated during the current recording. The input box is not a usable
  // source for this: it may already hold typed text, and the user can keep editing it
  // afterwards, so reading it at send time would attach the wrong words to the clip.
  const dictatedRef = useRef("");
  // Auto-ends a recording after a stretch of silence so the user never has to remember
  // to tap "完成". Reset on every dictation result and whenever the mic level clears a
  // noise floor; left alone otherwise so normal speaking pauses do not trip it.
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const levelPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Mirrors the staged attachments' total size. A ref rather than derived state so
  // `addFiles` (a stable callback awaiting FileReader) can read the current total
  // without closing over a stale `attachments`.
  const attachedBytesRef = useRef(0);

  useEffect(() => {
    attachedBytesRef.current = attachments.reduce((sum, a) => sum + (a.size_bytes ?? 0), 0);
  }, [attachments]);

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
    const next: AgentComposerAttachment[] = [];
    // Measured against what is already staged, because the server's ceiling is per
    // message, not per file. Refusing here means the user never uploads bytes that
    // were going to be rejected anyway.
    let staged = attachedBytesRef.current;
    for (const file of list) {
      if (file.type.startsWith("image/")) {
        const dataUrl = await readFileAsDataUrl(file);
        const bytes = dataUrlBytes(dataUrl);
        const tooBig = attachmentSizeError(file.name, bytes, staged);
        if (tooBig) {
          setAttachError(tooBig);
          continue;
        }
        staged += bytes;
        next.push({
          kind: "image",
          name: file.name,
          label: file.name,
          mime_type: file.type,
          data_url: dataUrl,
          size_bytes: bytes,
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
    if (next.length > 0) setAttachments((prev) => [...prev, ...next]);
    setAttachOpen(false);
  }, []);

  const displayValue = listening && interim ? `${input}${input ? " " : ""}${interim}` : input;

  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, window.innerHeight * 0.28)}px`;
  }, [displayValue]);

  function clearSilenceWatch(): void {
    if (silenceTimerRef.current !== null) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (levelPollRef.current !== null) {
      clearInterval(levelPollRef.current);
      levelPollRef.current = null;
    }
  }

  function resetSilenceTimer(): void {
    if (silenceTimerRef.current !== null) clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = setTimeout(() => {
      void finishListen();
    }, VOICE_SILENCE_MS);
  }

  function armSilenceWatch(): void {
    clearSilenceWatch();
    resetSilenceTimer();
    // Dictation results already reset the timer (see onFinal/onInterim below), but
    // interim results stop arriving the moment the user falls silent — the mic level
    // is the only signal that still updates after that, so poll it independently.
    levelPollRef.current = setInterval(() => {
      const level = recorderRef.current?.getLevel() ?? 0;
      if (level > VOICE_NOISE_FLOOR) resetSilenceTimer();
    }, 200);
  }

  async function cancelListen(): Promise<void> {
    clearSilenceWatch();
    dictationRef.current?.stop();
    dictationRef.current = null;
    await recorderRef.current?.stop();
    recorderRef.current = null;
    dictatedRef.current = "";
    setListening(false);
    setInterim("");
  }

  async function finishListen(): Promise<void> {
    clearSilenceWatch();
    dictationRef.current?.stop();
    dictationRef.current = null;
    const clip = await recorderRef.current?.stop();
    recorderRef.current = null;
    const said = dictatedRef.current.trim();
    dictatedRef.current = "";
    setListening(false);
    setInterim("");
    if (clip) {
      const bytes = dataUrlBytes(clip.dataUrl);
      const tooBig = attachmentSizeError(labels.voiceClipSizeLabel, bytes, attachedBytesRef.current);
      if (tooBig) {
        // The transcript is already in the input box, so dropping the clip loses the
        // evidence copy but not what the user said.
        setAttachError(tooBig);
        return;
      }
      setAttachments((prev) => [
        ...prev,
        {
          kind: "audio",
          name: `voice${clip.ext}`,
          label: labels.voiceClipLabel,
          mime_type: clip.mime,
          data_url: clip.dataUrl,
          size_bytes: bytes,
          // Travels with the clip rather than only inside the message text. The server
          // has no speech-to-text, so these words are the only readable form of the
          // recording — and keeping them on the same row is what lets a replayed turn
          // show which sentence came out of which clip.
          transcript: said || null,
          duration_ms: clip.durationMs,
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
    setAttachError(null);
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
      setSpeechError(mic.reason === "missing" ? labels.micMissing : labels.micDenied);
      return;
    }

    const dictation = createDictation({
      onFinal: (chunk) => {
        setInput((prev) => appendDictation(prev, chunk));
        dictatedRef.current = appendDictation(dictatedRef.current, chunk);
        resetSilenceTimer();
      },
      onInterim: (chunk) => {
        setInterim(chunk);
        if (chunk.trim()) resetSilenceTimer();
      },
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
      setSpeechError(labels.speechUnsupported);
      return;
    }

    dictatedRef.current = "";
    const recorder = createVoiceRecorder();
    if (recorder) {
      const ok = await recorder.start();
      if (ok) recorderRef.current = recorder;
    }

    dictationRef.current = dictation;
    const started = dictation.start();
    if (!started) {
      setSpeechError(labels.speechStartFailed);
      await finishListen();
      return;
    }
    setListening(true);
    armSilenceWatch();
  }

  function onCameraUse(dataUrl: string) {
    const bytes = dataUrlBytes(dataUrl);
    const tooBig = attachmentSizeError(labels.cameraShotSizeLabel, bytes, attachedBytesRef.current);
    if (tooBig) {
      setAttachError(tooBig);
      setCameraOpen(false);
      return;
    }
    setAttachments((prev) => [
      ...prev,
      {
        kind: "image",
        name: "camera.jpg",
        label: labels.cameraShotLabel,
        mime_type: "image/jpeg",
        data_url: dataUrl,
        size_bytes: bytes,
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
  // Resolved in an effect, not during render: `getSpeechRecognitionCtor` reads
  // `window`, which does not exist in the server pass, so computing it inline made the
  // server and client disagree about this button and React discarded the markup.
  // `null` means "not resolved yet" and renders the supported shape, which is what the
  // vast majority of users get.
  const [hasVoice, setHasVoice] = useState<boolean | null>(null);
  useEffect(() => {
    setHasVoice(getSpeechRecognitionCtor() !== null);
  }, []);

  // Stops any live mic/recognition and the silence watch if the composer unmounts
  // mid-recording (e.g. navigating away) so neither keeps running in the background.
  useEffect(() => {
    return () => {
      clearSilenceWatch();
      dictationRef.current?.stop();
      void recorderRef.current?.stop();
    };
  }, []);
  const voiceSupported = hasVoice !== false;
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
          {labels.dropOverlay}
        </div>
      ) : null}

      {listening && voiceUi === "bar" ? (
        <VoiceCaptureBar
          interim={interim}
          transcript={input}
          onCancel={() => void cancelListen()}
          onFinish={() => void finishListen()}
          labels={labels.voiceCaptureBar}
        />
      ) : null}
      {listening && voiceUi === "orb" ? (
        <VoiceCaptureOrb
          interim={interim}
          transcript={input}
          getAudioLevel={() => recorderRef.current?.getLevel() ?? 0}
          onCancel={() => void cancelListen()}
          onFinish={() => void finishListen()}
          idleHint={labels.voiceOrbIdleHint}
          dragHint={labels.voiceOrbDragHint}
          cancelLabel={labels.voiceOrbCancel}
          finishLabel={labels.voiceOrbFinish}
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
                    labels={labels.imageViewer}
                  />
                ) : att.kind === "audio" && att.data_url ? (
                  <VoiceCard
                    src={att.data_url}
                    transcript={att.transcript}
                    durationMs={att.duration_ms}
                    compact
                    onClear={() => setAttachments((a) => a.filter((_, j) => j !== i))}
                    labels={labels.voiceCard}
                    audioLabels={labels.audioPlayer}
                  />
                ) : (
                  <span className="inline-flex max-w-[180px] items-center rounded-lg bg-surface-sunken px-2.5 py-2 text-xs text-ink-700 ring-1 ring-inset ring-surface-border">
                    <span className="truncate">{att.label ?? att.name}</span>
                  </span>
                )}
                {att.kind !== "audio" ? (
                  <button
                    type="button"
                    className="absolute -right-1.5 -top-1.5 inline-flex size-5 items-center justify-center rounded-full bg-ink-700 text-micro text-white shadow-xs transition hover:bg-danger-600"
                    aria-label={labels.removeAttachmentAria}
                    onClick={() => setAttachments((a) => a.filter((_, j) => j !== i))}
                  >
                    ✕
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}

        {attachError ? (
          <p className="px-3 pt-2 text-xs text-danger-700">{attachError}</p>
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
                ? labels.placeholderBusy
                : listening
                  ? labels.placeholderListening
                  : resolvedPlaceholder
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
              title={labels.attachMenuTitle}
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
                  {labels.attachImage}
                </button>
                <button
                  type="button"
                  className="flex w-full rounded-md px-2.5 py-2 text-left text-xs text-ink-700 transition hover:bg-ink-100"
                  onClick={() => fileRef.current?.click()}
                >
                  {labels.attachFile}
                </button>
                <p className="px-3 pb-1 pt-1 text-micro text-ink-500">
                  {labels.attachPasteHint}
                </p>
              </div>
            ) : null}
            <button
              type="button"
              className={iconBtn}
              title={labels.cameraTitle}
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
            {voiceSupported ? (
              <>
                {!listening ? (
                  <button
                    type="button"
                    className={iconBtn}
                    title={voiceUi === "orb" ? labels.voiceUiBarTitle : labels.voiceUiOrbTitle}
                    onClick={() => setVoiceUi(voiceUi === "orb" ? "bar" : "orb")}
                  >
                    {voiceUi === "orb" ? (
                      <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path
                          strokeLinecap="round"
                          strokeWidth={2}
                          d="M4 12v2M8 9v8M12 6v12M16 9v8M20 12v2"
                        />
                      </svg>
                    ) : (
                      <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="12" cy="12" r="5" strokeWidth={2} />
                        <circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none" />
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
                title={listening ? labels.voiceStopTitle : labels.voiceStartTitle}
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
            ) : (
              // Safari and some Android browsers have no SpeechRecognition. Recording
              // anyway would archive a clip nothing in this version can read, so the
              // button stays disabled — but visible, because a control that silently
              // disappears reads as a broken page rather than an unsupported browser.
              <button
                type="button"
                className={iconBtn}
                title={labels.voiceUnsupportedTitle}
                aria-label={labels.voiceUnsupportedAria}
                disabled
              >
                <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 14a3 3 0 003-3V7a3 3 0 10-6 0v4a3 3 0 003 3zm7-1v1a7 7 0 01-14 0v-1M12 19v3M4 4l16 16"
                  />
                </svg>
              </button>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-0.5">
            {isSidebar ? (
              <TokenMeter context={context} busy={busy} closeAria={labels.tokenMeterCloseAria} />
            ) : null}
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
            title={busy ? labels.stopTitle : labels.sendTitle}
            aria-label={busy ? labels.stopAria : labels.sendAria}
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
        {labels.footerHint(context.percent)}
      </p>
      ) : null}

      {cameraOpen ? (
        <CameraPage onClose={() => setCameraOpen(false)} onUse={onCameraUse} labels={labels.camera} />
      ) : null}
    </div>
  );
}
