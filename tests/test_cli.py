from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from planner_ai import config as config_mod
from planner_ai import cli
from planner_ai.config import load_config, save_config


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config_mod, "get_config_dir", lambda: tmp_path)
    return tmp_path


def test_reset_auth_clears_keys_and_skips_tui(
    config_home: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    save_config(
        {
            "claudeCodeOAuthToken": "claude-token",
            "cursorApiKey": "cursor-key",
            "codexApiKey": "codex-key",
            "includeMocks": True,
        }
    )
    assert load_config().get("claudeCodeOAuthToken") == "claude-token"

    run_mock = MagicMock()
    monkeypatch.setattr("planner_ai.app.PlannerApp.run", run_mock)
    monkeypatch.setattr(cli.sys, "argv", ["planner", "--reset-auth"])

    cli.main()

    out = capsys.readouterr().out
    expected_path = str(config_mod.get_config_path())
    assert f"Cleared credentials in {expected_path}" in out

    loaded = load_config()
    assert "claudeCodeOAuthToken" not in loaded
    assert "cursorApiKey" not in loaded
    assert "codexApiKey" not in loaded
    assert loaded.get("includeMocks") is True
    run_mock.assert_not_called()


def test_main_launches_app_without_reset_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_mock = MagicMock()

    class FakeApp:
        def run(self) -> None:
            run_mock()

    monkeypatch.setattr(cli.sys, "argv", ["planner"])
    monkeypatch.setattr("planner_ai.app.PlannerApp", FakeApp)

    cli.main()

    run_mock.assert_called_once()
