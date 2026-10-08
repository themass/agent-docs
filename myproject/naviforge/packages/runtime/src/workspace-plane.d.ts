/** Local disk workspace — implemented by the Host HTTP helper. Runtime stays Chrome-free. */
export type WorkspaceEntry = {
    name: string;
    kind: 'file' | 'dir';
    size?: number;
    mtime?: number;
};
export type WorkspaceSkill = {
    id: string;
    version: string;
    description: string;
    instructions: string;
    triggers?: string[];
    enabled: boolean;
    relativePath: string;
    files?: string[];
};
export type WorkspaceShotResult = {
    relativePath: string;
};
export type WorkspaceStat = {
    path: string;
    kind: 'file' | 'dir';
    size?: number;
    mtime?: number;
};
export type WorkspaceGrepHit = {
    path: string;
    line: number;
    text: string;
};
/** User data on disk (`~/NaviForge` by default). Config JSON lives under `config/`. */
export interface WorkspacePlane {
    available(): Promise<boolean>;
    status(): Promise<{
        root: string;
        ok: boolean;
    }>;
    saveShot(input: {
        kind: string;
        dataUrl: string;
        threadId?: string;
        slug?: string;
        title?: string;
        runId?: string;
        tool?: string;
    }): Promise<WorkspaceShotResult>;
    savePage(input: {
        kind: 'md' | 'pdf';
        content?: string;
        dataUrl?: string;
        slug?: string;
    }): Promise<{
        relativePath: string;
        bytes: number;
    }>;
    listSkills(): Promise<WorkspaceSkill[]>;
    writeSkill(input: {
        id: string;
        markdown: string;
    }): Promise<void>;
    removeSkill(id: string): Promise<void>;
    setSkillDisabled(id: string, disabled: boolean): Promise<void>;
    readMcp(): Promise<{
        connections: unknown[];
    }>;
    writeMcp(connections: unknown[]): Promise<void>;
    listDir(dir: string): Promise<WorkspaceEntry[]>;
    readFile(path: string): Promise<string>;
    writeFile(path: string, content: string): Promise<void>;
    mkdir(path: string): Promise<void>;
    touch(path: string): Promise<void>;
    stat(path: string): Promise<WorkspaceStat>;
    glob(pattern: string, dir?: string): Promise<string[]>;
    grep(pattern: string, opts?: {
        path?: string;
        glob?: string;
        max?: number;
    }): Promise<WorkspaceGrepHit[]>;
    writeScript(input: {
        filename: string;
        content: string;
    }): Promise<{
        relativePath: string;
    }>;
    open(path?: string): Promise<void>;
}
export declare function workspaceSlug(title: string): string;
