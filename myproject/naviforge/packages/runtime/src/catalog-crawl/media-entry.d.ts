import { classifyMediaUrl } from '@naviforge/media-plane';
/** Playback evidence format for catalog / spawn output schema. */
export type MediaPlaybackFormat = 'hls' | 'dash' | 'mp4' | 'webm' | 'embed' | 'unknown';
export declare function mapHintKindToFormat(kind: ReturnType<typeof classifyMediaUrl>): MediaPlaybackFormat;
export declare function classifyPlaybackUrl(url: string): MediaPlaybackFormat;
export declare function entryHasPlayableEvidence(entry: {
    mediaUrl?: string;
    playPageUrl?: string;
}): boolean;
export declare function isLikelyPlayPageUrl(url: string): boolean;
/** Pinned in KERNEL/GUIDANCE — agent + spawn children use this shape. */
export declare const MEDIA_ENTRY_OUTPUT_SCHEMA = "\u6BCF\u6761\u5A92\u4F53\u6761\u76EE\u8F93\u51FA schema\uFF08\u7236/\u5B50\u4EFB\u52A1 system_done \u5747\u9075\u5B88\uFF09\uFF1A\n{\n  \"title\": string,\n  \"listUrl\"?: string,        // \u5217\u8868/\u8BE6\u60C5\u94FE\u63A5\n  \"mediaUrl\"?: string,       // \u76F4\u94FE\uFF1Am3u8/mpd/mp4/webm/\u2026\n  \"playPageUrl\"?: string,    // \u65E0\u76F4\u94FE\u65F6\u7684\u64AD\u653E/embed/\u5185\u5D4C\u9875\n  \"format\"?: \"hls\"|\"dash\"|\"mp4\"|\"webm\"|\"embed\"|\"unknown\",\n  \"confidence\"?: number,     // 0\u20131\n  \"shortfall\"?: string       // \u4E3A\u4F55\u65E0\u76F4\u94FE\u3001\u9700\u70B9\u51FB\u64AD\u653E\u3001blob/DRM \u7B49\n}\n\u89C4\u5219\uFF1A\u6709\u76F4\u94FE\u5199 mediaUrl+format\uFF1B\u4EC5 iframe/\u5185\u5D4C\u64AD\u653E\u5668\u5199 playPageUrl+shortfall\uFF1B\u591A\u4E2A\u5019\u9009\u7531\u6A21\u578B\u7ED3\u5408 PAGE SIGNALS \u9009\u4E3B\u64AD\u653E\u6D41\u3002";
export declare const MEDIA_AGENT_JUDGMENT_GUIDANCE: readonly ["GUIDANCE: 视频源不限 m3u8 — mp4/webm/dash(mpd)/hls 均可；无直链可输出 playPageUrl（内嵌播放页）。", "GUIDANCE: 列表页通常无直链 — spawn 打开详情/播放页，读 PAGE SIGNALS；需点播放时用 dom_click + network_read。", "GUIDANCE: blob:/MediaSource/DRM — 禁止逆向；shortfall 说明 + 给 playPageUrl 或 listUrl。", "GUIDANCE: preflight 预算外条目（>24）— system_spawn_readonly_tasks 每批≤3，子 prompt 要求返回 MEDIA_ENTRY schema。"];
