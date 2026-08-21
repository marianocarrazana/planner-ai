from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from planner_ai.providers.mock import MockProposer, mock_consensus, mock_proposers
from planner_ai.providers.models import (
    ModelChoice,
    ModelPick,
    ModelSelection,
    ProviderKind,
    find_choice_label,
)
from planner_ai.providers.types import (
    ConsensusProvider,
    ModelProvider,
    ProviderCallOptions,
)


class ProviderCredentials(TypedDict, total=False):
    claudeCodeOAuthToken: str
    cursorApiKey: str
    codexApiKey: str


class ResolvedSources(TypedDict):
    proposers: list[str]
    consensus: str


@dataclass
class ResolvedProviders:
    proposers: list[ModelProvider]
    consensus: ConsensusProvider
    sources: ResolvedSources


@dataclass
class _BoundMockProposer:
    id: str
    label: str
    _inner: MockProposer

    async def propose(
        self,
        goal: str,
        options: ProviderCallOptions | None = None,
    ) -> str:
        return await self._inner.propose(goal, options)


def _non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def _require_creds(
    provider: ProviderKind,
    creds: ProviderCredentials,
    *,
    codex_authenticated: bool,
) -> None:
    if provider == "anthropic" and not _non_empty(
        creds.get("claudeCodeOAuthToken")
    ):
        raise ValueError(
            "Selected Anthropic model but Claude OAuth token is missing"
        )
    if provider == "cursor" and not _non_empty(creds.get("cursorApiKey")):
        raise ValueError("Selected Cursor model but Cursor API key is missing")
    if (
        provider == "codex"
        and not codex_authenticated
        and not _non_empty(creds.get("codexApiKey"))
    ):
        raise ValueError("Selected Codex model but Codex authentication is missing")


def _create_proposer(
    pick: ModelPick,
    creds: ProviderCredentials,
    choices: list[ModelChoice],
    *,
    codex_authenticated: bool,
) -> ModelProvider:
    _require_creds(
        pick["provider"],
        creds,
        codex_authenticated=codex_authenticated,
    )
    label = find_choice_label(choices, pick)
    provider_id = f"{pick['provider']}:{pick['modelId']}"

    if pick["provider"] == "anthropic":
        from planner_ai.providers.anthropic import create_anthropic_proposer

        token = _non_empty(creds.get("claudeCodeOAuthToken"))
        assert token is not None
        return create_anthropic_proposer(token, pick["modelId"], label)

    if pick["provider"] == "cursor":
        from planner_ai.providers.cursor import create_cursor_proposer

        api_key = _non_empty(creds.get("cursorApiKey"))
        assert api_key is not None
        return create_cursor_proposer(api_key, pick["modelId"], label)

    if pick["provider"] == "codex":
        from planner_ai.providers.codex import create_codex_proposer

        api_key = _non_empty(creds.get("codexApiKey"))
        return create_codex_proposer(api_key, pick["modelId"], label)

    mock = next((p for p in mock_proposers if p.id == pick["modelId"]), None)
    if mock is None:
        raise ValueError(f"Unknown mock proposer: {pick['modelId']}")
    return _BoundMockProposer(id=provider_id, label=label, _inner=mock)


def _create_consensus(
    pick: ModelPick,
    creds: ProviderCredentials,
    *,
    codex_authenticated: bool,
) -> ConsensusProvider:
    _require_creds(
        pick["provider"],
        creds,
        codex_authenticated=codex_authenticated,
    )

    if pick["provider"] == "anthropic":
        from planner_ai.providers.anthropic import create_anthropic_consensus

        token = _non_empty(creds.get("claudeCodeOAuthToken"))
        assert token is not None
        return create_anthropic_consensus(token, pick["modelId"])

    if pick["provider"] == "cursor":
        from planner_ai.providers.cursor import create_cursor_consensus

        api_key = _non_empty(creds.get("cursorApiKey"))
        assert api_key is not None
        return create_cursor_consensus(api_key, pick["modelId"])

    if pick["provider"] == "codex":
        from planner_ai.providers.codex import create_codex_consensus

        api_key = _non_empty(creds.get("codexApiKey"))
        return create_codex_consensus(api_key, pick["modelId"])

    return mock_consensus


def resolve_providers(
    creds: ProviderCredentials | None,
    selection: ModelSelection,
    choices: list[ModelChoice] | None = None,
    *,
    codex_authenticated: bool = False,
) -> ResolvedProviders:
    if creds is None:
        creds = {}
    if choices is None:
        choices = []

    if len(selection["proposers"]) == 0:
        raise ValueError("Select at least one proposer model")

    proposers = [
        _create_proposer(
            pick,
            creds,
            choices,
            codex_authenticated=codex_authenticated,
        )
        for pick in selection["proposers"]
    ]
    consensus = _create_consensus(
        selection["consensus"],
        creds,
        codex_authenticated=codex_authenticated,
    )

    return ResolvedProviders(
        proposers=proposers,
        consensus=consensus,
        sources={
            "proposers": [
                f"{p['provider']}:{p['modelId']}" for p in selection["proposers"]
            ],
            "consensus": (
                f"{selection['consensus']['provider']}:"
                f"{selection['consensus']['modelId']}"
            ),
        },
    )
