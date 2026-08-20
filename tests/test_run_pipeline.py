from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from planner_ai.pipeline.run_pipeline import run_pipeline
from planner_ai.pipeline.types import Phase, PipelineCallbacks, ProposalState
from planner_ai.providers.mock import mock_consensus, mock_proposers
from planner_ai.providers.types import ProviderCallOptions
from planner_ai.write_run_archive import ARCHIVE_DIR, PLAN_FILENAME


@dataclass
class FailingProposer:
    id: str = "fail"
    label: str = "Failing Model"

    async def propose(
        self,
        goal: str,
        options: ProviderCallOptions | None = None,
    ) -> str:
        raise RuntimeError("mock propose failed")


@dataclass
class EmptyBodyProposer:
    id: str = "empty"
    label: str = "Empty Body"

    async def propose(
        self,
        goal: str,
        options: ProviderCallOptions | None = None,
    ) -> str:
        return ""


def _callbacks() -> tuple[PipelineCallbacks, list[Phase], list[list[ProposalState]]]:
    phases: list[Phase] = []
    proposal_snapshots: list[list[ProposalState]] = []

    def on_phase(phase: Phase) -> None:
        phases.append(phase)

    def on_proposals(proposals: list[ProposalState]) -> None:
        proposal_snapshots.append(proposals)

    return (
        PipelineCallbacks(on_phase=on_phase, on_proposals=on_proposals),
        phases,
        proposal_snapshots,
    )


def _alpha_beta() -> list:
    return [
        next(p for p in mock_proposers if p.id == "alpha"),
        next(p for p in mock_proposers if p.id == "beta"),
    ]


def test_plan_mode_writes_archive_only(tmp_path: Path) -> None:
    callbacks, phases, _ = _callbacks()

    async def run():
        return await run_pipeline(
            "Ship feature X",
            _alpha_beta(),
            mock_consensus,
            callbacks,
            cwd=tmp_path,
        )

    result = asyncio.run(run())

    assert result.mode == "plan"
    assert result.plan_path is None
    assert not (tmp_path / PLAN_FILENAME).exists()
    assert result.archive_path.parent == tmp_path / ARCHIVE_DIR
    assert result.archive_path.name.startswith("plan-")
    assert (result.archive_path / "plan.md").read_text(encoding="utf-8") == result.plan
    assert (result.archive_path / "alpha-output.md").exists()
    assert (result.archive_path / "beta-output.md").exists()
    assert phases == ["proposing", "consensus", "writing", "done"]
    assert all(p.status == "done" for p in result.proposals)


def test_ask_mode_no_cwd_plan(tmp_path: Path) -> None:
    callbacks, phases, _ = _callbacks()

    async def run():
        return await run_pipeline(
            "What does main do?",
            _alpha_beta(),
            mock_consensus,
            callbacks,
            options=ProviderCallOptions(mode="ask"),
            cwd=tmp_path,
        )

    result = asyncio.run(run())

    assert result.mode == "ask"
    assert result.plan_path is None
    assert not (tmp_path / PLAN_FILENAME).exists()
    assert result.archive_path.name.startswith("ask-")
    assert (result.archive_path / "answer.md").read_text(encoding="utf-8") == result.plan
    assert not (result.archive_path / "plan.md").exists()
    assert phases == ["proposing", "consensus", "writing", "done"]
    assert result.plan.startswith("# Answer\n")


def test_improve_mode_archives_improvements(tmp_path: Path) -> None:
    callbacks, phases, _ = _callbacks()

    async def run():
        return await run_pipeline(
            "Last commits",
            _alpha_beta(),
            mock_consensus,
            callbacks,
            options=ProviderCallOptions(mode="improve"),
            cwd=tmp_path,
        )

    result = asyncio.run(run())

    assert result.mode == "improve"
    assert result.plan_path is None
    assert not (tmp_path / PLAN_FILENAME).exists()
    assert result.archive_path.name.startswith("improve-")
    assert (
        result.archive_path / "improvements.md"
    ).read_text(encoding="utf-8") == result.plan
    assert not (result.archive_path / "plan.md").exists()
    assert not (result.archive_path / "answer.md").exists()
    assert phases == ["proposing", "consensus", "writing", "done"]
    assert result.plan.startswith("# Improvements\n")


def test_partial_failure_still_runs_consensus(tmp_path: Path) -> None:
    callbacks, _, _ = _callbacks()
    alpha = next(p for p in mock_proposers if p.id == "alpha")

    async def run():
        return await run_pipeline(
            "Partial ok",
            [alpha, FailingProposer()],
            mock_consensus,
            callbacks,
            cwd=tmp_path,
        )

    result = asyncio.run(run())

    by_id = {p.id: p for p in result.proposals}
    assert by_id["alpha"].status == "done"
    assert by_id["fail"].status == "error"
    assert by_id["fail"].error == "mock propose failed"
    assert "- alpha" in result.plan
    assert "- fail" not in result.plan
    fail_out = (result.archive_path / "fail-output.md").read_text(encoding="utf-8")
    assert fail_out.startswith("# Error\n")
    assert "mock propose failed" in fail_out


def test_empty_goal_plan_mode(tmp_path: Path) -> None:
    callbacks, phases, _ = _callbacks()

    async def run():
        await run_pipeline(
            "   ",
            _alpha_beta(),
            mock_consensus,
            callbacks,
            cwd=tmp_path,
        )

    with pytest.raises(ValueError, match=r"^Goal is required$"):
        asyncio.run(run())
    assert phases == ["error"]


def test_empty_goal_ask_mode(tmp_path: Path) -> None:
    callbacks, phases, _ = _callbacks()

    async def run():
        await run_pipeline(
            "",
            _alpha_beta(),
            mock_consensus,
            callbacks,
            options=ProviderCallOptions(mode="ask"),
            cwd=tmp_path,
        )

    with pytest.raises(ValueError, match=r"^Question is required$"):
        asyncio.run(run())
    assert phases == ["error"]


def test_empty_scope_improve_mode(tmp_path: Path) -> None:
    callbacks, phases, _ = _callbacks()

    async def run():
        await run_pipeline(
            "  ",
            _alpha_beta(),
            mock_consensus,
            callbacks,
            options=ProviderCallOptions(mode="improve"),
            cwd=tmp_path,
        )

    with pytest.raises(ValueError, match=r"^Scope is required$"):
        asyncio.run(run())
    assert phases == ["error"]


def test_all_proposals_failed(tmp_path: Path) -> None:
    callbacks, phases, _ = _callbacks()

    async def run():
        await run_pipeline(
            "nope",
            [FailingProposer(id="a"), FailingProposer(id="b")],
            mock_consensus,
            callbacks,
            cwd=tmp_path,
        )

    with pytest.raises(ValueError, match=r"^All proposals failed$"):
        asyncio.run(run())
    assert phases == ["proposing", "error"]


def test_all_answers_failed(tmp_path: Path) -> None:
    callbacks, phases, _ = _callbacks()

    async def run():
        await run_pipeline(
            "nope",
            [FailingProposer()],
            mock_consensus,
            callbacks,
            options=ProviderCallOptions(mode="ask"),
            cwd=tmp_path,
        )

    with pytest.raises(ValueError, match=r"^All answers failed$"):
        asyncio.run(run())
    assert phases == ["proposing", "error"]


def test_all_improvement_proposals_failed(tmp_path: Path) -> None:
    callbacks, phases, _ = _callbacks()

    async def run():
        await run_pipeline(
            "Whole repo",
            [FailingProposer()],
            mock_consensus,
            callbacks,
            options=ProviderCallOptions(mode="improve"),
            cwd=tmp_path,
        )

    with pytest.raises(ValueError, match=r"^All improvement proposals failed$"):
        asyncio.run(run())
    assert phases == ["proposing", "error"]


def test_empty_body_not_consensus_input(tmp_path: Path) -> None:
    callbacks, phases, _ = _callbacks()

    async def run():
        await run_pipeline(
            "empty",
            [EmptyBodyProposer()],
            mock_consensus,
            callbacks,
            cwd=tmp_path,
        )

    with pytest.raises(ValueError, match=r"^All proposals failed$"):
        asyncio.run(run())
    assert phases == ["proposing", "error"]


def test_shared_started_at_while_streaming(tmp_path: Path) -> None:
    callbacks, phases, snapshots = _callbacks()
    consensus_started: list[int] = []

    callbacks = PipelineCallbacks(
        on_phase=callbacks.on_phase,
        on_proposals=callbacks.on_proposals,
        on_consensus_started=lambda t: consensus_started.append(t),
    )

    async def run():
        return await run_pipeline(
            "timing",
            _alpha_beta(),
            mock_consensus,
            callbacks,
            cwd=tmp_path,
        )

    asyncio.run(run())

    assert phases == ["proposing", "consensus", "writing", "done"]
    assert len(snapshots) >= 2
    pending = snapshots[0]
    streaming = snapshots[1]
    assert all(p.status == "pending" for p in pending)
    assert all(p.status == "streaming" for p in streaming)
    assert streaming[0].started_at is not None
    assert streaming[0].started_at == streaming[1].started_at
    assert len(consensus_started) == 1
