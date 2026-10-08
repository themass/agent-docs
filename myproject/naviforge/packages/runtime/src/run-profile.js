export const READONLY_RUN_PROFILE = {
    name: 'readonly-child',
    allowedTools: [
        'browser_observe',
        'tabs',
        'network',
        'fetch_text',
        'web_search',
        'system_done',
    ],
    allowReadonlyMcp: true,
    manageNetwork: false,
};
