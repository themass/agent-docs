import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, LogIn, UserRound } from 'lucide-react'

import {
  isNewApiLoggedIn,
  loadNewApiAuth,
  startNewApiLogin,
  type NewApiAuthState,
} from '../lib/newapi-auth'
import { openOptionsPage, openOptionsPageFromPopup } from '../lib/surface-launch'
import { STORAGE } from '../lib/settings'
import { useI18n } from '../i18n'
import { cn } from '../lib/cn'

type Props = {
  variant?: 'popup' | 'chat' | 'palette'
  /** Popup footer: single-line label, no subtitle */
  compact?: boolean
  /** Popup footer: ultra-slim strip (~28px), quota in tooltip only */
  strip?: boolean
  /** Popup footer: borderless inline row */
  inline?: boolean
  /** Popup header: compact account pill */
  chip?: boolean
  className?: string
}

function displayUser(auth: NewApiAuthState): string {
  const user = auth.user
  if (user?.displayName?.trim()) return user.displayName.trim()
  if (user?.email?.trim()) return user.email.trim()
  return 'NewAPI'
}

export function AuthStatusBar({ variant = 'popup', compact = false, strip = false, inline = false, chip = false, className }: Props) {
  const { t } = useI18n()
  const [auth, setAuth] = useState<NewApiAuthState | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    setAuth(await loadNewApiAuth())
  }, [])

  useEffect(() => {
    void refresh()
    const onStorage = (changes: Record<string, chrome.storage.StorageChange>, area: string) => {
      if (area !== 'local' || !changes[STORAGE.newapiAuth]) return
      void refresh()
    }
    chrome.storage.onChanged.addListener(onStorage)
    const onMsg = (message: unknown) => {
      if ((message as { type?: string })?.type === 'NEWAPI_AUTH_DONE') void refresh()
    }
    chrome.runtime.onMessage.addListener(onMsg)
    return () => {
      chrome.storage.onChanged.removeListener(onStorage)
      chrome.runtime.onMessage.removeListener(onMsg)
    }
  }, [refresh])

  if (!auth) return null

  const managed = auth.mode === 'managed'
  const loggedIn = managed && isNewApiLoggedIn(auth)
  const manual = auth.mode === 'manual'

  async function handleClick(): Promise<void> {
    if (busy) return
    if (manual || loggedIn) {
      if (variant === 'popup') {
        openOptionsPageFromPopup('account')
        window.close()
        return
      }
      await openOptionsPage('account')
      return
    }
    setBusy(true)
    try {
      await startNewApiLogin()
      await refresh()
    } catch (error) {
      window.alert((error as Error).message || t('authBar.loginFailed'))
    } finally {
      setBusy(false)
    }
  }

  const label = manual
    ? t('authBar.manualMode')
    : loggedIn
      ? displayUser(auth)
      : t('authBar.signIn')

  const hint = manual
    ? t('authBar.manualHint')
    : loggedIn
      ? auth.user?.quotaUsd != null
        ? t('authBar.quota', { amount: `$${auth.user.quotaUsd.toFixed(2)}` })
        : t('authBar.connected')
      : t('authBar.signInHint')

  const palette = variant === 'palette'
  const chat = variant === 'chat'

  const slim = compact || strip || inline || chip
  const quotaText =
    loggedIn && auth.user?.quotaUsd != null ? `$${auth.user.quotaUsd.toFixed(2)}` : null

  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => void handleClick()}
      className={cn(
        'flex items-center text-left transition-colors disabled:opacity-60',
        inline
          ? 'nf-auth-inline w-full justify-between gap-2 py-0.5'
          : chip
            ? 'nf-popup-account-chip max-w-[108px] shrink-0 gap-1.5 px-2.5 py-1'
            : strip
            ? 'nf-auth-strip w-full gap-1.5'
            : slim
              ? 'min-w-0 flex-1 gap-2 nf-popup-footer-btn'
              : 'w-full gap-2.5',
        palette
          ? 'rounded-xl border border-[rgba(15,20,18,.1)] bg-white px-3 py-2 hover:bg-[#f4f7f5]'
          : chat
            ? 'border-t border-border/60 bg-muted/30 px-3 py-2 hover:bg-muted/50'
            : inline
              ? 'border-0 bg-transparent hover:opacity-80'
              : chip
                ? 'nf-popup-account-chip border border-[var(--nf-line)] bg-[#fffef9] hover:border-[var(--nf-ink)]'
                : strip
                ? 'nf-auth-strip border border-[var(--nf-line)] bg-white hover:bg-[#f4f7f5]'
                : slim
                  ? 'nf-popup-footer-btn border border-[var(--nf-line)] bg-white hover:bg-[#f4f7f5]'
                  : 'nf-popup-btn border border-[var(--nf-line)] bg-white hover:bg-[#f4f7f5]',
        loggedIn && !palette && !chat && !strip && !inline && !chip && 'border-emerald-200 bg-emerald-50/80',
        loggedIn && strip && 'border-emerald-200/80 bg-emerald-50/60',
        loggedIn && chip && 'border-emerald-300/80 bg-emerald-50/90',
        className
      )}
      title={hint}
    >
      {chip ? (
        <>
          <span
            className={cn(
              'size-1.5 shrink-0 rounded-full',
              loggedIn ? 'bg-emerald-500' : manual ? 'bg-[var(--nf-muted)]' : 'bg-amber-400'
            )}
          />
          <span className="min-w-0 truncate text-[10px] font-semibold leading-none text-[var(--nf-ink)]">
            {busy ? '…' : loggedIn ? label : t('authBar.signIn')}
          </span>
        </>
      ) : inline ? (
        <>
          <span className="flex min-w-0 items-center gap-1 overflow-hidden">
            {loggedIn ? (
              <CheckCircle2 className="size-2.5 shrink-0 text-emerald-600" />
            ) : manual ? (
              <UserRound className="size-2.5 shrink-0 text-[var(--nf-muted)]" />
            ) : (
              <LogIn className="size-2.5 shrink-0 text-[var(--nf-muted)]" />
            )}
            <span className="truncate text-[9px] font-semibold leading-none text-[var(--nf-ink)]">
              {busy ? t('authBar.signingIn') : label}
            </span>
          </span>
          {quotaText ? (
            <span className="shrink-0 text-[9px] tabular-nums text-[var(--nf-muted)]">{quotaText}</span>
          ) : null}
        </>
      ) : (
        <>
      {loggedIn ? (
        <CheckCircle2
          className={cn(
            'shrink-0 text-emerald-600',
            strip ? 'size-2.5' : slim || palette ? 'size-3' : 'size-4',
            palette && 'text-emerald-600'
          )}
        />
      ) : manual ? (
        <UserRound className={cn('shrink-0 text-[var(--nf-muted)]', strip ? 'size-2.5' : slim ? 'size-3' : 'size-4')} />
      ) : (
        <LogIn className={cn('shrink-0 text-[var(--nf-muted)]', strip ? 'size-2.5' : slim ? 'size-3' : 'size-4')} />
      )}
      <span className="min-w-0 flex-1 overflow-hidden">
        <span
          className={cn(
            'block truncate font-semibold',
            strip
              ? 'text-[9px] leading-none whitespace-nowrap'
              : slim
                ? 'text-[10px] leading-tight whitespace-nowrap'
                : palette
                  ? 'text-[13px] text-[#0f1412]'
                  : chat
                    ? 'text-xs text-foreground'
                    : 'text-sm'
          )}
        >
          {busy ? t('authBar.signingIn') : label}
        </span>
        {!slim ? (
          <span
            className={cn(
              'block truncate',
              palette
                ? 'text-[11px] text-[#5c6b62]'
                : chat
                  ? 'text-[10px] text-muted-foreground'
                  : 'text-xs text-[var(--nf-muted)]'
            )}
          >
            {hint}
          </span>
        ) : null}
      </span>
        </>
      )}
    </button>
  )
}
