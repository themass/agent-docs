import type { AudioPlayer } from '@xuexi/scene-runtime';

/**
 * Browser audio. Two things that break on phones are handled here rather than in scene code:
 * autoplay blocking (unlock on first gesture) and audio focus loss (becomes a pause, not a crash).
 */
export function createWebAudio(getUrl: (assetId: string) => string): AudioPlayer {
  let el: HTMLAudioElement | null = null;
  let ducked = false;
  const listeners = new Set<(paused: boolean) => void>();
  const fire = (paused: boolean) => listeners.forEach(cb => cb(paused));

  const attach = () => {
    if (el || typeof Audio === 'undefined') return;
    el = new Audio();
    el.addEventListener('pause', () => { if (!el?.ended) fire(true); });
    el.addEventListener('play', () => fire(false));
  };

  return {
    async play(assetId) {
      attach();
      if (!el) return;
      el.src = getUrl(assetId);
      el.volume = ducked ? 0.25 : 1;
      // Autoplay policy: the first call may need a gesture. A failure (blocked, 404, undecodable) is announced as an
      // interruption AND rethrown, so the caller can fall back to the caption text instead of showing a silent player.
      try { await el.play(); }
      catch (e) { fire(true); throw e; }
    },
    pause() { el?.pause(); },
    stop() { if (el) { el.pause(); el.currentTime = 0; } },
    onInterrupt(cb) { listeners.add(cb); return () => listeners.delete(cb); },
    setDuck(enabled) { ducked = enabled; if (el) el.volume = enabled ? 0.25 : 1; },
  };
}
