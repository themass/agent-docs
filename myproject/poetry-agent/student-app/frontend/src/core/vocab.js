/** Closed vocabularies. Mirrors vvv-student's StudentVocabulary; data/events.js is checked against it in tests. */
export const STEPS = ['read', 'arrive', 'meet', 'return', 'recite'];
export const LAYERS = ['SCENE', 'CITY', 'WORLD', 'PERSON'];
// A reader's own question ('free_text') is deliberately NOT here: it is not an event at all (lesson.js), so
// nothing about it is queued, stored or sent to vvv-student.
export const ASK_ACTIONS = ['rephrase', 'hint', 'ask_why', 'open_layer', 'basis', 'recite_prompt', 'decline'];
export const DEGRADE_REASONS = ['weak_net', 'low_memory', 'reduced_motion', 'user_off', 'asset_failed', 'context_lost'];
export const FALLBACK_REASONS = ['timeout', 'unavailable', 'rejected', 'budget', 'disabled'];
export const RETELL_LENGTHS = ['len_0_20', 'len_21_60', 'len_61_plus'];
export const EVENT_KINDS = ['step_enter', 'step_leave', 'step_skip', 'layer_open', 'line_tap', 'ask',
  'retell_submit', 'media_degraded', 'agent_fallback'];
export const ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/;
export const MAX_EVENTS_PER_BATCH = 50;
export const MAX_DWELL_MS = 3_600_000;
export const MAX_LINE_SEQ = 64;
