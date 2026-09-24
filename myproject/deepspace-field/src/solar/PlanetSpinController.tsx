import { useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import { useSpaceStore } from "../state/useSpaceStore";

/** 检视模式：拖拽只旋转当前选中的天体，不带动整个空间。 */
export function PlanetSpinController() {
  const viewMode = useSpaceStore((state) => state.viewMode);
  const flightState = useSpaceStore((state) => state.flightState);
  const addPlanetSpin = useSpaceStore((state) => state.addPlanetSpin);
  const suppressSelectionFor = useSpaceStore((state) => state.suppressSelectionFor);
  const { gl } = useThree();
  const dragging = useRef(false);
  const moved = useRef(false);
  const last = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = gl.domElement;
    const active = viewMode === "inspect" && flightState === "orbiting";

    const onPointerDown = (event: PointerEvent) => {
      if (!active || event.button !== 0) {
        return;
      }
      dragging.current = true;
      moved.current = false;
      last.current = { x: event.clientX, y: event.clientY };
      canvas.setPointerCapture(event.pointerId);
    };

    const onPointerMove = (event: PointerEvent) => {
      if (!dragging.current) {
        return;
      }
      const dx = event.clientX - last.current.x;
      const dy = event.clientY - last.current.y;
      last.current = { x: event.clientX, y: event.clientY };
      if (Math.abs(dx) + Math.abs(dy) > 2) {
        moved.current = true;
      }
      addPlanetSpin(dx * 0.006, dy * 0.004);
    };

    const endDrag = (event: PointerEvent) => {
      if (!dragging.current) {
        return;
      }
      dragging.current = false;
      if (moved.current) {
        suppressSelectionFor(180);
      }
      if (canvas.hasPointerCapture(event.pointerId)) {
        canvas.releasePointerCapture(event.pointerId);
      }
    };

    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);

    return () => {
      canvas.removeEventListener("pointerdown", onPointerDown);
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("pointerup", endDrag);
      canvas.removeEventListener("pointercancel", endDrag);
    };
  }, [addPlanetSpin, flightState, gl.domElement, suppressSelectionFor, viewMode]);

  return null;
}
