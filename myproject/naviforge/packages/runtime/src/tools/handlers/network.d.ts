import type { BuiltinHandler } from './types.js';
export declare const networkHandlers: {
    readonly network_digest: BuiltinHandler;
    readonly network_list: BuiltinHandler;
    readonly network_get_body: BuiltinHandler;
    readonly network_media_hints: BuiltinHandler;
    readonly network_resolve_hls: BuiltinHandler;
    readonly network_wait: BuiltinHandler;
    readonly network_intercept: BuiltinHandler;
    readonly network_clear_intercepts: BuiltinHandler;
};
export declare const networkCatalogHandler: BuiltinHandler;
