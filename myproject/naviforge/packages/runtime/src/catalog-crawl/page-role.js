export function detailShapeRegex(shape) {
    if (!shape)
        return undefined;
    const escaped = shape
        .split('/')
        .map((part) => (part === '*' ? '[^/]+' : part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
        .join('/');
    try {
        return new RegExp(`/${escaped}(?:[/?#]|$)`, 'i');
    }
    catch {
        return undefined;
    }
}
export function urlMatchesDetailShape(url, shape) {
    if (!shape)
        return false;
    const re = detailShapeRegex(shape);
    if (!re)
        return false;
    try {
        return re.test(new URL(url).pathname);
    }
    catch {
        return false;
    }
}
function playbackSignals(bundle) {
    return (bundle?.signals.filter((s) => s.kind === 'resolved' &&
        s.label === 'playback' &&
        (s.confidence ?? 0) >= 0.9 &&
        s.resolvedUrl) ?? []);
}
/** Classify page role from discover voting + PAGE SIGNALS playback evidence. */
export function classifyPageBrief(discover, bundle) {
    const detailShape = discover.detailShape;
    const listItemCount = discover.listSample.length;
    const playback = playbackSignals(bundle);
    const hasPlayback = playback.length > 0;
    const playbackUrl = playback[0]?.resolvedUrl;
    const currentMatchesDetailShape = urlMatchesDetailShape(discover.url, detailShape);
    if (hasPlayback && currentMatchesDetailShape) {
        return {
            role: 'play',
            confidence: 0.92,
            detailShape,
            listItemCount,
            hasPlayback,
            playbackUrl,
            currentMatchesDetailShape,
        };
    }
    if (detailShape && listItemCount >= 3 && !currentMatchesDetailShape) {
        return {
            role: 'list',
            confidence: Math.min(0.95, 0.72 + listItemCount * 0.02),
            detailShape,
            listItemCount,
            hasPlayback,
            playbackUrl,
            currentMatchesDetailShape,
        };
    }
    if (currentMatchesDetailShape && detailShape) {
        return {
            role: 'detail',
            confidence: hasPlayback ? 0.88 : 0.74,
            detailShape,
            listItemCount,
            hasPlayback,
            playbackUrl,
            currentMatchesDetailShape,
        };
    }
    if (hasPlayback) {
        return {
            role: 'play',
            confidence: 0.8,
            detailShape,
            listItemCount,
            hasPlayback,
            playbackUrl,
            currentMatchesDetailShape,
        };
    }
    if (detailShape && listItemCount >= 2) {
        return {
            role: 'list',
            confidence: 0.62,
            detailShape,
            listItemCount,
            hasPlayback,
            playbackUrl,
            currentMatchesDetailShape,
        };
    }
    return {
        role: 'unknown',
        confidence: 0.4,
        detailShape,
        listItemCount,
        hasPlayback,
        playbackUrl,
        currentMatchesDetailShape,
    };
}
