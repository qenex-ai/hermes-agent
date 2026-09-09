import type { RunLike, SdkStreamEvent } from "./types.ts";

export interface StreamIo {
  writeOut: (text: string) => void;
  writeErr: (text: string) => void;
}

const defaultIo: StreamIo = {
  writeOut: (text) => process.stdout.write(text),
  writeErr: (text) => process.stderr.write(text),
};

export async function consumeStream(run: RunLike, io: StreamIo = defaultIo): Promise<void> {
  if (!run.supports("stream")) {
    const reason = run.unsupportedReason?.("stream");
    io.writeErr(`[cursor-sdk] stream not supported${reason ? `: ${reason}` : ""}\n`);
    return;
  }
  for await (const event of run.stream()) {
    renderEvent(event as SdkStreamEvent, io);
  }
}

export function renderEvent(event: SdkStreamEvent, io: StreamIo = defaultIo): void {
  switch (event.type) {
    case "assistant":
      for (const block of event.message.content) {
        if (block.type === "text" && block.text) io.writeOut(block.text);
      }
      return;
    case "thinking":
      io.writeErr(`[thinking] ${event.text}\n`);
      return;
    case "tool_call":
      io.writeErr(`[tool] ${event.name} ${event.status}\n`);
      return;
    case "status":
      io.writeErr(`[status] ${event.status}\n`);
      return;
    case "task":
      if (event.text) io.writeErr(`[task] ${event.text}\n`);
      return;
    default:
      return;
  }
}

export async function waitForRun(run: RunLike, io: StreamIo = defaultIo) {
  if (!run.supports("wait")) {
    const reason = run.unsupportedReason?.("wait");
    throw new Error(`wait() is required but not supported${reason ? `: ${reason}` : ""}`);
  }
  return run.wait();
}

export async function cancelIfSupported(run: RunLike, io: StreamIo = defaultIo): Promise<boolean> {
  if (!run.supports("cancel")) {
    const reason = run.unsupportedReason?.("cancel");
    io.writeErr(`[cursor-sdk] cancel not supported${reason ? `: ${reason}` : ""}\n`);
    return false;
  }
  await run.cancel();
  return true;
}
