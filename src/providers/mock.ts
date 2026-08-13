import { abortableSleep, createCallAbort } from "./callAbort.js";
import type {
  ConsensusProvider,
  ModelProvider,
  ProviderCallOptions,
} from "./types.js";

function createMockProposer(
  id: string,
  label: string,
  delayMs: number,
  angle: string,
): ModelProvider {
  return {
    id,
    label,
    async propose(goal: string, options?: ProviderCallOptions): Promise<string> {
      const abort = createCallAbort(options);
      try {
        abort.throwIfAborted();
        await abortableSleep(delayMs, abort.signal);
      } finally {
        abort.cleanup();
      }
      if (options?.mode === "ask") {
        return [
          `# Answer from ${label}`,
          "",
          `Question: ${goal}`,
          "",
          `## Take (${angle})`,
          "",
          `Based on a quick look at the workspace, here is a ${angle} answer to: ${goal}`,
          "",
          "Key points:",
          `- Ground the reply in the working directory (${angle})`,
          "- Prefer concrete references over speculation",
          "- Call out unknowns when the code is unclear",
          "",
        ].join("\n");
      }
      return [
        `# Proposal from ${label}`,
        "",
        `Goal: ${goal}`,
        "",
        `## Approach (${angle})`,
        "",
        `1. Clarify scope for: ${goal}`,
        `2. Break work into small steps (${angle})`,
        "3. Validate assumptions before implementation",
        "4. Ship an incremental first cut",
        "",
      ].join("\n");
    },
  };
}

export const mockProposers: ModelProvider[] = [
  createMockProposer("alpha", "Model Alpha", 400, "breadth-first"),
  createMockProposer("beta", "Model Beta", 700, "risk-first"),
  createMockProposer("gamma", "Model Gamma", 550, "mvp-first"),
];

export const mockConsensus: ConsensusProvider = {
  async reconcile(goal, proposals, options?: ProviderCallOptions) {
    const abort = createCallAbort(options);
    try {
      abort.throwIfAborted();
      await abortableSleep(500, abort.signal);
    } finally {
      abort.cleanup();
    }
    const sources = proposals.map((p) => `- ${p.id}`).join("\n");
    if (options?.mode === "ask") {
      return [
        `# Answer`,
        "",
        `## Question`,
        "",
        goal,
        "",
        "## Response",
        "",
        "Merged from the following answers:",
        sources,
        "",
        "The consensus answer is a concise synthesis of the proposer replies,",
        "grounded in the workspace and free of a planning template.",
        "",
        "This answer was produced by planner-ai consensus (mock).",
        "",
      ].join("\n");
    }
    return [
      `# Plan`,
      "",
      `## Goal`,
      "",
      goal,
      "",
      `## Consensus`,
      "",
      "Merged from the following proposals:",
      sources,
      "",
      "## Steps",
      "",
      "1. Clarify the goal and success criteria",
      "2. Identify highest-risk unknowns early",
      "3. Define a minimal first deliverable",
      "4. Implement and verify incrementally",
      "5. Document follow-ups for later execution",
      "",
      "## Notes",
      "",
      "This plan was produced by planner-ai consensus (mock).",
      "",
    ].join("\n");
  },
};
