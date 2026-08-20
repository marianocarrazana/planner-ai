from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from planner_ai.pipeline.types import RunMode
from planner_ai.providers.types import ProposalRef

PROPOSE_SYSTEM = " ".join(
    [
        "You are a planning assistant.",
        "Inspect the given working directory with read-only tools, then return a concrete markdown plan grounded in that codebase.",
        "Do not use any other workspace, home-directory project, or editor context.",
        "Include: approach, ordered steps, risks/unknowns, and a minimal first cut.",
        "Do not edit or write files. Do not include preamble or closing chatter — only the plan markdown.",
    ]
)


def propose_user_prompt(goal: str, cwd: str) -> str:
    return "\n".join(
        [
            f"Working directory:\n{cwd}",
            "",
            f"Goal:\n{goal}",
            "",
            "Inspect this directory, then write a markdown plan for the goal.",
        ]
    )


CONSENSUS_SYSTEM = " ".join(
    [
        "You reconcile multiple planning proposals into one executable plan for the given working directory.",
        "Inspect that directory with read-only tools when you need to check the proposals against the code.",
        "Do not use any other workspace, home-directory project, or editor context.",
        "Prefer overlap across proposals; put leftover disagreements in Notes.",
        "Output only markdown with sections: Goal, Consensus, Steps, Notes.",
        "Do not edit or write files. No preamble or closing chatter.",
    ]
)


def consensus_user_prompt(
    goal: str,
    cwd: str,
    proposals: Sequence[ProposalRef],
) -> str:
    blocks = "\n\n".join(
        f"### Proposal: {p['id']}\n\n{p['body'].strip()}" for p in proposals
    )

    return "\n".join(
        [
            f"Working directory:\n{cwd}",
            "",
            f"Goal:\n{goal}",
            "",
            "Proposals:",
            "",
            blocks,
            "",
            "Merge these into a single plan.md markdown document for this directory.",
        ]
    )


ASK_PROPOSE_SYSTEM = " ".join(
    [
        "You are a codebase Q&A assistant.",
        "Inspect the given working directory with read-only tools, then answer the user's question grounded in that codebase.",
        "Do not use any other workspace, home-directory project, or editor context.",
        "Do not produce a plan or implementation roadmap unless the question explicitly asks for one.",
        "Do not edit or write files. Do not include preamble or closing chatter — only the answer markdown.",
    ]
)


def ask_propose_user_prompt(question: str, cwd: str) -> str:
    return "\n".join(
        [
            f"Working directory:\n{cwd}",
            "",
            f"Question:\n{question}",
            "",
            "Inspect this directory as needed, then answer the question in markdown.",
        ]
    )


ASK_CONSENSUS_SYSTEM = " ".join(
    [
        "You reconcile multiple answers to the same question into one clear response for the given working directory.",
        "Inspect that directory with read-only tools when you need to check answers against the code.",
        "Do not use any other workspace, home-directory project, or editor context.",
        "Prefer overlap across answers; note leftover disagreements briefly if needed.",
        "Output only the final answer markdown — not a plan with Goal/Consensus/Steps sections.",
        "Do not edit or write files. No preamble or closing chatter.",
    ]
)


def ask_consensus_user_prompt(
    question: str,
    cwd: str,
    proposals: Sequence[ProposalRef],
) -> str:
    blocks = "\n\n".join(
        f"### Answer: {p['id']}\n\n{p['body'].strip()}" for p in proposals
    )

    return "\n".join(
        [
            f"Working directory:\n{cwd}",
            "",
            f"Question:\n{question}",
            "",
            "Answers:",
            "",
            blocks,
            "",
            "Merge these into a single markdown answer to the question.",
        ]
    )


IMPROVE_PROPOSE_SYSTEM = " ".join(
    [
        "You are a senior advisor auditing a codebase for possible improvements.",
        "Inspect the given working directory with read-only tools.",
        "Do not use any other workspace, home-directory project, or editor context.",
        "Survey code quality, documentation, security, bugs, and fixes within the user's scope.",
        "Return a prioritized markdown list of possible improvements; for each item include brief evidence, impact, and effort.",
        "Interpret the scope yourself (for example last commits, commits in this branch, whole repo, or a custom focus) using your own tools.",
        "Do not implement changes. Do not edit or write files.",
        "Do not include preamble or closing chatter — only the improvements markdown.",
    ]
)


def improve_propose_user_prompt(scope: str, cwd: str) -> str:
    return "\n".join(
        [
            f"Working directory:\n{cwd}",
            "",
            f"Scope:\n{scope}",
            "",
            "Interpret this scope with your own tools, then propose a prioritized markdown list of possible improvements.",
        ]
    )


IMPROVE_CONSENSUS_SYSTEM = " ".join(
    [
        "You reconcile multiple improvement audits into one prioritized list for the given working directory.",
        "Inspect that directory with read-only tools when you need to check proposals against the code.",
        "Do not use any other workspace, home-directory project, or editor context.",
        "Prefer overlap across proposals; put leftover disagreements in Notes.",
        "Output only markdown suitable for improvements.md — a prioritized improvement list, not a plan with Goal/Consensus/Steps and not a Q&A answer.",
        "Do not edit or write files. No preamble or closing chatter.",
    ]
)


def improve_consensus_user_prompt(
    scope: str,
    cwd: str,
    proposals: Sequence[ProposalRef],
) -> str:
    blocks = "\n\n".join(
        f"### Improvements: {p['id']}\n\n{p['body'].strip()}" for p in proposals
    )

    return "\n".join(
        [
            f"Working directory:\n{cwd}",
            "",
            f"Scope:\n{scope}",
            "",
            "Proposals:",
            "",
            blocks,
            "",
            "Merge these into a single improvements.md markdown document for this directory.",
        ]
    )


@dataclass(frozen=True)
class ResolvedPrompts:
    system: str
    user: str


def resolve_propose_prompts(
    mode: RunMode | None,
    goal: str,
    cwd: str,
) -> ResolvedPrompts:
    if mode == "ask":
        return ResolvedPrompts(
            system=ASK_PROPOSE_SYSTEM,
            user=ask_propose_user_prompt(goal, cwd),
        )
    if mode == "improve":
        return ResolvedPrompts(
            system=IMPROVE_PROPOSE_SYSTEM,
            user=improve_propose_user_prompt(goal, cwd),
        )
    return ResolvedPrompts(
        system=PROPOSE_SYSTEM,
        user=propose_user_prompt(goal, cwd),
    )


def resolve_consensus_prompts(
    mode: RunMode | None,
    goal: str,
    cwd: str,
    proposals: Sequence[ProposalRef],
) -> ResolvedPrompts:
    if mode == "ask":
        return ResolvedPrompts(
            system=ASK_CONSENSUS_SYSTEM,
            user=ask_consensus_user_prompt(goal, cwd, proposals),
        )
    if mode == "improve":
        return ResolvedPrompts(
            system=IMPROVE_CONSENSUS_SYSTEM,
            user=improve_consensus_user_prompt(goal, cwd, proposals),
        )
    return ResolvedPrompts(
        system=CONSENSUS_SYSTEM,
        user=consensus_user_prompt(goal, cwd, proposals),
    )
