from __future__ import annotations

from planner_ai.providers.prompts import (
    ASK_CONSENSUS_SYSTEM,
    ASK_PROPOSE_SYSTEM,
    CONSENSUS_SYSTEM,
    IMPROVE_CONSENSUS_SYSTEM,
    IMPROVE_PROPOSE_SYSTEM,
    PROPOSE_SYSTEM,
    ask_consensus_user_prompt,
    ask_propose_user_prompt,
    consensus_user_prompt,
    improve_consensus_user_prompt,
    improve_propose_user_prompt,
    propose_user_prompt,
    resolve_consensus_prompts,
    resolve_propose_prompts,
)


def test_propose_system_unchanged() -> None:
    assert PROPOSE_SYSTEM == (
        "You are a planning assistant. "
        "Inspect the given working directory with read-only tools, then return a concrete markdown plan grounded in that codebase. "
        "Do not use any other workspace, home-directory project, or editor context. "
        "Include: approach, ordered steps, risks/unknowns, and a minimal first cut. "
        "Do not edit or write files. Do not include preamble or closing chatter — only the plan markdown."
    )


def test_consensus_system_unchanged() -> None:
    assert CONSENSUS_SYSTEM == (
        "You reconcile multiple planning proposals into one executable plan for the given working directory. "
        "Inspect that directory with read-only tools when you need to check the proposals against the code. "
        "Do not use any other workspace, home-directory project, or editor context. "
        "Prefer overlap across proposals; put leftover disagreements in Notes. "
        "Output only markdown with sections: Goal, Consensus, Steps, Notes. "
        "Do not edit or write files. No preamble or closing chatter."
    )


def test_ask_propose_system_unchanged() -> None:
    assert ASK_PROPOSE_SYSTEM == (
        "You are a codebase Q&A assistant. "
        "Inspect the given working directory with read-only tools, then answer the user's question grounded in that codebase. "
        "Do not use any other workspace, home-directory project, or editor context. "
        "Do not produce a plan or implementation roadmap unless the question explicitly asks for one. "
        "Do not edit or write files. Do not include preamble or closing chatter — only the answer markdown."
    )


def test_ask_consensus_system_unchanged() -> None:
    assert ASK_CONSENSUS_SYSTEM == (
        "You reconcile multiple answers to the same question into one clear response for the given working directory. "
        "Inspect that directory with read-only tools when you need to check answers against the code. "
        "Do not use any other workspace, home-directory project, or editor context. "
        "Prefer overlap across answers; note leftover disagreements briefly if needed. "
        "Output only the final answer markdown — not a plan with Goal/Consensus/Steps sections. "
        "Do not edit or write files. No preamble or closing chatter."
    )


def test_improve_propose_system_unchanged() -> None:
    assert IMPROVE_PROPOSE_SYSTEM == (
        "You are a senior advisor auditing a codebase for possible improvements. "
        "Inspect the given working directory with read-only tools. "
        "Do not use any other workspace, home-directory project, or editor context. "
        "Survey code quality, documentation, security, bugs, and fixes within the user's scope. "
        "Return a prioritized markdown list of possible improvements; for each item include brief evidence, impact, and effort. "
        "Interpret the scope yourself (for example last commits, commits in this branch, whole repo, or a custom focus) using your own tools. "
        "Do not implement changes. Do not edit or write files. "
        "Do not include preamble or closing chatter — only the improvements markdown."
    )


def test_improve_consensus_system_unchanged() -> None:
    assert IMPROVE_CONSENSUS_SYSTEM == (
        "You reconcile multiple improvement audits into one prioritized list for the given working directory. "
        "Inspect that directory with read-only tools when you need to check proposals against the code. "
        "Do not use any other workspace, home-directory project, or editor context. "
        "Prefer overlap across proposals; put leftover disagreements in Notes. "
        "Output only markdown suitable for improvements.md — a prioritized improvement list, not a plan with Goal/Consensus/Steps and not a Q&A answer. "
        "Do not edit or write files. No preamble or closing chatter."
    )


def test_propose_user_prompt_shape() -> None:
    assert propose_user_prompt("Ship it", "/tmp/ws") == (
        "Working directory:\n/tmp/ws\n"
        "\n"
        "Goal:\nShip it\n"
        "\n"
        "Inspect this directory, then write a markdown plan for the goal."
    )


def test_ask_propose_user_prompt_shape() -> None:
    assert ask_propose_user_prompt("What is X?", "/tmp/ws") == (
        "Working directory:\n/tmp/ws\n"
        "\n"
        "Question:\nWhat is X?\n"
        "\n"
        "Inspect this directory as needed, then answer the question in markdown."
    )


def test_improve_propose_user_prompt_shape() -> None:
    assert improve_propose_user_prompt("Last commits", "/tmp/ws") == (
        "Working directory:\n/tmp/ws\n"
        "\n"
        "Scope:\nLast commits\n"
        "\n"
        "Interpret this scope with your own tools, then propose a prioritized markdown list of possible improvements."
    )


def test_consensus_user_prompt_uses_proposal_heading() -> None:
    body = consensus_user_prompt(
        "Ship it",
        "/tmp/ws",
        [{"id": "alpha", "body": "  plan body  "}],
    )
    assert "### Proposal: alpha\n\nplan body" in body
    assert "### Answer:" not in body
    assert "Merge these into a single plan.md markdown document for this directory." in body


def test_ask_consensus_user_prompt_uses_answer_heading() -> None:
    body = ask_consensus_user_prompt(
        "What is X?",
        "/tmp/ws",
        [{"id": "beta", "body": "  answer body  "}],
    )
    assert "### Answer: beta\n\nanswer body" in body
    assert "### Proposal:" not in body
    assert "Merge these into a single markdown answer to the question." in body


def test_improve_consensus_user_prompt_uses_improvements_heading() -> None:
    body = improve_consensus_user_prompt(
        "Whole repo",
        "/tmp/ws",
        [{"id": "gamma", "body": "  findings  "}],
    )
    assert "### Improvements: gamma\n\nfindings" in body
    assert "### Proposal:" not in body
    assert "### Answer:" not in body
    assert (
        "Merge these into a single improvements.md markdown document for this directory."
        in body
    )


def test_resolve_propose_prompts_plan_ask_improve() -> None:
    plan = resolve_propose_prompts("plan", "g", "/cwd")
    ask = resolve_propose_prompts("ask", "g", "/cwd")
    improve = resolve_propose_prompts("improve", "g", "/cwd")
    default = resolve_propose_prompts(None, "g", "/cwd")

    assert plan.system == PROPOSE_SYSTEM
    assert ask.system == ASK_PROPOSE_SYSTEM
    assert improve.system == IMPROVE_PROPOSE_SYSTEM
    assert default.system == PROPOSE_SYSTEM
    assert "Goal:\ng" in plan.user
    assert "Question:\ng" in ask.user
    assert "Scope:\ng" in improve.user


def test_resolve_consensus_prompts_plan_ask_improve() -> None:
    proposals = [{"id": "a", "body": "x"}]
    plan = resolve_consensus_prompts("plan", "g", "/cwd", proposals)
    ask = resolve_consensus_prompts("ask", "g", "/cwd", proposals)
    improve = resolve_consensus_prompts("improve", "g", "/cwd", proposals)

    assert plan.system == CONSENSUS_SYSTEM
    assert ask.system == ASK_CONSENSUS_SYSTEM
    assert improve.system == IMPROVE_CONSENSUS_SYSTEM
    assert "### Proposal: a" in plan.user
    assert "### Answer: a" in ask.user
    assert "### Improvements: a" in improve.user
    assert "Scope:\ng" in improve.user
