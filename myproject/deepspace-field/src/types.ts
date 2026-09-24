export type ScaleMode = "compressed" | "real" | "cinematic";

export type FlightState = "idle" | "traveling" | "orbiting";

/** navigate = 相机绕目标转；inspect = 拖拽只转当前天体 */
export type ViewMode = "navigate" | "inspect";

export type CloseUpLevel = "approach" | "surface";

export type BodyKind = "star" | "planet" | "dwarf-planet" | "moon";

export type DeepSpaceKind =
  | "deep-field"
  | "nebula"
  | "galaxy-group"
  | "black-hole";

export type SourceRecord = {
  name: string;
  url: string;
  note: string;
};

export type Body = {
  id: string;
  name: string;
  englishName: string;
  kind: BodyKind;
  parentId?: string;
  radiusKm: number;
  orbitRadiusAu: number;
  orbitPeriodDays: number;
  rotationPeriodHours: number;
  color: string;
  accentColor: string;
  facts: string[];
  sources: SourceRecord[];
  texturePlan: string;
  visualNotes: string[];
  moons?: string[];
};

export type DeepSpacePoi = {
  id: string;
  name: string;
  englishName: string;
  kind: DeepSpaceKind;
  distance: string;
  coordinates: string;
  sourceMission: string;
  archive: SourceRecord[];
  whyItMatters: string;
  visualizationPlan: string;
  observationFacts: string[];
  artisticEnhancements: string[];
  color: string;
};

export type Target =
  | { type: "body"; id: string }
  | { type: "deep-space"; id: string };
