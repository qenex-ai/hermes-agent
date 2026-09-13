import { describe, expect, test } from "vitest";
import {
  assertRunIdIsNotAgentId,
  buildAgentOptions,
  isCloudAgentId,
  PlanError,
  validateRequest,
} from "./options.ts";
import type { SdkRequest } from "./types.ts";

function localPrompt(over: Partial<SdkRequest> = {}): SdkRequest {
  return {
    pattern: "prompt",
    prompt: "hello",
    apiKey: "cursor_test_key",
    model: "composer-2",
    runtime: "local",
    cwd: "/tmp/repo",
    settingSources: [],
    ...over,
  };
}

describe("buildAgentOptions", () => {
  test("local always sets cwd and empty settingSources under local, never cloud", () => {
    const plan = buildAgentOptions(localPrompt());
    expect(plan.local).toEqual({ cwd: "/tmp/repo", settingSources: [] });
    expect(plan.cloud).toBeUndefined();
    expect(plan.apiKey).toBe("cursor_test_key");
    expect(plan.model).toEqual({ id: "composer-2" });
  });

  test("cloud always sets repos and skipReviewerRequest, never local", () => {
    const plan = buildAgentOptions(
      localPrompt({
        runtime: "cloud",
        cwd: undefined,
        repos: [{ url: "https://github.com/org/repo", startingRef: "main" }],
        skipReviewerRequest: true,
      }),
    );
    expect(plan.local).toBeUndefined();
    expect(plan.cloud).toEqual({
      repos: [{ url: "https://github.com/org/repo", startingRef: "main" }],
      skipReviewerRequest: true,
      autoCreatePR: false,
    });
  });

  test("refuses local without cwd and cloud without repo", () => {
    expect(() => buildAgentOptions(localPrompt({ cwd: "" }))).toThrow(PlanError);
    expect(() =>
      buildAgentOptions(
        localPrompt({ runtime: "cloud", cwd: undefined, repos: [] }),
      ),
    ).toThrow(/cloud runtime requires --repo/);
  });

  test("resume re-includes mcpServers on the options object", () => {
    const mcp = {
      docs: { type: "http" as const, url: "https://example.com/mcp" },
    };
    const plan = buildAgentOptions(
      localPrompt({ pattern: "resume", agentId: "agt_1", mcpServers: mcp }),
    );
    expect(plan.mcpServers).toEqual(mcp);
  });
});

describe("id contracts", () => {
  test("bc- prefix is a cloud agent id, not a run id", () => {
    expect(isCloudAgentId("bc-abc123")).toBe(true);
    expect(isCloudAgentId("run-uuid")).toBe(false);
    expect(() => assertRunIdIsNotAgentId("bc-abc123")).toThrow(/not a run ID/);
  });

  test("validateRequest rejects get-run with a bc- id", () => {
    expect(() =>
      validateRequest(
        localPrompt({
          pattern: "get-run",
          prompt: undefined,
          runId: "bc-abc123",
          runtime: "cloud",
          agentId: "bc-abc123",
          repos: [{ url: "https://github.com/org/repo" }],
        }),
      ),
    ).toThrow(/not a run ID/);
  });
});
