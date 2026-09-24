/** Composer mode — legacy full composer is the only supported mode. */

export type ComposerMode = "legacy";

const STORAGE_KEY = "jobcome_composer_mode";

export function getComposerMode(): ComposerMode {
  if (typeof window !== "undefined") {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "aui") {
      localStorage.setItem(STORAGE_KEY, "legacy");
    }
  }
  return "legacy";
}

export function setComposerMode(_mode: ComposerMode): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, "legacy");
}
