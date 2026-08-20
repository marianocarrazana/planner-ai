from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from planner_ai.pipeline.types import ProposalState, RunMode
from planner_ai.workspace import get_workspace_cwd
from planner_ai.write_run_archive import (
    ANSWER_FILENAME,
    ARCHIVE_DIR,
    IMPROVEMENTS_FILENAME,
    OUTPUT_SUFFIX,
    PLAN_FILENAME,
    primary_doc_filename,
)

RUN_DIR_RE = re.compile(
    r"^(plan|ask|improve)-(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})(?:-(\d+))?$"
)

_CONSENSUS_FILENAMES = (
    PLAN_FILENAME,
    ANSWER_FILENAME,
    IMPROVEMENTS_FILENAME,
)


@dataclass(frozen=True)
class ArchivedRunSummary:
    id: str
    kind: RunMode
    dir_name: str
    path: Path
    sort_key: str
    timestamp_label: str
    output_count: int


@dataclass
class ArchivedRun:
    path: Path
    kind: RunMode
    plan: str
    proposals: list[ProposalState]


def _parse_run_dir(
    dir_name: str,
) -> tuple[RunMode, str, str | None] | None:
    match = RUN_DIR_RE.match(dir_name)
    if match is None or match.group(1) is None or match.group(2) is None:
        return None
    kind: RunMode = match.group(1)  # type: ignore[assignment]
    return kind, match.group(2), match.group(3)


def _format_timestamp_label(dir_name: str) -> str:
    parsed = _parse_run_dir(dir_name)
    if parsed is None:
        return dir_name
    kind, timestamp, collision = parsed
    del kind
    date_part, _, time_part = timestamp.partition("T")
    label = f"{date_part} {time_part.replace('-', ':')}"
    return f"{label} ({collision})" if collision else label


def _sort_key_for(dir_name: str) -> str:
    parsed = _parse_run_dir(dir_name)
    if parsed is None:
        return dir_name
    _, timestamp, collision = parsed
    return f"{timestamp}-{collision}" if collision else timestamp


def _is_error_body(body: str) -> bool:
    return body.startswith("# Error\n")


def _proposal_from_output(filename: str, body: str) -> ProposalState:
    if filename.endswith(OUTPUT_SUFFIX):
        stem = filename[: -len(OUTPUT_SUFFIX)]
    else:
        stem = filename.removesuffix(".md")
    proposal_id = stem or "model"
    if _is_error_body(body):
        message = re.sub(r"^# Error\n\n?", "", body).strip() or body.strip()
        return ProposalState(
            id=proposal_id,
            label=proposal_id,
            status="error",
            error=message,
        )
    return ProposalState(
        id=proposal_id,
        label=proposal_id,
        status="done",
        body=body,
    )


def list_archived_runs(cwd: Path | None = None) -> list[ArchivedRunSummary]:
    cwd = cwd or get_workspace_cwd()
    archive_root = cwd / ARCHIVE_DIR
    try:
        entries = list(archive_root.iterdir())
    except FileNotFoundError:
        return []

    runs: list[ArchivedRunSummary] = []
    for entry in entries:
        if not entry.is_dir():
            continue
        parsed = _parse_run_dir(entry.name)
        if parsed is None:
            continue
        kind, _, _ = parsed
        output_count = 0
        try:
            output_count = sum(
                1 for f in entry.iterdir() if f.name.endswith(OUTPUT_SUFFIX)
            )
        except OSError:
            pass
        runs.append(
            ArchivedRunSummary(
                id=entry.name,
                kind=kind,
                dir_name=entry.name,
                path=entry,
                sort_key=_sort_key_for(entry.name),
                timestamp_label=_format_timestamp_label(entry.name),
                output_count=output_count,
            )
        )

    runs.sort(key=lambda r: r.sort_key, reverse=True)
    return runs


def _read_primary_doc(run_dir: Path, kind: RunMode) -> str:
    preferred_name = primary_doc_filename(kind)
    preferred = run_dir / preferred_name
    try:
        return preferred.read_text(encoding="utf-8")
    except FileNotFoundError:
        pass

    for fallback_name in _CONSENSUS_FILENAMES:
        if fallback_name == preferred_name:
            continue
        try:
            return (run_dir / fallback_name).read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
    return ""


def read_archived_run(run_dir: Path | str) -> ArchivedRun:
    run_dir = Path(run_dir)
    dir_name = run_dir.name
    parsed = _parse_run_dir(dir_name)
    kind: RunMode = parsed[0] if parsed is not None else "plan"

    plan = _read_primary_doc(run_dir, kind)

    try:
        files = [f.name for f in run_dir.iterdir()]
    except FileNotFoundError as err:
        raise FileNotFoundError(f"Archived run not found: {run_dir}") from err

    output_files = sorted(f for f in files if f.endswith(OUTPUT_SUFFIX))

    proposals: list[ProposalState] = []
    for filename in output_files:
        try:
            body = (run_dir / filename).read_text(encoding="utf-8")
            proposals.append(_proposal_from_output(filename, body))
        except OSError:
            stem = filename[: -len(OUTPUT_SUFFIX)] or "model"
            proposals.append(
                ProposalState(
                    id=stem,
                    label=stem,
                    status="error",
                    error=f"Failed to read {filename}",
                )
            )

    return ArchivedRun(path=run_dir, kind=kind, plan=plan, proposals=proposals)
