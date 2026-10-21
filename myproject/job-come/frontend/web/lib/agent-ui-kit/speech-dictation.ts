/** Web Speech API dictation (naviforge pattern, web-only). */

type SpeechRec = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};

type SpeechRecEvent = {
  resultIndex: number;
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>;
};

export function getSpeechRecognitionCtor(): (new () => SpeechRec) | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRec;
    webkitSpeechRecognition?: new () => SpeechRec;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function speechErrorMessage(code: string): string {
  if (code === "no-speech" || code === "aborted") return "";
  if (code === "not-allowed" || code === "service-not-allowed") {
    return "没有麦克风权限，请在浏览器站点设置中允许麦克风。";
  }
  if (code === "audio-capture") return "没有找到麦克风";
  if (code === "network") return "语音识别需要网络连接";
  return `语音识别失败（${code}）`;
}

export function dictationShouldKeepListening(code: string): boolean {
  return code === "no-speech";
}

export function appendDictation(existing: string, chunk: string): string {
  const add = chunk.trim();
  if (!add) return existing;
  const base = existing.trimEnd();
  if (!base) return add;
  if (/[\u4e00-\u9fff]$/.test(base) || /^[\u4e00-\u9fff]/.test(add)) return `${base}${add}`;
  return `${base} ${add}`;
}

export async function ensureMicrophoneAccess(): Promise<
  { ok: true } | { ok: false; reason: "unsupported" | "denied" | "missing" }
> {
  if (!navigator.mediaDevices?.getUserMedia) return { ok: false, reason: "unsupported" };
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    return { ok: true };
  } catch (error) {
    const name =
      error && typeof error === "object" && "name" in error ? String((error as { name: string }).name) : "";
    if (name === "NotFoundError" || name === "DevicesNotFoundError") return { ok: false, reason: "missing" };
    return { ok: false, reason: "denied" };
  }
}

export function createDictation(opts: {
  getLang?: () => string;
  onFinal: (text: string) => void;
  onInterim: (text: string) => void;
  onError: (code: string) => void;
  onEnd: () => void;
}): { start: () => boolean; stop: () => void } | null {
  const Ctor = getSpeechRecognitionCtor();
  if (!Ctor) return null;

  const Recognition = Ctor;
  let want = false;
  let rec: SpeechRec | null = null;

  function resolveLang(): string {
    return opts.getLang?.() ?? "zh-CN";
  }

  function start(): boolean {
    if (want) return true;
    want = true;
    rec = new Recognition();
    rec.lang = resolveLang();
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (event) => {
      let finalChunk = "";
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const piece = event.results[i];
        if (!piece) continue;
        if (piece.isFinal) finalChunk += piece[0].transcript;
        else interim += piece[0].transcript;
      }
      if (finalChunk) opts.onFinal(finalChunk.trim());
      opts.onInterim(interim.trim());
    };
    rec.onerror = (event) => {
      if (!dictationShouldKeepListening(event.error)) want = false;
      opts.onError(event.error);
    };
    rec.onend = () => {
      if (want && rec) {
        try {
          rec.lang = resolveLang();
          rec.start();
          return;
        } catch {
          want = false;
        }
      }
      rec = null;
      opts.onInterim("");
      opts.onEnd();
    };
    try {
      rec.start();
      return true;
    } catch {
      want = false;
      rec = null;
      opts.onError("start-failed");
      return false;
    }
  }

  function stop(): void {
    want = false;
    rec?.stop();
  }

  return { start, stop };
}
