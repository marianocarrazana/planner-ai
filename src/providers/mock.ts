import type { ConsensusProvider, ModelProvider } from "./types.js";

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function createMockProposer(
  id: string,
  label: string,
  delayMs: number,
  angle: string,
): ModelProvider {
  return {
    id,
    label,
    async propose(goal: string): Promise<string> {
      await sleep(delayMs);
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
  async reconcile(goal, proposals) {
    await sleep(500);
    const sources = proposals.map((p) => `- ${p.id}`).join("\n");
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
