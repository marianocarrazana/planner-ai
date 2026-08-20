from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RunMode = Literal["plan", "ask", "improve"]

Phase = Literal[
    "idle",
    "proposing",
    "consensus",
    "writing",
    "done",
    "error",
]

ProposalStatus = Literal["pending", "streaming", "done", "error"]


@dataclass
class ProposalState:
    id: str
    label: str
    status: ProposalStatus
    body: str | None = None
    error: str | None = None
    # Epoch ms when this proposer entered "streaming"; used for elapsed UI.
    started_at: int | None = None


@dataclass
class PipelineResult:
    # Always None; consensus is written only under .planner-ai/.
    plan_path: Path | None
    # Archive directory under .planner-ai/.
    archive_path: Path
    # Consensus markdown (plan, answer, or improvements).
    plan: str
    mode: RunMode
    proposals: list[ProposalState]


@dataclass
class PipelineCallbacks:
    on_phase: Callable[[Phase], None]
    on_proposals: Callable[[list[ProposalState]], None]
    on_consensus_started: Callable[[int], None] | None = None
