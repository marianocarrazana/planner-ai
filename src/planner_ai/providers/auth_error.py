from __future__ import annotations

import re
from typing import Literal

from planner_ai.config import ConfigCredentialKey
from planner_ai.pipeline.types import ProposalState

AuthRecoveryTarget = ConfigCredentialKey | Literal["codexSession"]

AUTH_ERROR_PATTERNS = [
    re.compile(r"invalid auth", re.I),
    re.compile(r"unauthorized", re.I),
    re.compile(r"\b401\b"),
    re.compile(r"invalid authorization", re.I),
    re.compile(r"invalid api key", re.I),
    re.compile(r"expired token", re.I),
    re.compile(r"authentication", re.I),
    re.compile(r"missing external auth", re.I),
]


def is_auth_error_message(message: str) -> bool:
    return any(pattern.search(message) for pattern in AUTH_ERROR_PATTERNS)


def credential_key_for_provider(
    kind: str,
    *,
    codex_uses_config_key: bool = True,
) -> AuthRecoveryTarget | None:
    base = kind[: kind.index(":")] if ":" in kind else kind
    match base:
        case "anthropic":
            return "claudeCodeOAuthToken"
        case "cursor":
            return "cursorApiKey"
        case "codex":
            return "codexApiKey" if codex_uses_config_key else "codexSession"
        case _:
            return None


def collect_failing_credential_keys(
    *,
    proposals: list[ProposalState],
    error_message: str,
    consensus_source: str,
    codex_uses_config_key: bool = True,
) -> list[AuthRecoveryTarget]:
    keys: set[AuthRecoveryTarget] = set()

    for proposal in proposals:
        if proposal.status != "error" or not proposal.error:
            continue
        if not is_auth_error_message(proposal.error):
            continue
        key = credential_key_for_provider(
            proposal.id,
            codex_uses_config_key=codex_uses_config_key,
        )
        if key:
            keys.add(key)

    if is_auth_error_message(error_message):
        key = credential_key_for_provider(
            consensus_source,
            codex_uses_config_key=codex_uses_config_key,
        )
        if key:
            keys.add(key)

        # Top-level errors often come from a proposer (e.g. "All proposals failed"
        # is not auth-like, but the thrown SDK message can be). Map by message alone
        # when consensus source is mock but a real provider failed auth.
        if len(keys) == 0:
            if re.search(
                r"claude|anthropic|CLAUDE_CODE_OAUTH",
                error_message,
                re.I,
            ):
                keys.add("claudeCodeOAuthToken")
            if re.search(r"cursor", error_message, re.I):
                keys.add("cursorApiKey")
            if re.search(
                r"codex|openai|CODEX_API_KEY",
                error_message,
                re.I,
            ):
                keys.add(
                    "codexApiKey"
                    if codex_uses_config_key
                    else "codexSession"
                )

    return list(keys)
