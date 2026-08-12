export const PROPOSE_SYSTEM = [
  "You are a planning assistant.",
  "Inspect the given working directory with read-only tools, then return a concrete markdown plan grounded in that codebase.",
  "Do not use any other workspace, home-directory project, or editor context.",
  "Include: approach, ordered steps, risks/unknowns, and a minimal first cut.",
  "Do not edit or write files. Do not include preamble or closing chatter — only the plan markdown.",
].join(" ");

export function proposeUserPrompt(goal: string, cwd: string): string {
  return [
    `Working directory:\n${cwd}`,
    "",
    `Goal:\n${goal}`,
    "",
    "Inspect this directory, then write a markdown plan for the goal.",
  ].join("\n");
}

export const CONSENSUS_SYSTEM = [
  "You reconcile multiple planning proposals into one executable plan for the given working directory.",
  "Inspect that directory with read-only tools when you need to check the proposals against the code.",
  "Do not use any other workspace, home-directory project, or editor context.",
  "Prefer overlap across proposals; put leftover disagreements in Notes.",
  "Output only markdown with sections: Goal, Consensus, Steps, Notes.",
  "Do not edit or write files. No preamble or closing chatter.",
].join(" ");

export function consensusUserPrompt(
  goal: string,
  cwd: string,
  proposals: { id: string; body: string }[],
): string {
  const blocks = proposals
    .map((p) => `### Proposal: ${p.id}\n\n${p.body.trim()}`)
    .join("\n\n");

  return [
    `Working directory:\n${cwd}`,
    "",
    `Goal:\n${goal}`,
    "",
    "Proposals:",
    "",
    blocks,
    "",
    "Merge these into a single plan.md markdown document for this directory.",
  ].join("\n");
}
