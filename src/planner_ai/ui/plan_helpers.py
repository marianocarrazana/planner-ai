from __future__ import annotations

from typing import Literal

from planner_ai.config import AppConfig
from planner_ai.pipeline.types import ProposalStatus, RunMode
from planner_ai.providers.resolve import ResolvedProviders, ResolvedSources

PlanGate = Literal["ready", "need-models", "need-auth"]


def has_any_real_credential(creds: AppConfig) -> bool:
    return bool(
        creds.get("claudeCodeOAuthToken")
        or creds.get("cursorApiKey")
        or creds.get("codexApiKey")
    )


def format_proposer_sources(sources: ResolvedSources | dict[str, object]) -> str:
    proposers_raw = sources.get("proposers", [])
    if isinstance(proposers_raw, list):
        proposers = " + ".join(str(p) for p in proposers_raw)
    else:
        proposers = ""
    return f"proposers: {proposers}"


def format_consensus_source(sources: ResolvedSources | dict[str, object]) -> str:
    consensus = sources.get("consensus", "")
    return f"consensus: {consensus}"


def format_sources(sources: ResolvedSources | dict[str, object]) -> str:
    return (
        f"{format_proposer_sources(sources)}\n{format_consensus_source(sources)}"
    )


def plan_gate(
    providers: ResolvedProviders | None,
    config: AppConfig,
) -> PlanGate:
    if providers is not None:
        return "ready"
    if not has_any_real_credential(config):
        return "need-auth"
    return "need-models"


def format_elapsed_seconds(seconds: int) -> str:
    return f"{seconds}s"


def status_label(
    status: ProposalStatus,
    elapsed_seconds: int | None = None,
) -> str:
    match status:
        case "pending":
            return "pending"
        case "streaming":
            if elapsed_seconds is not None:
                return f"working… {format_elapsed_seconds(elapsed_seconds)}"
            return "working…"
        case "done":
            return "done"
        case "error":
            return "error"


def status_color(status: ProposalStatus) -> str:
    match status:
        case "pending":
            return "#888888"
        case "streaming":
            return "yellow"
        case "done":
            return "green"
        case "error":
            return "red"


def consensus_title(*, writing: bool, mode: RunMode) -> str:
    if writing:
        return "Saving answer" if mode == "ask" else "Writing plan"
    return "Consensus"


def consensus_body(
    *,
    writing: bool,
    mode: RunMode,
    elapsed_seconds: int | None = None,
) -> str:
    is_ask = mode == "ask"
    if writing:
        return "Archiving answer…" if is_ask else "Saving plan.md…"
    base = (
        "Reconciling answers into one response…"
        if is_ask
        else "Reconciling proposals into one plan…"
    )
    if elapsed_seconds is not None:
        return f"{base} {format_elapsed_seconds(elapsed_seconds)}"
    return base


def error_hint(
    *,
    mode: RunMode,
    failing_labels: list[str],
) -> str:
    another = "ask another" if mode == "ask" else "plan another"
    if failing_labels:
        joined = " and ".join(failing_labels)
        return (
            f"Enter retry · Esc {another} · Press r to remove "
            f"{joined} and re-enter · q to quit"
        )
    return f"Enter retry · Esc {another} · q to quit"
