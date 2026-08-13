from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Literal, TypedDict, get_args

from planner_ai.providers.models import ModelPick, ModelSelection, ProviderKind

ConfigCredentialKey = Literal[
    "claudeCodeOAuthToken",
    "cursorApiKey",
    "codexApiKey",
]


class AppConfig(TypedDict, total=False):
    claudeCodeOAuthToken: str
    cursorApiKey: str
    codexApiKey: str
    modelSelection: ModelSelection
    includeMocks: bool


APP_NAME = "planner-ai"
CONFIG_FILENAME = "config.json"

_PROVIDER_KINDS: frozenset[str] = frozenset(get_args(ProviderKind))


def get_config_dir() -> Path:
    match sys.platform:
        case "darwin":
            return Path.home() / "Library" / "Application Support" / APP_NAME
        case "win32":
            appdata = os.environ.get("APPDATA")
            base = (
                Path(appdata)
                if appdata
                else Path.home() / "AppData" / "Roaming"
            )
            return base / APP_NAME
        case _:
            xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
            base = Path(xdg) if xdg else Path.home() / ".config"
            return base / APP_NAME


def get_config_path() -> Path:
    return get_config_dir() / CONFIG_FILENAME


def sanitize_token(value: str) -> str:
    """Strip all whitespace so pasted line breaks cannot poison Authorization headers."""
    return re.sub(r"\s+", "", value)


def _field_needs_rewrite(raw: object) -> bool:
    return isinstance(raw, str) and sanitize_token(raw) != raw


def _is_provider_kind(value: object) -> bool:
    return isinstance(value, str) and value in _PROVIDER_KINDS


def _normalize_model_selection(raw: object) -> ModelSelection | None:
    if not isinstance(raw, dict):
        return None

    proposers_raw = raw.get("proposers")
    if not isinstance(proposers_raw, list):
        return None

    proposers: list[ModelPick] = []
    for item in proposers_raw:
        if not isinstance(item, dict):
            continue
        provider = item.get("provider")
        model_id = item.get("modelId")
        if not _is_provider_kind(provider):
            continue
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        proposers.append(
            {
                "provider": provider,  # type: ignore[typeddict-item]
                "modelId": model_id.strip(),
            }
        )

    consensus_raw = raw.get("consensus")
    if not isinstance(consensus_raw, dict) or len(proposers) == 0:
        return None

    consensus_provider = consensus_raw.get("provider")
    consensus_model_id = consensus_raw.get("modelId")
    if not _is_provider_kind(consensus_provider):
        return None
    if not isinstance(consensus_model_id, str) or not consensus_model_id.strip():
        return None

    return {
        "proposers": proposers,
        "consensus": {
            "provider": consensus_provider,  # type: ignore[typeddict-item]
            "modelId": consensus_model_id.strip(),
        },
    }


def _normalize_config(raw: object) -> AppConfig:
    if not isinstance(raw, dict):
        return {}

    config: AppConfig = {}

    for key in (
        "claudeCodeOAuthToken",
        "cursorApiKey",
        "codexApiKey",
    ):
        value = raw.get(key)
        if isinstance(value, str):
            sanitized = sanitize_token(value)
            if sanitized:
                config[key] = sanitized  # type: ignore[literal-required]

    model_selection = _normalize_model_selection(raw.get("modelSelection"))
    if model_selection is not None:
        config["modelSelection"] = model_selection

    if raw.get("includeMocks") is True:
        config["includeMocks"] = True

    return config


def _write_config_file(config: AppConfig) -> None:
    directory = get_config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = get_config_path()
    body = f"{json.dumps(config, indent=2)}\n"
    # Write a sibling temp file with 0o600, then replace so an existing
    # world-readable config is recreated with the correct mode.
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(
        tmp_path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    try:
        os.write(fd, body.encode("utf-8"))
    except Exception:
        os.close(fd)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    else:
        os.close(fd)
    os.replace(tmp_path, path)


def load_config() -> AppConfig:
    path = get_config_path()
    try:
        body = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}

    parsed = json.loads(body)
    normalized = _normalize_config(parsed)

    if isinstance(parsed, dict) and (
        _field_needs_rewrite(parsed.get("claudeCodeOAuthToken"))
        or _field_needs_rewrite(parsed.get("cursorApiKey"))
        or _field_needs_rewrite(parsed.get("codexApiKey"))
    ):
        _write_config_file(normalized)

    return normalized


def save_config(partial: AppConfig) -> AppConfig:
    current = load_config()
    next_config: AppConfig = {**current}

    if "claudeCodeOAuthToken" in partial:
        value = sanitize_token(partial["claudeCodeOAuthToken"])
        if value:
            next_config["claudeCodeOAuthToken"] = value
        else:
            next_config.pop("claudeCodeOAuthToken", None)

    if "cursorApiKey" in partial:
        value = sanitize_token(partial["cursorApiKey"])
        if value:
            next_config["cursorApiKey"] = value
        else:
            next_config.pop("cursorApiKey", None)

    if "codexApiKey" in partial:
        value = sanitize_token(partial["codexApiKey"])
        if value:
            next_config["codexApiKey"] = value
        else:
            next_config.pop("codexApiKey", None)

    if "modelSelection" in partial:
        next_config["modelSelection"] = partial["modelSelection"]

    if "includeMocks" in partial:
        if partial["includeMocks"]:
            next_config["includeMocks"] = True
        else:
            next_config.pop("includeMocks", None)

    _write_config_file(next_config)
    return next_config


def clear_credentials(keys: list[ConfigCredentialKey]) -> AppConfig:
    partial: AppConfig = {}
    for key in keys:
        partial[key] = ""
    return save_config(partial)
