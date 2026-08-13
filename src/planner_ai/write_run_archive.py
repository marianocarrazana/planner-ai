from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from planner_ai.pipeline.types import ProposalState, RunMode
from planner_ai.workspace import get_workspace_cwd

ARCHIVE_DIR = ".planner-ai"
PLAN_FILENAME = "plan.md"
ANSWER_FILENAME = "answer.md"
OUTPUT_SUFFIX = "-output.md"


def format_run_timestamp(when: datetime | None = None) -> str:
    when = when or datetime.now()
    return when.strftime("%Y-%m-%dT%H-%M-%S")


def sanitize_model_id(model_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", model_id)
    cleaned = re.sub(r"^-+|-+$", "", cleaned)
    return cleaned or "model"


def primary_doc_filename(kind: RunMode) -> str:
    return ANSWER_FILENAME if kind == "ask" else PLAN_FILENAME


def _allocate_run_dir(archive_root: Path, kind: RunMode, timestamp: str) -> Path:
    candidate = archive_root / f"{kind}-{timestamp}"
    if not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = archive_root / f"{kind}-{timestamp}-{n}"
        if not candidate.exists():
            return candidate
        n += 1


def _proposal_body(proposal: ProposalState) -> str:
    if proposal.status == "done" and proposal.body:
        return proposal.body
    message = (proposal.error or "").strip() or "Proposal failed with no error message"
    return f"# Error\n\n{message}\n"


def write_run_archive(
    *,
    kind: RunMode,
    plan: str,
    proposals: list[ProposalState],
    cwd: Path | None = None,
    date: datetime | None = None,
) -> Path:
    cwd = cwd or get_workspace_cwd()
    archive_root = cwd / ARCHIVE_DIR
    archive_root.mkdir(parents=True, exist_ok=True)

    run_dir = _allocate_run_dir(archive_root, kind, format_run_timestamp(date))
    run_dir.mkdir(parents=True, exist_ok=True)

    for proposal in proposals:
        filename = f"{sanitize_model_id(proposal.id)}{OUTPUT_SUFFIX}"
        (run_dir / filename).write_text(_proposal_body(proposal), encoding="utf-8")

    (run_dir / primary_doc_filename(kind)).write_text(plan, encoding="utf-8")
    return run_dir
