from __future__ import annotations

import json
import stat
import time
from pathlib import Path

import pytest

from planner_ai import config as config_mod
from planner_ai.config import (
    clear_credentials,
    get_config_dir,
    get_config_path,
    load_config,
    sanitize_token,
    save_config,
)


@pytest.fixture
def config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point config at a temp dir; never touch the real OS config."""
    monkeypatch.setattr(config_mod, "get_config_dir", lambda: tmp_path)
    return tmp_path


def test_sanitize_token_strips_all_whitespace() -> None:
    assert sanitize_token("  ab\ncd\tef  ") == "abcdef"
    assert sanitize_token("token") == "token"


def test_get_config_dir_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_mod.sys, "platform", "darwin")
    monkeypatch.setattr(
        config_mod.Path, "home", staticmethod(lambda: Path("/Users/test"))
    )
    assert get_config_dir() == Path(
        "/Users/test/Library/Application Support/planner-ai"
    )


def test_get_config_dir_linux_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_mod.sys, "platform", "linux")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(
        config_mod.Path, "home", staticmethod(lambda: Path("/home/test"))
    )
    assert get_config_dir() == Path("/home/test/.config/planner-ai")


def test_get_config_dir_linux_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_mod.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/xdg")
    assert get_config_dir() == Path("/custom/xdg/planner-ai")


def test_get_config_dir_linux_blank_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_mod.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "   ")
    monkeypatch.setattr(
        config_mod.Path, "home", staticmethod(lambda: Path("/home/test"))
    )
    assert get_config_dir() == Path("/home/test/.config/planner-ai")


def test_get_config_dir_win32_appdata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_mod.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\test\AppData\Roaming")
    # On non-Windows hosts Path keeps backslashes in the APPDATA segment.
    assert get_config_dir() == Path(r"C:\Users\test\AppData\Roaming") / "planner-ai"


def test_get_config_dir_win32_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_mod.sys, "platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(
        config_mod.Path,
        "home",
        staticmethod(lambda: Path(r"C:\Users\test")),
    )
    assert get_config_dir() == (
        Path(r"C:\Users\test") / "AppData" / "Roaming" / "planner-ai"
    )


def test_get_config_path(config_home: Path) -> None:
    assert get_config_path() == config_home / "config.json"


def test_load_config_missing_file(config_home: Path) -> None:
    assert load_config() == {}


def test_load_config_invalid_json(config_home: Path) -> None:
    (config_home / "config.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_config()


def test_load_drops_unknown_and_invalid_selection(config_home: Path) -> None:
    payload = {
        "claudeCodeOAuthToken": "tok",
        "unknownField": "nope",
        "includeMocks": False,
        "modelSelection": {
            "proposers": [{"provider": "nope", "modelId": "x"}],
            "consensus": {"provider": "cursor", "modelId": "auto"},
        },
    }
    (config_home / "config.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    assert load_config() == {"claudeCodeOAuthToken": "tok"}


def test_load_keeps_valid_selection_with_trimmed_model_ids(
    config_home: Path,
) -> None:
    payload = {
        "modelSelection": {
            "proposers": [
                {"provider": "cursor", "modelId": "  composer-2.5  "},
                {"provider": "bad", "modelId": "x"},
                {"modelId": "only-id"},
            ],
            "consensus": {"provider": "anthropic", "modelId": "  claude  "},
        },
        "includeMocks": True,
    }
    path = config_home / "config.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    before = path.stat().st_mtime_ns
    time.sleep(0.02)
    loaded = load_config()
    assert loaded == {
        "modelSelection": {
            "proposers": [
                {"provider": "cursor", "modelId": "composer-2.5"},
            ],
            "consensus": {"provider": "anthropic", "modelId": "claude"},
        },
        "includeMocks": True,
    }
    # Trimmed modelIds alone must not rewrite the file.
    assert path.stat().st_mtime_ns == before


def test_round_trip_save_and_load(config_home: Path) -> None:
    saved = save_config(
        {
            "claudeCodeOAuthToken": "claude-tok",
            "cursorApiKey": "cursor-tok",
            "codexApiKey": "codex-tok",
            "modelSelection": {
                "proposers": [
                    {"provider": "anthropic", "modelId": "claude-sonnet"},
                    {"provider": "cursor", "modelId": "composer-2.5"},
                ],
                "consensus": {"provider": "codex", "modelId": "gpt-5.2"},
            },
            "includeMocks": True,
        }
    )
    assert saved == load_config()
    mode = (config_home / "config.json").stat().st_mode & 0o777
    assert mode == 0o600


def test_save_empty_token_clears_key(config_home: Path) -> None:
    save_config({"cursorApiKey": "keep-me", "codexApiKey": "drop-me"})
    next_cfg = save_config({"codexApiKey": "  \n  "})
    assert next_cfg == {"cursorApiKey": "keep-me"}
    assert "codexApiKey" not in load_config()


def test_save_include_mocks_false_omits_key(config_home: Path) -> None:
    save_config({"includeMocks": True, "cursorApiKey": "k"})
    next_cfg = save_config({"includeMocks": False})
    assert next_cfg == {"cursorApiKey": "k"}
    assert "includeMocks" not in next_cfg


def test_clear_credentials(config_home: Path) -> None:
    save_config(
        {
            "claudeCodeOAuthToken": "a",
            "cursorApiKey": "b",
            "codexApiKey": "c",
            "includeMocks": True,
        }
    )
    next_cfg = clear_credentials(
        ["claudeCodeOAuthToken", "cursorApiKey", "codexApiKey"]
    )
    assert next_cfg == {"includeMocks": True}


def test_dirty_token_rewrites_sanitized_file(config_home: Path) -> None:
    path = config_home / "config.json"
    path.write_text(
        json.dumps({"cursorApiKey": "ab cd\nef"}, indent=2) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o644)
    loaded = load_config()
    assert loaded == {"cursorApiKey": "abcdef"}
    rewritten = json.loads(path.read_text(encoding="utf-8"))
    assert rewritten == {"cursorApiKey": "abcdef"}
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600
    assert not (path.stat().st_mode & stat.S_IROTH)


def test_clean_token_does_not_rewrite(config_home: Path) -> None:
    path = config_home / "config.json"
    path.write_text(
        json.dumps(
            {
                "cursorApiKey": "clean-token",
                "extraIgnored": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    before = path.read_bytes()
    before_mtime = path.stat().st_mtime_ns
    time.sleep(0.02)
    loaded = load_config()
    assert loaded == {"cursorApiKey": "clean-token"}
    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == before_mtime


def test_typescript_shaped_fixture_loads_without_rewrite(
    config_home: Path,
) -> None:
    # Mimics JSON.stringify(config, null, 2) from the TypeScript app.
    body = """{
  "claudeCodeOAuthToken": "oauth-token",
  "cursorApiKey": "cursor-key",
  "codexApiKey": "codex-key",
  "modelSelection": {
    "proposers": [
      {
        "provider": "anthropic",
        "modelId": "claude-sonnet-4-5"
      },
      {
        "provider": "cursor",
        "modelId": "composer-2.5"
      }
    ],
    "consensus": {
      "provider": "codex",
      "modelId": "gpt-5.2"
    }
  },
  "includeMocks": true,
  "futureField": "ignored"
}
"""
    path = config_home / "config.json"
    path.write_text(body, encoding="utf-8")
    before = path.read_bytes()
    loaded = load_config()
    assert loaded == {
        "claudeCodeOAuthToken": "oauth-token",
        "cursorApiKey": "cursor-key",
        "codexApiKey": "codex-key",
        "modelSelection": {
            "proposers": [
                {"provider": "anthropic", "modelId": "claude-sonnet-4-5"},
                {"provider": "cursor", "modelId": "composer-2.5"},
            ],
            "consensus": {"provider": "codex", "modelId": "gpt-5.2"},
        },
        "includeMocks": True,
    }
    assert path.read_bytes() == before
