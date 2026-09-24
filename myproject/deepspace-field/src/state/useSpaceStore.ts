import { create } from "zustand";
import type { CloseUpLevel, FlightState, ScaleMode, Target, ViewMode } from "../types";

type PlanetSpin = { yaw: number; pitch: number };

type SpaceStore = {
  selectedTarget: Target;
  scaleMode: ScaleMode;
  flightState: FlightState;
  viewMode: ViewMode;
  focusIsolation: boolean;
  closeUpLevel: CloseUpLevel;
  closeUpNonce: number;
  planetSpin: PlanetSpin;
  simulationDay: number;
  showSciencePanel: boolean;
  suppressSelectUntil: number;
  selectTarget: (target: Target) => void;
  setScaleMode: (mode: ScaleMode) => void;
  setFlightState: (state: FlightState) => void;
  setViewMode: (mode: ViewMode) => void;
  setFocusIsolation: (enabled: boolean) => void;
  toggleFocusIsolation: () => void;
  requestCloseUp: () => void;
  addPlanetSpin: (deltaYaw: number, deltaPitch: number) => void;
  suppressSelectionFor: (ms: number) => void;
  resetPlanetSpin: () => void;
  setSimulationDay: (day: number) => void;
  toggleSciencePanel: () => void;
};

export const useSpaceStore = create<SpaceStore>((set, get) => ({
  selectedTarget: { type: "body", id: "earth" },
  scaleMode: "compressed",
  flightState: "traveling",
  viewMode: "navigate",
  focusIsolation: false,
  closeUpLevel: "approach",
  closeUpNonce: 0,
  planetSpin: { yaw: 0, pitch: 0 },
  simulationDay: 0,
  showSciencePanel: true,
  suppressSelectUntil: 0,
  selectTarget: (target) => {
    if (Date.now() < get().suppressSelectUntil) {
      return;
    }

    const current = get().selectedTarget;
    const selectingCurrent =
      current.type === target.type && current.id === target.id;

    set({
      selectedTarget: target,
      flightState: selectingCurrent ? get().flightState : "traveling",
      viewMode: selectingCurrent ? get().viewMode : "navigate",
      closeUpLevel: selectingCurrent ? get().closeUpLevel : "approach",
      planetSpin: selectingCurrent ? get().planetSpin : { yaw: 0, pitch: 0 },
      showSciencePanel: true,
      focusIsolation: selectingCurrent ? get().focusIsolation : target.type === "body",
    });
  },
  setScaleMode: (mode) => set({ scaleMode: mode }),
  setFlightState: (state) => set({ flightState: state }),
  setViewMode: (mode) => set({ viewMode: mode }),
  setFocusIsolation: (enabled) => set({ focusIsolation: enabled }),
  toggleFocusIsolation: () =>
    set((state) => ({ focusIsolation: !state.focusIsolation })),
  requestCloseUp: () =>
    set((state) => ({
      closeUpNonce: state.closeUpNonce + 1,
      closeUpLevel: "surface",
      viewMode: "inspect",
      focusIsolation: state.selectedTarget.type === "body",
      flightState: "traveling",
    })),
  addPlanetSpin: (deltaYaw, deltaPitch) =>
    set((state) => ({
      planetSpin: {
        yaw: state.planetSpin.yaw + deltaYaw,
        pitch: Math.max(
          -Math.PI / 2.2,
          Math.min(Math.PI / 2.2, state.planetSpin.pitch + deltaPitch),
        ),
      },
    })),
  suppressSelectionFor: (ms) =>
    set({ suppressSelectUntil: Date.now() + ms }),
  resetPlanetSpin: () => set({ planetSpin: { yaw: 0, pitch: 0 } }),
  setSimulationDay: (day) => set({ simulationDay: day }),
  toggleSciencePanel: () =>
    set((state) => ({ showSciencePanel: !state.showSciencePanel })),
}));
