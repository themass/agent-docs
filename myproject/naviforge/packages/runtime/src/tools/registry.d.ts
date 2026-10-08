export type ToolHandler<TContext, TResult> = (context: TContext) => Promise<TResult> | TResult;
export declare class ToolRegistry<TContext, TResult> {
    #private;
    register(id: string, handler: ToolHandler<TContext, TResult>): this;
    ids(): string[];
    get(id: string): ToolHandler<TContext, TResult> | undefined;
    assertCatalog(catalogIds: readonly string[]): void;
}
