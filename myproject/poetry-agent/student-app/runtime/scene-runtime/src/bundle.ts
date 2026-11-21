/**
 * The scene bundle contract, as TypeScript types. This is the ONLY thing the client ever sees:
 * the base (poetry_*) never reaches the browser. Kept in sync with contracts/bundle.schema.json;
 * tools/scene-validator/validate.mjs is the authority — if they disagree, fix this file.
 */
export const SCHEMA_MAJOR = 1;

export type StepId = 'read' | 'arrive' | 'meet' | 'return' | 'recite';
export type LayerId = 'SCENE' | 'CITY' | 'WORLD' | 'PERSON';
export type ClaimKind = 'FACT' | 'INTERPRETATION' | 'DRAMATIZATION';
export type MediaLevel = 'L0' | 'L1' | 'L2' | 'L3' | 'L4';

export const STEPS: StepId[] = ['read', 'arrive', 'meet', 'return', 'recite'];
export const TERMINAL_ASSET = 'L0-text';

export interface SpokenLine {
  text: string;
  kind: ClaimKind;
  /** null only when kind === DRAMATIZATION, and then badge must be rendered visibly. */
  basis: { claim_id: string } | null;
  badge?: string;
}

export interface SceneLayer {
  layer: LayerId;
  bg_id: string;
  line_seqs?: number[];
  assets?: string[];
  lines?: SpokenLine[];
  places?: string[];
  events?: string[];
  experience?: string[];
  theme_id?: string;
  timeline_window?: [number, number];
}

export interface SituationChoice {
  layer: LayerId;
  /** 面向学生的指路词，2–12 字。它是路标，不是标题：不用"眼前/这座城"这类抽象层名。 */
  label: string;
}

/**
 * 「到」的入口句：先说"你在这里"，再由学生决定先看哪儿。
 * 是 DRAMATIZATION 时 badge 必须逐字等于 OQ-01 那一句，否则页面不显示（与 spokenLine 同一条规则）。
 */
export interface Situation {
  text: string;
  kind: ClaimKind;
  basis: { claim_id: string } | null;
  badge?: string;
  choices: SituationChoice[];
}

export interface ScriptStep {
  step: StepId;
  /** R12: never gate a learner. Both flags are compile-time required to be true. */
  skip_allowed: true;
  back_allowed: true;
  /** 只有 arrive 用；缺省时页面退回四张并列卡片，不是错误。 */
  situation?: Situation;
  layers?: SceneLayer[];
  roleplay?: { declared_as: 'DRAMATIZATION'; layers: SceneLayer[] };
  person_id?: string;
  at?: { place_id: string; year_claim?: string; year_claims?: string[] };
  text_side?: { annotations?: string[] };
  demo_audio?: string;
  learner_recording?: { policy: 'local_only' | 'upload_with_consent'; upload: boolean };
  agent_help?: { mode: 'guided'; actions: string[] };
}

export interface AssetSpec {
  kind: 'illustration' | 'map' | 'character' | 'audio' | 'voice' | 'subtitle' | 'video';
  level: MediaLevel;
  hash: string;
  files: Record<string, string>;
  /** Must terminate at TERMINAL_ASSET. Text is always the floor; never an empty chain. */
  fallback: string[];
  rights: { origin: string; license: string; human_fix?: boolean; workflow?: string };
  /** Which line this asset helps the learner understand. "Cannot say it" => must not exist (R10). */
  meaning: string;
  bytes?: number;
}

export interface SceneBundle {
  schema_version: string;
  script_id: string;
  script_version: string;
  work_id: string;
  text_version_id: string;
  audiences: string[];
  coverage_notice: string;
  unknown_dates_notice?: string;
  glossary_bindings: true;
  annotation_ids?: string[];
  cast?: { content_id: string; voice_id?: string; avatar_asset?: string }[];
  steps: ScriptStep[];
  assets: Record<string, AssetSpec>;
}

export interface BundleManifest {
  bundle_hash: string;
  script_id: string;
  script_version: string;
  schema_version: string;
  text_version_id: string;
  asset_hashes: Record<string, string>;
  coverage_notice: string;
  compiled_at: string;
  compiled_by: string;
  total_bytes: number;
}

export function schemaMajor(bundle: Pick<SceneBundle, 'schema_version'>): number {
  return Number(String(bundle.schema_version).split('.')[0]);
}
