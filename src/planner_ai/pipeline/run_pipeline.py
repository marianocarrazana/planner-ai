from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from pathlib import Path

from planner_ai.pipeline.types import (
    PipelineCallbacks,
    PipelineResult,
    ProposalState,
    RunMode,
)
from planner_ai.providers.types import (
    ConsensusProvider,
    ModelProvider,
    ProposalRef,
    ProviderCallOptions,
)
from planner_ai.write_run_archive import write_run_archive


async def run_pipeline(
    goal: str,
    proposers: list[ModelProvider],
    consensus: ConsensusProvider,
    callbacks: PipelineCallbacks,
    options: ProviderCallOptions | None = None,
    cwd: Path | None = None,
) -> PipelineResult:
    mode: RunMode = "plan"
    if options is not None and options.mode is not None:
        mode = options.mode

    call_options = ProviderCallOptions(
        cancel_event=options.cancel_event if options else None,
        timeout_ms=options.timeout_ms if options else None,
        mode=mode,
    )

    trimmed = goal.strip()
    if not trimmed:
        callbacks.on_phase("error")
        raise ValueError(
            "Question is required" if mode == "ask" else "Goal is required"
        )

    proposals: list[ProposalState] = [
        ProposalState(id=p.id, label=p.label, status="pending") for p in proposers
    ]

    def emit() -> None:
        callbacks.on_proposals([replace(p) for p in proposals])

    callbacks.on_phase("proposing")
    emit()

    streaming_started_at = int(time.time() * 1000)
    proposals = [
        replace(p, status="streaming", started_at=streaming_started_at)
        for p in proposals
    ]
    emit()

    async def run_one(provider: ModelProvider) -> tuple[str, str]:
        body = await provider.propose(trimmed, call_options)
        return provider.id, body

    settled = await asyncio.gather(
        *[run_one(p) for p in proposers],
        return_exceptions=True,
    )

    updated: list[ProposalState] = []
    for proposal, result in zip(proposals, settled, strict=True):
        if isinstance(result, BaseException):
            updated.append(
                replace(
                    proposal,
                    status="error",
                    error=str(result),
                    started_at=None,
                )
            )
        else:
            _id, body = result
            updated.append(
                replace(
                    proposal,
                    status="done",
                    body=body,
                    started_at=None,
                )
            )
    proposals = updated
    emit()

    successful: list[ProposalRef] = [
        {"id": p.id, "body": p.body}
        for p in proposals
        if p.status == "done" and p.body
    ]

    if len(successful) == 0:
        callbacks.on_phase("error")
        raise ValueError(
            "All answers failed" if mode == "ask" else "All proposals failed"
        )

    callbacks.on_phase("consensus")
    if callbacks.on_consensus_started is not None:
        callbacks.on_consensus_started(int(time.time() * 1000))
    plan = await consensus.reconcile(trimmed, successful, call_options)

    callbacks.on_phase("writing")
    archive_path = write_run_archive(
        kind=mode,
        plan=plan,
        proposals=proposals,
        cwd=cwd,
    )

    callbacks.on_phase("done")
    return PipelineResult(
        plan_path=None,
        archive_path=archive_path,
        plan=plan,
        mode=mode,
        proposals=proposals,
    )
