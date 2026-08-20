from __future__ import annotations

from datetime import datetime
from pathlib import Path

from planner_ai.pipeline.types import ProposalState
from planner_ai.write_run_archive import (
    ARCHIVE_DIR,
    PLAN_FILENAME,
    sanitize_model_id,
    write_run_archive,
)

FIXED = datetime(2026, 8, 13, 16, 48, 0)


def _done(proposal_id: str, body: str = "# Ok\n") -> ProposalState:
    return ProposalState(id=proposal_id, label=proposal_id, status="done", body=body)


def _error(proposal_id: str, error: str | None) -> ProposalState:
    return ProposalState(
        id=proposal_id, label=proposal_id, status="error", error=error
    )


def test_sanitize_model_id() -> None:
    assert sanitize_model_id("anthropic:claude-sonnet-4-5") == (
        "anthropic-claude-sonnet-4-5"
    )
    assert sanitize_model_id("!!!") == "model"
    assert sanitize_model_id("a..b_c-d") == "a..b_c-d"


def test_write_plan_archive(tmp_path: Path) -> None:
    proposals = [
        _done("anthropic:claude-sonnet-4-5", "# Proposal\n"),
        _done("cursor:composer-2.5", "# Other\n"),
    ]
    run_dir = write_run_archive(
        kind="plan",
        plan="# Consensus plan\n",
        proposals=proposals,
        cwd=tmp_path,
        date=FIXED,
    )
    assert run_dir == tmp_path / ARCHIVE_DIR / "plan-2026-08-13T16-48-00"
    assert (run_dir / "plan.md").read_text(encoding="utf-8") == "# Consensus plan\n"
    assert (run_dir / "anthropic-claude-sonnet-4-5-output.md").read_text(
        encoding="utf-8"
    ) == "# Proposal\n"
    assert (run_dir / "cursor-composer-2.5-output.md").exists()


def test_write_ask_archive_no_cwd_plan(tmp_path: Path) -> None:
    run_dir = write_run_archive(
        kind="ask",
        plan="# Answer\n",
        proposals=[_done("alpha")],
        cwd=tmp_path,
        date=FIXED,
    )
    assert run_dir.name.startswith("ask-")
    assert (run_dir / "answer.md").read_text(encoding="utf-8") == "# Answer\n"
    assert not (run_dir / "plan.md").exists()
    assert not (tmp_path / PLAN_FILENAME).exists()


def test_write_improve_archive(tmp_path: Path) -> None:
    run_dir = write_run_archive(
        kind="improve",
        plan="# Improvements\n",
        proposals=[_done("alpha")],
        cwd=tmp_path,
        date=FIXED,
    )
    assert run_dir.name.startswith("improve-")
    assert (
        run_dir / "improvements.md"
    ).read_text(encoding="utf-8") == "# Improvements\n"
    assert not (run_dir / "plan.md").exists()
    assert not (run_dir / "answer.md").exists()
    assert not (tmp_path / PLAN_FILENAME).exists()


def test_collision_suffix(tmp_path: Path) -> None:
    first = write_run_archive(
        kind="plan",
        plan="a",
        proposals=[_done("alpha")],
        cwd=tmp_path,
        date=FIXED,
    )
    second = write_run_archive(
        kind="plan",
        plan="b",
        proposals=[_done("alpha")],
        cwd=tmp_path,
        date=FIXED,
    )
    assert first.name == "plan-2026-08-13T16-48-00"
    assert second.name == "plan-2026-08-13T16-48-00-2"


def test_error_proposal_body(tmp_path: Path) -> None:
    run_dir = write_run_archive(
        kind="plan",
        plan="p",
        proposals=[_error("alpha", "boom")],
        cwd=tmp_path,
        date=FIXED,
    )
    body = (run_dir / "alpha-output.md").read_text(encoding="utf-8")
    assert body == "# Error\n\nboom\n"


def test_error_proposal_empty_message(tmp_path: Path) -> None:
    run_dir = write_run_archive(
        kind="plan",
        plan="p",
        proposals=[_error("alpha", None)],
        cwd=tmp_path,
        date=FIXED,
    )
    body = (run_dir / "alpha-output.md").read_text(encoding="utf-8")
    assert body == "# Error\n\nProposal failed with no error message\n"


def test_done_with_empty_body_treated_as_error(tmp_path: Path) -> None:
    proposal = ProposalState(id="alpha", label="Alpha", status="done", body="")
    run_dir = write_run_archive(
        kind="plan",
        plan="p",
        proposals=[proposal],
        cwd=tmp_path,
        date=FIXED,
    )
    body = (run_dir / "alpha-output.md").read_text(encoding="utf-8")
    assert body == "# Error\n\nProposal failed with no error message\n"
