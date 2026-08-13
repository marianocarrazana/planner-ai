import { Codex } from "@openai/codex-sdk";
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

async function runPrompt(
  apiKey: string,
  modelId: string,
  prompt: string,
  options?: ProviderCallOptions,
): Promise<string> {
  const cwd = getWorkspaceCwd();
  const abort = createCallAbort(options);
  abort.throwIfAborted();

  try {
    const codex = new Codex({ apiKey });
    const thread = codex.startThread({
      model: modelId,
      workingDirectory: cwd,
      skipGitRepoCheck: true,
      sandboxMode: "read-only",
      approvalPolicy: "never",
    });

    const turn = await thread.run(prompt, { signal: abort.signal });
    const text = turn.finalResponse?.trim();
    if (!text) {
      throw new Error("Codex returned empty text");
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
    abort.cleanup();
  }
}

export function createCodexProposer(
  apiKey: string,
  modelId: string,
  label: string,
): ModelProvider {
  return {
    id: `codex:${modelId}`,
    label,
    async propose(goal: string, options?: ProviderCallOptions): Promise<string> {
      const cwd = getWorkspaceCwd();
      const { system, user } = resolveProposePrompts(options?.mode, goal, cwd);
      return runPrompt(apiKey, modelId, `${system}\n\n${user}`, options);
    },
  };
}

export function createCodexConsensus(
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
