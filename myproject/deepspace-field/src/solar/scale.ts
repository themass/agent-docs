import type { Body, ScaleMode } from "../types";

export const AU_IN_KM = 149_597_870.7;

export function orbitRadiusUnits(body: Body, mode: ScaleMode): number {
  if (body.parentId) {
    const moonBase = body.orbitRadiusAu * 120;
    return Math.max(body.kind === "moon" ? 0.62 : 0.32, moonBase);
  }

  if (mode === "real") {
    return Math.max(0.1, body.orbitRadiusAu * 2.2);
  }

  if (mode === "cinematic") {
    return Math.sqrt(body.orbitRadiusAu) * 5.4;
  }

  return Math.sqrt(body.orbitRadiusAu) * 4.2;
}

export function bodyRadiusUnits(body: Body, mode: ScaleMode): number {
  if (body.kind === "star") {
    return mode === "real" ? 0.75 : 1.55;
  }

  const visualBoost = mode === "real" ? 1 : mode === "cinematic" ? 1.45 : 1.75;
  const base = Math.cbrt(body.radiusKm / 6_371) * 0.28 * visualBoost;
  if (body.kind === "moon") {
    return Math.max(0.09, base * 0.78);
  }
  if (body.kind === "dwarf-planet") {
    return Math.max(0.18, base * 1.35);
  }
  return Math.max(0.26, base);
}

export function orbitalAngle(body: Body, simulationDay: number): number {
  if (!body.orbitPeriodDays) {
    return 0;
  }
  const direction = body.orbitPeriodDays < 0 ? -1 : 1;
  const period = Math.abs(body.orbitPeriodDays);
  return direction * ((simulationDay / period) * Math.PI * 2);
}

export function formatDistanceAu(au: number): string {
  if (au < 0.01) {
    return `${Math.round(au * AU_IN_KM).toLocaleString()} km`;
  }
  return `${au.toFixed(3)} AU`;
}
