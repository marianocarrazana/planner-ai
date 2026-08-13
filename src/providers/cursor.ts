import { Agent } from "@cursor/sdk";
import { getWorkspaceCwd } from "../workspace.js";
import {
  createCallAbort,
  isAbortError,
  ProviderAbortError,
} from "./callAbort.js";
import {
  resolveConsensusPrompts,
  resolveProposePrompts,
} from "./prompts.js";
import type {
  ConsensusProvider,
  ModelProvider,
  ProviderCallOptions,
} from "./types.js";

const READ_TOOLS = ["read", "grep", "glob", "ls", "semSearch"] as const;

async function runPrompt(
  apiKey: string,
  modelId: string,
  prompt: string,
  options?: ProviderCallOptions,
): Promise<string> {
  const cwd = getWorkspaceCwd();
  const abort = createCallAbort(options);
  abort.throwIfAborted();

  await using agent = await Agent.create({
    apiKey,
    model: { id: modelId },
    local: {
      cwd,
      settingSources: ["project"],
    },
    tools: [...READ_TOOLS],
  });

  const run = await agent.send(prompt);

  const onAbort = () => {
    if (run.supports("cancel")) {
      void run.cancel();
    }
  };

  if (abort.signal.aborted) {
    onAbort();
  } else {
    abort.signal.addEventListener("abort", onAbort, { once: true });
  }

  try {
    const result = await run.wait();

    if (abort.signal.aborted || result.status === "cancelled") {
      const reason = abort.signal.reason;
      throw reason instanceof Error
        ? reason
        : new ProviderAbortError(
            typeof reason === "string" && reason.length > 0
              ? reason
              : "Aborted",
          );
    }

    if (result.status !== "finished") {
      const detail = result.error?.message ?? result.status;
      throw new Error(`Cursor agent failed: ${detail}`);
    }

    const text = result.result?.trim();
    if (!text) {
      throw new Error("Cursor returned empty text");
    }

    return text;
  } catch (err) {
    if (isAbortError(err) || abort.signal.aborted) {
      const reason = abort.signal.reason;
      throw reason instanceof Error
        ? reason
        : new ProviderAbortError(
            typeof reason === "string" && reason.length > 0
              ? reason
              : "Aborted",
          );
    }
    throw err;
  } finally {
    abort.signal.removeEventListener("abort", onAbort);
    abort.cleanup();
  }
}

export function createCursorProposer(
  apiKey: string,
  modelId: string,
  label: string,
): ModelProvider {
  return {
    id: `cursor:${modelId}`,
    label,
    async propose(goal: string, options?: ProviderCallOptions): Promise<string> {
      const cwd = getWorkspaceCwd();
      const { system, user } = resolveProposePrompts(options?.mode, goal, cwd);
      return runPrompt(apiKey, modelId, `${system}\n\n${user}`, options);
    },
  };
}

export function createCursorConsensus(
  apiKey: string,
  modelId: string,
): ConsensusProvider {
  return {
    async reconcile(goal, proposals, options?: ProviderCallOptions) {
      const cwd = getWorkspaceCwd();
      const { system, user } = resolveConsensusPrompts(
        options?.mode,
        goal,
        cwd,
        proposals,
      );
      return runPrompt(apiKey, modelId, `${system}\n\n${user}`, options);
    },
  };
}
