export type { PageFrictionKind, PageFrictionReport } from './types.js';
export { PAGE_FRICTION_JS, classifyTextFriction, parsePageFrictionPayload, } from './detect.js';
export { formatPageFrictionForPrompt, frictionGuidanceNotes, frictionHitlQuestion, shouldAutoHitl, } from './policy.js';
export { applyPageFrictionToCtx, shouldRefreshPageFriction, type PageFrictionApplyResult, } from './hydrate.js';
export { markPageRateLimited, resetPageThrottleForTests, throttlePageNavigation } from './throttle.js';
