import { ToolRegistry } from './registry.js';
import type { BuiltinContext, BuiltinResult } from './handlers/types.js';
export declare const BUILTIN_TOOL_REGISTRY: ToolRegistry<BuiltinContext, BuiltinResult>;
export declare function executeBuiltinTool(input: BuiltinContext): Promise<BuiltinResult>;
