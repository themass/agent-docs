import { stopMediaStream } from "@/lib/camera-capture";

export type VoiceClip = {
  dataUrl: string;
  mime: string;
  ext: string;
};

type LevelMonitor = {
  getLevel: () => number;
  dispose: () => void;
};

function attachLevelMonitor(stream: MediaStream): LevelMonitor {
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  analyser.smoothingTimeConstant = 0.82;
  source.connect(analyser);
  const bins = new Uint8Array(analyser.frequencyBinCount);
  return {
    getLevel() {
      analyser.getByteFrequencyData(bins);
      let sum = 0;
      for (let i = 0; i < bins.length; i += 1) sum += bins[i]!;
      return Math.min(1, sum / bins.length / 96);
    },
    dispose() {
      source.disconnect();
      void ctx.close().catch(() => undefined);
    },
  };
}

function audioExtForMime(mime: string): string {
  const base = mime.split(";")[0]!.trim().toLowerCase();
  if (base === "audio/mp4" || base === "audio/aac" || base === "audio/m4a") return ".m4a";
  if (base === "audio/mpeg" || base === "audio/mp3") return ".mp3";
  if (base === "audio/ogg" || base === "audio/opus") return ".ogg";
  if (base === "audio/wav" || base === "audio/wave") return ".wav";
  return ".webm";
}

function pickRecorderMime(): string {
  if (typeof MediaRecorder === "undefined" || typeof MediaRecorder.isTypeSupported !== "function") {
    return "audio/webm";
  }
  for (const type of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"]) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return "";
}

export function createVoiceRecorder(): {
  start: () => Promise<boolean>;
  stop: () => Promise<VoiceClip | null>;
  getLevel: () => number;
} | null {
  if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) return null;
  if (typeof MediaRecorder === "undefined") return null;
  let stream: MediaStream | null = null;
  let recorder: MediaRecorder | null = null;
  let levelMonitor: LevelMonitor | null = null;
  let chunks: Blob[] = [];
  let mime = pickRecorderMime();

  return {
    async start() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        levelMonitor = attachLevelMonitor(stream);
        recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
        mime = recorder.mimeType || mime || "audio/webm";
        chunks = [];
        recorder.ondataavailable = (event) => {
          if (event.data.size) chunks.push(event.data);
        };
        recorder.start();
        return true;
      } catch {
        levelMonitor?.dispose();
        levelMonitor = null;
        stopMediaStream(stream);
        stream = null;
        recorder = null;
        return false;
      }
    },
    getLevel() {
      return levelMonitor?.getLevel() ?? 0;
    },
    stop() {
      return new Promise((resolve) => {
        const rec = recorder;
        recorder = null;
        levelMonitor?.dispose();
        levelMonitor = null;
        if (!rec || rec.state === "inactive") {
          stopMediaStream(stream);
          stream = null;
          resolve(null);
          return;
        }
        rec.onstop = () => {
          stopMediaStream(stream);
          stream = null;
          const blob = new Blob(chunks, { type: mime || "audio/webm" });
          chunks = [];
          if (!blob.size) {
            resolve(null);
            return;
          }
          const reader = new FileReader();
          reader.onload = () => {
            const dataUrl = String(reader.result ?? "");
            resolve(
              dataUrl.startsWith("data:audio/")
                ? { dataUrl, mime: mime || "audio/webm", ext: audioExtForMime(mime || "audio/webm") }
                : null,
            );
          };
          reader.onerror = () => resolve(null);
          reader.readAsDataURL(blob);
        };
        rec.stop();
      });
    },
  };
}
