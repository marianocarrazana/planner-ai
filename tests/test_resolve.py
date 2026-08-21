from __future__ import annotations

import asyncio

import pytest

from planner_ai.providers.mock import mock_consensus
from planner_ai.providers.models import MOCK_MODELS
from planner_ai.providers.resolve import resolve_providers


def test_resolve_providers_mocks() -> None:
    selection = {
        "proposers": [
            {"provider": "mock", "modelId": "alpha"},
            {"provider": "mock", "modelId": "beta"},
        ],
        "consensus": {"provider": "mock", "modelId": "gamma"},
    }
    resolved = resolve_providers({}, selection, MOCK_MODELS)
    assert [p.id for p in resolved.proposers] == ["mock:alpha", "mock:beta"]
    assert [p.label for p in resolved.proposers] == [
        "Model Alpha (mock)",
        "Model Beta (mock)",
    ]
    assert resolved.consensus is mock_consensus
    assert resolved.sources == {
        "proposers": ["mock:alpha", "mock:beta"],
        "consensus": "mock:gamma",
    }

    body = asyncio.run(resolved.proposers[0].propose("Ship it"))
    assert body.startswith("# Proposal from Model Alpha\n")
    assert "Goal: Ship it" in body


def test_resolve_providers_unknown_mock() -> None:
    with pytest.raises(ValueError, match=r"Unknown mock proposer: delta"):
        resolve_providers(
            {},
            {
                "proposers": [{"provider": "mock", "modelId": "delta"}],
                "consensus": {"provider": "mock", "modelId": "alpha"},
            },
        )


def test_resolve_providers_requires_proposers() -> None:
    with pytest.raises(ValueError, match=r"Select at least one proposer model"):
        resolve_providers(
            {},
            {
                "proposers": [],
                "consensus": {"provider": "mock", "modelId": "alpha"},
            },
        )


def test_resolve_providers_requires_creds_before_real_factory() -> None:
    cursor_choice = {
        "provider": "cursor",
        "modelId": "auto",
        "label": "Cursor Auto",
    }
    with pytest.raises(
        ValueError,
        match=r"Selected Cursor model but Cursor API key is missing",
    ):
        resolve_providers(
            {},
            {
                "proposers": [{"provider": "cursor", "modelId": "auto"}],
                "consensus": {"provider": "mock", "modelId": "alpha"},
            },
            [cursor_choice],
        )
    with pytest.raises(
        ValueError,
        match=r"Selected Anthropic model but Claude OAuth token is missing",
    ):
        resolve_providers(
            {"cursorApiKey": "k"},
            {
                "proposers": [{"provider": "mock", "modelId": "alpha"}],
                "consensus": {"provider": "anthropic", "modelId": "sonnet"},
            },
        )
    with pytest.raises(
        ValueError,
        match=r"Selected Codex model but Codex authentication is missing",
    ):
        resolve_providers(
            {"codexApiKey": "  "},
            {
                "proposers": [{"provider": "codex", "modelId": "gpt-5.2"}],
                "consensus": {"provider": "mock", "modelId": "alpha"},
            },
        )


def test_resolve_providers_constructs_real_factories() -> None:
    choices = [
        {
            "provider": "anthropic",
            "modelId": "claude-sonnet",
            "label": "Sonnet",
        },
        {
            "provider": "cursor",
            "modelId": "composer-2.5",
            "label": "Composer 2.5",
        },
        {
            "provider": "codex",
            "modelId": "gpt-5.2",
            "label": "GPT-5.2",
        },
    ]
    resolved = resolve_providers(
        {
            "claudeCodeOAuthToken": "oauth",
            "cursorApiKey": "ckey",
            "codexApiKey": "xkey",
        },
        {
            "proposers": [
                {"provider": "anthropic", "modelId": "claude-sonnet"},
                {"provider": "cursor", "modelId": "composer-2.5"},
                {"provider": "codex", "modelId": "gpt-5.2"},
            ],
            "consensus": {"provider": "anthropic", "modelId": "claude-sonnet"},
        },
        choices,
    )
    assert [p.id for p in resolved.proposers] == [
        "anthropic:claude-sonnet",
        "cursor:composer-2.5",
        "codex:gpt-5.2",
    ]
    assert [p.label for p in resolved.proposers] == [
        "Sonnet",
        "Composer 2.5",
        "GPT-5.2",
    ]
    assert resolved.sources == {
        "proposers": [
            "anthropic:claude-sonnet",
            "cursor:composer-2.5",
            "codex:gpt-5.2",
        ],
        "consensus": "anthropic:claude-sonnet",
    }
    assert hasattr(resolved.consensus, "reconcile")


def test_resolve_providers_accepts_cached_codex_session() -> None:
    selection = {
        "proposers": [{"provider": "codex", "modelId": "gpt-5.2"}],
        "consensus": {"provider": "codex", "modelId": "gpt-5.2"},
    }
    resolved = resolve_providers(
        {},
        selection,
        codex_authenticated=True,
    )
    assert resolved.proposers[0].id == "codex:gpt-5.2"
