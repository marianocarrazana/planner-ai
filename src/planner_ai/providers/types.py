from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol, TypedDict

from planner_ai.pipeline.types import RunMode


class ProposalRef(TypedDict):
    id: str
    body: str


@dataclass
class ProviderCallOptions:
    cancel_event: asyncio.Event | None = None
    timeout_ms: int | None = None
    # Defaults to "plan" when omitted.
    mode: RunMode | None = None


class ModelProvider(Protocol):
    id: str
    label: str

    async def propose(
        self,
        goal: str,
        options: ProviderCallOptions | None = None,
    ) -> str: ...


class ConsensusProvider(Protocol):
    async def reconcile(
        self,
        goal: str,
        proposals: list[ProposalRef],
        options: ProviderCallOptions | None = None,
    ) -> str: ...
