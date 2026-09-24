import { adEmbedUrl, adsEnabled, type AdSurface } from '../lib/ads-config'
import { cn } from '../lib/cn'

/** Extension-page ad slot via iframe (AdSense on your HTTPS/HTTP host, not in MV3 CSP). */
export function AdBanner({
  surface,
  className,
}: {
  surface: AdSurface
  className?: string
}) {
  const src = adEmbedUrl(surface)
  if (!src || !adsEnabled(surface)) return null

  return (
    <div className={cn('ad-banner', className)} aria-label="Advertisement">
      <iframe
        title="Advertisement"
        src={src}
        className="ad-banner-frame"
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
      />
    </div>
  )
}
