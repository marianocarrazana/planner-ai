from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from textual.widgets import Footer, Header

from planner_ai import config as config_mod
from planner_ai.app import (
    PlannerApp,
    credential_label,
    startup_tab,
)
from planner_ai.config import save_config
from planner_ai.providers.models import MOCK_MODELS
from planner_ai.ui.plan_helpers import format_sources, has_any_real_credential
from planner_ai.ui.tabs import AppTabs
from planner_ai.workspace import get_workspace_cwd


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config_mod, "get_config_dir", lambda: tmp_path)
    return tmp_path


def test_format_sources() -> None:
    assert (
        format_sources(
            {
                "proposers": ["mock:alpha", "mock:beta"],
                "consensus": "mock:gamma",
            }
        )
        == "proposers: mock:alpha + mock:beta\nconsensus: mock:gamma"
    )


def test_has_any_real_credential() -> None:
    assert not has_any_real_credential({})
    assert not has_any_real_credential({"includeMocks": True})
    assert has_any_real_credential({"cursorApiKey": "k"})


def test_credential_label() -> None:
    assert credential_label("claudeCodeOAuthToken") == "Claude OAuth token"
    assert credential_label("cursorApiKey") == "Cursor API key"
    assert credential_label("codexApiKey") == "Codex API key"


def test_startup_tab_auth_when_no_creds() -> None:
    assert startup_tab({}, MOCK_MODELS) == "auth"


def test_startup_tab_proposers_when_selection_invalid() -> None:
    creds = {
        "cursorApiKey": "k",
        "modelSelection": {
            "proposers": [{"provider": "anthropic", "modelId": "missing"}],
            "consensus": {"provider": "anthropic", "modelId": "missing"},
        },
    }
    assert startup_tab(creds, MOCK_MODELS) == "proposers"


def test_startup_tab_plan_when_selection_valid() -> None:
    creds = {
        "cursorApiKey": "k",
        "modelSelection": {
            "proposers": [{"provider": "mock", "modelId": "alpha"}],
            "consensus": {"provider": "mock", "modelId": "beta"},
        },
    }
    assert startup_tab(creds, MOCK_MODELS) == "plan"


def test_ctrl_tabs_and_click(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_choices(_creds, _opts=None):
        return list(MOCK_MODELS)

    monkeypatch.setattr("planner_ai.app.available_choices", fake_choices)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            # No real creds → startup tab is Auth
            assert app.active_tab == "auth"
            switcher = app.query_one("#tab-body")
            assert switcher.current == "auth"

            await pilot.press("ctrl+1")
            assert app.active_tab == "plan"
            assert switcher.current == "plan"

            await pilot.press("ctrl+2")
            assert app.active_tab == "proposers"

            await pilot.press("ctrl+3")
            assert app.active_tab == "consensus"

            await pilot.press("ctrl+5")
            assert app.active_tab == "history"

            await pilot.press("ctrl+4")
            assert app.active_tab == "auth"

            await pilot.click("#tab-plan")
            assert app.active_tab == "plan"
            assert app.query_one("#app-tabs", AppTabs).active == "tab-plan"

            assert app.query_one(Footer) is not None
            quit_keys = [
                key
                for key in app.query("FooterKey")
                if getattr(key, "description", None) == "Quit"
            ]
            assert len(quit_keys) == 1

            header = app.query_one(Header)
            assert header is not None
            assert app.title == "planner-ai"
            assert app.sub_title == str(get_workspace_cwd())
            assert "cwd:" not in app.sub_title
            assert "proposers:" not in app.sub_title
            assert "-hidden" in app.query_one("#loading-config").classes

    asyncio.run(run())


def test_ctrl_q_quits(config_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_choices(_creds, _opts=None):
        return list(MOCK_MODELS)

    monkeypatch.setattr("planner_ai.app.available_choices", fake_choices)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+q")
            await pilot.pause()
            assert not app.is_running

    asyncio.run(run())


def test_reload_models_prefer_auth(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_choices(_creds, _opts=None):
        return list(MOCK_MODELS)

    monkeypatch.setattr("planner_ai.app.available_choices", fake_choices)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            assert app.active_tab == "auth"
            await app.reload_models(
                {"includeMocks": True},
                "auth",
            )
            await pilot.pause()
            assert app.active_tab == "auth"
            assert app.draft_selection is not None
            # No saved selection → providers stay None
            assert app.providers is None

    asyncio.run(run())


def test_save_credential_stays_on_auth(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_choices(creds, _opts=None):
        # Still return mocks; real catalog not needed for shell
        return list(MOCK_MODELS)

    monkeypatch.setattr("planner_ai.app.available_choices", fake_choices)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await app.on_save_cursor("cursor-test-key")
            await pilot.pause()
            assert app.active_tab == "auth"
            loaded = config_mod.load_config()
            assert loaded.get("cursorApiKey") == "cursor-test-key"

    asyncio.run(run())


def test_clear_credentials_stays_on_auth(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_config({"cursorApiKey": "cursor-test-key"})

    async def fake_choices(_creds, _opts=None):
        return list(MOCK_MODELS)

    monkeypatch.setattr("planner_ai.app.available_choices", fake_choices)
    monkeypatch.setattr(
        "planner_ai.app.load_config",
        lambda: {"cursorApiKey": "cursor-test-key"},
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await app.on_clear_credentials(["cursorApiKey"])
            await pilot.pause()
            assert app.active_tab == "auth"
            assert "cursorApiKey" not in config_mod.load_config()

    asyncio.run(run())
