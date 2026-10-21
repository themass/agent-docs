/**
 * Crop geometry and canvas encoding for the headshot cropper.
 *
 * Kept as pure functions separate from the dialog for two reasons: the maths is the
 * part that is easy to get subtly wrong (an off-by-one in the clamp shows up as a
 * sliver of background along one edge of a printed resume), and it is the only part
 * worth exercising without a browser.
 *
 * No crop library is used. `react-easy-crop` is the obvious candidate, but the whole
 * frontend currently carries no UI dependency beyond assistant-ui, and what we need
 * here — pan, zoom, fixed aspect, export — is the small subset below. The crop runs
 * in the browser rather than on the server because framing a face is a direct
 * manipulation gesture: the user has to see the result while dragging.
 */

/** Crop box aspect, width / height. 0.8 is the 25mm × 31.25mm print box in `_theme.css.html`. */
export const HEADSHOT_ASPECT = 0.8;

/**
 * Exported pixel size. 1024 tall is exactly `MAX_EDGE_PX` on the server, so the
 * upload needs no further downscale and what the user framed is what gets stored.
 */
export const HEADSHOT_OUTPUT_HEIGHT = 1024;
export const HEADSHOT_OUTPUT_WIDTH = Math.round(HEADSHOT_OUTPUT_HEIGHT * HEADSHOT_ASPECT);

export const MIN_ZOOM = 1;
export const MAX_ZOOM = 4;

/** Pan offset of the image centre from the viewport centre, in viewport pixels, plus zoom. */
export type CropTransform = { x: number; y: number; zoom: number };

export type Size = { width: number; height: number };

export const IDENTITY_TRANSFORM: CropTransform = { x: 0, y: 0, zoom: 1 };

export function clampZoom(zoom: number): number {
  if (!Number.isFinite(zoom)) return MIN_ZOOM;
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom));
}

/**
 * Scale at which the image exactly covers the viewport — the floor, not a choice.
 * Anything smaller would let background show through inside the crop box, which
 * would then be baked into the resume as a white band.
 */
export function coverScale(natural: Size, viewport: Size): number {
  if (!natural.width || !natural.height) return 1;
  return Math.max(viewport.width / natural.width, viewport.height / natural.height);
}

/**
 * Pull the pan back inside the legal range for the current zoom.
 *
 * Applied on every drag frame *and* after a zoom change: zooming out shrinks the
 * slack, so a pan that was legal at 3× can leave the crop box hanging off the image
 * at 1.2×. Without the second call, zooming out after panning to a corner is exactly
 * how the empty-edge bug appears.
 */
export function clampTransform(
  transform: CropTransform,
  natural: Size,
  viewport: Size,
): CropTransform {
  const zoom = clampZoom(transform.zoom);
  const scale = coverScale(natural, viewport) * zoom;
  const displayed = { width: natural.width * scale, height: natural.height * scale };
  // Half the overhang on each axis. `max(0, …)` guards the degenerate case where
  // rounding leaves the displayed size a hair under the viewport.
  const slackX = Math.max(0, (displayed.width - viewport.width) / 2);
  const slackY = Math.max(0, (displayed.height - viewport.height) / 2);
  return {
    zoom,
    x: Math.min(slackX, Math.max(-slackX, transform.x)),
    y: Math.min(slackY, Math.max(-slackY, transform.y)),
  };
}

/**
 * Keep the point under the cursor fixed while zooming, the way every map does.
 * Zooming around the viewport centre instead is the single most disorienting thing
 * a cropper can do: the face the user just centred slides out from under them.
 *
 * `focus` is in viewport pixels relative to the viewport centre.
 */
export function zoomAround(
  transform: CropTransform,
  nextZoom: number,
  focus: { x: number; y: number },
  natural: Size,
  viewport: Size,
): CropTransform {
  const zoom = clampZoom(nextZoom);
  const ratio = zoom / clampZoom(transform.zoom);
  return clampTransform(
    {
      zoom,
      x: focus.x + (transform.x - focus.x) * ratio,
      y: focus.y + (transform.y - focus.y) * ratio,
    },
    natural,
    viewport,
  );
}

/** The source rectangle, in the image's own pixels, that the crop box currently covers. */
export function sourceRect(
  transform: CropTransform,
  natural: Size,
  viewport: Size,
): { x: number; y: number; width: number; height: number } {
  const scale = coverScale(natural, viewport) * clampZoom(transform.zoom);
  const displayed = { width: natural.width * scale, height: natural.height * scale };
  const left = displayed.width / 2 - transform.x - viewport.width / 2;
  const top = displayed.height / 2 - transform.y - viewport.height / 2;
  return {
    x: left / scale,
    y: top / scale,
    width: viewport.width / scale,
    height: viewport.height / scale,
  };
}

/**
 * Render the crop to a JPEG blob.
 *
 * JPEG, not PNG: the server re-encodes to JPEG anyway, and a PNG of a photograph is
 * several times the bytes for no visible gain. White backdrop first so a transparent
 * source (a PNG cut-out) lands on white rather than black, matching the printed page.
 */
export async function encodeCrop(
  image: HTMLImageElement | ImageBitmap,
  rect: { x: number; y: number; width: number; height: number },
  quality = 0.92,
): Promise<Blob> {
  const canvas = document.createElement("canvas");
  canvas.width = HEADSHOT_OUTPUT_WIDTH;
  canvas.height = HEADSHOT_OUTPUT_HEIGHT;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("当前浏览器无法处理图片裁剪");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(
    image as CanvasImageSource,
    rect.x,
    rect.y,
    rect.width,
    rect.height,
    0,
    0,
    canvas.width,
    canvas.height,
  );
  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", quality),
  );
  if (!blob) throw new Error("图片导出失败，请换一张试试");
  return blob;
}

/**
 * A decoded source image plus ownership of the blob URL backing it.
 *
 * The URL has to outlive `onload`. The dialog renders its own `<img src={image.src}>`
 * for the pan/zoom preview, so revoking as soon as the off-DOM `Image` finished
 * decoding left that preview pointing at a dead URL — a grey box — even though the
 * already-decoded `Image` still worked fine for the canvas export. Handing the
 * revoke back to the caller keeps the lifetime tied to the component that displays
 * it instead of to the decode.
 */
export type LoadedImage = {
  image: HTMLImageElement;
  /** Idempotent; call on unmount or when the picked file changes. */
  revoke: () => void;
};

/** Load a picked file, rejecting anything the backend would refuse anyway. */
export function loadImageFile(file: File): Promise<LoadedImage> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    let revoked = false;
    const revoke = () => {
      if (revoked) return;
      revoked = true;
      URL.revokeObjectURL(url);
    };
    const image = new Image();
    // Browsers apply EXIF orientation when decoding, and `drawImage` inherits that,
    // so the exported crop is upright without any rotation handling here.
    image.onload = () => {
      if (!image.naturalWidth || !image.naturalHeight) {
        revoke();
        reject(new Error("这个文件不是能识别的图片，请换一张（JPG / PNG / WebP）"));
        return;
      }
      resolve({ image, revoke });
    };
    image.onerror = () => {
      revoke();
      reject(new Error("这个文件不是能识别的图片，请换一张（JPG / PNG / WebP）"));
    };
    image.src = url;
  });
}

/** Mirrors the server's accept list; checked here so the rejection is instant. */
export const ACCEPTED_PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export const PHOTO_FILE_ACCEPT = ".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp";

/** Generous: this is the *source* file, pre-crop, straight off a phone camera. */
export const MAX_SOURCE_PHOTO_BYTES = 20 * 1024 * 1024;

export function photoFileError(file: File): string | null {
  if (!ACCEPTED_PHOTO_TYPES.includes(file.type as (typeof ACCEPTED_PHOTO_TYPES)[number])) {
    return "只支持 JPG、PNG 和 WebP 格式的照片。";
  }
  if (file.size > MAX_SOURCE_PHOTO_BYTES) {
    return "照片太大了，请先压缩后再上传（上限 20MB）。";
  }
  return null;
}

export type CropRect = { x: number; y: number; width: number; height: number };
export type CropCorner = "nw" | "ne" | "sw" | "se";

export function moveCrop(rect: CropRect, dx: number, dy: number, bounds: Size): CropRect {
  return {
    ...rect,
    x: Math.max(0, Math.min(bounds.width - rect.width, rect.x + dx)),
    y: Math.max(0, Math.min(bounds.height - rect.height, rect.y + dy)),
  };
}

/** Opposite corner stays fixed. Project pointer movement onto the 4:5 diagonal. */
export function resizeCrop(rect: CropRect, corner: CropCorner, dx: number, dy: number, bounds: Size): CropRect {
  const sx = corner.endsWith("e") ? 1 : -1;
  const sy = corner.startsWith("s") ? 1 : -1;
  const anchorX = sx === 1 ? rect.x : rect.x + rect.width;
  const anchorY = sy === 1 ? rect.y : rect.y + rect.height;
  const limit = Math.min((sx === 1 ? bounds.width - anchorX : anchorX) / HEADSHOT_ASPECT,
    sy === 1 ? bounds.height - anchorY : anchorY);
  const delta = (sx * dx * HEADSHOT_ASPECT + sy * dy) / (1 + HEADSHOT_ASPECT ** 2);
  const height = Math.max(Math.min(48, limit), Math.min(limit, rect.height + delta));
  const width = height * HEADSHOT_ASPECT;
  return { x: sx === 1 ? anchorX : anchorX - width, y: sy === 1 ? anchorY : anchorY - height, width, height };
}

/** Preview and export share the same image scale, pan and selection rectangle. */
export function selectionSourceRect(transform: CropTransform, natural: Size, viewport: Size, crop: CropRect): CropRect {
  const full = sourceRect(transform, natural, viewport);
  const scale = coverScale(natural, viewport) * clampZoom(transform.zoom);
  return {
    x: full.x + crop.x / scale,
    y: full.y + crop.y / scale,
    width: crop.width / scale,
    height: crop.height / scale,
  };
}
