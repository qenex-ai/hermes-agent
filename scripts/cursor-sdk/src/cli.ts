#!/usr/bin/env node
/**
 * Production entry: maps a JSON request onto @cursor/sdk.
 *
 * Prefer `hermes cursor-sdk …` (Python wrapper). Direct use:
 *   npx tsx src/cli.ts --request-json -  < request.json
 */
import { Agent, CursorAgentError } from "@cursor/sdk";
import { readFileSync } from "node:fs";
import { runInvocation } from "./invoke.ts";
import type { SdkBindings, SdkRequest } from "./types.ts";

function readRequest(): SdkRequest {
  const idx = process.argv.indexOf("--request-json");
  if (idx >= 0) {
    const path = process.argv[idx + 1];
    if (!path) {
      throw new Error("--request-json requires a path or '-' for stdin");
    }
    const raw = path === "-" ? readFileSync(0, "utf8") : readFileSync(path, "utf8");
    return JSON.parse(raw) as SdkRequest;
  }
  throw new Error("Pass --request-json <file|-> with a SdkRequest payload");
}

const sdk: SdkBindings = {
  prompt: (message, options) => Agent.prompt(message, options as never),
  create: (options) => Agent.create(options as never),
  resume: (agentId, options) => Agent.resume(agentId, options as never),
  get: (agentId, options) => Agent.get(agentId, options as never),
  getRun: (runId, options) => Agent.getRun(runId, options as never),
  list: (options) => Agent.list(options as never),
  isCursorAgentError: (err: unknown): err is CursorAgentError => err instanceof CursorAgentError,
};

async function main(): Promise<number> {
  let request: SdkRequest;
  try {
    request = readRequest();
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    process.stderr.write(`[cursor-sdk] ${message}\n`);
    return 1;
  }
  const outcome = await runInvocation(request, sdk);
  if (process.argv.includes("--json")) {
    process.stdout.write(`${JSON.stringify(outcome, null, 2)}\n`);
  } else if (outcome.result && outcome.pattern !== "send" && outcome.pattern !== "resume") {
    const text = outcome.result.endsWith("\n") ? outcome.result : `${outcome.result}\n`;
    process.stdout.write(text);
  } else if (outcome.error) {
    process.stderr.write(`[cursor-sdk] ${outcome.error}\n`);
  }
  if (outcome.retryable) {
    process.stderr.write("[cursor-sdk] error.isRetryable=true; not retrying (duplicate cloud runs).\n");
  }
  return outcome.exitCode;
}

main()
  .then((code) => {
    process.exit(code);
  })
  .catch((err) => {
    process.stderr.write(`[cursor-sdk] unexpected: ${err instanceof Error ? err.message : err}\n`);
    process.exit(1);
  });
