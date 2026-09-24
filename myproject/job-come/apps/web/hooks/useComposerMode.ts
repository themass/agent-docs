"use client";

import { useState } from "react";

import type { ComposerMode } from "@/lib/composer-mode";

/** Composer mode hook — always legacy (full composer). */
export function useComposerMode(): [ComposerMode, (mode: ComposerMode) => void] {
  const [, setModeState] = useState<ComposerMode>("legacy");
  const setMode = () => setModeState("legacy");
  return ["legacy", setMode];
}
