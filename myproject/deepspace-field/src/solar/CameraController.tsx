import { OrbitControls as DreiOrbitControls } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { bodyById } from "../data/solarSystem";
import { useSpaceStore } from "../state/useSpaceStore";
import { bodyWorldRadius, cameraOffsetForBody, orbitPosition } from "./orbit";

export function CameraController() {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const selectedTarget = useSpaceStore((state) => state.selectedTarget);
  const flightState = useSpaceStore((state) => state.flightState);
  const setFlightState = useSpaceStore((state) => state.setFlightState);
  const focusIsolation = useSpaceStore((state) => state.focusIsolation);
  const setFocusIsolation = useSpaceStore((state) => state.setFocusIsolation);
  const viewMode = useSpaceStore((state) => state.viewMode);
  const closeUpLevel = useSpaceStore((state) => state.closeUpLevel);
  const closeUpNonce = useSpaceStore((state) => state.closeUpNonce);
  const scaleMode = useSpaceStore((state) => state.scaleMode);
  const simulationDay = useSpaceStore((state) => state.simulationDay);
  const flyRequested = useRef(true);
  const { camera } = useThree();

  useEffect(() => {
    flyRequested.current = true;
    setFlightState("traveling");
  }, [selectedTarget, closeUpNonce, setFlightState]);

  useFrame(() => {
    const controls = controlsRef.current;
    if (!controls || selectedTarget.type !== "body") {
      return;
    }

    const body = bodyById.get(selectedTarget.id);
    if (!body) {
      return;
    }

    const targetPos = orbitPosition(body, simulationDay, scaleMode);
    const radius = bodyWorldRadius(body, scaleMode);
    const offset = cameraOffsetForBody(
      body,
      radius,
      simulationDay,
      scaleMode,
      closeUpLevel,
    );
    const desiredCam = targetPos.clone().add(offset);

    if (flyRequested.current || flightState === "traveling") {
      const targetLerp = THREE.MathUtils.clamp(
        controls.target.distanceTo(targetPos) * 0.1,
        0.1,
        0.28,
      );
      const cameraLerp = THREE.MathUtils.clamp(
        camera.position.distanceTo(desiredCam) * 0.015,
        0.08,
        0.24,
      );

      controls.target.lerp(targetPos, targetLerp);
      camera.position.lerp(desiredCam, cameraLerp);

      const arrived =
        camera.position.distanceTo(desiredCam) < radius * 0.35 &&
        controls.target.distanceTo(targetPos) < radius * 0.25;

      if (arrived) {
        flyRequested.current = false;
        setFlightState("orbiting");
      }
    } else {
      controls.target.copy(targetPos);
    }

    if (
      focusIsolation &&
      flightState !== "traveling" &&
      camera.position.distanceTo(targetPos) > radius * 18
    ) {
      setFocusIsolation(false);
    }

    const minDist =
      closeUpLevel === "surface"
        ? Math.max(radius * 1.01, 0.08)
        : Math.max(radius * 1.08, 0.12);
    controls.minDistance = minDist;
    controls.maxDistance = Math.max(radius * 60, 45);
    controls.update();
  });

  const inspectMode = viewMode === "inspect";

  return (
    <DreiOrbitControls
      ref={controlsRef}
      enableDamping
      dampingFactor={0.06}
      enableRotate={!inspectMode}
      enablePan={!inspectMode}
      rotateSpeed={0.75}
      zoomSpeed={1.25}
      panSpeed={0.55}
      makeDefault
    />
  );
}
