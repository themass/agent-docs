export type RunProfile = {
    name: 'readonly-child';
    allowedTools: readonly string[];
    allowReadonlyMcp?: boolean;
    /** Parent owns the network debugger lifecycle. */
    manageNetwork?: boolean;
};
export declare const READONLY_RUN_PROFILE: RunProfile;
