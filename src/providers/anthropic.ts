import { query } from "@anthropic-ai/claude-agent-sdk";
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

const READ_TOOLS = ["Read", "Glob", "Grep"] as const;

function claudeEnv(token: string): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...process.env };
  env.CLAUDE_CODE_OAUTH_TOKEN = token;
  // Prefer subscription OAuth over any ambient Console API key.
  delete env.ANTHROPIC_API_KEY;
  return env;
}

async function runClaude(
  token: string,
  modelId: string,
  system: string,
  prompt: string,
  options?: ProviderCallOptions,
): Promise<string> {
  const cwd = getWorkspaceCwd();
  let resultText: string | undefined;
  let errorDetail: string | undefined;
  const abort = createCallAbort(options);

  try {
    abort.throwIfAborted();

    for await (const message of query({
      prompt,
      options: {
        model: modelId,
        systemPrompt: system,
        cwd,
        settingSources: ["project"],
        tools: [...READ_TOOLS],
        allowedTools: [...READ_TOOLS],
        permissionMode: "dontAsk",
        maxTurns: 20,
        env: claudeEnv(token),
        abortController: abort.controller,
      },
    })) {
      if (message.type !== "result") continue;

      if (message.subtype === "success") {
        resultText = message.result?.trim();
      } else {
        errorDetail =
          "errors" in message && Array.isArray(message.errors)
            ? message.errors.join("; ")
            : message.subtype;
      }
    }
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
    throw new Error(
      err instanceof Error
        ? `Claude Agent SDK failed: ${err.message}`
        : `Claude Agent SDK failed: ${String(err)}`,
    );
  } finally {
    abort.cleanup();
  }

  if (resultText) {
    return resultText;
  }

  if (abort.signal.aborted) {
    const reason = abort.signal.reason;
    throw reason instanceof Error
      ? reason
      : new ProviderAbortError(
          typeof reason === "string" && reason.length > 0 ? reason : "Aborted",
        );
  }

  throw new Error(
    errorDetail
      ? `Claude Agent SDK failed: ${errorDetail}`
      : "Claude Agent SDK returned empty text",
  );
}

export function createAnthropicProposer(
  token: string,
  modelId: string,
  label: string,
): ModelProvider {
  return {
    id: `anthropic:${modelId}`,
    label,
    async propose(goal: string, options?: ProviderCallOptions): Promise<string> {
      const cwd = getWorkspaceCwd();
      const { system, user } = resolveProposePrompts(options?.mode, goal, cwd);
      return runClaude(token, modelId, system, user, options);
    },
  };
}

export function createAnthropicConsensus(
  token: string,
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
      return runClaude(token, modelId, system, user, options);
    },
  };
}
