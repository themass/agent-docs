import type { PageFrictionReport } from './types.js';
export declare function formatPageFrictionForPrompt(report: PageFrictionReport): string;
export declare function frictionGuidanceNotes(report: PageFrictionReport): string[];
export declare function frictionHitlQuestion(report: PageFrictionReport): string | undefined;
export declare function shouldAutoHitl(report: PageFrictionReport): boolean;
export declare function frictionHitlKey(report: PageFrictionReport): string;
