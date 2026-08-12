import { Agent } from "@cursor/sdk";
import { getWorkspaceCwd } from "../workspace.js";
import {
  CONSENSUS_SYSTEM,
  PROPOSE_SYSTEM,
  consensusUserPrompt,
  proposeUserPrompt,
} from "./prompts.js";
import type { ConsensusProvider, ModelProvider } from "./types.js";

const READ_TOOLS = ["read", "grep", "glob", "ls", "semSearch"] as const;

async function runPrompt(
  apiKey: string,
  modelId: string,
  prompt: string,
): Promise<string> {
  const cwd = getWorkspaceCwd();
  const result = await Agent.prompt(prompt, {
    apiKey,
    model: { id: modelId },
    local: {
      cwd,
      settingSources: ["project"],
    },
    tools: [...READ_TOOLS],
  });

  if (result.status !== "finished") {
    const detail = result.error?.message ?? result.status;
    throw new Error(`Cursor agent failed: ${detail}`);
  }

  const text = result.result?.trim();
  if (!text) {
    throw new Error("Cursor returned empty text");
  }

  return text;
}

export function createCursorProposer(
  apiKey: string,
  modelId: string,
  label: string,
): ModelProvider {
  return {
    id: `cursor:${modelId}`,
    label,
    async propose(goal: string): Promise<string> {
      const cwd = getWorkspaceCwd();
      return runPrompt(
        apiKey,
        modelId,
        `${PROPOSE_SYSTEM}\n\n${proposeUserPrompt(goal, cwd)}`,
      );
    },
  };
}

export function createCursorConsensus(
  apiKey: string,
  modelId: string,
): ConsensusProvider {
  return {
    async reconcile(goal, proposals): Promise<string> {
      const cwd = getWorkspaceCwd();
      return runPrompt(
        apiKey,
        modelId,
        `${CONSENSUS_SYSTEM}\n\n${consensusUserPrompt(goal, cwd, proposals)}`,
      );
    },
  };
}
