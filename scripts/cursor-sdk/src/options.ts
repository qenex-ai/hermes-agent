/**
 * Pure option builder. Always emits exactly one of `local` or `cloud`.
 * Silent SDK default-to-local is the trap this seam exists to prevent.
 */
import {
  CLOUD_AGENT_ID_PREFIX,
  DEFAULT_MODEL,
  type AgentOptionsPlan,
  type SdkRequest,
} from "./types.ts";

export class PlanError extends Error {
  readonly exitCode = 1;
  constructor(message: string) {
    super(message);
    this.name = "PlanError";
  }
}

export function isCloudAgentId(id: string): boolean {
  return id.startsWith(CLOUD_AGENT_ID_PREFIX);
}

export function buildAgentOptions(request: SdkRequest): AgentOptionsPlan {
  if (request.runtime !== "local" && request.runtime !== "cloud") {
    throw new PlanError("runtime must be explicitly 'local' or 'cloud'");
  }
  const apiKey = (request.apiKey ?? "").trim();
  if (!apiKey) {
    throw new PlanError(
      "Missing API key. Pass --api-key or set CURSOR_API_KEY (mint at https://cursor.com/dashboard/cloud-agents).",
    );
  }
  const model = (request.model || DEFAULT_MODEL).trim() || DEFAULT_MODEL;

  const plan: AgentOptionsPlan = {
    apiKey,
    model: { id: model },
  };
  if (request.mcpServers && Object.keys(request.mcpServers).length > 0) {
    plan.mcpServers = request.mcpServers;
  }

  if (request.runtime === "local") {
    const cwd = (request.cwd || "").trim();
    if (!cwd) {
      throw new PlanError("local runtime requires cwd");
    }
    plan.local = {
      cwd,
      // Empty unless the caller opted into ambient Cursor config.
      settingSources: Array.isArray(request.settingSources) ? request.settingSources : [],
    };
    return plan;
  }

  const repos = request.repos ?? [];
  if (request.pattern === "prompt" || request.pattern === "send" || request.pattern === "resume") {
    if (repos.length === 0 || !repos[0]?.url) {
      throw new PlanError("cloud runtime requires --repo <url> (cloud.repos)");
    }
  }
  plan.cloud = {
    repos,
    skipReviewerRequest: request.skipReviewerRequest !== false,
    autoCreatePR: Boolean(request.autoCreatePR),
  };
  return plan;
}

export function assertRuntimeMatchesAgentId(request: SdkRequest): void {
  const id = request.agentId;
  if (!id) return;
  if (isCloudAgentId(id) && request.runtime !== "cloud") {
    throw new PlanError(
      `Agent ID ${id} is a cloud agent ID (bc- prefix). Pass --cloud, not --local.`,
    );
  }
}

export function assertRunIdIsNotAgentId(runId: string): void {
  if (isCloudAgentId(runId)) {
    throw new PlanError(
      `${runId} is a cloud agent ID (bc- prefix), not a run ID. Use 'get <agentId>' or pass the run UUID to get-run.`,
    );
  }
}

export function inspectOptions(request: SdkRequest): Record<string, unknown> {
  if (request.runtime === "local") {
    const cwd = (request.cwd || "").trim();
    if (!cwd) throw new PlanError("local runtime requires cwd");
    return { runtime: "local", cwd, apiKey: request.apiKey };
  }
  const opts: Record<string, unknown> = { runtime: "cloud", apiKey: request.apiKey };
  if (request.agentId) opts.agentId = request.agentId;
  return opts;
}

export function validateRequest(request: SdkRequest): void {
  if (!request.pattern) {
    throw new PlanError("missing invocation pattern");
  }
  if (request.runtime !== "local" && request.runtime !== "cloud") {
    throw new PlanError("runtime must be explicitly --local or --cloud (never omit both)");
  }
  if (request.pattern === "prompt" || request.pattern === "send" || request.pattern === "resume") {
    if (!request.prompt?.trim()) {
      throw new PlanError(`${request.pattern} requires a prompt`);
    }
  }
  if (request.pattern === "resume" && !request.agentId?.trim()) {
    throw new PlanError("resume requires an agent ID");
  }
  if (request.pattern === "get" && !request.agentId?.trim()) {
    throw new PlanError("get requires an agent ID");
  }
  if (request.pattern === "get-run") {
    if (!request.runId?.trim()) {
      throw new PlanError("get-run requires a run ID");
    }
    assertRunIdIsNotAgentId(request.runId);
    if (request.runtime === "cloud" && !request.agentId?.trim()) {
      throw new PlanError("cloud get-run requires --agent-id (parent cloud agent)");
    }
  }
  assertRuntimeMatchesAgentId(request);
  if (request.pattern === "prompt" || request.pattern === "send" || request.pattern === "resume") {
    buildAgentOptions(request);
  }
}
