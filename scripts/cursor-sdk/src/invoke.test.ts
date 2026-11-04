import { describe, expect, test } from "vitest";
import { runInvocation } from "./invoke.ts";
import { shouldRetry } from "./errors.ts";
import {
  EXIT_OK,
  EXIT_RUN_ERROR,
  EXIT_STARTUP,
  type AgentLike,
  type RunLike,
  type RunResultLike,
  type SdkBindings,
  type SdkRequest,
} from "./types.ts";

class FakeCursorAgentError extends Error {
  isRetryable: boolean;
  constructor(message: string, isRetryable = false) {
    super(message);
    this.name = "CursorAgentError";
    this.isRetryable = isRetryable;
  }
}

function localSend(over: Partial<SdkRequest> = {}): SdkRequest {
  return {
    pattern: "send",
    prompt: "find the bug",
    apiKey: "cursor_test_key",
    model: "composer-2",
    runtime: "local",
    cwd: "/tmp/repo",
    settingSources: [],
    stream: true,
    ...over,
  };
}

function makeRun(result: RunResultLike, ops: Partial<Record<"stream" | "wait" | "cancel", boolean>> = {}): RunLike {
  const supported = {
    stream: ops.stream ?? true,
    wait: ops.wait ?? true,
    cancel: ops.cancel ?? true,
    conversation: false,
  };
  return {
    id: result.id,
    supports: (op) => Boolean(supported[op]),
    async *stream() {
      yield {
        type: "assistant" as const,
        message: { content: [{ type: "text", text: "ok" }] },
      };
    },
    wait: async () => result,
    cancel: async () => undefined,
  };
}

function makeSdk(opts?: {
  runStatus?: RunResultLike["status"];
  failSend?: Error;
  failPrompt?: Error;
}): { sdk: SdkBindings; calls: string[]; disposed: number; createdOptions: unknown[]; resumeOptions: unknown[] } {
  const calls: string[] = [];
  const createdOptions: unknown[] = [];
  const resumeOptions: unknown[] = [];
  let disposed = 0;
  const finished: RunResultLike = {
    id: "run-1",
    status: opts?.runStatus ?? "finished",
    result: "done",
  };

  const agent: AgentLike = {
    agentId: "agt_live",
    send: async (prompt: string) => {
      calls.push(`send:${prompt}`);
      if (opts?.failSend) throw opts.failSend;
      return makeRun({ ...finished, id: `run-${calls.length}` });
    },
    [Symbol.asyncDispose]: async () => {
      disposed += 1;
    },
  };

  const sdk: SdkBindings = {
    prompt: async (message, options) => {
      calls.push(`prompt:${message}`);
      createdOptions.push(options);
      if (opts?.failPrompt) throw opts.failPrompt;
      return { id: "run-prompt", status: opts?.runStatus ?? "finished", result: "one-shot" };
    },
    create: (options) => {
      calls.push("create");
      createdOptions.push(options);
      return agent;
    },
    resume: (agentId, options) => {
      calls.push(`resume:${agentId}`);
      resumeOptions.push(options);
      return {
        agentId,
        send: agent.send,
        [Symbol.asyncDispose]: agent[Symbol.asyncDispose],
      };
    },
    get: async (agentId) => {
      calls.push(`get:${agentId}`);
      return { id: agentId };
    },
    getRun: async (runId) => {
      calls.push(`getRun:${runId}`);
      return makeRun({ id: runId, status: "finished" });
    },
    list: async () => {
      calls.push("list");
      return { items: [] };
    },
    isCursorAgentError: (err): err is FakeCursorAgentError => err instanceof FakeCursorAgentError,
  };
  return { sdk, calls, get disposed() { return disposed; }, createdOptions, resumeOptions };
}

describe("runInvocation patterns", () => {
  test("prompt uses Agent.prompt and does not create/dispose a durable handle", async () => {
    const fake = makeSdk();
    const logs: string[] = [];
    const result = await runInvocation(localSend({ pattern: "prompt", prompt: "one shot" }), fake.sdk, {
      log: (l) => logs.push(l),
      io: { writeOut: () => undefined, writeErr: () => undefined },
    });
    expect(fake.calls[0]).toMatch(/^prompt:/);
    expect(fake.calls).not.toContain("create");
    expect(fake.disposed).toBe(0);
    expect(result.exitCode).toBe(EXIT_OK);
    expect(result.pattern).toBe("prompt");
    expect(logs.some((l) => l.includes("run=run-prompt"))).toBe(true);
  });

  test("send uses create + send + wait + dispose, including in-process follow-up", async () => {
    const fake = makeSdk();
    const logs: string[] = [];
    const result = await runInvocation(
      localSend({ followUps: ["write a regression test"] }),
      fake.sdk,
      { log: (l) => logs.push(l), io: { writeOut: () => undefined, writeErr: () => undefined } },
    );
    expect(fake.calls).toEqual([
      "create",
      "send:find the bug",
      "send:write a regression test",
    ]);
    expect(fake.disposed).toBe(1);
    expect(result.exitCode).toBe(EXIT_OK);
    expect(result.pattern).toBe("send");
    expect(logs.some((l) => l.includes("agent=agt_live") && l.includes("run="))).toBe(true);
  });

  test("resume re-passes mcpServers and always disposes", async () => {
    const fake = makeSdk();
    const mcp = { linear: { type: "http" as const, url: "https://mcp.linear.app/sse" } };
    const result = await runInvocation(
      localSend({
        pattern: "resume",
        agentId: "agt_prev",
        prompt: "continue",
        mcpServers: mcp,
      }),
      fake.sdk,
      { log: () => undefined, io: { writeOut: () => undefined, writeErr: () => undefined } },
    );
    expect(fake.calls[0]).toBe("resume:agt_prev");
    expect(fake.resumeOptions[0]).toMatchObject({ mcpServers: mcp, local: { cwd: "/tmp/repo" } });
    expect(fake.disposed).toBe(1);
    expect(result.exitCode).toBe(EXIT_OK);
    expect(result.pattern).toBe("resume");
  });

  test("dispose still runs when send throws CursorAgentError", async () => {
    const fake = makeSdk({ failSend: new FakeCursorAgentError("auth failed", false) });
    const result = await runInvocation(localSend(), fake.sdk, {
      log: () => undefined,
      io: { writeOut: () => undefined, writeErr: () => undefined },
    });
    expect(result.exitCode).toBe(EXIT_STARTUP);
    expect(result.retryable).toBe(false);
    expect(fake.disposed).toBe(1);
  });

  test("run status error exits 2 and is not treated as retryable startup", async () => {
    const fake = makeSdk({ runStatus: "error" });
    const result = await runInvocation(localSend(), fake.sdk, {
      log: () => undefined,
      io: { writeOut: () => undefined, writeErr: () => undefined },
    });
    expect(result.exitCode).toBe(EXIT_RUN_ERROR);
    expect(result.status).toBe("error");
    expect(shouldRetry(result)).toBe(false);
    expect(fake.disposed).toBe(1);
  });

  test("retryable CursorAgentError is reported but not retried", async () => {
    const fake = makeSdk({ failPrompt: new FakeCursorAgentError("rate limit", true) });
    const result = await runInvocation(localSend({ pattern: "prompt", prompt: "hi" }), fake.sdk, {
      log: () => undefined,
      io: { writeOut: () => undefined, writeErr: () => undefined },
    });
    expect(result.exitCode).toBe(EXIT_STARTUP);
    expect(result.retryable).toBe(true);
    expect(shouldRetry(result)).toBe(true);
    expect(fake.calls.filter((c) => c.startsWith("prompt:")).length).toBe(1);
  });

  test("explicit local vs cloud is required", async () => {
    const fake = makeSdk();
    const result = await runInvocation(
      { ...localSend(), runtime: "bogus" as SdkRequest["runtime"] },
      fake.sdk,
      { log: () => undefined, io: { writeOut: () => undefined, writeErr: () => undefined } },
    );
    expect(result.exitCode).toBe(EXIT_STARTUP);
    expect(fake.calls).toEqual([]);
  });
});
