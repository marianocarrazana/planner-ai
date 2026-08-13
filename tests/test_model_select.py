from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from planner_ai import config as config_mod
from planner_ai.app import PlannerApp
from planner_ai.config import load_config, save_config
from planner_ai.providers.models import MOCK_MODELS, ModelChoice, ModelSelection
from planner_ai.ui.model_select import (
    ModelSelect,
    build_display_rows,
    choice_matches_query,
    first_choice_row_index,
    next_choice_row_index,
    pick_key,
    snap_to_choice_row,
    toggle_proposer,
)
from textual.widgets import Button

@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config_mod, "get_config_dir", lambda: tmp_path)
    return tmp_path


MIXED_CHOICES: list[ModelChoice] = [
    {"provider": "anthropic", "modelId": "sonnet", "label": "Sonnet"},
    {"provider": "cursor", "modelId": "auto", "label": "Cursor Auto"},
    {"provider": "codex", "modelId": "gpt-5.2", "label": "GPT-5.2"},
    *MOCK_MODELS,
]


def test_pick_key() -> None:
    assert pick_key({"provider": "mock", "modelId": "alpha"}) == "mock:alpha"


def test_build_display_rows_groups_in_order() -> None:
    rows = build_display_rows(MIXED_CHOICES)
    headers = [r["label"] for r in rows if r["kind"] == "header"]
    assert headers == ["Claude", "Cursor", "Codex", "Mock"]
    choices = [r for r in rows if r["kind"] == "choice"]
    assert choices[0]["choice"]["provider"] == "anthropic"
    assert first_choice_row_index(rows) == 1  # after Claude header


def test_build_display_rows_skips_empty_groups() -> None:
    rows = build_display_rows(list(MOCK_MODELS))
    headers = [r["label"] for r in rows if r["kind"] == "header"]
    assert headers == ["Mock"]


def test_choice_matches_query_claude_source() -> None:
    choice: ModelChoice = {
        "provider": "anthropic",
        "modelId": "sonnet",
        "label": "Sonnet",
    }
    assert choice_matches_query(choice, "claude")
    assert choice_matches_query(choice, "SONNET")
    assert not choice_matches_query(choice, "cursor")


def test_toggle_proposer_add_remove_preserves_order() -> None:
    a = {"provider": "mock", "modelId": "alpha"}
    b = {"provider": "mock", "modelId": "beta"}
    c = {"provider": "mock", "modelId": "gamma"}
    proposers = [a, b]
    proposers = toggle_proposer(proposers, c)
    assert proposers == [a, b, c]
    proposers = toggle_proposer(proposers, a)
    assert proposers == [b, c]
    proposers = toggle_proposer(proposers, a)
    assert proposers == [b, c, a]


def test_next_and_snap_choice_rows() -> None:
    rows = build_display_rows(MIXED_CHOICES)
    first = first_choice_row_index(rows)
    assert rows[first]["kind"] == "choice"
    # From a header, snap forward to choice
    assert snap_to_choice_row(rows, 0) == first
    nxt = next_choice_row_index(rows, first, 1)
    assert nxt > first
    assert rows[nxt]["kind"] == "choice"
    # At last choice, next stays
    last = next_choice_row_index(rows, len(rows), -1)
    assert next_choice_row_index(rows, last, 1) == last


def _fake_choices_honoring_mocks(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_choices(creds, opts=None):
        include = opts is not None and opts.get("includeMocks") is True
        # Real cred present → mocks only if flagged; else always mocks
        has_real = bool(
            creds.get("claudeCodeOAuthToken")
            or creds.get("cursorApiKey")
            or creds.get("codexApiKey")
        )
        if has_real and not include:
            return [
                {
                    "provider": "cursor",
                    "modelId": "auto",
                    "label": "Cursor Auto",
                },
                {
                    "provider": "cursor",
                    "modelId": "composer-2.5",
                    "label": "Composer 2.5",
                },
            ]
        if has_real and include:
            return [
                {
                    "provider": "cursor",
                    "modelId": "auto",
                    "label": "Cursor Auto",
                },
                *MOCK_MODELS,
            ]
        return list(MOCK_MODELS)

    monkeypatch.setattr("planner_ai.app.available_choices", fake_choices)


def test_cannot_continue_with_zero_proposers(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_choices_honoring_mocks(monkeypatch)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+2")
            await pilot.pause()
            ms = app.query_one("#proposers", ModelSelect)
            ms.focus()
            # Clear all proposers via draft
            assert app.draft_selection is not None
            empty: ModelSelection = {
                "proposers": [],
                "consensus": app.draft_selection["consensus"],
            }
            app.on_draft_selection_change(empty)
            await pilot.pause()
            continue_button = ms.query_one("#ms-continue", Button)
            assert "select ≥1 proposer" in str(continue_button.label)
            await pilot.press("c")
            await pilot.pause()
            assert app.active_tab == "proposers"
            assert "modelSelection" not in load_config()

    asyncio.run(run())


def test_consensus_is_single_select(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_choices_honoring_mocks(monkeypatch)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+3")
            await pilot.pause()
            ms = app.query_one("#consensus", ModelSelect)
            ms.focus()
            assert app.draft_selection is not None
            # Activate second mock choice (row index after Mock header = 1)
            rows = ms._display_rows
            choice_indexes = [
                i for i, r in enumerate(rows) if r["kind"] == "choice"
            ]
            assert len(choice_indexes) >= 2
            first_i, second_i = choice_indexes[0], choice_indexes[1]
            ms.activate_choice(second_i)
            await pilot.pause()
            assert app.draft_selection["consensus"]["modelId"] == rows[second_i][
                "choice"
            ]["modelId"]
            ms.activate_choice(first_i)
            await pilot.pause()
            assert app.draft_selection["consensus"]["modelId"] == rows[first_i][
                "choice"
            ]["modelId"]
            # Still exactly one consensus pick (TypedDict field)
            assert isinstance(app.draft_selection["consensus"], dict)

    asyncio.run(run())


def test_filter_typing_m_does_not_toggle_mocks(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_choices_honoring_mocks(monkeypatch)
    # Start with a real cred so includeMocks matters
    monkeypatch.setattr(
        "planner_ai.app.load_config",
        lambda: {"cursorApiKey": "k"},
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+2")
            await pilot.pause()
            ms = app.query_one("#proposers", ModelSelect)
            ms.focus()
            assert load_config().get("includeMocks") is not True
            await pilot.press("slash")
            await pilot.pause()
            assert ms.filtering
            await pilot.press("m")
            await pilot.pause()
            assert "includeMocks" not in load_config()
            assert ms.filter_query == "m"
            await pilot.press("escape")
            await pilot.pause()
            # Esc clears query first
            assert ms.filter_query == ""
            await pilot.press("escape")
            await pilot.pause()
            assert not ms.filtering

    asyncio.run(run())


def test_m_toggles_include_mocks_and_stays(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_choices_honoring_mocks(monkeypatch)
    monkeypatch.setattr(
        "planner_ai.app.load_config",
        lambda: {"cursorApiKey": "k"},
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+2")
            await pilot.pause()
            ms = app.query_one("#proposers", ModelSelect)
            ms.focus()
            await pilot.press("m")
            for _ in range(30):
                if load_config().get("includeMocks") is True:
                    break
                await pilot.pause()
            assert load_config().get("includeMocks") is True
            assert app.active_tab == "proposers"
            # Mock header should appear
            assert any(
                r["kind"] == "header" and r["label"] == "Mock"
                for r in ms._display_rows
            )

    asyncio.run(run())


def test_continue_saves_and_goes_to_plan(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_choices_honoring_mocks(monkeypatch)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+2")
            await pilot.pause()
            ms = app.query_one("#proposers", ModelSelect)
            ms.focus()
            assert app.draft_selection is not None
            # Default selection from mocks is already valid
            await pilot.press("c")
            for _ in range(30):
                if app.active_tab == "plan" and app.providers is not None:
                    break
                await pilot.pause()
            assert app.active_tab == "plan"
            saved = load_config().get("modelSelection")
            assert saved is not None
            assert len(saved["proposers"]) > 0
            sources = str(app.query_one("#header-sources").render())
            assert sources.startswith("proposers:")
            assert "consensus:" in sources

    asyncio.run(run())


def test_restart_lands_on_plan_with_sources(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selection: ModelSelection = {
        "proposers": [
            {"provider": "mock", "modelId": "alpha"},
            {"provider": "mock", "modelId": "beta"},
        ],
        "consensus": {"provider": "mock", "modelId": "gamma"},
    }
    save_config(
        {
            "cursorApiKey": "dummy-key",
            "includeMocks": True,
            "modelSelection": selection,
        }
    )
    _fake_choices_honoring_mocks(monkeypatch)
    # load from disk via real load_config (tmp dir)

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.active_tab == "plan"
            assert app.providers is not None
            sources = str(app.query_one("#header-sources").render())
            assert "mock:alpha" in sources
            assert "mock:beta" in sources
            assert "mock:gamma" in sources

    asyncio.run(run())


def test_activate_choice_toggles_proposer(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_choices_honoring_mocks(monkeypatch)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+2")
            await pilot.pause()
            assert app.draft_selection is not None
            before = {pick_key(p) for p in app.draft_selection["proposers"]}
            ms = app.query_one("#proposers", ModelSelect)
            target_index = None
            target_choice = None
            for index, row in enumerate(ms._display_rows):
                if row["kind"] == "choice" and pick_key(row["choice"]) not in before:
                    target_index = index
                    target_choice = row["choice"]
                    break
            if target_index is None:
                target_index = first_choice_row_index(ms._display_rows)
                row = ms._display_rows[target_index]
                assert row["kind"] == "choice"
                target_choice = row["choice"]
            assert target_choice is not None
            key = pick_key(target_choice)
            ms.activate_choice(target_index)
            await pilot.pause()
            after = {pick_key(p) for p in app.draft_selection["proposers"]}
            if key in before:
                assert key not in after
            else:
                assert key in after

    asyncio.run(run())
