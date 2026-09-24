import { Html, useTexture } from "@react-three/drei";
import { useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { useLayoutEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import * as THREE from "three";
import type { Body } from "../types";
import { useSpaceStore } from "../state/useSpaceStore";
import {
  cloudDetailOpacity,
  computeTextureDetail,
  ringDetailOpacity,
  sphereSegments,
} from "./detailBlend";
import { computeBodyVisibility } from "./orbit";
import { PLANET_TEXTURES } from "./planetTextures";

type PlanetMeshProps = {
  body: Body;
  radius: number;
  isSelected: boolean;
  onSelect: () => void;
};

function applyTextureQuality(texture: THREE.Texture, anisotropy: number) {
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = anisotropy;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.needsUpdate = true;
}

function RingDisc({
  body,
  radius,
  ringTexture,
  detailRef,
  visibilityRef,
}: {
  body: Body;
  radius: number;
  ringTexture: THREE.Texture;
  detailRef: MutableRefObject<number>;
  visibilityRef: MutableRefObject<number>;
}) {
  const materialRef = useRef<THREE.MeshStandardMaterial>(null);
  const isSaturn = body.id === "saturn";
  const inner = isSaturn ? radius * 1.35 : radius * 1.22;
  const outer = isSaturn ? radius * 2.35 : radius * 1.55;
  const baseOpacity = isSaturn ? 0.92 : 0.28;

  useFrame(() => {
    if (!materialRef.current) {
      return;
    }
    materialRef.current.opacity =
      ringDetailOpacity(baseOpacity, detailRef.current) * visibilityRef.current;
  });

  return (
    <mesh renderOrder={3} rotation-x={Math.PI / 2.55}>
      <ringGeometry args={[inner, outer, 128]} />
      <meshStandardMaterial
        ref={materialRef}
        map={ringTexture}
        transparent
        opacity={0}
        side={THREE.DoubleSide}
        depthWrite={false}
        roughness={0.85}
        metalness={0.05}
      />
    </mesh>
  );
}

function TexturedPlanet({ body, radius, isSelected, onSelect }: PlanetMeshProps) {
  const spinGroupRef = useRef<THREE.Group>(null);
  const baseMeshRef = useRef<THREE.Mesh>(null);
  const detailMeshRef = useRef<THREE.Mesh>(null);
  const cloudRef = useRef<THREE.Mesh>(null);
  const baseMatRef = useRef<THREE.MeshStandardMaterial>(null);
  const detailMatRef = useRef<THREE.MeshBasicMaterial>(null);
  const sunDetailMatRef = useRef<THREE.MeshBasicMaterial>(null);
  const cloudMatRef = useRef<THREE.MeshStandardMaterial>(null);
  const detailRef = useRef(0);
  const visibilityRef = useRef(1);
  const worldPos = useMemo(() => new THREE.Vector3(), []);
  const { gl } = useThree();

  const viewMode = useSpaceStore((state) => state.viewMode);
  const closeUpLevel = useSpaceStore((state) => state.closeUpLevel);
  const planetSpin = useSpaceStore((state) => state.planetSpin);
  const focusIsolation = useSpaceStore((state) => state.focusIsolation);
  const selectedTarget = useSpaceStore((state) => state.selectedTarget);
  const requestCloseUp = useSpaceStore((state) => state.requestCloseUp);

  const selectedId =
    selectedTarget.type === "body" ? selectedTarget.id : null;
  const [segments, setSegments] = useState<[number, number]>([64, 48]);

  const texSet = PLANET_TEXTURES[body.id]!;
  const urls = useMemo(() => {
    const list = [texSet.map];
    if (texSet.clouds) {
      list.push(texSet.clouds);
    }
    if (texSet.ring) {
      list.push(texSet.ring);
    }
    return list;
  }, [texSet]);

  const loaded = useTexture(urls);
  const map = loaded[0];
  const clouds = texSet.clouds ? loaded[1] : undefined;
  const ringMap = texSet.ring ? loaded[texSet.clouds ? 2 : 1] : undefined;

  const maxAnisotropy = gl.capabilities.getMaxAnisotropy();

  useLayoutEffect(() => {
    applyTextureQuality(map, maxAnisotropy);
    if (clouds) {
      applyTextureQuality(clouds, maxAnisotropy);
    }
    if (ringMap) {
      applyTextureQuality(ringMap, maxAnisotropy);
    }
  }, [clouds, map, maxAnisotropy, ringMap]);

  const spinRate = body.kind === "star" ? 0.04 : 0.1;
  const tint = texSet.tint ? new THREE.Color(texSet.tint) : undefined;
  const autoSpin = !isSelected || viewMode !== "inspect";

  useFrame(({ camera }, delta) => {
    if (spinGroupRef.current && isSelected) {
      spinGroupRef.current.rotation.set(planetSpin.pitch, planetSpin.yaw, 0);
    }

    if (autoSpin) {
      if (baseMeshRef.current) {
        baseMeshRef.current.rotation.y += delta * spinRate;
      }
      if (detailMeshRef.current) {
        detailMeshRef.current.rotation.y += delta * spinRate;
      }
      if (cloudRef.current) {
        cloudRef.current.rotation.y += delta * spinRate * 1.06;
      }
    }

    if (!spinGroupRef.current) {
      return;
    }

    spinGroupRef.current.getWorldPosition(worldPos);
    const distance = camera.position.distanceTo(worldPos);
    const rawDetail = computeTextureDetail(distance, radius, body.kind, isSelected);
    const detail =
      isSelected && focusIsolation
        ? Math.max(rawDetail, closeUpLevel === "surface" ? 1 : 0.94)
        : rawDetail;
    detailRef.current = detail;

    const visibility = computeBodyVisibility(body, selectedId, focusIsolation);
    visibilityRef.current = visibility;

    const nextSegments = sphereSegments(detail);
    if (nextSegments[0] !== segments[0]) {
      setSegments(nextSegments);
    }

    const isGhosted = visibility < 0.995;
    const textureOpacity = isGhosted ? detail * visibility : detail;

    if (texSet.emissive && sunDetailMatRef.current) {
      sunDetailMatRef.current.opacity = textureOpacity;
      sunDetailMatRef.current.transparent = textureOpacity < 0.995;
      sunDetailMatRef.current.depthWrite = textureOpacity >= 0.995 && !isGhosted;
    } else if (detailMatRef.current) {
      detailMatRef.current.opacity = textureOpacity;
      detailMatRef.current.transparent = textureOpacity < 0.995;
      detailMatRef.current.depthWrite = textureOpacity >= 0.995 && !isGhosted;
    }

    if (baseMatRef.current) {
      baseMatRef.current.opacity = visibility;
      baseMatRef.current.transparent = isGhosted;
      baseMatRef.current.depthWrite = !isGhosted;
      baseMatRef.current.emissiveIntensity =
        body.kind === "star"
          ? (1.4 + detail * 0.6) * visibility
          : isSelected
            ? (0.08 + detail * 0.1) * visibility
            : 0;
    }

    if (cloudMatRef.current) {
      const cloudBaseOpacity =
        isSelected && focusIsolation
          ? closeUpLevel === "surface"
            ? 0
            : 0.025
          : 0.42;
      cloudMatRef.current.opacity =
        cloudDetailOpacity(cloudBaseOpacity, detail) * visibility;
    }
  });

  const handleDoubleClick = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation();
    onSelect();
    requestCloseUp();
  };

  return (
    <group ref={spinGroupRef}>
      <mesh
        renderOrder={0}
        ref={baseMeshRef}
        onClick={(event) => {
          event.stopPropagation();
          if (isSelected && viewMode === "inspect") {
            return;
          }
          onSelect();
        }}
        onDoubleClick={handleDoubleClick}
      >
        <sphereGeometry args={[radius, segments[0], segments[1]]} />
        <meshStandardMaterial
          ref={baseMatRef}
          color={body.color}
          emissive={body.kind === "star" ? body.accentColor : isSelected ? body.accentColor : "#000000"}
          emissiveIntensity={body.kind === "star" ? 1.6 : isSelected ? 0.08 : 0}
          roughness={0.82}
          metalness={body.kind === "star" ? 0 : 0.03}
          opacity={1}
        />
      </mesh>

      <mesh
        renderOrder={1}
        ref={detailMeshRef}
        onClick={(event) => {
          event.stopPropagation();
          if (isSelected && viewMode === "inspect") {
            return;
          }
          onSelect();
        }}
        onDoubleClick={handleDoubleClick}
      >
        <sphereGeometry args={[radius * 1.001, segments[0], segments[1]]} />
        {texSet.emissive ? (
          <meshBasicMaterial
            ref={sunDetailMatRef}
            map={map}
            transparent
            opacity={0}
            toneMapped={false}
            depthWrite={false}
          />
        ) : (
          <meshBasicMaterial
            ref={detailMatRef}
            map={map}
            color={tint ?? "#ffffff"}
            transparent
            opacity={0}
            depthWrite={false}
            toneMapped={false}
          />
        )}
      </mesh>

      {clouds && (
        <mesh ref={cloudRef} renderOrder={2}>
          <sphereGeometry args={[radius * 1.015, segments[0], segments[1]]} />
          <meshStandardMaterial
            ref={cloudMatRef}
            map={clouds}
            transparent
            opacity={0}
            depthWrite={false}
            roughness={1}
            metalness={0}
          />
        </mesh>
      )}

      {ringMap && (
        <RingDisc
          body={body}
          radius={radius}
          ringTexture={ringMap}
          detailRef={detailRef}
          visibilityRef={visibilityRef}
        />
      )}

      {isSelected && !focusIsolation && closeUpLevel !== "surface" && (
        <mesh renderOrder={4}>
          <sphereGeometry args={[radius * 1.14, 48, 24]} />
          <meshBasicMaterial
            color={body.accentColor}
            transparent
            opacity={0.08}
            depthWrite={false}
          />
        </mesh>
      )}

      <Html center distanceFactor={9} position={[0, radius + 0.24, 0]}>
        <button
          className={`space-label ${isSelected ? "is-selected" : ""}`}
          onClick={onSelect}
          onDoubleClick={(event) => {
            event.stopPropagation();
            onSelect();
            requestCloseUp();
          }}
        >
          {body.name}
        </button>
      </Html>
    </group>
  );
}

function FallbackPlanet({ body, radius, isSelected, onSelect }: PlanetMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const requestCloseUp = useSpaceStore((state) => state.requestCloseUp);

  useFrame((_, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * (body.kind === "star" ? 0.08 : 0.18);
    }
  });

  return (
    <group>
      <mesh
        ref={meshRef}
        onClick={onSelect}
        onDoubleClick={(event) => {
          event.stopPropagation();
          onSelect();
          requestCloseUp();
        }}
      >
        <sphereGeometry args={[radius, 48, 32]} />
        <meshStandardMaterial
          color={body.color}
          emissive={body.kind === "star" ? body.accentColor : "#000000"}
          emissiveIntensity={body.kind === "star" ? 1.8 : isSelected ? 0.16 : 0}
          roughness={0.72}
          metalness={0.02}
        />
      </mesh>
      <Html center distanceFactor={9} position={[0, radius + 0.22, 0]}>
        <button className={`space-label ${isSelected ? "is-selected" : ""}`} onClick={onSelect}>
          {body.name}
        </button>
      </Html>
    </group>
  );
}

export function PlanetMesh(props: PlanetMeshProps) {
  if (PLANET_TEXTURES[props.body.id]) {
    return <TexturedPlanet {...props} />;
  }
  return <FallbackPlanet {...props} />;
}
