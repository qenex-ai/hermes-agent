/**
 * Shared request/result types for the Hermes ↔ @cursor/sdk bridge.
 *
 * These are our own shapes so the testable seams do not import @cursor/sdk.
 * Production `cli.ts` maps them onto the real SDK.
 */

export type RuntimeKind = "local" | "cloud";

export type InvocationPattern = "prompt" | "send" | "resume" | "get" | "get-run" | "list";

export type McpServerConfig =
  | {
      type?: "stdio";
      command: string;
      args?: string[];
      env?: Record<string, string>;
      cwd?: string;
    }
  | {
      type?: "http" | "sse";
      url: string;
      headers?: Record<string, string>;
    };

export interface CloudRepo {
  url: string;
  startingRef?: string;
}

export interface SdkRequest {
  pattern: InvocationPattern;
  prompt?: string;
  followUps?: string[];
  agentId?: string;
  runId?: string;
  apiKey: string;
  model: string;
  runtime: RuntimeKind;
  cwd?: string;
  repos?: CloudRepo[];
  skipReviewerRequest?: boolean;
  autoCreatePR?: boolean;
  settingSources?: string[];
  mcpServers?: Record<string, McpServerConfig>;
  stream?: boolean;
  cancelAfterMs?: number | null;
}

export interface AgentOptionsPlan {
  apiKey: string;
  model: { id: string };
  mcpServers?: Record<string, McpServerConfig>;
  local?: {
    cwd: string;
    settingSources: string[];
  };
  cloud?: {
    repos: CloudRepo[];
    skipReviewerRequest: boolean;
    autoCreatePR: boolean;
  };
}

export type RunStatus = "finished" | "error" | "cancelled";

export interface RunResultLike {
  id: string;
  status: RunStatus;
  result?: string;
  durationMs?: number;
}

export interface RunLike {
  id: string;
  supports: (op: "stream" | "wait" | "cancel" | "conversation") => boolean;
  unsupportedReason?: (op: string) => string | undefined;
  stream: () => AsyncIterable<SdkStreamEvent>;
  wait: () => Promise<RunResultLike>;
  cancel: () => Promise<void>;
  conversation?: () => Promise<unknown>;
}

export interface AgentLike {
  agentId: string;
  send: (prompt: string) => Promise<RunLike>;
  [Symbol.asyncDispose]?: () => Promise<void>;
}

export type SdkStreamEvent =
  | {
      type: "assistant";
      message: { content: Array<{ type: string; text?: string }> };
    }
  | { type: "thinking"; text: string }
  | { type: "tool_call"; name: string; status: string; call_id?: string }
  | { type: "status"; status: string }
  | { type: "task"; text?: string }
  | { type: "user" }
  | { type: "system" }
  | { type: "request"; request_id?: string };

export interface CursorAgentErrorLike extends Error {
  isRetryable?: boolean;
  code?: unknown;
  protoErrorCode?: unknown;
}

export interface SdkBindings {
  prompt: (message: string, options: AgentOptionsPlan) => Promise<RunResultLike>;
  create: (options: AgentOptionsPlan) => AgentLike | Promise<AgentLike>;
  resume: (agentId: string, options: AgentOptionsPlan) => AgentLike | Promise<AgentLike>;
  get: (agentId: string, options: Record<string, unknown>) => Promise<unknown>;
  getRun: (runId: string, options: Record<string, unknown>) => Promise<RunLike>;
  list: (options: Record<string, unknown>) => Promise<{ items: unknown[]; nextCursor?: string }>;
  isCursorAgentError: (err: unknown) => err is CursorAgentErrorLike;
}

export interface InvocationResult {
  exitCode: number;
  pattern: InvocationPattern;
  agentId?: string;
  runId?: string;
  status?: RunStatus | string;
  retryable?: boolean;
  result?: string;
  error?: string;
}

export const EXIT_OK = 0;
export const EXIT_STARTUP = 1;
export const EXIT_RUN_ERROR = 2;
export const EXIT_CANCELLED = 3;

export const DEFAULT_MODEL = "composer-2";
export const CLOUD_AGENT_ID_PREFIX = "bc-";
