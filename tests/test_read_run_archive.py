from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from planner_ai.pipeline.types import ProposalState
from planner_ai.read_run_archive import list_archived_runs, read_archived_run
from planner_ai.write_run_archive import ARCHIVE_DIR, write_run_archive

FIXED = datetime(2026, 8, 13, 16, 48, 0)
LATER = datetime(2026, 8, 13, 16, 49, 0)


def _done(proposal_id: str, body: str = "# Ok\n") -> ProposalState:
    return ProposalState(id=proposal_id, label=proposal_id, status="done", body=body)


def _error(proposal_id: str, error: str) -> ProposalState:
    return ProposalState(
        id=proposal_id, label=proposal_id, status="error", error=error
    )


def test_list_missing_archive_root(tmp_path: Path) -> None:
    assert list_archived_runs(cwd=tmp_path) == []


def test_list_newest_first_and_collision(tmp_path: Path) -> None:
    write_run_archive(
        kind="plan",
        plan="old",
        proposals=[_done("a")],
        cwd=tmp_path,
        date=FIXED,
    )
    write_run_archive(
        kind="plan",
        plan="collision",
        proposals=[_done("a")],
        cwd=tmp_path,
        date=FIXED,
    )
    write_run_archive(
        kind="ask",
        plan="new",
        proposals=[_done("b")],
        cwd=tmp_path,
        date=LATER,
    )

    runs = list_archived_runs(cwd=tmp_path)
    assert [r.dir_name for r in runs] == [
        "ask-2026-08-13T16-49-00",
        "plan-2026-08-13T16-48-00-2",
        "plan-2026-08-13T16-48-00",
    ]
    assert runs[0].kind == "ask"
    assert runs[1].timestamp_label == "2026-08-13 16:48:00 (2)"
    assert runs[2].timestamp_label == "2026-08-13 16:48:00"
    assert runs[0].output_count == 1


def test_list_skips_junk(tmp_path: Path) -> None:
    root = tmp_path / ARCHIVE_DIR
    root.mkdir()
    (root / "notes.txt").write_text("x", encoding="utf-8")
    (root / "weird-dir").mkdir()
    (root / ".DS_Store").write_text("", encoding="utf-8")
    write_run_archive(
        kind="plan",
        plan="p",
        proposals=[_done("a")],
        cwd=tmp_path,
        date=FIXED,
    )
    runs = list_archived_runs(cwd=tmp_path)
    assert len(runs) == 1
    assert runs[0].dir_name == "plan-2026-08-13T16-48-00"


def test_typescript_shaped_fixture(tmp_path: Path) -> None:
    root = tmp_path / ARCHIVE_DIR
    plan_dir = root / "plan-2026-08-13T16-48-00"
    ask_dir = root / "ask-2026-08-13T16-49-00"
    plan_dir.mkdir(parents=True)
    ask_dir.mkdir(parents=True)

    (plan_dir / "anthropic-claude-sonnet-4-5-output.md").write_text(
        "# Proposal from Claude\n", encoding="utf-8"
    )
    (plan_dir / "plan.md").write_text("# Consensus plan\n", encoding="utf-8")
    (ask_dir / "cursor-composer-2.5-output.md").write_text(
        "# Answer from Cursor\n", encoding="utf-8"
    )
    (ask_dir / "answer.md").write_text("# Consensus answer\n", encoding="utf-8")

    runs = list_archived_runs(cwd=tmp_path)
    assert [r.dir_name for r in runs] == [
        "ask-2026-08-13T16-49-00",
        "plan-2026-08-13T16-48-00",
    ]

    ask = read_archived_run(ask_dir)
    assert ask.kind == "ask"
    assert ask.plan == "# Consensus answer\n"
    assert len(ask.proposals) == 1
    assert ask.proposals[0].id == "cursor-composer-2.5"
    assert ask.proposals[0].status == "done"
    assert ask.proposals[0].body == "# Answer from Cursor\n"

    plan = read_archived_run(plan_dir)
    assert plan.kind == "plan"
    assert plan.plan == "# Consensus plan\n"
    assert plan.proposals[0].id == "anthropic-claude-sonnet-4-5"
    assert plan.proposals[0].status == "done"


def test_read_fallback_ask_with_plan_md(tmp_path: Path) -> None:
    run_dir = tmp_path / ARCHIVE_DIR / "ask-2026-08-13T16-48-00"
    run_dir.mkdir(parents=True)
    (run_dir / "plan.md").write_text("legacy plan body", encoding="utf-8")

    archived = read_archived_run(run_dir)
    assert archived.kind == "ask"
    assert archived.plan == "legacy plan body"


def test_read_fallback_plan_with_answer_md(tmp_path: Path) -> None:
    run_dir = tmp_path / ARCHIVE_DIR / "plan-2026-08-13T16-48-00"
    run_dir.mkdir(parents=True)
    (run_dir / "answer.md").write_text("legacy answer body", encoding="utf-8")

    archived = read_archived_run(run_dir)
    assert archived.kind == "plan"
    assert archived.plan == "legacy answer body"


def test_read_both_primary_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / ARCHIVE_DIR / "plan-2026-08-13T16-48-00"
    run_dir.mkdir(parents=True)
    (run_dir / "alpha-output.md").write_text("# Ok\n", encoding="utf-8")

    archived = read_archived_run(run_dir)
    assert archived.plan == ""
    assert len(archived.proposals) == 1


def test_read_missing_run_dir(tmp_path: Path) -> None:
    missing = tmp_path / ARCHIVE_DIR / "plan-2026-08-13T16-48-00"
    with pytest.raises(FileNotFoundError, match="Archived run not found"):
        read_archived_run(missing)


def test_error_body_round_trip(tmp_path: Path) -> None:
    run_dir = write_run_archive(
        kind="plan",
        plan="p",
        proposals=[_error("alpha", "timeout")],
        cwd=tmp_path,
        date=FIXED,
    )
    archived = read_archived_run(run_dir)
    assert len(archived.proposals) == 1
    assert archived.proposals[0].status == "error"
    assert archived.proposals[0].error == "timeout"
