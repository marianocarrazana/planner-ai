from __future__ import annotations

import asyncio

import pytest

from planner_ai.providers import models as models_mod
from planner_ai.providers.models import (
    CODEX_FALLBACK_MODELS,
    CURSOR_FALLBACK_MODELS,
    MOCK_MODELS,
    available_choices,
    default_selection,
    find_choice_label,
    format_choice_label,
    load_anthropic_choices,
    load_codex_choices,
    load_cursor_choices,
    normalize_selection,
    resolve_initial_selection,
)


def test_load_codex_choices_is_static_fallback() -> None:
    choices = load_codex_choices()
    assert choices == [
        {"provider": "codex", "modelId": "gpt-5.6-sol", "label": "GPT-5.6 Sol"},
        {"provider": "codex", "modelId": "gpt-5.6-terra", "label": "GPT-5.6 Terra"},
        {"provider": "codex", "modelId": "gpt-5.6-luna", "label": "GPT-5.6 Luna"},
        {"provider": "codex", "modelId": "gpt-5.5", "label": "GPT-5.5"},
        {"provider": "codex", "modelId": "gpt-5.2", "label": "GPT-5.2"},
    ]
    choices.append(
        {"provider": "codex", "modelId": "extra", "label": "Extra"},
    )
    assert load_codex_choices() == CODEX_FALLBACK_MODELS


def test_format_and_find_choice_label() -> None:
    choice = {
        "provider": "anthropic",
        "modelId": "claude-sonnet",
        "label": "Sonnet",
    }
    assert format_choice_label(choice) == "Sonnet · claude · claude-sonnet"
    cursor = {"provider": "cursor", "modelId": "auto", "label": "Cursor Auto"}
    assert format_choice_label(cursor) == "Cursor Auto · cursor · auto"
    pick = {"provider": "cursor", "modelId": "auto"}
    assert find_choice_label([cursor], pick) == "Cursor Auto"
    assert find_choice_label([], pick) == "cursor:auto"


def test_available_choices_empty_creds_are_three_mocks() -> None:
    choices = asyncio.run(available_choices({}))
    assert choices == MOCK_MODELS
    assert [c["modelId"] for c in choices] == ["alpha", "beta", "gamma"]


def test_available_choices_whitespace_creds_are_empty() -> None:
    choices = asyncio.run(
        available_choices(
            {
                "claudeCodeOAuthToken": "  ",
                "cursorApiKey": "\n",
                "codexApiKey": "\t",
            }
        )
    )
    assert choices == MOCK_MODELS


def test_available_choices_cursor_key_omits_mocks_unless_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cursor_only = [
        {"provider": "cursor", "modelId": "composer-2.5", "label": "Composer 2.5"},
        {"provider": "cursor", "modelId": "auto", "label": "Cursor Auto"},
    ]

    async def fake_cursor(api_key: str) -> list[dict[str, str]]:
        assert api_key == "cursor-key"
        return cursor_only

    async def fail_anthropic(token: str) -> list[dict[str, str]]:
        raise AssertionError("anthropic should not be called")

    monkeypatch.setattr(models_mod, "load_cursor_choices", fake_cursor)
    monkeypatch.setattr(models_mod, "load_anthropic_choices", fail_anthropic)

    without_mocks = asyncio.run(available_choices({"cursorApiKey": "cursor-key"}))
    assert without_mocks == cursor_only
    assert all(c["provider"] == "cursor" for c in without_mocks)

    with_mocks = asyncio.run(
        available_choices(
            {"cursorApiKey": "cursor-key"},
            {"includeMocks": True},
        )
    )
    assert with_mocks == cursor_only + MOCK_MODELS


def test_available_choices_codex_key_adds_static_list() -> None:
    choices = asyncio.run(available_choices({"codexApiKey": "codex-key"}))
    assert choices == CODEX_FALLBACK_MODELS


def test_available_choices_cached_codex_session_adds_static_list() -> None:
    choices = asyncio.run(
        available_choices({}, {"codexAuthenticated": True})
    )
    assert choices == CODEX_FALLBACK_MODELS


def test_load_anthropic_choices_paginates_and_dedupes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_get(url: str, headers: dict[str, str]) -> object:
        calls.append((url, headers))
        if "after_id=" not in url:
            return {
                "data": [
                    {"id": "m1", "display_name": "One"},
                    {"id": "m1", "display_name": "Dup"},
                    {"id": "  "},
                    None,
                ],
                "has_more": True,
                "last_id": "m1",
            }
        return {
            "data": [{"id": "m2"}],
            "has_more": False,
            "last_id": "m2",
        }

    monkeypatch.setattr(models_mod, "_http_get_json", fake_get)
    listed = asyncio.run(load_anthropic_choices("oauth-token"))
    assert listed == [
        {"provider": "anthropic", "modelId": "m1", "label": "One"},
        {"provider": "anthropic", "modelId": "m2", "label": "m2"},
    ]
    assert "limit=1000" in calls[0][0]
    assert "after_id=m1" in calls[1][0]
    assert calls[0][1] == {
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "oauth-2025-04-20",
        "Authorization": "Bearer oauth-token",
    }


def test_load_anthropic_choices_http_failure_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(url: str, headers: dict[str, str]) -> object:
        raise OSError("HTTP 401")

    monkeypatch.setattr(models_mod, "_http_get_json", boom)
    assert asyncio.run(load_anthropic_choices("bad")) == []


def test_load_cursor_choices_merges_missing_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Model:
        def __init__(self, model_id: str, display_name: str) -> None:
            self.id = model_id
            self.display_name = display_name

    def fake_list(api_key: str) -> list[Model]:
        assert api_key == "k"
        return [Model("  other  ", "Other Model")]

    monkeypatch.setattr(models_mod, "_list_cursor_models", fake_list)
    listed = asyncio.run(load_cursor_choices("k"))
    assert listed[0] == {
        "provider": "cursor",
        "modelId": "other",
        "label": "Other Model",
    }
    assert listed[1:] == CURSOR_FALLBACK_MODELS


def test_load_cursor_choices_error_or_empty_returns_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def empty(api_key: str) -> list[object]:
        return []

    monkeypatch.setattr(models_mod, "_list_cursor_models", empty)
    assert asyncio.run(load_cursor_choices("k")) == CURSOR_FALLBACK_MODELS

    def boom(api_key: str) -> list[object]:
        raise RuntimeError("network")

    monkeypatch.setattr(models_mod, "_list_cursor_models", boom)
    assert asyncio.run(load_cursor_choices("k")) == CURSOR_FALLBACK_MODELS


def test_default_selection_one_per_real_provider() -> None:
    choices = [
        {"provider": "mock", "modelId": "alpha", "label": "A"},
        {"provider": "codex", "modelId": "gpt-5.2", "label": "C"},
        {"provider": "cursor", "modelId": "auto", "label": "U"},
        {"provider": "anthropic", "modelId": "sonnet", "label": "S"},
        {"provider": "anthropic", "modelId": "opus", "label": "O"},
    ]
    assert default_selection(choices) == {
        "proposers": [
            {"provider": "anthropic", "modelId": "sonnet"},
            {"provider": "cursor", "modelId": "auto"},
            {"provider": "codex", "modelId": "gpt-5.2"},
        ],
        "consensus": {"provider": "anthropic", "modelId": "sonnet"},
    }


def test_default_selection_mocks_when_no_real() -> None:
    assert default_selection(MOCK_MODELS) == {
        "proposers": [
            {"provider": "mock", "modelId": "alpha"},
            {"provider": "mock", "modelId": "beta"},
        ],
        "consensus": {"provider": "mock", "modelId": "alpha"},
    }
    assert default_selection([]) is None


def test_normalize_selection_rejects_invalid_and_unknown() -> None:
    choices = MOCK_MODELS
    assert normalize_selection(None, choices) is None
    assert normalize_selection("nope", choices) is None
    assert (
        normalize_selection(
            {"consensus": {"provider": "mock", "modelId": "alpha"}},
            choices,
        )
        is None
    )
    assert (
        normalize_selection(
            {
                "proposers": [{"provider": "cursor", "modelId": "auto"}],
                "consensus": {"provider": "mock", "modelId": "alpha"},
            },
            choices,
        )
        is None
    )
    assert (
        normalize_selection(
            {
                "proposers": [{"provider": "mock", "modelId": "alpha"}],
                "consensus": {"provider": "cursor", "modelId": "auto"},
            },
            choices,
        )
        is None
    )
    assert (
        normalize_selection(
            {
                "proposers": [],
                "consensus": {"provider": "mock", "modelId": "alpha"},
            },
            choices,
        )
        is None
    )


def test_normalize_selection_keeps_valid_unique_picks() -> None:
    raw = {
        "proposers": [
            {"provider": "mock", "modelId": "  alpha  "},
            {"provider": "mock", "modelId": "alpha"},
            {"provider": "nope", "modelId": "x"},
            {"provider": "mock", "modelId": "gamma"},
        ],
        "consensus": {"provider": "mock", "modelId": "beta"},
    }
    assert normalize_selection(raw, MOCK_MODELS) == {
        "proposers": [
            {"provider": "mock", "modelId": "alpha"},
            {"provider": "mock", "modelId": "gamma"},
        ],
        "consensus": {"provider": "mock", "modelId": "beta"},
    }


def test_resolve_initial_selection_falls_back() -> None:
    saved = {
        "proposers": [{"provider": "cursor", "modelId": "missing"}],
        "consensus": {"provider": "mock", "modelId": "alpha"},
    }
    assert resolve_initial_selection(saved, MOCK_MODELS) == default_selection(
        MOCK_MODELS
    )
    assert resolve_initial_selection(None, []) == {
        "proposers": [{"provider": "mock", "modelId": "alpha"}],
        "consensus": {"provider": "mock", "modelId": "alpha"},
    }
    valid = {
        "proposers": [{"provider": "mock", "modelId": "gamma"}],
        "consensus": {"provider": "mock", "modelId": "beta"},
    }
    assert resolve_initial_selection(valid, MOCK_MODELS) == valid
