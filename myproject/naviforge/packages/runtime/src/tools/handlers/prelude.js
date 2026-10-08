import { num, str } from './types.js';
export function normalizeScrollArgs(args) {
    const toRaw = str(args.to);
    const y = num(args.y);
    const direction = str(args.direction);
    const amount = num(args.amount);
    if (toRaw === 'top' || toRaw === 'bottom')
        return { to: toRaw };
    if (toRaw === 'y' && y != null)
        return { to: 'y', y };
    if (y != null)
        return { y };
    if (direction === 'up' || direction === 'down')
        return { direction, amount: amount ?? undefined };
    return { direction: 'down' };
}
export function parseSnapshotMode(value) {
    return value === 'compact' || value === 'viewport' || value === 'full' ? value : undefined;
}
export async function withStaleRevisionRetry(dom, snap, run) {
    let current = snap;
    let result = await run(current.revision);
    if (!result.ok && result.error.code === 'stale_revision') {
        const fresh = await dom.snapshot();
        if (fresh.ok) {
            current = fresh.data;
            result = await run(current.revision);
        }
    }
    return { result, snap: current };
}
export async function networkAfter(network, after) {
    if (!network)
        return undefined;
    await new Promise((resolve) => setTimeout(resolve, 250));
    const events = await network.list({ limit: 10 });
    if (!events.ok)
        return undefined;
    return [...events.data].reverse().find((event) => event.ts >= after && event.status != null);
}
export function handlerPrelude(input) {
    const { decision: turn, action, ctx, blockAsk } = input;
    const { planes: { dom, network, tabs, scripts }, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, } = ctx;
    return {
        turn,
        action,
        ctx,
        blockAsk,
        dom,
        network,
        tabs,
        scripts,
        taskScope,
        callMcpTool,
        mcpTools,
        allowDomInject,
        allowNetworkIntercept,
        skills,
        search: ctx.planes.search,
        fetch: ctx.planes.fetch,
        workspace: ctx.planes.workspace,
    };
}
