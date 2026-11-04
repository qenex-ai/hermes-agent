import {
  EXIT_CANCELLED,
  EXIT_OK,
  EXIT_RUN_ERROR,
  EXIT_STARTUP,
  type CursorAgentErrorLike,
  type InvocationResult,
  type RunResultLike,
  type SdkBindings,
} from "./types.ts";
import { PlanError } from "./options.ts";

export function mapRunStatus(result: RunResultLike): Pick<InvocationResult, "exitCode" | "status"> {
  if (result.status === "finished") {
    return { exitCode: EXIT_OK, status: "finished" };
  }
  if (result.status === "cancelled") {
    return { exitCode: EXIT_CANCELLED, status: "cancelled" };
  }
  return { exitCode: EXIT_RUN_ERROR, status: "error" };
}

export function mapThrownError(
  err: unknown,
  sdk: SdkBindings,
): Pick<InvocationResult, "exitCode" | "error" | "retryable"> {
  if (err instanceof PlanError) {
    return { exitCode: EXIT_STARTUP, error: err.message, retryable: false };
  }
  if (sdk.isCursorAgentError(err)) {
    const typed = err as CursorAgentErrorLike;
    return {
      exitCode: EXIT_STARTUP,
      error: typed.message,
      retryable: Boolean(typed.isRetryable),
    };
  }
  const message = err instanceof Error ? err.message : String(err);
  return { exitCode: EXIT_STARTUP, error: message, retryable: false };
}

/** Callers must not blindly retry; only `retryable === true` is safe. */
export function shouldRetry(result: InvocationResult): boolean {
  return result.exitCode === EXIT_STARTUP && result.retryable === true;
}
