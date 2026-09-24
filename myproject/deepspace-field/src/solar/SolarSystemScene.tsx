import { Html, Stars } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";
import * as THREE from "three";
import { bodies, bodyById } from "../data/solarSystem";
import { useSpaceStore } from "../state/useSpaceStore";
import type { Body } from "../types";
import { AdaptiveFog } from "./AdaptiveFog";
import { CameraController } from "./CameraController";
import { orbitPosition } from "./orbit";
import { PlanetMesh } from "./PlanetMesh";
import { PlanetSpinController } from "./PlanetSpinController";
import { bodyRadiusUnits, orbitRadiusUnits } from "./scale";

function OrbitRing({ body }: { body: Body }) {
  const scaleMode = useSpaceStore((state) => state.scaleMode);
  const focusIsolation = useSpaceStore((state) => state.focusIsolation);
  const radius = orbitRadiusUnits(body, scaleMode);
  if (body.id === "sun" || body.parentId) {
    return null;
  }

  if (focusIsolation) {
    return null;
  }

  return (
    <mesh rotation-x={Math.PI / 2}>
      <ringGeometry args={[radius - 0.006, radius + 0.006, 192]} />
      <meshBasicMaterial
        color="#31506c"
        transparent
        opacity={0.34}
        side={THREE.DoubleSide}
        depthWrite={false}
      />
    </mesh>
  );
}

function BodyGroup({ body }: { body: Body }) {
  const selectedTarget = useSpaceStore((state) => state.selectedTarget);
  const focusIsolation = useSpaceStore((state) => state.focusIsolation);
  const scaleMode = useSpaceStore((state) => state.scaleMode);
  const simulationDay = useSpaceStore((state) => state.simulationDay);
  const selectTarget = useSpaceStore((state) => state.selectTarget);

  let position = orbitPosition(body, simulationDay, scaleMode);
  let radius = bodyRadiusUnits(body, scaleMode);
  const isSelected = selectedTarget.type === "body" && selectedTarget.id === body.id;

  if (focusIsolation && selectedTarget.type === "body") {
    const selected = bodyById.get(selectedTarget.id);
    if (!selected) {
      return null;
    }

    const selectedPosition = orbitPosition(selected, simulationDay, scaleMode);
    const selectedRadius = bodyRadiusUnits(selected, scaleMode);

    if (body.id === selected.id) {
      position = selectedPosition;
      radius = selectedRadius;
    } else if (body.parentId === selected.id) {
      const children = bodies.filter((item) => item.parentId === selected.id);
      const index = Math.max(0, children.findIndex((item) => item.id === body.id));
      const angle = children.length === 1 ? Math.PI : (index / children.length) * Math.PI * 2;
      const distance = selectedRadius * 3.4 + radius * 2.8;
      position = selectedPosition
        .clone()
        .add(new THREE.Vector3(Math.cos(angle) * distance, selectedRadius * 0.12, Math.sin(angle) * distance));
      radius *= 0.68;
    } else if (selected.parentId === body.id) {
      const distance = selectedRadius * 6 + bodyRadiusUnits(body, scaleMode) * 0.8;
      position = selectedPosition.clone().add(new THREE.Vector3(distance, 0, -distance * 0.25));
      radius *= 0.32;
    } else {
      return null;
    }
  }

  return (
    <group position={position}>
      <PlanetMesh
        body={body}
        radius={radius}
        isSelected={isSelected}
        onSelect={() => selectTarget({ type: "body", id: body.id })}
      />
    </group>
  );
}

function SceneContents() {
  const scaleMode = useSpaceStore((state) => state.scaleMode);

  return (
    <>
      <color attach="background" args={["#020611"]} />
      <AdaptiveFog />
      <ambientLight intensity={0.24} />
      <pointLight position={[0, 0, 0]} intensity={12} color="#ffde93" distance={0} decay={1.35} />
      <Stars radius={180} depth={90} count={9000} factor={4} saturation={0.2} fade speed={0.18} />
      <group>
        {bodies.map((body) => (
          <OrbitRing key={`orbit-${body.id}-${scaleMode}`} body={body} />
        ))}
        {bodies.map((body) => (
          <BodyGroup key={`${body.id}-${scaleMode}`} body={body} />
        ))}
      </group>
      <CameraController />
      <PlanetSpinController />
    </>
  );
}

function SceneLoader() {
  return (
    <Html center>
      <div className="scene-loader">加载行星纹理…</div>
    </Html>
  );
}

export function SolarSystemScene() {
  return (
    <Canvas camera={{ position: [0, 11, 22], fov: 48, near: 0.01, far: 2000 }} dpr={[1, 2]}>
      <Suspense fallback={<SceneLoader />}>
        <SceneContents />
      </Suspense>
    </Canvas>
  );
}
