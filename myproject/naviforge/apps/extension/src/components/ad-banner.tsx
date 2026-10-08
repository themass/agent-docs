import { adEmbedUrl, adsEnabled, type AdSurface } from '../lib/ads-config'
import { cn } from '../lib/cn'

/** Extension-page ad slot via iframe (AdSense on your HTTPS/HTTP host, not in MV3 CSP). */
export function AdBanner({
  surface,
  className,
  size = 'default',
}: {
  surface: AdSurface
  className?: string
  /** compact = shorter slot for in-feed agent list */
  size?: 'default' | 'compact'
}) {
  const src = adEmbedUrl(surface)
  if (!src || !adsEnabled(surface)) return null

  return (
    <div
      className={cn('ad-banner', size === 'compact' && 'ad-banner-compact', className)}
      aria-label="Advertisement"
    >
      <iframe
        title="Advertisement"
        src={src}
        className={cn('ad-banner-frame', size === 'compact' && 'ad-banner-frame-compact')}
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
      />
    </div>
  )
}
