from planner_ai.pipeline.types import (
    Phase,
    PipelineCallbacks,
    PipelineResult,
    ProposalState,
    ProposalStatus,
    RunMode,
)

__all__ = [
    "Phase",
    "PipelineCallbacks",
    "PipelineResult",
    "ProposalState",
    "ProposalStatus",
    "RunMode",
    "run_pipeline",
]


def __getattr__(name: str):
    if name == "run_pipeline":
        from planner_ai.pipeline.run_pipeline import run_pipeline

        return run_pipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
