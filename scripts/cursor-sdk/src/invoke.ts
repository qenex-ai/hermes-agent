/**
 * Orchestrates the three SDK invocation patterns behind an injectable SDK seam.
 *
 * Production wires this to `@cursor/sdk`. Tests inject fakes so we can assert
 * routing, dispose, logging, and exit codes without a live Cursor backend.
 */
import { mapRunStatus, mapThrownError } from "./errors.ts";
import {
  assertRunIdIsNotAgentId,
  buildAgentOptions,
  inspectOptions,
  validateRequest,
} from "./options.ts";
import { cancelIfSupported, consumeStream, waitForRun } from "./stream.ts";
import {
  EXIT_STARTUP,
  type AgentLike,
  type InvocationResult,
  type RunLike,
  type SdkBindings,
  type SdkRequest,
} from "./types.ts";

export interface InvokeHooks {
  log: (line: string) => void;
  io?: {
    writeOut: (text: string) => void;
    writeErr: (text: string) => void;
  };
}

const defaultHooks: InvokeHooks = {
  log: (line) => process.stderr.write(`${line}\n`),
};

async function disposeAgent(agent: AgentLike | undefined): Promise<void> {
  if (!agent) return;
  const dispose = agent[Symbol.asyncDispose];
  if (typeof dispose === "function") {
    await dispose.call(agent);
  }
}

async function driveRun(
  agent: AgentLike,
  run: RunLike,
  request: SdkRequest,
  hooks: InvokeHooks,
): Promise<InvocationResult> {
  const io = hooks.io;
  // IDs first — if the stream hangs these are what you look up.
  hooks.log(`[cursor-sdk] agent=${agent.agentId} run=${run.id}`);

  let cancelTimer: ReturnType<typeof setTimeout> | undefined;
  if (request.cancelAfterMs && request.cancelAfterMs > 0) {
    cancelTimer = setTimeout(() => {
      void cancelIfSupported(run, io);
    }, request.cancelAfterMs);
  }

  try {
    if (request.stream !== false) {
      await consumeStream(run, io);
    }
    const result = await waitForRun(run, io);
    const mapped = mapRunStatus(result);
    return {
      exitCode: mapped.exitCode,
      pattern: "send",
      agentId: agent.agentId,
      runId: result.id,
      status: mapped.status,
      result: result.result,
    };
  } finally {
    if (cancelTimer) clearTimeout(cancelTimer);
  }
}

async function durableConversation(
  agent: AgentLike,
  request: SdkRequest,
  hooks: InvokeHooks,
): Promise<InvocationResult> {
  const prompts = [request.prompt!, ...(request.followUps ?? [])].filter((p) => p.trim());
  let last: InvocationResult | undefined;
  for (const prompt of prompts) {
    const run = await agent.send(prompt);
    last = await driveRun(agent, run, request, hooks);
    if (last.exitCode !== 0) return { ...last, pattern: request.pattern };
  }
  return last ?? {
    exitCode: EXIT_STARTUP,
    pattern: request.pattern,
    error: "no prompts sent",
  };
}

export async function runInvocation(
  request: SdkRequest,
  sdk: SdkBindings,
  hooks: InvokeHooks = defaultHooks,
): Promise<InvocationResult> {
  try {
    validateRequest(request);

    if (request.pattern === "prompt") {
      const options = buildAgentOptions(request);
      const result = await sdk.prompt(request.prompt!, options);
      const mapped = mapRunStatus(result);
      hooks.log(`[cursor-sdk] pattern=prompt run=${result.id} status=${result.status}`);
      return {
        exitCode: mapped.exitCode,
        pattern: "prompt",
        runId: result.id,
        status: mapped.status,
        result: result.result,
      };
    }

    if (request.pattern === "get") {
      const info = await sdk.get(request.agentId!, inspectOptions(request));
      hooks.log(`[cursor-sdk] pattern=get agent=${request.agentId}`);
      return {
        exitCode: 0,
        pattern: "get",
        agentId: request.agentId,
        result: JSON.stringify(info),
      };
    }

    if (request.pattern === "get-run") {
      assertRunIdIsNotAgentId(request.runId!);
      const opts = inspectOptions(request);
      if (request.runtime === "cloud") opts.agentId = request.agentId;
      const run = await sdk.getRun(request.runId!, opts);
      hooks.log(`[cursor-sdk] pattern=get-run run=${run.id} agent=${request.agentId ?? ""}`);
      if (request.stream !== false && run.supports("stream")) {
        await consumeStream(run, hooks.io);
      }
      const result = run.supports("wait") ? await run.wait() : { id: run.id, status: "finished" as const };
      const mapped = mapRunStatus(result);
      return {
        exitCode: mapped.exitCode,
        pattern: "get-run",
        agentId: request.agentId,
        runId: result.id,
        status: mapped.status,
        result: result.result,
      };
    }

    if (request.pattern === "list") {
      const listed = await sdk.list(inspectOptions(request));
      return {
        exitCode: 0,
        pattern: "list",
        result: JSON.stringify(listed),
      };
    }

    const options = buildAgentOptions(request);
    // mcpServers are re-passed on resume on purpose — the SDK does not persist them.
    const agent = await (request.pattern === "resume"
      ? sdk.resume(request.agentId!, options)
      : sdk.create(options));
    try {
      hooks.log(`[cursor-sdk] pattern=${request.pattern} agent=${agent.agentId}`);
      const outcome = await durableConversation(agent, request, hooks);
      return { ...outcome, pattern: request.pattern, agentId: agent.agentId };
    } finally {
      await disposeAgent(agent);
    }
  } catch (err) {
    const mapped = mapThrownError(err, sdk);
    if (mapped.retryable) {
      hooks.log(
        `[cursor-sdk] startup failed (retryable=${mapped.retryable}): ${mapped.error}. Not retrying automatically.`,
      );
    } else {
      hooks.log(`[cursor-sdk] failed: ${mapped.error}`);
    }
    return {
      exitCode: mapped.exitCode,
      pattern: request.pattern,
      error: mapped.error,
      retryable: mapped.retryable,
    };
  }
}
