import * as THREE from "three";
import { bodyById } from "../data/solarSystem";
import type { Body, CloseUpLevel, ScaleMode } from "../types";
import { bodyRadiusUnits, orbitRadiusUnits, orbitalAngle } from "./scale";

export function orbitPosition(
  body: Body,
  simulationDay: number,
  scaleMode: ScaleMode,
): THREE.Vector3 {
  if (!body.parentId) {
    const r = orbitRadiusUnits(body, scaleMode);
    const a = orbitalAngle(body, simulationDay);
    return new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r);
  }

  const parent = bodyById.get(body.parentId);
  if (!parent) {
    return new THREE.Vector3();
  }

  const parentPosition = orbitPosition(parent, simulationDay, scaleMode);
  const r = orbitRadiusUnits(body, scaleMode);
  const a = orbitalAngle(body, simulationDay);
  return parentPosition
    .clone()
    .add(new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r));
}

export function cameraOffsetForBody(
  body: Body,
  radius: number,
  simulationDay: number,
  scaleMode: ScaleMode,
  closeUpLevel: CloseUpLevel,
): THREE.Vector3 {
  const closeFactor = closeUpLevel === "surface" ? 1.15 : 1;

  if (body.parentId) {
    const parent = bodyById.get(body.parentId);
    if (parent) {
      const bodyPos = orbitPosition(body, simulationDay, scaleMode);
      const parentPos = orbitPosition(parent, simulationDay, scaleMode);
      const parentRadius = bodyRadiusUnits(parent, scaleMode);
      const away = bodyPos.clone().sub(parentPos);
      if (away.lengthSq() < 1e-8) {
        away.set(1, 0, 0);
      } else {
        away.normalize();
      }
      const standoff = radius * (closeUpLevel === "surface" ? 3.2 : 5.5) + parentRadius * 0.08;
      return away.multiplyScalar(standoff).add(new THREE.Vector3(0, radius * 1.8, 0));
    }
  }

  if (body.kind === "star") {
    return new THREE.Vector3(
      radius * 5.5 * closeFactor,
      radius * 1.8 * closeFactor,
      radius * 5.5 * closeFactor,
    );
  }
  if (body.id === "saturn" || body.id === "uranus") {
    return new THREE.Vector3(
      radius * 4.5 * closeFactor,
      radius * 1.2 * closeFactor,
      radius * 4.5 * closeFactor,
    );
  }

  const dist = closeUpLevel === "surface" ? 2.1 : 3.2;
  return new THREE.Vector3(
    radius * dist * closeFactor,
    radius * 1.2 * closeFactor,
    radius * dist * 1.1 * closeFactor,
  );
}

export function bodyWorldRadius(body: Body, scaleMode: ScaleMode): number {
  return bodyRadiusUnits(body, scaleMode);
}

export function computeBodyVisibility(
  body: Body,
  selectedId: string | null,
  focusIsolation: boolean,
): number {
  if (!focusIsolation || !selectedId) {
    return 1;
  }

  const selected = bodyById.get(selectedId);
  if (!selected || selected.id === body.id) {
    return 1;
  }

  if (selected.parentId === body.id) {
    return 0.05;
  }

  if (body.parentId === selected.id) {
    return 0.86;
  }

  if (
    selected.parentId &&
    body.parentId === selected.parentId &&
    body.kind === "moon"
  ) {
    return 0.12;
  }

  return 0.28;
}
