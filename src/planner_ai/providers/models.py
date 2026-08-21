from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request
from typing import Literal, TypedDict, get_args

ProviderKind = Literal["anthropic", "cursor", "codex", "mock"]

ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_OAUTH_BETA = "oauth-2025-04-20"


class ModelChoice(TypedDict):
    provider: ProviderKind
    modelId: str
    label: str


class ModelPick(TypedDict):
    provider: ProviderKind
    modelId: str


class ModelSelection(TypedDict):
    proposers: list[ModelPick]
    consensus: ModelPick


class ProviderCredentialsForModels(TypedDict, total=False):
    claudeCodeOAuthToken: str
    cursorApiKey: str
    codexApiKey: str


class AvailableChoicesOptions(TypedDict, total=False):
    includeMocks: bool
    codexAuthenticated: bool


_PROVIDER_KINDS: frozenset[str] = frozenset(get_args(ProviderKind))

CURSOR_FALLBACK_MODELS: list[ModelChoice] = [
    {
        "provider": "cursor",
        "modelId": "composer-2.5",
        "label": "Composer 2.5",
    },
    {
        "provider": "cursor",
        "modelId": "auto",
        "label": "Cursor Auto",
    },
]

CODEX_FALLBACK_MODELS: list[ModelChoice] = [
    {"provider": "codex", "modelId": "gpt-5.6-sol", "label": "GPT-5.6 Sol"},
    {"provider": "codex", "modelId": "gpt-5.6-terra", "label": "GPT-5.6 Terra"},
    {"provider": "codex", "modelId": "gpt-5.6-luna", "label": "GPT-5.6 Luna"},
    {"provider": "codex", "modelId": "gpt-5.5", "label": "GPT-5.5"},
    {"provider": "codex", "modelId": "gpt-5.2", "label": "GPT-5.2"},
]

MOCK_MODELS: list[ModelChoice] = [
    {"provider": "mock", "modelId": "alpha", "label": "Model Alpha (mock)"},
    {"provider": "mock", "modelId": "beta", "label": "Model Beta (mock)"},
    {"provider": "mock", "modelId": "gamma", "label": "Model Gamma (mock)"},
]


def _non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def _choice_key(choice: ModelPick) -> str:
    return f"{choice['provider']}:{choice['modelId']}"


def _source_label(provider: ProviderKind) -> str:
    if provider == "anthropic":
        return "claude"
    return provider


def load_codex_choices() -> list[ModelChoice]:
    return list(CODEX_FALLBACK_MODELS)


def format_choice_label(choice: ModelChoice) -> str:
    return (
        f"{choice['label']} · {_source_label(choice['provider'])} · {choice['modelId']}"
    )


def find_choice_label(choices: list[ModelChoice], pick: ModelPick) -> str:
    for choice in choices:
        if (
            choice["provider"] == pick["provider"]
            and choice["modelId"] == pick["modelId"]
        ):
            return choice["label"]
    return f"{pick['provider']}:{pick['modelId']}"


def _anthropic_model_choice(raw: object) -> ModelChoice | None:
    if not isinstance(raw, dict):
        return None
    model_id = raw.get("id")
    if not isinstance(model_id, str) or not model_id.strip():
        return None
    model_id = model_id.strip()
    display_name = raw.get("display_name")
    if isinstance(display_name, str) and display_name.strip():
        label = display_name.strip()
    else:
        label = model_id
    return {"provider": "anthropic", "modelId": model_id, "label": label}


def _http_get_json(url: str, headers: dict[str, str]) -> object:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request) as response:
        if response.status != 200:
            raise OSError(f"HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def _load_anthropic_choices_sync(oauth_token: str) -> list[ModelChoice]:
    try:
        listed: list[ModelChoice] = []
        seen: set[str] = set()
        after_id: str | None = None

        while True:
            query: dict[str, str] = {"limit": "1000"}
            if after_id:
                query["after_id"] = after_id
            url = f"{ANTHROPIC_MODELS_URL}?{urllib.parse.urlencode(query)}"
            page = _http_get_json(
                url,
                {
                    "anthropic-version": ANTHROPIC_VERSION,
                    "anthropic-beta": ANTHROPIC_OAUTH_BETA,
                    "Authorization": f"Bearer {oauth_token}",
                },
            )
            if not isinstance(page, dict):
                return []

            rows = page.get("data")
            if not isinstance(rows, list):
                rows = []

            for row in rows:
                choice = _anthropic_model_choice(row)
                if choice is None or choice["modelId"] in seen:
                    continue
                seen.add(choice["modelId"])
                listed.append(choice)

            if not page.get("has_more"):
                break
            last_id = page.get("last_id")
            next_id = (
                last_id.strip()
                if isinstance(last_id, str) and last_id.strip()
                else None
            )
            if next_id is None or next_id == after_id:
                break
            after_id = next_id

        return listed
    except Exception:
        return []


async def load_anthropic_choices(oauth_token: str) -> list[ModelChoice]:
    """List Claude models via Anthropic Models API using a Claude Code OAuth token."""
    return await asyncio.to_thread(_load_anthropic_choices_sync, oauth_token)


def _model_attr(model: object, *names: str) -> object:
    if isinstance(model, dict):
        for name in names:
            if name in model:
                return model[name]
        return None
    for name in names:
        if hasattr(model, name):
            return getattr(model, name)
    return None


def _list_cursor_models(api_key: str) -> list[object]:
    from cursor_sdk import Cursor

    return list(Cursor.models.list(api_key=api_key))


def _load_cursor_choices_sync(api_key: str) -> list[ModelChoice]:
    try:
        models = _list_cursor_models(api_key)
        listed: list[ModelChoice] = []
        seen: set[str] = set()

        for model in models:
            raw_id = _model_attr(model, "id")
            model_id = raw_id.strip() if isinstance(raw_id, str) else ""
            if not model_id or model_id in seen:
                continue
            seen.add(model_id)
            display_name = _model_attr(model, "display_name", "displayName")
            if isinstance(display_name, str) and display_name.strip():
                label = display_name.strip()
            else:
                label = model_id
            listed.append(
                {"provider": "cursor", "modelId": model_id, "label": label}
            )

        if len(listed) == 0:
            return list(CURSOR_FALLBACK_MODELS)

        for fallback in CURSOR_FALLBACK_MODELS:
            if fallback["modelId"] not in seen:
                listed.append(fallback)

        return listed
    except Exception:
        return list(CURSOR_FALLBACK_MODELS)


async def load_cursor_choices(api_key: str) -> list[ModelChoice]:
    return await asyncio.to_thread(_load_cursor_choices_sync, api_key)


async def available_choices(
    creds: ProviderCredentialsForModels,
    opts: AvailableChoicesOptions | None = None,
) -> list[ModelChoice]:
    claude_token = _non_empty(creds.get("claudeCodeOAuthToken"))
    cursor_key = _non_empty(creds.get("cursorApiKey"))
    codex_key = _non_empty(creds.get("codexApiKey"))
    choices: list[ModelChoice] = []

    if claude_token:
        choices.extend(await load_anthropic_choices(claude_token))

    if cursor_key:
        choices.extend(await load_cursor_choices(cursor_key))

    codex_authenticated = (
        codex_key is not None
        or (opts is not None and opts.get("codexAuthenticated") is True)
    )
    if codex_authenticated:
        choices.extend(load_codex_choices())

    include_mocks = opts is not None and opts.get("includeMocks") is True
    show_mocks = include_mocks or (
        not claude_token and not cursor_key and not codex_authenticated
    )
    if show_mocks:
        choices.extend(MOCK_MODELS)

    return choices


def default_selection(choices: list[ModelChoice]) -> ModelSelection | None:
    anthropic = [c for c in choices if c["provider"] == "anthropic"]
    cursor = [c for c in choices if c["provider"] == "cursor"]
    codex = [c for c in choices if c["provider"] == "codex"]
    mock = [c for c in choices if c["provider"] == "mock"]

    proposers: list[ModelPick] = []

    if anthropic:
        proposers.append(
            {"provider": anthropic[0]["provider"], "modelId": anthropic[0]["modelId"]}
        )
    if cursor:
        proposers.append(
            {"provider": cursor[0]["provider"], "modelId": cursor[0]["modelId"]}
        )
    if codex:
        proposers.append(
            {"provider": codex[0]["provider"], "modelId": codex[0]["modelId"]}
        )
    if len(proposers) == 0 and mock:
        proposers.extend(
            {"provider": c["provider"], "modelId": c["modelId"]} for c in mock[:2]
        )

    if len(proposers) == 0:
        return None

    if anthropic:
        consensus: ModelPick = {
            "provider": anthropic[0]["provider"],
            "modelId": anthropic[0]["modelId"],
        }
    elif cursor:
        consensus = {
            "provider": cursor[0]["provider"],
            "modelId": cursor[0]["modelId"],
        }
    elif codex:
        consensus = {
            "provider": codex[0]["provider"],
            "modelId": codex[0]["modelId"],
        }
    else:
        consensus = {
            "provider": mock[0]["provider"],
            "modelId": mock[0]["modelId"],
        }

    return {"proposers": proposers, "consensus": consensus}


def _normalize_pick(raw: object) -> ModelPick | None:
    if not isinstance(raw, dict):
        return None
    provider = raw.get("provider")
    model_id = raw.get("modelId")
    if provider not in _PROVIDER_KINDS:
        return None
    if not isinstance(model_id, str) or not model_id.strip():
        return None
    return {"provider": provider, "modelId": model_id.strip()}  # type: ignore[typeddict-item]


def normalize_selection(
    raw: object,
    choices: list[ModelChoice],
) -> ModelSelection | None:
    if not isinstance(raw, dict):
        return None

    allowed = {_choice_key(choice) for choice in choices}

    proposers_raw = raw.get("proposers")
    if not isinstance(proposers_raw, list):
        return None

    proposers: list[ModelPick] = []
    for item in proposers_raw:
        pick = _normalize_pick(item)
        if pick is None:
            continue
        key = _choice_key(pick)
        if key not in allowed:
            continue
        if any(_choice_key(existing) == key for existing in proposers):
            continue
        proposers.append(pick)

    consensus = _normalize_pick(raw.get("consensus"))
    if consensus is None or _choice_key(consensus) not in allowed:
        return None
    if len(proposers) == 0:
        return None

    return {"proposers": proposers, "consensus": consensus}


def resolve_initial_selection(
    saved: object,
    choices: list[ModelChoice],
) -> ModelSelection:
    normalized = normalize_selection(saved, choices)
    if normalized is not None:
        return normalized
    default = default_selection(choices)
    if default is not None:
        return default
    return {
        "proposers": [{"provider": "mock", "modelId": "alpha"}],
        "consensus": {"provider": "mock", "modelId": "alpha"},
    }
