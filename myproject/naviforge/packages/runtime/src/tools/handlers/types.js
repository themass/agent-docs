export function str(value) {
    return typeof value === 'string' ? value : null;
}
export function num(value) {
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
