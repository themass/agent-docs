import * as THREE from "three";
import type { BodyKind } from "../types";

/** 0 = 远距纯色，1 = 近距全纹理。阈值随天体半径缩放。 */
export function computeTextureDetail(
  cameraDistance: number,
  bodyRadius: number,
  kind: BodyKind,
  isSelected: boolean,
): number {
  const boost = isSelected ? 0.72 : 1;
  const near =
    bodyRadius *
    boost *
    (kind === "star" ? 4 : kind === "moon" ? 1.6 : kind === "dwarf-planet" ? 2.2 : 2.4);
  const far =
    bodyRadius *
    (kind === "star" ? 28 : kind === "moon" ? 9 : kind === "dwarf-planet" ? 12 : 18);

  return 1 - THREE.MathUtils.smoothstep(near, far, cameraDistance);
}

export function ringDetailOpacity(baseOpacity: number, detail: number): number {
  const gate = THREE.MathUtils.smoothstep(0.12, 0.42, detail);
  return baseOpacity * gate;
}

export function cloudDetailOpacity(baseOpacity: number, detail: number): number {
  return baseOpacity * THREE.MathUtils.smoothstep(0.05, 0.35, detail);
}

export function sphereSegments(detail: number): [number, number] {
  if (detail > 0.82) {
    return [128, 96];
  }
  if (detail > 0.45) {
    return [96, 72];
  }
  return [64, 48];
}
