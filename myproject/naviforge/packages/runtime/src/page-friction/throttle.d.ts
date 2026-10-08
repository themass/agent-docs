export declare function throttlePageNavigation(opts?: {
    rateLimited?: boolean;
}): Promise<void>;
export declare function markPageRateLimited(): void;
export declare function resetPageThrottleForTests(): void;
