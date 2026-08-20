from __future__ import annotations

from dataclasses import dataclass

from planner_ai.providers.call_abort import abortable_sleep, create_call_abort
from planner_ai.providers.types import (
    ProposalRef,
    ProviderCallOptions,
)


@dataclass
class MockProposer:
    id: str
    label: str
    delay_ms: int
    angle: str

    async def propose(
        self,
        goal: str,
        options: ProviderCallOptions | None = None,
    ) -> str:
        abort = create_call_abort(options)
        try:
            abort.throw_if_aborted()
            await abortable_sleep(self.delay_ms, abort)
        finally:
            abort.cleanup()

        mode = options.mode if options is not None else None
        if mode == "ask":
            return "\n".join(
                [
                    f"# Answer from {self.label}",
                    "",
                    f"Question: {goal}",
                    "",
                    f"## Take ({self.angle})",
                    "",
                    f"Based on a quick look at the workspace, here is a {self.angle} answer to: {goal}",
                    "",
                    "Key points:",
                    f"- Ground the reply in the working directory ({self.angle})",
                    "- Prefer concrete references over speculation",
                    "- Call out unknowns when the code is unclear",
                    "",
                ]
            )
        if mode == "improve":
            return "\n".join(
                [
                    f"# Improvements from {self.label}",
                    "",
                    f"Scope: {goal}",
                    "",
                    f"## Findings ({self.angle})",
                    "",
                    f"1. Harden error handling around the scoped area ({self.angle})",
                    "2. Clarify docs where behavior is ambiguous",
                    "3. Review security-sensitive paths for missing checks",
                    "4. Add tests for the highest-risk edge cases",
                    "",
                ]
            )
        return "\n".join(
            [
                f"# Proposal from {self.label}",
                "",
                f"Goal: {goal}",
                "",
                f"## Approach ({self.angle})",
                "",
                f"1. Clarify scope for: {goal}",
                f"2. Break work into small steps ({self.angle})",
                "3. Validate assumptions before implementation",
                "4. Ship an incremental first cut",
                "",
            ]
        )


class MockConsensus:
    async def reconcile(
        self,
        goal: str,
        proposals: list[ProposalRef],
        options: ProviderCallOptions | None = None,
    ) -> str:
        abort = create_call_abort(options)
        try:
            abort.throw_if_aborted()
            await abortable_sleep(500, abort)
        finally:
            abort.cleanup()

        sources = "\n".join(f"- {p['id']}" for p in proposals)
        mode = options.mode if options is not None else None
        if mode == "ask":
            return "\n".join(
                [
                    "# Answer",
                    "",
                    "## Question",
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
                ]
            )
        if mode == "improve":
            return "\n".join(
                [
                    "# Improvements",
                    "",
                    "## Scope",
                    "",
                    goal,
                    "",
                    "## Prioritized list",
                    "",
                    "Merged from the following proposals:",
                    sources,
                    "",
                    "1. Fix the highest-confidence bugs in scope",
                    "2. Address security gaps with clear evidence",
                    "3. Improve docs where they mislead contributors",
                    "4. Reduce tech debt that blocks the above",
                    "",
                    "## Notes",
                    "",
                    "This improvements list was produced by planner-ai consensus (mock).",
                    "",
                ]
            )
        return "\n".join(
            [
                "# Plan",
                "",
                "## Goal",
                "",
                goal,
                "",
                "## Consensus",
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
            ]
        )


mock_proposers: list[MockProposer] = [
    MockProposer("alpha", "Model Alpha", 400, "breadth-first"),
    MockProposer("beta", "Model Beta", 700, "risk-first"),
    MockProposer("gamma", "Model Gamma", 550, "mvp-first"),
]

mock_consensus = MockConsensus()
