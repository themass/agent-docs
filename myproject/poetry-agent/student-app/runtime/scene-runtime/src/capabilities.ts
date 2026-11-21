/**
 * Platform seam. The runtime never touches document/window/Audio/fetch directly: the host injects
 * these. That single rule is what makes Android/iOS a ~1-2 week shell instead of a rewrite —
 * the shell swaps implementations, the scene code does not move.
 */
export interface AudioPlayer {
  play(assetId: string, opts?: { resumeAfterInterrupt?: boolean }): Promise<void>;
  pause(): void;
  stop(): void;
  /** Phone calls / other apps stealing audio focus. Native shells get real events here. */
  onInterrupt(cb: (paused: boolean) => void): () => void;
  setDuck(enabled: boolean): void;
}

export interface Recorder {
  /** Product rule: student recordings stay on device unless a parent explicitly opts in. */
  start(opts: { localOnly: true }): Promise<void>;
  stop(): Promise<{ assetId: string; bytes: number }>;
  playback(assetId: string): Promise<void>;
  delete(assetId: string): Promise<void>;
}

export interface AssetLoader {
  /** Content-addressed: the hash is the url. Offline + rollback both depend on this. */
  fetch(manifest: { bundle_hash: string }, assetId: string, path: string): Promise<Uint8Array>;
  probe(): Promise<{ weakNetwork: boolean }>;
}

export interface Storage {
  /** Native shells back this with the app sandbox; the web build with OPFS/IndexedDB. */
  put(key: string, bytes: Uint8Array): Promise<void>;
  get(key: string): Promise<Uint8Array | null>;
  usage(): Promise<number>;
  evict(keys: string[]): Promise<void>;
  keys(): Promise<string[]>;
}

export interface SafeArea {
  insets(): { top: number; bottom: number; left: number; right: number };
  orientation(): 'portrait' | 'landscape';
}

export interface Telemetry {
  /** No student identity, no third-party trackers. Resettable anonymous device id only. */
  event(name: string, props?: Record<string, string | number | boolean>): void;
}

export interface Share { shareUrl(url: string, title: string): Promise<void>; }
export interface ParentGate { isUnlocked(): Promise<boolean>; unlock(): Promise<boolean>; }

/** One WebGL context per page, ever. Capability probe, not user-agent sniffing. */
export interface Graphics {
  supportsWebGL(): boolean;
  onContextLost(cb: () => void): () => void;
  frameRate(): number;
  deviceMemoryMB(): number | null;
  prefersReducedMotion(): boolean;
}

export interface Platform {
  audio: AudioPlayer;
  recorder: Recorder;
  loader: AssetLoader;
  storage: Storage;
  safeArea: SafeArea;
  telemetry: Telemetry;
  share: Share;
  parentGate: ParentGate;
  graphics: Graphics;
}
