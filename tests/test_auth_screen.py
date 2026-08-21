from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from planner_ai import config as config_mod
from planner_ai.app import PlannerApp
from planner_ai.config import load_config, save_config
from planner_ai.providers.models import MOCK_MODELS
from planner_ai.ui.auth_screen import AuthScreen
from planner_ai.ui.token_input import TokenInput
from textual.widgets import Input, Link, OptionList, Static

from planner_ai.providers.codex_auth import (
    CodexAuthStatus,
    CodexLoginDetails,
)


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config_mod, "get_config_dir", lambda: tmp_path)
    return tmp_path


def _mock_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_choices(_creds, _opts=None):
        return list(MOCK_MODELS)

    monkeypatch.setattr("planner_ai.app.available_choices", fake_choices)


def _visible_static_text(app: PlannerApp) -> str:
    parts: list[str] = []
    for widget in app.query(Static):
        parts.append(str(widget.render()))
    return "\n".join(parts)


def test_empty_config_shows_missing(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_choices(monkeypatch)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.active_tab == "auth"
            auth = app.query_one(AuthScreen)
            assert "Claude OAuth: missing" in str(
                auth.query_one("#status-claude").render()
            )
            assert "Cursor API key: missing" in str(
                auth.query_one("#status-cursor").render()
            )
            assert "Codex ChatGPT: missing" in str(
                auth.query_one("#status-codex").render()
            )
            # Clear actions are disabled; activating them is a no-op
            auth.highlight_action("clear-cursor")
            auth.activate_highlighted()
            await pilot.pause()
            assert load_config() == {}
            assert auth.mode == "overview"

    asyncio.run(run())


def test_set_cursor_key_and_restart(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_choices(monkeypatch)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})
    dummy = "cursor-dummy-key-xyz"

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            auth = app.query_one(AuthScreen)
            auth.query_one("#auth-actions", OptionList).focus()
            auth.highlight_action("edit-cursor")
            auth.activate_highlighted()
            await pilot.pause()
            assert auth.mode == "cursor"

            field = auth.query_one("#token-field", Input)
            field.focus()
            await pilot.press(*list(dummy))
            await pilot.press("enter")
            await pilot.pause()
            # Wait for worker save + reload
            for _ in range(20):
                if load_config().get("cursorApiKey") == dummy:
                    break
                await pilot.pause()

            assert load_config().get("cursorApiKey") == dummy
            assert auth.mode == "overview"
            assert app.active_tab == "auth"
            assert "Cursor API key: set" in str(
                auth.query_one("#status-cursor").render()
            )
            actions = auth.query_one("#auth-actions", OptionList)
            cursor_option = actions.get_option("edit-cursor")
            assert "Edit Cursor API key" in str(cursor_option.prompt)
            visible = _visible_static_text(app)
            assert dummy not in visible

    asyncio.run(run())

    # Restart: status shows set
    async def restart() -> None:
        # load_config reads from temp dir written above
        monkeypatch.setattr(
            "planner_ai.app.load_config",
            lambda: {"cursorApiKey": dummy},
        )
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            # Has a real cred but no valid modelSelection → proposers, or plan
            # Navigate to auth
            await pilot.press("ctrl+4")
            await pilot.pause()
            auth = app.query_one(AuthScreen)
            assert "Cursor API key: set" in str(
                auth.query_one("#status-cursor").render()
            )
            visible = _visible_static_text(app)
            assert dummy not in visible

    asyncio.run(restart())


def test_empty_enter_cancels_editor(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_choices(monkeypatch)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            auth = app.query_one(AuthScreen)
            auth.query_one("#auth-actions", OptionList).focus()
            auth.highlight_action("edit-claude")
            auth.activate_highlighted()
            await pilot.pause()
            assert auth.mode == "claude"
            await pilot.press("enter")  # empty submit
            await pilot.pause()
            assert auth.mode == "overview"
            assert load_config() == {}

    asyncio.run(run())


def test_clear_key_preserves_include_mocks(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_config({"cursorApiKey": "cursor-to-clear", "includeMocks": True})
    _mock_choices(monkeypatch)
    monkeypatch.setattr(
        "planner_ai.app.load_config",
        lambda: {
            "cursorApiKey": "cursor-to-clear",
            "includeMocks": True,
        },
    )

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+4")
            await pilot.pause()
            auth = app.query_one(AuthScreen)
            assert "Cursor API key: set" in str(
                auth.query_one("#status-cursor").render()
            )
            auth.query_one("#auth-actions", OptionList).focus()
            auth.highlight_action("clear-cursor")
            auth.activate_highlighted()
            for _ in range(20):
                if (
                    "cursorApiKey" not in load_config()
                    and "Cursor API key: missing"
                    in str(auth.query_one("#status-cursor").render())
                ):
                    break
                await pilot.pause()

            loaded = load_config()
            assert "cursorApiKey" not in loaded
            assert loaded.get("includeMocks") is True
            assert "Cursor API key: missing" in str(
                auth.query_one("#status-cursor").render()
            )
            assert app.active_tab == "auth"
            visible = _visible_static_text(app)
            assert "cursor-to-clear" not in visible

    asyncio.run(run())


def test_token_input_trims_and_masks(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_choices(monkeypatch)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})
    submitted: list[str] = []

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            auth = app.query_one(AuthScreen)
            token = auth.query_one(TokenInput)
            token.configure("Test", "hint", submitted.append)
            field = token.query_one("#token-field", Input)
            assert field.password is True
            field.value = "  ab cd  "
            await field.action_submit()
            await pilot.pause()
            assert submitted == ["ab cd"]

    asyncio.run(run())


def test_device_code_login_shows_url_and_code_and_cancels(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_choices(monkeypatch)
    monkeypatch.setattr("planner_ai.app.load_config", lambda: {})
    started = asyncio.Event()
    cancelled: list[bool] = []

    async def fake_login(method, on_ready):
        assert method == "device"
        on_ready(
            CodexLoginDetails(
                method="device",
                url="https://example.test/device",
                user_code="ABCD-EFGH",
            )
        )
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.append(True)

    monkeypatch.setattr("planner_ai.app.login_codex_chatgpt", fake_login)

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            auth = app.query_one(AuthScreen)
            auth.highlight_action("login-codex-device")
            auth.activate_highlighted()
            await started.wait()
            await pilot.pause()

            assert auth.mode == "codex-login"
            assert auth.query_one("#codex-login-url", Link).url == (
                "https://example.test/device"
            )
            assert "ABCD-EFGH" in str(
                auth.query_one("#codex-login-code", Static).render()
            )

            await pilot.click("#codex-login-cancel")
            await pilot.pause()
            assert auth.mode == "overview"
            assert cancelled == [True]

    asyncio.run(run())


def test_browser_login_success_clears_api_key(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_config({"codexApiKey": "api-key"})
    _mock_choices(monkeypatch)
    monkeypatch.setattr(
        "planner_ai.app.load_config",
        lambda: {"codexApiKey": "api-key"},
    )
    connected = CodexAuthStatus(
        authenticated=True,
        method="chatgpt",
        plan="plus",
    )

    async def fake_login(method, on_ready):
        assert method == "browser"
        on_ready(
            CodexLoginDetails(
                method="browser",
                url="https://example.test/browser",
            )
        )
        return connected

    async def read_connected() -> CodexAuthStatus:
        return connected

    monkeypatch.setattr("planner_ai.app.login_codex_chatgpt", fake_login)
    monkeypatch.setattr("planner_ai.app.read_codex_auth_status", read_connected)

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            auth = app.query_one(AuthScreen)
            auth.highlight_action("login-codex-browser")
            auth.activate_highlighted()
            for _ in range(20):
                if auth.mode == "overview" and "codexApiKey" not in load_config():
                    break
                await pilot.pause()

            assert "codexApiKey" not in load_config()
            assert "Codex ChatGPT (Plus): set" in str(
                auth.query_one("#status-codex", Static).render()
            )

    asyncio.run(run())


def test_codex_login_error_keeps_existing_api_key(
    config_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_config({"codexApiKey": "keep-key"})
    _mock_choices(monkeypatch)
    monkeypatch.setattr(
        "planner_ai.app.load_config",
        lambda: {"codexApiKey": "keep-key"},
    )

    async def fail_login(_method, _on_ready):
        raise RuntimeError("Device login is unavailable")

    monkeypatch.setattr("planner_ai.app.login_codex_chatgpt", fail_login)

    async def run() -> None:
        app = PlannerApp()
        async with app.run_test() as pilot:
            await pilot.pause()
            auth = app.query_one(AuthScreen)
            auth.highlight_action("login-codex-device")
            auth.activate_highlighted()
            for _ in range(20):
                error = str(
                    auth.query_one("#codex-login-error", Static).render()
                )
                if "unavailable" in error:
                    break
                await pilot.pause()

            assert load_config().get("codexApiKey") == "keep-key"
            assert "Device login is unavailable" in str(
                auth.query_one("#codex-login-error", Static).render()
            )

    asyncio.run(run())
