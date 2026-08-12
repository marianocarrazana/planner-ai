import { query } from "@anthropic-ai/claude-agent-sdk";
import { getWorkspaceCwd } from "../workspace.js";
import {
  CONSENSUS_SYSTEM,
  PROPOSE_SYSTEM,
  consensusUserPrompt,
  proposeUserPrompt,
} from "./prompts.js";
import type { ConsensusProvider, ModelProvider } from "./types.js";

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
): Promise<string> {
  const cwd = getWorkspaceCwd();
  let resultText: string | undefined;
  let errorDetail: string | undefined;

  try {
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
    throw new Error(
      err instanceof Error
        ? `Claude Agent SDK failed: ${err.message}`
        : `Claude Agent SDK failed: ${String(err)}`,
    );
  }

  if (resultText) {
    return resultText;
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
    async propose(goal: string): Promise<string> {
      const cwd = getWorkspaceCwd();
      return runClaude(
        token,
        modelId,
        PROPOSE_SYSTEM,
        proposeUserPrompt(goal, cwd),
      );
    },
  };
}

export function createAnthropicConsensus(
  token: string,
  modelId: string,
): ConsensusProvider {
  return {
    async reconcile(goal, proposals): Promise<string> {
      const cwd = getWorkspaceCwd();
      return runClaude(
        token,
        modelId,
        CONSENSUS_SYSTEM,
        consensusUserPrompt(goal, cwd, proposals),
      );
    },
  };
}
