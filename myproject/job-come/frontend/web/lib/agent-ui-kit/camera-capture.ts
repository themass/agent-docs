export type CameraFacing = "user" | "environment";

export function hasGetUserMedia(): boolean {
  return typeof navigator !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
}

export function mediaErrorMessage(err: unknown): string {
  const name =
    err && typeof err === "object" && "name" in err ? String((err as { name: string }).name) : "";
  if (name === "NotAllowedError" || name === "PermissionDeniedError") {
    return "没有摄像头权限，请在浏览器站点设置中允许摄像头。";
  }
  if (name === "NotFoundError" || name === "DevicesNotFoundError") return "没有找到摄像头";
  if (name === "NotReadableError" || name === "TrackStartError") return "摄像头被其他程序占用";
  if (name === "OverconstrainedError") return "这台摄像头不支持当前设置";
  if (err instanceof Error && err.message) return err.message;
  return "无法打开摄像头";
}

export function shouldMirrorPreview(facing: CameraFacing): boolean {
  return facing === "user";
}

export function stopMediaStream(stream: MediaStream | null | undefined): void {
  stream?.getTracks().forEach((track) => track.stop());
}

export async function openCameraStream(facing: CameraFacing): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: false,
    video: {
      facingMode: { ideal: facing },
      width: { ideal: 1280 },
      height: { ideal: 720 },
    },
  });
}

export async function videoInputCount(): Promise<number> {
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter((device) => device.kind === "videoinput").length;
}

export function captureVideoFrame(video: HTMLVideoElement, mirrored: boolean): string {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) throw new Error("画面还没准备好");
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("无法截取画面");
  if (mirrored) {
    ctx.translate(width, 0);
    ctx.scale(-1, 1);
  }
  ctx.drawImage(video, 0, 0, width, height);
  return canvas.toDataURL("image/jpeg", 0.92);
}
