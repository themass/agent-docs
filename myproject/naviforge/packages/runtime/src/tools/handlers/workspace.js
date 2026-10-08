import { resolveBuiltinToolCall } from '../builtin-tool-resolver.js';
function str(value) {
    return typeof value === 'string' ? value : null;
}
export function workspaceFail(code, message) {
    return { ok: false, error: { code, message, recoverable: true } };
}
export const workspaceLs = async (args, workspace) => {
    const rel = str(args.path) ?? '';
    const [entries, status] = await Promise.all([workspace.listDir(rel), workspace.status()]);
    return { ok: true, data: { root: status.root, path: rel || '.', entries } };
};
export const workspaceRead = async (args, workspace) => {
    const path = str(args.path);
    if (!path)
        return workspaceFail('bad_args', 'path required');
    const content = await workspace.readFile(path);
    return { ok: true, data: { path, content: content.length > 100_000 ? `${content.slice(0, 100_000)}…` : content } };
};
export const workspaceWrite = async (args, workspace) => {
    const path = str(args.path);
    const content = str(args.content);
    if (!path || content === null)
        return workspaceFail('bad_args', 'path and content required');
    if (content.length > 200_000)
        return workspaceFail('too_large', 'file exceeds 200KB');
    await workspace.writeFile(path, content);
    return { ok: true, data: { path, bytes: content.length } };
};
function workspacePathHandler(run) {
    return async (args, workspace) => {
        const path = str(args.path);
        if (!path)
            return workspaceFail('bad_args', 'path required');
        const data = await run(workspace, path);
        return data === undefined ? { ok: true, data: { path } } : { ok: true, data };
    };
}
export const workspaceMkdir = workspacePathHandler((workspace, path) => workspace.mkdir(path));
export const workspaceTouch = workspacePathHandler((workspace, path) => workspace.touch(path));
export const workspaceStat = workspacePathHandler((workspace, path) => workspace.stat(path));
export const workspaceGlob = async (args, workspace) => {
    const path = str(args.path) ?? '';
    const pattern = str(args.pattern) ?? '**/*';
    const paths = await workspace.glob(pattern, path);
    return { ok: true, data: { pattern, path: path || '.', paths, n: paths.length } };
};
export const workspaceGrep = async (args, workspace) => {
    const pattern = str(args.pattern);
    if (!pattern)
        return workspaceFail('bad_args', 'pattern required');
    const path = str(args.path);
    const hits = await workspace.grep(pattern, { path: path || undefined, glob: str(args.glob) ?? undefined });
    return { ok: true, data: { pattern, hits, n: hits.length } };
};
export function workspaceBuiltinHandler(run) {
    return async (input) => {
        const workspace = input.ctx.planes.workspace;
        if (!workspace) {
            return {
                result: workspaceFail('no_workspace', '本机工作区未连接'),
                snap: input.snap,
            };
        }
        try {
            return { result: await run(input.action.arguments, workspace), snap: input.snap };
        }
        catch (error) {
            return {
                result: workspaceFail('workspace_error', error.message),
                snap: input.snap,
            };
        }
    };
}
export const workspaceHandlers = {
    workspace_ls: workspaceBuiltinHandler(workspaceLs),
    workspace_read: workspaceBuiltinHandler(workspaceRead),
    workspace_write: workspaceBuiltinHandler(workspaceWrite),
    workspace_mkdir: workspaceBuiltinHandler(workspaceMkdir),
    workspace_touch: workspaceBuiltinHandler(workspaceTouch),
    workspace_stat: workspaceBuiltinHandler(workspaceStat),
    workspace_glob: workspaceBuiltinHandler(workspaceGlob),
    workspace_grep: workspaceBuiltinHandler(workspaceGrep),
};
export const workspaceCatalogHandler = async (input) => {
    const action = input.action.arguments.action;
    if (typeof action !== 'string') {
        return {
            result: workspaceFail('bad_args', 'workspace action required (ls|read|write|mkdir|touch|stat|glob|grep)'),
            snap: input.snap,
        };
    }
    const resolved = resolveBuiltinToolCall('workspace', input.action.arguments);
    const handler = workspaceHandlers[resolved.tool];
    if (!handler) {
        return {
            result: workspaceFail('bad_args', `unknown workspace action: ${action}`),
            snap: input.snap,
        };
    }
    return handler({
        ...input,
        action: { ...input.action, tool: resolved.tool, arguments: resolved.arguments },
    });
};
