import { useFrame, useThree } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";
import { bodyById } from "../data/solarSystem";
import { useSpaceStore } from "../state/useSpaceStore";
import { bodyWorldRadius, orbitPosition } from "./orbit";

/** 靠近目标时减弱雾效，避免纹理发糊。 */
export function AdaptiveFog() {
  const fogRef = useRef<THREE.Fog>(null);
  const selectedTarget = useSpaceStore((state) => state.selectedTarget);
  const scaleMode = useSpaceStore((state) => state.scaleMode);
  const simulationDay = useSpaceStore((state) => state.simulationDay);
  const closeUpLevel = useSpaceStore((state) => state.closeUpLevel);
  const worldPos = useRef(new THREE.Vector3());
  const { camera } = useThree();

  useFrame(() => {
    if (!fogRef.current) {
      return;
    }

    let near = 40;
    let far = 180;

    if (selectedTarget.type === "body") {
      const body = bodyById.get(selectedTarget.id);
      if (body) {
        worldPos.current.copy(orbitPosition(body, simulationDay, scaleMode));
        const dist = camera.position.distanceTo(worldPos.current);
        const radius = bodyWorldRadius(body, scaleMode);

        if (dist < radius * 8) {
          near = 120;
          far = 420;
        }
        if (closeUpLevel === "surface" && dist < radius * 4) {
          near = 280;
          far = 900;
        }
      }
    }

    fogRef.current.near = THREE.MathUtils.lerp(fogRef.current.near, near, 0.08);
    fogRef.current.far = THREE.MathUtils.lerp(fogRef.current.far, far, 0.08);
  });

  return <fog ref={fogRef} attach="fog" args={["#020611", 40, 180]} />;
}
