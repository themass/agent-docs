import { useEffect, useState } from 'react'
import { X } from 'lucide-react'

import { cn } from '../../lib/cn'

export function ImageLightbox({
  src,
  label,
  open,
  onClose,
}: {
  src: string
  label?: string
  open: boolean
  onClose: () => void
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/85 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={label ?? '查看大图'}
      onClick={onClose}
    >
      <button
        type="button"
        className="absolute right-4 top-4 inline-flex size-9 items-center justify-center rounded-full bg-black/50 text-white hover:bg-black/70"
        onClick={onClose}
        aria-label="关闭"
      >
        <X className="size-5" />
      </button>
      <img
        src={src}
        alt={label ?? ''}
        className="max-h-[92vh] max-w-[92vw] object-contain shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      />
      {label ? (
        <p className="pointer-events-none absolute bottom-4 left-1/2 max-w-[90vw] -translate-x-1/2 truncate rounded-full bg-black/50 px-3 py-1 text-xs text-white/90">
          {label}
        </p>
      ) : null}
    </div>
  )
}

export function ZoomableImage({
  src,
  alt = '',
  label,
  className,
  imgClassName,
}: {
  src: string
  alt?: string
  label?: string
  className?: string
  imgClassName?: string
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        className={cn('cursor-zoom-in border-0 bg-transparent p-0', className)}
        onClick={() => setOpen(true)}
        aria-label="查看大图"
        title="点击查看大图"
      >
        <img src={src} alt={alt} className={cn('pointer-events-none', imgClassName)} />
      </button>
      <ImageLightbox
        src={src}
        label={label ?? alt}
        open={open}
        onClose={() => setOpen(false)}
      />
    </>
  )
}
