import type { RunMode } from "../pipeline/types.js";

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

export const ASK_PROPOSE_SYSTEM = [
  "You are a codebase Q&A assistant.",
  "Inspect the given working directory with read-only tools, then answer the user's question grounded in that codebase.",
  "Do not use any other workspace, home-directory project, or editor context.",
  "Do not produce a plan or implementation roadmap unless the question explicitly asks for one.",
  "Do not edit or write files. Do not include preamble or closing chatter — only the answer markdown.",
].join(" ");

export function askProposeUserPrompt(question: string, cwd: string): string {
  return [
    `Working directory:\n${cwd}`,
    "",
    `Question:\n${question}`,
    "",
    "Inspect this directory as needed, then answer the question in markdown.",
  ].join("\n");
}

export const ASK_CONSENSUS_SYSTEM = [
  "You reconcile multiple answers to the same question into one clear response for the given working directory.",
  "Inspect that directory with read-only tools when you need to check answers against the code.",
  "Do not use any other workspace, home-directory project, or editor context.",
  "Prefer overlap across answers; note leftover disagreements briefly if needed.",
  "Output only the final answer markdown — not a plan with Goal/Consensus/Steps sections.",
  "Do not edit or write files. No preamble or closing chatter.",
].join(" ");

export function askConsensusUserPrompt(
  question: string,
  cwd: string,
  proposals: { id: string; body: string }[],
): string {
  const blocks = proposals
    .map((p) => `### Answer: ${p.id}\n\n${p.body.trim()}`)
    .join("\n\n");

  return [
    `Working directory:\n${cwd}`,
    "",
    `Question:\n${question}`,
    "",
    "Answers:",
    "",
    blocks,
    "",
    "Merge these into a single markdown answer to the question.",
  ].join("\n");
}

export function resolveProposePrompts(
  mode: RunMode | undefined,
  goal: string,
  cwd: string,
): { system: string; user: string } {
  if (mode === "ask") {
    return {
      system: ASK_PROPOSE_SYSTEM,
      user: askProposeUserPrompt(goal, cwd),
    };
  }
  return {
    system: PROPOSE_SYSTEM,
    user: proposeUserPrompt(goal, cwd),
  };
}

export function resolveConsensusPrompts(
  mode: RunMode | undefined,
  goal: string,
  cwd: string,
  proposals: { id: string; body: string }[],
): { system: string; user: string } {
  if (mode === "ask") {
    return {
      system: ASK_CONSENSUS_SYSTEM,
      user: askConsensusUserPrompt(goal, cwd, proposals),
    };
  }
  return {
    system: CONSENSUS_SYSTEM,
    user: consensusUserPrompt(goal, cwd, proposals),
  };
}
