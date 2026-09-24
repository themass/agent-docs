import {
  ArrowUp,
  Camera,
  ChevronDown,
  CircleDot,
  Crop,
  ImageIcon,
  Mic,
  Monitor,
  PanelTop,
  Plus,
  Square,
  X,
} from 'lucide-react'
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ClipboardEvent as ReactClipboardEvent, type KeyboardEvent as ReactKeyboardEvent, type ReactNode } from 'react'

import { formatProfilePickerLabel, type ModelProfile } from '../../lib/llm-profiles'
import { useI18n } from '../../i18n'
import { browserLanguages } from '../../i18n/locales'
import { textInputLangProps } from '../../lib/text-input-lang'
import { appendDictation, createDictation, ensureMicrophoneAccess, getCachedLastSpeechLang, openExtensionSiteSettings, resolveSpeechRecognitionLang, speechErrorI18nKey } from '../../lib/speech-dictation'
import { hydrateSpeechLangCache, useSpeechLangSettings, type SpeechLangConfig } from '../../lib/speech-lang'
import { createVoiceRecorder, type VoiceClip } from '../../lib/audio-record'
import { useVoiceUiMode } from '../../lib/voice-ui'
import type { ContextBreakdown } from '@naviforge/context-metrics'
import { ContextMeter } from '../../modules/context-meter'
import { cn } from '../../lib/cn'
import { composerEnterIntent } from './composer-key'
import {
  parseSlashDraftWithRegistry,
  resolveSlashCommand,
  SLASH_COMMAND_NAME_PATTERN,
  type SlashCommandDef,
} from './composer-slash-registry'
import { SlashCommandMenu, SlashInputHighlight, slashMenuItems } from './composer-slash'
import { VoiceCard } from './voice-card'
import { VoiceCaptureBar } from './voice-capture-bar'
import { VoiceCaptureOrb } from './voice-capture-orb'
import { ZoomableImage } from './zoomable-image'

const iconBtn =
  'inline-flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:pointer-events-none disabled:opacity-40'

function PageChip({
  label,
  active,
  disabled,
  onClick,
}: {
  label: string
  active?: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded-full border px-2.5 py-0.5 text-[11px] leading-5 transition-colors disabled:opacity-40 ${
        active
          ? 'border-primary/30 bg-primary/10 text-primary'
          : 'border-transparent bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground'
      }`}
    >
      {label}
    </button>
  )
}

function ModelPicker({
  profiles,
  activeId,
  open,
  onOpenChange,
  onSelect,
}: {
  profiles: ModelProfile[]
  activeId?: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSelect: (id: string) => void
}) {
  const active = profiles.find((profile) => profile.id === activeId) ?? profiles[0]
  if (!active) return null
  return (
    <div className="relative min-w-0">
      <button
        type="button"
        className="flex max-w-[10.5rem] items-center gap-1 rounded-full border border-border/70 bg-muted/30 px-2.5 py-1.5 text-left text-[12px] leading-4 text-muted-foreground hover:bg-muted hover:text-foreground"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="选择模型"
        title={formatProfilePickerLabel(active)}
        onClick={() => onOpenChange(!open)}
      >
        <span className="truncate">{formatProfilePickerLabel(active)}</span>
        <ChevronDown className="size-3 shrink-0 opacity-50" />
      </button>
      {open ? (
        <div
          role="listbox"
          className="absolute bottom-full left-0 z-20 mb-1 max-h-56 min-w-[12.5rem] overflow-y-auto rounded-xl border border-border/80 bg-background py-1 shadow-lg"
        >
          {profiles.map((profile) => (
            <button
              key={profile.id}
              type="button"
              role="option"
              aria-selected={profile.id === active.id}
              className={`flex w-full px-3 py-1.5 text-left text-[12px] hover:bg-muted ${
                profile.id === active.id ? 'text-foreground' : 'text-muted-foreground'
              }`}
              onClick={() => {
                onSelect(profile.id)
                onOpenChange(false)
              }}
            >
              {formatProfilePickerLabel(profile)}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function SendOrStop({
  showStop,
  canSubmit,
  sendTitle,
  onStop,
  onSubmit,
}: {
  showStop: boolean
  canSubmit: boolean
  sendTitle: string
  onStop: () => void
  onSubmit: () => void
}) {
  if (showStop) {
    return (
      <button
        type="button"
        className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-foreground text-background hover:opacity-90"
        onClick={onStop}
        title="停止"
        aria-label="停止"
      >
        <Square className="size-2.5 fill-current" />
      </button>
    )
  }
  return (
    <button
      type="button"
      className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:pointer-events-none disabled:opacity-30"
      onClick={onSubmit}
      disabled={!canSubmit}
      title={sendTitle}
      aria-label="发送"
    >
      <ArrowUp className="size-4" />
    </button>
  )
}

function ImageTile({
  label,
  name,
  disabled,
  onClick,
  children,
}: {
  label: string
  name?: string
  disabled?: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-label={name ?? label}
      className="flex flex-col items-center gap-1 rounded-xl border border-border/80 bg-muted/40 px-1.5 py-2 text-center hover:bg-muted disabled:opacity-40"
    >
      <span className="flex size-8 items-center justify-center text-muted-foreground">{children}</span>
      <span className="w-full truncate text-[11px] leading-4 text-foreground">{label}</span>
    </button>
  )
}

export function Composer({
  value,
  onChange,
  onSubmit,
  onSteer,
  onStop,
  onSlashCommand,
  slashCommands = [],
  running,
  awaitingQuestion,
  placeholder,
  wide,
  pageAskMode,
  onPageAskModeChange,
  onSummarize,
  onExplainPick,
  onCopyArticle,
  hasPickedElement,
  onPick,
  pickingElement,
  actingLabel,
  pickDisabled,
  imageAttachment,
  onClearAttachment,
  recentShots,
  onRefreshShots,
  onAttachViewport,
  onAttachShot,
  onAttachFile,
  onLaunchScreenshotStudio,
  onOpenCamera,
  shotAskHint,
  voiceAttachment,
  onClearVoice,
  onAttachVoice,
  modelProfiles,
  activeProfileId,
  onSelectModelProfile,
  contextBreakdown,
  runTotal,
  runTokenBudget,
}: {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void | Promise<void>
  onSteer?: () => void
  onSlashCommand?: (name: string, body: string) => void | Promise<boolean>
  slashCommands?: SlashCommandDef[]
  onStop: () => void
  running: boolean
  awaitingQuestion: boolean
  placeholder: string
  wide?: boolean
  pageAskMode?: boolean
  onPageAskModeChange?: (enabled: boolean) => void
  onSummarize?: () => void
  onExplainPick?: () => void
  onCopyArticle?: () => void
  hasPickedElement?: boolean
  onPick?: () => void
  pickingElement?: boolean
  actingLabel?: string | null
  pickDisabled?: boolean
  imageAttachment?: { dataUrl: string; label: string } | null
  onClearAttachment?: () => void
  recentShots?: Array<{ path: string; name: string; thumb?: string }>
  onRefreshShots?: () => void
  onAttachViewport?: () => void
  onAttachShot?: (path: string) => void
  onAttachFile?: (file: File) => void
  /** 框选区域 → 新标签页标注（⌘⇧S） */
  onLaunchScreenshotStudio?: () => void
  onOpenCamera?: () => void
  shotAskHint?: boolean
  voiceAttachment?: { dataUrl: string; path?: string; label: string } | null
  onClearVoice?: () => void
  onAttachVoice?: (clip: VoiceClip) => Promise<void>
  modelProfiles?: ModelProfile[]
  activeProfileId?: string
  onSelectModelProfile?: (profileId: string) => void
  contextBreakdown?: ContextBreakdown | null
  runTotal?: number
  runTokenBudget?: number
}) {
  const { t } = useI18n()
  const inputLang = textInputLangProps()
  const showStop = running
  const askMode = Boolean(pageAskMode)
  const menuOff = running
  const canAttach = Boolean(onAttachViewport || onAttachShot || onAttachFile || onLaunchScreenshotStudio)
  const canPlus = Boolean(canAttach || onOpenCamera)
  const hasPageChips = Boolean(
    onPageAskModeChange || onSummarize || onExplainPick || onCopyArticle || onPick
  )
  const emptyHeight = 22
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const slashPickPendingRef = useRef(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const plusRef = useRef<HTMLDivElement>(null)
  const modelRef = useRef<HTMLDivElement>(null)
  const valueRef = useRef(value)
  const onChangeRef = useRef(onChange)
  const dictationRef = useRef<ReturnType<typeof createDictation>>(null)
  const recorderRef = useRef<ReturnType<typeof createVoiceRecorder>>(null)
  const listeningRef = useRef(false)
  const onAttachVoiceRef = useRef(onAttachVoice)
  const [attachOpen, setAttachOpen] = useState(false)
  const [modelOpen, setModelOpen] = useState(false)
  const [listening, setListening] = useState(false)
  const [voiceUi, setVoiceUi] = useVoiceUiMode()
  const [speechLangConfig, updateSpeechLangConfig] = useSpeechLangSettings()
  const [interim, setInterim] = useState('')
  const [speechError, setSpeechError] = useState<string | null>(null)
  const [slashMenuIndex, setSlashMenuIndex] = useState(0)
  const slashDraft = parseSlashDraftWithRegistry(value, null, slashCommands)
  const slashMenuOpen =
    slashDraft.kind === 'menu' && !listening && Boolean(onSlashCommand)
  const slashMenuQuery = slashDraft.kind === 'menu' ? slashDraft.query : ''
  const slashHighlightMode =
    slashDraft.kind === 'menu' || slashDraft.kind === 'locked' ? slashDraft.kind : null
  const slashMenuChoices = useMemo(
    () => slashMenuItems(slashMenuQuery, slashCommands),
    [slashMenuQuery, slashCommands]
  )
  const canSubmit = Boolean(
    value.trim() || imageAttachment || voiceAttachment || listening
  )
  const profiles = modelProfiles ?? []
  const sendTitle =
    imageAttachment || askMode ? '看图问答 · Enter' : running ? '下一问 · Enter' : '运行 · Enter'

  valueRef.current = value
  onChangeRef.current = onChange
  onAttachVoiceRef.current = onAttachVoice
  const speechLangConfigRef = useRef(speechLangConfig)
  speechLangConfigRef.current = speechLangConfig
  const speechHintRef = useRef('')

  useEffect(() => {
    void hydrateSpeechLangCache()
  }, [])

  useEffect(() => {
    const session = createDictation({
      getLang: () =>
        resolveSpeechRecognitionLang({
          config: speechLangConfigRef.current,
          hintText: [valueRef.current, speechHintRef.current].filter(Boolean).join(' '),
          lastSpeechLang: getCachedLastSpeechLang(),
          languages: browserLanguages(),
        }),
      getTargetLangs: () =>
        speechLangConfigRef.current.mode === 'fixed'
          ? [speechLangConfigRef.current.fixed]
          : speechLangConfigRef.current.targets,
      onFinal: (chunk) => onChangeRef.current(appendDictation(valueRef.current, chunk)),
      onInterim: (text) => {
        speechHintRef.current = text
        setInterim(text)
      },
      onError: (code) => {
        const key = speechErrorI18nKey(code)
        setSpeechError(key ? t(key, key === 'chat.speech.failed' ? { code } : undefined) : null)
        setListening(false)
        listeningRef.current = false
        void stopAndAttach()
      },
      onEnd: () => {
        setListening(false)
        listeningRef.current = false
        setInterim('')
      },
    })
    dictationRef.current = session
    return () => {
      session?.stop()
      void recorderRef.current?.stop()
      recorderRef.current = null
    }
  }, [])

  useLayoutEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = '0px'
    el.style.height = `${Math.max(emptyHeight, el.scrollHeight)}px`
  }, [value])

  useLayoutEffect(() => {
    if (!slashPickPendingRef.current) return
    slashPickPendingRef.current = false
    const el = textareaRef.current
    if (!el) return
    const pos = el.value.length
    el.focus()
    el.setSelectionRange(pos, pos)
  }, [value, slashDraft.kind])

  useEffect(() => {
    setSlashMenuIndex(0)
  }, [slashMenuQuery])

  useEffect(() => {
    if (!attachOpen && !modelOpen) return
    const onDoc = (event: MouseEvent) => {
      const t = event.target as Node
      if (plusRef.current?.contains(t) || modelRef.current?.contains(t)) return
      setAttachOpen(false)
      setModelOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setAttachOpen(false)
        setModelOpen(false)
      }
    }
    document.addEventListener('click', onDoc)
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('click', onDoc)
      window.removeEventListener('keydown', onKey)
    }
  }, [attachOpen, modelOpen])

  async function startRecorder(): Promise<void> {
    const rec = createVoiceRecorder()
    if (!rec) return
    const ok = await rec.start()
    if (!ok) return
    if (!listeningRef.current) {
      const clip = await rec.stop()
      if (clip) await onAttachVoiceRef.current?.(clip)
      return
    }
    recorderRef.current = rec
  }

  async function stopAndAttach(): Promise<void> {
    const rec = recorderRef.current
    recorderRef.current = null
    const clip = rec ? await rec.stop() : null
    if (clip) await onAttachVoiceRef.current?.(clip)
  }

  async function beginListen(): Promise<void> {
    setSpeechError(null)
    speechHintRef.current = ''
    const session = dictationRef.current
    if (!session) {
      setSpeechError(t('chat.speech.unsupported'))
      return
    }
    const mic = await ensureMicrophoneAccess()
    if (!mic.ok) {
      setSpeechError(t(`chat.speech.${mic.reason === 'denied' ? 'notAllowed' : mic.reason === 'missing' ? 'missing' : 'unsupported'}`))
      return
    }
    if (session.start()) {
      listeningRef.current = true
      setListening(true)
      void startRecorder()
    }
  }

  function endListen(): void {
    dictationRef.current?.stop()
  }

  async function finishListen(opts?: { discardClip?: boolean }): Promise<void> {
    endListen()
    if (opts?.discardClip) {
      const rec = recorderRef.current
      recorderRef.current = null
      if (rec) await rec.stop()
      return
    }
    await stopAndAttach()
  }

  async function cancelListen(): Promise<void> {
    speechHintRef.current = ''
    setInterim('')
    await finishListen({ discardClip: true })
  }

  function onSpeechLangChange(next: SpeechLangConfig): void {
    updateSpeechLangConfig(next)
    if (listeningRef.current) dictationRef.current?.refreshLang()
  }

  async function toggleListen(): Promise<void> {
    if (listeningRef.current) {
      await finishListen()
      return
    }
    await beginListen()
  }

  function pickSlashCommand(command: SlashCommandDef): void {
    slashPickPendingRef.current = true
    onChange(`/${command.name} `)
  }

  function handleComposerChange(next: string): void {
    onChange(next)
  }

  async function submit(): Promise<void> {
    if (listeningRef.current) await finishListen()
    if (onSlashCommand && value.startsWith('/')) {
      const headMatch = value
        .slice(1)
        .match(new RegExp(`^(${SLASH_COMMAND_NAME_PATTERN})(?:\\s+([\\s\\S]*))?$`))
      const command = headMatch?.[1]
        ? resolveSlashCommand(headMatch[1], slashCommands)
        : undefined
      if (command) {
        const body = (headMatch?.[2] ?? '').trimStart()
        const handled = await onSlashCommand(command.name, body)
        if (handled) {
          onChange('')
        }
        return
      }
    }
    await onSubmit()
  }

  function onMicClick(): void {
    void toggleListen()
  }

  function closeMenu(): void {
    setAttachOpen(false)
    setModelOpen(false)
  }

  function onComposerPaste(event: ReactClipboardEvent<HTMLTextAreaElement>): void {
    if (!onAttachFile || menuOff) return
    const item = [...event.clipboardData.items].find((entry) => entry.type.startsWith('image/'))
    const file = item?.getAsFile()
    if (!file) return
    event.preventDefault()
    onAttachFile(file)
  }

  const composerInputValue = listening ? appendDictation(value, interim) : value
  const slashHighlightText = slashHighlightMode ? composerInputValue : ''
  const slashArgsPlaceholder =
    slashDraft.kind === 'locked'
      ? slashDraft.command.argumentHint
        ? `参数 ${slashDraft.command.argumentHint}`
        : '可选参数…'
      : placeholder

  function onComposerKeyDown(event: ReactKeyboardEvent<HTMLTextAreaElement>): void {
    if (slashMenuOpen) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setSlashMenuIndex((current) => (current + 1) % Math.max(slashMenuChoices.length, 1))
        return
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        setSlashMenuIndex((current) =>
          current <= 0 ? Math.max(slashMenuChoices.length - 1, 0) : current - 1
        )
        return
      }
      if (event.key === 'Tab' || (event.key === 'Enter' && !event.shiftKey)) {
        const pick = slashMenuChoices[slashMenuIndex]
        if (pick) {
          event.preventDefault()
          pickSlashCommand(pick)
          return
        }
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        onChange('')
        return
      }
    }
    if (slashDraft.kind === 'locked' && event.key === 'Backspace') {
      const el = textareaRef.current
      if (el && el.selectionStart === 0 && el.selectionEnd === 0) {
        event.preventDefault()
        onChange(`/${slashDraft.command.name}`)
        return
      }
    }
    if (slashDraft.kind === 'locked' && event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void submit()
      return
    }
    const intent = composerEnterIntent({
      key: event.key,
      shiftKey: event.shiftKey,
      altKey: event.altKey,
      ctrlKey: event.ctrlKey,
      isComposing: event.nativeEvent.isComposing,
      keyCode: event.keyCode,
    })
    if (!intent) return
    event.preventDefault()
    if (intent === 'steer' && onSteer) onSteer()
    else void submit()
  }

  const picker =
    profiles.length && onSelectModelProfile ? (
      <div ref={modelRef}>
        <ModelPicker
          profiles={profiles}
          activeId={activeProfileId}
          open={modelOpen}
          onOpenChange={setModelOpen}
          onSelect={onSelectModelProfile}
        />
      </div>
    ) : null

  const micButton = (
    <button
      type="button"
      className={`${iconBtn} touch-none ${
        listening
          ? 'bg-red-600 text-white shadow-[0_0_0_3px_rgba(239,68,68,0.18)] hover:bg-red-600 hover:text-white'
          : ''
      }`}
      title={listening ? t('chat.voice.micStopTitle') : t('chat.voice.micStartTitle')}
      aria-pressed={listening}
      onClick={onMicClick}
    >
      <Mic className="size-4" />
    </button>
  )

  const voiceUiToggle = !listening ? (
    <button
      type="button"
      className={`${iconBtn} size-7`}
      title={voiceUi === 'orb' ? t('chat.voice.uiBarTitle') : t('chat.voice.uiOrbTitle')}
      aria-label={voiceUi === 'orb' ? t('chat.voice.uiBarTitle') : t('chat.voice.uiOrbTitle')}
      onClick={() => setVoiceUi(voiceUi === 'orb' ? 'bar' : 'orb')}
    >
      {voiceUi === 'orb' ? <PanelTop className="size-3.5" /> : <CircleDot className="size-3.5" />}
    </button>
  ) : null

  const sendButton = (
    <SendOrStop
      showStop={showStop}
      canSubmit={canSubmit}
      sendTitle={sendTitle}
      onStop={onStop}
      onSubmit={() => void submit()}
    />
  )

  const cameraButton = onOpenCamera ? (
    <button
      type="button"
      className={iconBtn}
      disabled={menuOff}
      aria-label="拍照"
      title="摄像头拍照识别"
      onClick={() => {
        closeMenu()
        onOpenCamera()
      }}
    >
      <Camera className="size-4" />
    </button>
  ) : null

  const plusButton = canPlus ? (
    <div ref={plusRef} className="relative">
      <button
        type="button"
        className={`${iconBtn} ${attachOpen ? 'bg-muted text-foreground' : ''}`}
        disabled={menuOff}
        aria-label="添加"
        title="添加图片"
        onClick={() => {
          const next = !attachOpen
          setAttachOpen(next)
          if (next) onRefreshShots?.()
        }}
      >
        <Plus className="size-4" />
      </button>
      {attachOpen ? (
        <div className="absolute bottom-full left-0 z-20 mb-2 w-[248px] overflow-hidden rounded-2xl border border-border/80 bg-background p-2 shadow-lg">
          <div className="grid grid-cols-3 gap-1.5">
            {onAttachViewport ? (
              <ImageTile
                label="可见区域"
                onClick={() => {
                  closeMenu()
                  onAttachViewport()
                }}
              >
                <Monitor className="size-4" />
              </ImageTile>
            ) : null}
            {onLaunchScreenshotStudio ? (
              <ImageTile
                label="区域截图+编辑"
                name="截图工作室"
                onClick={() => {
                  closeMenu()
                  onLaunchScreenshotStudio()
                }}
              >
                <Crop className="size-4" />
              </ImageTile>
            ) : null}
            {onAttachFile ? (
              <ImageTile label="本地图片" onClick={() => fileRef.current?.click()}>
                <ImageIcon className="size-4" />
              </ImageTile>
            ) : null}
            {onOpenCamera ? (
              <ImageTile
                label="拍照"
                name="摄像头拍照"
                onClick={() => {
                  closeMenu()
                  onOpenCamera()
                }}
              >
                <Camera className="size-4" />
              </ImageTile>
            ) : null}
          </div>
          {recentShots?.length ? (
            <>
              <p className="mt-2 px-0.5 text-[11px] text-muted-foreground">工作区截图</p>
              <div className="mt-1.5 grid grid-cols-3 gap-1.5">
                {recentShots.map((shot) => (
                  <button
                    key={shot.path}
                    type="button"
                    title={shot.name}
                    className="overflow-hidden rounded-xl border border-border/80 bg-muted/30 text-left hover:border-border"
                    onClick={() => {
                      closeMenu()
                      onAttachShot?.(shot.path)
                    }}
                  >
                    {shot.thumb ? (
                      <img src={shot.thumb} alt="" className="aspect-square w-full object-cover" />
                    ) : (
                      <span className="flex aspect-square w-full items-center justify-center text-muted-foreground">
                        <ImageIcon className="size-4" />
                      </span>
                    )}
                    <span className="block truncate px-1 py-0.5 text-[10px] text-muted-foreground">
                      {shot.name.replace(/\.[^.]+$/, '')}
                    </span>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <p className="mt-2 px-0.5 text-[11px] text-muted-foreground">工作区还没有截图</p>
          )}
        </div>
      ) : null}
      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif,.png,.jpg,.jpeg,.webp,.gif"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          closeMenu()
          if (file) onAttachFile?.(file)
        }}
      />
    </div>
  ) : null

  return (
    <div className={`relative shrink-0 bg-background ${wide ? 'px-6 pb-3 pt-2' : 'px-3 pb-2 pt-1'}`}>
      {actingLabel && running ? (
        <p className="mb-1.5 truncate px-1 text-xs text-muted-foreground">
          {actingLabel.includes(' ') || actingLabel.includes('…')
            ? actingLabel
            : t('chat.actingFallback', { label: actingLabel })}
        </p>
      ) : null}
      {pickingElement ? (
        <p className="mb-1.5 px-1 text-xs text-muted-foreground">{t('chat.picking')}</p>
      ) : null}
      {listening && voiceUi === 'bar' ? (
        <VoiceCaptureBar
          interim={interim}
          transcript={value}
          speechLangConfig={speechLangConfig}
          onSpeechLangChange={onSpeechLangChange}
          onCancel={() => void cancelListen()}
          onFinish={() => void finishListen()}
        />
      ) : null}
      {listening && voiceUi === 'orb' ? (
        <VoiceCaptureOrb
          interim={interim}
          transcript={value}
          getAudioLevel={() => recorderRef.current?.getLevel() ?? 0}
          speechLangConfig={speechLangConfig}
          onSpeechLangChange={onSpeechLangChange}
          onCancel={() => void cancelListen()}
          onFinish={() => void finishListen()}
        />
      ) : null}

      <div className="overflow-visible rounded-[1.25rem] border border-border/80 bg-background shadow-[0_4px_24px_rgba(15,23,42,0.08)] focus-within:border-border focus-within:shadow-[0_8px_32px_rgba(15,23,42,0.1)]">
        {speechError ? (
          <p className="border-b border-border/50 px-3 py-2 text-xs text-red-600">
            {speechError}
            {speechError === t('chat.speech.notAllowed') ? (
              <>
                {' '}
                <button
                  type="button"
                  className="underline underline-offset-2"
                  onClick={() => void openExtensionSiteSettings()}
                >
                  {t('chat.speech.openSettings')}
                </button>
              </>
            ) : null}
          </p>
        ) : null}
        {hasPageChips ? (
          <div className="flex items-center gap-2 border-b border-border/50 px-3 py-2">
            <div className="flex min-w-0 flex-1 flex-wrap gap-1">
                {onPageAskModeChange ? (
                  <PageChip
                    label={t('chat.pageAsk')}
                    active={askMode}
                    disabled={menuOff}
                    onClick={() => onPageAskModeChange(!askMode)}
                  />
                ) : null}
                {onSummarize ? (
                  <PageChip label={t('chat.summarizePage')} disabled={menuOff} onClick={onSummarize} />
                ) : null}
                {onExplainPick ? (
                  <PageChip
                    label={pickingElement ? t('chat.explainPickActive') : t('chat.explainPick')}
                    active={Boolean(hasPickedElement || pickingElement)}
                    disabled={menuOff}
                    onClick={onExplainPick}
                  />
                ) : null}
                {onCopyArticle ? (
                  <PageChip label={t('chat.copyArticle')} disabled={menuOff} onClick={onCopyArticle} />
                ) : null}
                {onPick ? (
                  <PageChip
                    label={t('chat.pick')}
                    active={Boolean(pickingElement)}
                    disabled={Boolean(pickDisabled)}
                    onClick={onPick}
                  />
                ) : null}
            </div>
          </div>
        ) : null}

        {imageAttachment || voiceAttachment || shotAskHint ? (
          <div className="flex flex-wrap items-center gap-2 border-b border-border/50 px-3 py-2">
            {voiceAttachment ? (
              <VoiceCard
                src={voiceAttachment.dataUrl}
                path={voiceAttachment.path}
                compact
                onClear={onClearVoice}
              />
            ) : null}
            {imageAttachment ? (
              <div className="relative">
                <ZoomableImage
                  src={imageAttachment.dataUrl}
                  label={imageAttachment.label}
                  className="block overflow-hidden rounded-lg"
                  imgClassName="size-11 object-cover"
                />
                {onClearAttachment ? (
                  <button
                    type="button"
                    className="absolute -right-1.5 -top-1.5 inline-flex size-4 items-center justify-center rounded-full bg-foreground text-background"
                    onClick={onClearAttachment}
                    title="移除图片"
                    aria-label="移除图片"
                  >
                    <X className="size-2.5" />
                  </button>
                ) : null}
              </div>
            ) : null}
            {!imageAttachment && shotAskHint ? (
              <span className="text-[11px] text-muted-foreground">将查看工作区截图</span>
            ) : null}
          </div>
        ) : null}

        <div className="relative px-3 pt-2 pb-0" data-composer-input>
          {slashMenuOpen ? (
            <SlashCommandMenu
              query={slashMenuQuery}
              activeIndex={slashMenuIndex}
              registry={slashCommands}
              onPick={(command) => pickSlashCommand(command)}
              onHover={setSlashMenuIndex}
            />
          ) : null}
          <SlashInputHighlight text={slashHighlightText} mode={slashHighlightMode} />
          <textarea
            ref={textareaRef}
            className={cn(
              'relative z-[1] max-h-[28vh] w-full resize-none bg-transparent py-0.5 text-[14px] leading-5 outline-none placeholder:text-muted-foreground/60',
              slashHighlightMode && 'font-mono',
              slashHighlightMode ? 'text-transparent caret-foreground' : 'text-foreground'
            )}
            style={{ height: emptyHeight, ...inputLang.style }}
            rows={1}
            value={composerInputValue}
            readOnly={listening}
            onChange={(e) => handleComposerChange(e.target.value)}
            placeholder={
              listening
                ? t('chat.voice.listeningPlaceholder')
                : slashHighlightMode === 'locked'
                  ? slashArgsPlaceholder
                  : placeholder
            }
            title="Enter 发送 · Shift+Enter 换行 · / 命令 · Tab 补全"
            autoCapitalize={inputLang.autoCapitalize}
            autoCorrect={inputLang.autoCorrect}
            spellCheck={inputLang.spellCheck}
            onPaste={onComposerPaste}
            onKeyDown={onComposerKeyDown}
          />
        </div>

        <div className="flex items-center justify-between gap-2 px-2 pb-1.5 pt-0.5">
          <div className="flex min-w-0 items-center gap-0.5">{plusButton}</div>
          <div className="flex shrink-0 items-center gap-0.5">
            {picker}
            <ContextMeter
              variant="toolbar"
              breakdown={contextBreakdown ?? null}
              runTotal={runTotal}
              runTokenBudget={runTokenBudget}
              active={running}
            />
            {cameraButton}
            {voiceUiToggle}
            {micButton}
            {sendButton}
          </div>
        </div>
      </div>
    </div>
  )
}
