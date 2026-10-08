export { PAGE_FRICTION_JS as AUTH_GATE_JS } from '../page-friction/detect.js';
export type AuthGateResult = {
    needsAuth: boolean;
    captcha: boolean;
    url: string;
    title: string;
};
export declare function parseAuthGatePayload(raw: unknown): AuthGateResult | null;
