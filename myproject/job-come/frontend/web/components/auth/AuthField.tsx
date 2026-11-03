"use client";

import { useState, type InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
};

/** Labelled text input used across the auth pages. */
export function AuthField({ label, hint, ...input }: Props) {
  const [revealed, setRevealed] = useState(false);
  const isPassword = input.type === "password";
  return (
    <label className="block">
      <span className="text-sm font-medium text-ink-800">{label}</span>
      <span className="relative mt-1.5 block">
        <input
          {...input}
          type={isPassword && revealed ? "text" : input.type}
          className={isPassword ? "field pr-10" : "field"}
        />
        {isPassword ? (
          <button
            type="button"
            onClick={() => setRevealed((value) => !value)}
            aria-label={revealed ? "隐藏密码" : "显示密码"}
            aria-pressed={revealed}
            title={revealed ? "隐藏密码" : "显示密码"}
            className="absolute inset-y-0 right-0 flex items-center px-3 text-ink-500 hover:text-ink-900"
          >
            {revealed ? (
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M3 3l18 18" />
                <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" />
                <path d="M9.9 5.1A10.4 10.4 0 0 1 12 5c6 0 9.5 7 9.5 7a17.6 17.6 0 0 1-3.2 4.1M6.6 6.6C3.9 8.4 2.5 12 2.5 12s3.5 7 9.5 7a10 10 0 0 0 4.1-.9" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            )}
          </button>
        ) : null}
      </span>
      {hint ? <span className="mt-1 block text-xs text-ink-500">{hint}</span> : null}
    </label>
  );
}
